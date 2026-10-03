"""
PostVisit AI - Clinical Guideline Cross-Reference API Endpoints
Provides REST routes for guideline evaluation, provenance retrieval, and physician reviews.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Header, Query, Path, status
from fastapi.responses import JSONResponse

from src.schemas.guideline_schema import (
    GuidelineCrossReferenceResult,
    GuidelineDoctorReviewRequest
)
from src.services.guideline_service import GuidelineService, get_guideline_service
from src.guidelines.source_registry import get_guideline_registry

logger = logging.getLogger("postvisit.routes.guidelines")

router = APIRouter(
    tags=["Clinical Guidelines"]
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
# 1. Get Guideline Cross-Reference Findings
# -------------------------------------------------------------
@router.get(
    "/api/v1/consultations/{consultation_id}/guidelines",
    status_code=status.HTTP_200_OK,
    summary="Get Guideline Cross-Reference Findings",
    description="Retrieves evidence-backed clinical decision-support findings. Filtered by role."
)
async def get_guideline_findings_endpoint(
    consultation_id: str = Path(..., description="UUID of the consultation"),
    auth: Dict[str, str] = Depends(get_caller_identity),
    guideline_service: GuidelineService = Depends(get_guideline_service)
):
    try:
        findings = guideline_service.get_guideline_findings(
            consultation_id=consultation_id,
            caller_role=auth["role"]
        )
        return findings
    except Exception as e:
        logger.error(f"Error fetching guideline findings: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "GUIDELINE_RETRIEVAL_ERROR", "message": str(e)}}
        )


# -------------------------------------------------------------
# 2. Trigger Guideline Cross-Referencing
# -------------------------------------------------------------
@router.post(
    "/api/v1/consultations/{consultation_id}/guidelines/cross-reference",
    status_code=status.HTTP_200_OK,
    summary="Execute Guideline Cross-Referencing",
    description="Cross-references consultation medical record against authoritative Indian guidelines."
)
@router.post(
    "/api/v1/consultations/{consultation_id}/cross-reference",
    status_code=status.HTTP_200_OK,
    summary="Execute Guideline Cross-Referencing (Alias)",
    description="Cross-references consultation medical record against authoritative Indian guidelines.",
    include_in_schema=False
)
async def cross_reference_guidelines_endpoint(
    consultation_id: str = Path(..., description="UUID of the consultation"),
    auth: Dict[str, str] = Depends(get_caller_identity),
    guideline_service: GuidelineService = Depends(get_guideline_service)
):
    if auth["role"] not in ("doctor", "system"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "DOCTOR_ROLE_REQUIRED",
                    "message": "Only authorized physicians or system workers can trigger guideline cross-referencing."
                }
            }
        )

    try:
        res = guideline_service.cross_reference_consultation(
            consultation_id=consultation_id,
            caller_role=auth["role"]
        )
        return res
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "NOT_FOUND", "message": str(ve)}}
        )
    except Exception as e:
        logger.error(f"Error executing guideline cross-referencing: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "EVALUATION_ERROR", "message": str(e)}}
        )


# -------------------------------------------------------------
# 3. Doctor Review of Guideline Finding
# -------------------------------------------------------------
@router.post(
    "/api/v1/consultations/{consultation_id}/guidelines/review",
    status_code=status.HTTP_200_OK,
    summary="Submit Doctor Review for Guideline Finding",
    description="Physician acknowledges, dismisses, or amends a guideline advisory prompt."
)
async def review_guideline_finding_endpoint(
    consultation_id: str = Path(..., description="UUID of the consultation"),
    payload: GuidelineDoctorReviewRequest = ...,
    auth: Dict[str, str] = Depends(get_caller_identity),
    guideline_service: GuidelineService = Depends(get_guideline_service)
):
    if auth["role"] not in ("doctor", "system"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "DOCTOR_ROLE_REQUIRED",
                    "message": "Only authorized physicians can review clinical guideline findings."
                }
            }
        )

    try:
        review = guideline_service.review_finding(
            consultation_id=consultation_id,
            finding_id=payload.finding_id,
            doctor_name=payload.doctor_name,
            decision=payload.decision,
            notes=payload.notes,
            caller_role=auth["role"]
        )
        return review
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_REQUEST", "message": str(ve)}}
        )
    except PermissionError as pe:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": {"code": "FORBIDDEN", "message": str(pe)}}
        )


# -------------------------------------------------------------
# 4. List Verified Guideline Sources
# -------------------------------------------------------------
@router.get(
    "/api/v1/guidelines/sources",
    status_code=status.HTTP_200_OK,
    summary="List Curated Indian Guideline Sources",
    description="Returns metadata, versioning, and provenance checksums for verified clinical guidelines."
)
async def list_guideline_sources_endpoint():
    registry = get_guideline_registry()
    sources = registry.list_guidelines()
    return {"sources": sources, "total": len(sources)}
