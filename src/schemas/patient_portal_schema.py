"""
PostVisit AI - Patient Portal & Health Dashboard Schemas
Defines request and response structures for patient health overview, last visit summary,
visit history, structured recovery plans, lab reports, AI assistant chat, and voice notes.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator


# -------------------------------------------------------------
# 1. Patient Profile & Demographics
# -------------------------------------------------------------
class PatientProfileResponse(BaseModel):
    """Profile details permitted for patient view."""
    patient_id: str = Field(description="Unique patient identifier, e.g. 'PT-89241'")
    full_name: str = Field(default="Patient", description="Patient full name")
    name: Optional[str] = Field(default=None, description="Patient name alias")
    age: Optional[int] = Field(default=None, description="Patient age in years")
    gender: Optional[str] = Field(default=None, description="Gender identity")
    phone: Optional[str] = Field(default=None, description="Contact phone")
    email: Optional[str] = Field(default=None, description="Contact email")
    preferred_language: Optional[str] = Field(default="en", description="Preferred language")
    blood_group: Optional[str] = Field(default=None, description="Blood type")
    allergies: List[str] = Field(default_factory=list, description="Known patient allergies")
    chronic_conditions: List[str] = Field(default_factory=list, description="Documented chronic conditions")
    created_at: Optional[str] = None


# -------------------------------------------------------------
# 2. Health Metrics & Trends (Actual dated measurements only)
# -------------------------------------------------------------
class PatientHealthMetricItem(BaseModel):
    """A single dated clinical measurement."""
    id: Optional[str] = None
    metric_type: str = Field(description="'blood_pressure', 'glucose', 'heart_rate', 'weight'")
    metric_name: Optional[str] = None
    numeric_value: Optional[float] = None
    value: Optional[float] = None
    secondary_value: Optional[float] = None
    value_secondary: Optional[float] = None
    unit: str
    recorded_at: str
    source: str = "consultation"
    notes: Optional[str] = None


class PatientHealthTrendSeries(BaseModel):
    """Trend series for a specific clinical measurement."""
    metric_name: str
    metric_type: Optional[str] = None
    unit: str
    has_sufficient_data: bool = False
    has_data: bool = False
    data_points: List[PatientHealthMetricItem] = Field(default_factory=list)
    empty_state_message: Optional[str] = None
    latest_value_display: Optional[str] = None
    trend_direction: Optional[str] = None  # 'stable', 'rising', 'falling', or None


# -------------------------------------------------------------
# 3. Patient Health Overview
# -------------------------------------------------------------
class PatientHealthOverviewResponse(BaseModel):
    """High-level health overview aggregating records for the patient dashboard."""
    patient_profile: PatientProfileResponse
    most_recent_consultation_date: Optional[str] = None
    most_recent_consultation_id: Optional[str] = None
    last_visit_quick_summary: Optional[Any] = None
    has_approved_summary: bool = False
    latest_approved_summary: Optional[Dict[str, Any]] = None
    doctor_approved_medications: List[Any] = Field(default_factory=list)
    current_medications: List[Any] = Field(default_factory=list)
    upcoming_follow_up_date: Optional[str] = None
    upcoming_follow_up_notes: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    recent_lab_reports: List[Any] = Field(default_factory=list)
    recent_symptoms: List[str] = Field(default_factory=list)
    health_trends: List[PatientHealthTrendSeries] = Field(default_factory=list)
    contextual_questions: List[str] = Field(default_factory=list)


# -------------------------------------------------------------
# 4. Last Visit Detailed Summary
# -------------------------------------------------------------
class LastVisitSummaryResponse(BaseModel):
    """Detailed breakdown of the most recent doctor-approved visit."""
    consultation_id: str
    consultation_date: Optional[str] = None
    doctor_name: Optional[str] = None
    main_reason_for_visit: str
    reported_symptoms: List[str] = Field(default_factory=list)
    history_of_present_illness: Optional[str] = None
    doctor_findings: Optional[str] = None
    doctor_approved_diagnosis: Optional[str] = None
    doctor_diagnosis: Optional[str] = None
    doctor_recommendations: List[str] = Field(default_factory=list)
    prescribed_medications: List[Any] = Field(default_factory=list)
    investigations_ordered: List[str] = Field(default_factory=list)
    tests_ordered: List[Any] = Field(default_factory=list)
    self_care_instructions: List[str] = Field(default_factory=list)
    warnings_and_precautions: List[str] = Field(default_factory=list)
    follow_up_instructions: Optional[str] = None
    follow_up_date: Optional[str] = None
    outstanding_uncertainties: List[str] = Field(default_factory=list)
    approval_status: str = Field(description="'SUMMARY_APPROVED' or 'PENDING_DOCTOR_APPROVAL'")
    reviewed_at: Optional[str] = None
    contextual_questions: List[str] = Field(default_factory=list)


# -------------------------------------------------------------
# 5. Visit History
# -------------------------------------------------------------
class ConsultationHistoryItem(BaseModel):
    """Item in chronological patient visit history."""
    consultation_id: str
    date: Optional[str] = None
    consultation_date: Optional[str] = None
    time: Optional[str] = None
    visit_reason: Optional[str] = None
    main_reason: Optional[str] = None
    doctor_name: Optional[str] = None
    recorded_symptoms: List[str] = Field(default_factory=list)
    reported_symptoms: List[str] = Field(default_factory=list)
    processing_status: str
    doctor_review_status: str
    approved_summary_available: bool = False
    summary_available: bool = False
    linked_lab_reports_count: int = 0
    follow_up_instructions: Optional[str] = None
    follow_up_timeline: Optional[str] = None


class ConsultationHistoryResponse(BaseModel):
    patient_id: str
    page: int = 1
    page_size: int = 10
    total: int = 0
    items: List[ConsultationHistoryItem] = Field(default_factory=list)


# -------------------------------------------------------------
# 6. Structured Recovery & Care Plan
# -------------------------------------------------------------
class RecoveryPlanItem(BaseModel):
    """Single item in the patient care plan."""
    task_key: str
    category: Optional[str] = None
    task_type: Optional[str] = Field(default="checklist", description="'medication', 'lab_test', 'self_care', 'diet_activity', 'follow_up'")
    title: str
    description: str
    doctor_instruction: Optional[str] = None
    is_doctor_prescribed: bool = True
    patient_completed: bool = False
    is_completed: bool = False
    completed_at: Optional[str] = None
    notes: Optional[str] = None


class RecoveryPlanResponse(BaseModel):
    patient_id: Optional[str] = None
    consultation_id: Optional[str] = None
    consultation_date: Optional[str] = None
    doctor_name: Optional[str] = None
    has_structured_plan: bool = False
    has_plan: bool = False
    empty_message: Optional[str] = None
    message: Optional[str] = None
    plan_items: List[RecoveryPlanItem] = Field(default_factory=list)
    items: List[RecoveryPlanItem] = Field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    contextual_questions: List[str] = Field(default_factory=list)


class RecoveryTaskToggleRequest(BaseModel):
    consultation_id: str
    task_key: str
    completed: Optional[bool] = None
    is_completed: Optional[bool] = None
    notes: Optional[str] = None


# -------------------------------------------------------------
# 7. Patient Medications View
# -------------------------------------------------------------
class PatientMedicationDetail(BaseModel):
    medicine_name: str
    name: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = "Oral"
    frequency: Optional[str] = "Daily"
    timing: Optional[str] = "After food"
    duration: Optional[str] = "Ongoing"
    instructions: Optional[str] = None
    source_consultation_id: Optional[str] = None
    source_consultation_date: Optional[str] = None
    review_status: str = "APPROVED"
    approval_status: str = "approved"


class PatientMedicationListResponse(BaseModel):
    patient_id: str
    medications: List[PatientMedicationDetail] = Field(default_factory=list)
    total: int = 0


# -------------------------------------------------------------
# 8. Lab Reports (Upload & Manual Entry)
# -------------------------------------------------------------
class LabReportManualCreateRequest(BaseModel):
    test_name: str = Field(..., min_length=2, max_length=150)
    report_date: str = Field(..., description="YYYY-MM-DD format")
    facility_name: Optional[str] = Field(default=None, max_length=150)
    laboratory_name: Optional[str] = Field(default=None, max_length=150)
    test_result: Optional[str] = Field(default=None, max_length=1000)
    result_summary: Optional[str] = Field(default=None, max_length=1000)
    unit: Optional[str] = Field(default=None, max_length=50)
    units: Optional[str] = Field(default=None, max_length=50)
    reference_range: Optional[str] = Field(default=None, max_length=100)
    patient_notes: Optional[str] = Field(default=None, max_length=1000)
    consultation_id: Optional[str] = None


class LabReportItem(BaseModel):
    id: str
    patient_id: str
    consultation_id: Optional[str] = None
    test_name: str
    report_date: str
    facility_name: Optional[str] = None
    laboratory_name: Optional[str] = None
    test_result: Optional[str] = None
    result_summary: Optional[str] = None
    unit: Optional[str] = None
    units: Optional[str] = None
    reference_range: Optional[str] = None
    patient_notes: Optional[str] = None
    entry_mode: str = "manual"  # 'manual' or 'upload'
    review_status: str = "unreviewed"  # 'unreviewed' or 'physician_reviewed'
    doctor_feedback: Optional[str] = None
    document_url: Optional[str] = None
    filename: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    created_at: Optional[str] = None


class LabReportListResponse(BaseModel):
    patient_id: str
    reports: List[LabReportItem] = Field(default_factory=list)
    total: int = 0


# -------------------------------------------------------------
# 9. Contextual AI Chatbot ("Ask About Your Visit")
# -------------------------------------------------------------
class PatientChatRequest(BaseModel):
    message: Optional[str] = Field(default=None, max_length=2000)
    question: Optional[str] = Field(default=None, max_length=2000)
    patient_id: Optional[str] = None
    context_type: str = Field(
        default="general",
        description="'general', 'last_visit', 'medications', 'lab_report', 'health_trend', 'recovery_plan'"
    )
    context_id: Optional[str] = None
    consultation_id: Optional[str] = None
    session_id: Optional[str] = None
    language: str = Field(default="en", description="'en' or 'ta'")

    @model_validator(mode="before")
    @classmethod
    def populate_message(cls, data: Any) -> Any:
        if isinstance(data, dict):
            msg = data.get("message") or data.get("question")
            if msg is not None:
                data["message"] = str(msg).strip()
        return data


class PatientChatResponse(BaseModel):
    session_id: Optional[str] = "session-default"
    reply: str
    context_topic: Optional[str] = "general"
    context_used: Dict[str, Any] = Field(default_factory=dict)
    cited_sections: List[str] = Field(default_factory=list)
    grounded_facts: List[str] = Field(default_factory=list)
    citations: List[Dict[str, str]] = Field(default_factory=list)
    suggested_followups: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "PostVisit AI Assistant explains documented clinical records for your information. "
        "It does not replace your physician's clinical judgment. For new symptoms or changes in medication, consult your doctor."
    )


class ChatMessageItem(BaseModel):
    id: str
    role: str
    content: str
    context_topic: Optional[str] = None
    citations: List[Dict[str, str]] = Field(default_factory=list)
    created_at: str


# -------------------------------------------------------------
# 10. Patient Voice Recording Transcribe
# -------------------------------------------------------------
class PatientVoiceTranscribeResponse(BaseModel):
    voice_note_id: str
    patient_id: Optional[str] = None
    transcription: str
    transcript_text: Optional[str] = None
    language: str = "ta"
    duration_seconds: float = 0.0
    status: str = "transcribed"
    review_status: str = "patient_draft"
    is_patient_provided: bool = True
    disclaimer: str = (
        "This transcript is patient-provided voice input for personal review or inquiry. "
        "It is not part of the official doctor-approved medical record until clinically verified."
    )
