"""
PostVisit AI - Stage 4: Comprehensive Patient Summary Test Suite
Validates all 23 Stage 4 requirements:
  Test 1: Generate an English summary from approved medical JSON
  Test 2: Generate a Tamil summary from approved medical JSON
  Test 3: Reject summary generation from an unapproved record
  Test 4: Preserve medication names and strengths
  Test 5: Preserve frequency, timing and duration
  Test 6: Detect altered numerical values
  Test 7: Detect hallucinated medications
  Test 8: Detect omitted important instructions
  Test 9: Handle missing medication fields
  Test 10: Handle contradictory source instructions
  Test 11: Reject malformed LLM output
  Test 12: Handle Groq rate limiting with Retry-After
  Test 13: Verify retry and idempotency behavior
  Test 14: Verify duplicate requests do not create duplicate summaries
  Test 15: Verify doctor approval and rejection
  Test 16: Verify patient access is blocked before approval
  Test 17: Verify patient ownership and access restrictions
  Test 18: Verify doctor authorization for review sign-off
  Test 19: Verify multilingual summary persistence
  Test 20: Verify audit history and versioning
  Test 21: Verify original medical JSON is never changed by summary generation
  Test 22: Verify integration with Stage 3 orchestrator
  Test 23: Verify MCP Tools for Patient Summary
  Test 24 (Optional): Live Groq API integration (skipped unless RUN_LIVE_GROQ=1)
"""

import os
import copy
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app
from src.workflow.states import WorkflowState
from src.workflow.orchestrator import WorkflowOrchestrator
from src.agents.registry import get_agent_registry
from src.agents.patient_summary_agent import PatientSummaryAgent
from src.agents.base import WorkflowContext
from src.guardrails.summary_guardrail import SummaryGuardrail
from src.schemas.patient_summary_schema import (
    PatientSummaryContent,
    PatientMedicationInstruction,
    PatientSummaryCreateRequest,
    PatientSummaryReviewRequest
)
from api.repositories.consultation_repository import ConsultationRepository
from api.repositories.summary_repository import SummaryRepository
from api.repositories.workflow_repository import WorkflowRepository
from src.services.summary_service import SummaryService
from src.tools.clinical_tools import (
    GeneratePatientSummaryTool,
    GetPatientSummaryTool,
    ReviewPatientSummaryTool
)
from src.tools.base import ToolContext
from src.llm_client import LLMClient

client = TestClient(app)

MOCK_ENGLISH_SUMMARY = {
    "overview": "Here is a simple summary of what the doctor discussed during your consultation. Symptoms discussed include: High fever for 3 days, Headache, Body fatigue.",
    "symptoms_discussed": ["High fever for 3 days", "Headache", "Body fatigue"],
    "medications": [
        {
            "medication_name": "Paracetamol",
            "strength": "650 mg",
            "dose": "1 tablet",
            "route": "oral",
            "frequency": "three times daily",
            "timing": "after food",
            "duration": "5 days",
            "instructions": "Take Paracetamol 650 mg - 1 tablet three times daily after food for 5 days.",
            "source_index": 0
        },
        {
            "medication_name": "Amoxicillin",
            "strength": "500 mg",
            "dose": "1 capsule",
            "route": "oral",
            "frequency": "twice daily",
            "timing": "after food",
            "duration": "7 days",
            "instructions": "Take Amoxicillin 500 mg - 1 capsule twice daily after food for 7 days.",
            "source_index": 1
        }
    ],
    "tests_ordered": [
        {
            "test_name": "Complete Blood Count",
            "timing": "Tomorrow morning",
            "instructions": "Fasting not required"
        }
    ],
    "self_care_instructions": ["Drink at least 2.5 liters of warm water daily", "Get adequate rest"],
    "warnings_and_precautions": ["If fever persists above 102F or difficulty breathing occurs, seek emergency care immediately"],
    "when_to_visit_again": "5 days",
    "unspecified_or_uncertain_info": []
}

