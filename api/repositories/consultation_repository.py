"""
PostVisit AI - Consultation Repository
Provides dedicated data persistence and object storage abstractions for Supabase.
Handles database CRUD on 'public.consultations' and private storage in 'postvisit-media'.
"""

import sys
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import Settings, get_settings

logger = logging.getLogger("postvisit.repository.consultations")

# Import supabase client safely
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False
    Client = None


class ConsultationRepository:
    """
    Manages persistence of clinical consultation records and audio media in Supabase.
    Includes in-memory fallback for local offline testing when credentials are not yet configured.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client: Optional[Client] = None
        self.bucket_name = self.settings.SUPABASE_STORAGE_BUCKET

        # In-memory storage for offline / unit test operation
        self._in_memory_db: Dict[str, Dict[str, Any]] = {}
        self._in_memory_storage: Dict[str, bytes] = {}

        if self.settings.is_supabase_configured and HAS_SUPABASE_LIB:
            try:
                logger.info(f"Connecting to Supabase at: {self.settings.SUPABASE_URL}")
                self.client = create_client(
                    self.settings.SUPABASE_URL,
                    self.settings.SUPABASE_SERVICE_ROLE_KEY
                )
                logger.info("Supabase client initialized successfully with service role privileges.")
                self.ensure_storage_bucket()
            except Exception as e:
                logger.warning(
                    f"Failed to initialize live Supabase client ({e}). "
                    "Operating with in-memory persistence fallback."
                )
                self.client = None
        else:
            logger.info("Supabase credentials not configured in .env. Using in-memory repository fallback.")

    @property
    def is_connected(self) -> bool:
        """Returns True if connected to live Supabase project."""
        return self.client is not None

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests connection to Supabase database and storage bucket.
        """
        if not self.is_connected:
            return {
                "connected": False,
                "mode": "in_memory_fallback",
                "message": "Supabase credentials not set in .env."
            }

        db_ok = False
        storage_ok = False
        db_err = None
        storage_err = None

        try:
            # Test DB query
            res = self.client.table("consultations").select("id").limit(1).execute()
            db_ok = True
        except Exception as ex:
            db_err = str(ex)

        try:
            # Test storage bucket access
            self.ensure_storage_bucket()
            storage_ok = True
        except Exception as ex:
            storage_err = str(ex)

        return {
            "connected": db_ok and storage_ok,
            "mode": "supabase_cloud",
            "database": {"ok": db_ok, "error": db_err},
            "storage": {"ok": storage_ok, "bucket": self.bucket_name, "error": storage_err}
        }

    def ensure_storage_bucket(self) -> bool:
        """
        Guarantees that the private postvisit-media storage bucket exists in Supabase.
        """
        if not self.is_connected:
            return True

        try:
            buckets = self.client.storage.list_buckets()
            existing_names = [b.name for b in buckets] if buckets else []
            if self.bucket_name not in existing_names:
                logger.info(f"Creating private Supabase Storage bucket: {self.bucket_name}")
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={"public": False}
                )
                logger.info(f"Private bucket '{self.bucket_name}' created successfully.")
            return True
        except Exception as ex:
            logger.warning(f"Error checking/creating storage bucket '{self.bucket_name}': {ex}")
            return False

    def upload_media(
        self,
        consultation_id: str,
        local_file_path: str,
        filename: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Uploads original consultation audio/video media to private Supabase Storage.
        Storage Path: consultations/{consultation_id}/original{file_ext}
        """
        ext = Path(filename).suffix.lower()
        storage_path = f"consultations/{consultation_id}/original{ext}"

        with open(local_file_path, "rb") as f:
            file_bytes = f.read()

        if self.is_connected:
            try:
                mime_type = content_type or "application/octet-stream"
                self.client.storage.from_(self.bucket_name).upload(
                    path=storage_path,
                    file=file_bytes,
                    file_options={"content-type": mime_type, "upsert": "true"}
                )
                logger.info(f"Uploaded media to Supabase Storage: {self.bucket_name}/{storage_path}")
                return storage_path
            except Exception as e:
                logger.error(f"Failed to upload media to Supabase Storage: {e}", exc_info=True)
                raise RuntimeError(f"Storage upload failed: {str(e)}") from e
        else:
            # In-memory storage fallback
            self._in_memory_storage[storage_path] = file_bytes
            logger.info(f"[In-Memory] Stored media at simulated path: {storage_path}")
            return storage_path

    def create(
        self,
        consultation_id: str,
        original_filename: str,
        media_type: str
    ) -> Dict[str, Any]:
        """
        Initializes a new consultation row in Supabase database with status='processing'.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        row_data = {
            "id": consultation_id,
            "status": "processing",
            "original_filename": original_filename,
            "media_type": media_type,
            "media_storage_path": None,
            "duration_seconds": None,
            "transcript": None,
            "medical_record": None,
            "validation_result": None,
            "error_code": None,
            "error_message": None,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        if self.is_connected:
            try:
                res = self.client.table("consultations").insert(row_data).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return row_data
            except Exception as e:
                logger.error(f"Failed to create consultation row in Supabase: {e}", exc_info=True)
                raise RuntimeError(f"Database insert failed: {str(e)}") from e
        else:
            self._in_memory_db[consultation_id] = row_data
            return row_data

    def update_media_path(self, consultation_id: str, media_storage_path: str) -> None:
        """
        Updates the media_storage_path once file upload completes.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "media_storage_path": media_storage_path,
            "updated_at": now_iso
        }

        if self.is_connected:
            try:
                self.client.table("consultations").update(update_data).eq("id", consultation_id).execute()
            except Exception as e:
                logger.warning(f"Failed to update media_storage_path in Supabase: {e}")
        else:
            if consultation_id in self._in_memory_db:
                self._in_memory_db[consultation_id].update(update_data)

    def update_completed(
        self,
        consultation_id: str,
        duration_seconds: float,
        transcript: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Updates consultation record upon successful AI processing.
        Sets status='completed' and saves transcript, medical_record, and validation JSONB.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "status": "completed",
            "duration_seconds": round(float(duration_seconds), 2),
            "transcript": transcript,
            "medical_record": medical_record,
            "validation_result": validation_result,
            "updated_at": now_iso
        }

        if self.is_connected:
            try:
                res = self.client.table("consultations").update(update_data).eq("id", consultation_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return update_data
            except Exception as e:
                logger.error(f"Failed to update consultation {consultation_id} in Supabase: {e}", exc_info=True)
                raise RuntimeError(f"Database update failed: {str(e)}") from e
        else:
            if consultation_id in self._in_memory_db:
                self._in_memory_db[consultation_id].update(update_data)
                return self._in_memory_db[consultation_id]
            return update_data

    def update_failed(
        self,
        consultation_id: str,
        error_code: str,
        error_message: str
    ) -> Dict[str, Any]:
        """
        Updates consultation record when processing encounters a failure.
        Sets status='failed' and records safe error code and description.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "status": "failed",
            "error_code": error_code,
            "error_message": error_message,
            "updated_at": now_iso
        }

        if self.is_connected:
            try:
                res = self.client.table("consultations").update(update_data).eq("id", consultation_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return update_data
            except Exception as e:
                logger.warning(f"Failed to record failure in Supabase for {consultation_id}: {e}")
                return update_data
        else:
            if consultation_id in self._in_memory_db:
                self._in_memory_db[consultation_id].update(update_data)
                return self._in_memory_db[consultation_id]
            return update_data

    def get_by_id(self, consultation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a consultation record by its UUID.
        """
        if self.is_connected:
            try:
                res = self.client.table("consultations").select("*").eq("id", consultation_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return None
            except Exception as e:
                logger.error(f"Failed to retrieve consultation {consultation_id} from Supabase: {e}")
                return None
        else:
            return self._in_memory_db.get(consultation_id)

    def list_all(self, limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        Returns paginated list of consultations ordered by created_at DESC with total count.
        """
        if self.is_connected:
            try:
                res = (
                    self.client.table("consultations")
                    .select("*", count="exact")
                    .order("created_at", desc=True)
                    .range(offset, offset + limit - 1)
                    .execute()
                )
                items = res.data or []
                total = res.count if res.count is not None else len(items)
                return items, total
            except Exception as e:
                logger.error(f"Failed to list consultations from Supabase: {e}")
                return [], 0
        else:
            all_items = sorted(
                list(self._in_memory_db.values()),
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )
            total = len(all_items)
            items = all_items[offset:offset + limit]
            return items, total


_repository_instance: Optional[ConsultationRepository] = None


def get_consultation_repository() -> ConsultationRepository:
    """Returns singleton ConsultationRepository instance."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = ConsultationRepository()
    return _repository_instance
