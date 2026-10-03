"""
PostVisit AI - Background Worker Abstraction
Manages asynchronous background job execution for clinical consultation workflows.
Decoupled design allows future seamless migration to Celery, Redis Queue, or Temporal.
"""

import sys
import queue
import logging
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow.orchestrator import WorkflowOrchestrator, get_workflow_orchestrator

logger = logging.getLogger("postvisit.worker")


class BackgroundWorker:
    """
    Asynchronous background job worker.
    Processes queued consultation workflow jobs in a background thread pool,
    preventing HTTP request blocking while ensuring durable state tracking.
    """

    def __init__(
        self,
        orchestrator: Optional[WorkflowOrchestrator] = None,
        max_workers: int = 2
    ):
        self.orchestrator = orchestrator or get_workflow_orchestrator()
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pv-worker-")
        self._is_running = True
        logger.info(f"Initialized BackgroundWorker with {max_workers} worker threads.")

    def enqueue(
        self,
        consultation_id: str,
        workflow_run_id: str,
        media_path: str,
        original_filename: str,
        media_type: str = "application/octet-stream",
        language: str = "ta"
    ) -> None:
        """
        Dispatches a workflow execution job to the background thread pool immediately.
        Non-blocking: returns control instantly to the caller.
        """
        logger.info(
            f"Enqueuing workflow job in background [consultation_id={consultation_id}, "
            f"workflow_run_id={workflow_run_id}]"
        )
        self._executor.submit(
            self._job_wrapper,
            consultation_id,
            workflow_run_id,
            media_path,
            original_filename,
            media_type,
            language
        )

    def _job_wrapper(
        self,
        consultation_id: str,
        workflow_run_id: str,
        media_path: str,
        original_filename: str,
        media_type: str,
        language: str
    ) -> None:
        """Internal execution runner capturing all unhandled exceptions."""
        try:
            logger.info(f"Background worker picked up job [consultation_id={consultation_id}]")
            self.orchestrator.execute_workflow(
                consultation_id=consultation_id,
                workflow_run_id=workflow_run_id,
                media_path=media_path,
                original_filename=original_filename,
                media_type=media_type,
                language=language
            )
            logger.info(f"Background worker completed job [consultation_id={consultation_id}]")
        except Exception as e:
            logger.error(
                f"Unhandled exception in background worker for consultation [{consultation_id}]: {e}",
                exc_info=True
            )

    def startup(self) -> None:
        """Startup hook: runs crash recovery on pending/interrupted workflows."""
        logger.info("BackgroundWorker starting up. Running crash recovery check...")
        recovered = self.orchestrator.recover_pending_workflows()
        logger.info(f"BackgroundWorker startup complete. Recovered {recovered} workflows.")

    def shutdown(self) -> None:
        """Graceful shutdown hook."""
        logger.info("BackgroundWorker shutting down. Draining worker pool...")
        self._is_running = False
        self._executor.shutdown(wait=False)
        logger.info("BackgroundWorker shutdown complete.")


_worker_instance: Optional[BackgroundWorker] = None


def get_background_worker() -> BackgroundWorker:
    """Returns singleton BackgroundWorker instance."""
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = BackgroundWorker()
    return _worker_instance
