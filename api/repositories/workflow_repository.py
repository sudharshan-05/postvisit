"""
PostVisit AI - Workflow Repository
Provides durable persistence for workflow runs, workflow steps, and agent executions.
Includes seamless in-memory fallback for local offline testing and unmigrated instances.
"""

import sys
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import Settings, get_settings
from src.workflow.states import WorkflowState

logger = logging.getLogger("postvisit.repository.workflow")

try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False
    Client = None


class WorkflowRepository:
    """
    Manages persistence of workflow runs, steps, and agent executions in Supabase.
    Gracefully falls back to thread-safe in-memory dictionary storage when Supabase
    tables are not available or during unit testing.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client: Optional[Client] = None

        # In-memory storage for offline / testing operation
        self._in_memory_runs: Dict[str, Dict[str, Any]] = {}
        self._in_memory_steps: Dict[str, Dict[str, Any]] = {}
        self._in_memory_agent_execs: Dict[str, Dict[str, Any]] = {}

        self._has_live_workflow_tables = False

        if self.settings.is_supabase_configured and HAS_SUPABASE_LIB:
            try:
                self.client = create_client(
                    self.settings.SUPABASE_URL,
                    self.settings.SUPABASE_SERVICE_ROLE_KEY
                )
                # Verify if workflow_runs table exists in schema cache
                try:
                    self.client.table("workflow_runs").select("id").limit(1).execute()
                    self._has_live_workflow_tables = True
                    logger.info("Connected to live Supabase workflow tables.")
                except Exception as table_err:
                    logger.info(
                        f"Supabase connected, but workflow_runs table not yet detected ({table_err}). "
                        "Using in-memory workflow repository fallback until migration is applied."
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize live Supabase client for workflow: {e}")
                self.client = None

    @property
    def is_live(self) -> bool:
        """Returns True if connected and workflow tables exist in Supabase."""
        return self.client is not None and self._has_live_workflow_tables

    # -------------------------------------------------------------
    # Workflow Runs CRUD
    # -------------------------------------------------------------
    def create_workflow_run(
        self,
        consultation_id: str,
        workflow_version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Creates a new workflow run record with initial status 'queued'."""
        run_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "id": run_id,
            "consultation_id": consultation_id,
            "status": WorkflowState.QUEUED.value,
            "current_step": "QUEUED",
            "workflow_version": workflow_version,
            "started_at": None,
            "completed_at": None,
            "failed_at": None,
            "error_code": None,
            "error_message": None,
            "metadata": metadata or {},
            "created_at": now_iso,
            "updated_at": now_iso
        }

        if self.is_live:
            try:
                res = self.client.table("workflow_runs").insert(row).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Error creating workflow run in Supabase ({ex}). Falling back to memory.")

        self._in_memory_runs[run_id] = row
        return row

    def update_workflow_run_status(
        self,
        workflow_run_id: str,
        status: str,
        current_step: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Updates the status and current step of a workflow run."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates: Dict[str, Any] = {
            "status": status,
            "updated_at": now_iso
        }
        if current_step is not None:
            updates["current_step"] = current_step

        if status in (WorkflowState.VALIDATING_INPUT.value, "running") and not updates.get("started_at"):
            updates["started_at"] = now_iso
        elif status == WorkflowState.COMPLETED.value:
            updates["completed_at"] = now_iso
        elif status in (WorkflowState.FAILED.value, WorkflowState.NEEDS_REVIEW.value):
            updates["failed_at"] = now_iso
            updates["error_code"] = error_code
            updates["error_message"] = error_message

        if metadata:
            updates["metadata"] = metadata

        if self.is_live:
            try:
                res = self.client.table("workflow_runs").update(updates).eq("id", workflow_run_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Error updating workflow run in Supabase ({ex}). Updating memory.")

        if workflow_run_id in self._in_memory_runs:
            self._in_memory_runs[workflow_run_id].update(updates)
            return self._in_memory_runs[workflow_run_id]

        updates["id"] = workflow_run_id
        return updates

    def get_workflow_run(self, workflow_run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a workflow run by its ID."""
        if self.is_live:
            try:
                res = self.client.table("workflow_runs").select("*").eq("id", workflow_run_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Failed to query workflow run {workflow_run_id} from Supabase: {ex}")

        return self._in_memory_runs.get(workflow_run_id)

    def get_workflow_run_by_consultation(self, consultation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent workflow run for a consultation."""
        if self.is_live:
            try:
                res = (
                    self.client.table("workflow_runs")
                    .select("*")
                    .eq("consultation_id", consultation_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Failed to query workflow run for consultation {consultation_id}: {ex}")

        runs = [
            r for r in self._in_memory_runs.values()
            if r.get("consultation_id") == consultation_id
        ]
        if runs:
            runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return runs[0]
        return None

    def get_active_workflow_runs(self) -> List[Dict[str, Any]]:
        """Returns all workflow runs currently in non-terminal states (for crash recovery)."""
        active_statuses = [
            WorkflowState.QUEUED.value,
            WorkflowState.VALIDATING_INPUT.value,
            WorkflowState.PROCESSING_AUDIO.value,
            WorkflowState.DIARIZING.value,
            WorkflowState.TRANSCRIBING.value,
            WorkflowState.VALIDATING_TRANSCRIPT.value,
            WorkflowState.EXTRACTING_MEDICAL_DATA.value,
            WorkflowState.VALIDATING_MEDICAL_DATA.value,
            WorkflowState.PERSISTING_RESULT.value,
        ]

        if self.is_live:
            try:
                res = (
                    self.client.table("workflow_runs")
                    .select("*")
                    .in_("status", active_statuses)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as ex:
                logger.warning(f"Failed to query active workflow runs from Supabase: {ex}")

        return [
            r for r in self._in_memory_runs.values()
            if r.get("status") in active_statuses
        ]

    # -------------------------------------------------------------
    # Workflow Steps CRUD
    # -------------------------------------------------------------
    def create_workflow_step(
        self,
        workflow_run_id: str,
        step_name: str,
        step_type: str = "service",
        max_attempts: int = 3,
        input_reference: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initializes a workflow step record with status 'pending'."""
        step_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "id": step_id,
            "workflow_run_id": workflow_run_id,
            "step_name": step_name,
            "step_type": step_type,
            "status": "pending",
            "attempt": 1,
            "max_attempts": max_attempts,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "input_reference": input_reference or {},
            "output_reference": None,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        if self.is_live:
            try:
                res = self.client.table("workflow_steps").insert(row).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Error creating workflow step in Supabase ({ex}). Using memory.")

        self._in_memory_steps[step_id] = row
        return row

    def update_workflow_step(
        self,
        step_id: str,
        status: str,
        attempt: Optional[int] = None,
        error: Optional[str] = None,
        output_reference: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Updates status, attempt count, or output of an existing step."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates: Dict[str, Any] = {
            "status": status,
            "updated_at": now_iso
        }
        if status == "running":
            updates["started_at"] = now_iso
        elif status in ("completed", "failed", "needs_review"):
            updates["completed_at"] = now_iso

        if attempt is not None:
            updates["attempt"] = attempt
        if error is not None:
            updates["error"] = error
        if output_reference is not None:
            updates["output_reference"] = output_reference

        if self.is_live:
            try:
                res = self.client.table("workflow_steps").update(updates).eq("id", step_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Error updating workflow step in Supabase ({ex}). Updating memory.")

        if step_id in self._in_memory_steps:
            self._in_memory_steps[step_id].update(updates)
            return self._in_memory_steps[step_id]

        updates["id"] = step_id
        return updates

    def get_workflow_steps(self, workflow_run_id: str) -> List[Dict[str, Any]]:
        """Returns all steps executed for a workflow run ordered by creation time."""
        if self.is_live:
            try:
                res = (
                    self.client.table("workflow_steps")
                    .select("*")
                    .eq("workflow_run_id", workflow_run_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as ex:
                logger.warning(f"Failed to query workflow steps from Supabase: {ex}")

        steps = [
            s for s in self._in_memory_steps.values()
            if s.get("workflow_run_id") == workflow_run_id
        ]
        steps.sort(key=lambda x: x.get("created_at", ""))
        return steps

    # -------------------------------------------------------------
    # Agent Executions CRUD
    # -------------------------------------------------------------
    def create_agent_execution(
        self,
        workflow_run_id: str,
        step_id: Optional[str],
        agent_name: str,
        agent_version: str = "1.0.0",
        attempt: int = 1,
        input_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Creates an agent execution record."""
        exec_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "id": exec_id,
            "workflow_run_id": workflow_run_id,
            "step_id": step_id,
            "agent_name": agent_name,
            "agent_version": agent_version,
            "status": "running",
            "attempt": attempt,
            "input_hash": input_hash,
            "started_at": now_iso,
            "completed_at": None,
            "error": None,
            "metadata": metadata or {},
            "created_at": now_iso
        }

        if self.is_live:
            try:
                res = self.client.table("agent_executions").insert(row).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Error creating agent execution in Supabase ({ex}). Using memory.")

        self._in_memory_agent_execs[exec_id] = row
        return row

    def update_agent_execution(
        self,
        execution_id: str,
        status: str,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Updates agent execution result upon completion or failure."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates: Dict[str, Any] = {
            "status": status,
            "completed_at": now_iso
        }
        if error:
            updates["error"] = error
        if metadata:
            updates["metadata"] = metadata

        if self.is_live:
            try:
                res = self.client.table("agent_executions").update(updates).eq("id", execution_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as ex:
                logger.warning(f"Error updating agent execution in Supabase ({ex}). Updating memory.")

        if execution_id in self._in_memory_agent_execs:
            self._in_memory_agent_execs[execution_id].update(updates)
            return self._in_memory_agent_execs[execution_id]

        updates["id"] = execution_id
        return updates

    def get_agent_executions(self, workflow_run_id: str) -> List[Dict[str, Any]]:
        """Returns all agent executions associated with a workflow run."""
        if self.is_live:
            try:
                res = (
                    self.client.table("agent_executions")
                    .select("*")
                    .eq("workflow_run_id", workflow_run_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as ex:
                logger.warning(f"Failed to query agent executions from Supabase: {ex}")

        execs = [
            e for e in self._in_memory_agent_execs.values()
            if e.get("workflow_run_id") == workflow_run_id
        ]
        execs.sort(key=lambda x: x.get("created_at", ""))
        return execs

    def get_workflow_history(self, consultation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves full workflow history for a consultation including run, steps, and agent executions.
        """
        run = self.get_workflow_run_by_consultation(consultation_id)
        if not run:
            return None

        run_id = run["id"]
        steps = self.get_workflow_steps(run_id)
        agent_execs = self.get_agent_executions(run_id)

        return {
            "workflow_run": run,
            "steps": steps,
            "agent_executions": agent_execs,
            "total_steps": len(steps),
            "total_agent_executions": len(agent_execs)
        }


_workflow_repository_instance: Optional[WorkflowRepository] = None


def get_workflow_repository() -> WorkflowRepository:
    """Returns singleton WorkflowRepository instance."""
    global _workflow_repository_instance
    if _workflow_repository_instance is None:
        _workflow_repository_instance = WorkflowRepository()
    return _workflow_repository_instance
