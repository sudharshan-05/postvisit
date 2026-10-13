"""
PostVisit AI - Doctor Portal & Clinical Review API Routes (Stage 5B)
Provides physician-facing endpoints:
- Consultation list with unified statuses (PROCESSING, PENDING REVIEW, NEEDS REVIEW, APPROVED, REJECTED, FAILED)
- Patient clinical overview (last visit, visit history, structured clinical domains)
- Compact organizational quick summary with direct source record drill-down
- Lab report review workflow (preserves patient submissions, stores doctor corrections, audit logs)
- Medical guideline cross-reference and finding reviews (neutral non-punitive discrepancy prompts)
- Grounded Ask AI separating Source Data, AI Summary, Guideline Evidence, and AI Interpretation
- Voice clinical recording with mandatory doctor transcript review and confirmation gate
- Truthful consultation timeline reflecting backend states
- Comprehensive append-only audit trail
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Path,
    UploadFile,
    File,
    status,
    HTTPException
)
from fastapi.responses import JSONResponse

from api.auth import get_doctor_identity_secure
from src.services.doctor_service import DoctorService, get_doctor_service
from src.schemas.doctor_dashboard_schema import (
    DoctorConsultationListResponse,
    PatientClinicalOverview,
    DoctorQuickSummary,
    DoctorLabReportReviewRequest,
    DoctorGuidelineReviewRequest,
    DoctorAskAIRequest,
    DoctorAskAIResponse,
    DoctorVoiceTranscribeResponse,
    DoctorVoiceConfirmRequest,
    DoctorVoiceConfirmResponse,
    ConsultationTimelineResponse,
    DoctorTranscriptUpdateRequest,
    DoctorConsultationVitalsRequest,
)

logger = logging.getLogger("postvisit.routes.doctor")

router = APIRouter(prefix="/api/v1/doctor", tags=["Doctor Portal & Review"])


# -----------------------------------------------------------------------------
# Security — uses real JWT verification via api.auth
# -----------------------------------------------------------------------------
# All doctor routes use get_doctor_identity_secure from api.auth.
# This verifies the Supabase Bearer token and enforces doctor/clinician role.
# No role or user_id injection via query params or headers is permitted.
# get_doctor_identity is kept as an alias for backward test-fixture compatibility.
get_doctor_identity = get_doctor_identity_secure


# -----------------------------------------------------------------------------
# 1. Doctor Consultation List
# -----------------------------------------------------------------------------

@router.get(
    "/consultations",
    response_model=DoctorConsultationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Authorized Consultations for Doctor Queue"
)
async def list_doctor_consultations(
    filter_type: str = Query(
        default="all",
        description="Filter option: 'all', 'pending_review', 'needs_attention', 'completed', 'recent'"
    ),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    patient_id: Optional[str] = Query(default=None, description="Filter by specific patient ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Retrieves authorized consultations categorized into:
    PROCESSING, PENDING REVIEW, NEEDS REVIEW, APPROVED, REJECTED, FAILED.
    """
    return doctor_service.list_consultations(
        doctor_id=auth["caller_id"],
        filter_type=filter_type,
        start_date=start_date,
        end_date=end_date,
        patient_id=patient_id,
        page=page,
        page_size=page_size
    )


# -----------------------------------------------------------------------------
# 2. Patient Clinical Overview & Longitudinal History
# -----------------------------------------------------------------------------

@router.get(
    "/patient/{patient_id}/overview",
    response_model=PatientClinicalOverview,
    status_code=status.HTTP_200_OK,
    summary="Get Structured Patient Clinical Overview & Visit History"
)
async def get_patient_clinical_overview(
    patient_id: str = Path(..., description="Unique patient identifier (e.g. PT-89241)"),
    consultation_id: Optional[str] = Query(default=None, description="Target consultation UUID"),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Assembles comprehensive clinical domains:
    Last visit, visit history, symptoms, HPI, findings, medications, tests,
    doctor recommendations, follow-up, lab reports, summary, guidelines, audit history.
    """
    try:
        return doctor_service.get_patient_clinical_overview(
            patient_id=patient_id,
            consultation_id=consultation_id,
            doctor_id=auth["caller_id"]
        )
    except Exception as e:
        logger.error(f"Error fetching patient clinical overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "OVERVIEW_ERROR", "message": str(e)}
        )


# -----------------------------------------------------------------------------
# 3. Patient Quick Summary
# -----------------------------------------------------------------------------

@router.get(
    "/consultations/{consultation_id}/quick-summary",
    response_model=DoctorQuickSummary,
    status_code=status.HTTP_200_OK,
    summary="Get Compact Doctor-Side Quick Summary"
)
async def get_patient_quick_summary(
    consultation_id: str = Path(..., description="UUID of consultation"),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Returns an organizational quick summary with direct source record drill-down link.
    """
    try:
        return doctor_service.get_patient_quick_summary(
            consultation_id=consultation_id,
            doctor_id=auth["caller_id"]
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(ve)}
        )


