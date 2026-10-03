"""
PostVisit AI - Patient Summary API Endpoints
Provides REST routes for generating, reviewing, retrieving, and auditing patient-friendly clinical summaries.
Enforces role-based access control, physician review gates, and deterministic validation.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Header, Query, Path, status
from fastapi.responses import JSONResponse

from src.schemas.patient_summary_schema import (
    PatientSummaryCreateRequest,
    PatientSummaryReviewRequest,
    PatientSummaryRecord,
    PatientSummaryAuditItem
)
from src.services.summary_service import SummaryService, get_summary_service

logger = logging.getLogger("postvisit.routes.summaries")

router = APIRouter(
    tags=["Patient Summaries"]
)


def get_caller_identity(
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    role: Optional[str] = Query(default=None, description="Role override for testing"),
    user_id: Optional[str] = Query(default=None, description="User ID override for testing")
) -> Dict[str, str]:
    """Resolves caller role and identity from headers or query parameters."""
    resolved_role = (role or x_user_role or "patient").lower()
    resolved_id = user_id or x_user_id or "anonymous"
    return {"role": resolved_role, "caller_id": resolved_id}


# -------------------------------------------------------------
# 1. Trigger / Generate Patient Summary
# -------------------------------------------------------------
@router.post(
    "/api/v1/consultations/{consultation_id}/summaries",
    status_code=status.HTTP_200_OK,
    summary="Generate Patient Summary",
    description=(
        "Triggers generation of a patient-friendly summary from a doctor-approved medical record. "
        "Enforces clinical approval gating, idempotency, and deterministic guardrail validation."
    )
)
async def generate_patient_summary_endpoint(
    consultation_id: str = Path(..., description="UUID of the consultation"),
    payload: Optional[PatientSummaryCreateRequest] = None,
    auth: Dict[str, str] = Depends(get_caller_identity),
    summary_service: SummaryService = Depends(get_summary_service)
):
    target_lang = payload.target_language if payload else "en"
    idempotency_key = payload.idempotency_key if payload else None

    try:
        summary = summary_service.generate_summary(
            consultation_id=consultation_id,
            target_language=target_lang,
            idempotency_key=idempotency_key,
            caller_role=auth["role"],
            caller_id=auth["caller_id"]
        )
        return summary
    except ValueError as ve:
        logger.warning(f"Summary generation rejected: {ve}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "RECORD_NOT_APPROVED", "message": str(ve)}}
        )
    except PermissionError as pe:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": {"code": "FORBIDDEN", "message": str(pe)}}
        )
    except Exception as e:
        logger.error(f"Error during summary generation: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "GENERATION_ERROR", "message": str(e)}}
        )


# -------------------------------------------------------------
# 2. List Summaries for Consultation
# -------------------------------------------------------------
@router.get(
    "/api/v1/consultations/{consultation_id}/summaries",
    status_code=status.HTTP_200_OK,
    summary="List Summaries for Consultation",
    description="Retrieves patient summaries. Patients only see approved summaries; doctors see all."
)
async def list_consultation_summaries_endpoint(
    consultation_id: str = Path(..., description="UUID of the consultation"),
    language: Optional[str] = Query(default=None, description="Filter by language code ('en', 'ta')"),
    auth: Dict[str, str] = Depends(get_caller_identity),
    summary_service: SummaryService = Depends(get_summary_service)
):
    summaries = summary_service.list_summaries_for_consultation(
        consultation_id=consultation_id,
        caller_role=auth["role"],
        caller_id=auth["caller_id"],
        language=language
    )
    return {"consultation_id": consultation_id, "summaries": summaries, "total": len(summaries)}


# -------------------------------------------------------------
# 3. Get Single Summary
# -------------------------------------------------------------
@router.get(
    "/api/v1/summaries/{summary_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Single Patient Summary",
    description="Retrieves an authorized summary. Blocks patient access if not approved by physician."
)
async def get_summary_endpoint(
    summary_id: str = Path(..., description="UUID of the patient summary"),
    auth: Dict[str, str] = Depends(get_caller_identity),
    summary_service: SummaryService = Depends(get_summary_service)
):
    try:
        summary = summary_service.get_summary(
            summary_id=summary_id,
            caller_role=auth["role"],
            caller_id=auth["caller_id"]
        )
        return summary
    except PermissionError as pe:
        logger.warning(f"Access denied to summary [{summary_id}]: {pe}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": {"code": "ACCESS_DENIED", "message": str(pe)}}
        )
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "NOT_FOUND", "message": str(ve)}}
        )


# -------------------------------------------------------------
# 4. Doctor Review Sign-Off
# -------------------------------------------------------------
@router.post(
    "/api/v1/summaries/{summary_id}/review",
    status_code=status.HTTP_200_OK,
    summary="Submit Physician Review & Sign-Off for Summary",
    description="Authorized physician approves, rejects, or amends the patient summary."
)
async def review_summary_endpoint(
    summary_id: str = Path(..., description="UUID of the patient summary"),
    payload: PatientSummaryReviewRequest = ...,
    auth: Dict[str, str] = Depends(get_caller_identity),
    summary_service: SummaryService = Depends(get_summary_service)
):
    # Enforce doctor role
    if auth["role"] not in ("doctor", "system"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "DOCTOR_ROLE_REQUIRED",
                    "message": "Only authorized physicians can review or approve patient summaries."
                }
            }
        )

    try:
        updated = summary_service.review_summary(
            summary_id=summary_id,
            doctor_name=payload.doctor_name,
            decision=payload.decision,
            notes=payload.notes,
            corrected_summary=payload.corrected_summary.model_dump() if payload.corrected_summary else None,
            caller_role=auth["role"]
        )
        return updated
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_REVIEW_REQUEST", "message": str(ve)}}
        )
    except PermissionError as pe:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": {"code": "FORBIDDEN", "message": str(pe)}}
        )
    except Exception as e:
        logger.error(f"Error reviewing summary: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "REVIEW_ERROR", "message": str(e)}}
        )


@router.post(
    "/api/v1/consultations/{consultation_id}/summaries/review",
    status_code=status.HTTP_200_OK,
    summary="Submit Physician Review & Sign-Off by Consultation ID",
    description="Authorized physician approves, rejects, or amends the patient summary for a consultation."
)
async def review_consultation_summary_endpoint(
    consultation_id: str = Path(..., description="UUID of the consultation"),
    payload: PatientSummaryReviewRequest = ...,
    auth: Dict[str, str] = Depends(get_caller_identity),
    summary_service: SummaryService = Depends(get_summary_service)
):
    if auth["role"] not in ("doctor", "system"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "DOCTOR_ROLE_REQUIRED",
                    "message": "Only authorized physicians can review or approve patient summaries."
                }
            }
        )

    summaries = summary_service.summary_repo.list_summaries_for_consultation(consultation_id)
    if not summaries:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "NOT_FOUND", "message": f"No summary found for consultation '{consultation_id}'."}}
        )

    summary_id = summaries[-1]["id"]
    return await review_summary_endpoint(
        summary_id=summary_id,
        payload=payload,
        auth=auth,
        summary_service=summary_service
    )


# -------------------------------------------------------------
# 5. Get Audit History
# -------------------------------------------------------------
@router.get(
    "/api/v1/summaries/{summary_id}/history",
    status_code=status.HTTP_200_OK,
    summary="Get Summary Audit and Version History",
    description="Retrieves chronological audit log entries for a summary. Restricted to doctors and administrators."
)
async def get_summary_history_endpoint(
    summary_id: str = Path(..., description="UUID of the patient summary"),
    auth: Dict[str, str] = Depends(get_caller_identity),
    summary_service: SummaryService = Depends(get_summary_service)
):
    if auth["role"] not in ("doctor", "system"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "ACCESS_DENIED",
                    "message": "Access to audit history is restricted to physicians and administrators."
                }
            }
        )

    try:
        history = summary_service.get_summary_history(
            summary_id=summary_id,
            caller_role=auth["role"]
        )
        return {"summary_id": summary_id, "history": history, "total": len(history)}
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "NOT_FOUND", "message": str(ve)}}
        )
