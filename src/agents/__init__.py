"""
PostVisit AI - Agents Package
"""

from src.agents.base import BaseAgent, AgentResult, WorkflowContext, RetryPolicy
from src.agents.registry import AgentRegistry, get_agent_registry
from src.agents.medical_extraction_agent import MedicalExtractionAgent
from src.agents.patient_summary_agent import PatientSummaryAgent
from src.agents.guideline_agent import GuidelineCrossReferenceAgent

# Automatically register default agents in registry
_registry = get_agent_registry()
if not _registry.get(MedicalExtractionAgent.name):
    _registry.register(MedicalExtractionAgent())
if not _registry.get(PatientSummaryAgent.name):
    _registry.register(PatientSummaryAgent())
if not _registry.get(GuidelineCrossReferenceAgent.name):
    _registry.register(GuidelineCrossReferenceAgent())

__all__ = [
    "BaseAgent",
    "AgentResult",
    "WorkflowContext",
    "RetryPolicy",
    "AgentRegistry",
    "get_agent_registry",
    "MedicalExtractionAgent",
    "PatientSummaryAgent",
    "GuidelineCrossReferenceAgent",
]


