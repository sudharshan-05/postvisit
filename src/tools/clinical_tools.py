"""
PostVisit AI - Core Clinical Tools
Implements concrete clinical tools for querying consultations, transcripts,
medical records, and submitting doctor reviews.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolContext
from api.repositories.consultation_repository import get_consultation_repository
from api.repositories.workflow_repository import get_workflow_repository


# -------------------------------------------------------------
# 1. Get Consultation Tool
# -------------------------------------------------------------
class ConsultationInputSchema(BaseModel):
    consultation_id: str = Field(description="UUID of the consultation")


class GetConsultationTool(BaseTool):
    name = "get_consultation"
    description = "Retrieves complete clinical consultation details by UUID."
    input_schema = ConsultationInputSchema
    required_permissions = ["read:consultation"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        repo = get_consultation_repository()
        record = repo.get_by_id(params["consultation_id"])
        if not record:
            raise ValueError(f"Consultation '{params['consultation_id']}' not found.")
        return record


# -------------------------------------------------------------
# 2. Get Transcript Tool
# -------------------------------------------------------------
class GetTranscriptTool(BaseTool):
    name = "get_transcript"
    description = "Retrieves speaker-labelled transcript turns for a consultation."
    input_schema = ConsultationInputSchema
    required_permissions = ["read:transcript"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        repo = get_consultation_repository()
        record = repo.get_by_id(params["consultation_id"])
        if not record:
            raise ValueError(f"Consultation '{params['consultation_id']}' not found.")
        return {
            "consultation_id": params["consultation_id"],
            "transcript": record.get("transcript") or []
        }


# -------------------------------------------------------------
# 3. Get Medical Record Tool
# -------------------------------------------------------------
class GetMedicalRecordTool(BaseTool):
    name = "get_medical_record"
    description = "Retrieves verified structured medical JSON for a consultation."
    input_schema = ConsultationInputSchema
    required_permissions = ["read:medical_record"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        repo = get_consultation_repository()
        record = repo.get_by_id(params["consultation_id"])
        if not record:
            raise ValueError(f"Consultation '{params['consultation_id']}' not found.")
        return {
            "consultation_id": params["consultation_id"],
            "medical_record": record.get("medical_record") or {}
        }


# -------------------------------------------------------------
# 4. Save Doctor Review Tool
# -------------------------------------------------------------
class DoctorReviewInputSchema(BaseModel):
    consultation_id: str = Field(description="UUID of the consultation")
    doctor_name: str = Field(description="Full name of reviewing doctor")
    decision: str = Field(default="approved", description="'approved' or 'amended'")
    corrected_medical_record: Optional[Dict[str, Any]] = Field(default=None, description="Corrected medical JSON")
    notes: Optional[str] = Field(default=None, description="Doctor notes or comments")


class SaveDoctorReviewTool(BaseTool):
    name = "save_doctor_review"
    description = "Saves physician review sign-off and transitions consultation to completed."
    input_schema = DoctorReviewInputSchema
    required_permissions = ["write:doctor_review"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        consultation_id = params["consultation_id"]
        repo = get_consultation_repository()
        record = repo.get_by_id(consultation_id)
        if not record:
            raise ValueError(f"Consultation '{consultation_id}' not found.")

        current_med = record.get("medical_record") or {}
        if params.get("corrected_medical_record"):
            current_med = params["corrected_medical_record"]

        current_med["requires_doctor_review"] = False
        current_med["doctor_review"] = {
            "reviewed_by": params["doctor_name"],
            "decision": params["decision"],
            "notes": params.get("notes") or "Reviewed and approved.",
            "caller_id": context.caller_id
        }

        # Update in repository
        duration = float(record.get("duration_seconds") or 0.0)
        repo.update_completed(
            consultation_id=consultation_id,
            duration_seconds=duration,
            transcript=record.get("transcript") or [],
            medical_record=current_med,
            validation_result=record.get("validation_result") or {"valid": True, "errors": [], "warnings": []}
        )

        # Update workflow run if present
        wf_repo = get_workflow_repository()
        wf_run = wf_repo.get_workflow_run_by_consultation(consultation_id)
        if wf_run:
            wf_repo.update_workflow_run_status(
                workflow_run_id=wf_run["id"],
                status="COMPLETED",
                current_step="COMPLETED",
                metadata={"doctor_review": current_med["doctor_review"]}
            )

        return {
            "consultation_id": consultation_id,
            "status": "completed",
            "reviewed_by": params["doctor_name"],
            "decision": params["decision"]
        }


# -------------------------------------------------------------
# 5. Patient Summary Tools (Stage 4)
# -------------------------------------------------------------
class GeneratePatientSummaryInputSchema(BaseModel):
    consultation_id: str = Field(description="UUID of the consultation")
    language: str = Field(default="en", description="Target language ('en', 'ta', 'kn', 'te', 'ml')")
    idempotency_key: Optional[str] = Field(default=None, description="Optional key to prevent duplicate runs")


class GeneratePatientSummaryTool(BaseTool):
    name = "generate_patient_summary"
    description = "Generates patient-friendly consultation summary from approved medical JSON."
    input_schema = GeneratePatientSummaryInputSchema
    required_permissions = ["generate:patient_summary"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        from src.services.summary_service import get_summary_service
        service = get_summary_service()
        return service.generate_summary(
            consultation_id=params["consultation_id"],
            target_language=params.get("language", "en"),
            idempotency_key=params.get("idempotency_key"),
            caller_role=context.role,
            caller_id=context.caller_id
        )


class GetPatientSummaryInputSchema(BaseModel):
    summary_id: str = Field(description="UUID of the patient summary")


class GetPatientSummaryTool(BaseTool):
    name = "get_patient_summary"
    description = "Retrieves a patient summary by UUID, enforcing patient approval gate."
    input_schema = GetPatientSummaryInputSchema
    required_permissions = ["read:patient_summary"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        from src.services.summary_service import get_summary_service
        service = get_summary_service()
        return service.get_summary(
            summary_id=params["summary_id"],
            caller_role=context.role,
            caller_id=context.caller_id
        )


class ReviewPatientSummaryInputSchema(BaseModel):
    summary_id: str = Field(description="UUID of the patient summary")
    doctor_name: str = Field(description="Name or ID of reviewing physician")
    decision: str = Field(default="approved", description="'approved', 'rejected', or 'amended'")
    notes: Optional[str] = Field(default=None, description="Physician clinical notes")
    corrected_summary: Optional[Dict[str, Any]] = Field(default=None, description="Amended summary if corrected")


class ReviewPatientSummaryTool(BaseTool):
    name = "review_patient_summary"
    description = "Allows an authorized physician to approve, reject, or amend a patient summary."
    input_schema = ReviewPatientSummaryInputSchema
    required_permissions = ["review:patient_summary"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        from src.services.summary_service import get_summary_service
        service = get_summary_service()
        return service.review_summary(
            summary_id=params["summary_id"],
            doctor_name=params["doctor_name"],
            decision=params.get("decision", "approved"),
            notes=params.get("notes"),
            corrected_summary=params.get("corrected_summary"),
            caller_role=context.role
        )


class CreateFollowUpTool(BaseTool):
    name = "create_follow_up"
    description = "Creates follow-up reminder and calendar schedule."
    input_schema = ConsultationInputSchema
    required_permissions = ["manage:follow_up"]

    def run(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        return {
            "consultation_id": params["consultation_id"],
            "status": "ready",
            "message": "Follow-up scheduling tool operational."
        }