MOCK_TAMIL_SUMMARY = {
    "overview": "உங்கள் மருத்துவ சந்திப்பில் விவாதிக்கப்பட்ட முக்கிய தகவல்கள் கீழே கொடுக்கப்பட்டுள்ளன. அறிகுறிகள்: High fever for 3 days, Headache, Body fatigue.",
    "symptoms_discussed": ["High fever for 3 days", "Headache", "Body fatigue"],
    "medications": [
        {
            "medication_name": "Paracetamol",
            "strength": "650 mg",
            "dose": "1 tablet",
            "route": "oral",
            "frequency": "three times daily",
            "timing": "after food",
            "duration": "5 days",
            "instructions": "Paracetamol (650 mg) 1 tablet three times daily after food எடுத்துக்கொள்ளவும் (5 days)",
            "source_index": 0
        },
        {
            "medication_name": "Amoxicillin",
            "strength": "500 mg",
            "dose": "1 capsule",
            "route": "oral",
            "frequency": "twice daily",
            "timing": "after food",
            "duration": "7 days",
            "instructions": "Amoxicillin (500 mg) 1 capsule twice daily after food எடுத்துக்கொள்ளவும் (7 days)",
            "source_index": 1
        }
    ],
    "tests_ordered": [
        {
            "test_name": "Complete Blood Count",
            "timing": "Tomorrow morning",
            "instructions": "Fasting not required"
        }
    ],
    "self_care_instructions": ["Drink at least 2.5 liters of warm water daily"],
    "warnings_and_precautions": ["If fever persists above 102F or difficulty breathing occurs, seek emergency care immediately"],
    "when_to_visit_again": "அறிகுறிகள் தொடர்ந்தால் மருத்துவரை மீண்டும் அணுகவும்.",
    "unspecified_or_uncertain_info": []
}


@pytest.fixture(autouse=True)
def mock_llm_generation(monkeypatch):
    """
    Enforces deterministic LLM output without external network requests
    as mandated by the prompt testing instructions.
    """
    def fake_generate_json(self, system_prompt, user_prompt, *args, **kwargs):
        if "Tamil" in system_prompt or "ta" in system_prompt:
            return copy.deepcopy(MOCK_TAMIL_SUMMARY)
        return copy.deepcopy(MOCK_ENGLISH_SUMMARY)

    monkeypatch.setattr(LLMClient, "generate_json", fake_generate_json)


def build_sample_approved_medical_record():
    """Generates a valid, doctor-approved medical extraction dictionary."""
    return {
        "symptoms": ["High fever for 3 days", "Headache", "Body fatigue"],
        "medications": [
            {
                "name": "Paracetamol",
                "strength": "650 mg",
                "dose": "1 tablet",
                "route": "oral",
                "frequency": "three times daily",
                "timing": "after food",
                "duration": "5 days",
                "source_speaker": "Doctor",
                "evidence": "Take Paracetamol 650mg three times daily after food for 5 days."
            },
            {
                "name": "Amoxicillin",
                "strength": "500 mg",
                "dose": "1 capsule",
                "route": "oral",
                "frequency": "twice daily",
                "timing": "after food",
                "duration": "7 days",
                "source_speaker": "Doctor",
                "evidence": "Take Amoxicillin 500mg capsule twice daily after meals for 7 days."
            }
        ],
        "tests": [
            {
                "name": "Complete Blood Count",
                "timing": "Tomorrow morning",
                "instructions": "Fasting not required"
            }
        ],
        "instructions": ["Drink at least 2.5 liters of warm water daily", "Get adequate rest"],
        "warnings_and_precautions": ["If fever persists above 102F or difficulty breathing occurs, seek emergency care immediately"],
        "follow_up": {"timeline": "5 days", "instructions": "Review in clinic after completing course"},
        "uncertain_items": [],
        "requires_doctor_review": False,
        "doctor_review": {
            "reviewed_by": "Dr. Ramanathan",
            "decision": "approved",
            "notes": "Clinically verified."
        }
    }


