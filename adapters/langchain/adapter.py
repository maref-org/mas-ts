# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""LangChain Agent to MAS-TS Agent Card adapter."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class LangChainAdapter:
    """Adapter for converting LangChain Agents to MAS-TS Agent Card format."""

    def __init__(self, agent: Any, agent_config: Optional[Dict] = None):
        """Initialize adapter with LangChain agent instance.

        Args:
            agent: LangChain Agent instance.
            agent_config: Optional agent configuration dict.
        """
        self.agent = agent
        self.config = agent_config or {}

    def to_agent_card(self) -> Dict:
        """Convert LangChain agent to MAS-TS Agent Card v2.0 format.

        Returns:
            Agent card dict conforming to agent_card_v2.0.json schema.
        """
        card = {
            "card_version": "2.0",
            "schema_version": "2.0",
            "agent_id": self._generate_agent_id(),
            "name": self._get_agent_name(),
            "description": self._get_description(),
            "version": self._get_version(),
            "compliance": self._get_compliance(),
            "constitution": self._get_constitution(),
            "model_backend": self._get_model_backend(),
            "capabilities": self._get_capabilities(),
            "authentication": self._get_authentication(),
            "federation": self._get_federation(),
            "governance": self._get_governance(),
            "audit": self._get_audit(),
        }
        return card

    def _generate_agent_id(self) -> str:
        """Generate URN-format agent ID."""
        name = self._get_agent_name().lower().replace(" ", "-")
        return f"urn:agent:langchain:{name}:{uuid.uuid4().hex[:12]}"

    def _get_agent_name(self) -> str:
        """Extract agent name."""
        if hasattr(self.agent, "name"):
            return str(self.agent.name)
        return self.config.get("name", "langchain-agent")  # type: ignore

    def _get_description(self) -> str:
        """Extract agent description."""
        if hasattr(self.agent, "description"):
            return str(self.agent.description)
        return self.config.get("description", "LangChain Agent")

    def _get_version(self) -> str:
        """Extract agent version."""
        return self.config.get("version", "0.1.0")

    def _get_compliance(self) -> Dict:
        """Extract compliance configuration."""
        return {
            "data_residency": self.config.get("data_residency", "LOCAL"),
            "data_classification": self.config.get("data_classification", "internal"),
            "cross_border": self.config.get("cross_border", False),
            "model_backend_location": self.config.get(
                "model_backend_location", "LOCAL"
            ),
            "audit_trail_required": self.config.get("audit_trail_required", True),
        }

    def _get_constitution(self) -> Dict:
        """Extract constitution compliance fields."""
        return {
            "envelope": {
                "message_id": str(uuid.uuid4()),
                "correlation_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "sender": self._generate_agent_id(),
            },
            "health_state": "HEALTHY",
            "heartbeat_interval_seconds": 60,
        }

    def _get_model_backend(self) -> Dict:
        """Extract model backend configuration."""
        provider = self.config.get("provider", "unknown")
        model = self.config.get("model", "unknown")
        endpoint = self.config.get("endpoint", "http://localhost:8000")

        if hasattr(self.agent, "llm"):
            llm = self.agent.llm
            if hasattr(llm, "model_name"):
                model = llm.model_name
            if hasattr(llm, "_llm_type"):
                provider = llm._llm_type

        return {
            "provider": provider,
            "model": model,
            "deployment": self.config.get("deployment", "local"),
            "endpoint": endpoint,
        }

    def _get_capabilities(self) -> list:
        """Extract agent capabilities."""
        capabilities = self.config.get("capabilities", [])

        if not capabilities and hasattr(self.agent, "tools"):
            capabilities = [
                {
                    "skill_id": f"tool-{i}",
                    "description": getattr(tool, "name", f"Tool {i}"),
                    "input_schema": {},
                    "output_schema": {},
                    "examples": [],
                }
                for i, tool in enumerate(self.agent.tools)
            ]

        if not capabilities:
            capabilities = [
                {
                    "skill_id": "default-skill",
                    "description": "Default LangChain agent capability",
                    "input_schema": {},
                    "output_schema": {},
                    "examples": [],
                }
            ]

        return capabilities

    def _get_authentication(self) -> Dict:
        """Extract authentication configuration."""
        return {
            "type": self.config.get("auth_type", "None"),
            "scopes": self.config.get("auth_scopes", []),
        }

    def _get_federation(self) -> Dict:
        """Extract federation configuration."""
        return {
            "role": self.config.get("federation_role", "primary"),
            "trust_score": self.config.get("trust_score", 1.0),
            "allowed_mcp_servers": self.config.get("allowed_mcp_servers", []),
            "permissions": self.config.get("permissions", {}),
        }

    def _get_governance(self) -> Dict:
        """Extract governance configuration."""
        return {
            "state_machine_version": self.config.get("state_machine_version", "1.0"),
            "circuit_breaker": {
                "enabled": self.config.get("circuit_breaker_enabled", True),
                "threshold": self.config.get("circuit_breaker_threshold", 3),
                "cooldown_seconds": self.config.get("circuit_breaker_cooldown", 30),
            },
            "oscillation_detection": {
                "enabled": self.config.get("oscillation_detection_enabled", True),
                "window_size": self.config.get("oscillation_window_size", 10),
            },
        }

    def _get_audit(self) -> Dict:
        """Extract audit configuration."""
        return {
            "trace_id_required": True,
            "timestamp_required": True,
            "source_agent_required": True,
            "target_agent_required": True,
            "audit_retention_days": self.config.get("audit_retention_days", 30),
        }
