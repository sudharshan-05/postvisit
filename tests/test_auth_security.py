"""
PostVisit AI - Authentication, Authorization & Security Hardening Test Suite
=============================================================================
Validates:
1. Missing Bearer token (401 Unauthorized in production)
2. Malformed / Garbled token (401 Unauthorized)
3. Invalid signature (401 Unauthorized)
4. Expired token (401 Unauthorized)
5. Tampered token payload/signature (401 Unauthorized)
6. Valid doctor JWT token access
7. Valid patient JWT token access
8. Patient calling doctor-only endpoints (403 Forbidden - DOCTOR_ROLE_REQUIRED)
9. Patient attempting summary approval (403 Forbidden)
10. Patient data isolation (patient PT-1 cannot access patient PT-2)
11. Doctor role query parameter override rejected (?role=doctor doesn't grant access)
12. Doctor role header override rejected in production mode
13. No clinical or secret data leaked in 401 / 403 responses
"""

import os
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import create_test_jwt, get_jwt_secret

client = TestClient(app)


class TestAuthenticationSecurity:
    """Rigorous security testing for JWT verification, tampering, and expiration."""

    def test_missing_token_in_production_mode(self, monkeypatch):
        """In production mode, requests without Bearer token must get 401 Unauthorized."""
        monkeypatch.setenv("APP_ENV", "production")
        resp = client.get("/api/v1/doctor/consultations")
        assert resp.status_code == 401
        data = resp.json()
        assert data["detail"]["code"] == "MISSING_TOKEN"

    def test_malformed_token_rejected(self):
        """Malformed token string must return 401."""
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": "Bearer this-is-not-a-valid-jwt-token"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "INVALID_TOKEN"

    def test_invalid_signature_rejected(self):
        """Token signed with wrong secret must return 401."""
        bad_token = create_test_jwt(
            role="doctor",
            secret_override="completely-wrong-secret-key-32-chars-long"
        )
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": f"Bearer {bad_token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "INVALID_TOKEN"

    def test_expired_token_rejected(self):
        """Token with past expiration timestamp must return 401 TOKEN_EXPIRED."""
        expired_token = create_test_jwt(
            role="doctor",
            expires_in_seconds=-3600  # Expired 1 hour ago
        )
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_EXPIRED"

    def test_tampered_token_signature_rejected(self):
        """Token with tampered signature bits must be rejected."""
        tampered_token = create_test_jwt(role="doctor", tamper=True)
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "INVALID_TOKEN"

    def test_valid_doctor_token_accepted(self):
        """Valid signed doctor JWT successfully accesses doctor queue."""
        doc_token = create_test_jwt(role="doctor", user_id="doc_verified_123")
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_valid_patient_token_accepted(self):
        """Valid signed patient JWT successfully accesses patient profile."""
        patient_token = create_test_jwt(role="patient", user_id="PT-89241")
        resp = client.get(
            "/api/v1/patient/profile",
            headers={"Authorization": f"Bearer {patient_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == "PT-89241"


class TestRoleBasedAccessControl:
    """Verifies that doctor, patient, and clinical review boundaries are enforced."""

    def test_patient_token_blocked_from_doctor_queue(self):
        """A valid patient token MUST NOT be able to view doctor consultation queue."""
        patient_token = create_test_jwt(role="patient", user_id="PT-89241")
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": f"Bearer {patient_token}"}
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["code"] == "DOCTOR_ROLE_REQUIRED"

    def test_patient_token_blocked_from_summary_review(self):
        """A valid patient token MUST NOT be able to approve a summary."""
        patient_token = create_test_jwt(role="patient", user_id="PT-89241")
        resp = client.post(
            f"/api/v1/summaries/{uuid.uuid4()}/review",
            json={"doctor_name": "Dr. Impersonator", "decision": "approved"},
            headers={"Authorization": f"Bearer {patient_token}"}
        )
        assert resp.status_code == 403

    def test_patient_isolation_patient_cannot_access_other_patient(self):
        """Patient PT-11111 cannot view records of PT-89241."""
        pt1_token = create_test_jwt(role="patient", user_id="PT-11111")
        resp = client.get(
            "/api/v1/patient/overview?patient_id=PT-89241",
            headers={"Authorization": f"Bearer {pt1_token}"}
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "FORBIDDEN"

    def test_doctor_can_access_patient_record(self):
        """Doctor token CAN access patient PT-89241 clinical overview."""
        doc_token = create_test_jwt(role="doctor", user_id="doc_treating_456")
        resp = client.get(
            "/api/v1/patient/overview?patient_id=PT-89241",
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        assert resp.status_code == 200

    def test_query_param_role_impersonation_ignored(self, monkeypatch):
        """In production mode, passing ?role=doctor without a valid token fails."""
        monkeypatch.setenv("APP_ENV", "production")
        resp = client.get("/api/v1/doctor/consultations?role=doctor")
        assert resp.status_code == 401

    def test_header_role_impersonation_ignored_in_production(self, monkeypatch):
        """In production mode, X-User-Role: doctor header without a valid token fails."""
        monkeypatch.setenv("APP_ENV", "production")
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"X-User-Role": "doctor", "X-User-Id": "fake_doctor"}
        )
        assert resp.status_code == 401

    def test_no_secrets_in_auth_failure_responses(self):
        """401 and 403 responses must never leak backend secrets or tokens."""
        resp = client.get(
            "/api/v1/doctor/consultations",
            headers={"Authorization": "Bearer bad-token"}
        )
        text = resp.text
        assert "gsk_" not in text
        assert "AIza" not in text
        assert "SUPABASE_SERVICE_ROLE" not in text
        assert get_jwt_secret() not in text