def setup_test_consultation(is_approved: bool = True):
    """Sets up an in-memory consultation with approved or unapproved medical record."""
    consult_repo = ConsultationRepository()
    consult_repo.client = None
    summary_repo = SummaryRepository()
    summary_repo.client = None
    wf_repo = WorkflowRepository()
    wf_repo.client = None
    service = SummaryService(
        summary_repo=summary_repo,
        consultation_repo=consult_repo,
        workflow_repo=wf_repo
    )


    cid = str(uuid.uuid4())
    consult_repo.create(cid, "patient_visit.wav", "audio/wav")

    med_record = build_sample_approved_medical_record()
    if not is_approved:
        med_record["requires_doctor_review"] = True
        med_record["doctor_review"] = None
        consult_repo.update_completed(
            consultation_id=cid,
            duration_seconds=120.0,
            transcript=[],
            medical_record=med_record,
            validation_result={"valid": True}
        )
        if cid in consult_repo._in_memory_db:
            consult_repo._in_memory_db[cid]["status"] = "pending_doctor_review"
    else:
        consult_repo.update_completed(
            consultation_id=cid,
            duration_seconds=120.0,
            transcript=[],
            medical_record=med_record,
            validation_result={"valid": True}
        )
        if cid in consult_repo._in_memory_db:
            consult_repo._in_memory_db[cid]["status"] = "completed"

    return cid, consult_repo, summary_repo, wf_repo, service, med_record


# ---------------------------------------------------------------------------
# Test 1: Generate an English summary from approved medical JSON
# ---------------------------------------------------------------------------
def test_1_generate_english_summary():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    summary = service.generate_summary(consultation_id=cid, target_language="en")
    assert summary is not None
    assert summary["consultation_id"] == cid
    assert summary["language"] == "en"
    assert summary["status"] == "PENDING_SUMMARY_REVIEW"

    gen = summary["generated_summary"]
    assert "overview" in gen
    assert len(gen["medications"]) == 2
    assert len(gen["tests_ordered"]) == 1
    assert len(gen["warnings_and_precautions"]) >= 1


# ---------------------------------------------------------------------------
# Test 2: Generate a Tamil summary from approved medical JSON
# ---------------------------------------------------------------------------
def test_2_generate_tamil_summary():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    summary = service.generate_summary(consultation_id=cid, target_language="ta")
    assert summary is not None
    assert summary["language"] == "ta"
    assert summary["status"] == "PENDING_SUMMARY_REVIEW"

    gen = summary["generated_summary"]
    med_names = [m["medication_name"] for m in gen["medications"]]
    assert "Paracetamol" in med_names
    assert "Amoxicillin" in med_names
    assert "மருத்துவ" in gen["overview"] or "எடுத்துக்கொள்ளவும்" in str(gen["medications"])


# ---------------------------------------------------------------------------
# Test 3: Reject summary generation from an unapproved record
# ---------------------------------------------------------------------------
def test_3_reject_unapproved_record():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=False)

    with pytest.raises(ValueError) as excinfo:
        service.generate_summary(consultation_id=cid, target_language="en")
    assert "not doctor-approved" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Test 4: Preserve medication names and strengths
# ---------------------------------------------------------------------------
def test_4_preserve_medication_names_and_strengths():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    summary = service.generate_summary(consultation_id=cid, target_language="en")
    gen_meds = summary["generated_summary"]["medications"]

    paracetamol = next(m for m in gen_meds if m["medication_name"] == "Paracetamol")
    assert "650" in paracetamol["strength"]

    amoxicillin = next(m for m in gen_meds if m["medication_name"] == "Amoxicillin")
    assert "500" in amoxicillin["strength"]


# ---------------------------------------------------------------------------
# Test 5: Preserve frequency, timing and duration
# ---------------------------------------------------------------------------
def test_5_preserve_frequency_timing_duration():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    summary = service.generate_summary(consultation_id=cid, target_language="en")
    gen_meds = summary["generated_summary"]["medications"]

    paracetamol = next(m for m in gen_meds if m["medication_name"] == "Paracetamol")
    assert "5 days" in paracetamol["duration"]
    assert "after food" in paracetamol["timing"].lower() or "after meals" in paracetamol["timing"].lower()

    amoxicillin = next(m for m in gen_meds if m["medication_name"] == "Amoxicillin")
    assert "7 days" in amoxicillin["duration"]


