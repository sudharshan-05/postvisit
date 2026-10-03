"""
PostVisit AI - Agent Registry
Provides central discovery, registration, and lifecycle management for AI agents.
Enables adding new agents (PatientSummary, Translation, DrugInteraction)
without modifying the workflow orchestrator.
"""

import logging
from typing import Dict, Any, Optional, List
from src.agents.base import BaseAgent

logger = logging.getLogger("postvisit.agents.registry")


class AgentRegistry:
    """
    Central registry for discovering and executing clinical agents.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Registers an agent instance with the registry."""
        if not agent.name:
            raise ValueError("Agent must have a valid non-empty 'name'.")
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} v{agent.version}")

    def get(self, name: str) -> Optional[BaseAgent]:
        """Retrieves an agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        """Returns metadata for all registered agents."""
        return [
            {
                "name": agent.name,
                "version": agent.version,
                "description": agent.description,
                "permissions": agent.permissions,
                "timeout_seconds": agent.timeout_seconds,
                "max_attempts": agent.retry_policy.max_attempts
            }
            for agent in self._agents.values()
        ]

    def clear(self) -> None:
        """Clears all registered agents (useful for test isolation)."""
        self._agents.clear()


_default_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Returns singleton AgentRegistry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = AgentRegistry()
    return _default_registry
