"""
PostVisit AI - Patient Summary Service
Coordinates the end-to-end lifecycle of patient-friendly summaries:
  1. Verifies doctor-approval gating on source consultation.
  2. Enforces idempotency to prevent duplicate generation runs.
  3. Executes PatientSummaryAgent within BaseAgent and AgentRegistry framework.
  4. Runs deterministic SummaryGuardrail checks.
  5. Manages doctor review workflow (approve, reject, amend).
  6. Enforces strict role-based access control (patients blocked until approved).
"""

import sys
import hashlib
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.repositories.consultation_repository import ConsultationRepository, get_consultation_repository
from api.repositories.summary_repository import SummaryRepository, get_summary_repository
from api.repositories.workflow_repository import WorkflowRepository, get_workflow_repository
from src.agents.registry import AgentRegistry, get_agent_registry
from src.agents.base import WorkflowContext
from src.guardrails.summary_guardrail import SummaryGuardrail
from src.workflow.states import WorkflowState
from src.schemas.patient_summary_schema import (
    PatientSummaryContent,
    PatientSummaryRecord,
    PatientSummaryReviewRequest
)

logger = logging.getLogger("postvisit.services.summary")


class SummaryService:
    """
    Core domain service managing patient summaries, clinical guardrails,
    physician review sign-offs, and role-based access control.
    """

    def __init__(
        self,
        summary_repo: Optional[SummaryRepository] = None,
        consultation_repo: Optional[ConsultationRepository] = None,
        workflow_repo: Optional[WorkflowRepository] = None,
        agent_registry: Optional[AgentRegistry] = None,
        guardrail: Optional[SummaryGuardrail] = None
    ):
        self.summary_repo = summary_repo or get_summary_repository()
        self.consultation_repo = consultation_repo or get_consultation_repository()
        self.workflow_repo = workflow_repo or get_workflow_repository()
        self.agent_registry = agent_registry or get_agent_registry()
        self.guardrail = guardrail or SummaryGuardrail()

    @staticmethod
    def _compute_record_hash(medical_record: Dict[str, Any]) -> str:
        """Deterministic hash of source medical record for provenance and caching."""
        import json
        raw = json.dumps(medical_record, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_summary(
        self,
        consultation_id: str,
        target_language: str = "en",
        idempotency_key: Optional[str] = None,
        caller_role: str = "system",
        caller_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Generates and validates a patient summary for an approved consultation.
        Transitions:
          SUMMARY_QUEUED -> GENERATING_SUMMARY -> VALIDATING_SUMMARY -> PENDING_SUMMARY_REVIEW (or NEEDS_REVIEW)
        """
        # 1. Fetch consultation record
        consultation = self.consultation_repo.get_by_id(consultation_id)
        if not consultation:
            raise ValueError(f"Consultation '{consultation_id}' not found.")

        # 2. Check Idempotency
        if idempotency_key:
            existing = self.summary_repo.get_summary_by_idempotency_key(consultation_id, idempotency_key)
            if existing:
                logger.info(f"Returning cached summary for idempotency key '{idempotency_key}'.")
                return existing

        medical_record = consultation.get("medical_record") or {}

        # 3. Clinical Gating: Medical record MUST be doctor-approved
        consultation_status = (consultation.get("status") or "").lower()
        requires_review = medical_record.get("requires_doctor_review")
        doctor_review = medical_record.get("doctor_review") or {}
        decision = doctor_review.get("decision", "").lower()

        is_approved = (
            consultation_status == "completed"
            and requires_review is False
            and decision in ("approved", "amended")
        )

        if not is_approved:
            logger.warning(
                f"Attempted summary generation on unapproved consultation [{consultation_id}]. "
                f"status={consultation_status}, requires_doctor_review={requires_review}, decision={decision}"
            )
            raise ValueError(
                "Cannot generate patient summary: Medical record is not doctor-approved. "
                "Consultation must be completed and reviewed by a physician."
            )

        # 4. Check for existing approved summary with identical record hash and language
        record_hash = self._compute_record_hash(medical_record)
        existing_summaries = self.summary_repo.list_summaries_for_consultation(consultation_id, language=target_language)
        for s in existing_summaries:
            if s.get("source_record_hash") == record_hash and s.get("status") == "SUMMARY_APPROVED":
                logger.info(f"Approved summary already exists for consultation {consultation_id} in {target_language}. Returning cached version.")
                return s

        # 5. Create Workflow Step Tracking
        step_id = f"summary_{consultation_id}_{target_language}"
        wf_run = self.workflow_repo.get_workflow_run_by_consultation(consultation_id)
        wf_run_id = wf_run["id"] if wf_run else consultation_id

        # 6. Execute PatientSummaryAgent
        agent = self.agent_registry.get("patient_summary")
        if not agent:
            raise RuntimeError("PatientSummaryAgent is not registered in AgentRegistry.")

        context = WorkflowContext(
            consultation_id=consultation_id,
            workflow_run_id=wf_run_id,
            language=target_language,
            medical_record=medical_record,
            original_filename=consultation.get("original_filename", "")
        )

        agent_result = agent.execute(context)
        if not agent_result.success or not agent_result.output:
            logger.error(f"PatientSummaryAgent execution failed: {agent_result.error}")
            # Persist failed summary record
            record = self.summary_repo.create_summary(
                consultation_id=consultation_id,
                language=target_language,
                generated_summary={
                    "overview": "Summary generation encountered an error.",
                    "symptoms_discussed": [],
                    "medications": [],
                    "tests_ordered": [],
                    "self_care_instructions": [],
                    "warnings_and_precautions": [],
                    "unspecified_or_uncertain_info": [f"Error: {agent_result.error}"]
                },
                status=WorkflowState.SUMMARY_FAILED.value,
                source_record_hash=record_hash,
                idempotency_key=idempotency_key
            )
            return record

        generated_content = agent_result.output

        # 7. Execute SummaryGuardrail Validation
        guardrail_result = self.guardrail.validate(
            summary_content=generated_content,
            approved_medical_record=medical_record,
            language=target_language
        )

        initial_status = WorkflowState.PENDING_SUMMARY_REVIEW.value
        review_notes = None

        if not guardrail_result.passed:
            logger.warning(
                f"SummaryGuardrail validation flagged issues: {guardrail_result.error_code} - {guardrail_result.message}"
            )
            initial_status = WorkflowState.NEEDS_REVIEW.value
            review_notes = f"Guardrail Alert [{guardrail_result.error_code}]: {guardrail_result.message}"

        # 8. Persist Draft Summary
        record = self.summary_repo.create_summary(
            consultation_id=consultation_id,
            language=target_language,
            generated_summary=generated_content,
            status=initial_status,
            source_record_hash=record_hash,
            idempotency_key=idempotency_key
        )

        if review_notes:
            self.summary_repo.update_summary_status(
                summary_id=record["id"],
                status=initial_status,
                error_details={"message": review_notes}
            )
            record["review_notes"] = review_notes
            record["status"] = initial_status

        # Log validation audit
        self.summary_repo.create_audit(
            summary_id=record["id"],
            consultation_id=consultation_id,
            action="validated",
            actor_id="guardrail:summary_guardrail",
            actor_role="system",
            notes=f"Guardrail passed={guardrail_result.passed}. Status={initial_status}."
        )

        logger.info(
            f"Patient summary created [id={record['id']}, status={initial_status}, lang={target_language}]"
        )
        return record

    def review_summary(
        self,
        summary_id: str,
        doctor_name: str,
        decision: str = "approved",
        notes: Optional[str] = None,
        corrected_summary: Optional[Dict[str, Any]] = None,
        caller_role: str = "doctor"
    ) -> Dict[str, Any]:
        """
        Allows an authorized physician to approve, reject, or amend a patient summary.
        """
        if caller_role not in ("doctor", "system"):
            raise PermissionError("Only authorized physicians can review or approve patient summaries.")

        summary = self.summary_repo.get_summary_by_id(summary_id)
        if not summary:
            raise ValueError(f"Summary '{summary_id}' not found.")

        # If amended, validate corrected_summary schema
        valid_corrected = None
        if corrected_summary is not None:
            try:
                valid_corrected = PatientSummaryContent(**corrected_summary).model_dump()
            except Exception as ve:
                raise ValueError(f"Corrected summary does not match valid schema: {ve}")

        updated = self.summary_repo.save_doctor_review(
            summary_id=summary_id,
            doctor_name=doctor_name,
            decision=decision,
            notes=notes,
            corrected_summary=valid_corrected
        )

        if not updated:
            raise RuntimeError("Failed to persist doctor review for summary.")

        return updated

    def get_summary(
        self,
        summary_id: str,
        caller_role: str = "patient",
        caller_id: str = "patient"
    ) -> Dict[str, Any]:
        """
        Retrieves a summary by ID enforcing patient access restrictions.
        Patients can ONLY view summaries with status == 'SUMMARY_APPROVED'.
        """
        summary = self.summary_repo.get_summary_by_id(summary_id)
        if not summary:
            raise ValueError(f"Summary '{summary_id}' not found.")

        # Access Gate: Patients cannot view unapproved summaries
        if caller_role == "patient":
            if summary.get("status") != "SUMMARY_APPROVED":
                logger.warning(
                    f"Blocked patient access to unapproved summary [{summary_id}]. Status: {summary.get('status')}"
                )
                raise PermissionError("Summary is pending physician approval and cannot be viewed by the patient.")

        return summary

    def list_summaries_for_consultation(
        self,
        consultation_id: str,
        caller_role: str = "patient",
        caller_id: str = "patient",
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists summaries for a consultation.
        Patients only receive doctor-approved summaries.
        """
        approved_only = (caller_role == "patient")
        return self.summary_repo.list_summaries_for_consultation(
            consultation_id=consultation_id,
            language=language,
            approved_only=approved_only
        )

    def get_summary_history(
        self,
        summary_id: str,
        caller_role: str = "doctor"
    ) -> List[Dict[str, Any]]:
        """
        Retrieves audit trail and version history for a summary.
        Only accessible by doctors and system administrators.
        """
        if caller_role not in ("doctor", "system"):
            raise PermissionError("Access to audit history is restricted to physicians and administrators.")

        summary = self.summary_repo.get_summary_by_id(summary_id)
        if not summary:
            raise ValueError(f"Summary '{summary_id}' not found.")

        return self.summary_repo.get_audit_history(summary_id)


_summary_service_instance: Optional[SummaryService] = None


def get_summary_service() -> SummaryService:
    """Returns singleton SummaryService instance."""
    global _summary_service_instance
    if _summary_service_instance is None:
        _summary_service_instance = SummaryService()
    return _summary_service_instance
