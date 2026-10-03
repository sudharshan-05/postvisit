"""
PostVisit AI - Medical Guideline Repository
Manages persistence of guideline cross-reference results and physician reviews in Supabase.
Includes in-memory fallback for local offline testing when credentials are not configured.
"""

import sys
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import Settings, get_settings

logger = logging.getLogger("postvisit.repository.guidelines")

# Import supabase safely
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False
    Client = None


class GuidelineRepository:
    """
    Data repository for clinical guideline cross-reference runs and physician reviews.
    Supports live Supabase PostgreSQL and thread-safe in-memory fallback for unit testing.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client: Optional[Client] = None

        # In-memory storage for offline / unit testing
        self._in_memory_cross_refs: Dict[str, Dict[str, Any]] = {}
        self._in_memory_reviews: Dict[str, List[Dict[str, Any]]] = {}

        if self.settings.is_supabase_configured and HAS_SUPABASE_LIB:
            try:
                self.client = create_client(
                    self.settings.SUPABASE_URL,
                    self.settings.SUPABASE_SERVICE_ROLE_KEY
                )
                # Fast probe to verify table exists
                self.client.table("guideline_cross_references").select("id").limit(1).execute()
                logger.info("GuidelineRepository: Initialized Supabase client successfully.")
            except Exception as e:
                logger.warning(f"GuidelineRepository: Supabase client/table check failed ({e}). Operating with in-memory fallback.")
                self.client = None
        else:
            logger.info("GuidelineRepository: Using in-memory repository fallback.")

    @property
    def is_connected(self) -> bool:
        return self.client is not None

    def save_cross_reference(self, cross_ref_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves or updates a guideline cross-reference evaluation record.
        """
        cid = cross_ref_data["consultation_id"]
        crid = cross_ref_data.get("id") or str(uuid.uuid4())
        cross_ref_data["id"] = crid

        now_iso = datetime.now(timezone.utc).isoformat()
        cross_ref_data.setdefault("created_at", now_iso)
        cross_ref_data["updated_at"] = now_iso

        if self.is_connected:
            try:
                res = self.client.table("guideline_cross_references").upsert(cross_ref_data).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"Supabase upsert failed for guideline cross-reference ({e}). Using in-memory.")

        self._in_memory_cross_refs[cid] = cross_ref_data
        return cross_ref_data

    def get_by_consultation(self, consultation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest guideline cross-reference result for a consultation.
        """
        if self.is_connected:
            try:
                res = (
                    self.client.table("guideline_cross_references")
                    .select("*")
                    .eq("consultation_id", consultation_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"Supabase query failed for guideline cross-reference ({e}). Checking in-memory.")

        return self._in_memory_cross_refs.get(consultation_id)

    def save_doctor_review(
        self,
        cross_reference_id: str,
        consultation_id: str,
        finding_id: str,
        doctor_id: str,
        doctor_name: str,
        decision: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records a physician's review action on a specific guideline finding.
        """
        review_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        review_record = {
            "id": review_id,
            "cross_reference_id": cross_reference_id,
            "consultation_id": consultation_id,
            "finding_id": finding_id,
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "decision": decision,
            "notes": notes or f"Reviewed by {doctor_name}.",
            "created_at": now_iso
        }

        # Update finding status in the parent cross-reference
        cross_ref = self.get_by_consultation(consultation_id)
        if cross_ref and "findings" in cross_ref:
            findings = cross_ref["findings"]
            for f in findings:
                if f.get("id") == finding_id:
                    f["status"] = decision
                    f["doctor_decision"] = decision
                    f["doctor_notes"] = notes
            self.save_cross_reference(cross_ref)

        if self.is_connected:
            try:
                self.client.table("guideline_reviews").insert(review_record).execute()
            except Exception as e:
                logger.warning(f"Supabase insert failed for guideline review ({e}).")

        if consultation_id not in self._in_memory_reviews:
            self._in_memory_reviews[consultation_id] = []
        self._in_memory_reviews[consultation_id].append(review_record)

        return review_record

    def list_reviews_for_consultation(self, consultation_id: str) -> List[Dict[str, Any]]:
        """Retrieves physician reviews for guideline findings of a consultation."""
        if self.is_connected:
            try:
                res = (
                    self.client.table("guideline_reviews")
                    .select("*")
                    .eq("consultation_id", consultation_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as e:
                logger.warning(f"Supabase query failed for guideline reviews ({e}).")

        return list(self._in_memory_reviews.get(consultation_id, []))


_guideline_repo: Optional[GuidelineRepository] = None


def get_guideline_repository() -> GuidelineRepository:
    """Singleton getter for GuidelineRepository."""
    global _guideline_repo
    if _guideline_repo is None:
        _guideline_repo = GuidelineRepository()
    return _guideline_repo
