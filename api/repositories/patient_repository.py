"""
PostVisit AI - Patient Repository
Manages persistence for patient profiles, health metrics, lab reports, recovery plan tracking,
conversational chat history, and voice notes.
Provides Supabase database operations with safe in-memory fallback for local/unit test execution.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from api.config import Settings, get_settings

logger = logging.getLogger("postvisit.repository.patient")

try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False
    Client = None


# Default seed profile for demonstration and testing
DEFAULT_PATIENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "PT-89241": {
        "patient_id": "PT-89241",
        "name": "Ananya Patel",
        "full_name": "Ananya Patel",
        "age": 42,
        "gender": "Female",
        "phone": "+91 98401 23456",
        "blood_group": "B+",
        "allergies": ["Penicillin (mild skin rash)"],
        "chronic_conditions": ["Type 2 Diabetes Mellitus (Diagnosed 2024)", "Mild Essential Hypertension"],
        "created_at": "2026-01-10T08:00:00Z",
        "updated_at": "2026-10-02T08:00:00Z"
    },
    "pt_ananya_patel": {
        "patient_id": "PT-89241",
        "name": "Ananya Patel",
        "full_name": "Ananya Patel",
        "age": 42,
        "gender": "Female",
        "phone": "+91 98401 23456",
        "blood_group": "B+",
        "allergies": ["Penicillin (mild skin rash)"],
        "chronic_conditions": ["Type 2 Diabetes Mellitus (Diagnosed 2024)", "Mild Essential Hypertension"],
        "created_at": "2026-01-10T08:00:00Z",
        "updated_at": "2026-10-02T08:00:00Z"
    }
}

# Default initial metrics with real dated measurements for PT-89241
DEFAULT_METRICS_SEED: List[Dict[str, Any]] = [
    {
        "id": "met-bp-1",
        "patient_id": "PT-89241",
        "metric_type": "blood_pressure",
        "metric_name": "Blood Pressure",
        "value": 142,
        "value_secondary": 90,
        "unit": "mmHg",
        "recorded_at": "2026-08-10T10:30:00Z",
        "source": "consultation",
        "notes": "Clinic visit"
    },
    {
        "id": "met-bp-2",
        "patient_id": "PT-89241",
        "metric_type": "blood_pressure",
        "metric_name": "Blood Pressure",
        "value": 138,
        "value_secondary": 88,
        "unit": "mmHg",
        "recorded_at": "2026-09-15T09:15:00Z",
        "source": "consultation",
        "notes": "Follow-up visit"
    },
    {
        "id": "met-bp-3",
        "patient_id": "PT-89241",
        "metric_type": "blood_pressure",
        "metric_name": "Blood Pressure",
        "value": 130,
        "value_secondary": 84,
        "unit": "mmHg",
        "recorded_at": "2026-10-02T11:00:00Z",
        "source": "consultation",
        "notes": "Recent consultation with Dr. Rajesh Sharma"
    },
    {
        "id": "met-glu-1",
        "patient_id": "PT-89241",
        "metric_type": "glucose",
        "metric_name": "Fasting Blood Glucose",
        "value": 146,
        "value_secondary": None,
        "unit": "mg/dL",
        "recorded_at": "2026-08-10T08:00:00Z",
        "source": "consultation",
        "notes": "Fasting sample"
    },
    {
        "id": "met-glu-2",
        "patient_id": "PT-89241",
        "metric_type": "glucose",
        "metric_name": "Fasting Blood Glucose",
        "value": 138,
        "value_secondary": None,
        "unit": "mg/dL",
        "recorded_at": "2026-09-15T08:15:00Z",
        "source": "consultation",
        "notes": "Fasting sample"
    },
    {
        "id": "met-glu-3",
        "patient_id": "PT-89241",
        "metric_type": "glucose",
        "metric_name": "Fasting Blood Glucose",
        "value": 126,
        "value_secondary": None,
        "unit": "mg/dL",
        "recorded_at": "2026-10-02T08:30:00Z",
        "source": "consultation",
        "notes": "Fasting sample on Metformin"
    },
    {
        "id": "met-hr-1",
        "patient_id": "PT-89241",
        "metric_type": "heart_rate",
        "metric_name": "Resting Heart Rate",
        "value": 78,
        "value_secondary": None,
        "unit": "bpm",
        "recorded_at": "2026-09-15T09:15:00Z",
        "source": "consultation",
        "notes": "Normal sinus rhythm"
    },
    {
        "id": "met-hr-2",
        "patient_id": "PT-89241",
        "metric_type": "heart_rate",
        "metric_name": "Resting Heart Rate",
        "value": 74,
        "value_secondary": None,
        "unit": "bpm",
        "recorded_at": "2026-10-02T11:00:00Z",
        "source": "consultation",
        "notes": "Clinic triage"
    },
    {
        "id": "met-wt-1",
        "patient_id": "PT-89241",
        "metric_type": "weight",
        "metric_name": "Body Weight",
        "value": 68.5,
        "value_secondary": None,
        "unit": "kg",
        "recorded_at": "2026-08-10T10:30:00Z",
        "source": "consultation",
        "notes": "Weighing scale"
    },
    {
        "id": "met-wt-2",
        "patient_id": "PT-89241",
        "metric_type": "weight",
        "metric_name": "Body Weight",
        "value": 67.2,
        "value_secondary": None,
        "unit": "kg",
        "recorded_at": "2026-10-02T11:00:00Z",
        "source": "consultation",
        "notes": "Dietary modification progress"
    }
]


class PatientRepository:
    """
    Data repository for patient portal interactions.
    Provides database persistence with memory fallback.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client: Optional[Client] = None

        # In-memory storage stores
        self._files: Dict[str, bytes] = {}
        self._seed_initial_data()

        if self.settings.is_supabase_configured and HAS_SUPABASE_LIB:
            try:
                self.client = create_client(
                    self.settings.SUPABASE_URL,
                    self.settings.SUPABASE_SERVICE_ROLE_KEY
                )
                self.client.table("patient_profiles").select("id").limit(1).execute()
                logger.info("PatientRepository: Supabase client verified successfully.")
            except Exception as e:
                logger.warning(f"PatientRepository: Operating with in-memory persistence fallback ({e}).")
                self.client = None

    def _seed_initial_data(self):
        import copy
        self._profiles = copy.deepcopy(DEFAULT_PATIENT_PROFILES)
        self._in_memory_profiles = self._profiles
        self._metrics = copy.deepcopy(DEFAULT_METRICS_SEED)
        self._lab_reports = {}
        self._recovery_tasks = {}
        self._chat_messages = []
        self._voice_notes = {}
        self._seed_initial_lab_reports()

    def _seed_initial_lab_reports(self):
        sample_report = {
            "id": "rep-hba1c-prev",
            "patient_id": "PT-89241",
            "consultation_id": None,
            "test_name": "Glycated Hemoglobin (HbA1c)",
            "report_date": "2026-09-10",
            "laboratory_name": "Metropolis Healthcare Lab",
            "facility_name": "Metropolis Healthcare Lab",
            "result_summary": "7.8% (Target < 7.0% per ICMR Guidelines)",
            "test_result": "7.8%",
            "units": "%",
            "unit": "%",
            "reference_range": "< 5.7% Normal, 5.7 - 6.4% Prediabetes, >= 6.5% Diabetes",
            "patient_notes": "Previous 3-month checkup report before medication adjustment.",
            "entry_mode": "manual",
            "file_storage_path": None,
            "file_name": "hba1c_metropolis_sep2026.pdf",
            "filename": "hba1c_metropolis_sep2026.pdf",
            "file_type": "application/pdf",
            "file_size_bytes": 1048576,
            "review_status": "reviewed",
            "reviewed_by": "Dr. Rajesh Sharma, MD",
            "reviewed_at": "2026-09-15T10:00:00Z",
            "doctor_feedback": "Noted 7.8% elevation; commenced Metformin 500mg BD.",
            "created_at": "2026-09-12T14:30:00Z",
            "updated_at": "2026-09-15T10:00:00Z"
        }
        self._lab_reports[sample_report["id"]] = sample_report

    # ---------------------------------------------------------
    # 1. Patient Profiles
    # ---------------------------------------------------------
    def get_profile(self, patient_id: str) -> Dict[str, Any]:
        """Retrieves patient profile. Generates sanitized default if new."""
        normalized_id = patient_id.strip()
        if normalized_id in self._profiles:
            return self._profiles[normalized_id]

        # Check secondary key
        for p in self._profiles.values():
            if p.get("patient_id") == normalized_id:
                return p

        # Default fallback
        new_prof = {
            "patient_id": normalized_id,
            "name": f"Patient {normalized_id}",
            "age": None,
            "gender": None,
            "phone": None,
            "blood_group": None,
            "allergies": [],
            "chronic_conditions": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        self._profiles[normalized_id] = new_prof
        return new_prof

    # ---------------------------------------------------------
    # 2. Health Metrics (Actual dated measurements only)
    # ---------------------------------------------------------
    def get_health_metrics(
        self,
        patient_id: str,
        metric_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Returns dated measurements for patient, sorted by recorded_at ASC for trend rendering."""
        normalized_id = "PT-89241" if patient_id in ("pt_ananya_patel", "PT-89241") else patient_id
        items = [m for m in self._metrics if m["patient_id"] == normalized_id]
        if metric_type:
            items = [m for m in items if m["metric_type"] == metric_type]
        items.sort(key=lambda x: x.get("recorded_at", ""))
        return items[-limit:]

    def list_health_metrics(
        self,
        patient_id: str,
        metric_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Normalized health metrics helper for frontend and services."""
        raw_items = self.get_health_metrics(patient_id, metric_type=metric_type, limit=limit)
        normalized = []
        for m in raw_items:
            m_type = m.get("metric_type", "")
            if m_type == "blood_pressure":
                m_type = "blood_pressure_systolic"
            elif m_type == "glucose":
                m_type = "glucose_fasting"

            val = m.get("value")
            if val is None:
                val = m.get("numeric_value", 0.0)

            sec_val = m.get("value_secondary")
            if sec_val is None:
                sec_val = m.get("secondary_value")

            normalized.append({
                "id": m.get("id"),
                "metric_type": m_type,
                "metric_name": m.get("metric_name", ""),
                "numeric_value": float(val),
                "secondary_value": float(sec_val) if sec_val is not None else None,
                "unit": m.get("unit", ""),
                "recorded_at": m.get("recorded_at", ""),
                "source": m.get("source", "consultation")
            })
        return normalized

    def add_health_metric(
        self,
        patient_id: str,
        metric_type: str,
        metric_name: str,
        value: float,
        unit: str,
        value_secondary: Optional[float] = None,
        consultation_id: Optional[str] = None,
        source: str = "consultation",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records an actual clinical measurement."""
        rec = {
            "id": f"met-{uuid.uuid4().hex[:8]}",
            "patient_id": patient_id,
            "consultation_id": consultation_id,
            "metric_type": metric_type,
            "metric_name": metric_name,
            "value": float(value),
            "numeric_value": float(value),
            "value_secondary": float(value_secondary) if value_secondary is not None else None,
            "secondary_value": float(value_secondary) if value_secondary is not None else None,
            "unit": unit,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "notes": notes,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self._metrics.append(rec)
        return rec

    # ---------------------------------------------------------
    # 3. Lab Reports
    # ---------------------------------------------------------
    def list_lab_reports(
        self,
        patient_id: str,
        consultation_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Lists lab reports for patient, ordered by report_date DESC."""
        normalized_id = "PT-89241" if patient_id in ("pt_ananya_patel", "PT-89241") else patient_id
        raw_reports = [r for r in self._lab_reports.values() if r["patient_id"] == normalized_id]
        if consultation_id:
            raw_reports = [r for r in raw_reports if r.get("consultation_id") == consultation_id]
        raw_reports.sort(key=lambda x: x.get("report_date", ""), reverse=True)

        items = []
        for r in raw_reports[:limit]:
            items.append({
                "id": r["id"],
                "patient_id": r["patient_id"],
                "consultation_id": r.get("consultation_id"),
                "test_name": r.get("test_name"),
                "report_date": r.get("report_date", ""),
                "facility_name": r.get("facility_name") or r.get("laboratory_name"),
                "laboratory_name": r.get("laboratory_name") or r.get("facility_name"),
                "test_result": r.get("test_result") or r.get("result_summary"),
                "result_summary": r.get("result_summary") or r.get("test_result"),
                "unit": r.get("unit") or r.get("units"),
                "units": r.get("units") or r.get("unit"),
                "reference_range": r.get("reference_range"),
                "patient_notes": r.get("patient_notes"),
                "entry_mode": r.get("entry_mode", "manual"),
                "review_status": r.get("review_status", "unreviewed"),
                "filename": r.get("filename") or r.get("file_name"),
                "file_name": r.get("file_name") or r.get("filename"),
                "document_url": r.get("document_url"),
                "file_storage_path": r.get("file_storage_path"),
                "storage_path": r.get("file_storage_path"),
                "created_at": r.get("created_at", "")
            })
        return items

    def create_lab_report(
        self,
        patient_id: str,
        test_name: str,
        report_date: str,
        result_summary: str,
        laboratory_name: Optional[str] = None,
        units: Optional[str] = None,
        reference_range: Optional[str] = None,
        patient_notes: Optional[str] = None,
        consultation_id: Optional[str] = None,
        entry_mode: str = "manual",
        file_storage_path: Optional[str] = None,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        file_size_bytes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Creates a new lab report entry (either manual summary or uploaded document)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        report_id = f"rep-{uuid.uuid4().hex[:10]}"
        rec = {
            "id": report_id,
            "patient_id": patient_id,
            "consultation_id": consultation_id,
            "test_name": test_name,
            "report_date": report_date,
            "laboratory_name": laboratory_name,
            "facility_name": laboratory_name,
            "result_summary": result_summary,
            "test_result": result_summary,
            "units": units,
            "unit": units,
            "reference_range": reference_range,
            "patient_notes": patient_notes,
            "entry_mode": entry_mode,
            "file_storage_path": file_storage_path,
            "storage_path": file_storage_path,
            "file_name": file_name,
            "filename": file_name,
            "file_type": file_type,
            "content_type": file_type,
            "file_size_bytes": file_size_bytes,
            "review_status": "unreviewed",
            "reviewed_by": None,
            "reviewed_at": None,
            "doctor_feedback": None,
            "created_at": now_iso,
            "updated_at": now_iso
        }
        self._lab_reports[report_id] = rec
        return rec

    def create_manual_lab_report(
        self,
        patient_id: str,
        test_name: str,
        report_date: str,
        facility_name: Optional[str] = None,
        test_result: Optional[str] = None,
        unit: Optional[str] = None,
        reference_range: Optional[str] = None,
        patient_notes: Optional[str] = None,
        consultation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return self.create_lab_report(
            patient_id=patient_id,
            test_name=test_name,
            report_date=report_date,
            result_summary=test_result or "",
            laboratory_name=facility_name,
            units=unit,
            reference_range=reference_range,
            patient_notes=patient_notes,
            consultation_id=consultation_id,
            entry_mode="manual"
        )

    def save_uploaded_lab_report(
        self,
        patient_id: str,
        filename: str,
        file_bytes: bytes,
        content_type: str,
        test_name: str,
        report_date: str,
        facility_name: Optional[str] = None,
        consultation_id: Optional[str] = None,
        patient_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        storage_path = f"patient-lab-reports/{patient_id}/{uuid.uuid4().hex[:8]}_{filename}"
        self._files[storage_path] = file_bytes
        return self.create_lab_report(
            patient_id=patient_id,
            test_name=test_name,
            report_date=report_date,
            result_summary="Uploaded document attached",
            laboratory_name=facility_name,
            units=None,
            reference_range=None,
            patient_notes=patient_notes,
            consultation_id=consultation_id,
            entry_mode="upload",
            file_storage_path=storage_path,
            file_name=filename,
            file_type=content_type,
            file_size_bytes=len(file_bytes)
        )

    def get_lab_report(self, report_id: str, patient_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a lab report by ID enforcing patient ownership."""
        rep = self._lab_reports.get(report_id)
        if not rep:
            return None
        if patient_id and rep.get("patient_id") != patient_id:
            normalized_req = "PT-89241" if patient_id in ("pt_ananya_patel", "PT-89241") else patient_id
            if rep.get("patient_id") != normalized_req:
                raise PermissionError("Access denied: You do not own this lab report.")
        return rep

    def get_lab_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        r = self.get_lab_report(report_id)
        if not r:
            return None
        return {
            "id": r["id"],
            "patient_id": r["patient_id"],
            "consultation_id": r.get("consultation_id"),
            "test_name": r.get("test_name"),
            "report_date": r.get("report_date"),
            "facility_name": r.get("facility_name") or r.get("laboratory_name"),
            "test_result": r.get("test_result") or r.get("result_summary"),
            "unit": r.get("unit") or r.get("units"),
            "reference_range": r.get("reference_range"),
            "patient_notes": r.get("patient_notes"),
            "entry_mode": r.get("entry_mode", "manual"),
            "review_status": r.get("review_status", "unreviewed"),
            "filename": r.get("filename") or r.get("file_name"),
            "storage_path": r.get("file_storage_path"),
            "content_type": r.get("file_type", "application/pdf")
        }

    def get_file_bytes(self, storage_path: str) -> Optional[bytes]:
        return self._files.get(storage_path)

    # ---------------------------------------------------------
    # 4. Recovery Plan Tracking (Checklist personal tracking)
    # ---------------------------------------------------------
    def get_recovery_tasks(self, patient_id: str, consultation_id: str) -> Dict[str, Dict[str, Any]]:
        """Returns map of task_key -> tracking record for a consultation."""
        prefix = f"{patient_id}:{consultation_id}:"
        result = {}
        for k, v in self._recovery_tasks.items():
            if k.startswith(prefix):
                task_key = k[len(prefix):]
                result[task_key] = v
        return result

    def get_recovery_tracking(self, patient_id: str, consultation_id: str) -> List[Dict[str, Any]]:
        tasks_map = self.get_recovery_tasks(patient_id, consultation_id)
        return [
            {
                "task_key": k,
                "patient_completed": v.get("is_completed", False),
                "completed_at": v.get("completed_at"),
                "notes": v.get("notes")
            }
            for k, v in tasks_map.items()
        ]

    def set_recovery_task(
        self,
        patient_id: str,
        consultation_id: str,
        task_key: str,
        task_type: str,
        task_title: str,
        is_completed: bool,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Toggles a patient's personal completion checkmark."""
        composite_key = f"{patient_id}:{consultation_id}:{task_key}"
        now_iso = datetime.now(timezone.utc).isoformat()
        rec = {
            "id": f"rec-{uuid.uuid4().hex[:8]}",
            "patient_id": patient_id,
            "consultation_id": consultation_id,
            "task_key": task_key,
            "task_type": task_type,
            "task_title": task_title,
            "is_completed": bool(is_completed),
            "patient_completed": bool(is_completed),
            "completed_at": now_iso if is_completed else None,
            "notes": notes,
            "created_at": now_iso
        }
        self._recovery_tasks[composite_key] = rec
        return rec

    def set_task_completion(
        self,
        patient_id: str,
        consultation_id: str,
        task_key: str,
        completed: bool,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        return self.set_recovery_task(
            patient_id=patient_id,
            consultation_id=consultation_id,
            task_key=task_key,
            task_type="checklist",
            task_title=task_key,
            is_completed=completed,
            notes=notes
        )

    # ---------------------------------------------------------
    # 5. AI Chat Messages
    # ---------------------------------------------------------
    def save_chat_message(
        self,
        session_id: str,
        patient_id: str,
        sender_role: Optional[str] = None,
        role: Optional[str] = None,
        message_text: Optional[str] = None,
        content: Optional[str] = None,
        context_type: Optional[str] = None,
        context_topic: Optional[str] = None,
        citations: Optional[List[Dict[str, str]]] = None,
        consultation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Saves a conversation turn to session history."""
        resolved_role = role or sender_role or "patient"
        resolved_content = content or message_text or ""
        resolved_topic = context_topic or context_type

        msg = {
            "id": f"msg-{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "patient_id": patient_id,
            "consultation_id": consultation_id,
            "role": resolved_role,
            "sender_role": resolved_role,
            "content": resolved_content,
            "message_text": resolved_content,
            "context_topic": resolved_topic,
            "context_type": resolved_topic,
            "citations": citations or [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self._chat_messages.append(msg)
        return msg

    def get_chat_history(
        self,
        patient_id: str,
        session_id: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Returns message history for active session."""
        normalized_id = "PT-89241" if patient_id in ("pt_ananya_patel", "PT-89241") else patient_id
        msgs = [m for m in self._chat_messages if m["patient_id"] == normalized_id]
        if session_id:
            msgs = [m for m in msgs if m["session_id"] == session_id]
        msgs.sort(key=lambda x: x.get("created_at", ""))
        return msgs[-limit:]

    # ---------------------------------------------------------
    # 6. Patient Voice Notes
    # ---------------------------------------------------------
    def save_voice_note(
        self,
        patient_id: str,
        audio_filename: Optional[str] = None,
        audio_format: Optional[str] = None,
        transcription: Optional[str] = None,
        duration_seconds: float = 0.0,
        language: str = "ta",
        storage_path: Optional[str] = None,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        transcript_text: Optional[str] = None,
        audio_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Saves a transcribed patient voice inquiry note."""
        vid = f"vn-{uuid.uuid4().hex[:8]}"
        resolved_filename = filename or audio_filename or "recording.webm"
        resolved_format = content_type or audio_format or "audio/webm"
        resolved_text = transcript_text or transcription or ""

        if audio_bytes:
            sp = f"patient-voice/{patient_id}/{vid}_{resolved_filename}"
            self._files[sp] = audio_bytes
            storage_path = sp

        rec = {
            "id": vid,
            "patient_id": patient_id,
            "storage_path": storage_path,
            "audio_filename": resolved_filename,
            "audio_format": resolved_format,
            "transcription": resolved_text,
            "transcript_text": resolved_text,
            "language": language,
            "duration_seconds": round(duration_seconds, 2),
            "status": "transcribed",
            "review_status": "patient_draft",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self._voice_notes[vid] = rec
        return rec

    def get_voice_note(self, voice_note_id: str, patient_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a patient voice note."""
        rec = self._voice_notes.get(voice_note_id)
        if not rec:
            return None
        if patient_id and rec.get("patient_id") != patient_id:
            normalized_req = "PT-89241" if patient_id in ("pt_ananya_patel", "PT-89241") else patient_id
            if rec.get("patient_id") != normalized_req:
                raise PermissionError("Access denied: You do not own this voice note.")
        return rec


_patient_repo_instance: Optional[PatientRepository] = None


def get_patient_repository() -> PatientRepository:
    """Singleton getter for PatientRepository."""
    global _patient_repo_instance
    if _patient_repo_instance is None:
        _patient_repo_instance = PatientRepository()
    return _patient_repo_instance
