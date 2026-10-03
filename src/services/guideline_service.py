"""
PostVisit AI - Medical Guideline Cross-Reference Service
Coordinates clinical decision-support evaluation, physician review gating,
and evidence provenance. Enforces RBAC so patients never receive raw clinical discrepancies.
"""

import sys
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.repositories.consultation_repository import ConsultationRepository, get_consultation_repository
from api.repositories.guideline_repository import GuidelineRepository, get_guideline_repository
from src.agents.registry import AgentRegistry, get_agent_registry
from src.agents.base import WorkflowContext
from src.schemas.guideline_schema import (
    GuidelineCrossReferenceResult,
    GuidelineDoctorReviewRequest
)

logger = logging.getLogger("postvisit.services.guidelines")


class GuidelineService:
    """
    Core domain service managing clinical guideline cross-referencing and physician review sign-offs.
    """

    def __init__(
        self,
        guideline_repo: Optional[GuidelineRepository] = None,
        consultation_repo: Optional[ConsultationRepository] = None,
        agent_registry: Optional[AgentRegistry] = None
    ):
        self.guideline_repo = guideline_repo or get_guideline_repository()
        self.consultation_repo = consultation_repo or get_consultation_repository()
        self.agent_registry = agent_registry or get_agent_registry()

    def cross_reference_consultation(
        self,
        consultation_id: str,
        caller_role: str = "system"
    ) -> Dict[str, Any]:
        """
        Executes guideline comparison against the consultation's medical record.
        Transitions: PENDING -> RUNNING -> COMPLETED_WITH_FINDINGS / COMPLETED_NO_FINDINGS / NO_VERIFIED_SOURCE
        """
        consultation = self.consultation_repo.get_by_id(consultation_id)
        if not consultation:
            raise ValueError(f"Consultation '{consultation_id}' not found.")

        medical_record = consultation.get("medical_record") or consultation.get("extracted_medical_record") or {}
        if not medical_record:
            logger.warning(f"No medical record found to cross-reference for consultation [{consultation_id}].")
            return {
                "consultation_id": consultation_id,
                "status": "NOT_CONFIGURED",
                "findings": [],
                "notes": "No extracted medical record available for guideline cross-referencing."
            }

        agent = self.agent_registry.get("guideline_cross_reference")
        if not agent:
            raise RuntimeError("GuidelineCrossReferenceAgent is not registered in AgentRegistry.")

        context = WorkflowContext(
            consultation_id=consultation_id,
            workflow_run_id=f"wf-guidelines-{consultation_id}",
            medical_record=medical_record,
            original_filename=consultation.get("original_filename", "")
        )

        agent_result = agent.execute(context)
        if not agent_result.success or not agent_result.output:
            logger.error(f"GuidelineCrossReferenceAgent failed: {agent_result.error}")
            failed_record = {
                "consultation_id": consultation_id,
                "status": "FAILED",
                "findings": [],
                "notes": f"Evaluation error: {agent_result.error}"
            }
            return self.guideline_repo.save_cross_reference(failed_record)

        result_data = agent_result.output
        result_data["execution_time_sec"] = agent_result.execution_time_sec

        # Persist result
        saved = self.guideline_repo.save_cross_reference(result_data)
        return saved

    def get_guideline_findings(
        self,
        consultation_id: str,
        caller_role: str = "doctor"
    ) -> Dict[str, Any]:
        """
        Retrieves guideline cross-reference results for a consultation.
        Doctors see full clinical evidence, excerpts, and review controls.
        Patients only receive high-level status ("Verified against national clinical guidelines").
        """
        result = self.guideline_repo.get_by_consultation(consultation_id)

        # If not evaluated yet
        if not result:
            return {
                "consultation_id": consultation_id,
                "status": "NOT_CONFIGURED",
                "message": "Medical guideline cross-reference is not currently enabled for this record.",
                "findings": []
            }

        # Role-based filtering: Patients cannot see raw clinical discrepancy prompts
        if caller_role == "patient":
            status_val = result.get("status", "NOT_CONFIGURED")
            patient_status_msg = "Evaluated against verified clinical guidelines" if "COMPLETED" in status_val else "Not applicable"
            return {
                "consultation_id": consultation_id,
                "status": status_val,
                "summary": patient_status_msg,
                "findings_count": len(result.get("findings", []))
            }

        # Doctors receive full clinical decision-support data
        return result

    def review_finding(
        self,
        consultation_id: str,
        finding_id: str,
        doctor_name: str,
        decision: str = "acknowledged",
        notes: Optional[str] = None,
        caller_role: str = "doctor"
    ) -> Dict[str, Any]:
        """
        Physician reviews, acknowledges, or dismisses a guideline advisory prompt.
        """
        if caller_role not in ("doctor", "system"):
            raise PermissionError("Only authorized physicians can review clinical guideline findings.")

        cross_ref = self.guideline_repo.get_by_consultation(consultation_id)
        if not cross_ref:
            raise ValueError(f"No guideline evaluation found for consultation '{consultation_id}'.")

        review = self.guideline_repo.save_doctor_review(
            cross_reference_id=cross_ref["id"],
            consultation_id=consultation_id,
            finding_id=finding_id,
            doctor_id=doctor_name,
            doctor_name=doctor_name,
            decision=decision,
            notes=notes
        )

        return review


_guideline_service: Optional[GuidelineService] = None


def get_guideline_service() -> GuidelineService:
    """Singleton getter for GuidelineService."""
    global _guideline_service
    if _guideline_service is None:
        _guideline_service = GuidelineService()
    return _guideline_service
