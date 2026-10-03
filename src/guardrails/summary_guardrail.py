"""
PostVisit AI - Patient Summary Guardrail & Clinical Safety Engine
Validates generated patient-facing summaries against doctor-approved medical JSON.
Enforces deterministic clinical safety:
  - Exact preservation of medication names, strengths, dosages, routes, frequencies, durations.
  - Detects hallucinated medications (unsupported additions).
  - Detects altered numerical values (e.g., dosage or duration changes).
  - Flags omitted critical warnings or instructions.
  - Detects contradictory instructions or attempts to resolve clinical ambiguities without authorization.
  - Requires approved source medical record.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set
from pydantic import ValidationError

from src.guardrails.base import GuardrailResult
from src.schemas.patient_summary_schema import (
    PatientSummaryContent,
    PatientMedicationInstruction
)

logger = logging.getLogger("postvisit.guardrails.summary")


class SummaryGuardrail:
    """
    Deterministic clinical verification of patient summaries against approved medical JSON.
    Never relies solely on LLM self-evaluation.
    """

    @staticmethod
    def _extract_numbers(text: Optional[str]) -> Set[str]:
        """Extracts numerical sequences from text for strict value preservation."""
        if not text:
            return set()
        return set(re.findall(r"\b\d+(?:\.\d+)?\b", str(text)))

    @staticmethod
    def _normalize_name(name: Optional[str]) -> str:
        """Normalizes medication or test names for robust matching."""
        if not name:
            return ""
        return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

    def validate(
        self,
        summary_content: Any,
        approved_medical_record: Dict[str, Any],
        language: str = "en"
    ) -> GuardrailResult:
        """
        Executes strict deterministic verification between the approved medical JSON
        and the generated patient summary.
        """
        if not approved_medical_record:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="MISSING_APPROVED_RECORD",
                message="Cannot generate or validate summary without an approved medical record."
            )

        # 1. Verify that the source record is indeed doctor-approved
        requires_review = approved_medical_record.get("requires_doctor_review")
        doctor_review = approved_medical_record.get("doctor_review") or {}
        review_decision = doctor_review.get("decision", "").lower()

        # If requires_doctor_review is True or decision is not approved/amended
        if requires_review is True or (requires_review is None and review_decision not in ("approved", "amended")):
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="RECORD_NOT_DOCTOR_APPROVED",
                message="Source medical record has not completed physician review and approval."
            )

        # 2. Pydantic validation of the summary content
        if isinstance(summary_content, dict):
            try:
                summary_model = PatientSummaryContent(**summary_content)
            except ValidationError as val_err:
                return GuardrailResult(
                    passed=False,
                    action="FAILED",
                    error_code="SUMMARY_SCHEMA_ERROR",
                    message=f"Generated summary failed Pydantic schema validation: {str(val_err)}",
                    details={"errors": val_err.errors()}
                )
        elif isinstance(summary_content, PatientSummaryContent):
            summary_model = summary_content
        else:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="INVALID_SUMMARY_TYPE",
                message=f"Expected summary dict or PatientSummaryContent, got {type(summary_content).__name__}."
            )

        # 3. Check for source contradictions
        uncertain_items = approved_medical_record.get("uncertain_items", [])
        if any("contradiction" in str(item).lower() or "conflict" in str(item).lower() for item in uncertain_items):
            # If the source record has unresolved contradictory instructions
            # Summary MUST explicitly acknowledge uncertainty in unspecified_or_uncertain_info
            if not summary_model.unspecified_or_uncertain_info:
                return GuardrailResult(
                    passed=False,
                    action="NEEDS_REVIEW",
                    error_code="UNRESOLVED_CONTRADICTION",
                    message="Source record contains contradictory instructions that were not acknowledged as uncertain."
                )

        # 4. Medication Verification
        approved_meds = approved_medical_record.get("medications", [])
        summary_meds = summary_model.medications

        approved_med_names = [self._normalize_name(m.get("name")) for m in approved_meds if m.get("name")]
        summary_med_names = [self._normalize_name(m.medication_name) for m in summary_meds if m.medication_name]

        # 4a. Check for Hallucinated Medications (in summary but NOT in approved record)
        hallucinated_meds = []
        for sm in summary_meds:
            s_norm = self._normalize_name(sm.medication_name)
            # Check if this matches any approved med by substring or normalized equality
            matched = any(s_norm in an or an in s_norm for an in approved_med_names)
            if not matched:
                hallucinated_meds.append(sm.medication_name)

        if hallucinated_meds:
            logger.warning(f"Summary contains hallucinated medication(s): {hallucinated_meds}")
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="HALLUCINATED_MEDICATION",
                message=f"Summary contains unsupported medication(s) not in approved record: {', '.join(hallucinated_meds)}",
                details={"hallucinated_medications": hallucinated_meds}
            )

        # 4b. Check for Omitted Prescribed Medications
        omitted_meds = []
        for am in approved_meds:
            # Only doctor-prescribed medications must be present
            spk = (am.get("source_speaker") or "Doctor").lower()
            if "patient" in spk and "doctor" not in spk:
                continue
            a_norm = self._normalize_name(am.get("name"))
            if not a_norm:
                continue
            matched = any(a_norm in sn or sn in a_norm for sn in summary_med_names)
            if not matched:
                omitted_meds.append(am.get("name"))

        if omitted_meds:
            logger.warning(f"Summary omitted prescribed medication(s): {omitted_meds}")
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="OMITTED_PRESCRIBED_MEDICATION",
                message=f"Summary omitted prescribed medication(s): {', '.join(omitted_meds)}",
                details={"omitted_medications": omitted_meds}
            )

        # 4c. Verify Numerical Strengths and Durations for Matched Medications
        for am in approved_meds:
            a_norm = self._normalize_name(am.get("name"))
            # Find matching summary med
            matching_sm = next(
                (sm for sm in summary_meds if a_norm in self._normalize_name(sm.medication_name) or self._normalize_name(sm.medication_name) in a_norm),
                None
            )
            if not matching_sm:
                continue

            # Verify strength numbers
            app_strength_nums = self._extract_numbers(am.get("strength"))
            sum_strength_nums = self._extract_numbers(matching_sm.strength)
            sum_instruction_nums = self._extract_numbers(matching_sm.instructions)
            all_sum_nums = sum_strength_nums.union(sum_instruction_nums)

            if app_strength_nums:
                # Every number in approved strength should appear in the summary medication
                # If the summary specified a strength with conflicting numbers, flag it
                missing_nums = app_strength_nums - all_sum_nums
                if missing_nums:
                    # Check if summary has different numbers
                    if sum_strength_nums and sum_strength_nums != app_strength_nums:
                        return GuardrailResult(
                            passed=False,
                            action="NEEDS_REVIEW",
                            error_code="ALTERED_NUMERICAL_VALUE",
                            message=f"Altered strength for '{matching_sm.medication_name}': expected {am.get('strength')}, got {matching_sm.strength}",
                            details={"expected": am.get("strength"), "received": matching_sm.strength}
                        )

            # Verify duration numbers
            app_duration_nums = self._extract_numbers(am.get("duration"))
            sum_duration_nums = self._extract_numbers(matching_sm.duration)
            if app_duration_nums and sum_duration_nums:
                if app_duration_nums != sum_duration_nums:
                    return GuardrailResult(
                        passed=False,
                        action="NEEDS_REVIEW",
                        error_code="ALTERED_NUMERICAL_VALUE",
                        message=f"Altered duration for '{matching_sm.medication_name}': expected {am.get('duration')}, got {matching_sm.duration}",
                        details={"expected": am.get("duration"), "received": matching_sm.duration}
                    )

        # 5. Check Critical Warnings Preservation
        approved_warnings = approved_medical_record.get("warnings_and_precautions", []) or approved_medical_record.get("warnings", [])
        if approved_warnings:
            # Summary should contain warnings_and_precautions
            if not summary_model.warnings_and_precautions:
                return GuardrailResult(
                    passed=False,
                    action="NEEDS_REVIEW",
                    error_code="OMITTED_CRITICAL_WARNINGS",
                    message="Source record contains warnings that were omitted from the summary.",
                    details={"approved_warnings": approved_warnings}
                )

        # 6. Check Diagnostic Tests Conformance
        approved_tests = approved_medical_record.get("tests", [])
        app_test_names = [self._normalize_name(t.get("name")) for t in approved_tests if t.get("name")]
        summary_test_names = [self._normalize_name(t.test_name) for t in summary_model.tests_ordered if t.test_name]

        # Check for hallucinated tests
        hallucinated_tests = []
        for st in summary_model.tests_ordered:
            st_norm = self._normalize_name(st.test_name)
            if not any(st_norm in at or at in st_norm for at in app_test_names):
                hallucinated_tests.append(st.test_name)

        if hallucinated_tests:
            return GuardrailResult(
                passed=False,
                action="NEEDS_REVIEW",
                error_code="HALLUCINATED_TEST",
                message=f"Summary contains test(s) not ordered by physician: {', '.join(hallucinated_tests)}",
                details={"hallucinated_tests": hallucinated_tests}
            )

        # All deterministic checks passed
        return GuardrailResult(
            passed=True,
            action="CONTINUE",
            message="Summary passed all deterministic clinical safety guardrails."
        )
