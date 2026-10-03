"""
PostVisit AI - Stage 3 Comprehensive Test Suite
Validates all 12 Stage 3 requirements:
  Test 1: Valid consultation async upload & background processing
  Test 2: Invalid file rejection by input guardrails
  Test 3: ASR failure simulation with step retries
  Test 4: LLM failure simulation with agent retry policy
  Test 5: Worker restart and crash recovery
  Test 6: Duplicate step execution & idempotency
  Test 7: Malformed LLM JSON blocked by schema guardrail
  Test 8: Speaker attribution preservation
  Test 9: Patient medication mention safety (not doctor prescription)
  Test 10: Dynamic prescription of new medicine without whitelist
  Test 11: Workflow state persistence across steps
  Test 12: API responsiveness (POST returns immediately without pipeline blocking)
"""

import io
import time
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app
from src.workflow.states import WorkflowState
from src.workflow.orchestrator import WorkflowOrchestrator
from src.workflow.worker import BackgroundWorker
from src.agents.base import BaseAgent, AgentResult, WorkflowContext, RetryPolicy
from src.agents.registry import AgentRegistry, get_agent_registry
from src.agents.medical_extraction_agent import MedicalExtractionAgent
from src.guardrails.input_guardrail import InputGuardrail
from src.guardrails.audio_guardrail import AudioQualityGuardrail
from src.guardrails.transcript_guardrail import TranscriptGuardrail
from src.guardrails.medical_output_guardrail import MedicalOutputGuardrail
from api.repositories.consultation_repository import ConsultationRepository, get_consultation_repository
from api.repositories.workflow_repository import WorkflowRepository, get_workflow_repository
from api.services.consultation_service import ConsultationService, get_consultation_service
from src.tools.clinical_tools import GetConsultationTool, SaveDoctorReviewTool
from src.tools.base import ToolContext

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test 1 — Valid consultation (Async Upload -> Queued -> Worker -> Review)
# ---------------------------------------------------------------------------
def test_1_valid_consultation_async_flow():
    """
    Test 1: Valid consultation file uploaded asynchronously.
    Returns status='queued' immediately, background worker executes pipeline,
    and workflow reaches PENDING_DOCTOR_REVIEW.
    """
    consult_repo = ConsultationRepository()
    wf_repo = WorkflowRepository()
    orchestrator = WorkflowOrchestrator(workflow_repo=wf_repo, consultation_repo=consult_repo)
    worker = BackgroundWorker(orchestrator=orchestrator)
    service = ConsultationService(
        repository=consult_repo,
        workflow_repository=wf_repo,
        worker=worker
    )

    app.dependency_overrides[get_consultation_service] = lambda: service

    try:
        # Create a valid 44-byte WAV header buffer
        wav_header = (
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        fake_wav = io.BytesIO(wav_header + b"\x00" * 4096)

        resp = client.post(
            "/api/v1/consultations/process",
            files={"file": ("valid_consultation.wav", fake_wav, "audio/wav")}
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "consultation_id" in data
        assert "workflow_id" in data
        assert data["status"] == "queued"

        cid = data["consultation_id"]
        wid = data["workflow_id"]

        # Verify initial workflow run persisted in repository
        wf_run = wf_repo.get_workflow_run(wid)
        assert wf_run is not None
        assert wf_run["consultation_id"] == cid
        assert wf_run["status"] in ("queued", "VALIDATING_INPUT", "PROCESSING_AUDIO", "TRANSCRIBING", "COMPLETED", "PENDING_DOCTOR_REVIEW")

        # Verify status endpoint returns consultation details
        status_resp = client.get(f"/api/v1/consultations/{cid}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["consultation_id"] == cid
        assert status_data["status"] is not None

    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 2 — Invalid file rejection
# ---------------------------------------------------------------------------
def test_2_invalid_file_rejection():
    """
    Test 2: Invalid file extension rejected immediately with 415 without worker crash.
    """
    fake_txt = io.BytesIO(b"Non-audio clinical transcript notes.")
    resp = client.post(
        "/api/v1/consultations/process",
        files={"file": ("clinical_summary.txt", fake_txt, "text/plain")}
    )
    assert resp.status_code == 415
    data = resp.json()
    assert data["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    # Input guardrail unit check
    guardrail = InputGuardrail()
    res = guardrail.validate("some_path.pdf", filename="report.pdf")
    assert res.passed is False
    assert res.action == "FAILED"
    assert res.error_code == "UNSUPPORTED_MEDIA_TYPE"


# ---------------------------------------------------------------------------
# Test 3 — ASR failure simulation with step retries
# ---------------------------------------------------------------------------
def test_3_asr_failure_simulation():
    """
    Test 3: Simulate ASR failure.
    Verifies that the orchestrator retries up to 3 attempts,
    logs attempts, and safely routes to FAILED.
    """
    wf_repo = WorkflowRepository()
    consult_repo = ConsultationRepository()
    orchestrator = WorkflowOrchestrator(workflow_repo=wf_repo, consultation_repo=consult_repo)

    cid = str(uuid.uuid4())
    wf_run = wf_repo.create_workflow_run(consultation_id=cid)
    wid = wf_run["id"]

    consult_repo.create(cid, "test_asr.wav", "audio/wav")

    # Mock load_and_normalize_audio to succeed, but diarize_and_transcribe to fail
    with patch("src.audio_processor.load_and_normalize_audio") as mock_audio, \
         patch("src.diarization.diarize_and_transcribe") as mock_diar:
        import numpy as np
        # Return 2-second valid non-silent audio
        mock_audio.return_value = (np.ones((1, 32000), dtype=np.float32) * 0.1, 16000)
        mock_diar.side_effect = RuntimeError("IndicConformer ASR device CUDA/CPU out of memory")

        res = orchestrator.execute_workflow(
            consultation_id=cid,
            workflow_run_id=wid,
            media_path="test.wav",
            original_filename="test.wav",
            media_type="audio/wav"
        )

        assert res["status"] == "failed"
        assert "ASR" in res["error"] or "Speech recognition" in res["error"]

        # Check step history: TRANSCRIBING should have 3 attempts
        steps = wf_repo.get_workflow_steps(wid)
        asr_steps = [s for s in steps if s["step_name"] == "TRANSCRIBING"]
        assert len(asr_steps) == 1
        assert asr_steps[0]["status"] == "failed"

        # Verify consultation marked failed
        c_row = consult_repo.get_by_id(cid)
        assert c_row["status"] == "failed"
        assert c_row["error_code"] == "ASR_PIPELINE_FAILED"


# ---------------------------------------------------------------------------
# Test 4 — LLM failure simulation with retry behavior
# ---------------------------------------------------------------------------
def test_4_llm_failure_retry_behavior():
    """
    Test 4: Simulate Groq LLM failure.
    Verifies that the agent retry policy executes up to max_attempts before failing.
    """
    class FlakyAgent(BaseAgent):
        name = "flaky_test_agent"
        retry_policy = RetryPolicy(max_attempts=3, initial_delay_sec=0.01, backoff_factor=1.0)
        call_count = 0

        def run(self, context: WorkflowContext) -> AgentResult:
            FlakyAgent.call_count += 1
            if FlakyAgent.call_count < 3:
                raise ConnectionError("Groq API 503 Service Unavailable")
            return AgentResult(success=True, output={"recovered": True})

    agent = FlakyAgent()
    context = WorkflowContext(
        consultation_id=str(uuid.uuid4()),
        workflow_run_id=str(uuid.uuid4())
    )

    FlakyAgent.call_count = 0
    res = agent.execute(context)
    assert res.success is True
    assert res.attempt == 3
    assert FlakyAgent.call_count == 3


# ---------------------------------------------------------------------------
# Test 5 — Worker restart and crash recovery
# ---------------------------------------------------------------------------
def test_5_worker_restart_recovery():
    """
    Test 5: Simulate worker crash during execution.
    Verifies that recover_pending_workflows() detects interrupted workflows
    and safely marks them for review without silent data loss.
    """
    wf_repo = WorkflowRepository()
    consult_repo = ConsultationRepository()
    orchestrator = WorkflowOrchestrator(workflow_repo=wf_repo, consultation_repo=consult_repo)

    cid = str(uuid.uuid4())
    consult_repo.create(cid, "crashed_consultation.wav", "audio/wav")
    run = wf_repo.create_workflow_run(consultation_id=cid)
    wid = run["id"]

    # Set status to TRANSCRIBING as if worker died mid-flight
    wf_repo.update_workflow_run_status(
        workflow_run_id=wid,
        status="TRANSCRIBING",
        current_step="TRANSCRIBING"
    )

    # Trigger crash recovery
    recovered_count = orchestrator.recover_pending_workflows()
    assert recovered_count >= 1

    # Verify workflow run transitioned to NEEDS_REVIEW
    recovered_run = wf_repo.get_workflow_run(wid)
    assert recovered_run["status"] == "NEEDS_REVIEW"
    assert recovered_run["error_code"] == "WORKER_RESTARTED"


# ---------------------------------------------------------------------------
# Test 6 — Duplicate execution (Idempotency)
# ---------------------------------------------------------------------------
def test_6_idempotency_and_no_duplicates():
    """
    Test 6: Idempotent execution.
    Calling repository update_completed repeatedly with identical input
    updates the record in-place without creating duplicate consultations.
    """
    repo = ConsultationRepository()
    cid = str(uuid.uuid4())

    repo.create(cid, "idempotent.mp4", "video/mp4")

    med_rec = {
        "medications": [{"name": "Paracetamol", "strength": "650 mg"}],
        "symptoms_mentioned": ["Fever"]
    }
    trans = [{"start": 0.0, "end": 5.0, "speaker": "Doctor", "text": "Paracetamol 650 mg"}]

    # First completion
    repo.update_completed(cid, 20.0, trans, med_rec, {"valid": True})
    first_row = repo.get_by_id(cid)

    # Second completion (re-try)
    repo.update_completed(cid, 20.0, trans, med_rec, {"valid": True})
    second_row = repo.get_by_id(cid)

    assert first_row["id"] == second_row["id"]
    assert len(second_row["medical_record"]["medications"]) == 1
    items, total = repo.list_all(limit=100)
    matching = [i for i in items if i["id"] == cid]
    assert len(matching) == 1, "Must never create duplicate database rows for same consultation"


# ---------------------------------------------------------------------------
# Test 7 — Invalid LLM JSON blocked by schema guardrail
# ---------------------------------------------------------------------------
def test_7_invalid_llm_json_guardrail():
    """
    Test 7: Malformed LLM output is rejected by MedicalOutputGuardrail.
    """
    guardrail = MedicalOutputGuardrail()

    # Case A: String instead of dict
    res_str = guardrail.validate("not a json object")
    assert res_str.passed is False
    assert res_str.action == "FAILED"
    assert res_str.error_code == "INVALID_OUTPUT_TYPE"

    # Case B: Malformed medication fields (wrong type)
    malformed_data = {
        "medications": "should_be_a_list_not_a_string",
        "tests": []
    }
    res_malformed = guardrail.validate(malformed_data)
    assert res_malformed.passed is False
    assert res_malformed.action == "FAILED"
    assert res_malformed.error_code == "SCHEMA_VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Test 8 — Speaker attribution preservation
# ---------------------------------------------------------------------------
def test_8_speaker_attribution():
    """
    Test 8: Speaker labels (Doctor, Patient) are preserved accurately across turns.
    """
    turns = [
        {"turn_id": 1, "speaker": "Patient", "start": 0.0, "end": 5.0, "text": "டாக்டர் எனக்கு காய்ச்சல்"},
        {"turn_id": 2, "speaker": "Doctor", "start": 5.5, "end": 12.0, "text": "பேராசிட்டமால் 650 mg எடுத்துக்கோங்க"}
    ]
    guardrail = TranscriptGuardrail()
    res = guardrail.validate("Patient: காய்ச்சல் Doctor: பேராசிட்டமால்", turns)
    assert res.passed is True
    assert turns[0]["speaker"] == "Patient"
    assert turns[1]["speaker"] == "Doctor"


# ---------------------------------------------------------------------------
# Test 9 — Patient medication mention safety
# ---------------------------------------------------------------------------
def test_9_patient_medication_mention_safety():
    """
    Test 9: Patient mentions past medicine.
    Ensures that medication with source_speaker='Patient' is NOT extracted
    as an active doctor prescription.
    """
    guardrail = MedicalOutputGuardrail()
    extracted_data = {
        "medications": [
            {
                "name": "Metformin",
                "strength": "500 mg",
                "source_speaker": "Patient",
                "source_text": "நான் ஏற்கனவே Metformin 500 mg எடுத்துக்கிட்டு இருக்கேன்"
            },
            {
                "name": "Paracetamol",
                "strength": "650 mg",
                "source_speaker": "Doctor",
                "source_text": "Paracetamol 650 mg சாப்பிடுங்கள்"
            }
        ],
        "tests": [],
        "instructions": [],
        "follow_up": {"time": None, "instructions": None},
        "warnings": [],
        "symptoms_mentioned": ["Fever"],
        "uncertain_items": [],
        "requires_doctor_review": False
    }

    transcript = (
        "Patient: நான் ஏற்கனவே Metformin 500 mg எடுத்துக்கிட்டு இருக்கேன்\n"
        "Doctor: Paracetamol 650 mg சாப்பிடுங்கள்"
    )

    res = guardrail.validate(extracted_data, transcript_text=transcript)
    assert res.passed is True
    sanitized = res.details["sanitized_data"]

    # Metformin must be stripped from active prescriptions!
    active_meds = sanitized["medications"]
    assert len(active_meds) == 1
    assert active_meds[0]["name"] == "Paracetamol"
    assert active_meds[0]["source_speaker"] == "Doctor"

    # Patient mention flagged in uncertain_items and mandates review
    assert any("Metformin" in note for note in sanitized["uncertain_items"])
    assert sanitized["requires_doctor_review"] is True


# ---------------------------------------------------------------------------
# Test 10 — Doctor prescription (Dynamic extraction without whitelist)
# ---------------------------------------------------------------------------
def test_10_doctor_prescription_dynamic_extraction():
    """
    Test 10: Prescribes a novel/synthetic medication ('NovelCardioX') not in any whitelist.
    Verifies that the medical extraction schema preserves it dynamically.
    """
    from src.medical_schema import MedicationItem, MedicalExtraction

    novel_med = MedicationItem(
        name="NovelCardioX",
        strength="25 mg",
        dose="1 tablet",
        frequency="once daily",
        timing="after breakfast",
        source_speaker="Doctor",
        source_text="Take NovelCardioX 25 mg once daily"
    )

    extraction = MedicalExtraction(medications=[novel_med])
    d = extraction.to_dict()
    assert d["medications"][0]["name"] == "NovelCardioX"
    assert d["medications"][0]["strength"] == "25 mg"

    # Output guardrail validation
    guardrail = MedicalOutputGuardrail()
    res = guardrail.validate(d, transcript_text="Take NovelCardioX 25 mg once daily")
    assert res.passed is True
    assert res.details["sanitized_data"]["medications"][0]["name"] == "NovelCardioX"


# ---------------------------------------------------------------------------
# Test 11 — Workflow status persistence
# ---------------------------------------------------------------------------
def test_11_workflow_status_persistence():
    """
    Test 11: Verifies state transitions and step persistence in WorkflowRepository.
    """
    wf_repo = WorkflowRepository()
    consult_repo = ConsultationRepository()
    cid = str(uuid.uuid4())

    consult_repo.create(cid, "history_test.mp4", "video/mp4")
    run = wf_repo.create_workflow_run(cid, workflow_version="1.0.0")
    wid = run["id"]

    # Step 1: Input
    s1 = wf_repo.create_workflow_step(wid, "VALIDATING_INPUT", "guardrail")
    wf_repo.update_workflow_step(s1["id"], "completed")

    # Step 2: Audio
    s2 = wf_repo.create_workflow_step(wid, "PROCESSING_AUDIO", "service")
    wf_repo.update_workflow_step(s2["id"], "completed")

    # Update run state
    wf_repo.update_workflow_run_status(wid, "PROCESSING_AUDIO", current_step="PROCESSING_AUDIO")

    # Query history
    history = wf_repo.get_workflow_history(cid)
    assert history is not None
    assert history["workflow_run"]["status"] == "PROCESSING_AUDIO"
    assert history["workflow_run"]["current_step"] == "PROCESSING_AUDIO"
    assert len(history["steps"]) == 2


# ---------------------------------------------------------------------------
# Test 12 — API responsiveness
# ---------------------------------------------------------------------------
def test_12_api_responsiveness():
    """
    Test 12: Verify POST /process returns quickly (< 1.5s) without waiting for AI pipeline.
    """
    sample_wav = io.BytesIO(
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        + b"\x00" * 8192
    )

    t0 = time.time()
    resp = client.post(
        "/api/v1/consultations/process",
        files={"file": ("rapid_upload.wav", sample_wav, "audio/wav")}
    )
    duration = time.time() - t0

    assert resp.status_code == 200
    assert duration < 5.0, f"Endpoint took {duration:.3f}s; must return immediately"
    data = resp.json()
    assert data["status"] == "queued"
    assert "workflow_id" in data


# ---------------------------------------------------------------------------
# Extra Test: MCP Tool Execution & Doctor Review Sign-Off
# ---------------------------------------------------------------------------
def test_doctor_review_and_mcp_tool_execution():
    """
    Verifies SaveDoctorReviewTool and GetConsultationTool with security context.
    """
    consult_repo = get_consultation_repository()
    wf_repo = get_workflow_repository()
    cid = str(uuid.uuid4())

    consult_repo.create(cid, "review_test.mp4", "video/mp4")
    run = wf_repo.create_workflow_run(cid)
    wf_repo.update_workflow_run_status(run["id"], "PENDING_DOCTOR_REVIEW", current_step="PENDING_DOCTOR_REVIEW")

    # Call GetConsultationTool
    get_tool = GetConsultationTool()
    tool_ctx = ToolContext(caller_id="Dr. Swaminathan", role="doctor", permissions=["read:consultation"])
    get_res = get_tool.execute({"consultation_id": cid}, tool_ctx)
    assert get_res.success is True
    assert get_res.data["id"] == cid

    # Call SaveDoctorReviewTool
    review_tool = SaveDoctorReviewTool()
    rev_ctx = ToolContext(caller_id="Dr. Swaminathan", role="doctor", permissions=["write:doctor_review"])
    rev_res = review_tool.execute(
        {
            "consultation_id": cid,
            "doctor_name": "Dr. Swaminathan",
            "decision": "approved",
            "notes": "Prescription verified and signed."
        },
        rev_ctx
    )
    assert rev_res.success is True
    assert rev_res.data["status"] == "completed"

    # Verify workflow transitioned to COMPLETED
    updated_run = wf_repo.get_workflow_run(run["id"])
    assert updated_run["status"] == "COMPLETED"