# ---------------------------------------------------------------------------
# Test 6: Detect altered numerical values
# ---------------------------------------------------------------------------
def test_6_detect_altered_numerical_values():
    guardrail = SummaryGuardrail()
    approved_med = build_sample_approved_medical_record()

    bad_summary = {
        "overview": "Overview of visit.",
        "symptoms_discussed": ["Fever"],
        "medications": [
            {
                "medication_name": "Paracetamol",
                "strength": "1000 mg",  # ALTERED!
                "dose": "1 tablet",
                "frequency": "three times daily",
                "duration": "5 days",
                "instructions": "Take Paracetamol 1000 mg."
            },
            {
                "medication_name": "Amoxicillin",
                "strength": "500 mg",
                "dose": "1 capsule",
                "frequency": "twice daily",
                "duration": "7 days",
                "instructions": "Take Amoxicillin 500 mg."
            }
        ],
        "tests_ordered": [{"test_name": "Complete Blood Count"}],
        "self_care_instructions": ["Rest"],
        "warnings_and_precautions": ["Seek emergency care if fever persists"],
        "when_to_visit_again": "5 days",
        "unspecified_or_uncertain_info": []
    }

    res = guardrail.validate(bad_summary, approved_med)
    assert res.passed is False
    assert res.action == "NEEDS_REVIEW"
    assert res.error_code == "ALTERED_NUMERICAL_VALUE"


# ---------------------------------------------------------------------------
# Test 7: Detect hallucinated medications
# ---------------------------------------------------------------------------
def test_7_detect_hallucinated_medications():
    guardrail = SummaryGuardrail()
    approved_med = build_sample_approved_medical_record()

    bad_summary = {
        "overview": "Overview of visit.",
        "symptoms_discussed": ["Fever"],
        "medications": [
            {
                "medication_name": "Paracetamol",
                "strength": "650 mg",
                "dose": "1 tablet",
                "frequency": "three times daily",
                "duration": "5 days",
                "instructions": "Take Paracetamol."
            },
            {
                "medication_name": "Amoxicillin",
                "strength": "500 mg",
                "dose": "1 capsule",
                "frequency": "twice daily",
                "duration": "7 days",
                "instructions": "Take Amoxicillin."
            },
            {
                "medication_name": "Ibuprofen",  # HALLUCINATED!
                "strength": "400 mg",
                "dose": "1 tablet",
                "frequency": "as needed",
                "duration": "3 days",
                "instructions": "Take for pain."
            }
        ],
        "tests_ordered": [{"test_name": "Complete Blood Count"}],
        "self_care_instructions": [],
        "warnings_and_precautions": ["Danger signs explained"],
        "when_to_visit_again": "5 days",
        "unspecified_or_uncertain_info": []
    }

    res = guardrail.validate(bad_summary, approved_med)
    assert res.passed is False
    assert res.action == "NEEDS_REVIEW"
    assert res.error_code == "HALLUCINATED_MEDICATION"


# ---------------------------------------------------------------------------
# Test 8: Detect omitted important instructions / warnings
# ---------------------------------------------------------------------------
def test_8_detect_omitted_important_instructions():
    guardrail = SummaryGuardrail()
    approved_med = build_sample_approved_medical_record()

    bad_summary = {
        "overview": "Overview of visit.",
        "symptoms_discussed": ["Fever"],
        "medications": [
            {
                "medication_name": "Paracetamol",
                "strength": "650 mg",
                "duration": "5 days",
                "instructions": "Take Paracetamol."
            },
            {
                "medication_name": "Amoxicillin",
                "strength": "500 mg",
                "duration": "7 days",
                "instructions": "Take Amoxicillin."
            }
        ],
        "tests_ordered": [{"test_name": "Complete Blood Count"}],
        "self_care_instructions": ["Rest"],
        "warnings_and_precautions": [],  # OMITTED!
        "when_to_visit_again": "5 days",
        "unspecified_or_uncertain_info": []
    }

    res = guardrail.validate(bad_summary, approved_med)
    assert res.passed is False
    assert res.error_code == "OMITTED_CRITICAL_WARNINGS"


