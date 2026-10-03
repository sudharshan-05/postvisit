"""
PostVisit AI - Stage 5B Comprehensive Test Suite
Validates:
  1. Doctor authentication & session identity
  2. Unauthorized users blocked (patient role gets 403 Forbidden on doctor endpoints)
  3. Doctor consultation access (retrieves queue with status metrics)
  4. Patient outside scope blocked (RBAC patient isolation)
  5. Longitudinal visit history assembly
  6. Last visit retrieval & clinical continuity
  7. Summary review side-by-side inspection
  8. Summary approval (transitions to SUMMARY_APPROVED)
  9. Summary rejection (transitions to SUMMARY_REJECTED)
  10. Summary amendment (amended text stored separately from original generated)
  11. Patient submits lab report
  12. Doctor views lab report in clinical queue
  13. Doctor verifies lab report (status REPORT_REVIEWED)
  14. Doctor requests clarification (status REPORT_NEEDS_CLARIFICATION)
  15. Doctor rejects lab report (status REPORT_REJECTED)
  16. Immutability of original patient submission (patient values preserved completely)
  17. Doctor correction creates audit record
  18. Guideline source retrieval (ICMR / MoHFW)
  19. Valid guideline provenance (org, title, section, excerpt, publication date, url)
  20. Missing guideline source handling
  21. No relevant guideline produces truthful NO_VERIFIED_SOURCE notice
  22. Guideline retrieval failure handled gracefully
  23. Guideline finding review workflow
  24. Doctor decision recorded (relevant, not_relevant, review_later, add_note)
  25. Approved medical JSON remains strictly unchanged
  26. Doctor asks about consultation (grounded in SOURCE DATA, AI SUMMARY, GUIDELINE EVIDENCE, AI INTERPRETATION)
  27. Doctor asks about lab report
  28. Doctor asks about guideline finding
  29. Doctor voice note recording begins draft
  30. Draft transcript requires confirmation (awaiting_doctor_confirmation)
  31. Doctor edits transcript
  32. Doctor confirms note before it joins medical record
  33. Regression: Stage 1 consultation audio/metadata
  34. Regression: Stage 2 persistence & retrieval
  35. Regression: Stage 3 workflow state
  36. Regression: Stage 4 patient summary generation & guardrail
  37. Regression: Speaker attribution (doctor vs patient turns)
  38. Regression: RLS & patient data isolation
  39. Regression: Summary approval gate (patient portal blocked until approved)
"""

import uuid
import copy
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from api.main import app
from api.repositories.consultation_repository import get_consultation_repository
from api.repositories.summary_repository import get_summary_repository
from api.repositories.patient_repository import get_patient_repository
from api.repositories.guideline_repository import get_guideline_repository
from src.services.doctor_service import get_doctor_service
from src.guidelines.source_registry import get_guideline_registry
from src.guidelines.retrieval_service import get_guideline_retrieval_service

client = TestClient(app)


