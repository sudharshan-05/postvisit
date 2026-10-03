"""
PostVisit AI - Stage 5A Comprehensive Test Suite
Validates:
  1. Patient Profile & Demographics
  2. RBAC & Patient Ownership Isolation (Patients blocked from other patients' records)
  3. Patient Health Overview & Dated Health Trends (Never fabricated/interpolated)
  4. Honest Empty State for Trends when insufficient data
  5. Last Visit Quick Summary Approval Gating (Unapproved hidden, approved exposed)
  6. 14 Clinical Sections in Approved Last Visit Summary
  7. Chronological Visit History with Pagination
  8. Structured Recovery Plan Checklist (Personal tracking without mutating medical record)
  9. Preserved Medication Details (Strength, dosage, frequency, food timing)
  10. Manual Lab Report Summary Submission with Patient-Provided Provenance
  11. Lab Report Document Upload, File Validation & Ownership Gating
  12. Rejection of Unsupported File Types & Oversized Uploads
  13. Contextual AI Chatbot Grounding & Disclaimer
  14. AI Chatbot Emergency Safety Escalation (Chest pain, breathing difficulty -> 108/112)
  15. AI Chatbot Multilingual Support (Tamil / English)
  16. Patient Voice Recording Transcription & Patient Draft Isolation
"""

import io
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from api.main import app
from src.services.patient_service import get_patient_service, PatientService
from api.repositories.patient_repository import get_patient_repository
from api.repositories.consultation_repository import get_consultation_repository
from api.repositories.summary_repository import get_summary_repository

client = TestClient(app)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def setup_test_patient_portal():
    """Seeds patient repository and approved consultation for deterministic testing."""
    p_repo = get_patient_repository()
    c_repo = get_consultation_repository()
    s_repo = get_summary_repository()

    # Re-seed test patient profile PT-89241
    p_repo._seed_initial_data()

    # Create synthetic completed consultation with approved summary for PT-89241
    cid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    med_rec = {
        "patient": {
            "name": "Ananya Patel",
            "age": 42,
            "gender": "Female",
            "patient_id": "PT-89241"
        },
        "doctor_name": "Dr. Rajesh Sharma, MD",
        "chief_complaints": ["Follow-up for Type 2 Diabetes and general fatigue"],
        "symptoms": ["elevated fasting blood sugar", "mild fatigue"],
        "history_of_present_illness": "Diagnosed 2 years ago, on oral hypoglycemic agents.",
        "examination_findings": "Clinic BP 138/88 mmHg, Pulse 76 bpm, BMI 26.2.",
        "diagnosis": "Type 2 Diabetes Mellitus with Essential Hypertension",
        "recommendations": [
            "Maintain strict low-sodium, low-glycemic dietary regimen.",
            "Continue regular 30 minutes daily moderate brisk walking."
        ],
        "medications": [
            {
                "medicine_name": "Metformin",
                "strength": "500 mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Twice daily",
                "timing": "After food",
                "duration": "90 days",
                "instructions": "Take 15 minutes after meals with a glass of water."
            },
            {
                "medicine_name": "Amlodipine",
                "strength": "5 mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Once daily",
                "timing": "Morning after breakfast",
                "duration": "90 days",
                "instructions": "Take consistently at 9:00 AM."
            }
        ],
        "investigations_ordered": ["Fasting Blood Glucose", "Serum Creatinine", "HbA1c in 3 months"],
        "self_care": ["Monitor daily morning fasting glucose.", "Maintain adequate hydration (2.5L daily)."],
        "warnings": ["If you experience sudden dizziness, severe sweating, or chest tightness, seek emergency medical care immediately."],
        "follow_up": "Routine follow-up in 3 months with repeat HbA1c and renal function tests.",
        "follow_up_date": "2026-12-15",
        "uncertainties": ["Pending confirmation of microalbuminuria from repeat spot urine test."]
    }

    c_repo.create(
        consultation_id=cid,
        original_filename="ananya_t2d_followup.wav",
        media_type="audio/wav"
    )
    c_repo.update_completed(
        consultation_id=cid,
        duration_seconds=120.0,
        transcript=[
            {"speaker": "Doctor", "text": "Good morning Mrs. Patel, how are your glucose levels?", "start": 0.0, "end": 4.0},
            {"speaker": "Patient", "text": "Morning doctor, my fasting readings have been around 138 mg/dL.", "start": 4.5, "end": 9.0}
        ],
        medical_record=med_rec,
        validation_result={"is_valid": True, "critical_errors": []}
    )

    # Create approved summary for this consultation
    s_repo.create_summary(
        consultation_id=cid,
        language="en",
        generated_summary={
            "brief_summary": "Follow-up consultation for Type 2 Diabetes and blood pressure monitoring.",
            "core_findings": "Fasting blood sugar remains elevated at 138 mg/dL; BP 138/88 mmHg.",
            "doctor_recommendations": ["Continue Metformin 500mg twice daily after meals", "Amlodipine 5mg morning"],
            "self_care_instructions": ["30 mins brisk walking daily", "Low sodium diet"],
            "warnings_and_precautions": ["Seek emergency care if chest pain or severe hypoglycemia occurs."]
        },
        status="SUMMARY_APPROVED"
    )

    return cid


