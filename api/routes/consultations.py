"""
PostVisit AI - Consultation Processing & Persistence Endpoints
Exposes REST endpoints for asynchronous background processing, consultation retrieval,
workflow observability history, and physician review sign-offs.
"""

import os
import shutil
import logging
import tempfile
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, UploadFile, File, Depends, Query, status
from fastapi.responses import JSONResponse

from api.config import Settings, get_settings
from api.schemas.consultation import (
    ConsultationResponse,
    ConsultationDetailResponse,
    ConsultationListResponse,
    ErrorResponse
)
from api.schemas.workflow import (
    WorkflowEnqueueResponse,
    ConsultationWorkflowStatusResponse,
    WorkflowHistoryResponse,
    DoctorReviewRequest,
    DoctorReviewResponse
)
from api.services.consultation_service import (
    ConsultationService,
    get_consultation_service
)

logger = logging.getLogger("postvisit.routes.consultations")

router = APIRouter(
    prefix="/api/v1/consultations",
    tags=["Consultations"]
)


@router.post(
    "/process",
    response_model=Union[WorkflowEnqueueResponse, ConsultationResponse],
    status_code=status.HTTP_200_OK,
    summary="Process Consultation Media (Async Background Execution)",
    description=(
        "Upload an audio or video consultation file (WAV, MP3, MP4, M4A, FLAC, OGG). "
        "By default (Stage 3), creates a consultation and workflow job in Supabase, "
        "dispatches the clinical pipeline to the background worker, and returns immediately "
        "with consultation_id and status='queued'. "
        "Set ?sync=true to run synchronously (Stage 2 backwards compatibility)."
    ),
    responses={
        200: {
            "description": "Consultation successfully queued or completed synchronously."
        },
        400: {
            "model": ErrorResponse,
            "description": "Bad Request (e.g. empty file or missing filename)."
        },
        413: {
            "model": ErrorResponse,
            "description": "Payload Too Large (file exceeds MAX_UPLOAD_SIZE_MB)."
        },
        415: {
            "model": ErrorResponse,
            "description": "Unsupported Media Type (unsupported container extension)."
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal Server Error or Processing Failure."
        }
    }
)
async def process_consultation(
    file: UploadFile = File(
        ...,
        description="Audio or video file (supported: WAV, MP3, MP4, M4A, FLAC, OGG)"
    ),
    sync: bool = Query(
        default=False,
        description="Set True to block synchronously until processing completes (Stage 2 legacy)"
    ),
    settings: Settings = Depends(get_settings),
    consultation_service: ConsultationService = Depends(get_consultation_service)
):
    original_filename = file.filename or ""
    if not original_filename.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "INVALID_FILENAME",
                    "message": "A valid filename must be provided."
                }
            }
        )

    # Validate file extension
    file_ext = Path(original_filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={
                "error": {
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": "Unsupported file type. Supported formats: WAV, MP3, MP4, M4A, FLAC, OGG."
                }
            }
        )

    # Create temporary sandbox directory for file upload
    temp_dir = tempfile.mkdtemp(prefix="postvisit_upload_")
    temp_file_path = Path(temp_dir) / f"upload{file_ext}"

    try:
        total_bytes = 0
        max_bytes = settings.max_upload_size_bytes

        with open(temp_file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": {
                                "code": "FILE_TOO_LARGE",
                                "message": f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
                            }
                        }
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "EMPTY_FILE",
                        "message": "Uploaded file is empty (0 bytes)."
                    }
                }
            )

        media_type = file.content_type or "application/octet-stream"

        # Check synchronous execution flag
        if sync:
            logger.info(f"Executing synchronous processing for [{original_filename}]")
            result = consultation_service.process_consultation(
                local_temp_file_path=str(temp_file_path),
                original_filename=original_filename,
                media_type=media_type
            )
            return result

        # Stage 3: Asynchronous background processing (returns immediately)
        enqueue_res = consultation_service.start_background_workflow(
            local_temp_file_path=str(temp_file_path),
            original_filename=original_filename,
            media_type=media_type
        )
        return enqueue_res

    except (ValueError, RuntimeError) as e:
        err_msg = str(e)
        logger.error(f"Audio/pipeline processing failure: {err_msg}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "AUDIO_PROCESSING_FAILED",
                    "message": "Unable to process the uploaded audio."
                }
            }
        )
    except Exception as e:
        logger.error(f"Unexpected internal server error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the consultation."
                }
            }
        )
    finally:
        # Note: If sync=True, clean up immediately. If async, worker cleans up after processing,
        # or cleanup occurs once background job finishes reading.
        # For sync mode we clean up now:
        if sync:
            try:
                if temp_file_path.exists():
                    temp_file_path.unlink(missing_ok=True)
                if Path(temp_dir).exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as cleanup_err:
                logger.warning(f"Error cleaning up temporary directory: {cleanup_err}")


