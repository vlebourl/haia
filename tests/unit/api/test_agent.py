"""Unit tests for PydanticAI agent initialization."""

from pathlib import Path

import pytest
from pydantic_ai import Agent

from haia.agent import (
    DEFAULT_SYSTEM_PROMPT,
    HOMELAB_ASSISTANT_PROMPT,
    build_system_prompt,
    create_agent,
)


class TestAgentInitialization:
    """Tests for agent creation and configuration."""

    def test_create_agent_returns_agent_instance(self, mocker):
        """Test that create_agent returns a PydanticAI Agent."""
        # Mock PydanticAI's model inference to avoid API calls
        mocker.patch("pydantic_ai.models.infer_model")
        # Mock profile loading to avoid file I/O
        mocker.patch("haia.agent.load_profile_context", return_value="")

        agent = create_agent("test:model")

        assert isinstance(agent, Agent)

    def test_system_prompt_uses_default_without_config(self, mocker):
        """Test that agent uses default prompt when no custom config provided."""
        mocker.patch("pydantic_ai.models.infer_model")
        mocker.patch("haia.agent.load_profile_context", return_value="")
        mocker.patch("haia.agent.settings.haia_system_prompt", None)

        agent = create_agent("test:model")

        # Should contain default prompt
        assert DEFAULT_SYSTEM_PROMPT in agent._system_prompts

    def test_system_prompt_uses_custom_from_env(self, mocker):
        """Test that agent uses custom prompt from HAIA_SYSTEM_PROMPT env var."""
        custom_prompt = "Custom AI assistant for testing"
        mocker.patch("pydantic_ai.models.infer_model")
        mocker.patch("haia.agent.load_profile_context", return_value="")
        mocker.patch("haia.agent.settings.haia_system_prompt", custom_prompt)

        agent = create_agent("test:model")

        assert custom_prompt in agent._system_prompts
        # Should NOT contain default
        assert DEFAULT_SYSTEM_PROMPT not in agent._system_prompts

    def test_system_prompt_includes_profile_context(self, mocker):
        """Test that profile context is appended to system prompt."""
        profile_context = "## Homelab Context: Test Lab\n### Proxmox Hosts:\n- pve1: 192.168.1.10"
        mocker.patch("pydantic_ai.models.infer_model")
        mocker.patch("haia.agent.load_profile_context", return_value=profile_context)
        mocker.patch("haia.agent.settings.haia_system_prompt", None)

        agent = create_agent("test:model")

        # Should contain both default prompt and profile context
        combined_prompt = next(iter(agent._system_prompts))
        assert DEFAULT_SYSTEM_PROMPT in combined_prompt
        assert profile_context in combined_prompt

    def test_default_prompt_is_minimal(self):
        """Test that default system prompt is minimal (comprehensive prompt should be in .env)."""
        # The DEFAULT_SYSTEM_PROMPT is intentionally minimal - the full personality
        # prompt should be configured via HAIA_SYSTEM_PROMPT in .env
        assert "Haia" in DEFAULT_SYSTEM_PROMPT
        assert "homelab" in DEFAULT_SYSTEM_PROMPT.lower()
        assert len(DEFAULT_SYSTEM_PROMPT) < 500  # Should be brief

    def test_default_prompt_warns_about_destructive_operations(self):
        """Test that default system prompt includes safety guidance."""
        assert "destructive" in DEFAULT_SYSTEM_PROMPT.lower()
        assert "warn" in DEFAULT_SYSTEM_PROMPT.lower()

    def test_homelab_assistant_prompt_is_default(self):
        """Test that legacy HOMELAB_ASSISTANT_PROMPT constant equals DEFAULT_SYSTEM_PROMPT."""
        # Backward compatibility check
        assert HOMELAB_ASSISTANT_PROMPT == DEFAULT_SYSTEM_PROMPT


class TestSystemPromptBuilder:
    """Tests for build_system_prompt function."""

    def test_build_system_prompt_default_only(self, mocker):
        """Test building prompt with only default (no env var, no profile)."""
        mocker.patch("haia.agent.load_profile_context", return_value="")
        mocker.patch("haia.agent.settings.haia_system_prompt", None)

        prompt = build_system_prompt()

        assert prompt == DEFAULT_SYSTEM_PROMPT

    def test_build_system_prompt_custom_base_only(self, mocker):
        """Test building prompt with custom base from env (no profile)."""
        custom_base = "Custom system prompt"
        mocker.patch("haia.agent.load_profile_context", return_value="")
        mocker.patch("haia.agent.settings.haia_system_prompt", custom_base)

        prompt = build_system_prompt()

        assert prompt == custom_base

    def test_build_system_prompt_default_plus_profile(self, mocker):
        """Test building prompt with default base + profile context."""
        profile_context = "## Homelab Context\nTest profile data"
        mocker.patch("haia.agent.load_profile_context", return_value=profile_context)
        mocker.patch("haia.agent.settings.haia_system_prompt", None)

        prompt = build_system_prompt()

        assert DEFAULT_SYSTEM_PROMPT in prompt
        assert profile_context in prompt
        assert prompt == f"{DEFAULT_SYSTEM_PROMPT}\n\n{profile_context}"

    def test_build_system_prompt_custom_plus_profile(self, mocker):
        """Test building prompt with custom base + profile context."""
        custom_base = "Custom prompt"
        profile_context = "## Homelab Context\nTest profile"
        mocker.patch("haia.agent.load_profile_context", return_value=profile_context)
        mocker.patch("haia.agent.settings.haia_system_prompt", custom_base)

        prompt = build_system_prompt()

        assert custom_base in prompt
        assert profile_context in prompt
        assert prompt == f"{custom_base}\n\n{profile_context}"
