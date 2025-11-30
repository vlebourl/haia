"""Unit tests for PydanticAI agent initialization."""

import pytest
from pydantic_ai import Agent

from haia.agent import HOMELAB_ASSISTANT_PROMPT, create_agent


class TestAgentInitialization:
    """Tests for agent creation and configuration."""

    def test_create_agent_returns_agent_instance(self, mocker):
        """Test that create_agent returns a PydanticAI Agent."""
        # Mock LLM client
        mock_client = mocker.Mock()

        agent = create_agent(mock_client)

        assert isinstance(agent, Agent)

    def test_create_agent_uses_llm_client(self, mocker):
        """Test that create_agent uses the provided LLM client."""
        mock_client = mocker.Mock()

        agent = create_agent(mock_client)

        # Agent should have the client as its model
        assert agent.model == mock_client

    def test_system_prompt_is_set(self, mocker):
        """Test that agent is created with homelab system prompt."""
        mock_client = mocker.Mock()

        agent = create_agent(mock_client)

        # Agent should have the homelab assistant prompt
        assert agent.system_prompt == HOMELAB_ASSISTANT_PROMPT

    def test_system_prompt_contains_homelab_keywords(self):
        """Test that system prompt mentions key homelab technologies."""
        assert "Proxmox" in HOMELAB_ASSISTANT_PROMPT
        assert "Ceph" in HOMELAB_ASSISTANT_PROMPT
        assert "Home Assistant" in HOMELAB_ASSISTANT_PROMPT
        assert "Docker" in HOMELAB_ASSISTANT_PROMPT
        assert "Prometheus" in HOMELAB_ASSISTANT_PROMPT

    def test_system_prompt_warns_about_destructive_operations(self):
        """Test that system prompt includes safety guidance."""
        assert "destructive" in HOMELAB_ASSISTANT_PROMPT.lower()
        assert "warn" in HOMELAB_ASSISTANT_PROMPT.lower()