@router.get(
    "/{consultation_id}",
    response_model=ConsultationWorkflowStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Consultation Status and Clinical Record",
    description="Retrieves persisted consultation details, active workflow step, doctor review flag, and medical data.",
    responses={
        200: {
            "model": ConsultationWorkflowStatusResponse,
            "description": "Consultation details successfully retrieved."
        },
        404: {
            "model": ErrorResponse,
            "description": "Consultation record not found."
        }
    }
)
async def get_consultation(
    consultation_id: str,
    consultation_service: ConsultationService = Depends(get_consultation_service)
):
    record = consultation_service.get_consultation(consultation_id)
    if not record:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "CONSULTATION_NOT_FOUND",
                    "message": f"Consultation with ID '{consultation_id}' was not found."
                }
            }
        )
    return record


@router.get(
    "/{consultation_id}/workflow",
    response_model=WorkflowHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Workflow Observability History",
    description="Returns complete workflow step execution audit logs, agent runs, retry counts, errors, and timestamps.",
    responses={
        200: {
            "model": WorkflowHistoryResponse,
            "description": "Workflow execution history successfully retrieved."
        },
        404: {
            "model": ErrorResponse,
            "description": "Workflow history for the specified consultation was not found."
        }
    }
)
async def get_workflow_history(
    consultation_id: str,
    consultation_service: ConsultationService = Depends(get_consultation_service)
):
    history = consultation_service.get_workflow_history(consultation_id)
    if not history:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "WORKFLOW_NOT_FOUND",
                    "message": f"Workflow history for consultation '{consultation_id}' was not found."
                }
            }
        )
    return history


@router.get(
    "/{consultation_id}/progress",
    status_code=status.HTTP_200_OK,
    summary="Get Real-Time Workflow Progress for UI",
    description="Returns authoritative workflow step states, elapsed time, and genuine completion status for processing screen."
)
async def get_consultation_progress_endpoint(
    consultation_id: str,
    consultation_service: ConsultationService = Depends(get_consultation_service)
):
    progress = consultation_service.get_consultation_progress(consultation_id)
    if not progress:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "CONSULTATION_NOT_FOUND",
                    "message": f"Consultation '{consultation_id}' was not found."
                }
            }
        )
    return progress


@router.post(
    "/{consultation_id}/review",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Physician Review & Sign-Off",
    description="Physician approves or amends the clinical record, transitioning state from PENDING_DOCTOR_REVIEW to COMPLETED.",
    responses={
        200: {
            "model": DoctorReviewResponse,
            "description": "Physician sign-off recorded successfully."
        },
        400: {
            "model": ErrorResponse,
            "description": "Failed to submit review."
        },
        404: {
            "model": ErrorResponse,
            "description": "Consultation record not found."
        }
    }
)
async def submit_doctor_review(
    consultation_id: str,
    payload: DoctorReviewRequest,
    consultation_service: ConsultationService = Depends(get_consultation_service)
):
    try:
        result = consultation_service.review_consultation(
            consultation_id=consultation_id,
            doctor_name=payload.doctor_name,
            decision=payload.decision,
            notes=payload.notes,
            corrected_medical_record=payload.corrected_medical_record
        )
        return result
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "REVIEW_SUBMISSION_FAILED", "message": str(ve)}}
        )


@router.get(
    "",
    response_model=ConsultationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Consultations",
    description="Returns a paginated list of consultations ordered from most recent to oldest.",
    responses={
        200: {
            "model": ConsultationListResponse,
            "description": "List of consultations."
        }
    }
)
async def list_consultations(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum items to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    consultation_service: ConsultationService = Depends(get_consultation_service)
):
    return consultation_service.list_consultations(limit=limit, offset=offset)
