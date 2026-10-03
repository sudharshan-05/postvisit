"""
PostVisit AI - Stage 5: Medical Guideline Cross-Referencing Schemas
Defines structured clinical decision-support models, evidence provenance,
guideline findings, and physician review requests.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GuidelineEvidenceItem(BaseModel):
    """
    Evidence passage retrieved from an authoritative clinical guideline.
    Provides complete provenance: publishing org, document title, section, and URL.
    """
    guideline_id: str = Field(description="Unique ID of guideline source (e.g. 'icmr-diabetes-2022')")
    guideline_title: str = Field(description="Formal title of guideline document")
    publishing_org: str = Field(description="Publishing authority (e.g. 'Indian Council of Medical Research (ICMR)')")
    topic: str = Field(description="Clinical topic or disease area")
    section: Optional[str] = Field(default=None, description="Specific chapter, section or page reference")
    excerpt: str = Field(description="Exact excerpt or verbatim guidance from authoritative source")
    source_url: Optional[str] = Field(default=None, description="Direct URL to published guideline or portal")
    publication_date: Optional[str] = Field(default=None, description="Publication date or revision year")
    retrieval_timestamp: str = Field(description="ISO timestamp when evidence was retrieved")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Relevance confidence score")


class GuidelineFindingItem(BaseModel):
    """
    Individual decision-support finding comparing documented care against guideline evidence.
    Framed strictly as review prompts for the treating physician.
    """
    id: str = Field(description="Unique finding identifier")
    category: str = Field(
        description="Category: 'dosage_consideration', 'monitoring_test_recommendation', 'safety_precaution', 'lifestyle_therapy', 'follow_up_timeline'"
    )
    severity: str = Field(default="info", description="Severity level: 'info', 'advisory', 'warning'")
    clinical_prompt: str = Field(description="Objective, respectful decision-support prompt for the doctor")
    target_entity: Optional[str] = Field(default=None, description="Clinical entity involved (e.g., 'Metformin', 'Blood Sugar')")
    evidence: GuidelineEvidenceItem = Field(description="Attributed evidence provenance from guideline")
    status: str = Field(default="pending_review", description="'pending_review', 'acknowledged', 'dismissed', 'amended'")
    doctor_decision: Optional[str] = Field(default=None, description="'acknowledged', 'dismissed', or 'amended'")
    doctor_notes: Optional[str] = Field(default=None, description="Physician remarks on this guideline finding")


class GuidelineCrossReferenceResult(BaseModel):
    """
    Complete outcome of guideline cross-referencing for a consultation.
    """
    id: str = Field(description="Unique evaluation run UUID")
    consultation_id: str = Field(description="Associated consultation UUID")
    medical_record_hash: Optional[str] = Field(default=None, description="Hash of evaluated medical JSON")
    status: str = Field(
        default="COMPLETED_NO_FINDINGS",
        description="Status: 'COMPLETED_WITH_FINDINGS', 'COMPLETED_NO_FINDINGS', 'NO_VERIFIED_SOURCE', 'NOT_CONFIGURED', 'FAILED', 'NEEDS_REVIEW'"
    )
    guidelines_evaluated: List[str] = Field(default_factory=list, description="List of guideline IDs queried")
    findings: List[GuidelineFindingItem] = Field(default_factory=list, description="Identified guideline comparison findings")
    agent_version: str = Field(default="1.0.0")
    execution_time_sec: float = Field(default=0.0)
    notes: Optional[str] = Field(default=None)
    created_at: str
    updated_at: str


class GuidelineDoctorReviewRequest(BaseModel):
    """
    Request model for a doctor reviewing, acknowledging, or dismissing a guideline finding.
    """
    doctor_name: str = Field(description="Name or ID of reviewing physician")
    finding_id: str = Field(description="Identifier of the guideline finding")
    decision: str = Field(default="acknowledged", description="'acknowledged', 'dismissed', or 'amended'")
    notes: Optional[str] = Field(default=None, description="Clinical verification remarks")


class WorkflowProgressStep(BaseModel):
    """
    Real-time workflow progress item for UI tracking.
    """
    step_id: str
    title: str
    description: str
    status: str  # 'pending', 'running', 'completed', 'failed', 'needs_review', 'not_configured', 'not_applicable'
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_sec: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class WorkflowProgressResponse(BaseModel):
    """
    Authoritative workflow progress payload consumed by the real-time processing UI.
    """
    consultation_id: str
    status: str
    current_step: Optional[str] = None
    elapsed_time_sec: float
    total_steps: int
    completed_steps: int
    is_terminal: bool
    can_patient_view_summary: bool
    steps: List[WorkflowProgressStep]
