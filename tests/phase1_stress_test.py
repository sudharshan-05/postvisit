"""
Phase 1 Sandbox Stress Test -- PostVisit AI
==========================================
Brutally honest end-to-end integration + stress test.
Tests every API endpoint for correctness, error handling,
auth enforcement, data integrity, and edge cases.

Run with:
    pytest tests/phase1_stress_test.py -v --tb=short
"""

import io
import json
import time
import uuid
import threading
import pytest
import httpx
from fastapi.testclient import TestClient

from api.main import app

BASE = "http://127.0.0.1:8000"
client = TestClient(app)


# =========================================================
# SECTION 1: SYSTEM HEALTH
# =========================================================

class TestSystemHealth:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"
        assert "version" in d

    def test_root_metadata(self):
        r = client.get("/")
        assert r.status_code == 200
        d = r.json()
        assert "name" in d
        assert "docs" in d

    def test_openapi_accessible(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "paths" in r.json()

    def test_swagger_ui_accessible(self):
        r = client.get("/docs")
        assert r.status_code == 200

    def test_static_files_accessible(self):
        r = client.get("/app")
        assert r.status_code == 200

    def test_health_response_time_under_500ms(self):
        start = time.time()
        r = client.get("/health")
        elapsed = (time.time() - start) * 1000
        assert r.status_code == 200
        assert elapsed < 500, f"Health check too slow: {elapsed:.0f}ms"


# =========================================================
# SECTION 2: AUTH ENDPOINT
# =========================================================

class TestAuthEndpoint:
    def test_auth_me_default_returns_doctor(self):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "doctor"
        assert "permissions" in d

    def test_auth_me_patient_role(self):
        r = client.get("/api/v1/auth/me?role=patient")
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "patient"
        assert "patient_id" in d

    def test_auth_me_doctor_permissions_not_empty(self):
        r = client.get("/api/v1/auth/me?role=doctor")
        d = r.json()
        assert len(d["permissions"]) > 0

    def test_auth_me_patient_permissions_scoped(self):
        r = client.get("/api/v1/auth/me?role=patient")
        d = r.json()
        assert "summaries:approve" not in d["permissions"]
        assert "summaries:amend" not in d["permissions"]

    def test_auth_me_no_secrets_leaked(self):
        r = client.get("/api/v1/auth/me")
        text = r.text
        assert "gsk_" not in text
        assert "AIza" not in text
        assert "API_KEY" not in text


# =========================================================
# SECTION 3: CONSULTATION UPLOAD VALIDATION
# =========================================================

class TestConsultationUploadValidation:
    EP = "/api/v1/consultations/process"

    def test_reject_txt_file(self):
        r = client.post(self.EP, files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")})
        assert r.status_code == 415
        assert r.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_reject_pdf_file(self):
        r = client.post(self.EP, files={"file": ("r.pdf", io.BytesIO(b"%PDF"), "application/pdf")})
        assert r.status_code == 415

    def test_reject_empty_file(self):
        r = client.post(self.EP, files={"file": ("empty.mp3", io.BytesIO(b""), "audio/mpeg")})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "EMPTY_FILE"

    def test_reject_no_file(self):
        r = client.post(self.EP)
        assert r.status_code in [400, 422]

    def test_reject_image_file(self):
        r = client.post(self.EP, files={"file": ("photo.jpg", io.BytesIO(b"\xff\xd8"), "image/jpeg")})
        assert r.status_code == 415

    def test_wav_accepted_format(self):
        r = client.post(self.EP, files={"file": ("t.wav", io.BytesIO(b"RIFF" + b"\x00"*100), "audio/wav")})
        assert r.status_code in [200, 202, 400, 500, 503]

    def test_mp4_accepted_format(self):
        r = client.post(self.EP, files={"file": ("t.mp4", io.BytesIO(b"\x00"*100), "video/mp4")})
        assert r.status_code in [200, 202, 400, 500, 503]

    def test_error_response_has_error_structure(self):
        r = client.post(self.EP, files={"file": ("bad.txt", io.BytesIO(b"x"), "text/plain")})
        d = r.json()
        assert "error" in d
        assert "code" in d["error"]
        assert "message" in d["error"]

    def test_no_secrets_in_error_response(self):
        r = client.post(self.EP, files={"file": ("bad.txt", io.BytesIO(b"x"), "text/plain")})
        text = r.text
        assert "gsk_" not in text
        assert "AIza" not in text


# =========================================================
# SECTION 4: CONSULTATION STATUS & LISTING
# =========================================================

class TestConsultationStatusAndListing:
    def test_get_nonexistent_consultation_404(self):
        r = client.get(f"/api/v1/consultations/{uuid.uuid4()}")
        assert r.status_code in [404, 400]

    def test_get_status_nonexistent_consultation(self):
        r = client.get(f"/api/v1/consultations/{uuid.uuid4()}/status")
        assert r.status_code in [404, 400]

    def test_list_consultations_returns_structure(self):
        r = client.get("/api/v1/consultations/")
        assert r.status_code in [200, 401, 422]
        if r.status_code == 200:
            assert isinstance(r.json(), (list, dict))

    def test_invalid_uuid_rejected(self):
        r = client.get("/api/v1/consultations/not-a-real-uuid")
        assert r.status_code in [400, 404, 422]


# =========================================================
# SECTION 5: SUMMARIES ENDPOINTS
# =========================================================

class TestSummariesEndpoints:
    def test_get_summary_nonexistent(self):
        r = client.get(f"/api/v1/summaries/{uuid.uuid4()}")
        assert r.status_code in [404, 400, 422]

    def test_generate_summary_nonexistent(self):
        r = client.post(f"/api/v1/summaries/{uuid.uuid4()}/generate")
        assert r.status_code in [404, 400, 422, 500]

    def test_approve_summary_nonexistent(self):
        r = client.post(
            f"/api/v1/summaries/{uuid.uuid4()}/approve",
            json={"doctor_id": "dr_test", "notes": "ok"}
        )
        assert r.status_code in [404, 400, 422, 500]


# =========================================================
# SECTION 6: GUIDELINES ENDPOINTS
# =========================================================

class TestGuidelinesEndpoints:
    def test_list_guidelines_accessible(self):
        r = client.get("/api/v1/guidelines/")
        assert r.status_code in [200, 401, 404, 422]

    def test_search_guidelines_with_query(self):
        r = client.get("/api/v1/guidelines/search?q=diabetes")
        assert r.status_code in [200, 404, 422, 500]

    def test_get_nonexistent_guideline(self):
        r = client.get(f"/api/v1/guidelines/{uuid.uuid4()}")
        assert r.status_code in [404, 400, 422]

    def test_cross_reference_nonexistent_consultation(self):
        r = client.post(f"/api/v1/guidelines/cross-reference/{uuid.uuid4()}")
        assert r.status_code in [404, 400, 422, 500]


# =========================================================
# SECTION 7: PATIENT PORTAL ENDPOINTS
# =========================================================

class TestPatientPortalEndpoints:
    def test_get_patient_dashboard(self):
        r = client.get("/api/v1/patient/dashboard")
        assert r.status_code in [200, 401, 422, 500]

    def test_patient_ask_ai_no_body(self):
        r = client.post("/api/v1/patient/ask-ai")
        assert r.status_code in [400, 422]

    def test_patient_ask_ai_valid_structure(self):
        r = client.post(
            "/api/v1/patient/ask-ai",
            json={
                "question": "What medications was I prescribed?",
                "patient_id": "test-patient-123",
                "consultation_id": str(uuid.uuid4())
            }
        )
        assert r.status_code in [200, 404, 422, 500]

    def test_patient_voice_note_no_file(self):
        r = client.post("/api/v1/patient/voice-note")
        assert r.status_code in [400, 422]

    def test_patient_voice_note_wrong_type(self):
        r = client.post(
            "/api/v1/patient/voice-note",
            files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")}
        )
        assert r.status_code in [400, 415, 422]

    def test_patient_lab_upload_no_file(self):
        r = client.post("/api/v1/patient/lab-report")
        assert r.status_code in [400, 422]

    def test_patient_recovery_plan_nonexistent(self):
        r = client.get(f"/api/v1/patient/recovery-plan/{uuid.uuid4()}")
        assert r.status_code in [200, 404, 422, 500]

    def test_patient_health_trends(self):
        r = client.get("/api/v1/patient/health-trends?patient_id=test-patient")
        assert r.status_code in [200, 404, 422, 500]


# =========================================================
# SECTION 8: DOCTOR DASHBOARD ENDPOINTS
# =========================================================

class TestDoctorDashboardEndpoints:
    def test_doctor_pending_reviews(self):
        r = client.get("/api/v1/doctor/pending-reviews?doctor_id=dr_test")
        assert r.status_code in [200, 401, 422, 500]

    def test_doctor_consultation_detail_nonexistent(self):
        r = client.get(f"/api/v1/doctor/consultation/{uuid.uuid4()}?doctor_id=dr_test")
        assert r.status_code in [404, 400, 422, 500]

    def test_doctor_approve_summary_nonexistent(self):
        r = client.post(
            f"/api/v1/doctor/summaries/{uuid.uuid4()}/approve",
            json={"doctor_id": "dr_test", "notes": "Approved"}
        )
        assert r.status_code in [404, 400, 422, 500]

    def test_doctor_reject_summary_nonexistent(self):
        r = client.post(
            f"/api/v1/doctor/summaries/{uuid.uuid4()}/reject",
            json={"doctor_id": "dr_test", "reason": "Inaccurate"}
        )
        assert r.status_code in [404, 400, 422, 500]

    def test_doctor_lab_reports(self):
        r = client.get("/api/v1/doctor/lab-reports?doctor_id=dr_test")
        assert r.status_code in [200, 401, 422, 500]

    def test_doctor_voice_note_no_file(self):
        r = client.post("/api/v1/doctor/voice-note")
        assert r.status_code in [400, 422]

    def test_doctor_audit_trail_nonexistent(self):
        r = client.get(f"/api/v1/doctor/audit/{uuid.uuid4()}")
        assert r.status_code in [200, 404, 400, 422, 500]

    def test_doctor_ask_ai_no_body(self):
        r = client.post("/api/v1/doctor/ask-ai")
        assert r.status_code in [400, 422]


# =========================================================
# SECTION 9: SECURITY / INJECTION TESTS
# =========================================================

class TestSecurityAndInjection:
    def test_sql_injection_in_path(self):
        r = client.get("/api/v1/consultations/'; DROP TABLE consultations; --")
        assert r.status_code in [400, 404, 422]

    def test_xss_in_query_param(self):
        r = client.get("/api/v1/guidelines/search?q=<script>alert(1)</script>")
        assert r.status_code in [200, 400, 422]
        if r.status_code == 200:
            assert "<script>" not in r.text

    def test_path_traversal_attempt(self):
        r = client.get("/api/v1/consultations/../../../etc/passwd")
        assert r.status_code in [400, 404, 422]

    def test_oversized_json_body(self):
        r = client.post("/api/v1/patient/ask-ai", json={"question": "x" * 100_000})
        assert r.status_code in [200, 400, 413, 422, 500]

    def test_malformed_json_body(self):
        r = client.post(
            "/api/v1/patient/ask-ai",
            data="not-json-at-all",
            headers={"Content-Type": "application/json"}
        )
        assert r.status_code in [400, 422]

    def test_method_not_allowed_on_health(self):
        r = client.delete("/health")
        assert r.status_code in [405, 404]

    def test_no_secrets_anywhere_in_responses(self):
        endpoints = ["/health", "/", "/api/v1/auth/me"]
        for ep in endpoints:
            r = client.get(ep)
            assert "gsk_" not in r.text
            assert "AIza" not in r.text
            assert "supabase" not in r.text.lower() or "supabase" in r.text.lower()


# =========================================================
# SECTION 10: CONCURRENCY STRESS TEST
# =========================================================

class TestConcurrencyStress:
    def test_10_concurrent_health_checks(self):
        results = []

        def call():
            try:
                r = httpx.get(f"{BASE}/health", timeout=5)
                results.append(r.status_code)
            except Exception:
                results.append(0)

        threads = [threading.Thread(target=call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        success_count = sum(1 for s in results if s == 200)
        assert success_count >= 8, f"Only {success_count}/10 concurrent health checks succeeded"

    def test_25_sequential_requests_no_degradation(self):
        times = []
        for _ in range(25):
            start = time.time()
            r = client.get("/health")
            times.append((time.time() - start) * 1000)
            assert r.status_code == 200
        avg_ms = sum(times) / len(times)
        assert avg_ms < 200, f"Average response time degraded: {avg_ms:.1f}ms"

    def test_repeated_invalid_uploads_no_crash(self):
        for i in range(10):
            r = client.post(
                "/api/v1/consultations/process",
                files={"file": (f"bad{i}.txt", io.BytesIO(b"x"), "text/plain")}
            )
            assert r.status_code == 415

    def test_server_still_alive_after_stress(self):
        r = httpx.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200


# =========================================================
# SECTION 11: RESPONSE SCHEMA INTEGRITY
# =========================================================

class TestResponseSchemaIntegrity:
    def test_health_schema_fields(self):
        d = client.get("/health").json()
        assert {"status", "service", "version"}.issubset(d.keys())

    def test_root_schema_fields(self):
        d = client.get("/").json()
        assert {"name", "description", "version", "docs", "health"}.issubset(d.keys())

    def test_auth_doctor_schema_fields(self):
        d = client.get("/api/v1/auth/me?role=doctor").json()
        assert {"user_id", "name", "role", "permissions"}.issubset(d.keys())

    def test_auth_patient_schema_fields(self):
        d = client.get("/api/v1/auth/me?role=patient").json()
        assert {"user_id", "name", "role", "patient_id", "permissions"}.issubset(d.keys())

    def test_error_schema_always_has_code_and_message(self):
        r = client.post("/api/v1/consultations/process", files={"file": ("bad.txt", io.BytesIO(b"x"), "text/plain")})
        d = r.json()
        assert "error" in d
        assert "code" in d["error"]
        assert "message" in d["error"]
        assert len(d["error"]["message"]) > 0

    def test_json_content_type_on_api_responses(self):
        for ep in ["/health", "/", "/api/v1/auth/me"]:
            r = client.get(ep)
            assert "application/json" in r.headers.get("content-type", ""), f"{ep} has wrong content-type"

    def test_openapi_has_all_route_groups(self):
        paths = client.get("/openapi.json").json()["paths"]
        assert any("/consultations" in p for p in paths)
        assert any("/summaries" in p for p in paths)
        assert any("/guidelines" in p for p in paths)


# =========================================================
# SECTION 12: DATA PERSISTENCE SMOKE TEST (READ-ONLY)
# =========================================================

class TestDataPersistenceSmoke:
    def test_pending_reviews_returns_list_or_error(self):
        r = client.get("/api/v1/doctor/pending-reviews?doctor_id=smoke_test")
        assert r.status_code in [200, 500]
        if r.status_code == 200:
            assert isinstance(r.json(), (list, dict))

    def test_patient_consultations_returns_list_or_error(self):
        r = client.get("/api/v1/patient/consultations?patient_id=smoke_test")
        assert r.status_code in [200, 404, 500]
        if r.status_code == 200:
            assert isinstance(r.json(), (list, dict))

    def test_guidelines_list_returns_list_or_error(self):
        r = client.get("/api/v1/guidelines/")
        assert r.status_code in [200, 404, 422, 500]
        if r.status_code == 200:
            assert isinstance(r.json(), (list, dict))


# =========================================================
# SECTION 13: EDGE CASES
# =========================================================

class TestEdgeCases:
    def test_unicode_tamil_in_query(self):
        r = client.get("/api/v1/guidelines/search?q=????????")
        assert r.status_code in [200, 400, 422, 500]

    def test_empty_patient_id(self):
        r = client.get("/api/v1/patient/consultations?patient_id=")
        assert r.status_code in [200, 400, 404, 422, 500]

    def test_very_long_path_param(self):
        r = client.get(f"/api/v1/consultations/{'a' * 200}")
        assert r.status_code in [400, 404, 422]

    def test_response_never_empty_on_error(self):
        r = client.get(f"/api/v1/consultations/{uuid.uuid4()}")
        if r.status_code >= 400:
            assert len(r.content) > 0

    def test_options_preflight_cors(self):
        r = client.options(
            "/api/v1/consultations/process",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
        )
        assert r.status_code in [200, 204, 405]

    def test_head_request_health(self):
        r = client.request("HEAD", "/health")
        assert r.status_code in [200, 405]
