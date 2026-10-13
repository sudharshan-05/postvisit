"""
PostVisit AI - Patient Portal API Routes (Stage 5A)
Endpoints for:
- Patient Profile & Demographics
- Patient Health Overview & Dated Health Trends
- Last Visit Clinical Summary (14 clinical sections, approved version only)
- Chronological Consultation History (Patient isolation enforced)
- Structured Recovery Plan (Non-mutating checklist tracking)
- Prescribed Medications Display
- Patient Lab Reports (Upload & Manual Entry with clear provenance)
- Grounded Contextual AI Chatbot ("Ask About Your Visit") with Safety Guardrails
- Patient Voice Recording and Transcription
"""

import logging
from typing import Dict, Any, List, Optional
import io

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    Path,
    UploadFile,
    File,
    Form,
    status,
    HTTPException
)
from fastapi.responses import JSONResponse, StreamingResponse, Response

from api.auth import get_patient_identity_secure, enforce_patient_data_scope
from src.services.patient_service import PatientService, get_patient_service
from src.schemas.patient_portal_schema import (
    PatientProfileResponse,
    PatientHealthOverviewResponse,
    LastVisitSummaryResponse,
    ConsultationHistoryResponse,
    RecoveryPlanResponse,
    RecoveryPlanItem,
    RecoveryTaskToggleRequest,
    PatientMedicationListResponse,
    LabReportListResponse,
    LabReportItem,
    LabReportManualCreateRequest,
    PatientChatRequest,
    PatientChatResponse,
    ChatMessageItem,
    PatientVoiceTranscribeResponse,
    LabReportConfirmRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/patient", tags=["Patient Portal"])


# -----------------------------------------------------------------------------
# Auth Dependencies — real JWT verification via api.auth
# No role or user_id injection via query params or headers is permitted.
# get_patient_identity and enforce_patient_access are aliases for backward
# test-fixture compatibility only.
# -----------------------------------------------------------------------------
get_patient_identity = get_patient_identity_secure


def enforce_patient_access(auth: Dict[str, str], requested_patient_id: Optional[str] = None) -> str:
    """
    Enforces RBAC using the verified JWT identity:
    - Doctors and admins can access any patient record.
    - Patients can ONLY access their own records.
    """
    return enforce_patient_data_scope(auth, requested_patient_id)


# -----------------------------------------------------------------------------
# 1. Patient Profile
# -----------------------------------------------------------------------------
@router.get(
    "/profile",
    response_model=PatientProfileResponse,
    summary="Get Patient Profile",
    description="Retrieves demographic and medical profile details for the authenticated patient."
)
async def get_patient_profile_endpoint(
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    try:
        return service.get_patient_profile(pid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# -----------------------------------------------------------------------------
# 2. Patient Health Overview & Trends
# -----------------------------------------------------------------------------
@router.get(
    "/overview",
    response_model=PatientHealthOverviewResponse,
    summary="Get Patient Health Overview",
    description="Retrieves the patient health overview including genuine dated health trends and recent consultation snapshot."
)
async def get_health_overview_endpoint(
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    try:
        return service.get_health_overview(pid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# -----------------------------------------------------------------------------
# 3. Last Visit - Quick Summary (14 Clinical Sections, Approved Gated)
# -----------------------------------------------------------------------------
@router.get(
    "/last-visit",
    response_model=LastVisitSummaryResponse,
    summary="Get Last Visit Summary",
    description="Displays the 14-section patient-friendly clinical summary of the latest doctor-approved consultation."
)
@router.get(
    "/visits/last",
    response_model=LastVisitSummaryResponse,
    include_in_schema=False
)
async def get_last_visit_summary_endpoint(
    consultation_id: Optional[str] = Query(default=None, description="Specific consultation UUID"),
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    try:
        return service.get_last_visit_summary(pid, consultation_id=consultation_id)
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": str(pe)}
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(ve)}
        )


# -----------------------------------------------------------------------------
# 4. Chronological Visit History (Patient Isolation Enforced)
# -----------------------------------------------------------------------------
@router.get(
    "/history",
    response_model=ConsultationHistoryResponse,
    summary="Get Visit History",
    description="Returns chronological consultation history strictly belonging to the authorized patient."
)
async def get_visit_history_endpoint(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=50, description="Items per page"),
    status_filter: Optional[str] = Query(default=None, description="Filter by consultation status"),
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    return service.get_visit_history(pid, page=page, page_size=page_size, status_filter=status_filter)


# -----------------------------------------------------------------------------
# 5. Structured Recovery Plan
# -----------------------------------------------------------------------------
@router.get(
    "/recovery-plan",
    response_model=RecoveryPlanResponse,
    summary="Get Structured Recovery Plan",
    description="Returns structured checklist of recovery tasks combining doctor-approved instructions with personal tracking marks."
)
async def get_recovery_plan_endpoint(
    consultation_id: Optional[str] = Query(default=None, description="Specific consultation UUID"),
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    return service.get_recovery_plan(pid, consultation_id=consultation_id)


@router.post(
    "/recovery-plan/toggle",
    summary="Toggle Recovery Checklist Task",
    description="Marks a checklist task as completed for personal tracking. Does NOT mutate the physician's authoritative medical record."
)
async def toggle_recovery_task_endpoint(
    payload: RecoveryTaskToggleRequest,
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    return service.toggle_recovery_task(pid, payload)


# -----------------------------------------------------------------------------
# 6. Prescribed Medications
# -----------------------------------------------------------------------------
@router.get(
    "/medications",
    response_model=PatientMedicationListResponse,
    summary="Get Prescribed Medications",
    description="Returns patient-friendly medication cards with exact clinically important details from the approved medical record."
)
async def get_medications_endpoint(
    consultation_id: Optional[str] = Query(default=None, description="Specific consultation UUID"),
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    return service.get_medications(pid, consultation_id=consultation_id)


# -----------------------------------------------------------------------------
# 7. Lab Reports (Upload & Manual Entry)
# -----------------------------------------------------------------------------
@router.get(
    "/lab-reports",
    response_model=LabReportListResponse,
    summary="List Lab Reports",
    description="Retrieves patient lab reports, clearly marking patient-provided vs physician-reviewed reports."
)
async def list_lab_reports_endpoint(
    consultation_id: Optional[str] = Query(default=None, description="Filter by consultation UUID"),
    patient_id: Optional[str] = Query(default=None, description="Patient ID (doctors only)"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = enforce_patient_access(auth, patient_id)
    return service.list_lab_reports(pid, consultation_id=consultation_id)


@router.post(
    "/lab-reports/manual",
    response_model=LabReportItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add Manual Lab Report Summary",
    description="Submits a patient-entered lab test summary. Labeled as patient-provided and unreviewed."
)
async def create_manual_lab_report_endpoint(
    payload: LabReportManualCreateRequest,
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    return service.create_manual_lab_report(pid, payload)


@router.post(
    "/lab-reports/upload",
    response_model=LabReportItem,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Lab Report Document",
    description="Uploads a PDF or image medical report securely. Validates file size (max 10MB) and format."
)
async def upload_lab_report_endpoint(
    file: UploadFile = File(..., description="PDF or Image lab document"),
    test_name: Optional[str] = Form(default="Diagnostic Lab Report", description="Name of test e.g. HbA1c, Lipid Profile"),
    report_date: Optional[str] = Form(default=None, description="Date on report YYYY-MM-DD"),
    facility_name: Optional[str] = Form(default=None, description="Laboratory name"),
    consultation_id: Optional[str] = Form(default=None, description="Linked consultation UUID"),
    patient_notes: Optional[str] = Form(default=None, description="Optional notes"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    try:
        content = await file.read()
        return service.create_uploaded_lab_report(
            patient_id=pid,
            file_bytes=content,
            filename=file.filename or "report.pdf",
            content_type=file.content_type or "application/pdf",
            test_name=test_name,
            report_date=report_date,
            facility_name=facility_name,
            consultation_id=consultation_id,
            patient_notes=patient_notes
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get(
    "/lab-reports/{report_id}/download",
    summary="Download Lab Report Document",
    description="Securely streams the lab report document after verifying patient ownership."
)
async def download_lab_report_endpoint(
    report_id: str = Path(..., description="Lab report UUID"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    try:
        res = service.get_lab_report_bytes(pid, report_id)
        file_bytes = res["bytes"]
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found in storage.")

        return Response(
            content=file_bytes,
            media_type=res["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{res["filename"]}"'}
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post(
    "/lab-reports/{report_id}/confirm",
    response_model=LabReportItem,
    summary="Confirm Extracted Lab Report Results",
    description="Patient confirms or corrects extracted test results before submitting for clinician review."
)
async def confirm_lab_report_endpoint(
    report_id: str = Path(..., description="Lab report UUID"),
    payload: LabReportConfirmRequest = ...,
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    try:
        return service.confirm_lab_report(
            patient_id=pid,
            report_id=report_id,
            confirmed_results=payload.confirmed_results,
            patient_notes=payload.patient_notes
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# -----------------------------------------------------------------------------
# 8. Contextual AI Chatbot ("Ask About Your Visit")
# -----------------------------------------------------------------------------
@router.post(
    "/chat",
    response_model=PatientChatResponse,
    summary="Contextual AI Chat Inquiry",
    description="Queries the AI assistant with automatic grounding in approved consultation records and strict clinical safety guardrails."
)
async def patient_chat_endpoint(
    payload: PatientChatRequest,
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    return service.handle_chat_query(pid, payload)


@router.get(
    "/chat/history",
    summary="Get Chat History",
    description="Returns previous chat messages for the active session."
)
async def get_chat_history_endpoint(
    session_id: Optional[str] = Query(default=None),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    messages = service.patient_repo.get_chat_history(pid, session_id=session_id)
    return {"patient_id": pid, "session_id": session_id, "messages": messages}


# -----------------------------------------------------------------------------
# 9. Voice Recording and Transcription
# -----------------------------------------------------------------------------
@router.post(
    "/voice-transcribe",
    response_model=PatientVoiceTranscribeResponse,
    summary="Transcribe Patient Voice Note",
    description="Transcribes patient audio inquiry in Tamil/English. Clearly marked as patient-provided and unverified."
)
async def voice_transcribe_endpoint(
    audio: UploadFile = File(..., description="Audio file (WAV, MP3, WebM, OGG, M4A)"),
    language: str = Form(default="auto", description="Spoken language ('ta', 'en', 'auto')"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    pid = auth["caller_id"]
    try:
        content = await audio.read()
        return service.transcribe_patient_voice(
            patient_id=pid,
            audio_bytes=content,
            filename=audio.filename or "recording.webm",
            content_type=audio.content_type or "audio/webm",
            language=language
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Voice transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Transcription failed: {str(e)}")


# -----------------------------------------------------------------------------
# 10. Route Aliases for Frontend & Test Compatibility
# -----------------------------------------------------------------------------
@router.get("/dashboard", summary="Patient Dashboard (Alias for /overview)", include_in_schema=False)
async def get_patient_dashboard_alias(
    patient_id: Optional[str] = Query(default=None),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    return await get_health_overview_endpoint(patient_id=patient_id, auth=auth, service=service)


@router.get("/health-trends", summary="Patient Health Trends (Alias)", include_in_schema=False)
async def get_patient_health_trends_alias(
    patient_id: Optional[str] = Query(default=None),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    overview = await get_health_overview_endpoint(patient_id=patient_id, auth=auth, service=service)
    return {"patient_id": patient_id or auth["caller_id"], "health_trends": overview.health_trends}


@router.post("/ask-ai", response_model=PatientChatResponse, summary="Ask AI (Alias for /chat)", include_in_schema=False)
async def patient_ask_ai_alias(
    payload: PatientChatRequest,
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    return await patient_chat_endpoint(payload=payload, auth=auth, service=service)


@router.post("/voice-note", response_model=PatientVoiceTranscribeResponse, summary="Voice Note (Alias for /voice-transcribe)", include_in_schema=False)
async def patient_voice_note_alias(
    file: UploadFile = File(..., description="Audio file"),
    language: str = Form(default="auto"),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    return await voice_transcribe_endpoint(audio=file, language=language, auth=auth, service=service)


@router.post("/lab-report", summary="Lab Report Upload (Alias for /lab-reports/upload)", include_in_schema=False)
async def patient_lab_report_alias(
    file: UploadFile = File(..., description="PDF or Image lab document"),
    test_name: str = Form(default="Lab Test"),
    report_date: Optional[str] = Form(default=None),
    facility_name: Optional[str] = Form(default=None),
    consultation_id: Optional[str] = Form(default=None),
    patient_notes: Optional[str] = Form(default=None),
    auth: Dict[str, str] = Depends(get_patient_identity),
    service: PatientService = Depends(get_patient_service)
):
    return await upload_lab_report_endpoint(
        file=file,
        test_name=test_name,
        report_date=report_date,
        facility_name=facility_name,
        consultation_id=consultation_id,
        patient_notes=patient_notes,
        auth=auth,
        service=service
    )

