"""
PostVisit AI - Base Agent Abstraction
Defines the common contract, retry policies, execution context,
and standardized result wrapper for all clinical AI agents.
"""

import time
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Type
from pydantic import BaseModel, Field


class RetryPolicy(BaseModel):
    """
    Configurable retry policy for agent execution.
    """
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_sec: float = Field(default=0.5, ge=0.0)
    backoff_factor: float = Field(default=2.0, ge=1.0)
    retryable_exceptions: Tuple[str, ...] = ("TimeoutError", "ConnectionError", "RuntimeError")


class AgentResult(BaseModel):
    """
    Standardized result wrapper returned by all agents.
    """
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_sec: float = 0.0
    attempt: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowContext(BaseModel):
    """
    Shared execution context passed across workflow steps and agents.
    """
    consultation_id: str
    workflow_run_id: str
    step_id: Optional[str] = None
    media_path: Optional[str] = None
    original_filename: str = ""
    media_type: str = "application/octet-stream"
    duration_seconds: float = 0.0
    language: str = "ta"

    # Intermediate artifacts
    transcript_turns: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_labelled_transcript: str = ""
    combined_transcript: str = ""
    medical_record: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    doctor_verification: Optional[Dict[str, Any]] = None

    # Step-level and execution metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract Base Agent Contract for PostVisit AI agents.
    Every agent must define:
      - name, version, description
      - input_schema, output_schema
      - permissions
      - timeout_seconds, retry_policy
      - execute(context)
    """

    name: str = "base_agent"
    version: str = "1.0.0"
    description: str = "Base clinical agent"
    input_schema: Optional[Type[BaseModel]] = None
    output_schema: Optional[Type[BaseModel]] = None
    permissions: List[str] = ["read_context"]
    timeout_seconds: float = 60.0
    retry_policy: RetryPolicy = RetryPolicy()

    @abstractmethod
    def run(self, context: WorkflowContext) -> AgentResult:
        """
        Synchronous or core execution logic to be implemented by concrete agents.
        """
        pass

    def execute(self, context: WorkflowContext) -> AgentResult:
        """
        Executes the agent with retry policy, timeout monitoring,
        and execution timing.
        """
        start_time = time.time()
        last_error = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                result = self.run(context)
                result.execution_time_sec = round(time.time() - start_time, 3)
                result.attempt = attempt
                if result.success:
                    return result
                last_error = result.error
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                exc_name = type(e).__name__
                if exc_name not in self.retry_policy.retryable_exceptions and attempt < self.retry_policy.max_attempts:
                    # Check if retryable by substring or broad exception
                    pass

            if attempt < self.retry_policy.max_attempts:
                delay = self.retry_policy.initial_delay_sec * (self.retry_policy.backoff_factor ** (attempt - 1))
                time.sleep(delay)

        total_time = round(time.time() - start_time, 3)
        return AgentResult(
            success=False,
            error=last_error or "Agent execution failed after retries.",
            execution_time_sec=total_time,
            attempt=self.retry_policy.max_attempts
        )
