"""
PostVisit AI - Stage 2: Supabase Persistence and Retrieval Tests
Verifies database CRUD, storage upload, consultation retrieval by ID,
consultation listing, and failure state tracking.
"""

import io
import uuid
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from api.main import app
from api.routes.consultations import get_consultation_service
from api.repositories.consultation_repository import ConsultationRepository
from api.services.consultation_service import ConsultationService
from api.schemas.consultation import (
    ConsultationResponse,
    InputMetadata,
    TranscriptTurn,
    MedicalRecord,
    ValidationSummary,
)
from src.medical_schema import MedicationItem

client = TestClient(app)


def test_repository_lifecycle():
    """Verify repository creation, update, and retrieval operations."""
    repo = ConsultationRepository()
    test_id = str(uuid.uuid4())

    # 1. Create row
    created = repo.create(test_id, "consultation_sample.mp4", "video/mp4")
    assert created["id"] == test_id
    assert created["status"] == "processing"

    # 2. Update media storage path
    storage_path = f"consultations/{test_id}/original.mp4"
    repo.update_media_path(test_id, storage_path)
    fetched = repo.get_by_id(test_id)
    assert fetched["media_storage_path"] == storage_path

    # 3. Update completed
    transcript = [{"start": 0.0, "end": 5.0, "speaker": "Doctor", "text": "Take paracetamol"}]
    med_rec = {"medications": [{"name": "Paracetamol", "strength": "650 mg"}]}
    val_res = {"valid": True, "errors": [], "warnings": []}

    repo.update_completed(
        consultation_id=test_id,
        duration_seconds=25.5,
        transcript=transcript,
        medical_record=med_rec,
        validation_result=val_res
    )
    completed_row = repo.get_by_id(test_id)
    assert completed_row["status"] == "completed"
    assert completed_row["duration_seconds"] == 25.5
    assert completed_row["transcript"] == transcript
    assert completed_row["medical_record"] == med_rec

    # 4. List all
    items, total = repo.list_all(limit=10, offset=0)
    assert total >= 1
    assert any(item["id"] == test_id for item in items)


def test_repository_failure_state():
    """Verify failure state tracking in repository."""
    repo = ConsultationRepository()
    fail_id = str(uuid.uuid4())

    repo.create(fail_id, "corrupt_file.mp4", "video/mp4")
    repo.update_failed(fail_id, "AUDIO_PROCESSING_FAILED", "Corrupted audio container.")

    row = repo.get_by_id(fail_id)
    assert row["status"] == "failed"
    assert row["error_code"] == "AUDIO_PROCESSING_FAILED"
    assert "Corrupted" in row["error_message"]


def test_api_process_and_retrieve_flow():
    """
    Integration test:
    POST /api/v1/consultations/process
    -> Verify consultation_id returned
    -> GET /api/v1/consultations/{consultation_id}
    -> Verify retrieved record matches original output
    """
    mock_pipeline_service = MagicMock()
    mock_pipeline_service.process.return_value = ConsultationResponse(
        status="completed",
        input=InputMetadata(
            filename="consultation_flow.mp4",
            media_type="video/mp4",
            duration_seconds=28.48
        ),
        transcript=[
            TranscriptTurn(start=0.0, end=9.0, speaker="Patient", text="காய்ச்சல் இருக்கு"),
            TranscriptTurn(start=9.0, end=18.0, speaker="Doctor", text="பேராசிட்டமால் 650 mg")
        ],
        medical_record=MedicalRecord(
            medications=[
                MedicationItem(
                    name="Paracetamol",
                    strength="650 mg",
                    frequency="twice daily",
                    source_speaker="Doctor"
                )
            ],
            symptoms_mentioned=["Fever"],
            requires_doctor_review=True
        ),
        validation=ValidationSummary(status="valid", errors=[], warnings=[])
    )

    repo = ConsultationRepository()
    service = ConsultationService(repository=repo, pipeline_service=mock_pipeline_service)

    app.dependency_overrides[get_consultation_service] = lambda: service

    try:
        sample_audio = io.BytesIO(b"\x00" * 2048)
        post_resp = client.post(
            "/api/v1/consultations/process?sync=true",
            files={"file": ("consultation_flow.mp4", sample_audio, "video/mp4")}
        )
        assert post_resp.status_code == 200
        post_data = post_resp.json()

        assert "consultation_id" in post_data
        cid = post_data["consultation_id"]
        assert cid is not None
        assert post_data["status"] == "completed"
        assert post_data["media_storage_path"] is not None

        # Retrieve by ID
        get_resp = client.get(f"/api/v1/consultations/{cid}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()

        assert get_data["consultation_id"] == cid
        assert get_data["status"] == "completed"
        assert get_data["input"]["filename"] == "consultation_flow.mp4"
        assert len(get_data["transcript"]) == 2
        assert get_data["medical_record"]["medications"][0]["name"] == "Paracetamol"
        assert get_data["medical_record"]["medications"][0]["source_speaker"] == "Doctor"

        # List consultations
        list_resp = client.get("/api/v1/consultations")
        assert list_resp.status_code == 200
        list_data = list_resp.json()

        assert list_data["total"] >= 1
        assert any(item["consultation_id"] == cid for item in list_data["items"])

    finally:
        app.dependency_overrides.clear()


def test_get_nonexistent_consultation():
    """Verify 404 response when querying invalid consultation UUID."""
    random_uuid = str(uuid.uuid4())
    resp = client.get(f"/api/v1/consultations/{random_uuid}")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "CONSULTATION_NOT_FOUND"
