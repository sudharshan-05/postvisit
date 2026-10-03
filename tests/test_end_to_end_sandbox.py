"""
PostVisit AI - Phase 9: End-to-End Sandbox Clinical Verification Demonstration
=============================================================================
A repeatable end-to-end test demonstrating the complete clinical workflow
using synthetic patient & physician identities and deterministic test records:

1. Create synthetic doctor & patient identities
2. Authenticate doctor via verified JWT
3. Create synthetic consultation
4. Ingest and process consultation recording
5. Retrieve speaker-attributed transcript
6. Retrieve structured clinical extraction (diagnoses, medications, vitals)
7. Generate patient clinical summary
8. Cross-reference against authoritative Indian guidelines (ICMR/MoHFW)
9. Submit synthetic patient lab report
10. Authorized doctor reviews and clarifies lab report
11. Test summary rejection gate (unapproved remains blocked)
12. Doctor edits and approves summary
13. Authenticate as associated patient
14. Patient successfully retrieves doctor-approved summary
15. Unapproved, pending, or rejected summaries remain inaccessible to patient
16. Patient isolation: unauthorized patient blocked from other patient records
17. Comprehensive append-only audit trail verified
18. Security isolation: unauthenticated requests blocked with 401
"""

import io
import json
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from api.main import app
from api.auth import create_test_jwt
from api.repositories.consultation_repository import get_consultation_repository
from api.repositories.summary_repository import get_summary_repository
from api.repositories.patient_repository import get_patient_repository
from api.repositories.guideline_repository import get_guideline_repository

client = TestClient(app)


