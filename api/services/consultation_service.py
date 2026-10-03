"""
PostVisit AI - Consultation Persistence & Workflow Service
Coordinates consultation lifecycle across Stage 2 and Stage 3:
- Stage 2: Synchronous processing (process_consultation)
- Stage 3: Asynchronous background workflow initiation (start_background_workflow),
  status tracking, workflow history observability, and doctor review.
"""

import sys
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.repositories.consultation_repository import (
    ConsultationRepository,
    get_consultation_repository
)
from api.repositories.workflow_repository import (
    WorkflowRepository,
    get_workflow_repository
)
from api.services.pipeline_service import PipelineService, get_pipeline_service
from src.workflow.worker import BackgroundWorker, get_background_worker
from src.workflow.states import WorkflowState
from api.schemas.consultation import (
    ConsultationResponse,
    ConsultationDetailResponse,
    ConsultationListItem,
    ConsultationListResponse,
    InputMetadata,
    TranscriptTurn,
    MedicalRecord,
    ValidationSummary,
    ErrorDetail
)
from api.schemas.workflow import (
    WorkflowEnqueueResponse,
    ConsultationWorkflowStatusResponse,
    WorkflowHistoryResponse,
    WorkflowStepItem,
    AgentExecutionItem,
    DoctorReviewResponse
)
from src.medical_schema import MedicationItem, TestItem, FollowUpItem
from src.tools.clinical_tools import SaveDoctorReviewTool
from src.tools.base import ToolContext

logger = logging.getLogger("postvisit.services.consultation")


