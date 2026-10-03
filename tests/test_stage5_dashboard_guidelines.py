"""
PostVisit AI - Stage 5: Comprehensive Test Suite
Validates:
  1. Authenticated session profiles & RBAC permissions (Doctor vs Patient)
  2. Static HTML dashboard routes (/app, /dashboard)
  3. Authoritative real-time workflow progress endpoint (/progress)
  4. Real elapsed time calculation and honest step statuses (no fake progress)
  5. Curated Indian Clinical Guidelines registry (ICMR 2022, MoHFW 2021)
  6. Guideline retrieval with evidence provenance, citations & checksums
  7. Handling missing/unverified guideline topics (transparent NO_VERIFIED_SOURCE)
  8. Physician-gated guideline findings (review prompts, never autonomous diagnoses)
  9. Doctor review of guideline findings (acknowledged / dismissed) with audit logs
  10. Strict immutability of doctor-approved medical JSON
  11. Patient guideline view redaction (no raw clinical discrepancy prompts)
  12. Doctor summary sign-off (Approve, Amend, Reject)
  13. Patient summary access gating (403 before approval, 200 after approval)
  14. Separate storage of generated vs amended summary versions
  15. Patient RBAC enforcement (cannot view unapproved summary or call review APIs)
  16. Regression preservation of existing Stage 1-4 endpoints
"""

import copy
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from api.main import app
from src.workflow.states import WorkflowState
from src.guidelines.source_registry import get_guideline_registry
from src.guidelines.retrieval_service import get_guideline_retrieval_service
from src.agents.guideline_agent import GuidelineCrossReferenceAgent
from api.repositories.consultation_repository import ConsultationRepository, get_consultation_repository
from api.repositories.summary_repository import SummaryRepository, get_summary_repository
from api.repositories.guideline_repository import get_guideline_repository
from api.services.consultation_service import get_consultation_service
from src.services.guideline_service import get_guideline_service

client = TestClient(app)


# -------------------------------------------------------------
# Fixtures & Synthetic Test Records
# -------------------------------------------------------------
@pytest.fixture
def sample_approved_medical_record():
    """Synthetic approved medical record for a Type 2 Diabetes follow-up patient in India."""
    return {
        "patient": {
            "name": "Ananya Patel",
            "age": 42,
            "gender": "Female",
            "patient_id": "PT-89241"
        },
        "chief_complaint": "Routine follow-up for Type 2 Diabetes and general fatigue",
        "diagnoses": [
            {
                "condition": "Type 2 Diabetes Mellitus",
                "status": "confirmed",
                "notes": "Diagnosed 2 years ago, HbA1c elevated at 7.8%"
            },
            {
                "condition": "Essential Hypertension",
                "status": "suspected",
                "notes": "Clinic BP 138/88 mmHg"
            }
        ],
        "vitals": {
            "blood_pressure": "138/88 mmHg",
            "heart_rate": "76 bpm",
            "temperature": "98.4 F"
        },
        "symptoms": ["elevated blood sugar", "fatigue"],
        "medications": [
            {
                "name": "Metformin",
                "strength": "500 mg",
                "dosage_form": "tablet",
                "frequency": "Twice daily",
                "timing": "With meals",
                "duration": "90 days",
                "special_instructions": "Take with breakfast and dinner to minimize GI upset"
            }
        ],
        "lab_investigations": [
            {"name": "HbA1c test in 3 months"},
            {"name": "Serum Creatinine and eGFR renal function test"}
        ],
        "lifestyle_recommendations": [
            "Maintain dietary sodium intake under 5 grams per day",
            "30 minutes of moderate aerobic exercise 5 days a week"
        ],
        "follow_up": {
            "recommended_days": 90,
            "condition": "Follow up after completing HbA1c"
        }
    }


