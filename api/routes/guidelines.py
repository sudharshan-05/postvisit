"""
PostVisit AI - Clinical Guideline Cross-Reference API Endpoints
Provides REST routes for guideline evaluation, provenance retrieval, and physician reviews.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Header, Query, Path, status
from fastapi.responses import JSONResponse

from api.auth import get_verified_user
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


async def get_caller_identity(
    user: Dict[str, Any] = Depends(get_verified_user)
) -> Dict[str, str]:
    """Resolves caller role and identity securely from verified JWT or test identity."""
    return {
        "role": user["role"],
        "caller_id": user["user_id"],
        "user_id": user["user_id"],
        "doctor_name": user.get("doctor_name") or user.get("email") or user["user_id"],
    }



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


import html
import re

def sanitize_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    clean = re.sub(r'<[^>]*>', '', text)
    return html.escape(clean).strip()


@router.get(
    "/api/v1/guidelines/search",
    status_code=status.HTTP_200_OK,
    summary="Search Curated Guideline Sources by Keyword",
    description=(
        "Searches the curated guideline source registry by keyword. "
        "Returns only verified, provenance-tracked sources. "
        "Does NOT perform live internet retrieval or invent citations."
    )
)
async def search_guidelines_endpoint(
    q: Optional[str] = Query(default=None, description="Search keyword (e.g. 'diabetes', 'hypertension')"),
    topic: Optional[str] = Query(default=None, description="Filter by clinical topic"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results to return")
):
    clean_q = sanitize_text(q)
    clean_topic = sanitize_text(topic)

    if not clean_q and not clean_topic:
        return {
            "query": clean_q,
            "results": [],
            "total": 0,
            "message": "Provide a search keyword using the ?q= parameter."
        }

    registry = get_guideline_registry()
    all_guidelines = registry.list_guidelines()
    q_lower = (clean_q or "").lower().strip()
    topic_lower = (clean_topic or "").lower().strip()


    matched = []
    for guideline in all_guidelines:
        if not guideline.get("verified", False):
            continue

        # Topic match
        if topic_lower and topic_lower not in guideline.get("topic", "").lower():
            continue

        # Keyword match against keywords list, title, topic, and summary
        if q_lower:
            searchable = " ".join([
                " ".join(guideline.get("keywords", [])),
                guideline.get("title", ""),
                guideline.get("topic", ""),
                guideline.get("summary", "")
            ]).lower()
            if q_lower not in searchable:
                continue

        matched.append({
            "id": guideline["id"],
            "title": guideline["title"],
            "organization": guideline["organization"],
            "topic": guideline["topic"],
            "version": guideline["version"],
            "publication_date": guideline["publication_date"],
            "summary": guideline["summary"],
            "keywords": guideline["keywords"],
            "source_url": guideline["source_url"],
            "verified": guideline["verified"],
            "checksum": guideline.get("checksum", ""),
        })

    matched = matched[:limit]

    return {
        "query": clean_q,
        "topic_filter": clean_topic,
        "results": matched,
        "total": len(matched),
        "note": (
            "Results are from the curated PostVisit AI guideline registry (ICMR, MoHFW, WHO-SEARO). "
            "These are verified sources only. No live internet retrieval is performed."
        )
    }


# -------------------------------------------------------------
# 6. Get Guideline by ID
# -------------------------------------------------------------
@router.get(
    "/api/v1/guidelines/{guideline_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Curated Guideline Source by ID",
    description="Retrieves a specific verified guideline and its evidence passages by ID."
)
async def get_guideline_by_id_endpoint(
    guideline_id: str = Path(..., description="ID of the guideline (e.g. icmr-diabetes-2022)")
):
    registry = get_guideline_registry()
    guideline = registry.get_guideline(guideline_id)
    if not guideline:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "GUIDELINE_NOT_FOUND",
                    "message": f"Guideline with ID '{guideline_id}' not found in registry."
                }
            }
        )
    return guideline

