"""
PostVisit AI - Consultation Processing Request and Response Schemas
Provides strict Pydantic response models preserving clinical evidence and source attribution.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

# Re-use existing medical items to guarantee full attribute and evidence preservation
from src.medical_schema import MedicationItem, TestItem, FollowUpItem


class InputMetadata(BaseModel):
    """Metadata regarding the input consultation media container."""
    filename: str = Field(..., description="Uploaded file name")
    media_type: str = Field(..., description="MIME content type of the media file")
    duration_seconds: float = Field(..., description="Audio duration in seconds")


class TranscriptTurn(BaseModel):
    """Individual speaker turn in the clinical dialogue."""
    start: float = Field(..., description="Start timestamp of the speech turn in seconds")
    end: float = Field(..., description="End timestamp of the speech turn in seconds")
    speaker: str = Field(..., description="Role attribution ('Doctor' or 'Patient')")
    text: str = Field(..., description="Transcribed speech in original language")


class MedicalRecord(BaseModel):
    """Structured clinical record extracted from the consultation."""
    medications: List[MedicationItem] = Field(
        default_factory=list,
        description="Prescribed medications with dosing, schedule, and source evidence"
    )
    tests: List[TestItem] = Field(
        default_factory=list,
        description="Ordered diagnostic tests and investigations"
    )
    instructions: List[str] = Field(
        default_factory=list,
        description="Clinical advice, dietary guidance, or lifestyle modifications"
    )
    follow_up: FollowUpItem = Field(
        default_factory=FollowUpItem,
        description="Follow-up consultation timeline and instructions"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Clinical warnings, dosage safety caps, or emergency red flags"
    )
    symptoms_mentioned: List[str] = Field(
        default_factory=list,
        description="Symptoms and complaints reported by the patient"
    )
    uncertain_items: List[str] = Field(
        default_factory=list,
        description="Ambiguities or unconfirmed items flagged for physician review"
    )
    requires_doctor_review: bool = Field(
        default=True,
        description="Physician verification required before patient dispatch"
    )


class ValidationSummary(BaseModel):
    """Deterministic validation results for the clinical extraction."""
    status: str = Field(default="valid", description="Overall validation status: 'valid' or 'invalid'")
    errors: List[str] = Field(default_factory=list, description="Validation error messages if any")
    warnings: List[str] = Field(default_factory=list, description="Clinical or schema warning messages")


class ConsultationResponse(BaseModel):
    """Standardized root response model for processed consultations."""
    status: str = Field(default="completed", description="Lifecycle status of consultation processing")
    consultation_id: Optional[str] = Field(default=None, description="Unique consultation UUID assigned by persistence layer")
    media_storage_path: Optional[str] = Field(default=None, description="Path to original media file in Supabase Storage")
    input: InputMetadata = Field(..., description="Input media metadata")
    transcript: List[TranscriptTurn] = Field(..., description="Speaker-attributed dialogue turns")
    medical_record: MedicalRecord = Field(..., description="Structured clinical findings and prescriptions")
    validation: ValidationSummary = Field(..., description="Schema and clinical validation summary")


class ConsultationListItem(BaseModel):
    """Compact summary item for consultation list views."""
    consultation_id: str = Field(..., description="Unique consultation UUID")
    status: str = Field(..., description="Processing status ('processing', 'completed', 'failed')")
    original_filename: Optional[str] = Field(default=None, description="Original uploaded filename")
    media_type: Optional[str] = Field(default=None, description="MIME media type")
    duration_seconds: Optional[float] = Field(default=None, description="Media duration in seconds")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp ISO-8601")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp ISO-8601")


class ConsultationListResponse(BaseModel):
    """List response model for consultation collections."""
    items: List[ConsultationListItem] = Field(default_factory=list, description="Array of consultation summaries")
    total: int = Field(default=0, description="Total number of consultation records")


class ErrorDetail(BaseModel):
    """Structured error payload details."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")


class ErrorResponse(BaseModel):
    """Standardized error envelope."""
    error: ErrorDetail = Field(..., description="Error detail object")


class ConsultationDetailResponse(BaseModel):
    """Full consultation detail model returned by GET /api/v1/consultations/{id}."""
    consultation_id: str = Field(..., description="Unique consultation UUID")
    status: str = Field(..., description="Processing lifecycle state: 'processing', 'completed', or 'failed'")
    input: Optional[InputMetadata] = Field(default=None, description="Input media metadata")
    media_storage_path: Optional[str] = Field(default=None, description="Storage bucket path for media")
    transcript: Optional[List[TranscriptTurn]] = Field(default=None, description="Dialogue transcript")
    medical_record: Optional[MedicalRecord] = Field(default=None, description="Clinical extraction record")
    validation: Optional[ValidationSummary] = Field(default=None, description="Validation summary")
    error: Optional[ErrorDetail] = Field(default=None, description="Error detail if consultation status is 'failed'")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last updated timestamp")


class HealthResponse(BaseModel):
    """Response model for API health check."""
    status: str = Field(default="ok", description="Service health state")
    service: str = Field(default="PostVisit AI API", description="Service identifier")
    version: str = Field(default="1.0.0", description="API semver")


class RootResponse(BaseModel):
    """Response model for API root endpoint."""
    name: str = Field(default="PostVisit AI", description="Service title")
    description: str = Field(default="Clinical consultation processing API", description="Brief description")
    version: str = Field(default="1.0.0", description="API semver")
    docs: str = Field(default="/docs", description="Interactive OpenAPI documentation path")
    health: str = Field(default="/health", description="Health check endpoint path")
