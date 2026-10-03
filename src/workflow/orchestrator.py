"""
PostVisit AI - Workflow Orchestrator
Controlled runtime engine coordinating services, agents, guardrails,
retries, idempotency, and persistent state transitions across Supabase.
"""

import os
import sys
import time
import uuid
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow.states import WorkflowState
from src.agents.base import WorkflowContext, AgentResult
from src.agents.registry import AgentRegistry, get_agent_registry
from src.guardrails.base import GuardrailResult
from src.guardrails.input_guardrail import InputGuardrail
from src.guardrails.audio_guardrail import AudioQualityGuardrail
from src.guardrails.transcript_guardrail import TranscriptGuardrail
from src.guardrails.medical_output_guardrail import MedicalOutputGuardrail
from api.repositories.consultation_repository import ConsultationRepository, get_consultation_repository
from api.repositories.workflow_repository import WorkflowRepository, get_workflow_repository

logger = logging.getLogger("postvisit.workflow.orchestrator")


class WorkflowOrchestrator:
    """
    Traffic controller and state machine executor for PostVisit AI consultation pipelines.
    Enforces deterministic service calls, LLM agent boundaries, guardrails, and persistent states.
    """

    def __init__(
        self,
        workflow_repo: Optional[WorkflowRepository] = None,
        consultation_repo: Optional[ConsultationRepository] = None,
        agent_registry: Optional[AgentRegistry] = None,
        input_guardrail: Optional[InputGuardrail] = None,
        audio_guardrail: Optional[AudioQualityGuardrail] = None,
        transcript_guardrail: Optional[TranscriptGuardrail] = None,
        medical_guardrail: Optional[MedicalOutputGuardrail] = None,
    ):
        self.workflow_repo = workflow_repo or get_workflow_repository()
        self.consultation_repo = consultation_repo or get_consultation_repository()
        self.agent_registry = agent_registry or get_agent_registry()

        self.input_guardrail = input_guardrail or InputGuardrail()
        self.audio_guardrail = audio_guardrail or AudioQualityGuardrail()
        self.transcript_guardrail = transcript_guardrail or TranscriptGuardrail()
        self.medical_guardrail = medical_guardrail or MedicalOutputGuardrail()

    @staticmethod
    def _compute_hash(data: Any) -> str:
        """Computes deterministic SHA-256 hash for idempotency and step caching."""
        if isinstance(data, (bytes, bytearray)):
            return hashlib.sha256(data).hexdigest()
        raw_str = str(data)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def execute_workflow(
        self,
        consultation_id: str,
        workflow_run_id: str,
        media_path: str,
        original_filename: str,
        media_type: str = "application/octet-stream",
        language: str = "ta"
    ) -> Dict[str, Any]:
        """
        Executes the durable multi-stage consultation workflow from start to finish.
        Transitions:
          QUEUED -> VALIDATING_INPUT -> PROCESSING_AUDIO -> DIARIZING ->
          TRANSCRIBING -> VALIDATING_TRANSCRIPT -> EXTRACTING_MEDICAL_DATA ->
          VALIDATING_MEDICAL_DATA -> PERSISTING_RESULT -> PENDING_DOCTOR_REVIEW
        """
        logger.info(
            f"Starting workflow orchestration [consultation_id={consultation_id}, "
            f"workflow_run_id={workflow_run_id}, file={original_filename}]"
        )

        context = WorkflowContext(
            consultation_id=consultation_id,
            workflow_run_id=workflow_run_id,
            media_path=media_path,
            original_filename=original_filename,
            media_type=media_type,
            language=language
        )

        # -------------------------------------------------------------
        # Step 1: Input Guardrail Validation
        # -------------------------------------------------------------
        step_input = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.VALIDATING_INPUT.value,
            step_type="guardrail",
            input_reference={"filename": original_filename, "media_type": media_type}
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.VALIDATING_INPUT.value,
            current_step=WorkflowState.VALIDATING_INPUT.value
        )

        input_result = self.input_guardrail.validate(
            file_path=media_path,
            filename=original_filename,
            mime_type=media_type
        )

        if not input_result.passed:
            logger.warning(
                f"Input guardrail rejected file [{original_filename}]: {input_result.message}"
            )
            self.workflow_repo.update_workflow_step(
                step_id=step_input["id"],
                status="failed",
                error=input_result.message
            )
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=WorkflowState.FAILED.value,
                current_step=WorkflowState.VALIDATING_INPUT.value,
                error_code=input_result.error_code or "INPUT_GUARDRAIL_FAILED",
                error_message=input_result.message
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code=input_result.error_code or "INPUT_GUARDRAIL_FAILED",
                error_message=input_result.message or "Input validation failed."
            )
            return {"status": "failed", "error": input_result.message}

        self.workflow_repo.update_workflow_step(
            step_id=step_input["id"],
            status="completed",
            output_reference=input_result.details
        )

        # -------------------------------------------------------------
        # Step 2: Audio Processing & Audio Quality Guardrail
        # -------------------------------------------------------------
        step_audio = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.PROCESSING_AUDIO.value,
            step_type="service",
            input_reference={"media_path": media_path}
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.PROCESSING_AUDIO.value,
            current_step=WorkflowState.PROCESSING_AUDIO.value
        )

        try:
            from src.audio_processor import load_and_normalize_audio
            wav, sr = load_and_normalize_audio(media_path)
            duration_sec = round(float(wav.shape[-1] / sr), 2)
            context.duration_seconds = duration_sec
        except Exception as e:
            err_msg = f"Audio normalization failed: {str(e)}"
            logger.error(err_msg, exc_info=True)
            self.workflow_repo.update_workflow_step(
                step_id=step_audio["id"],
                status="failed",
                error=err_msg
            )
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=WorkflowState.FAILED.value,
                current_step=WorkflowState.PROCESSING_AUDIO.value,
                error_code="AUDIO_DECODE_FAILED",
                error_message=err_msg
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code="AUDIO_DECODE_FAILED",
                error_message=err_msg
            )
            return {"status": "failed", "error": err_msg}

        # Run Audio Quality Guardrail
        audio_quality_result = self.audio_guardrail.validate(wav, sr)
        if not audio_quality_result.passed:
            logger.warning(
                f"Audio quality guardrail triggered: {audio_quality_result.message}"
            )
            target_status = WorkflowState.NEEDS_REVIEW.value if audio_quality_result.action == "NEEDS_REVIEW" else WorkflowState.FAILED.value
            self.workflow_repo.update_workflow_step(
                step_id=step_audio["id"],
                status="needs_review" if target_status == WorkflowState.NEEDS_REVIEW.value else "failed",
                error=audio_quality_result.message
            )
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=target_status,
                current_step=WorkflowState.PROCESSING_AUDIO.value,
                error_code=audio_quality_result.error_code or "AUDIO_QUALITY_INSUFFICIENT",
                error_message=audio_quality_result.message
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code=audio_quality_result.error_code or "AUDIO_QUALITY_INSUFFICIENT",
                error_message=audio_quality_result.message or "Audio quality insufficient."
            )
            return {"status": target_status.lower(), "error": audio_quality_result.message}

        self.workflow_repo.update_workflow_step(
            step_id=step_audio["id"],
            status="completed",
            output_reference={"duration_seconds": duration_sec, "sample_rate": sr}
        )

        # -------------------------------------------------------------
        # Step 3: Diarization & Speech Recognition (ASR)
        # -------------------------------------------------------------
        step_asr = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.TRANSCRIBING.value,
            step_type="service",
            max_attempts=3,
            input_reference={"duration_sec": duration_sec, "language": language}
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.TRANSCRIBING.value,
            current_step=WorkflowState.TRANSCRIBING.value
        )

        from src.diarization import diarize_and_transcribe

        diar_result = None
        asr_error = None
        for attempt in range(1, 4):
            try:
                logger.info(f"Executing Diarization & ASR [attempt {attempt}/3]...")
                diar_result = diarize_and_transcribe(
                    wav,
                    sample_rate=sr,
                    language=language,
                    strategy="ctc"
                )
                break
            except Exception as ex:
                asr_error = str(ex)
                logger.warning(f"ASR attempt {attempt} failed: {ex}")
                self.workflow_repo.update_workflow_step(
                    step_id=step_asr["id"],
                    status="retrying" if attempt < 3 else "failed",
                    attempt=attempt,
                    error=asr_error
                )
                if attempt < 3:
                    time.sleep(0.5 * attempt)

        if not diar_result:
            err_msg = f"Speech recognition failed after 3 attempts: {asr_error}"
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=WorkflowState.FAILED.value,
                current_step=WorkflowState.TRANSCRIBING.value,
                error_code="ASR_PIPELINE_FAILED",
                error_message=err_msg
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code="ASR_PIPELINE_FAILED",
                error_message=err_msg
            )
            return {"status": "failed", "error": err_msg}

        context.transcript_turns = diar_result.get("turns", [])
        context.speaker_labelled_transcript = diar_result.get("speaker_labelled_transcript", "")
        context.combined_transcript = diar_result.get("combined_transcript", "")

        self.workflow_repo.update_workflow_step(
            step_id=step_asr["id"],
            status="completed",
            output_reference={
                "turns_count": len(context.transcript_turns),
                "transcript_length": len(context.combined_transcript)
            }
        )

        # -------------------------------------------------------------
        # Step 4: Transcript Guardrail
        # -------------------------------------------------------------
        step_val_trans = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.VALIDATING_TRANSCRIPT.value,
            step_type="guardrail",
            input_reference={"transcript_length": len(context.combined_transcript)}
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.VALIDATING_TRANSCRIPT.value,
            current_step=WorkflowState.VALIDATING_TRANSCRIPT.value
        )

        transcript_guard_res = self.transcript_guardrail.validate(
            transcript_text=context.combined_transcript,
            speaker_turns=context.transcript_turns
        )

        if not transcript_guard_res.passed:
            logger.warning(f"Transcript guardrail flagged review: {transcript_guard_res.message}")
            target_status = WorkflowState.NEEDS_REVIEW.value if transcript_guard_res.action == "NEEDS_REVIEW" else WorkflowState.FAILED.value
            self.workflow_repo.update_workflow_step(
                step_id=step_val_trans["id"],
                status="needs_review" if target_status == WorkflowState.NEEDS_REVIEW.value else "failed",
                error=transcript_guard_res.message
            )
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=target_status,
                current_step=WorkflowState.VALIDATING_TRANSCRIPT.value,
                error_code=transcript_guard_res.error_code or "TRANSCRIPT_QUALITY_LOW",
                error_message=transcript_guard_res.message
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code=transcript_guard_res.error_code or "TRANSCRIPT_QUALITY_LOW",
                error_message=transcript_guard_res.message or "Transcript quality insufficient."
            )
            return {"status": target_status.lower(), "error": transcript_guard_res.message}

        self.workflow_repo.update_workflow_step(
            step_id=step_val_trans["id"],
            status="completed",
            output_reference=transcript_guard_res.details
        )

        # -------------------------------------------------------------
        # Step 5: Medical Extraction Agent Execution
        # -------------------------------------------------------------
        step_agent = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.EXTRACTING_MEDICAL_DATA.value,
            step_type="agent",
            input_reference={"agent": "medical_extraction"}
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.EXTRACTING_MEDICAL_DATA.value,
            current_step=WorkflowState.EXTRACTING_MEDICAL_DATA.value
        )

        agent = self.agent_registry.get("medical_extraction")
        if not agent:
            err_msg = "MedicalExtractionAgent not found in AgentRegistry."
            logger.error(err_msg)
            self.workflow_repo.update_workflow_step(step_id=step_agent["id"], status="failed", error=err_msg)
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=WorkflowState.FAILED.value,
                current_step=WorkflowState.EXTRACTING_MEDICAL_DATA.value,
                error_code="AGENT_NOT_FOUND",
                error_message=err_msg
            )
            return {"status": "failed", "error": err_msg}

        # Track agent execution audit log
        input_hash = self._compute_hash(context.speaker_labelled_transcript or context.combined_transcript)
        agent_exec_record = self.workflow_repo.create_agent_execution(
            workflow_run_id=workflow_run_id,
            step_id=step_agent["id"],
            agent_name=agent.name,
            agent_version=agent.version,
            input_hash=input_hash
        )

        agent_result: AgentResult = agent.execute(context)

        if not agent_result.success:
            err_msg = f"Agent {agent.name} failed: {agent_result.error}"
            self.workflow_repo.update_agent_execution(
                execution_id=agent_exec_record["id"],
                status="failed",
                error=err_msg
            )
            self.workflow_repo.update_workflow_step(step_id=step_agent["id"], status="failed", error=err_msg)
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=WorkflowState.FAILED.value,
                current_step=WorkflowState.EXTRACTING_MEDICAL_DATA.value,
                error_code="AGENT_EXECUTION_FAILED",
                error_message=err_msg
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code="AGENT_EXECUTION_FAILED",
                error_message=err_msg
            )
            return {"status": "failed", "error": err_msg}

        self.workflow_repo.update_agent_execution(
            execution_id=agent_exec_record["id"],
            status="completed",
            metadata=agent_result.metadata
        )
        self.workflow_repo.update_workflow_step(
            step_id=step_agent["id"],
            status="completed",
            output_reference=agent_result.metadata
        )

        # -------------------------------------------------------------
        # Step 6: Medical Output Guardrails & Safety Checks
        # -------------------------------------------------------------
        step_val_med = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.VALIDATING_MEDICAL_DATA.value,
            step_type="guardrail"
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.VALIDATING_MEDICAL_DATA.value,
            current_step=WorkflowState.VALIDATING_MEDICAL_DATA.value
        )

        med_guard_res = self.medical_guardrail.validate(
            raw_output=context.medical_record,
            transcript_text=context.speaker_labelled_transcript
        )

        if not med_guard_res.passed and med_guard_res.action == "FAILED":
            err_msg = f"Medical output guardrail failed: {med_guard_res.message}"
            logger.error(err_msg)
            self.workflow_repo.update_workflow_step(step_id=step_val_med["id"], status="failed", error=err_msg)
            self.workflow_repo.update_workflow_run_status(
                workflow_run_id=workflow_run_id,
                status=WorkflowState.FAILED.value,
                current_step=WorkflowState.VALIDATING_MEDICAL_DATA.value,
                error_code=med_guard_res.error_code or "SCHEMA_GUARDRAIL_FAILED",
                error_message=err_msg
            )
            self.consultation_repo.update_failed(
                consultation_id=consultation_id,
                error_code=med_guard_res.error_code or "SCHEMA_GUARDRAIL_FAILED",
                error_message=err_msg
            )
            return {"status": "failed", "error": err_msg}

        # Apply sanitized data from guardrail
        if med_guard_res.details.get("sanitized_data"):
            context.medical_record = med_guard_res.details["sanitized_data"]
        if med_guard_res.details.get("validation_summary"):
            context.validation_result = med_guard_res.details["validation_summary"]

        self.workflow_repo.update_workflow_step(
            step_id=step_val_med["id"],
            status="completed",
            output_reference={"valid": med_guard_res.passed}
        )

        # -------------------------------------------------------------
        # Step 7: Persisting Result (Idempotency Guaranteed)
        # -------------------------------------------------------------
        step_persist = self.workflow_repo.create_workflow_step(
            workflow_run_id=workflow_run_id,
            step_name=WorkflowState.PERSISTING_RESULT.value,
            step_type="persistence"
        )
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.PERSISTING_RESULT.value,
            current_step=WorkflowState.PERSISTING_RESULT.value
        )

        # Map turns into clean serialized list
        serialized_transcript = [
            {
                "start": round(float(t.get("start", t.get("start_sec", 0.0))), 2),
                "end": round(float(t.get("end", t.get("end_sec", 0.0))), 2),
                "speaker": str(t.get("speaker", "Unknown")),
                "text": str(t.get("text", "")).strip()
            }
            for t in context.transcript_turns
        ]

        # Update Supabase consultation record
        self.consultation_repo.update_completed(
            consultation_id=consultation_id,
            duration_seconds=context.duration_seconds,
            transcript=serialized_transcript,
            medical_record=context.medical_record or {},
            validation_result=context.validation_result or {"valid": True, "errors": [], "warnings": []}
        )

        self.workflow_repo.update_workflow_step(
            step_id=step_persist["id"],
            status="completed"
        )

        # -------------------------------------------------------------
        # Step 8: Transition to PENDING_DOCTOR_REVIEW
        # -------------------------------------------------------------
        self.workflow_repo.update_workflow_run_status(
            workflow_run_id=workflow_run_id,
            status=WorkflowState.PENDING_DOCTOR_REVIEW.value,
            current_step=WorkflowState.PENDING_DOCTOR_REVIEW.value
        )

        # Update consultation status to reflect pending doctor review
        if self.consultation_repo.is_connected:
            try:
                self.consultation_repo.client.table("consultations").update(
                    {"status": "pending_doctor_review"}
                ).eq("id", consultation_id).execute()
            except Exception as ex:
                logger.warning(f"Could not update status to pending_doctor_review in Supabase: {ex}")
        else:
            if consultation_id in self.consultation_repo._in_memory_db:
                self.consultation_repo._in_memory_db[consultation_id]["status"] = "pending_doctor_review"

        logger.info(
            f"Workflow successfully reached PENDING_DOCTOR_REVIEW [consultation_id={consultation_id}]"
        )

        return {
            "status": "pending_doctor_review",
            "consultation_id": consultation_id,
            "workflow_run_id": workflow_run_id,
            "duration_seconds": context.duration_seconds,
            "transcript_turns": len(serialized_transcript),
            "medications_count": len(context.medical_record.get("medications", []) if context.medical_record else [])
        }

    # -------------------------------------------------------------
    # Stage 4: Patient Summary Generation Step
    # -------------------------------------------------------------
    def generate_patient_summary(
        self,
        consultation_id: str,
        language: str = "en",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stage 4: Executes patient-friendly summary generation for an approved consultation.
        Creates workflow step, invokes PatientSummaryAgent, runs SummaryGuardrail,
        persists draft, and transitions to PENDING_SUMMARY_REVIEW.
        """
        from src.services.summary_service import get_summary_service
        service = get_summary_service()
        return service.generate_summary(
            consultation_id=consultation_id,
            target_language=language,
            idempotency_key=idempotency_key
        )

    # -------------------------------------------------------------
    # Crash Recovery
    # -------------------------------------------------------------

    def recover_pending_workflows(self) -> int:
        """
        Scans for active / interrupted workflows and resumes or marks them appropriately.
        Enables worker crash recovery without data loss.
        """
        active_runs = self.workflow_repo.get_active_workflow_runs()
        if not active_runs:
            logger.info("Crash recovery: No incomplete workflow runs found.")
            return 0

        logger.info(f"Crash recovery: Found {len(active_runs)} incomplete workflow runs. Resuming...")
        recovered_count = 0

        for run in active_runs:
            run_id = run["id"]
            consultation_id = run["consultation_id"]
            current_status = run.get("status")

            logger.info(f"Recovering workflow run [{run_id}, status={current_status}]...")
            steps = self.workflow_repo.get_workflow_steps(run_id)

            # If failed or pending review, nothing to recover
            if current_status in (WorkflowState.FAILED.value, WorkflowState.NEEDS_REVIEW.value, WorkflowState.COMPLETED.value):
                continue

            # Determine where the failure occurred
            last_step = steps[-1] if steps else None
            if not last_step or last_step.get("status") in ("failed", "running"):
                # Mark run as needs_review or retry
                self.workflow_repo.update_workflow_run_status(
                    workflow_run_id=run_id,
                    status=WorkflowState.NEEDS_REVIEW.value,
                    error_code="WORKER_RESTARTED",
                    error_message="Worker was restarted while this workflow was in progress."
                )
                self.consultation_repo.update_failed(
                    consultation_id=consultation_id,
                    error_code="WORKER_RESTARTED",
                    error_message="Processing was interrupted by worker restart. Needs review."
                )
                recovered_count += 1

        return recovered_count


_orchestrator_instance: Optional[WorkflowOrchestrator] = None


def get_workflow_orchestrator() -> WorkflowOrchestrator:
    """Returns singleton WorkflowOrchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = WorkflowOrchestrator()
    return _orchestrator_instance