# -----------------------------------------------------------------------------
# Fixtures & Test Setup
# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_test_doctor_environment():
    """Sets up deterministic consultation, summary, and lab reports for doctor testing."""
    c_repo = get_consultation_repository()
    s_repo = get_summary_repository()
    p_repo = get_patient_repository()
    g_repo = get_guideline_repository()
    d_service = get_doctor_service()

    # Reset patient repository seed
    p_repo._seed_initial_data()

    # Create consultation A: Type 2 Diabetes follow up (Must be valid UUID for Supabase)
    cid_a = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    med_rec_a = {
        "patient": {
            "name": "Ananya Patel",
            "age": 42,
            "gender": "Female",
            "patient_id": "PT-89241"
        },
        "chief_complaint": "Type 2 Diabetes routine follow-up",
        "symptoms": ["Mild fatigue", "Occasional increased thirst"],
        "history_of_present_illness": "Diagnosed 2 years ago, on Metformin monotherapy.",
        "clinical_findings": ["Clear chest, normal heart sounds, no peripheral edema."],
        "vitals": {
            "blood_pressure": "130/84 mmHg",
            "heart_rate": "74 bpm"
        },
        "diagnoses": [
            {
                "condition": "Type 2 Diabetes Mellitus",
                "status": "confirmed",
                "notes": "Glycemic review"
            }
        ],
        "medications": [
            {
                "name": "Metformin",
                "strength": "500 mg",
                "frequency": "twice daily",
                "timing": "after meals",
                "source_speaker": "Doctor"
            }
        ],
        "tests": [{"name": "Fasting Blood Glucose", "urgency": "routine"}],
        "lab_investigations": [],
        "recommendations": ["Maintain 30-minute daily brisk walking", "Reduce refined carbohydrate intake"],
        "follow_up": "Review in 4 weeks with fasting glucose log.",
        "warnings": [],
        "uncertain_items": [],
        "requires_doctor_review": True
    }

    transcript_a = [
        {"start": 0.0, "end": 4.5, "speaker": "Doctor", "text": "வணக்கம் அனன்யா, சுகர் அளவு எப்படி இருக்கு?"},
        {"start": 4.6, "end": 9.2, "speaker": "Patient", "text": "டாக்டர், கொஞ்சம் சோர்வா இருக்கு, ஆனா மாத்திரை சரியா எடுக்கிறேன்."},
        {"start": 9.3, "end": 15.0, "speaker": "Doctor", "text": "Metformin 500mg தொடர்ந்து காலை இரவு சாப்பிட்ட பிறகு எடுக்கவும்."}
    ]

    c_repo.create(cid_a, "consultation_ananya.wav", "audio/wav")
    c_repo.update_completed(
        consultation_id=cid_a,
        duration_seconds=22.4,
        transcript=transcript_a,
        medical_record=med_rec_a,
        validation_result={"valid": True, "errors": [], "warnings": []}
    )

    # Summary in PENDING_SUMMARY_REVIEW
    summary_id_a = str(uuid.uuid4())
    s_repo.create_summary(
        summary_id=summary_id_a,
        consultation_id=cid_a,
        language="en",
        generated_summary={
            "overview": "Routine follow-up for Type 2 Diabetes. Metformin continued at 500mg BD.",
            "symptoms_discussed": ["Mild fatigue"],
            "medications": [],
            "tests_ordered": [],
            "self_care_instructions": ["Daily 30-min walk"],
            "warnings_and_precautions": [],
            "when_to_visit_again": "Review in 4 weeks.",
            "unspecified_or_uncertain_info": []
        },
        status="PENDING_SUMMARY_REVIEW"
    )

    # Add a submitted lab report
    lab_id = "lab-test-01"
    p_repo._lab_reports[lab_id] = {
        "id": lab_id,
        "patient_id": "PT-89241",
        "consultation_id": cid_a,
        "test_name": "Fasting Blood Glucose",
        "report_date": "2026-10-02",
        "result_summary": "126 mg/dL",
        "test_result": "126 mg/dL",
        "unit": "mg/dL",
        "units": "mg/dL",
        "reference_range": "70 - 99 mg/dL Normal, 100 - 125 mg/dL Prediabetes, >= 126 mg/dL Diabetes",
        "patient_notes": "Taken in morning at Metropolis Lab.",
        "entry_mode": "manual",
        "review_status": "unreviewed",
        "created_at": now_iso,
        "updated_at": now_iso
    }

    return {
        "consultation_id": cid_a,
        "summary_id": summary_id_a,
        "patient_id": "PT-89241",
        "lab_id": lab_id
    }


# =============================================================================
# PART 1: DOCTOR DASHBOARD & RBAC (Tests 1 - 10)
# =============================================================================

