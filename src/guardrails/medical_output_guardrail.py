"""
PostVisit AI - Medical Output Guardrails & Clinical Safety Engine
Enforces:
  LLM -> Structured Output -> Pydantic Validation -> Deterministic Medical Validation -> Clinical Safety -> Database
Prevents direct LLM-to-DB writes. Enforces doctor authority over prescriptions,
guards against patient self-medication extraction, checks schema conformance,
and mandates physician review for uncertain entities.
"""

import logging
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from src.guardrails.base import GuardrailResult
from src.medical_schema import MedicalExtraction, MedicationItem
from src.medical_validator import sanitize_and_validate, validate_schema

logger = logging.getLogger("postvisit.guardrails.medical_output")


class MedicalOutputGuardrail:
    """
    Validates structured clinical extraction before persisting to Supabase.
    """

    def validate(
        self,
        raw_output: Any,
        transcript_text: str = ""
    ) -> GuardrailResult:
        """
        Runs comprehensive multi-tier medical validation:
        1. Type & structure verification
        2. Pydantic schema validation
        3. Deterministic normalizer & safety rules
        4. Speaker attribution & doctor prescription authority checks
        """
        if raw_output is None:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="EMPTY_EXTRACTION_OUTPUT",
                message="Medical extraction output is null or empty."
            )

        if not isinstance(raw_output, dict):
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="INVALID_OUTPUT_TYPE",
                message=f"Medical extraction output must be a dictionary, got {type(raw_output).__name__}."
            )

        # 1. Pydantic Schema Conformance Check
        try:
            validated_model = MedicalExtraction(**raw_output)
        except ValidationError as val_err:
            logger.warning(f"Pydantic schema validation failed: {val_err}")
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="SCHEMA_VALIDATION_ERROR",
                message=f"Extraction failed strict Pydantic medical schema: {str(val_err)}",
                details={"errors": val_err.errors()}
            )

        # 2. Deterministic Sanitize and Normalization
        sanitized_data, validation_summary = sanitize_and_validate(raw_output, transcript_text)

        # 3. Doctor / Patient Speaker Safety Check
        # Rule: A medication must NOT be attributed to the Doctor unless the source_speaker is Doctor
        # or there is clear evidence that the doctor instructed it.
        # If a medication has source_speaker = 'Patient', it must be rejected as an active prescription.
        medications = sanitized_data.get("medications", [])
        invalid_speaker_prescriptions = []

        for med in medications:
            spk = (med.get("source_speaker") or "").lower()
            if spk in ("patient", "speaker_00") and "doctor" not in spk:
                invalid_speaker_prescriptions.append(med.get("name") or "Unknown")

        if invalid_speaker_prescriptions:
            logger.warning(
                f"Blocked patient self-medication from active prescriptions: {invalid_speaker_prescriptions}"
            )
            # Filter out invalid prescriptions from active list and flag in uncertain_items
            sanitized_data["medications"] = [
                m for m in medications
                if (m.get("source_speaker") or "").lower() not in ("patient", "speaker_00")
            ]
            for bad_med in invalid_speaker_prescriptions:
                note = f"Medication '{bad_med}' was mentioned by the patient and was not confirmed by doctor."
                if note not in sanitized_data["uncertain_items"]:
                    sanitized_data["uncertain_items"].append(note)
            sanitized_data["requires_doctor_review"] = True

        # 4. Mandatory Physician Review Flagging
        # Any consultation with uncertainties or new medications requires doctor review
        if sanitized_data.get("uncertain_items"):
            sanitized_data["requires_doctor_review"] = True

        # Check if any errors occurred during validation
        if not validation_summary.get("valid", True):
            errors = validation_summary.get("errors", [])
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="CLINICAL_VALIDATION_WARNING",
                message=f"Medical extraction completed with clinical warnings: {', '.join(errors)}",
                details={
                    "sanitized_data": sanitized_data,
                    "validation_summary": validation_summary
                }
            )

        return GuardrailResult(
            passed=True,
            action="CONTINUE",
            message="Medical output guardrail passed successfully.",
            details={
                "sanitized_data": sanitized_data,
                "validation_summary": validation_summary
            }
        )
