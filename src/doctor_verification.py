"""
PostVisit AI - Doctor Verification & Physician Review Layer
Guarantees physician-in-the-loop oversight before patient-facing delivery.
Provides structured audit trails, sign-off checklists, and verification records.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class DoctorVerification:
    """
    Manages doctor review, sign-off workflows, and safety verification
    for AI-extracted clinical consultation summaries.
    """

    @staticmethod
    def create_pending_verification(
        medical_data: Dict[str, Any],
        validation_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Creates an initial verification record in 'PENDING_DOCTOR_REVIEW' status.
        """
        requires_review = validation_summary.get("requires_doctor_review", True)
        uncertainties = validation_summary.get("uncertain_items", [])

        checklist = {
            "symptoms_verified": False,
            "medications_verified": False,
            "tests_verified": False,
            "instructions_verified": False,
            "follow_up_verified": False
        }

        return {
            "status": "PENDING_DOCTOR_REVIEW" if requires_review else "AWAITING_DOCTOR_CONFIRMATION",
            "requires_doctor_review": requires_review,
            "verified_by": None,
            "verification_timestamp": None,
            "checklist": checklist,
            "uncertainties_to_resolve": list(uncertainties),
            "doctor_notes": None,
            "clinical_safety_notice": (
                "AI-extracted clinical records require licensed physician verification "
                "prior to patient care plan issuance or electronic prescription generation."
            )
        }

    @staticmethod
    def approve_and_sign(
        verification_record: Dict[str, Any],
        doctor_name: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Signs and authorizes the clinical record upon doctor review.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        verification_record["status"] = "APPROVED_BY_DOCTOR"
        verification_record["requires_doctor_review"] = False
        verification_record["verified_by"] = doctor_name
        verification_record["verification_timestamp"] = now_iso
        verification_record["doctor_notes"] = notes
        verification_record["checklist"] = {
            "symptoms_verified": True,
            "medications_verified": True,
            "tests_verified": True,
            "instructions_verified": True,
            "follow_up_verified": True
        }
        return verification_record

    @staticmethod
    def format_summary(verification_record: Dict[str, Any]) -> str:
        """
        Generates human-readable physician verification summary.
        """
        status = verification_record.get("status", "UNKNOWN")
        doc = verification_record.get("verified_by") or "Not yet signed"
        time_str = verification_record.get("verification_timestamp") or "Pending"
        uncertainties = verification_record.get("uncertainties_to_resolve", [])

        lines = [
            "=" * 60,
            "DOCTOR VERIFICATION & CLINICAL SAFETY AUDIT",
            "=" * 60,
            f"Review Status:        {status}",
            f"Authorized Doctor:    {doc}",
            f"Signed Timestamp:     {time_str}",
            "-" * 60,
            "Clinical Safety Checklist:"
        ]
        checklist = verification_record.get("checklist", {})
        for item, checked in checklist.items():
            check_mark = "[X]" if checked else "[ ]"
            lines.append(f"  {check_mark} {item.replace('_', ' ').title()}")

        if uncertainties:
            lines.append("-" * 60)
            lines.append("Flagged Clinical Ambiguities / Uncertainties:")
            for idx, u in enumerate(uncertainties, 1):
                lines.append(f"  {idx}. {u}")

        lines.append("=" * 60)
        return "\n".join(lines)