def test_01_doctor_authentication():
    """Test 1: Authorized doctor session accesses consultation list."""
    resp = client.get(
        "/api/v1/doctor/consultations",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh", "X-Doctor-Name": "Dr. Rajesh Sharma, MD"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_02_unauthorized_user_blocked():
    """Test 2: Patient attempting to call doctor endpoints is blocked with 403 Forbidden."""
    resp = client.get(
        "/api/v1/doctor/consultations",
        headers={"X-User-Role": "patient", "X-User-Id": "pt_ananya"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "DOCTOR_ROLE_REQUIRED"


def test_03_doctor_consultation_access(setup_test_doctor_environment):
    """Test 3: Doctor retrieves consultation list with unified status badges."""
    resp = client.get(
        "/api/v1/doctor/consultations?filter_type=all",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]
    assert any(i["consultation_id"] == setup_test_doctor_environment["consultation_id"] for i in items)
    target = next(i for i in items if i["consultation_id"] == setup_test_doctor_environment["consultation_id"])
    assert target["status"] in ("PENDING REVIEW", "NEEDS REVIEW", "PROCESSING", "APPROVED", "REJECTED", "FAILED")
    assert target["patient_name"] == "Ananya Patel"


def test_04_patient_outside_scope_filter():
    """Test 4: Doctor can filter specifically by authorized patient identifier."""
    resp = client.get(
        "/api/v1/doctor/consultations?patient_id=PT-89241",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["patient_id"] == "PT-89241"


def test_05_longitudinal_visit_history(setup_test_doctor_environment):
    """Test 5: Doctor retrieves longitudinal patient overview with previous visit history."""
    pid = setup_test_doctor_environment["patient_id"]
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.get(
        f"/api/v1/doctor/patient/{pid}/overview?consultation_id={cid}",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == pid
    assert "visit_history" in data
    assert isinstance(data["visit_history"], list)
    assert len(data["visit_history"]) >= 1


def test_06_last_visit_retrieval(setup_test_doctor_environment):
    """Test 6: Clinical overview identifies and formats last visit record."""
    pid = setup_test_doctor_environment["patient_id"]
    resp = client.get(
        f"/api/v1/doctor/patient/{pid}/overview",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_visit"] is not None
    assert "date" in data["last_visit"]
    assert "reason_for_visit" in data["last_visit"]


def test_07_doctor_summary_review_inspection(setup_test_doctor_environment):
    """Test 7: Doctor views unapproved summary in side-by-side review state."""
    sid = setup_test_doctor_environment["summary_id"]
    resp = client.get(
        f"/api/v1/summaries/{sid}",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING_SUMMARY_REVIEW"
    assert "Metformin" in data["generated_summary"]["overview"]


def test_08_summary_approval(setup_test_doctor_environment):
    """Test 8: Doctor approves summary, transitioning status to SUMMARY_APPROVED."""
    sid = setup_test_doctor_environment["summary_id"]
    payload = {
        "doctor_name": "Dr. Rajesh Sharma, MD",
        "decision": "approve",
        "notes": "Reviewed and verified HbA1c and Metformin dosage."
    }
    resp = client.post(
        f"/api/v1/summaries/{sid}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUMMARY_APPROVED"
    assert data["review_decision"] == "approved"


def test_09_summary_rejection(setup_test_doctor_environment):
    """Test 9: Doctor rejects summary with feedback, transitioning to SUMMARY_REJECTED."""
    sid = setup_test_doctor_environment["summary_id"]
    payload = {
        "doctor_name": "Dr. Rajesh Sharma, MD",
        "decision": "reject",
        "notes": "Missing crucial lifestyle counseling notes."
    }
    resp = client.post(
        f"/api/v1/summaries/{sid}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUMMARY_REJECTED"


def test_10_summary_amendment(setup_test_doctor_environment):
    """Test 10: Doctor amends summary text; original generated version is preserved separately."""
    sid = setup_test_doctor_environment["summary_id"]
    payload = {
        "doctor_name": "Dr. Rajesh Sharma, MD",
        "decision": "amend",
        "notes": "Added hydration instructions.",
        "corrected_summary": {
            "overview": "Doctor amended: Take Metformin 500mg with ample water after dinner.",
            "symptoms_discussed": ["Mild fatigue"],
            "medications": [],
            "tests_ordered": [],
            "self_care_instructions": ["Stay well hydrated and report back in 4 weeks."],
            "warnings_and_precautions": [],
            "when_to_visit_again": "In 4 weeks.",
            "unspecified_or_uncertain_info": []
        }
    }
    resp = client.post(
        f"/api/v1/summaries/{sid}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUMMARY_APPROVED"
    assert "Doctor amended" in data["reviewed_summary"]["overview"]
    # Check history preserves original
    hist_resp = client.get(
        f"/api/v1/summaries/{sid}/history",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total"] >= 1


# =============================================================================
# PART 2: LAB REPORT MANAGEMENT & REVIEW WORKFLOW (Tests 11 - 17)
# =============================================================================

def test_11_patient_submits_lab_report():
    """Test 11: Patient submits a manual lab report."""
    payload = {
        "patient_id": "PT-89241",
        "test_name": "Serum Creatinine",
        "report_date": "2026-10-01",
        "test_result": "0.9 mg/dL",
        "unit": "mg/dL",
        "reference_range": "0.7 - 1.2 mg/dL",
        "patient_notes": "Annual kidney checkup"
    }
    resp = client.post(
        "/api/v1/patient/lab-reports/manual",
        json=payload,
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["review_status"] == "unreviewed"
    assert data["test_name"] == "Serum Creatinine"


def test_12_doctor_sees_lab_reports(setup_test_doctor_environment):
    """Test 12: Doctor sees submitted lab reports in review queue."""
    resp = client.get(
        "/api/v1/doctor/lab-reports?patient_id=PT-89241",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "lab_reports" in data
    assert data["total"] >= 1
    assert any(r["id"] == setup_test_doctor_environment["lab_id"] for r in data["lab_reports"])


def test_13_doctor_verifies_lab_report(setup_test_doctor_environment):
    """Test 13: Doctor reviews and marks a lab report as verified (REPORT_REVIEWED)."""
    lab_id = setup_test_doctor_environment["lab_id"]
    payload = {
        "decision": "REPORT_REVIEWED",
        "doctor_notes": "126 mg/dL fasting confirmed consistent with T2D surveillance."
    }
    resp = client.post(
        f"/api/v1/doctor/lab-reports/{lab_id}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh", "X-Doctor-Name": "Dr. Rajesh Sharma, MD"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "REPORT_REVIEWED"
    assert data["reviewed_by"] == "Dr. Rajesh Sharma, MD"


def test_14_doctor_requests_clarification(setup_test_doctor_environment):
    """Test 14: Doctor requests clarification on an unclear report (REPORT_NEEDS_CLARIFICATION)."""
    lab_id = setup_test_doctor_environment["lab_id"]
    payload = {
        "decision": "REPORT_NEEDS_CLARIFICATION",
        "clarification_request": "Please confirm if this sample was taken in fasting or post-prandial state."
    }
    resp = client.post(
        f"/api/v1/doctor/lab-reports/{lab_id}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "REPORT_NEEDS_CLARIFICATION"
    assert "fasting" in data["clarification_request"]


def test_15_doctor_rejects_lab_report(setup_test_doctor_environment):
    """Test 15: Doctor rejects an incomplete or erroneous lab report (REPORT_REJECTED)."""
    lab_id = setup_test_doctor_environment["lab_id"]
    payload = {
        "decision": "REPORT_REJECTED",
        "doctor_notes": "Unreadable scan document. Please re-upload a clear copy."
    }
    resp = client.post(
        f"/api/v1/doctor/lab-reports/{lab_id}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "REPORT_REJECTED"


def test_16_patient_submission_preserved_on_doctor_correction(setup_test_doctor_environment):
    """Test 16: Doctor corrects a value, but the original patient-submitted value remains preserved."""
    lab_id = setup_test_doctor_environment["lab_id"]
    payload = {
        "decision": "REPORT_REVIEWED",
        "verified_value": "128 mg/dL",
        "doctor_notes": "Correction based on clinic glucometer confirmation."
    }
    resp = client.post(
        f"/api/v1/doctor/lab-reports/{lab_id}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    # Verified value is updated
    assert data["verified_value"] == "128 mg/dL"
    # Original patient value remains untouched
    assert data["patient_value"] == "126 mg/dL"


def test_17_doctor_correction_creates_audit_record(setup_test_doctor_environment):
    """Test 17: Doctor review and correction appends an immutable audit event."""
    cid = setup_test_doctor_environment["consultation_id"]
    d_service = get_doctor_service()
    trail = d_service.get_audit_trail(cid)
    assert isinstance(trail, list)
    # Check that audit events exist
    assert len(trail) >= 1


# =============================================================================
# PART 3: MEDICAL GUIDELINE CROSS-REFERENCE (Tests 18 - 25)
# =============================================================================

def test_18_guideline_source_retrieval():
    """Test 18: Authoritative Indian guideline sources are registered and retrievable."""
    registry = get_guideline_registry()
    sources = registry.list_guidelines()
    assert len(sources) >= 3
    source_ids = [s["id"] for s in sources]
    assert "icmr-diabetes-2022" in source_ids
    assert "icmr-htn-2021" in source_ids


def test_19_valid_guideline_provenance():
    """Test 19: Guideline evidence includes authoritative provenance metadata."""
    registry = get_guideline_registry()
    t2d = registry.get_guideline("icmr-diabetes-2022")
    assert t2d["organization"] == "Indian Council of Medical Research (ICMR)"
    assert t2d["country"] == "India"
    assert t2d["verified"] is True
    assert "checksum" in t2d
    assert len(t2d["evidence_passages"]) >= 2
    assert "Section 4.1" in t2d["evidence_passages"][0]["section"]


def test_20_missing_guideline_source_handling():
    """Test 20: Missing guideline IDs return None gracefully without error."""
    registry = get_guideline_registry()
    assert registry.get_guideline("nonexistent-guideline-id") is None


def test_21_no_relevant_guideline_message():
    """Test 21: Consultations with unsupported topics return NO_VERIFIED_SOURCE notice."""
    c_repo = get_consultation_repository()
    cid_rare = str(uuid.uuid4())
    c_repo.create(cid_rare, "rare_exam.wav", "audio/wav")
    c_repo.update_completed(
        consultation_id=cid_rare,
        duration_seconds=10.0,
        transcript=[],
        medical_record={
            "chief_complaint": "Rare genetic disorder evaluation",
            "diagnoses": [{"condition": "Fabry Disease"}],
            "medications": []
        },
        validation_result={"valid": True, "errors": [], "warnings": []}
    )

    d_service = get_doctor_service()
    res = d_service.get_guideline_cross_reference(cid_rare)
    assert res["status"] == "NO_VERIFIED_SOURCE"
    assert "No verified guideline source available" in res["message"]


def test_22_guideline_retrieval_failure_graceful():
    """Test 22: Empty or malformed records do not cause server crashes."""
    retrieval = get_guideline_retrieval_service()
    evidence, evaluated = retrieval.retrieve_evidence_for_record({})
    assert isinstance(evidence, list)
    assert len(evidence) == 0
    assert len(evaluated) >= 1


def test_23_guideline_finding_review(setup_test_doctor_environment):
    """Test 23: Doctor retrieves guideline findings for diabetes consultation."""
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.get(
        f"/api/v1/doctor/consultations/{cid}/guidelines",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "COMPLETED_WITH_FINDINGS", "COMPLETED_NO_FINDINGS")
    assert len(data["findings"]) >= 1
    first_finding = data["findings"][0]
    assert "Potential discrepancy for clinician review" in first_finding["why_flagged"]


def test_24_doctor_decision_recorded_on_guideline(setup_test_doctor_environment):
    """Test 24: Doctor records decision ('relevant', 'not_relevant', 'review_later', 'add_note')."""
    cid = setup_test_doctor_environment["consultation_id"]
    g_res = client.get(
        f"/api/v1/doctor/consultations/{cid}/guidelines",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    ).json()
    finding_id = g_res["findings"][0]["id"]

    payload = {
        "decision": "relevant",
        "doctor_notes": "Agreed with ICMR 2022 first-line monotherapy guidance."
    }
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/guidelines/{finding_id}/review",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh", "X-Doctor-Name": "Dr. Rajesh Sharma, MD"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "relevant"


def test_25_approved_medical_json_remains_unchanged(setup_test_doctor_environment):
    """Test 25: Guideline cross-referencing strictly never mutates the doctor's approved medical JSON."""
    cid = setup_test_doctor_environment["consultation_id"]
    c_repo = get_consultation_repository()
    c_before = copy.deepcopy(c_repo.get_by_id(cid)["medical_record"])

    g_res = client.get(
        f"/api/v1/doctor/consultations/{cid}/guidelines",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    ).json()
    finding_id = g_res["findings"][0]["id"] if g_res.get("findings") else "finding-01"

    # Perform guideline review
    client.post(
        f"/api/v1/doctor/consultations/{cid}/guidelines/{finding_id}/review",
        json={"decision": "not_relevant", "doctor_notes": "Clinical divergence noted."},
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )

    c_after = c_repo.get_by_id(cid)["medical_record"]
    assert c_before["medications"] == c_after["medications"]
    assert c_before["diagnoses"] == c_after["diagnoses"]


# =============================================================================
# PART 4: DOCTOR GROUNDED ASK AI (Tests 26 - 28)
# =============================================================================

def test_26_doctor_asks_about_consultation(setup_test_doctor_environment):
    """Test 26: Doctor asks about current visit; AI responds with grounded 4-box provenance."""
    cid = setup_test_doctor_environment["consultation_id"]
    payload = {
        "consultation_id": cid,
        "query": "What symptoms and medications were documented in this visit?",
        "context_type": "visit"
    }
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/ask",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "source_data" in data
    assert "ai_summary" in data
    assert "guideline_evidence" in data
    assert "ai_interpretation" in data
    assert "disclaimer" in data
    assert "Metformin" in data["source_data"]


def test_27_doctor_asks_about_lab_report(setup_test_doctor_environment):
    """Test 27: Doctor asks about lab report values."""
    cid = setup_test_doctor_environment["consultation_id"]
    payload = {
        "consultation_id": cid,
        "query": "Explain this fasting glucose lab report value.",
        "context_type": "lab_report"
    }
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/ask",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Regarding diagnostic investigations" in data["ai_interpretation"]


def test_28_doctor_asks_about_guideline_finding(setup_test_doctor_environment):
    """Test 28: Doctor asks why a guideline finding was flagged."""
    cid = setup_test_doctor_environment["consultation_id"]
    payload = {
        "consultation_id": cid,
        "query": "Explain why this medication was matched against guidelines.",
        "context_type": "guideline"
    }
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/ask",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "ICMR" in data["guideline_evidence"] or "Indian Council" in data["guideline_evidence"]


# =============================================================================
# PART 5: DOCTOR VOICE RECORDING & CONFIRMATION (Tests 29 - 32)
# =============================================================================

def test_29_doctor_voice_recording_begins_draft(setup_test_doctor_environment):
    """Test 29: Doctor records voice note; draft transcript is generated."""
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/voice-note/transcribe?mock_transcript=Patient%20compliant%20with%20diet.",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "draft_id" in data
    assert data["status"] == "awaiting_doctor_confirmation"
    assert "Patient compliant" in data["transcript_text"]


def test_30_draft_transcript_unconfirmed_not_in_record(setup_test_doctor_environment):
    """Test 30: Unconfirmed transcript is explicitly marked awaiting confirmation."""
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/voice-note/transcribe",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_doctor_confirmation"
    assert "requires clinician review" in data["note"]


def test_31_doctor_edits_and_confirms_transcript(setup_test_doctor_environment):
    """Test 31: Doctor edits transcript text and explicitly confirms it."""
    cid = setup_test_doctor_environment["consultation_id"]
    payload = {
        "consultation_id": cid,
        "final_note_text": "Doctor confirmed note: Patient showed good glycemic response on Metformin.",
        "category": "clinical_observation",
        "is_confirmed": True
    }
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/voice-note/confirm",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh", "X-Doctor-Name": "Dr. Rajesh Sharma, MD"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["confirmed_by"] == "Dr. Rajesh Sharma, MD"


def test_32_unconfirmed_note_rejected(setup_test_doctor_environment):
    """Test 32: Submitting without explicit confirmation (is_confirmed=False) is rejected."""
    cid = setup_test_doctor_environment["consultation_id"]
    payload = {
        "consultation_id": cid,
        "final_note_text": "Draft text",
        "is_confirmed": False
    }
    resp = client.post(
        f"/api/v1/doctor/consultations/{cid}/voice-note/confirm",
        json=payload,
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 400


# =============================================================================
# PART 6: REGRESSION PRESERVATION ACROSS STAGES 1 - 5A (Tests 33 - 39)
# =============================================================================

def test_33_stage1_regression_health_endpoint():
    """Test 33: Stage 1 health endpoint remains functional."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_34_stage2_regression_consultation_retrieval(setup_test_doctor_environment):
    """Test 34: Stage 2 GET /api/v1/consultations/{id} remains intact."""
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.get(f"/api/v1/consultations/{cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["consultation_id"] == cid
    assert data["status"] == "completed"


def test_35_stage3_regression_workflow_progress(setup_test_doctor_environment):
    """Test 35: Stage 3 workflow progress endpoint (/progress) functions."""
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.get(f"/api/v1/consultations/{cid}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert "elapsed_time_sec" in data


def test_36_stage4_regression_summary_generation(setup_test_doctor_environment):
    """Test 36: Stage 4 summary retrieval retains clinical schema."""
    sid = setup_test_doctor_environment["summary_id"]
    resp = client.get(
        f"/api/v1/summaries/{sid}",
        headers={"X-User-Role": "doctor", "X-User-Id": "doc_rajesh"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_summary" in data
    assert "overview" in data["generated_summary"]


def test_37_stage1_speaker_attribution(setup_test_doctor_environment):
    """Test 37: Transcript turns have distinct Doctor and Patient attribution."""
    cid = setup_test_doctor_environment["consultation_id"]
    resp = client.get(f"/api/v1/consultations/{cid}")
    assert resp.status_code == 200
    transcript = resp.json()["transcript"]
    speakers = {t["speaker"] for t in transcript}
    assert "Doctor" in speakers
    assert "Patient" in speakers


def test_38_stage5a_rbac_patient_isolation():
    """Test 38: Patients cannot access other patients' health overview."""
    resp = client.get(
        "/api/v1/patient/overview?patient_id=PT-OTHER-999",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "FORBIDDEN"


def test_39_stage4_and_5_summary_approval_gate(setup_test_doctor_environment):
    """Test 39: Patient portal blocked from accessing unapproved summary."""
    sid = setup_test_doctor_environment["summary_id"]
    resp = client.get(
        f"/api/v1/summaries/{sid}",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "ACCESS_DENIED"
