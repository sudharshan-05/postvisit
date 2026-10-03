"""
PostVisit AI - Tool Registry
Central discovery and registry for MCP-compatible clinical tools.
"""

from typing import Dict, Any, Optional, List
from src.tools.base import BaseTool
from src.tools.clinical_tools import (
    GetConsultationTool,
    GetTranscriptTool,
    GetMedicalRecordTool,
    SaveDoctorReviewTool,
    GeneratePatientSummaryTool,
    CreateFollowUpTool
)


class ToolRegistry:
    """
    Manages clinical tool instances and metadata discovery.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        # Pre-register default clinical tools
        self.register(GetConsultationTool())
        self.register(GetTranscriptTool())
        self.register(GetMedicalRecordTool())
        self.register(SaveDoctorReviewTool())
        self.register(GeneratePatientSummaryTool())
        self.register(CreateFollowUpTool())

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "required_permissions": tool.required_permissions,
                "input_schema": tool.input_schema.model_json_schema() if tool.input_schema else None,
                "output_schema": tool.output_schema.model_json_schema() if tool.output_schema else None,
            }
            for tool in self._tools.values()
        ]


_default_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _default_tool_registry
    if _default_tool_registry is None:
        _default_tool_registry = ToolRegistry()
    return _default_tool_registry