# ---------------------------------------------------------------------------
# Test 9: Handle missing medication fields gracefully
# ---------------------------------------------------------------------------
def test_9_handle_missing_medication_fields(monkeypatch):
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    med["medications"][0]["strength"] = None
    med["medications"][0]["duration"] = None
    c_repo._in_memory_db[cid]["medical_record"] = med

    # Force fallback generator to test template resilience
    agent = get_agent_registry().get("patient_summary")
    agent._llm_client = None
    monkeypatch.setattr(agent, "_get_llm_client", lambda: None)

    summary = service.generate_summary(consultation_id=cid, target_language="en")
    assert summary is not None
    assert summary["status"] == "PENDING_SUMMARY_REVIEW"
    gen_meds = summary["generated_summary"]["medications"]
    assert gen_meds[0]["medication_name"] == "Paracetamol"
    assert gen_meds[0]["strength"] is None


# ---------------------------------------------------------------------------
# Test 10: Handle contradictory source instructions
# ---------------------------------------------------------------------------
def test_10_handle_contradictory_source_instructions():
    guardrail = SummaryGuardrail()
    approved_med = build_sample_approved_medical_record()
    approved_med["uncertain_items"] = ["Contradiction: Doctor stated 3 days then changed to 7 days."]

    summary_ignoring_uncertainty = {
        "overview": "Overview.",
        "symptoms_discussed": ["Fever"],
        "medications": [
            {"medication_name": "Paracetamol", "strength": "650 mg", "duration": "5 days", "instructions": "Take it."},
            {"medication_name": "Amoxicillin", "strength": "500 mg", "duration": "7 days", "instructions": "Take it."}
        ],
        "tests_ordered": [{"test_name": "Complete Blood Count"}],
        "self_care_instructions": [],
        "warnings_and_precautions": ["Danger signs"],
        "when_to_visit_again": "5 days",
        "unspecified_or_uncertain_info": []
    }

    res = guardrail.validate(summary_ignoring_uncertainty, approved_med)
    assert res.passed is False
    assert res.error_code == "UNRESOLVED_CONTRADICTION"


# ---------------------------------------------------------------------------
# Test 11: Reject malformed LLM output
# ---------------------------------------------------------------------------
def test_11_reject_malformed_llm_output():
    agent = PatientSummaryAgent()
    ctx = WorkflowContext(
        consultation_id="c-test",
        workflow_run_id="w-test",
        medical_record=build_sample_approved_medical_record(),
        language="en"
    )

    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {"invalid_key": "not matching PatientSummaryContent"}
    agent._llm_client = mock_llm

    res = agent.run(ctx)
    assert res.success is False
    assert "validation" in res.error.lower()



# ---------------------------------------------------------------------------
# Test 12: Handle Groq rate limiting with Retry-After
# ---------------------------------------------------------------------------
def test_12_handle_groq_rate_limiting():
    llm = LLMClient(provider="groq", api_key="dummy-key-for-test")

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limit reached"
    mock_resp_429.headers = {"Retry-After": "0.01"}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "choices": [{"message": {"content": '{"overview": "Rate limit recovered successfully."}'}}]
    }

    # Unpatch generate_json specifically for this unit test
    with patch("httpx.Client.post", side_effect=[mock_resp_429, mock_resp_200]):
        # Call the private method directly to test actual HTTP handling
        res = llm._generate_openai_compatible_json("Sys", "User", temperature=0.0, max_retries=2, timeout=5.0)
        assert res["overview"] == "Rate limit recovered successfully."


# ---------------------------------------------------------------------------
# Test 13: Verify retry and idempotency behavior
# ---------------------------------------------------------------------------
def test_13_verify_retry_and_idempotency_behavior():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    key = "idemp-key-unique-123"
    s1 = service.generate_summary(consultation_id=cid, target_language="en", idempotency_key=key)
    s2 = service.generate_summary(consultation_id=cid, target_language="en", idempotency_key=key)

    assert s1["id"] == s2["id"]
    assert s1["created_at"] == s2["created_at"]


# ---------------------------------------------------------------------------
# Test 14: Duplicate requests do not create duplicate summaries
# ---------------------------------------------------------------------------
def test_14_verify_duplicate_requests_do_not_create_duplicate_summaries():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    s1 = service.generate_summary(consultation_id=cid, target_language="en", idempotency_key="run-1")
    service.review_summary(summary_id=s1["id"], doctor_name="Dr. Raman", decision="approved")

    s2 = service.generate_summary(consultation_id=cid, target_language="en")
    assert s2["id"] == s1["id"]

    all_summaries = s_repo.list_summaries_for_consultation(cid, language="en")
    assert len(all_summaries) == 1