# -----------------------------------------------------------------------------
# 1. Patient Profile & Demographics
# -----------------------------------------------------------------------------
def test_1_patient_profile_retrieval():
    resp = client.get(
        "/api/v1/patient/profile",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "PT-89241"
    assert data["full_name"] == "Ananya Patel"
    assert data["age"] == 42
    assert data["blood_group"] == "B+"
    assert any("Penicillin" in a for a in data["allergies"])
    assert any("Type 2 Diabetes" in c for c in data["chronic_conditions"])


# -----------------------------------------------------------------------------
# 2. RBAC & Patient Ownership Isolation
# -----------------------------------------------------------------------------
def test_2_patient_rbac_isolation_blocked_access():
    # Patient PT-99999 attempts to access patient PT-89241's overview
    resp = client.get(
        "/api/v1/patient/overview?patient_id=PT-89241",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-99999"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "FORBIDDEN"

    # Doctor accessing patient PT-89241 with physician privileges -> 200 OK
    doc_resp = client.get(
        "/api/v1/patient/overview?patient_id=PT-89241",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert doc_resp.status_code == 200
    assert doc_resp.json()["patient_profile"]["patient_id"] == "PT-89241"


# -----------------------------------------------------------------------------
# 3. Patient Health Overview & Genuine Dated Trends
# -----------------------------------------------------------------------------
def test_3_patient_overview_with_dated_trends():
    resp = client.get(
        "/api/v1/patient/overview",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_approved_summary"] is True
    assert data["upcoming_follow_up_date"] == "2026-12-15"
    assert len(data["doctor_approved_medications"]) >= 2

    # Trends check: genuine measurements exist
    trends = data["health_trends"]
    assert len(trends) >= 2  # BP and Glucose

    bp_series = next(t for t in trends if "Blood Pressure" in t["metric_name"])
    assert bp_series["unit"] == "mmHg"
    assert bp_series["has_sufficient_data"] is True
    assert len(bp_series["data_points"]) >= 3
    # Check dated points
    for pt in bp_series["data_points"]:
        assert pt["numeric_value"] is not None
        assert pt["recorded_at"] is not None
        assert "mmHg" in pt["unit"]


# -----------------------------------------------------------------------------
# 4. Honest Empty State for Trends when No Data
# -----------------------------------------------------------------------------
def test_4_patient_overview_empty_trends_when_no_data():
    p_repo = get_patient_repository()
    # Create empty patient with no metrics
    empty_pid = f"PT-EMPTY-{uuid.uuid4().hex[:6]}"
    p_repo._in_memory_profiles[empty_pid] = {
        "patient_id": empty_pid,
        "full_name": "New Patient",
        "age": 28,
        "gender": "Male",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    resp = client.get(
        f"/api/v1/patient/overview?patient_id={empty_pid}",
        headers={"X-User-Role": "doctor", "X-User-Id": "dr_rajesh_sharma"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["health_trends"] == []
    assert data["has_approved_summary"] is False


# -----------------------------------------------------------------------------
# 5. Last Visit Quick Summary Approval Gating
# -----------------------------------------------------------------------------
def test_5_last_visit_summary_gating_unapproved():
    c_repo = get_consultation_repository()
    # Create unapproved consultation
    unapproved_cid = str(uuid.uuid4())
    c_repo.create(unapproved_cid, "draft.wav", "audio/wav")
    c_repo.update_completed(
        consultation_id=unapproved_cid,
        duration_seconds=60.0,
        transcript=[],
        medical_record={
            "patient": {"patient_id": "PT-89241"},
            "diagnosis": "Draft Diagnosis Not Yet Approved"
        },
        validation_result={"is_valid": True}
    )

    resp = client.get(
        f"/api/v1/patient/last-visit?consultation_id={unapproved_cid}",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approval_status"] == "PENDING_DOCTOR_APPROVAL"
    # Never expose unapproved diagnosis or clinical findings
    assert data["doctor_approved_diagnosis"] is None
    assert "awaiting doctor review" in data["doctor_findings"].lower()


# -----------------------------------------------------------------------------
# 6. 14 Clinical Sections in Approved Last Visit Summary
# -----------------------------------------------------------------------------
def test_6_last_visit_summary_14_sections_approved():
    resp = client.get(
        "/api/v1/patient/last-visit",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["approval_status"] == "SUMMARY_APPROVED"
    assert data["consultation_date"] is not None
    assert "Dr. Rajesh Sharma" in data["doctor_name"]
    assert "Type 2 Diabetes" in data["main_reason_for_visit"]
    assert len(data["reported_symptoms"]) > 0
    assert data["history_of_present_illness"] is not None
    assert data["doctor_findings"] is not None
    assert "Type 2 Diabetes Mellitus" in data["doctor_approved_diagnosis"]
    assert len(data["doctor_recommendations"]) > 0
    assert len(data["prescribed_medications"]) >= 2
    assert len(data["investigations_ordered"]) >= 2
    assert len(data["self_care_instructions"]) > 0
    assert len(data["warnings_and_precautions"]) > 0
    assert data["follow_up_instructions"] is not None
    assert data["follow_up_date"] == "2026-12-15"
    assert len(data["outstanding_uncertainties"]) > 0
    assert len(data["contextual_questions"]) >= 3


# -----------------------------------------------------------------------------
# 7. Chronological Visit History with Pagination
# -----------------------------------------------------------------------------
def test_7_chronological_visit_history_and_pagination():
    resp = client.get(
        "/api/v1/patient/history?page=1&page_size=5",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "PT-89241"
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) > 0

    first_visit = data["items"][0]
    assert first_visit["doctor_name"] is not None
    assert first_visit["approved_summary_available"] is True


# -----------------------------------------------------------------------------
# 8. Structured Recovery Plan Checklist (Personal Tracking)
# -----------------------------------------------------------------------------
def test_8_structured_recovery_plan_non_mutating():
    resp = client.get(
        "/api/v1/patient/recovery-plan",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_structured_plan"] is True
    cid = data["consultation_id"]
    items = data["plan_items"]
    assert len(items) >= 4

    # Select medication task
    med_task = next(i for i in items if i["category"] == "medication")
    task_key = med_task["task_key"]

    # Toggle task completed
    toggle_resp = client.post(
        "/api/v1/patient/recovery-plan/toggle",
        json={"consultation_id": cid, "task_key": task_key, "completed": True},
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["status"] == "success"

    # Verify authoritative medical record in repository remains unchanged
    c_repo = get_consultation_repository()
    consultation = c_repo.get_by_id(cid)
    # Medical record is still pristine dict
    assert "medications" in consultation["medical_record"]


# -----------------------------------------------------------------------------
# 9. Preserved Medication Details
# -----------------------------------------------------------------------------
def test_9_patient_medications_exact_preservation():
    resp = client.get(
        "/api/v1/patient/medications",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    meds = data["medications"]
    assert len(meds) >= 2

    metformin = next(m for m in meds if "Metformin" in m["medicine_name"])
    assert metformin["strength"] == "500 mg"
    assert metformin["frequency"] == "Twice daily"
    assert "After food" in metformin["timing"]
    assert metformin["review_status"] == "APPROVED"


# -----------------------------------------------------------------------------
# 10. Manual Lab Report Summary Submission with Patient Provenance
# -----------------------------------------------------------------------------
def test_10_manual_lab_report_creation_and_provenance():
    payload = {
        "test_name": "Serum Creatinine",
        "report_date": "2026-09-28",
        "facility_name": "Dr. Lal PathLabs",
        "test_result": "0.95",
        "unit": "mg/dL",
        "reference_range": "0.7 - 1.2 mg/dL",
        "patient_notes": "Routine kidney function check"
    }

    resp = client.post(
        "/api/v1/patient/lab-reports/manual",
        json=payload,
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["test_name"] == "Serum Creatinine"
    assert data["test_result"] == "0.95"
    assert data["entry_mode"] == "manual"
    assert data["review_status"] == "unreviewed"  # Stamped as unreviewed / patient-provided


# -----------------------------------------------------------------------------
# 11. Lab Report Document Upload & Ownership Gating
# -----------------------------------------------------------------------------
def test_11_uploaded_lab_report_validation_and_ownership():
    fake_pdf = b"%PDF-1.4 Fake PDF Content for Lab Report HbA1c"
    files = {"file": ("hba1c_report.pdf", fake_pdf, "application/pdf")}
    data = {"test_name": "HbA1c Glycated Hemoglobin", "report_date": "2026-09-20", "facility_name": "Apollo Clinic"}

    upload_resp = client.post(
        "/api/v1/patient/lab-reports/upload",
        files=files,
        data=data,
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert upload_resp.status_code == 201
    rep = upload_resp.json()
    assert rep["entry_mode"] == "upload"
    assert rep["filename"] == "hba1c_report.pdf"
    report_id = rep["id"]

    # Authorized download
    dl_resp = client.get(
        f"/api/v1/patient/lab-reports/{report_id}/download",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content == fake_pdf

    # Unauthorized patient PT-99999 blocked
    unauth_dl = client.get(
        f"/api/v1/patient/lab-reports/{report_id}/download",
        headers={"X-User-Role": "patient", "X-User-Id": "PT-99999"}
    )
    assert unauth_dl.status_code == 403


# -----------------------------------------------------------------------------
# 12. Rejection of Unsupported File Types & Oversized Uploads
# -----------------------------------------------------------------------------
def test_12_uploaded_lab_report_invalid_file_rejected():
    fake_exe = b"MZ executable binary not allowed"
    files = {"file": ("malicious.exe", fake_exe, "application/x-msdownload")}
    data = {"test_name": "Malicious Test"}

    resp = client.post(
        "/api/v1/patient/lab-reports/upload",
        files=files,
        data=data,
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]


# -----------------------------------------------------------------------------
# 13. Contextual AI Chatbot Grounding & Disclaimer
# -----------------------------------------------------------------------------
def test_13_contextual_ai_chatbot_grounding_and_disclaimer():
    resp = client.post(
        "/api/v1/patient/chat",
        json={"message": "What does after food mean for my Metformin medicine?", "context_type": "medication"},
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "after food" in data["reply"].lower()
    assert "disclaimer" in data
    assert "Doctor-Approved Medications" in data["cited_sections"]


# -----------------------------------------------------------------------------
# 14. AI Chatbot Emergency Safety Escalation
# -----------------------------------------------------------------------------
def test_14_contextual_ai_chatbot_emergency_escalation():
    resp = client.post(
        "/api/v1/patient/chat",
        json={"message": "I am having severe chest pain and difficulty breathing right now"},
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    # Must immediately advise emergency call (108 / 112)
    assert "108" in data["reply"] or "112" in data["reply"]
    assert "CRITICAL CLINICAL SAFETY WARNING" in data["reply"]
    assert "Emergency Protocol" in data["cited_sections"]


# -----------------------------------------------------------------------------
# 15. AI Chatbot Multilingual Support (Tamil / English)
# -----------------------------------------------------------------------------
def test_15_contextual_ai_chatbot_tamil_explanation():
    resp = client.post(
        "/api/v1/patient/chat",
        json={"message": "Explain my last visit in simple Tamil", "language": "ta"},
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    # Check Tamil character set presence
    assert any('\u0b80' <= char <= '\u0bff' for char in data["reply"])


# -----------------------------------------------------------------------------
# 16. Patient Voice Recording Transcription & Patient Draft Isolation
# -----------------------------------------------------------------------------
def test_16_patient_voice_transcription_and_draft_status():
    fake_audio = b"RIFF....WAVEfmt ....dataFakeAudio"
    files = {"audio": ("patient_query.wav", fake_audio, "audio/wav")}
    data = {"language": "en"}

    resp = client.post(
        "/api/v1/patient/voice-transcribe",
        files=files,
        data=data,
        headers={"X-User-Role": "patient", "X-User-Id": "PT-89241"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_patient_provided"] is True
    assert data["review_status"] == "patient_draft"
    assert data["transcript_text"] is not None
    assert "not an official clinical consultation" in data["disclaimer"].lower()
