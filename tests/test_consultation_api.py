"""
Unit and integration validation tests for Consultation API endpoints.
Tests validation, error handling, file type enforcement, and response structuring.
"""

import io
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.consultations import get_consultation_service
from api.schemas.consultation import (
    ConsultationResponse,
    InputMetadata,
    TranscriptTurn,
    MedicalRecord,
    ValidationSummary,
)
from src.medical_schema import MedicationItem

client = TestClient(app)


def test_reject_unsupported_file_extension():
    """Verify that uploading non-audio/video file types returns 415."""
    fake_txt_file = io.BytesIO(b"Hello clinical world, this is a plain text file.")
    response = client.post(
        "/api/v1/consultations/process",
        files={"file": ("clinical_notes.txt", fake_txt_file, "text/plain")}
    )
    assert response.status_code == 415
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "WAV, MP3, MP4" in data["error"]["message"]


def test_reject_empty_file():
    """Verify that uploading an empty 0-byte file returns 400 Bad Request."""
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/v1/consultations/process",
        files={"file": ("empty.mp3", empty_file, "audio/mpeg")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "EMPTY_FILE"
    assert "empty" in data["error"]["message"]


def test_reject_missing_filename():
    """Verify that empty filename triggers validation error."""
    valid_bytes = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt ")
    response = client.post(
        "/api/v1/consultations/process",
        files={"file": ("", valid_bytes, "audio/wav")}
    )
    assert response.status_code in [400, 422]


def test_consultation_process_with_mocked_service():
    """
    Verifies that the route correctly delegates to PipelineService,
    preserves source evidence, formats response schema, and conceals API secrets.
    """
    mock_service = MagicMock()
    mock_response = ConsultationResponse(
        status="completed",
        input=InputMetadata(
            filename="consultation_demo.mp4",
            media_type="video/mp4",
            duration_seconds=28.48
        ),
        transcript=[
            TranscriptTurn(start=0.0, end=9.0, speaker="Patient", text="டாக்டர் காய்ச்சல் இருக்கு"),
            TranscriptTurn(start=9.0, end=18.0, speaker="Doctor", text="பேராசிட்டமால் 650 mg எடுத்துக்கோங்க")
        ],
        medical_record=MedicalRecord(
            medications=[
                MedicationItem(
                    name="Paracetamol",
                    strength="650 mg",
                    frequency="twice daily",
                    specific_schedule=["morning", "night"],
                    timing="after food",
                    duration="5 days",
                    source_speaker="Doctor",
                    source_text="பேராசிட்டமால் 650 mg எடுத்துக்கோங்க",
                    source_start=9.0,
                    source_end=18.0
                )
            ],
            tests=[],
            instructions=["Drink plenty of water"],
            warnings=[],
            symptoms_mentioned=["Fever"],
            uncertain_items=[],
            requires_doctor_review=True
        ),
        validation=ValidationSummary(status="valid", errors=[], warnings=[])
    )
    mock_service.process_consultation.return_value = mock_response

    # Override dependency in FastAPI
    app.dependency_overrides[get_consultation_service] = lambda: mock_service

    try:
        sample_audio = io.BytesIO(b"\x00" * 1024)
        response = client.post(
            "/api/v1/consultations/process?sync=true",
            files={"file": ("consultation_demo.mp4", sample_audio, "video/mp4")}
        )
        assert response.status_code == 200
        data = response.json()

        # Schema & structure assertions
        assert data["status"] == "completed"
        assert data["input"]["filename"] == "consultation_demo.mp4"
        assert len(data["transcript"]) == 2
        assert data["transcript"][1]["speaker"] == "Doctor"

        # Evidence preservation
        meds = data["medical_record"]["medications"]
        assert len(meds) == 1
        assert meds[0]["name"] == "Paracetamol"
        assert meds[0]["source_speaker"] == "Doctor"
        assert meds[0]["source_start"] == 9.0
        assert meds[0]["source_end"] == 18.0

        # Secret protection
        text_resp = response.text
        assert "gsk_" not in text_resp
        assert "AIza" not in text_resp
        assert "API_KEY" not in text_resp

    finally:
        app.dependency_overrides.clear()
