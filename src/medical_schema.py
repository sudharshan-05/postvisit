"""
PostVisit AI - Milestone 2: Medical Information Output Schema
Defines the strict Pydantic data models and schema constraints.
Defines the STRUCTURE of the output, NOT the allowed vocabulary.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MedicationItem(BaseModel):
    """
    Medication entity explicitly mentioned in consultation.
    All fields default to None/null when not explicitly stated in transcript.
    """
    name: Optional[str] = Field(
        default=None,
        description="Medication name (brand or generic). Null if not explicitly named."
    )
    strength: Optional[str] = Field(
        default=None,
        description="Strength with units (e.g., '500 mg', '5 ml', '50 mcg'). Null if not stated."
    )
    dose: Optional[str] = Field(
        default=None,
        description="Dose quantity per intake (e.g., '1 tablet', '2 puffs', '1 spoon'). Null if not stated."
    )
    route: Optional[str] = Field(
        default=None,
        description="Route of administration (e.g., 'oral', 'inhalation', 'topical'). Null if not stated."
    )
    frequency: Optional[str] = Field(
        default=None,
        description="Intake frequency (e.g., 'once daily', 'twice daily', 'as needed / PRN'). Null if not stated."
    )
    specific_schedule: Optional[List[str]] = Field(
        default=None,
        description="Explicit daily times of intake (e.g., ['morning', 'night']). Null if only general frequency stated."
    )
    timing: Optional[str] = Field(
        default=None,
        description="Timing relative to meals or time of day (e.g., 'after dinner', 'before breakfast'). Null if not stated."
    )
    duration: Optional[str] = Field(
        default=None,
        description="Duration of treatment (e.g., '30 days', '5 days', 'continuous'). Null if not stated."
    )
    source_speaker: Optional[str] = Field(
        default=None,
        description="Attributed speaker who prescribed/stated the medication (e.g. 'Doctor' / 'SPEAKER_01')."
    )
    source_text: Optional[str] = Field(
        default=None,
        description="Verbatim transcript sentence containing the prescription evidence."
    )
    source_start: Optional[float] = Field(
        default=None,
        description="Start timestamp in seconds."
    )
    source_end: Optional[float] = Field(
        default=None,
        description="End timestamp in seconds."
    )


class TestItem(BaseModel):
    """
    Diagnostic, imaging, or laboratory test explicitly mentioned.
    """
    name: Optional[str] = Field(
        default=None,
        description="Test name (e.g., 'HbA1c', 'ECG', 'Blood Sugar'). Null if unspecified."
    )
    timing: Optional[str] = Field(
        default=None,
        description="Timeline or schedule for test (e.g., 'before next visit', 'immediately'). Null if not stated."
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Pre-test clinical instructions (e.g., 'fasting required'). Null if not stated."
    )


class FollowUpItem(BaseModel):
    """
    Follow-up appointment timeline and doctor instructions.
    """
    time: Optional[str] = Field(
        default=None,
        description="Scheduled follow-up period (e.g., '1 month', '2 weeks', 'next visit'). Null if not stated."
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Instructions for follow-up consultation. Null if not stated."
    )


class MedicalExtraction(BaseModel):
    """
    Root structured clinical output conforming strictly to Milestone 2 requirements.
    Zero hallucination: only information explicitly supported by transcript is extracted.
    """
    medications: List[MedicationItem] = Field(
        default_factory=list,
        description="List of medications mentioned explicitly."
    )
    tests: List[TestItem] = Field(
        default_factory=list,
        description="List of diagnostic or lab tests ordered."
    )
    instructions: List[str] = Field(
        default_factory=list,
        description="Clinical, dietary, and lifestyle advice explicitly given by doctor."
    )
    follow_up: FollowUpItem = Field(
        default_factory=FollowUpItem,
        description="Follow-up consultation instructions and timeline."
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Red flag symptoms or emergency warnings requiring immediate care."
    )
    symptoms_mentioned: List[str] = Field(
        default_factory=list,
        description="Symptoms or complaints explicitly mentioned by patient/doctor."
    )
    uncertain_items: List[str] = Field(
        default_factory=list,
        description="Ambiguities, missing critical dosage/timing, or generic references flagged for doctor review."
    )
    requires_doctor_review: bool = Field(
        default=True,
        description="Always true when uncertain items or missing critical attributes exist."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Returns standard python dict with None/null values preserved."""
        return self.model_dump()


def get_empty_schema_dict() -> Dict[str, Any]:
    """Returns a fresh empty dictionary conforming to the required schema."""
    return MedicalExtraction().to_dict()
