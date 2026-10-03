"""
PostVisit AI - Pipeline Orchestration Service Layer
Acts as a clean, modular service boundary connecting the FastAPI HTTP layer
to the core PostVisit clinical audio, speech recognition, and medical extraction pipeline.
"""

import os
import sys
import uuid
import mimetypes
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Lazy imports for heavy ML components (IndicConformer / torch / NeMo)
# loaded on-demand in warmup() and process()
from api.schemas.consultation import (
    ConsultationResponse,
    InputMetadata,
    TranscriptTurn,
    MedicalRecord,
    ValidationSummary,
)
from src.medical_schema import MedicationItem, TestItem, FollowUpItem

# Setup structured logger
logger = logging.getLogger("postvisit.pipeline_service")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class PipelineService:
    """
    Orchestration service for processing consultation audio/video media
    using the core PostVisit clinical AI pipeline.
    """

    def __init__(self):
        self._warmed_up = False

    def warmup(self) -> None:
        """
        Pre-loads the IndicConformer ASR model in memory if not already cached.
        Ensures rapid inference on initial user requests without blocking /health.
        """
        if not self._warmed_up:
            logger.info("Initializing and caching IndicConformer ASR model...")
            from src.asr import get_model
            get_model()
            self._warmed_up = True
            logger.info("ASR model cached successfully.")

    def process(
        self,
        file_path: str,
        original_filename: str,
        content_type: Optional[str] = None
    ) -> ConsultationResponse:
        """
        Processes an uploaded consultation media file through the end-to-end pipeline:
        Audio Normalization -> Diarization -> IndicConformer ASR -> LLM Extraction -> Validation.

        Returns a strictly validated ConsultationResponse preserving evidence attribution.
        """
        from src.postvisit_pipeline import run_pipeline

        consultation_id = f"PV-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"Consultation processing started [consultation_id={consultation_id}]")
        logger.info(f"File received: {original_filename} [consultation_id={consultation_id}]")

        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Media file not found at path: {file_path}")

        # Resolve MIME media type
        media_type = content_type
        if not media_type or media_type in ["application/octet-stream", ""]:
            guessed, _ = mimetypes.guess_type(original_filename)
            media_type = guessed or "application/octet-stream"

        # Step-by-step pipeline execution
        logger.info(f"Executing PostVisit clinical pipeline [consultation_id={consultation_id}]...")
        pipeline_output = run_pipeline(
            media_path=str(path_obj),
            language="ta",
            strategy="ctc",
            debug=False
        )
        logger.info(f"Pipeline execution completed successfully [consultation_id={consultation_id}]")

        # Map turns into TranscriptTurn schema
        raw_turns = pipeline_output.get("speaker_turns", [])
        transcript_turns: List[TranscriptTurn] = []
        for t in raw_turns:
            start_val = float(t.get("start_sec", t.get("start", 0.0)))
            end_val = float(t.get("end_sec", t.get("end", 0.0)))
            spk_val = str(t.get("speaker", "Unknown"))
            text_val = str(t.get("text", "")).strip()
            transcript_turns.append(
                TranscriptTurn(
                    start=round(start_val, 2),
                    end=round(end_val, 2),
                    speaker=spk_val,
                    text=text_val
                )
            )

        # Map medical information into MedicalRecord schema
        med_info = pipeline_output.get("medical_information", {})
        medications_raw = med_info.get("medications", [])
        medication_items: List[MedicationItem] = []
        for m in medications_raw:
            if isinstance(m, dict):
                medication_items.append(MedicationItem(**m))
            elif isinstance(m, MedicationItem):
                medication_items.append(m)

        tests_raw = med_info.get("tests", [])
        test_items: List[TestItem] = []
        for t in tests_raw:
            if isinstance(t, dict):
                test_items.append(TestItem(**t))
            elif isinstance(t, TestItem):
                test_items.append(t)

        follow_up_raw = med_info.get("follow_up", {})
        if isinstance(follow_up_raw, dict):
            follow_up_item = FollowUpItem(**follow_up_raw)
        elif isinstance(follow_up_raw, FollowUpItem):
            follow_up_item = follow_up_raw
        else:
            follow_up_item = FollowUpItem()

        medical_record = MedicalRecord(
            medications=medication_items,
            tests=test_items,
            instructions=med_info.get("instructions", []),
            follow_up=follow_up_item,
            warnings=med_info.get("warnings", []),
            symptoms_mentioned=med_info.get("symptoms_mentioned", []),
            uncertain_items=med_info.get("uncertain_items", []),
            requires_doctor_review=med_info.get("requires_doctor_review", True)
        )

        # Map validation summary
        raw_val = pipeline_output.get("validation", {})
        is_valid = raw_val.get("valid", True)
        validation_status = "valid" if is_valid else "invalid"
        val_errors = raw_val.get("errors", [])
        val_warnings = raw_val.get("warnings", [])

        validation_summary = ValidationSummary(
            status=validation_status,
            errors=val_errors,
            warnings=val_warnings
        )

        # Formulate complete response
        duration_sec = float(pipeline_output.get("audio_duration_sec", 0.0))
        input_meta = InputMetadata(
            filename=original_filename,
            media_type=media_type,
            duration_seconds=round(duration_sec, 2)
        )

        logger.info(f"Consultation processing completed [consultation_id={consultation_id}]")

        return ConsultationResponse(
            status="completed",
            input=input_meta,
            transcript=transcript_turns,
            medical_record=medical_record,
            validation=validation_summary
        )


_pipeline_service = PipelineService()


def get_pipeline_service() -> PipelineService:
    """Returns singleton instance of PipelineService."""
    return _pipeline_service