# -----------------------------------------------------------------------------
# 4. Lab Reports Review Workflow
# -----------------------------------------------------------------------------

@router.get(
    "/lab-reports",
    status_code=status.HTTP_200_OK,
    summary="List Doctor-Facing Lab Reports"
)
async def list_doctor_lab_reports(
    patient_id: Optional[str] = Query(default=None),
    consultation_id: Optional[str] = Query(default=None),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Lists lab reports with patient submissions, AI labels, and doctor verified layer.
    """
    reports = doctor_service.list_lab_reports(
        patient_id=patient_id,
        consultation_id=consultation_id,
        doctor_id=auth["caller_id"]
    )
    return {"lab_reports": reports, "total": len(reports)}


@router.post(
    "/lab-reports/{report_id}/review",
    status_code=status.HTTP_200_OK,
    summary="Doctor Review / Correct Lab Report"
)
async def review_lab_report(
    report_id: str = Path(..., description="ID of lab report"),
    payload: DoctorLabReportReviewRequest = ...,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Reviews a lab report. Preserves original patient submission, stores verified value separately,
    and appends an audit event.
    """
    try:
        updated = doctor_service.review_lab_report(
            report_id=report_id,
            doctor_id=auth["caller_id"],
            doctor_name=auth["doctor_name"],
            review_req=payload
        )
        return updated
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": str(ve)}
        )


# -----------------------------------------------------------------------------
# 5. Medical Guideline Cross-Reference & Finding Reviews
# -----------------------------------------------------------------------------

@router.get(
    "/consultations/{consultation_id}/guidelines",
    status_code=status.HTTP_200_OK,
    summary="Get Authoritative Guideline Cross-Reference Findings"
)
async def get_consultation_guidelines(
    consultation_id: str = Path(..., description="UUID of consultation"),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Retrieves or calculates verified guideline cross-reference results.
    Never invents unverified guidelines.
    """
    try:
        return doctor_service.get_guideline_cross_reference(consultation_id)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(ve)}
        )


@router.post(
    "/consultations/{consultation_id}/guidelines/{finding_id}/review",
    status_code=status.HTTP_200_OK,
    summary="Record Doctor Decision on Guideline Finding"
)
async def review_guideline_finding(
    consultation_id: str = Path(...),
    finding_id: str = Path(...),
    payload: DoctorGuidelineReviewRequest = ...,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Records clinician decision ('relevant', 'not_relevant', 'review_later', 'add_note')
    on a guideline finding without mutating the underlying medical record.
    """
    try:
        return doctor_service.review_guideline_finding(
            consultation_id=consultation_id,
            finding_id=finding_id,
            doctor_id=auth["caller_id"],
            doctor_name=auth["doctor_name"],
            review_req=payload
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(ve)}
        )


# -----------------------------------------------------------------------------
# 6. Doctor Grounded Ask AI
# -----------------------------------------------------------------------------

@router.post(
    "/consultations/{consultation_id}/ask",
    response_model=DoctorAskAIResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor Grounded Ask AI Query"
)
async def doctor_ask_ai(
    consultation_id: str = Path(...),
    payload: DoctorAskAIRequest = ...,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Answers clinician questions grounded in verified context, clearly categorizing:
    SOURCE DATA, AI SUMMARY, GUIDELINE EVIDENCE, and AI INTERPRETATION.
    """
    try:
        return doctor_service.ask_ai(
            consultation_id=consultation_id,
            doctor_id=auth["caller_id"],
            query=payload.query,
            context_type=payload.context_type
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(ve)}
        )


# -----------------------------------------------------------------------------
# 7. Doctor Voice Recording Workflow (Transcribe -> Edit -> Confirm)
# -----------------------------------------------------------------------------

@router.post(
    "/consultations/{consultation_id}/voice-note/transcribe",
    response_model=DoctorVoiceTranscribeResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe Doctor Voice Note (Draft Requires Confirmation)"
)
async def transcribe_doctor_voice_note(
    consultation_id: str = Path(...),
    mock_transcript: Optional[str] = Query(default=None),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Generates a draft transcript for the clinician to inspect and edit.
    Does NOT store into medical record until explicitly confirmed.
    """
    return doctor_service.transcribe_voice_draft(
        consultation_id=consultation_id,
        doctor_id=auth["caller_id"],
        mock_transcript=mock_transcript
    )


@router.post(
    "/consultations/{consultation_id}/voice-note/confirm",
    response_model=DoctorVoiceConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Explicitly Confirm Doctor Voice Note"
)
async def confirm_doctor_voice_note(
    consultation_id: str = Path(...),
    payload: DoctorVoiceConfirmRequest = ...,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Saves doctor confirmed clinical note into the clinical record and audit log.
    """
    try:
        return doctor_service.confirm_voice_note(
            confirm_req=payload,
            doctor_id=auth["caller_id"],
            doctor_name=auth["doctor_name"]
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CONFIRMATION_REQUIRED", "message": str(ve)}
        )


# -----------------------------------------------------------------------------
# 8. Consultation Timeline & Audit Trail
# -----------------------------------------------------------------------------

@router.get(
    "/consultations/{consultation_id}/timeline",
    response_model=ConsultationTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Authoritative 10-Step Consultation Processing Timeline"
)
async def get_consultation_timeline(
    consultation_id: str = Path(...),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Reflects truthful backend states across all 10 workflow stages without fake checkmarks.
    """
    try:
        return doctor_service.get_consultation_timeline(consultation_id)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(ve)}
        )


