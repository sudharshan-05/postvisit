"""
PostVisit AI - Stage 4: Patient Summary Pydantic Schemas
Defines structured patient-friendly clinical summaries, multilingual instructions,
review requests, and audit models conforming strictly to clinical safety boundaries.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class PatientMedicationInstruction(BaseModel):
    """
    Patient-friendly instruction for a single prescribed medication.
    Preserves exact approved medical record drug names, strengths, timings, and durations.
    """
    medication_name: str = Field(description="Exact brand or generic drug name as prescribed by doctor")
    strength: Optional[str] = Field(default=None, description="Exact dosage strength with units (e.g., '650 mg')")
    dose: Optional[str] = Field(default=None, description="Dose quantity per intake (e.g., '1 tablet')")
    route: Optional[str] = Field(default=None, description="Route of administration (e.g., 'oral')")
    frequency: Optional[str] = Field(default=None, description="Intake frequency (e.g., 'twice daily')")
    timing: Optional[str] = Field(default=None, description="Timing relative to meals (e.g., 'after food')")
    duration: Optional[str] = Field(default=None, description="Treatment duration (e.g., '5 days')")
    instructions: str = Field(description="Clear, compassionate plain-language guidance in the target language")
    source_index: Optional[int] = Field(default=None, description="Index of corresponding item in approved medical record")


class PatientTestItem(BaseModel):
    """
    Diagnostic, imaging, or laboratory test ordered by physician.
    """
    test_name: str = Field(description="Name of test (e.g., 'Blood Sugar', 'ECG')")
    timing: Optional[str] = Field(default=None, description="When the test should be performed")
    instructions: Optional[str] = Field(default=None, description="Pre-test clinical preparation (e.g., 'fasting required')")


class PatientSummaryContent(BaseModel):
    """
    Core structured content of the patient-facing summary.
    Excludes independent diagnoses or unauthorized advice.
    """
    overview: str = Field(description="Simple, conversational summary of what was discussed during the visit")
    symptoms_discussed: List[str] = Field(default_factory=list, description="Complaints or symptoms discussed")
    medications: List[PatientMedicationInstruction] = Field(default_factory=list, description="Prescribed medications with patient instructions")
    tests_ordered: List[PatientTestItem] = Field(default_factory=list, description="Tests ordered by the doctor")
    self_care_instructions: List[str] = Field(default_factory=list, description="Dietary, hydration, and lifestyle guidance given by doctor")
    warnings_and_precautions: List[str] = Field(default_factory=list, description="Emergency red flags and danger signs")
    when_to_visit_again: Optional[str] = Field(default=None, description="Follow-up timeline and consultation review instructions")
    unspecified_or_uncertain_info: List[str] = Field(default_factory=list, description="Explicit statement of details not specified by doctor")


class PatientSummaryRecord(BaseModel):
    """
    Full persisted patient summary model with review metadata and audit tracking.
    """
    id: str = Field(description="Unique summary UUID")
    consultation_id: str = Field(description="Associated consultation UUID")
    language: str = Field(default="en", description="Target language code: 'en', 'ta', 'kn', 'te', 'ml'")
    version: int = Field(default=1, description="Version number of summary")
    status: str = Field(default="PENDING_SUMMARY_REVIEW", description="Workflow state")
    generated_summary: PatientSummaryContent = Field(description="Original LLM-generated patient summary")
    reviewed_summary: Optional[PatientSummaryContent] = Field(default=None, description="Doctor-amended version if modified")
    reviewed_by: Optional[str] = Field(default=None, description="Name or ID of reviewing physician")
    reviewed_at: Optional[str] = Field(default=None, description="ISO timestamp of doctor review")
    review_decision: Optional[str] = Field(default=None, description="'approved', 'rejected', or 'amended'")
    review_notes: Optional[str] = Field(default=None, description="Doctor clinical remarks")
    source_record_hash: Optional[str] = Field(default=None, description="SHA-256 hash of source approved medical JSON")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key for generation request")
    agent_version: str = Field(default="1.0.0")
    prompt_version: str = Field(default="1.0.0")
    created_at: str
    updated_at: str

    @property
    def is_approved(self) -> bool:
        return self.status == "SUMMARY_APPROVED"

    @property
    def effective_summary(self) -> PatientSummaryContent:
        """Returns the doctor-reviewed summary if amended; otherwise the generated summary."""
        return self.reviewed_summary if self.reviewed_summary is not None else self.generated_summary


class PatientSummaryCreateRequest(BaseModel):
    """
    Request payload to generate a patient summary.
    """
    target_language: str = Field(default="en", description="Target language ('en', 'ta', 'kn', 'te', 'ml')")
    idempotency_key: Optional[str] = Field(default=None, description="Optional key to prevent duplicate runs")


class PatientSummaryReviewRequest(BaseModel):
    """
    Request payload for physician approval, rejection, or clinical amendment.
    """
    doctor_name: str = Field(description="Name or ID of reviewing physician")
    decision: str = Field(default="approved", description="'approved', 'rejected', or 'amended'")
    notes: Optional[str] = Field(default=None, description="Clinical verification remarks")
    corrected_summary: Optional[PatientSummaryContent] = Field(default=None, description="Amended summary content if modified")

    @field_validator("decision")
    @classmethod
    def normalize_decision(cls, v: str) -> str:
        mapping = {
            "approve": "approved",
            "approved": "approved",
            "amend": "amended",
            "amended": "amended",
            "reject": "rejected",
            "rejected": "rejected"
        }
        val = str(v).lower().strip()
        if val not in mapping:
            raise ValueError("Decision must be 'approved', 'rejected', or 'amended'.")
        return mapping[val]


class PatientSummaryAuditItem(BaseModel):
    """
    Audit log item tracking all generation and review actions.
    """
    id: str
    summary_id: str
    consultation_id: str
    action: str  # 'generated', 'validated', 'reviewed', 'approved', 'rejected', 'amended'
    actor_id: str
    actor_role: str  # 'doctor', 'patient', 'system', 'agent'
    notes: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    created_at: str