# ---------------------------------------------------------------------------
# Test 15: Verify doctor approval and rejection
# ---------------------------------------------------------------------------
def test_15_verify_doctor_approval_and_rejection():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    s_app = service.generate_summary(consultation_id=cid, target_language="en", idempotency_key="app-1")
    res_app = service.review_summary(
        summary_id=s_app["id"],
        doctor_name="Dr. Ramanathan",
        decision="approved",
        notes="Reviewed and confirmed accurate."
    )
    assert res_app["status"] == "SUMMARY_APPROVED"
    assert res_app["reviewed_by"] == "Dr. Ramanathan"

    cid2, _, s_repo2, _, service2, _ = setup_test_consultation(is_approved=True)
    s_rej = service2.generate_summary(consultation_id=cid2, target_language="en", idempotency_key="rej-1")
    res_rej = service2.review_summary(
        summary_id=s_rej["id"],
        doctor_name="Dr. Ramanathan",
        decision="rejected",
        notes="Medication dosage requires clinic re-evaluation."
    )
    assert res_rej["status"] == "SUMMARY_REJECTED"


# ---------------------------------------------------------------------------
# Test 16: Verify that patient access is blocked before approval
# ---------------------------------------------------------------------------
def test_16_verify_patient_access_blocked_before_approval():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    summary = service.generate_summary(consultation_id=cid, target_language="en")

    assert summary["status"] == "PENDING_SUMMARY_REVIEW"

    with pytest.raises(PermissionError) as excinfo:
        service.get_summary(summary_id=summary["id"], caller_role="patient")
    assert "pending physician approval" in str(excinfo.value)

    service.review_summary(summary_id=summary["id"], doctor_name="Dr. Raman", decision="approved")
    approved_summary = service.get_summary(summary_id=summary["id"], caller_role="patient")
    assert approved_summary["status"] == "SUMMARY_APPROVED"


# ---------------------------------------------------------------------------
# Test 17: Verify patient ownership and access restrictions via HTTP API
# ---------------------------------------------------------------------------
def test_17_verify_patient_ownership_restrictions():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    s = service.generate_summary(consultation_id=cid, target_language="en")

    from src.services.summary_service import get_summary_service
    app.dependency_overrides[get_summary_service] = lambda: service

    try:
        resp = client.get(f"/api/v1/summaries/{s['id']}", headers={"X-User-Role": "patient"})
        assert resp.status_code == 403

        resp_doc = client.get(f"/api/v1/summaries/{s['id']}", headers={"X-User-Role": "doctor"})
        assert resp_doc.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 18: Verify doctor authorization for review sign-off
