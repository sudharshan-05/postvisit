"""
PostVisit AI - MCP-Compatible Internal Tool Abstraction
Provides the standard Tool contract for clinical capabilities.
Enforces authentication, authorization, input/output validation, and audit logging.
"""

import time
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("postvisit.tools")


class ToolContext(BaseModel):
    """
    Context passed into tool executions containing caller identity and security scope.
    """
    caller_id: str = Field(default="system")
    role: str = Field(default="system")  # "doctor", "system", "worker", "patient"
    permissions: List[str] = Field(default_factory=lambda: ["*"])
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ToolResult(BaseModel):
    """
    Standardized tool execution outcome.
    """
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_sec: float = 0.0
    audit_entry: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """
    MCP-compatible tool abstraction.
    Every tool must define name, description, input schema, output schema,
    required permissions, and execute().
    """

    name: str = "base_tool"
    description: str = "Base clinical tool"
    input_schema: Optional[Type[BaseModel]] = None
    output_schema: Optional[Type[BaseModel]] = None
    required_permissions: List[str] = []

    def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """
        Controlled execution wrapper performing:
        1. Authentication verification
        2. Authorization (permission check)
        3. Input schema validation
        4. Tool execution
        5. Output validation
        6. Audit logging
        """
        start_time = time.time()
        audit = {
            "tool_name": self.name,
            "caller_id": context.caller_id,
            "role": context.role,
            "correlation_id": context.correlation_id,
            "status": "pending"
        }

        # 1. Authentication
        if not context.caller_id:
            audit["status"] = "unauthenticated"
            return ToolResult(
                success=False,
                error="Unauthenticated tool execution: caller_id required.",
                audit_entry=audit
            )

        # 2. Authorization
        if "*" not in context.permissions:
            for perm in self.required_permissions:
                if perm not in context.permissions:
                    audit["status"] = "unauthorized"
                    logger.warning(
                        f"Unauthorized tool invocation: {context.caller_id} lacks permission '{perm}' for '{self.name}'"
                    )
                    return ToolResult(
                        success=False,
                        error=f"Permission denied: Missing required permission '{perm}'.",
                        audit_entry=audit
                    )

        # 3. Input Validation
        validated_input = params
        if self.input_schema is not None:
            try:
                validated_input = self.input_schema(**params).model_dump()
            except ValidationError as e:
                audit["status"] = "invalid_input"
                return ToolResult(
                    success=False,
                    error=f"Input validation failed: {str(e)}",
                    audit_entry=audit
                )

        # 4. Tool Execution
        try:
            raw_result = self.run(validated_input, context)
        except Exception as e:
            audit["status"] = "execution_error"
            logger.error(f"Error executing tool '{self.name}': {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Execution failure: {str(e)}",
                execution_time_sec=round(time.time() - start_time, 3),
                audit_entry=audit
            )

        # 5. Output Validation
        validated_output = raw_result
        if self.output_schema is not None and raw_result is not None:
            try:
                if isinstance(raw_result, dict):
                    validated_output = self.output_schema(**raw_result).model_dump()
            except ValidationError as e:
                audit["status"] = "invalid_output"
                return ToolResult(
                    success=False,
                    error=f"Output validation failed: {str(e)}",
                    execution_time_sec=round(time.time() - start_time, 3),
                    audit_entry=audit
                )

        # 6. Audit Logging
        exec_duration = round(time.time() - start_time, 3)
        audit["status"] = "completed"
        audit["duration_sec"] = exec_duration
        logger.info(
            f"Tool executed [tool={self.name}, caller={context.caller_id}, "
            f"correlation_id={context.correlation_id}, duration={exec_duration}s]"
        )

        return ToolResult(
            success=True,
            data=validated_output,
            execution_time_sec=exec_duration,
            audit_entry=audit
        )

    @abstractmethod
    def run(self, params: Dict[str, Any], context: ToolContext) -> Any:
        """Concrete tool implementation logic."""
        pass
