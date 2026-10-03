"""
PostVisit AI - Stage 3 Workflow Schemas
Defines request and response models for asynchronous workflow processing,
status reporting, observability history, and doctor review sign-offs.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from api.schemas.consultation import TranscriptTurn, MedicalRecord, ValidationSummary, InputMetadata, ErrorDetail


class WorkflowEnqueueResponse(BaseModel):
    """
    Immediate response returned when consultation upload is queued.
    """
    consultation_id: str = Field(description="UUID of the consultation")
    workflow_id: str = Field(description="UUID of the workflow run")
    status: str = Field(default="queued", description="Initial workflow status")


class WorkflowStepItem(BaseModel):
    """
    Summary of an individual workflow step execution.
    """
    id: Optional[str] = None
    step_name: str
    step_type: str
    status: str
    attempt: int = 1
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    input_reference: Optional[Dict[str, Any]] = None
    output_reference: Optional[Dict[str, Any]] = None


class AgentExecutionItem(BaseModel):
    """
    Summary of an AI agent execution within a workflow step.
    """
    id: Optional[str] = None
    agent_name: str
    agent_version: str = "1.0.0"
    status: str
    attempt: int = 1
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowHistoryResponse(BaseModel):
    """
    Comprehensive workflow history and observability response.
    """
    consultation_id: str
    workflow_run_id: str
    status: str
    current_step: Optional[str] = None
    workflow_version: str = "1.0.0"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    steps: List[WorkflowStepItem] = Field(default_factory=list)
    agent_executions: List[AgentExecutionItem] = Field(default_factory=list)


class ConsultationWorkflowStatusResponse(BaseModel):
    """
    Consultation status response exposing in-progress state, current step,
    and doctor review requirements for frontend tracking.
    """
    consultation_id: str
    status: str
    current_step: Optional[str] = None
    progress: Optional[float] = None  # None unless calculated reliably
    requires_doctor_review: bool = False
    media_storage_path: Optional[str] = None
    input: Optional[InputMetadata] = None
    transcript: Optional[List[TranscriptTurn]] = None
    medical_record: Optional[MedicalRecord] = None
    validation: Optional[ValidationSummary] = None
    error: Optional[ErrorDetail] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DoctorReviewRequest(BaseModel):
    """
    Request payload for doctor approval or clinical amendment.
    """
    doctor_name: str = Field(description="Name or ID of reviewing physician")
    decision: str = Field(default="approved", description="'approved' or 'amended'")
    notes: Optional[str] = Field(default=None, description="Doctor clinical remarks")
    corrected_medical_record: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Amended medical JSON if modifications were made"
    )


class DoctorReviewResponse(BaseModel):
    """
    Response returned upon doctor approval or sign-off.
    """
    consultation_id: str
    status: str = "completed"
    reviewed_by: str
    decision: str
    message: str = "Consultation successfully approved and signed."
