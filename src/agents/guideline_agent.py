"""
PostVisit AI - Clinical Guideline Cross-Reference Agent
Compares physician-approved medical records against verified Indian clinical guidelines
(ICMR, MoHFW, WHO-SEARO). Identifies dosage considerations, missing monitoring tests,
and safety precautions strictly as decision-support review prompts for authorized doctors.
NEVER autonomously diagnoses, prescribes, alters medications, or overrides doctor authority.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.agents.base import BaseAgent, AgentResult, WorkflowContext, RetryPolicy
from src.guidelines.retrieval_service import GuidelineRetrievalService, get_guideline_retrieval_service
from src.schemas.guideline_schema import (
    GuidelineEvidenceItem,
    GuidelineFindingItem,
    GuidelineCrossReferenceResult
)

logger = logging.getLogger("postvisit.agents.guidelines")


class GuidelineCrossReferenceAgent(BaseAgent):
    """
    Clinical Decision-Support AI Agent.
    Evaluates approved clinical consultations against verified national treatment protocols.
    """

    name: str = "guideline_cross_reference"
    version: str = "1.0.0"
    description: str = (
        "Cross-references doctor-approved medical records with verified Indian clinical guidelines "
        "(ICMR / MoHFW) to identify evidence-backed clinical decision-support prompts."
    )
    output_schema = GuidelineCrossReferenceResult
    permissions = ["read_medical_record", "query_guidelines"]
    timeout_seconds = 30.0
    retry_policy = RetryPolicy(
        max_attempts=2,
        initial_delay_sec=0.5,
        backoff_factor=2.0
    )

    def __init__(self, retrieval_service: Optional[GuidelineRetrievalService] = None):
        self.retrieval_service = retrieval_service or get_guideline_retrieval_service()

    def run(self, context: WorkflowContext) -> AgentResult:
        """
        Executes guideline comparison against the consultation's approved medical record.
        """
        medical_record = context.medical_record
        consultation_id = context.consultation_id

        if not medical_record:
            return AgentResult(
                success=False,
                error="Cannot run guideline cross-reference: No medical record found in context."
            )

        logger.info(f"GuidelineCrossReferenceAgent analyzing consultation [{consultation_id}]...")

        # 1. Retrieve relevant evidence passages
        evidence_list, evaluated_guidelines = self.retrieval_service.retrieve_evidence_for_record(medical_record)

        now_iso = datetime.now(timezone.utc).isoformat()
        res_id = str(uuid.uuid4())

        # If no relevant guidelines match the consultation topic
        if not evidence_list:
            logger.info(f"No verified clinical guideline found for consultation [{consultation_id}].")
            result_payload = GuidelineCrossReferenceResult(
                id=res_id,
                consultation_id=consultation_id,
                status="NO_VERIFIED_SOURCE",
                guidelines_evaluated=evaluated_guidelines,
                findings=[],
                agent_version=self.version,
                notes="No verified clinical guidelines currently configured for the discussed clinical entities.",
                created_at=now_iso,
                updated_at=now_iso
            )
            return AgentResult(
                success=True,
                output=result_payload.model_dump(),
                metadata={"status": "NO_VERIFIED_SOURCE", "findings_count": 0}
            )

        # 2. Perform deterministic clinical comparison
        findings: List[GuidelineFindingItem] = []
        medications = medical_record.get("medications", [])
        tests = medical_record.get("tests", [])
        instructions = medical_record.get("instructions", [])
        warnings = medical_record.get("warnings_and_precautions", []) or medical_record.get("warnings", [])

        med_names = [m.get("name", "").lower() for m in medications if m.get("name")]
        test_names = [t.get("name", "").lower() for t in tests if t.get("name")]
        instruction_text = " ".join(instructions).lower()
        warning_text = " ".join(warnings).lower()

        # Map evidence items by guideline_id for quick lookups
        evidence_by_id: Dict[str, List[GuidelineEvidenceItem]] = {}
        for ev in evidence_list:
            if ev.guideline_id not in evidence_by_id:
                evidence_by_id[ev.guideline_id] = []
            evidence_by_id[ev.guideline_id].append(ev)

        # Check Rule A: Diabetes & Metformin Guidelines (ICMR-Diabetes-2022)
        if any("metformin" in name for name in med_names) or any("diabetes" in name for name in med_names):
            diabetes_evidence = evidence_by_id.get("icmr-diabetes-2022", [])
            hba1c_evidence = next((e for e in diabetes_evidence if "hba1c" in e.excerpt.lower()), None)

            # Check if HbA1c or Glycemic test was ordered
            has_hba1c_test = any("hba1c" in t or "glycated" in t or "blood sugar" in t for t in test_names)
            if not has_hba1c_test and hba1c_evidence:
                findings.append(
                    GuidelineFindingItem(
                        id=f"gdf-{uuid.uuid4().hex[:8]}",
                        category="monitoring_test_recommendation",
                        severity="advisory",
                        clinical_prompt=(
                            "Consider ordering HbA1c glycemic monitoring. ICMR Diabetes Guidelines "
                            "mandate HbA1c testing at least every 3 to 6 months for patients on anti-diabetic therapy."
                        ),
                        target_entity="HbA1c",
                        evidence=hba1c_evidence
                    )
                )

        # Check Rule B: Hypertension & Amlodipine Guidelines (ICMR-HTN-2021)
        if any("amlodipine" in name for name in med_names) or any("telmisartan" in name for name in med_names):
            htn_evidence = evidence_by_id.get("icmr-htn-2021", [])
            lifestyle_evidence = next((e for e in htn_evidence if "sodium" in e.excerpt.lower() or "salt" in e.excerpt.lower()), None)

            # Check if dietary sodium/salt advice was documented
            has_salt_advice = any("salt" in instruction_text or "sodium" in instruction_text for _ in [1])
            if not has_salt_advice and lifestyle_evidence:
                findings.append(
                    GuidelineFindingItem(
                        id=f"gdf-{uuid.uuid4().hex[:8]}",
                        category="lifestyle_therapy",
                        severity="info",
                        clinical_prompt=(
                            "Dietary sodium restriction (< 5g salt/day) produces significant blood pressure reduction. "
                            "Standard Treatment Guidelines recommend reinforcing sodium restriction during antihypertensive visits."
                        ),
                        target_entity="Dietary Sodium Restriction",
                        evidence=lifestyle_evidence
                    )
                )

        # Check Rule C: Acute Febrile / Respiratory Illness Red Flags (MoHFW-ARI-2022)
        if any("paracetamol" in name for name in med_names) or any("fever" in s.lower() for s in medical_record.get("symptoms", [])):
            fever_evidence = evidence_by_id.get("mohfw-ari-fever-2022", [])
            red_flag_evidence = next((e for e in fever_evidence if "102" in e.excerpt or "spO2" in e.excerpt.lower()), None)

            # Check if red flags / danger signs are documented
            has_red_flags = any("102" in warning_text or "emergency" in warning_text or "breathing" in warning_text for _ in [1])
            if not has_red_flags and red_flag_evidence:
                findings.append(
                    GuidelineFindingItem(
                        id=f"gdf-{uuid.uuid4().hex[:8]}",
                        category="safety_precaution",
                        severity="advisory",
                        clinical_prompt=(
                            "Verify emergency red flags: National ARI Protocols recommend explicitly instructing patients "
                            "on danger signs (persistent fever > 102°F beyond 3 days, SpO2 < 94%, severe breathlessness)."
                        ),
                        target_entity="Emergency Red Flags",
                        evidence=red_flag_evidence
                    )
                )

        # Check Rule D: Antibiotic Stewardship (ICMR-AMR-2022)
        if any("amoxicillin" in name for name in med_names) or any("azithromycin" in name for name in med_names):
            amr_evidence = evidence_by_id.get("icmr-amr-respiratory-2022", [])
            amr_item = next((e for e in amr_evidence if "duration" in e.excerpt.lower()), None)

            # Check duration limits
            for med in medications:
                if "amoxicillin" in (med.get("name") or "").lower():
                    dur = med.get("duration", "")
                    if amr_item and dur and ("10 days" in dur or "14 days" in dur):
                        findings.append(
                            GuidelineFindingItem(
                                id=f"gdf-{uuid.uuid4().hex[:8]}",
                                category="dosage_consideration",
                                severity="warning",
                                clinical_prompt=(
                                    f"Review antibiotic treatment duration ({dur}): ICMR Antimicrobial Guidelines "
                                    "advise 5 to 7 days for uncomplicated bacterial respiratory infections to reduce resistance."
                                ),
                                target_entity=med.get("name"),
                                evidence=amr_item
                            )
                        )

        # Determine final status
        final_status = "COMPLETED_WITH_FINDINGS" if findings else "COMPLETED_NO_FINDINGS"

        result_payload = GuidelineCrossReferenceResult(
            id=res_id,
            consultation_id=consultation_id,
            status=final_status,
            guidelines_evaluated=evaluated_guidelines,
            findings=findings,
            agent_version=self.version,
            notes=(
                f"Evaluated against {len(evaluated_guidelines)} guidelines. "
                f"Generated {len(findings)} clinical decision-support prompt(s)."
            ),
            created_at=now_iso,
            updated_at=now_iso
        )

        return AgentResult(
            success=True,
            output=result_payload.model_dump(),
            metadata={
                "status": final_status,
                "findings_count": len(findings),
                "guidelines_count": len(evaluated_guidelines)
            }
        )