class ConsultationService:
    """
    Coordinates consultation lifecycle, persistence in Supabase PostgreSQL & Storage,
    and background autonomous workflow orchestration.
    """

    def __init__(
        self,
        repository: Optional[ConsultationRepository] = None,
        pipeline_service: Optional[PipelineService] = None,
        workflow_repository: Optional[WorkflowRepository] = None,
        worker: Optional[BackgroundWorker] = None
    ):
        self.repository = repository or get_consultation_repository()
        self.pipeline_service = pipeline_service or get_pipeline_service()
        self.workflow_repo = workflow_repository or get_workflow_repository()
        self.worker = worker or get_background_worker()

    # -------------------------------------------------------------
    # Stage 3: Asynchronous Background Workflow
    # -------------------------------------------------------------
    def start_background_workflow(
        self,
        local_temp_file_path: str,
        original_filename: str,
        media_type: str,
        language: str = "ta"
    ) -> WorkflowEnqueueResponse:
        """
        Executes Stage 3 asynchronous workflow initiation:
        1. Validate request (caller handles).
        2. Create consultation row in Supabase DB (status='queued').
        3. Store original media in private Supabase Storage.
        4. Create durable workflow run in Supabase DB (status='queued').
        5. Enqueue background execution job in BackgroundWorker.
        6. Return immediately with consultation_id, workflow_id, status='queued'.
        """
        consultation_id = str(uuid.uuid4())
        logger.info(
            f"Initiating Stage 3 background workflow [consultation_id={consultation_id}, file={original_filename}]"
        )

        # 2. Create consultation record with initial status 'queued'
        self.repository.create(
            consultation_id=consultation_id,
            original_filename=original_filename,
            media_type=media_type
        )
        if self.repository.is_connected:
            try:
                self.repository.client.table("consultations").update(
                    {"status": "queued"}
                ).eq("id", consultation_id).execute()
            except Exception as e:
                logger.warning(f"Could not set initial status to queued in DB: {e}")
        elif consultation_id in self.repository._in_memory_db:
            self.repository._in_memory_db[consultation_id]["status"] = "queued"

        # 3. Upload media to Supabase Storage
        logger.info(f"Uploading media to Supabase Storage [consultation_id={consultation_id}]...")
        storage_path = self.repository.upload_media(
            consultation_id=consultation_id,
            local_file_path=local_temp_file_path,
            filename=original_filename,
            content_type=media_type
        )
        self.repository.update_media_path(consultation_id, storage_path)
        logger.info(f"Media uploaded to: {storage_path}")

        # 4. Create durable workflow run
        wf_run = self.workflow_repo.create_workflow_run(
            consultation_id=consultation_id,
            workflow_version="1.0.0",
            metadata={"original_filename": original_filename, "media_type": media_type}
        )
        workflow_id = wf_run["id"]
        logger.info(f"Created workflow run [workflow_id={workflow_id}, status=queued]")

        # 5. Queue background processing in worker
        self.worker.enqueue(
            consultation_id=consultation_id,
            workflow_run_id=workflow_id,
            media_path=local_temp_file_path,
            original_filename=original_filename,
            media_type=media_type,
            language=language
        )

        # 6. Return immediately
        return WorkflowEnqueueResponse(
            consultation_id=consultation_id,
            workflow_id=workflow_id,
            status="queued"
        )

    # -------------------------------------------------------------
    # Stage 2: Synchronous Processing (Backwards Compatibility)
    # -------------------------------------------------------------
    def process_consultation(
        self,
        local_temp_file_path: str,
        original_filename: str,
        media_type: str
    ) -> ConsultationResponse:
        """
        Executes the Stage 2 synchronous consultation lifecycle:
        1. Generate consultation UUID
        2. Create database row (status='processing')
        3. Upload media to Supabase Storage
        4. Run existing AI pipeline
        5. Persist transcript, medical JSON, validation in DB (status='completed')
        6. Return complete structured response with consultation_id
        """
        consultation_id = str(uuid.uuid4())
        logger.info(f"Initiating synchronous consultation [id={consultation_id}, file={original_filename}]")

        self.repository.create(
            consultation_id=consultation_id,
            original_filename=original_filename,
            media_type=media_type
        )

        storage_path = None
        try:
            storage_path = self.repository.upload_media(
                consultation_id=consultation_id,
                local_file_path=local_temp_file_path,
                filename=original_filename,
                content_type=media_type
            )
            self.repository.update_media_path(consultation_id, storage_path)

            pipeline_result: ConsultationResponse = self.pipeline_service.process(
                file_path=local_temp_file_path,
                original_filename=original_filename,
                content_type=media_type
            )

            transcript_data = [t.model_dump() for t in pipeline_result.transcript]
            medical_record_data = pipeline_result.medical_record.model_dump()
            validation_data = pipeline_result.validation.model_dump()
            duration_sec = pipeline_result.input.duration_seconds

            self.repository.update_completed(
                consultation_id=consultation_id,
                duration_seconds=duration_sec,
                transcript=transcript_data,
                medical_record=medical_record_data,
                validation_result=validation_data
            )

            pipeline_result.consultation_id = consultation_id
            pipeline_result.media_storage_path = storage_path
            return pipeline_result

        except Exception as e:
            err_code = "AUDIO_PROCESSING_FAILED" if isinstance(e, (ValueError, RuntimeError)) else "INTERNAL_SERVER_ERROR"
            err_msg = "Unable to process the uploaded audio consultation." if err_code == "AUDIO_PROCESSING_FAILED" else "An unexpected error occurred during processing."
            
            logger.error(f"Consultation processing failed for [id={consultation_id}]: {str(e)}", exc_info=True)
            try:
                self.repository.update_failed(
                    consultation_id=consultation_id,
                    error_code=err_code,
                    error_message=err_msg
                )
            except Exception as db_err:
                logger.warning(f"Failed to record failure state in DB: {db_err}")
            raise

    # -------------------------------------------------------------
    # Consultation Retrieval & Status Exposing
    # -------------------------------------------------------------
    def get_consultation(self, consultation_id: str) -> Optional[ConsultationWorkflowStatusResponse]:
        """
        Retrieves consultation record including active workflow step,
        requires_doctor_review status, transcript, and medical JSON.
        """
        row = self.repository.get_by_id(consultation_id)
        if not row:
            return None

        status_val = row.get("status", "unknown")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        # Fetch latest workflow run to extract current step and detailed state
        wf_run = self.workflow_repo.get_workflow_run_by_consultation(consultation_id)
        current_step = wf_run.get("current_step") if wf_run else None
        if wf_run and wf_run.get("status"):
            # If DB row is still queued/processing, reflect granular workflow state
            if status_val in ("processing", "queued"):
                status_val = wf_run["status"].lower()

        if status_val in ("failed", "FAILED"):
            return ConsultationWorkflowStatusResponse(
                consultation_id=consultation_id,
                status="failed",
                current_step=current_step,
                error=ErrorDetail(
                    code=row.get("error_code") or (wf_run.get("error_code") if wf_run else "PROCESSING_FAILED") or "PROCESSING_FAILED",
                    message=row.get("error_message") or (wf_run.get("error_message") if wf_run else "Consultation processing failed.") or "Processing failed."
                ),
                created_at=created_at,
                updated_at=updated_at
            )

        # Input metadata
        input_meta = InputMetadata(
            filename=row.get("original_filename") or "unknown",
            media_type=row.get("media_type") or "application/octet-stream",
            duration_seconds=float(row.get("duration_seconds") or 0.0)
        )

        # Transcript turns
        raw_transcript = row.get("transcript") or []
        transcript_turns = [
            TranscriptTurn(
                start=float(t.get("start", 0.0)),
                end=float(t.get("end", 0.0)),
                speaker=str(t.get("speaker", "Unknown")),
                text=str(t.get("text", ""))
            )
            for t in raw_transcript
        ] if raw_transcript else None

        # Medical record
        raw_med = row.get("medical_record")
        medical_record = None
        requires_review = True

        if raw_med:
            med_items = [MedicationItem(**m) for m in raw_med.get("medications", [])]
            test_items = [TestItem(**t) for t in raw_med.get("tests", [])]
            follow_up_raw = raw_med.get("follow_up") or {}
            follow_up_item = FollowUpItem(**follow_up_raw) if isinstance(follow_up_raw, dict) else FollowUpItem()
            requires_review = raw_med.get("requires_doctor_review", True)

            medical_record = MedicalRecord(
                medications=med_items,
                tests=test_items,
                instructions=raw_med.get("instructions", []),
                follow_up=follow_up_item,
                warnings=raw_med.get("warnings", []),
                symptoms_mentioned=raw_med.get("symptoms_mentioned", []),
                uncertain_items=raw_med.get("uncertain_items", []),
                requires_doctor_review=requires_review
            )

        # Validation summary
        raw_val = row.get("validation_result")
        val_summary = None
        if raw_val:
            val_summary = ValidationSummary(
                status=raw_val.get("status", "valid"),
                errors=raw_val.get("errors", []),
                warnings=raw_val.get("warnings", [])
            )

        return ConsultationWorkflowStatusResponse(
            consultation_id=consultation_id,
            status=status_val,
            current_step=current_step,
            progress=None,
            requires_doctor_review=requires_review,
            input=input_meta,
            media_storage_path=row.get("media_storage_path"),
            transcript=transcript_turns,
            medical_record=medical_record,
            validation=val_summary,
            created_at=created_at,
            updated_at=updated_at
        )

    # -------------------------------------------------------------
    # Workflow History (Observability)
    # -------------------------------------------------------------
    def get_workflow_history(self, consultation_id: str) -> Optional[WorkflowHistoryResponse]:
        """
        Retrieves full workflow history including step executions,
        agent runs, retry counts, errors, and timestamps.
        """
        history = self.workflow_repo.get_workflow_history(consultation_id)
        if not history:
            return None

        wf_run = history["workflow_run"]
        steps = [
            WorkflowStepItem(
                id=s.get("id"),
                step_name=s["step_name"],
                step_type=s["step_type"],
                status=s["status"],
                attempt=s.get("attempt", 1),
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                error=s.get("error"),
                input_reference=s.get("input_reference"),
                output_reference=s.get("output_reference")
            )
            for s in history.get("steps", [])
        ]

        agent_execs = [
            AgentExecutionItem(
                id=a.get("id"),
                agent_name=a["agent_name"],
                agent_version=a.get("agent_version", "1.0.0"),
                status=a["status"],
                attempt=a.get("attempt", 1),
                started_at=a.get("started_at"),
                completed_at=a.get("completed_at"),
                error=a.get("error"),
                metadata=a.get("metadata")
            )
            for a in history.get("agent_executions", [])
        ]

        return WorkflowHistoryResponse(
            consultation_id=consultation_id,
            workflow_run_id=wf_run["id"],
            status=wf_run["status"],
            current_step=wf_run.get("current_step"),
            workflow_version=wf_run.get("workflow_version", "1.0.0"),
            started_at=wf_run.get("started_at"),
            completed_at=wf_run.get("completed_at"),
            failed_at=wf_run.get("failed_at"),
            error_code=wf_run.get("error_code"),
            error_message=wf_run.get("error_message"),
            steps=steps,
            agent_executions=agent_execs
        )

    # -------------------------------------------------------------
    # Doctor Review Sign-Off
    # -------------------------------------------------------------
    def review_consultation(
        self,
        consultation_id: str,
        doctor_name: str,
        decision: str = "approved",
        notes: Optional[str] = None,
        corrected_medical_record: Optional[Dict[str, Any]] = None
    ) -> DoctorReviewResponse:
        """
        Executes physician review sign-off via SaveDoctorReviewTool.
        Transitions consultation and workflow status to 'completed'.
        """
        tool = SaveDoctorReviewTool()
        context = ToolContext(caller_id=doctor_name, role="doctor", permissions=["*"])
        params = {
            "consultation_id": consultation_id,
            "doctor_name": doctor_name,
            "decision": decision,
            "notes": notes,
            "corrected_medical_record": corrected_medical_record
        }
        res = tool.execute(params=params, context=context)
        if not res.success:
            raise ValueError(f"Failed to submit doctor review: {res.error}")

        return DoctorReviewResponse(
            consultation_id=consultation_id,
            status="completed",
            reviewed_by=doctor_name,
            decision=decision,
            message="Consultation successfully approved and signed by physician."
        )

    def list_consultations(self, limit: int = 50, offset: int = 0) -> ConsultationListResponse:
        """
        Lists consultations from Supabase in reverse chronological order.
        """
        rows, total = self.repository.list_all(limit=limit, offset=offset)
        items: List[ConsultationListItem] = []
        for r in rows:
            items.append(
                ConsultationListItem(
                    consultation_id=str(r.get("id")),
                    status=str(r.get("status", "unknown")),
                    original_filename=r.get("original_filename"),
                    media_type=r.get("media_type"),
                    duration_seconds=float(r.get("duration_seconds")) if r.get("duration_seconds") is not None else None,
                    created_at=r.get("created_at"),
                    updated_at=r.get("updated_at")
                )
            )

        return ConsultationListResponse(items=items, total=total)

    def get_consultation_progress(self, consultation_id: str) -> Optional[Any]:
        """
        Calculates authoritative real-time progress for consultation processing UI.
        Distinguishes real statuses (pending, running, completed, failed, not_configured)
        without fabricating timers or artificial percentages.
        """
        from datetime import datetime, timezone
        from src.schemas.guideline_schema import WorkflowProgressStep, WorkflowProgressResponse
        from api.repositories.guideline_repository import get_guideline_repository
        from api.repositories.summary_repository import get_summary_repository

        consultation = self.repository.get_by_id(consultation_id)
        if not consultation:
            return None

        # Fetch workflow run
        wf_run = self.workflow_repo.get_workflow_run_by_consultation(consultation_id)
        steps = self.workflow_repo.get_workflow_steps(wf_run["id"]) if wf_run else []
        step_dict = {s["step_type"]: s for s in steps}

        # Fetch guideline status
        gl_repo = get_guideline_repository()
        gl_data = gl_repo.get_by_consultation(consultation_id)

        # Fetch patient summaries
        sm_repo = get_summary_repository()
        summaries = sm_repo.list_summaries_for_consultation(consultation_id)

        # Elapsed time calculation
        start_time_iso = wf_run.get("started_at") if wf_run else consultation.get("created_at")
        elapsed_sec = 0.0
        if start_time_iso:
            try:
                start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
                end_time_iso = wf_run.get("completed_at") if wf_run and wf_run.get("completed_at") else None
                end_dt = datetime.fromisoformat(end_time_iso.replace("Z", "+00:00")) if end_time_iso else datetime.now(timezone.utc)
                elapsed_sec = max(0.0, round((end_dt - start_dt).total_seconds(), 1))
            except Exception:
                elapsed_sec = float(consultation.get("duration_seconds") or 0.0)

        c_status = (consultation.get("status") or "queued").lower()

        # Step 2: Audio Processing & Diarization
        s2_data = step_dict.get("audio_processing")
        if s2_data:
            s2_status = s2_data.get("status", "pending")
        elif c_status in ("processing_audio", "diarizing"):
            s2_status = "running"
        elif c_status in ("transcribing", "extracting_medical_data", "pending_doctor_review", "completed"):
            s2_status = "completed"
        else:
            s2_status = "pending"

        # Step 3: Speech-to-Text Transcription
        s3_data = step_dict.get("transcription")
        if s3_data:
            s3_status = s3_data.get("status", "pending")
        elif c_status == "transcribing":
            s3_status = "running"
        elif c_status in ("extracting_medical_data", "validating_medical_data", "pending_doctor_review", "completed"):
            s3_status = "completed"
        else:
            s3_status = "pending"

        # Step 4: Medical Information Extraction
        s4_data = step_dict.get("medical_extraction")
        if s4_data:
            s4_status = s4_data.get("status", "pending")
        elif c_status in ("extracting_medical_data", "validating_medical_data"):
            s4_status = "running"
        elif c_status in ("pending_doctor_review", "completed"):
            s4_status = "completed"
        else:
            s4_status = "pending"

        # Step 5: Clinical Safety Guardrails
        s5_data = step_dict.get("medical_guardrail")
        if s5_data:
            s5_status = s5_data.get("status", "pending")
        elif c_status == "validating_medical_data":
            s5_status = "running"
        elif c_status in ("pending_doctor_review", "completed"):
            s5_status = "completed"
        elif c_status == "needs_review":
            s5_status = "needs_review"
        else:
            s5_status = "pending"

        # Step 6: Medical Guideline Cross-Referencing
        if gl_data:
            gl_st = gl_data.get("status")
            if gl_st in ("COMPLETED_WITH_FINDINGS", "COMPLETED_NO_FINDINGS"):
                s6_status = "completed"
                s6_desc = f"Verified against {len(gl_data.get('guidelines_evaluated', []))} national guidelines"
            elif gl_st == "NO_VERIFIED_SOURCE":
                s6_status = "not_configured"
                s6_desc = "No verified clinical guideline currently configured for this topic"
            elif gl_st == "FAILED":
                s6_status = "failed"
                s6_desc = "Guideline cross-referencing encountered an error"
            else:
                s6_status = "running"
                s6_desc = "Evaluating against verified treatment guidelines..."
        elif c_status in ("pending_doctor_review", "completed"):
            s6_status = "not_configured"
            s6_desc = "Medical guideline cross-reference is not currently enabled for this record"
        else:
            s6_status = "pending"
            s6_desc = "Waiting for extracted clinical data..."

        # Step 7: Doctor Review & Sign-Off
        med_rec = consultation.get("medical_record") or {}
        doc_rev = med_rec.get("doctor_review")
        if c_status == "completed" or (doc_rev and doc_rev.get("decision") in ("approved", "amended")):
            s7_status = "completed"
        elif c_status == "pending_doctor_review":
            s7_status = "running"
        elif c_status == "failed":
            s7_status = "failed"
        else:
            s7_status = "pending"

        # Step 8: Patient Summary Generation & Approval
        approved_summaries = [s for s in summaries if s.get("status") == "SUMMARY_APPROVED"]
        pending_summaries = [s for s in summaries if s.get("status") in ("PENDING_SUMMARY_REVIEW", "GENERATING_SUMMARY", "VALIDATING_SUMMARY")]
        review_needed_summaries = [s for s in summaries if s.get("status") in ("NEEDS_REVIEW", "SUMMARY_FAILED")]

        if approved_summaries:
            s8_status = "completed"
            s8_desc = f"Approved patient summary available in {', '.join([s.get('language', 'en').upper() for s in approved_summaries])}"
        elif pending_summaries:
            s8_status = "running"
            s8_desc = "Patient summary generated; waiting for doctor approval"
        elif review_needed_summaries:
            s8_status = "needs_review"
            s8_desc = "Generated summary flagged by guardrails for physician review"
        elif s7_status == "completed":
            s8_status = "pending"
            s8_desc = "Ready for patient summary generation"
        else:
            s8_status = "pending"
            s8_desc = "Waiting for doctor consultation review and sign-off"

        progress_steps = [
            WorkflowProgressStep(
                step_id="transcription",
                title="Transcribing audio...",
                description="Audio extraction, normalization, and speaker diarization.",
                status=s2_status
            ),
            WorkflowProgressStep(
                step_id="extraction",
                title="Extracting clinical information...",
                description="Structuring medications, dosages, symptoms, and tests.",
                status=s4_status
            ),
            WorkflowProgressStep(
                step_id="guardrail",
                title="Checking medications & safety...",
                description="Deterministic verification of drug strengths, routes, and speakers.",
                status=s5_status
            ),
            WorkflowProgressStep(
                step_id="guidelines",
                title="Cross-referencing medical guidelines...",
                description=s6_desc,
                status=s6_status
            ),
            WorkflowProgressStep(
                step_id="doctor_review",
                title="Waiting for doctor approval...",
                description="Physician verification and sign-off of extracted clinical record.",
                status=s7_status
            ),
            WorkflowProgressStep(
                step_id="summary_generation",
                title="Preparing your visit summary...",
                description=s8_desc,
                status=s8_status
            )
        ]

        completed_count = sum(1 for s in progress_steps if s.status == "completed")
        is_term = c_status in ("completed", "failed") and (s8_status == "completed" or c_status == "failed")
        can_view = len(approved_summaries) > 0

        return WorkflowProgressResponse(
            consultation_id=consultation_id,
            status=c_status,
            current_step=wf_run.get("current_step") if wf_run else c_status,
            elapsed_time_sec=elapsed_sec,
            total_steps=len(progress_steps),
            completed_steps=completed_count,
            is_terminal=is_term,
            can_patient_view_summary=can_view,
            steps=progress_steps
        )



_consultation_service_instance: Optional[ConsultationService] = None


def get_consultation_service() -> ConsultationService:
    """Returns singleton ConsultationService instance."""
    global _consultation_service_instance
    if _consultation_service_instance is None:
        _consultation_service_instance = ConsultationService()
    return _consultation_service_instance
