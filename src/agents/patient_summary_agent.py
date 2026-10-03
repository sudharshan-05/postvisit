"""
PostVisit AI - Patient Summary Agent
Converts doctor-approved medical JSON into plain-language, compassionate,
patient-friendly summaries. Supports multilingual generation (English 'en', Tamil 'ta',
extensible to Kannada 'kn', Telugu 'te', Malayalam 'ml').
Adheres strictly to clinical safety:
  - Never invents diagnoses or prescribes medications.
  - Preserves exact drug names, strengths, dosages, schedules, and durations.
  - Translates instructions into conversational, culturally sensitive phrasing.
  - Retains source JSON as single source of truth.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import ValidationError

from src.agents.base import BaseAgent, AgentResult, WorkflowContext, RetryPolicy
from src.schemas.patient_summary_schema import (
    PatientSummaryContent,
    PatientMedicationInstruction,
    PatientTestItem
)
from src.llm_client import LLMClient

logger = logging.getLogger("postvisit.agents.patient_summary")

LANGUAGE_NAMES = {
    "en": "English",
    "ta": "Tamil (தமிழ்)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "te": "Telugu (తెలుగు)",
    "ml": "Malayalam (മലയാളം)"
}


class PatientSummaryAgent(BaseAgent):
    """
    AI Agent that transforms doctor-approved structured clinical records
    into simple, easily understandable patient-facing discharge summaries.
    """

    name: str = "patient_summary"
    version: str = "1.0.0"
    description: str = (
        "Generates patient-friendly medical summaries in English, Tamil, and other Indian languages "
        "from physician-approved medical JSON."
    )
    output_schema = PatientSummaryContent
    permissions = ["read_medical_record", "generate_patient_summary"]
    timeout_seconds = 45.0
    retry_policy = RetryPolicy(
        max_attempts=3,
        initial_delay_sec=1.0,
        backoff_factor=2.0,
        retryable_exceptions=("TimeoutError", "ConnectionError", "RuntimeError", "Exception")
    )

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_client = llm_client

    def _get_llm_client(self) -> Optional[LLMClient]:
        if self._llm_client is None:
            try:
                self._llm_client = LLMClient()
            except Exception as e:
                logger.warning(f"PatientSummaryAgent: Could not initialize live LLMClient ({e}). Will use fallback.")
                self._llm_client = None
        return self._llm_client

    def _build_system_prompt(self, target_lang: str) -> str:
        lang_label = LANGUAGE_NAMES.get(target_lang, target_lang)
        return (
            f"You are a clinical communication assistant for PostVisit AI.\n"
            f"Your role is to translate a doctor-approved medical consultation record into a clear, "
            f"compassionate, easy-to-understand summary for the patient in {lang_label}.\n\n"
            f"CLINICAL SAFETY MANDATES:\n"
            f"1. You must ONLY use the information provided in the approved medical record.\n"
            f"2. NEVER invent, assume, or infer any new diagnosis, symptom, test, or treatment.\n"
            f"3. PRESERVE exact medication names, numerical strengths, dosages, routes, frequencies, and durations.\n"
            f"   DO NOT alter any number, unit, or drug name.\n"
            f"4. For Tamil ('ta'): Write natural, empathetic, conversational Tamil. Keep medication names "
            f"   in familiar English/Latin script (or clearly transliterated) to prevent dangerous pharmacy confusion.\n"
            f"5. Explicitly state any details that the doctor did NOT specify in 'unspecified_or_uncertain_info'.\n"
            f"6. Include all warnings, red flags, and follow-up timing mentioned by the doctor.\n"
            f"7. Return ONLY valid JSON matching the required schema.\n"
        )

    def _build_user_prompt(self, approved_record: Dict[str, Any], target_lang: str) -> str:
        lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        record_json = json.dumps(approved_record, indent=2, ensure_ascii=False)

        return (
            f"Please generate a patient-facing summary in {lang_name} for the following approved medical record:\n\n"
            f"APPROVED MEDICAL RECORD:\n"
            f"```json\n{record_json}\n```\n\n"
            f"Return a single JSON object with the following schema:\n"
            f"{{\n"
            f'  "overview": "Clear 2-3 sentence overview of what was discussed during your visit",\n'
            f'  "symptoms_discussed": ["List of symptoms you reported"],\n'
            f'  "medications": [\n'
            f"    {{\n"
            f'      "medication_name": "Exact medication name",\n'
            f'      "strength": "Exact strength (e.g. 650 mg)",\n'
            f'      "dose": "Dose (e.g. 1 tablet)",\n'
            f'      "route": "Route (e.g. oral)",\n'
            f'      "frequency": "Frequency (e.g. twice daily)",\n'
            f'      "timing": "Timing (e.g. after food)",\n'
            f'      "duration": "Duration (e.g. 5 days)",\n'
            f'      "instructions": "Simple explanation of how and when to take this medicine",\n'
            f'      "source_index": 0\n'
            f"    }}\n"
            f"  ],\n"
            f'  "tests_ordered": [\n'
            f"    {{\n"
            f'      "test_name": "Exact test name",\n'
            f'      "timing": "When to do it",\n'
            f'      "instructions": "Preparation instructions"\n'
            f"    }}\n"
            f"  ],\n"
            f'  "self_care_instructions": ["Dietary, rest, or lifestyle advice given by doctor"],\n'
            f'  "warnings_and_precautions": ["Danger signs, red flags, or side effects warned about"],\n'
            f'  "when_to_visit_again": "Follow-up schedule or when to return",\n'
            f'  "unspecified_or_uncertain_info": ["Details the doctor did not specify"]\n'
            f"}}\n"
        )

    def _generate_fallback_summary(
        self,
        approved_record: Dict[str, Any],
        target_lang: str
    ) -> Dict[str, Any]:
        """
        Deterministic, rule-based patient summary generator for offline tests or when LLM is unavailable.
        Ensures exact preservation of medication names, strengths, timings, and durations.
        """
        is_tamil = target_lang == "ta"

        # Overview
        symptoms = approved_record.get("symptoms", [])
        if is_tamil:
            overview = "உங்கள் மருத்துவ சந்திப்பில் விவாதிக்கப்பட்ட முக்கிய தகவல்கள் கீழே கொடுக்கப்பட்டுள்ளன."
            if symptoms:
                overview += f" நீங்கள் தெரிவித்த அறிகுறிகள்: {', '.join(symptoms)}."
        else:
            overview = "Here is a simple summary of what the doctor discussed during your consultation."
            if symptoms:
                overview += f" The symptoms discussed include: {', '.join(symptoms)}."

        # Medications
        med_list = []
        for idx, med in enumerate(approved_record.get("medications", [])):
            name = med.get("name") or "Medication"
            strength = med.get("strength")
            dose = med.get("dose")
            route = med.get("route")
            frequency = med.get("frequency")
            timing = med.get("timing")
            duration = med.get("duration")

            if is_tamil:
                inst_parts = [f"{name}"]
                if strength:
                    inst_parts.append(f"({strength})")
                if dose:
                    inst_parts.append(f"{dose}")
                if frequency:
                    inst_parts.append(f"{frequency}")
                if timing:
                    inst_parts.append(f"{timing} எடுத்துக்கொள்ளவும்")
                else:
                    inst_parts.append("எடுத்துக்கொள்ளவும்")
                if duration:
                    inst_parts.append(f"({duration})")
                instructions = " ".join(inst_parts)
            else:
                inst_parts = [f"Take {name}"]
                if strength:
                    inst_parts.append(f"({strength})")
                if dose:
                    inst_parts.append(f"- {dose}")
                if frequency:
                    inst_parts.append(f"{frequency}")
                if timing:
                    inst_parts.append(f"{timing}")
                if duration:
                    inst_parts.append(f"for {duration}")
                instructions = " ".join(inst_parts) + "."

            med_list.append({
                "medication_name": name,
                "strength": strength,
                "dose": dose,
                "route": route,
                "frequency": frequency,
                "timing": timing,
                "duration": duration,
                "instructions": instructions,
                "source_index": idx
            })

        # Tests
        test_list = []
        for t in approved_record.get("tests", []):
            test_list.append({
                "test_name": t.get("name", "Medical Test"),
                "timing": t.get("timing"),
                "instructions": t.get("instructions")
            })

        # Care instructions
        self_care = list(approved_record.get("instructions", []))
        if not self_care and approved_record.get("lifestyle_advice"):
            self_care = list(approved_record.get("lifestyle_advice", []))

        # Warnings
        warnings = list(approved_record.get("warnings_and_precautions", []) or approved_record.get("warnings", []))

        # Follow-up
        follow_up = approved_record.get("follow_up")
        if isinstance(follow_up, dict):
            when_to_visit = follow_up.get("timeline") or follow_up.get("instructions")
        elif isinstance(follow_up, str):
            when_to_visit = follow_up
        else:
            when_to_visit = "As instructed by your physician if symptoms persist." if not is_tamil else "அறிகுறிகள் தொடர்ந்தால் மருத்துவரை மீண்டும் அணுகவும்."

        # Uncertain or unspecified info
        uncertain = list(approved_record.get("uncertain_items", []))

        return {
            "overview": overview,
            "symptoms_discussed": symptoms,
            "medications": med_list,
            "tests_ordered": test_list,
            "self_care_instructions": self_care,
            "warnings_and_precautions": warnings,
            "when_to_visit_again": when_to_visit,
            "unspecified_or_uncertain_info": uncertain
        }

    def run(self, context: WorkflowContext) -> AgentResult:
        """
        Executes patient summary generation for the requested consultation and language.
        """
        medical_record = context.medical_record
        if not medical_record:
            return AgentResult(
                success=False,
                error="PatientSummaryAgent requires an approved medical_record in context."
            )

        # Desired output language
        target_lang = context.language or "en"
        logger.info(
            f"PatientSummaryAgent generating summary for consultation [{context.consultation_id}] "
            f"in language '{target_lang}'"
        )

        llm = self._get_llm_client()
        generated_data: Optional[Dict[str, Any]] = None

        if llm is not None:
            system_prompt = self._build_system_prompt(target_lang)
            user_prompt = self._build_user_prompt(medical_record, target_lang)

            try:
                raw_response = llm.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.1,
                    max_retries=self.retry_policy.max_attempts,
                    timeout=self.timeout_seconds
                )
                if isinstance(raw_response, dict):
                    generated_data = raw_response
            except Exception as e:
                logger.warning(
                    f"LLM generation failed for PatientSummaryAgent: {e}. "
                    "Falling back to deterministic clinical summary generator."
                )

        # Fallback if LLM is unavailable or failed
        if generated_data is None:
            generated_data = self._generate_fallback_summary(medical_record, target_lang)

        # Validate with Pydantic
        try:
            validated_summary = PatientSummaryContent(**generated_data)
        except ValidationError as val_err:
            logger.error(f"PatientSummaryContent validation failed: {val_err}")
            return AgentResult(
                success=False,
                error=f"Generated summary failed schema validation: {str(val_err)}"
            )

        return AgentResult(
            success=True,
            output=validated_summary.model_dump(),
            metadata={
                "language": target_lang,
                "medications_count": len(validated_summary.medications),
                "tests_count": len(validated_summary.tests_ordered),
                "has_warnings": len(validated_summary.warnings_and_precautions) > 0,
                "agent_version": self.version
            }
        )
