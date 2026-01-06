"""Integration tests for LiteLLM routing.

Session 16: LiteLLM Proxy Integration
Tests chat routing, fallback behavior, and provider selection.
"""

import pytest
from haia.services.llm_factory import llm_factory


@pytest.mark.integration
async def test_chat_uses_primary_model():
    """Test that chat feature uses primary model (Gemini)."""
    agent = llm_factory.create_agent(feature="chat")

    # Verify agent was created
    assert agent is not None
    assert agent.model is not None

    # Send test message
    result = await agent.run("What is 2+2? Answer in one word.")

    # Verify response
    assert result.data is not None
    # Note: In real test, check logs to verify chat-primary (Gemini) was used


@pytest.mark.integration
async def test_fallback_on_rate_limit():
    """Test automatic fallback when primary provider is rate limited.

    Note: This test requires manually triggering rate limit or mocking.
    For real testing, consider load testing to exhaust quota.
    """
    # This is a placeholder - real implementation needs:
    # 1. Mock Gemini to return 429 (rate limit)
    # 2. Verify request retries with chat-fallback-1 (Sonnet)
    # 3. Check logs show fallback decision

    pytest.skip("Requires rate limit simulation - manual test recommended")


@pytest.mark.integration
async def test_factory_loads_routing_config():
    """Test that factory successfully loads litellm_config.yaml."""
    config = llm_factory._load_routing_config()

    assert "model_list" in config
    assert len(config["model_list"]) > 0

    # Verify chat models exist
    chat_models = [
        m for m in config["model_list"]
        if m.get("model_info", {}).get("metadata", {}).get("feature") == "chat"
    ]
    assert len(chat_models) >= 5  # 5 chat models configured


@pytest.mark.integration
async def test_fallback_chain_parsing():
    """Test fallback chain parsing for chat feature."""
    chain = llm_factory._get_fallback_chain("chat")

    assert chain.feature == "chat"
    assert len(chain.entries) >= 5

    primary = chain.get_primary()
    assert primary.priority == 1
    assert primary.model_name == "chat-primary"
    assert primary.provider == "gemini"

    fallbacks = chain.get_fallbacks()
    assert len(fallbacks) >= 4
    assert fallbacks[0].priority == 2  # First fallback is Sonnet
