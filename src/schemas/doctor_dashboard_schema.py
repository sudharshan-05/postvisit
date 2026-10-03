"""
PostVisit AI - Stage 5B: Doctor Dashboard & Clinical Review Schemas
Defines models for:
- Doctor consultation list & filtering
- Patient clinical overview & previous visit history
- Doctor-side quick organizational summary
- Lab report review workflow (preserving patient submissions + storing doctor corrections)
- Clinical guideline cross-referencing & findings review (neutral non-punitive language)
- Doctor-side grounded Ask AI (source data, AI summary, guideline evidence, AI interpretation)
- Doctor voice recording confirmation workflow (transcribe -> edit -> confirm)
- Append-only clinical audit trail
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


# =============================================================================
# 1. Doctor Consultation List & Cards
# =============================================================================

class DoctorConsultationCard(BaseModel):
    """
    Authorized consultation card displayed in doctor review queues.
    Distinguishes: PROCESSING, PENDING REVIEW, NEEDS REVIEW, APPROVED, REJECTED, FAILED.
    """
    consultation_id: str = Field(description="Unique consultation identifier")
    patient_id: str = Field(description="Patient identifier (e.g. PT-89241)")
    patient_name: str = Field(description="Patient full name")
    consultation_date: str = Field(description="Date or timestamp of consultation")
    status: str = Field(
        description="High-level status: 'PROCESSING', 'PENDING REVIEW', 'NEEDS REVIEW', 'APPROVED', 'REJECTED', 'FAILED'"
    )
    processing_stage: str = Field(
        description="Detailed workflow stage (e.g. 'doctor_review', 'completed', 'extracting')"
    )
    summary_status: str = Field(
        description="Patient summary status: 'PENDING_SUMMARY_REVIEW', 'SUMMARY_APPROVED', 'SUMMARY_REJECTED', 'NEEDS_REVIEW', 'NOT_GENERATED'"
    )
    guideline_status: str = Field(
        description="Guideline status: 'COMPLETED', 'NO_RELEVANT_GUIDELINE', 'NOT_CONFIGURED', 'NEEDS_REVIEW', 'FAILED'"
    )
    lab_report_status: str = Field(
        default="NO_REPORTS",
        description="Lab report review status: 'REPORT_SUBMITTED', 'REPORT_PENDING_REVIEW', 'REPORT_REVIEWED', 'REPORT_NEEDS_CLARIFICATION', 'REPORT_REJECTED', 'NO_REPORTS'"
    )
    last_updated_at: str = Field(description="ISO timestamp of last activity")
    assigned_doctor: Optional[str] = Field(default=None, description="Assigned clinician identifier or name")
    chief_complaint: Optional[str] = Field(default=None, description="Primary clinical presentation")


class DoctorConsultationListResponse(BaseModel):
    """List response with aggregated operational metrics."""
    items: List[DoctorConsultationCard]
    total: int
    pending_review_count: int
    needs_attention_count: int
    completed_count: int
    processing_count: int


# =============================================================================
# 2. Patient Clinical Overview & Visit History
# =============================================================================

class PreviousVisitSummary(BaseModel):
    """Previous consultation summary for longitudinal clinical continuity."""
    consultation_id: str
    date: str
    reason_for_visit: str
    symptoms: List[str] = Field(default_factory=list)
    hpi: Optional[str] = None
    findings: List[str] = Field(default_factory=list)
    doctor_recommendations: List[str] = Field(default_factory=list)
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    tests: List[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
    approved_summary: Optional[str] = None


class PatientClinicalOverview(BaseModel):
    """
    Comprehensive structured overview for an authorized patient.
    Avoids long unformatted walls of text by organizing into distinct clinical domains.
    """
    patient_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    chronic_conditions: List[str] = Field(default_factory=list)
    last_visit: Optional[PreviousVisitSummary] = None
    visit_history: List[PreviousVisitSummary] = Field(default_factory=list)
    
    # Current consultation clinical sections
    consultation_id: Optional[str] = None
    consultation_date: Optional[str] = None
    reported_symptoms: List[str] = Field(default_factory=list)
    history_of_present_illness: Optional[str] = None
    clinical_findings: List[str] = Field(default_factory=list)
    vitals: Dict[str, Any] = Field(default_factory=dict)
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    tests_ordered: List[str] = Field(default_factory=list)
    doctor_recommendations: List[str] = Field(default_factory=list)
    follow_up_instructions: Optional[str] = None
    warnings_and_red_flags: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    
    # Attached contextual modules
    lab_reports: List[Dict[str, Any]] = Field(default_factory=list)
    guideline_findings: List[Dict[str, Any]] = Field(default_factory=list)
    patient_summary: Optional[Dict[str, Any]] = None
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# 3. Patient Quick Summary (Organizational overview with source link)
# =============================================================================

class DoctorQuickSummary(BaseModel):
    """
    Compact doctor-side quick summary for rapid orientation.
    Maintains strict link to the underlying source medical record.
    """
    consultation_id: str
    patient_id: str
    reason_for_consultation: str
    key_reported_symptoms: List[str] = Field(default_factory=list)
    relevant_hpi: Optional[str] = None
    important_clinical_findings: List[str] = Field(default_factory=list)
    current_medications: List[Dict[str, Any]] = Field(default_factory=list)
    tests_ordered: List[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
    previous_relevant_visit: Optional[str] = None
    relevant_lab_reports_summary: List[str] = Field(default_factory=list)
    source_record_url: str = Field(description="Direct URL/path to raw approved medical JSON")


# =============================================================================
# 4. Lab Report Management & Review
# =============================================================================

class DoctorLabReportItem(BaseModel):
    """
    Doctor-facing lab report item.
    Preserves original patient submission and tracks verified/corrected values separately.
    """
    id: str
    patient_id: str
    consultation_id: Optional[str] = None
    report_name: str
    test_name: str
    test_date: str
    
    # Original patient submission (IMMUTABLE)
    patient_value: Optional[str] = None
    patient_unit: Optional[str] = None
    reference_range: Optional[str] = None
    patient_notes: Optional[str] = None
    submission_timestamp: str
    entry_mode: str = "manual"  # 'manual' or 'upload'
    file_name: Optional[str] = None
    file_storage_path: Optional[str] = None
    is_ai_extracted: bool = False
    ai_extraction_label: Optional[str] = None  # 'AI-extracted — requires verification'
    
    # Doctor review & verification layer
    review_status: str = "REPORT_SUBMITTED"
    # Statuses: REPORT_SUBMITTED, REPORT_PROCESSING, REPORT_PENDING_REVIEW, REPORT_REVIEWED, REPORT_NEEDS_CLARIFICATION, REPORT_REJECTED
    verified_value: Optional[str] = None
    verified_unit: Optional[str] = None
    doctor_notes: Optional[str] = None
    clarification_request: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    
    # Provenance and contextual relation
    clinical_relevance_label: str = "Potentially relevant report identified for clinician review."


class DoctorLabReportReviewRequest(BaseModel):
    """Payload when a physician reviews or corrects a lab report."""
    decision: str = Field(
        description="'REPORT_REVIEWED', 'REPORT_NEEDS_CLARIFICATION', 'REPORT_REJECTED'"
    )
    verified_value: Optional[str] = Field(
        default=None,
        description="Clinician verified or corrected value (stored separately from patient value)"
    )
    verified_unit: Optional[str] = Field(default=None)
    doctor_notes: Optional[str] = Field(default=None, description="Doctor observations or clinical interpretation")
    clarification_request: Optional[str] = Field(default=None, description="Clarification message sent to patient")


# =============================================================================
# 5. Medical Guideline Cross-Reference
# =============================================================================

class DoctorGuidelineFinding(BaseModel):
    """
    Structured guideline finding with authoritative provenance.
    Uses neutral, respectful phrasing ('Potential discrepancy for clinician review').
    """
    id: str
    consultation_id: str
    finding_title: str
    category: str  # 'dosage_consideration', 'monitoring_test_recommendation', 'safety_precaution', 'lifestyle_therapy', 'follow_up_timeline'
    severity: str = "advisory"  # 'info', 'advisory', 'warning'
    why_flagged: str = Field(
        default="Potential discrepancy for clinician review",
        description="Objective rationale without accusing clinician of errors"
    )
    clinical_prompt: str
    
    # Full guideline provenance
    guideline_id: str
    guideline_title: str
    publishing_org: str
    topic: str
    version: Optional[str] = None
    publication_date: Optional[str] = None
    section: Optional[str] = None
    excerpt: str
    source_url: Optional[str] = None
    retrieval_timestamp: str
    
    # Doctor review decision
    doctor_decision: Optional[str] = Field(
        default=None,
        description="'relevant', 'not_relevant', 'review_later', 'add_note'"
    )
    doctor_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


class DoctorGuidelineReviewRequest(BaseModel):
    """Doctor decision on a guideline finding."""
    decision: str = Field(description="'relevant', 'not_relevant', 'review_later', 'add_note'")
    doctor_notes: Optional[str] = Field(default=None, description="Physician clinical remarks")


# =============================================================================
# 6. Doctor Grounded Ask AI
# =============================================================================

class DoctorAskAIRequest(BaseModel):
    """Physician query to Ask AI decision support."""
    consultation_id: str
    query: str
    context_type: str = Field(
        default="visit",
        description="'visit', 'previous_visits', 'lab_report', 'medication', 'guideline'"
    )


class DoctorAskAIResponse(BaseModel):
    """
    Grounded clinical response clearly distinguishing source data, summary,
    guideline evidence, and non-authoritative AI interpretation.
    """
    consultation_id: str
    query: str
    source_data: str = Field(description="Verified clinical facts from source record")
    ai_summary: str = Field(description="Concise organizational synthesis")
    guideline_evidence: str = Field(description="Exact retrieved guideline quotes and citations")
    ai_interpretation: str = Field(description="Decision-support guidance, explicitly marked non-prescriptive")
    disclaimer: str = Field(
        default="Clinical decision-support only. Doctor remains the final clinical authority."
    )


# =============================================================================
# 7. Doctor Voice Recording Workflow
# =============================================================================

class DoctorVoiceTranscribeResponse(BaseModel):
    """Generated transcript presented to the doctor for mandatory verification."""
    draft_id: str
    transcript_text: str
    confidence: float
    status: str = "awaiting_doctor_confirmation"
    note: str = "Raw transcription requires clinician review and confirmation before joining medical record."


class DoctorVoiceConfirmRequest(BaseModel):
    """Confirmed doctor voice note payload."""
    draft_id: Optional[str] = None
    consultation_id: str
    final_note_text: str = Field(description="Clinician-edited and confirmed text")
    category: str = Field(
        default="clinical_observation",
        description="'clinical_observation', 'follow_up_instruction', 'additional_note', 'summary_correction'"
    )
    is_confirmed: bool = Field(
        default=True,
        description="Explicit doctor confirmation flag"
    )


class DoctorVoiceConfirmResponse(BaseModel):
    note_id: str
    consultation_id: str
    final_note_text: str
    category: str
    confirmed_by: str
    confirmed_at: str
    status: str = "confirmed"


# =============================================================================
# 8. Clinical Timeline & Audit Trail
# =============================================================================

class ConsultationTimelineStep(BaseModel):
    step_key: str
    title: str
    status: str  # 'completed', 'in_progress', 'pending', 'needs_review', 'failed', 'unavailable'
    details: Optional[str] = None
    completed_at: Optional[str] = None


class ConsultationTimelineResponse(BaseModel):
    consultation_id: str
    overall_status: str
    steps: List[ConsultationTimelineStep]


class ClinicalAuditTrailItem(BaseModel):
    id: str
    consultation_id: str
    event_type: str
    actor_id: str
    actor_role: str
    timestamp: str
    action_description: str
    details: Dict[str, Any] = Field(default_factory=dict)
