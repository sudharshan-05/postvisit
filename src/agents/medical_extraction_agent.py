"""
PostVisit AI - Medical Extraction Agent
Executes structured clinical information extraction using the Groq LLM client,
grounded strictly in speaker-labelled transcripts. Preserves evidence attribution,
supports dynamic drug extraction without a hardcoded whitelist, and flags ambiguities.
"""

import logging
from typing import Dict, Any, Optional
from src.agents.base import BaseAgent, AgentResult, WorkflowContext, RetryPolicy
from src.medical_schema import MedicalExtraction
from src.medical_extractor import extract_medical_record

logger = logging.getLogger("postvisit.agents.medical_extraction")


class MedicalExtractionAgent(BaseAgent):
    """
    AI Agent responsible for extracting structured medical information
    from speaker-attributed clinical consultation dialogues.
    """

    name: str = "medical_extraction"
    version: str = "1.0.0"
    description: str = (
        "Extracts structured clinical medications, schedules, symptoms, "
        "tests, instructions, and warnings from consultation transcripts."
    )
    output_schema = MedicalExtraction
    permissions = ["read_transcript", "generate_medical_record"]
    timeout_seconds = 45.0
    retry_policy = RetryPolicy(
        max_attempts=3,
        initial_delay_sec=1.0,
        backoff_factor=2.0,
        retryable_exceptions=("TimeoutError", "ConnectionError", "RuntimeError", "Exception")
    )

    def run(self, context: WorkflowContext) -> AgentResult:
        """
        Executes clinical entity extraction from the transcript stored in context.
        """
        # Determine best input transcript
        transcript_input = (
            context.speaker_labelled_transcript.strip()
            or context.combined_transcript.strip()
        )

        if not transcript_input and context.transcript_turns:
            transcript_input = "\n".join([
                f"{t.get('speaker', 'Unknown')}: {t.get('text', '')}"
                for t in context.transcript_turns
            ])

        if not transcript_input:
            return AgentResult(
                success=False,
                error="Empty or missing transcript provided to MedicalExtractionAgent."
            )

        logger.info(
            f"MedicalExtractionAgent running for consultation [{context.consultation_id}], "
            f"transcript length: {len(transcript_input)} chars"
        )

        record = extract_medical_record(transcript_input)

        medical_info = record.get("medical_information", {})
        validation = record.get("validation", {})

        # Enrich context with extraction output
        context.medical_record = medical_info
        context.validation_result = validation

        return AgentResult(
            success=True,
            output={
                "medical_record": medical_info,
                "validation": validation,
                "transcript": record.get("transcript", "")
            },
            metadata={
                "medications_count": len(medical_info.get("medications", [])),
                "tests_count": len(medical_info.get("tests", [])),
                "instructions_count": len(medical_info.get("instructions", [])),
                "requires_doctor_review": medical_info.get("requires_doctor_review", True)
            }
        )