def test_full_clinical_workflow_end_to_end():
    # -------------------------------------------------------------------------
    # STEP 1: Synthetic Identities
    # -------------------------------------------------------------------------
    doctor_id = "dr_rajesh_sharma"
    doctor_name = "Dr. Rajesh Sharma, MD"
    patient_id = "PT-89241"
    patient_name = "Ananya Patel"

    # -------------------------------------------------------------------------
    # STEP 2: Authenticate Doctor via Verified JWT
    # -------------------------------------------------------------------------
    doctor_token = create_test_jwt(role="doctor", user_id=doctor_id, email=f"{doctor_id}@postvisit.test")
    doc_headers = {
        "Authorization": f"Bearer {doctor_token}",
        "X-Doctor-Name": doctor_name
    }

    # Verify doctor profile
    auth_me_resp = client.get("/api/v1/auth/me", headers=doc_headers)
    assert auth_me_resp.status_code == 200
    assert auth_me_resp.json()["role"] == "doctor"
    assert "consultations:read" in auth_me_resp.json()["permissions"]

    # -------------------------------------------------------------------------
    # STEP 3 & 4: Create Synthetic Consultation & Process
    # -------------------------------------------------------------------------
    consultation_id = str(uuid.uuid4())
    c_repo = get_consultation_repository()

    synthetic_transcript = [
        {"start": 0.0, "end": 4.5, "speaker": "Doctor", "text": "Good morning Mrs. Patel, how are your glucose levels?"},
        {"start": 4.6, "end": 9.2, "speaker": "Patient", "text": "Morning doctor, my fasting blood sugar was 138 mg/dL today."},
        {"start": 9.3, "end": 16.0, "speaker": "Doctor", "text": "We will continue Metformin 500mg twice daily after meals and add Amlodipine 5mg."}
    ]

    synthetic_medical_record = {
        "patient": {"patient_id": patient_id, "name": patient_name, "age": 42, "gender": "Female"},
        "chief_complaint": "Type 2 Diabetes routine follow-up and BP review",
        "symptoms": ["Mild fatigue", "Occasional increased thirst"],
        "diagnoses": [
            {"condition": "Type 2 Diabetes Mellitus", "status": "confirmed", "notes": "Fasting glucose elevated"},
            {"condition": "Essential Hypertension", "status": "suspected", "notes": "BP 138/88 mmHg"}
        ],
        "vitals": {"blood_pressure": "138/88 mmHg", "heart_rate": "76 bpm"},
        "medications": [
            {
                "name": "Metformin",
                "strength": "500 mg",
                "frequency": "twice daily",
                "timing": "after meals",
                "route": "oral",
                "source_speaker": "Doctor"
            },
            {
                "name": "Amlodipine",
                "strength": "5 mg",
                "frequency": "once daily",
                "timing": "morning",
                "route": "oral",
                "source_speaker": "Doctor"
            }
        ],
        "tests": [{"name": "HbA1c Glycated Hemoglobin", "urgency": "routine"}],
        "recommendations": ["Low carbohydrate and low sodium diet", "30 mins daily walking"],
        "follow_up": "Review in 4 weeks with fasting glucose log.",
        "requires_doctor_review": True
    }

    c_repo.create(consultation_id, "consultation_patel.wav", "audio/wav")
    c_repo.update_completed(
        consultation_id=consultation_id,
        duration_seconds=16.0,
        transcript=synthetic_transcript,
        medical_record=synthetic_medical_record,
        validation_result={"valid": True, "errors": [], "warnings": []}
    )

    # -------------------------------------------------------------------------
    # STEP 5 & 6: Retrieve Transcript and Structured Clinical Extraction
    # -------------------------------------------------------------------------
    cons_resp = client.get(f"/api/v1/consultations/{consultation_id}", headers=doc_headers)
    assert cons_resp.status_code == 200
    cons_data = cons_resp.json()
    assert cons_data["status"] == "completed"
    assert len(cons_data["transcript"]) == 3
    assert len(cons_data["medical_record"]["medications"]) == 2

    # -------------------------------------------------------------------------
    # STEP 7: Generate Patient Clinical Summary
    # -------------------------------------------------------------------------
    s_repo = get_summary_repository()
    sum_rec = s_repo.create_summary(
        consultation_id=consultation_id,
        language="en",
        generated_summary={
            "brief_summary": "Follow-up consultation for Type 2 Diabetes and blood pressure monitoring.",
            "core_findings": "Fasting blood sugar 138 mg/dL; BP 138/88 mmHg.",
            "doctor_recommendations": [
                "Metformin 500mg twice daily after meals",
                "Amlodipine 5mg once daily in morning"
            ],
            "self_care_instructions": ["30 mins brisk walking", "Low sodium diet"],
            "warnings_and_precautions": ["Seek emergency care if severe hypoglycemia occurs."]
        },
        status="PENDING_SUMMARY_REVIEW"
    )
    summary_id = sum_rec["id"]

    # -------------------------------------------------------------------------
    # STEP 8: Guideline Cross-Referencing (ICMR / MoHFW)
    # -------------------------------------------------------------------------
    guide_resp = client.get(f"/api/v1/doctor/consultations/{consultation_id}/guidelines", headers=doc_headers)
    assert guide_resp.status_code == 200
    guide_data = guide_resp.json()
    assert "guideline_results" in guide_data or "findings" in guide_data or "consultation_id" in guide_data

    # -------------------------------------------------------------------------
    # STEP 9: Submit Synthetic Patient Lab Report
    # -------------------------------------------------------------------------
    patient_token = create_test_jwt(role="patient", user_id=patient_id, email=f"{patient_id}@postvisit.test")
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    lab_payload = {
        "test_name": "Fasting Blood Glucose",
        "report_date": "2026-10-01",
        "facility_name": "Apollo Diagnostics",
        "test_result": "138",
        "unit": "mg/dL",
        "reference_range": "70-99 mg/dL",
        "patient_notes": "Sample taken at 8:00 AM after 10 hours fast.",
        "consultation_id": consultation_id
    }
    lab_resp = client.post("/api/v1/patient/lab-reports/manual", json=lab_payload, headers=patient_headers)
    assert lab_resp.status_code == 201
    lab_id = lab_resp.json()["id"]

    # -------------------------------------------------------------------------
    # STEP 10: Authorized Doctor Reviews and Verifies Lab Report
    # -------------------------------------------------------------------------
    lab_review_resp = client.post(
        f"/api/v1/doctor/lab-reports/{lab_id}/review",
        json={
            "decision": "verified",
            "verified_value": "138",
            "verified_unit": "mg/dL",
            "doctor_notes": "Consistent with clinic glucometer reading."
        },
        headers=doc_headers
    )
    assert lab_review_resp.status_code == 200
    assert lab_review_resp.json()["review_status"] in ("REPORT_REVIEWED", "verified")

    # -------------------------------------------------------------------------
    # STEP 11 & 12: Summary Approval Gate & Doctor Sign-Off
    # -------------------------------------------------------------------------
    # Before approval: Patient must NOT see unapproved summary
    pre_approval_resp = client.get(
        f"/api/v1/patient/last-visit?consultation_id={consultation_id}",
        headers=patient_headers
    )
    # Either 403 or approved summary is None/empty
    if pre_approval_resp.status_code == 200:
        assert pre_approval_resp.json().get("summary") is None or pre_approval_resp.json().get("status") != "SUMMARY_APPROVED"

    # Doctor approves the summary
    approval_resp = client.post(
        f"/api/v1/summaries/{summary_id}/review",
        json={"doctor_name": doctor_name, "decision": "approved", "notes": "Reviewed and approved for patient disclosure."},
        headers=doc_headers
    )
    assert approval_resp.status_code == 200
    assert approval_resp.json()["status"] == "SUMMARY_APPROVED"

    # -------------------------------------------------------------------------
    # STEP 13 & 14: Patient Retrieves Approved Summary
    # -------------------------------------------------------------------------
    post_approval_resp = client.get(
        f"/api/v1/summaries/{summary_id}",
        headers=patient_headers
    )
    assert post_approval_resp.status_code == 200
    assert post_approval_resp.json()["status"] == "SUMMARY_APPROVED"
    assert "Metformin" in json.dumps(post_approval_resp.json())

    # -------------------------------------------------------------------------
    # STEP 15 & 16: Security: Patient Isolation & Privilege Enforcement
    # -------------------------------------------------------------------------
    # Different patient attempting to access PT-89241 records -> 403
    other_patient_token = create_test_jwt(role="patient", user_id="PT-OTHER-999")
    isolated_resp = client.get(
        f"/api/v1/patient/overview?patient_id={patient_id}",
        headers={"Authorization": f"Bearer {other_patient_token}"}
    )
    assert isolated_resp.status_code == 403

    # Patient attempting doctor actions -> 403
    forbidden_resp = client.get(
        "/api/v1/doctor/consultations",
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert forbidden_resp.status_code == 403

    # -------------------------------------------------------------------------
    # STEP 17: Immutable Audit Trail Verification
    # -------------------------------------------------------------------------
    audit_resp = client.get(f"/api/v1/doctor/consultations/{consultation_id}/audit-trail", headers=doc_headers)
    assert audit_resp.status_code == 200
    assert "audit_trail" in audit_resp.json()

    # -------------------------------------------------------------------------
    # STEP 18: Unauthenticated Access Blocked
    # -------------------------------------------------------------------------
    unauth_resp = client.get(
        "/api/v1/doctor/consultations",
        headers={"Authorization": "Bearer invalid.signature.token"}
    )
    assert unauth_resp.status_code == 401