# ---------------------------------------------------------------------------
def test_18_verify_doctor_authorization():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    s = service.generate_summary(consultation_id=cid, target_language="en")

    from src.services.summary_service import get_summary_service
    app.dependency_overrides[get_summary_service] = lambda: service

    try:
        resp = client.post(
            f"/api/v1/summaries/{s['id']}/review",
            json={"doctor_name": "Impostor", "decision": "approved"},
            headers={"X-User-Role": "patient"}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "DOCTOR_ROLE_REQUIRED"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 19: Verify multilingual summary persistence
# ---------------------------------------------------------------------------
def test_19_verify_multilingual_summary_persistence():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    s_en = service.generate_summary(consultation_id=cid, target_language="en", idempotency_key="ml-en")
    s_ta = service.generate_summary(consultation_id=cid, target_language="ta", idempotency_key="ml-ta")

    assert s_en["id"] != s_ta["id"]
    assert s_en["language"] == "en"
    assert s_ta["language"] == "ta"

    all_sums = s_repo.list_summaries_for_consultation(cid)
    assert len(all_sums) == 2


# ---------------------------------------------------------------------------
# Test 20: Verify audit history and versioning
# ---------------------------------------------------------------------------
def test_20_verify_audit_history_and_versioning():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    s = service.generate_summary(consultation_id=cid, target_language="en")

    amended_content = copy.deepcopy(s["generated_summary"])
    amended_content["overview"] = "Doctor revised overview with additional lifestyle guidance."
    service.review_summary(
        summary_id=s["id"],
        doctor_name="Dr. Raman",
        decision="amended",
        notes="Amended overview.",
        corrected_summary=amended_content
    )

    history = service.get_summary_history(summary_id=s["id"], caller_role="doctor")
    assert len(history) >= 2
    actions = [h["action"] for h in history]
    assert "generated" in actions
    assert "amended" in actions


# ---------------------------------------------------------------------------
# Test 21: Verify original medical JSON is never changed by summary generation
# ---------------------------------------------------------------------------
def test_21_original_medical_json_never_changed():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    original_med_copy = copy.deepcopy(c_repo.get_by_id(cid)["medical_record"])

    s = service.generate_summary(consultation_id=cid, target_language="en")

    amended = copy.deepcopy(s["generated_summary"])
    amended["overview"] = "Changed overview by doctor."
    service.review_summary(
        summary_id=s["id"],
        doctor_name="Dr. Raman",
        decision="amended",
        corrected_summary=amended
    )

    current_med = c_repo.get_by_id(cid)["medical_record"]
    assert current_med == original_med_copy


# ---------------------------------------------------------------------------
# Test 22: Verify integration with Stage 3 orchestrator
# ---------------------------------------------------------------------------
def test_22_orchestrator_integration():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    orchestrator = WorkflowOrchestrator(
        workflow_repo=w_repo,
        consultation_repo=c_repo
    )

    with patch("src.services.summary_service.get_summary_service", return_value=service):
        res = orchestrator.generate_patient_summary(
            consultation_id=cid,
            language="en",
            idempotency_key="orch-test-1"
        )
        assert res is not None
        assert res["consultation_id"] == cid
        assert res["status"] in ("PENDING_SUMMARY_REVIEW", "SUMMARY_APPROVED")


# ---------------------------------------------------------------------------
# Test 23: Verify MCP Tools for Patient Summary
# ---------------------------------------------------------------------------
def test_23_mcp_patient_summary_tools():
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)

    with patch("src.services.summary_service.get_summary_service", return_value=service):
        gen_tool = GeneratePatientSummaryTool()
        ctx = ToolContext(caller_id="Dr. Raman", role="doctor", permissions=["generate:patient_summary"])
        res = gen_tool.execute({"consultation_id": cid, "language": "en"}, ctx)
        assert res.success is True
        sid = res.data["id"]

        rev_tool = ReviewPatientSummaryTool()
        rev_ctx = ToolContext(caller_id="Dr. Raman", role="doctor", permissions=["review:patient_summary"])
        rev_res = rev_tool.execute(
            {
                "summary_id": sid,
                "doctor_name": "Dr. Raman",
                "decision": "approved",
                "notes": "Approved via MCP tool."
            },
            rev_ctx
        )
        assert rev_res.success is True
        assert rev_res.data["status"] == "SUMMARY_APPROVED"

        get_tool = GetPatientSummaryTool()
        get_ctx = ToolContext(caller_id="patient_1", role="patient", permissions=["read:patient_summary"])
        get_res = get_tool.execute({"summary_id": sid}, get_ctx)
        assert get_res.success is True
        assert get_res.data["id"] == sid


# ---------------------------------------------------------------------------
# Test 24 (Optional): Live Groq API Integration (skipped unless RUN_LIVE_GROQ=1)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(os.getenv("RUN_LIVE_GROQ") != "1", reason="Live Groq test requires RUN_LIVE_GROQ=1")
def test_24_optional_live_groq_api():
    """Optional live integration test against live Groq API."""
    cid, c_repo, s_repo, w_repo, service, med = setup_test_consultation(is_approved=True)
    agent = PatientSummaryAgent()
    ctx = WorkflowContext(
        consultation_id=cid,
        workflow_run_id="live-test",
        medical_record=med,
        language="en"
    )
    res = agent.run(ctx)
    assert res.success is True
    assert "medications" in res.output
