"""
PostVisit AI - Guardrails Base Definitions
Defines standard guardrail results, actions, and evaluation interfaces.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class GuardrailResult(BaseModel):
    """
    Standard outcome returned by all input/audio/transcript/medical guardrails.
    """
    passed: bool
    action: str = Field(
        default="CONTINUE",
        description="Next workflow action: 'CONTINUE', 'NEEDS_REVIEW', or 'FAILED'"
    )
    error_code: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