@router.get(
    "/consultations/{consultation_id}/audit-trail",
    status_code=status.HTTP_200_OK,
    summary="Get Append-Only Clinical Audit Trail"
)
async def get_consultation_audit_trail(
    consultation_id: str = Path(...),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Returns chronological immutable audit events for this consultation.
    """
    trail = doctor_service.get_audit_trail(consultation_id)
    return {"consultation_id": consultation_id, "audit_trail": trail, "total": len(trail)}


# -----------------------------------------------------------------------------
# 9. Route Aliases for Test & Frontend Compatibility
# -----------------------------------------------------------------------------
@router.get("/pending-reviews", response_model=DoctorConsultationListResponse, summary="Pending Reviews (Alias)", include_in_schema=False)
async def get_doctor_pending_reviews_alias(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    patient_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    return await list_doctor_consultations(
        filter_type="pending_review",
        start_date=start_date,
        end_date=end_date,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        auth=auth,
        doctor_service=doctor_service
    )


@router.post("/voice-note", response_model=DoctorVoiceTranscribeResponse, summary="Doctor Voice Note (Alias)", include_in_schema=False)
async def doctor_voice_note_alias(
    file: UploadFile = File(..., description="Doctor audio file"),
    consultation_id: Optional[str] = Query(default="default-consultation"),
    mock_transcript: Optional[str] = Query(default=None),
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    return doctor_service.transcribe_voice_draft(
        consultation_id=consultation_id or "default-consultation",
        doctor_id=auth["caller_id"],
        mock_transcript=mock_transcript
    )


@router.post("/ask-ai", response_model=DoctorAskAIResponse, summary="Doctor Ask AI (Alias)", include_in_schema=False)
async def doctor_ask_ai_alias(
    payload: DoctorAskAIRequest,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    return await doctor_ask_ai(
        consultation_id=payload.consultation_id or "default-consultation",
        payload=payload,
        auth=auth,
        doctor_service=doctor_service
    )


# -----------------------------------------------------------------------------
# 10. Transcript Correction & Vitals Entry
# -----------------------------------------------------------------------------
@router.put(
    "/consultations/{consultation_id}/transcript",
    status_code=status.HTTP_200_OK,
    summary="Update Consultation Transcript"
)
async def update_consultation_transcript_endpoint(
    consultation_id: str = Path(...),
    payload: DoctorTranscriptUpdateRequest = ...,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Saves doctor transcript corrections and marks the transcript as clinically confirmed/edited.
    """
    try:
        return doctor_service.update_transcript(
            consultation_id=consultation_id,
            doctor_id=auth["caller_id"],
            doctor_name=auth.get("doctor_name", "Dr. A. Ramanathan"),
            req=payload
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.put(
    "/consultations/{consultation_id}/vitals",
    status_code=status.HTTP_200_OK,
    summary="Record or Update Current-Visit Vitals"
)
@router.post(
    "/consultations/{consultation_id}/vitals",
    status_code=status.HTTP_200_OK,
    summary="Record Current-Visit Vitals"
)
async def update_consultation_vitals_endpoint(
    consultation_id: str = Path(...),
    payload: DoctorConsultationVitalsRequest = ...,
    auth: Dict[str, str] = Depends(get_doctor_identity),
    doctor_service: DoctorService = Depends(get_doctor_service)
):
    """
    Records clinician measurements (BP, pulse, height, weight, SpO2, temp) with provenance.
    """
    try:
        return doctor_service.update_vitals(
            consultation_id=consultation_id,
            doctor_id=auth["caller_id"],
            doctor_name=auth.get("doctor_name", "Dr. A. Ramanathan"),
            req=payload
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