@pytest.fixture
def mock_consultation_in_db(sample_approved_medical_record):
    """Inserts a synthetic consultation directly into repository for test isolation."""
    consultation_service = get_consultation_service()
    consultation_id = str(uuid.uuid4())
    
    record = {
        "id": consultation_id,
        "consultation_id": consultation_id,
        "patient_id": "PT-89241",
        "doctor_name": "Dr. Rajesh Sharma, MD",
        "status": WorkflowState.PENDING_DOCTOR_REVIEW.value,
        "state": WorkflowState.PENDING_DOCTOR_REVIEW.value,
        "original_filename": "consultation_t2d_followup.wav",
        "media_file_name": "consultation_t2d_followup.wav",
        "media_type": "audio/wav",
        "audio_storage_path": f"consultations/{consultation_id}/audio.wav",
        "transcript": "Doctor: Good morning Ananya. How is your blood sugar?\nPatient: Doctor, morning fasting is around 140.",
        "speaker_labelled_transcript": [
            {"speaker": "Doctor", "text": "Good morning Ananya. How is your blood sugar?"},
            {"speaker": "Patient", "text": "Doctor, morning fasting is around 140."}
        ],
        "extracted_medical_record": sample_approved_medical_record,
        "requires_doctor_review": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Force offline test isolation
    repo = consultation_service.repository
    repo.client = None
    repo._in_memory_db[consultation_id] = record

    # Also register in summary repository for clean state
    summary_repo = get_summary_repository()
    summary_repo.client = None
    
    return consultation_id, record


# -------------------------------------------------------------
# 1. Authenticated Session Profiles & RBAC Tests
# -------------------------------------------------------------
def test_doctor_auth_profile():
    """Verify doctor session returns physician identity and review permissions."""
    res = client.get("/api/v1/auth/me?role=doctor")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "doctor"
    assert data["user_id"] == "dr_rajesh_sharma"
    assert "summaries:approve" in data["permissions"]
    assert "guidelines:review" in data["permissions"]


def test_patient_auth_profile():
    """Verify patient session returns patient identity and restricted permissions."""
    res = client.get("/api/v1/auth/me?role=patient")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "patient"
    assert data["patient_id"] == "PT-89241"
    assert "summaries:read_approved" in data["permissions"]
    assert "summaries:approve" not in data["permissions"]
    assert "guidelines:review" not in data["permissions"]


# -------------------------------------------------------------
# 2. Static HTML Dashboard Routes
# -------------------------------------------------------------
def test_dashboard_routes_serve_html():
    """Verify /app and /dashboard serve the single-page application index.html."""
    res_app = client.get("/app")
    assert res_app.status_code == 200
    assert "text/html" in res_app.headers["content-type"]
    assert "PostVisit AI" in res_app.text
    assert "doctor-view" in res_app.text
    assert "patient-view" in res_app.text
    assert "processing-view" in res_app.text

    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "text/html" in res_dash.headers["content-type"]


# -------------------------------------------------------------
# 3. Real-Time Processing UI Progress Endpoint
# -------------------------------------------------------------
def test_consultation_progress_truthfulness(mock_consultation_in_db):
    """Verify progress endpoint returns authentic step states and elapsed time."""
    cid, _ = mock_consultation_in_db
    
    res = client.get(f"/api/v1/consultations/{cid}/progress")
    assert res.status_code == 200
    data = res.json()
    
    assert data["consultation_id"] == cid
    assert "steps" in data
    assert len(data["steps"]) >= 6
    
    # Verify expected step identifiers exist
    step_ids = [s["step_id"] for s in data["steps"]]
    assert "transcription" in step_ids
    assert "extraction" in step_ids
    assert "guidelines" in step_ids
    assert "doctor_review" in step_ids

    # For PENDING_DOCTOR_REVIEW, transcription and extraction are completed
    step_dict = {s["step_id"]: s for s in data["steps"]}
    assert step_dict["transcription"]["status"] == "completed"
    assert step_dict["extraction"]["status"] == "completed"
    assert step_dict["doctor_review"]["status"] in ("running", "needs_review")
    
    # Verify genuine elapsed time
    assert "elapsed_time_sec" in data
    assert data["elapsed_time_sec"] >= 0


def test_progress_shows_not_configured_when_guidelines_not_run(mock_consultation_in_db):
    """Verify guideline step does not falsely show completed when un-evaluated."""
    cid, _ = mock_consultation_in_db
    
    res = client.get(f"/api/v1/consultations/{cid}/progress")
    assert res.status_code == 200
    data = res.json()
    
    guideline_step = next(s for s in data["steps"] if s["step_id"] == "guidelines")
    assert guideline_step["status"] == "not_configured"
    assert "not currently enabled" in guideline_step["description"].lower()


def test_progress_404_for_unknown_consultation():
    """Verify progress returns 404 for non-existent consultation."""
    res = client.get("/api/v1/consultations/non-existent-id/progress")
    assert res.status_code == 404


# -------------------------------------------------------------
# 4. Curated Indian Medical Guidelines Registry
# -------------------------------------------------------------
def test_guideline_sources_registry_contents():
    """Verify guideline registry includes verified ICMR and MoHFW guidelines with checksums."""
    registry = get_guideline_registry()
    sources = registry.list_sources()
    
    assert len(sources) >= 4
    source_ids = [s["id"] for s in sources]
    assert "icmr-diabetes-2022" in source_ids
    assert "icmr-htn-2021" in source_ids
    assert "mohfw-ari-fever-2022" in source_ids
    assert "icmr-amr-respiratory-2022" in source_ids

    # Verify checksums and provenance URLs are present
    for s in sources:
        assert s["verified"] is True
        assert len(s["checksum"]) == 64  # SHA-256 hex
        assert s["source_url"].startswith("https://")
        assert "India" in s["country"]


def test_guidelines_sources_api_endpoint():
    """Verify GET /api/v1/guidelines/sources endpoint returns verified guidelines."""
    res = client.get("/api/v1/guidelines/sources")
    assert res.status_code == 200
    data = res.json()
    assert "sources" in data
    assert data["total"] >= 4
    assert any("Type 2 Diabetes" in g["title"] for g in data["sources"])


# -------------------------------------------------------------
# 5. Guideline Retrieval & Evidence Provenance
# -------------------------------------------------------------
def test_guideline_retrieval_service_matches_diabetes():
    """Verify retrieval engine extracts relevant passages for Diabetes and Metformin."""
    retriever = get_guideline_retrieval_service()
    evidence = retriever.retrieve(
        clinical_topics=["Type 2 Diabetes Mellitus"],
        medication_names=["Metformin"]
    )
    
    assert len(evidence) > 0
    # Check provenance details
    for ev in evidence:
        assert ev.guideline_id == "icmr-diabetes-2022"
        assert "Indian Council of Medical Research" in ev.publishing_org
        assert ev.source_url.startswith("https://")
        assert len(ev.excerpt) > 20
        assert ev.retrieval_timestamp is not None


def test_guideline_retrieval_unmatched_returns_empty():
    """Verify retrieval returns empty list for clinical topics with no verified source."""
    retriever = get_guideline_retrieval_service()
    evidence = retriever.retrieve(
        clinical_topics=["Rare Unknown Genetic Syndrome X99"],
        medication_names=["ExperimentalDrugXYZ"]
    )
    assert len(evidence) == 0


# -------------------------------------------------------------
# 6. Guideline Cross-Reference Agent & Immutability
# -------------------------------------------------------------
def test_guideline_cross_reference_execution(mock_consultation_in_db):
    """Verify physician can execute guideline cross-referencing and receive review prompts."""
    cid, record = mock_consultation_in_db
    
    # Store deepcopy to verify medical record immutability
    original_medical_json = copy.deepcopy(record["extracted_medical_record"])
    
    res = client.post(
        f"/api/v1/consultations/{cid}/cross-reference",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert res.status_code == 200
    data = res.json()
    
    assert data["consultation_id"] == cid
    assert data["status"] in ("COMPLETED_WITH_FINDINGS", "COMPLETED_NO_FINDINGS")
    assert "guidelines_evaluated" in data
    assert len(data["guidelines_evaluated"]) > 0
    
    # Verify medical JSON is NOT mutated
    after_record = get_consultation_service().repository.get_by_id(cid)
    assert after_record["extracted_medical_record"] == original_medical_json


def test_guideline_findings_are_decision_support_not_autonomous_diagnoses(mock_consultation_in_db):
    """Verify findings are review prompts with citations, never autonomous prescribing."""
    cid, _ = mock_consultation_in_db
    
    client.post(
        f"/api/v1/consultations/{cid}/cross-reference",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    
    res = client.get(
        f"/api/v1/consultations/{cid}/guidelines",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert res.status_code == 200
    data = res.json()
    
    for finding in data["findings"]:
        # Must contain citation
        assert finding["evidence"]["guideline_id"] in (
            "icmr-diabetes-2022", "icmr-htn-2021", "mohfw-ari-fever-2022", "icmr-amr-respiratory-2022"
        )
        assert finding["evidence"]["source_url"].startswith("https://")
        assert finding["status"] in ("pending_review", "acknowledged", "dismissed")


def test_patient_blocked_from_raw_guideline_discrepancies(mock_consultation_in_db):
    """Verify patient role receives redacted guideline view without raw clinical discrepancy flags."""
    cid, _ = mock_consultation_in_db
    
    # Doctor triggers cross-reference first
    client.post(
        f"/api/v1/consultations/{cid}/cross-reference",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    
    # Patient queries guideline endpoint
    res = client.get(
        f"/api/v1/consultations/{cid}/guidelines",
        headers={"X-User-Role": "patient", "X-User-Id": "pt_ananya_patel"}
    )
    assert res.status_code == 200
    data = res.json()
    
    # Findings must be redacted (not present in payload for patients)
    assert "findings" not in data
    assert "summary" in data
    assert "verified clinical guidelines" in data["summary"].lower()


def test_patient_blocked_from_triggering_guideline_cross_reference(mock_consultation_in_db):
    """Verify patient role cannot trigger guideline cross-referencing."""
    cid, _ = mock_consultation_in_db
    
    res = client.post(
        f"/api/v1/consultations/{cid}/cross-reference",
        headers={"X-User-Role": "patient", "X-User-Id": "pt_ananya_patel"}
    )
    assert res.status_code == 403
    assert "Only authorized physicians" in res.json()["error"]["message"]


# -------------------------------------------------------------
# 7. Doctor Review Gate for Guideline Findings
# -------------------------------------------------------------
def test_doctor_can_acknowledge_or_dismiss_guideline_finding(mock_consultation_in_db):
    """Verify doctor can acknowledge or dismiss a guideline finding with audit notes."""
    cid, _ = mock_consultation_in_db
    
    # Trigger cross reference
    cr_res = client.post(
        f"/api/v1/consultations/{cid}/cross-reference",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    findings = cr_res.json()["findings"]
    assert len(findings) > 0
    first_finding_id = findings[0]["id"]
    
    # Submit physician review
    review_res = client.post(
        f"/api/v1/consultations/{cid}/guidelines/review",
        json={
            "doctor_name": "Dr. Rajesh Sharma, MD",
            "finding_id": first_finding_id,
            "decision": "acknowledged",
            "notes": "Reviewed ICMR HbA1c monitoring target. Scheduled 3-month follow-up."
        },
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert review_res.status_code == 200
    data = review_res.json()
    assert data["decision"] == "acknowledged"
    assert data["doctor_name"] == "Dr. Rajesh Sharma, MD"

    # Verify audit history is updated in guidelines response
    g_res = client.get(
        f"/api/v1/consultations/{cid}/guidelines",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    updated_findings = g_res.json()["findings"]
    updated = next(f for f in updated_findings if f["id"] == first_finding_id)
    assert updated["doctor_decision"] == "acknowledged"
    assert updated["doctor_notes"] == "Reviewed ICMR HbA1c monitoring target. Scheduled 3-month follow-up."


def test_patient_blocked_from_submitting_guideline_review(mock_consultation_in_db):
    """Verify patient cannot review or dismiss guideline findings."""
    cid, _ = mock_consultation_in_db
    
    res = client.post(
        f"/api/v1/consultations/{cid}/guidelines/review",
        json={
            "doctor_name": "Dr. Rajesh Sharma",
            "finding_id": "any-finding-id",
            "decision": "dismissed",
            "notes": "Patient attempting override"
        },
        headers={"X-User-Role": "patient", "X-User-Id": "pt_ananya_patel"}
    )
    assert res.status_code == 403


# -------------------------------------------------------------
# 8. Doctor Summary Sign-Off & Patient Access Gate
# -------------------------------------------------------------
def test_summary_approval_and_patient_access_gate(mock_consultation_in_db):
    """
    Verify complete patient summary lifecycle:
      - Block patient access while unapproved (403)
      - Doctor approves summary
      - Patient access granted (200)
    """
    cid, _ = mock_consultation_in_db
    summary_repo = get_summary_repository()
    summary_repo.client = None
    
    # Setup initial draft summary using official repository method
    mock_content = {
        "overview": "Summary of diabetes consultation",
        "symptoms_discussed": ["High blood sugar", "Fatigue"],
        "medications": [
            {
                "medication_name": "Metformin",
                "strength": "500 mg",
                "dose": "1 tablet",
                "route": "oral",
                "frequency": "twice daily",
                "timing": "with meals",
                "duration": "90 days",
                "instructions": "Take Metformin 500 mg twice daily with meals for 90 days."
            }
        ],
        "tests_ordered": [
            {
                "test_name": "HbA1c",
                "timing": "in 3 months",
                "instructions": "Fasting not required"
            }
        ],
        "self_care_instructions": ["Reduce salt intake", "Daily 30-min walk"],
        "warnings_and_precautions": ["If severe dizziness occurs, seek immediate care"],
        "when_to_visit_again": "3 months",
        "unspecified_or_uncertain_info": []
    }
    summary_record = summary_repo.create_summary(
        consultation_id=cid,
        language="en",
        generated_summary=mock_content,
        status="PENDING_SUMMARY_REVIEW"
    )
    summary_id = summary_record["id"]
    
    # 1. Patient tries to read single unapproved summary -> MUST BE 403
    p_res = client.get(
        f"/api/v1/summaries/{summary_id}",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert p_res.status_code == 403
    assert "pending physician approval" in p_res.json()["error"]["message"].lower()

    # 2. Doctor approves summary
    d_res = client.post(
        f"/api/v1/consultations/{cid}/summaries/review",
        json={
            "decision": "approved",
            "doctor_name": "Dr. Rajesh Sharma, MD",
            "notes": "Reviewed and verified patient instructions."
        },
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert d_res.status_code == 200
    assert d_res.json()["status"] == "SUMMARY_APPROVED"

    # 3. Patient reads summary AFTER approval -> MUST BE 200
    p_res_approved = client.get(
        f"/api/v1/summaries/{summary_id}",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert p_res_approved.status_code == 200
    approved_summary = p_res_approved.json()
    assert approved_summary["status"] == "SUMMARY_APPROVED"
    assert approved_summary["generated_summary"]["overview"] == "Summary of diabetes consultation"


def test_doctor_amends_summary_separating_original_and_amended(mock_consultation_in_db):
    """
    Verify doctor amendment:
      - Preserves original generated summary content
      - Stores amended summary separately
      - Serves amended summary to patient
    """
    cid, _ = mock_consultation_in_db
    summary_repo = get_summary_repository()
    summary_repo.client = None
    
    mock_content = {
        "overview": "Original generated overview",
        "symptoms_discussed": ["Fatigue"],
        "medications": [],
        "tests_ordered": [],
        "self_care_instructions": [],
        "warnings_and_precautions": [],
        "when_to_visit_again": "90 days",
        "unspecified_or_uncertain_info": []
    }
    summary_record = summary_repo.create_summary(
        consultation_id=cid,
        language="en",
        generated_summary=mock_content,
        status="PENDING_SUMMARY_REVIEW"
    )
    summary_id = summary_record["id"]

    # Doctor amends the summary
    amended_content = copy.deepcopy(mock_content)
    amended_content["overview"] = "Amended overview: Diabetes checkup & Blood Pressure evaluation"
    
    review_res = client.post(
        f"/api/v1/consultations/{cid}/summaries/review",
        json={
            "decision": "amended",
            "doctor_name": "Dr. Rajesh Sharma, MD",
            "notes": "Added blood pressure evaluation to visit reason.",
            "corrected_summary": amended_content
        },
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "SUMMARY_APPROVED"
    
    # Stored record should strictly preserve original AND separate reviewed version
    stored = summary_repo.get_summary_by_id(summary_id)
    assert stored["generated_summary"]["overview"] == "Original generated overview"
    assert stored["reviewed_summary"]["overview"] == "Amended overview: Diabetes checkup & Blood Pressure evaluation"


def test_doctor_rejection_marks_summary_rejected(mock_consultation_in_db):
    """Verify physician summary rejection marks status rejected and patient access is denied."""
    cid, _ = mock_consultation_in_db
    summary_repo = get_summary_repository()
    summary_repo.client = None
    
    mock_content = {
        "overview": "Flawed generated summary",
        "symptoms_discussed": [],
        "medications": [],
        "tests_ordered": [],
        "self_care_instructions": [],
        "warnings_and_precautions": [],
        "when_to_visit_again": "None",
        "unspecified_or_uncertain_info": []
    }
    summary_record = summary_repo.create_summary(
        consultation_id=cid,
        language="en",
        generated_summary=mock_content,
        status="PENDING_SUMMARY_REVIEW"
    )
    summary_id = summary_record["id"]

    # Doctor rejects the summary
    review_res = client.post(
        f"/api/v1/consultations/{cid}/summaries/review",
        json={
            "decision": "rejected",
            "doctor_name": "Dr. Rajesh Sharma, MD",
            "notes": "Summary omitted critical dietary salt restriction. Re-generation needed."
        },
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "SUMMARY_REJECTED"

    # Patient query must be blocked
    p_res = client.get(
        f"/api/v1/summaries/{summary_id}",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert p_res.status_code == 403


# -------------------------------------------------------------
# 9. Regression: Baseline API Endpoints
# -------------------------------------------------------------
def test_health_check_regression():
    """Verify existing /health endpoint functions properly."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_root_regression():
    """Verify existing / endpoint returns JSON metadata."""
    res = client.get("/")
    assert res.status_code == 200
    assert "name" in res.json()
    assert res.json()["docs"] == "/docs"


def test_list_consultations_regression():
    """Verify existing GET /api/v1/consultations endpoint returns paginated results."""
    res = client.get("/api/v1/consultations?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
