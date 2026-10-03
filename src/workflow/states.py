"""
PostVisit AI - Workflow States and Transitions
Defines explicit workflow states for durable consultation processing,
transitions, summary review lifecycles, and terminal state checks.
"""

from enum import Enum
from typing import Set


class WorkflowState(str, Enum):
    """
    Explicit lifecycle states for clinical consultation and patient summary workflows.
    """
    # Stage 1-3 Consultation Processing States
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    VALIDATING_INPUT = "VALIDATING_INPUT"
    PROCESSING_AUDIO = "PROCESSING_AUDIO"
    DIARIZING = "DIARIZING"
    TRANSCRIBING = "TRANSCRIBING"
    VALIDATING_TRANSCRIPT = "VALIDATING_TRANSCRIPT"
    EXTRACTING_MEDICAL_DATA = "EXTRACTING_MEDICAL_DATA"
    VALIDATING_MEDICAL_DATA = "VALIDATING_MEDICAL_DATA"
    PERSISTING_RESULT = "PERSISTING_RESULT"
    PENDING_DOCTOR_REVIEW = "PENDING_DOCTOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

    # Stage 4 Patient Summary Review States
    SUMMARY_QUEUED = "SUMMARY_QUEUED"
    GENERATING_SUMMARY = "GENERATING_SUMMARY"
    VALIDATING_SUMMARY = "VALIDATING_SUMMARY"
    PENDING_SUMMARY_REVIEW = "PENDING_SUMMARY_REVIEW"
    SUMMARY_APPROVED = "SUMMARY_APPROVED"
    SUMMARY_REJECTED = "SUMMARY_REJECTED"
    SUMMARY_FAILED = "SUMMARY_FAILED"

    @property
    def is_terminal(self) -> bool:
        """Returns True if the state represents an end of processing."""
        return self in (
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.NEEDS_REVIEW,
            WorkflowState.SUMMARY_APPROVED,
            WorkflowState.SUMMARY_REJECTED,
            WorkflowState.SUMMARY_FAILED,
        )

    @property
    def is_active(self) -> bool:
        """Returns True if the workflow is currently processing."""
        return not self.is_terminal and self not in (
            WorkflowState.PENDING_DOCTOR_REVIEW,
            WorkflowState.PENDING_SUMMARY_REVIEW
        )


# Valid state transitions
VALID_TRANSITIONS = {
    WorkflowState.RECEIVED: {WorkflowState.QUEUED, WorkflowState.FAILED},
    WorkflowState.QUEUED: {WorkflowState.VALIDATING_INPUT, WorkflowState.FAILED},
    WorkflowState.VALIDATING_INPUT: {
        WorkflowState.PROCESSING_AUDIO,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.PROCESSING_AUDIO: {
        WorkflowState.DIARIZING,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.DIARIZING: {
        WorkflowState.TRANSCRIBING,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.TRANSCRIBING: {
        WorkflowState.VALIDATING_TRANSCRIPT,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.VALIDATING_TRANSCRIPT: {
        WorkflowState.EXTRACTING_MEDICAL_DATA,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.EXTRACTING_MEDICAL_DATA: {
        WorkflowState.VALIDATING_MEDICAL_DATA,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.VALIDATING_MEDICAL_DATA: {
        WorkflowState.PERSISTING_RESULT,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.PERSISTING_RESULT: {
        WorkflowState.PENDING_DOCTOR_REVIEW,
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
    },
    WorkflowState.PENDING_DOCTOR_REVIEW: {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.COMPLETED: {WorkflowState.SUMMARY_QUEUED},
    WorkflowState.FAILED: set(),
    WorkflowState.NEEDS_REVIEW: {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.SUMMARY_QUEUED,
        WorkflowState.PENDING_SUMMARY_REVIEW,
    },

    # Summary lifecycle transitions
    WorkflowState.SUMMARY_QUEUED: {
        WorkflowState.GENERATING_SUMMARY,
        WorkflowState.SUMMARY_FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.GENERATING_SUMMARY: {
        WorkflowState.VALIDATING_SUMMARY,
        WorkflowState.SUMMARY_FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.VALIDATING_SUMMARY: {
        WorkflowState.PENDING_SUMMARY_REVIEW,
        WorkflowState.SUMMARY_FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.PENDING_SUMMARY_REVIEW: {
        WorkflowState.SUMMARY_APPROVED,
        WorkflowState.SUMMARY_REJECTED,
        WorkflowState.SUMMARY_FAILED,
        WorkflowState.NEEDS_REVIEW,
    },
    WorkflowState.SUMMARY_APPROVED: set(),
    WorkflowState.SUMMARY_REJECTED: {WorkflowState.SUMMARY_QUEUED},
    WorkflowState.SUMMARY_FAILED: {WorkflowState.SUMMARY_QUEUED},
}


def can_transition(current: WorkflowState, target: WorkflowState) -> bool:
    """Validates if transition from current state to target state is permissible."""
    allowed: Set[WorkflowState] = VALID_TRANSITIONS.get(current, set())
    return target in allowed
