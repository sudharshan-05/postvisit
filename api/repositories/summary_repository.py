"""
PostVisit AI - Patient Summary Repository
Manages persistence of generated patient summaries and audit trails in Supabase.
Includes in-memory fallback for local offline testing when credentials are not configured.
"""

import sys
import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import Settings, get_settings

logger = logging.getLogger("postvisit.repository.summaries")

# Import supabase safely
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False
    Client = None


class SummaryRepository:
    """
    Data repository for patient summaries and clinical audit logs.
    Supports live Supabase PostgreSQL and thread-safe in-memory fallback for unit testing.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client: Optional[Client] = None

        # In-memory storage for offline / unit test operations
        self._in_memory_summaries: Dict[str, Dict[str, Any]] = {}
        self._in_memory_audits: Dict[str, List[Dict[str, Any]]] = {}

        if self.settings.is_supabase_configured and HAS_SUPABASE_LIB:
            try:
                self.client = create_client(
                    self.settings.SUPABASE_URL,
                    self.settings.SUPABASE_SERVICE_ROLE_KEY
                )
                # Fast probe to verify remote table exists
                self.client.table("patient_summaries").select("id").limit(1).execute()
                logger.info("SummaryRepository: Initialized Supabase client and verified patient_summaries table successfully.")
            except Exception as e:
                logger.warning(f"SummaryRepository: Supabase client or table check failed ({e}). Operating with in-memory fallback.")
                self.client = None
        else:
            logger.info("SummaryRepository: Using in-memory repository fallback.")


    @property
    def is_connected(self) -> bool:
        return self.client is not None

    def create_summary(
        self,
        consultation_id: str,
        language: str,
        generated_summary: Dict[str, Any],
        status: str = "PENDING_SUMMARY_REVIEW",
        source_record_hash: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        agent_version: str = "1.0.0",
        prompt_version: str = "1.0.0",
        summary_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a new patient summary record with versioning and audit record.
        """
        sid = summary_id or str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        # Determine next version for this consultation & language
        existing_summaries = self.list_summaries_for_consultation(consultation_id, language=language)
        version = len(existing_summaries) + 1

        record = {
            "id": sid,
            "consultation_id": consultation_id,
            "language": language,
            "version": version,
            "status": status,
            "generated_summary": generated_summary,
            "reviewed_summary": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_decision": None,
            "review_notes": None,
            "source_record_hash": source_record_hash,
            "idempotency_key": idempotency_key,
            "agent_version": agent_version,
            "prompt_version": prompt_version,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        if self.is_connected:
            try:
                res = self.client.table("patient_summaries").insert(record).execute()
                if res.data:
                    record = res.data[0]
            except Exception as e:
                logger.warning(f"Supabase insert failed for summary ({e}). Persisting in-memory fallback.")
                self._in_memory_summaries[sid] = record
        else:
            self._in_memory_summaries[sid] = record

        # Automatically log creation audit
        self.create_audit(
            summary_id=sid,
            consultation_id=consultation_id,
            action="generated",
            actor_id=f"agent:patient_summary:{agent_version}",
            actor_role="agent",
            notes=f"Summary generated in language '{language}' (v{version})."
        )

        return record

    def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a summary by ID."""
        if self.is_connected:
            try:
                res = self.client.table("patient_summaries").select("*").eq("id", summary_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"Supabase select failed ({e}). Checking in-memory.")

        return self._in_memory_summaries.get(summary_id)

    def get_summary_by_idempotency_key(
        self,
        consultation_id: str,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieves an existing summary matching the idempotency key for this consultation."""
        if not idempotency_key:
            return None

        if self.is_connected:
            try:
                res = (
                    self.client.table("patient_summaries")
                    .select("*")
                    .eq("consultation_id", consultation_id)
                    .eq("idempotency_key", idempotency_key)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"Supabase query failed for idempotency key ({e}).")

        for s in self._in_memory_summaries.values():
            if s.get("consultation_id") == consultation_id and s.get("idempotency_key") == idempotency_key:
                return s
        return None

    def list_summaries_for_consultation(
        self,
        consultation_id: str,
        language: Optional[str] = None,
        approved_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Lists summaries associated with a consultation, optionally filtered."""
        results: List[Dict[str, Any]] = []

        if self.is_connected:
            try:
                query = self.client.table("patient_summaries").select("*").eq("consultation_id", consultation_id)
                if language:
                    query = query.eq("language", language)
                if approved_only:
                    query = query.eq("status", "SUMMARY_APPROVED")
                query = query.order("version", desc=True)
                res = query.execute()
                if res.data:
                    return res.data
            except Exception as e:
                logger.warning(f"Supabase list failed ({e}). Falling back to in-memory.")

        # In-memory search
        for s in self._in_memory_summaries.values():
            if s.get("consultation_id") != consultation_id:
                continue
            if language and s.get("language") != language:
                continue
            if approved_only and s.get("status") != "SUMMARY_APPROVED":
                continue
            results.append(s)

        results.sort(key=lambda x: x.get("version", 1), reverse=True)
        return results

    def update_summary_status(
        self,
        summary_id: str,
        status: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates summary state and optionally logs error details."""
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "status": status,
            "updated_at": now_iso
        }
        if error_details:
            update_data["review_notes"] = str(error_details.get("message") or "")

        if self.is_connected:
            try:
                res = self.client.table("patient_summaries").update(update_data).eq("id", summary_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"Supabase update status failed ({e}). Falling back.")

        rec = self._in_memory_summaries.get(summary_id)
        if rec:
            rec.update(update_data)
            return rec
        return None

    def save_doctor_review(
        self,
        summary_id: str,
        doctor_name: str,
        decision: str,
        notes: Optional[str] = None,
        corrected_summary: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Saves physician review sign-off.
        decision: 'approved', 'rejected', or 'amended'.
        Status transitions:
          - 'approved' / 'amended' -> 'SUMMARY_APPROVED'
          - 'rejected' -> 'SUMMARY_REJECTED'
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        new_status = "SUMMARY_APPROVED" if decision in ("approved", "amended") else "SUMMARY_REJECTED"

        update_payload: Dict[str, Any] = {
            "status": new_status,
            "reviewed_by": doctor_name,
            "reviewed_at": now_iso,
            "review_decision": decision,
            "review_notes": notes or ("Approved by physician." if decision == "approved" else "Rejected by physician."),
            "updated_at": now_iso
        }

        if corrected_summary is not None:
            update_payload["reviewed_summary"] = corrected_summary

        if self.is_connected:
            try:
                res = self.client.table("patient_summaries").update(update_payload).eq("id", summary_id).execute()
                if res.data:
                    updated = res.data[0]
                else:
                    updated = None
            except Exception as e:
                logger.warning(f"Supabase save doctor review failed ({e}). Using in-memory.")
                updated = None
        else:
            updated = None

        if updated is None:
            rec = self._in_memory_summaries.get(summary_id)
            if rec:
                rec.update(update_payload)
                updated = rec

        if updated:
            # Create audit record
            self.create_audit(
                summary_id=summary_id,
                consultation_id=updated.get("consultation_id", ""),
                action=decision,
                actor_id=doctor_name,
                actor_role="doctor",
                notes=notes,
                changes={"corrected_summary": corrected_summary is not None}
            )

        return updated

    def create_audit(
        self,
        summary_id: str,
        consultation_id: str,
        action: str,
        actor_id: str,
        actor_role: str,
        notes: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Creates an immutable audit log entry."""
        audit_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        audit_entry = {
            "id": audit_id,
            "summary_id": summary_id,
            "consultation_id": consultation_id,
            "action": action,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "notes": notes,
            "changes": changes or {},
            "created_at": now_iso
        }

        if self.is_connected:
            try:
                self.client.table("patient_summary_audits").insert(audit_entry).execute()
            except Exception as e:
                logger.warning(f"Supabase audit insert failed ({e}).")

        if summary_id not in self._in_memory_audits:
            self._in_memory_audits[summary_id] = []
        self._in_memory_audits[summary_id].append(audit_entry)

        return audit_entry

    def get_audit_history(self, summary_id: str) -> List[Dict[str, Any]]:
        """Retrieves audit entries for a specific summary ordered chronologically."""
        if self.is_connected:
            try:
                res = (
                    self.client.table("patient_summary_audits")
                    .select("*")
                    .eq("summary_id", summary_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as e:
                logger.warning(f"Supabase audit history select failed ({e}).")

        return list(self._in_memory_audits.get(summary_id, []))


_summary_repo_instance: Optional[SummaryRepository] = None


def get_summary_repository() -> SummaryRepository:
    """Returns singleton instance of SummaryRepository."""
    global _summary_repo_instance
    if _summary_repo_instance is None:
        _summary_repo_instance = SummaryRepository()
    return _summary_repo_instance
