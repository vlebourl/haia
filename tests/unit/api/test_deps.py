"""Unit tests for FastAPI dependency injection."""

import logging
import uuid
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import Agent

from haia.api.deps import (
    CorrelationIdFilter,
    correlation_id_var,
    get_agent,
    get_correlation_id,
    set_agent,
)


class TestCorrelationId:
    """Tests for correlation ID management."""

    @pytest.mark.asyncio
    async def test_get_correlation_id_from_header(self):
        """Test that correlation ID is extracted from request header."""
        expected_id = "test-correlation-id-123"

        cid = await get_correlation_id(x_correlation_id=expected_id)

        assert cid == expected_id
        assert correlation_id_var.get() == expected_id

    @pytest.mark.asyncio
    async def test_get_correlation_id_generates_uuid_when_no_header(self):
        """Test that UUID is generated when no correlation ID header provided."""
        cid = await get_correlation_id(x_correlation_id=None)

        # Should be a valid UUID
        assert uuid.UUID(cid)
        assert correlation_id_var.get() == cid

    @pytest.mark.asyncio
    async def test_get_correlation_id_sets_context_var(self):
        """Test that correlation ID is stored in context variable."""
        test_id = "context-test-id"

        await get_correlation_id(x_correlation_id=test_id)

        assert correlation_id_var.get() == test_id


class TestCorrelationIdFilter:
    """Tests for logging filter that adds correlation IDs."""

    def test_filter_adds_correlation_id_to_log_record(self):
        """Test that filter adds correlation_id attribute to log records."""
        # Set a known correlation ID
        test_id = "filter-test-id"
        correlation_id_var.set(test_id)

        # Create a mock log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Apply filter
        filter_instance = CorrelationIdFilter()
        result = filter_instance.filter(record)

        assert result is True
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == test_id

    def test_filter_uses_default_when_no_correlation_id_set(self):
        """Test that filter uses default value when no correlation ID in context."""
        # Reset context var to default
        correlation_id_var.set("unknown")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        filter_instance = CorrelationIdFilter()
        filter_instance.filter(record)

        assert record.correlation_id == "unknown"


class TestAgentDependency:
    """Tests for agent dependency injection."""

    def test_get_agent_returns_agent_when_initialized(self, mocker):
        """Test that get_agent returns the agent when it's been set."""
        # Create a mock agent
        mock_agent = mocker.Mock(spec=Agent)

        # Set the agent
        set_agent(mock_agent)

        # Get the agent
        agent = get_agent()

        assert agent is mock_agent

    def test_get_agent_raises_runtime_error_when_not_initialized(self):
        """Test that get_agent raises RuntimeError when agent not initialized."""
        # Reset agent to None
        set_agent(None)  # type: ignore

        with pytest.raises(RuntimeError, match="Agent not initialized"):
            get_agent()

    def test_set_agent_updates_global_instance(self, mocker):
        """Test that set_agent updates the global agent instance."""
        mock_agent_1 = mocker.Mock(spec=Agent)
        mock_agent_2 = mocker.Mock(spec=Agent)

        # Set first agent
        set_agent(mock_agent_1)
        assert get_agent() is mock_agent_1

        # Update to second agent
        set_agent(mock_agent_2)
        assert get_agent() is mock_agent_2
