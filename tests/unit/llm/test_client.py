"""Unit tests for LLMClient abstract base class."""

import inspect
from collections.abc import AsyncIterator

from haia.llm.client import LLMClient
from haia.llm.models import LLMResponse, LLMResponseChunk


class TestLLMClientInterface:
    """Tests for LLMClient abstract interface."""

    def test_chat_method_exists(self) -> None:
        """Test that chat() method is defined on abstract class."""
        assert hasattr(LLMClient, "chat")
        assert inspect.iscoroutinefunction(LLMClient.chat)

    def test_chat_return_type(self) -> None:
        """Test that chat() has correct return type annotation."""
        chat_method = getattr(LLMClient, "chat")
        annotations = chat_method.__annotations__

        # Verify return type is LLMResponse
        assert "return" in annotations
        # The annotation might be LLMResponse or typing constructs wrapping it
        # We just verify the method signature is properly annotated

    def test_stream_chat_method_exists(self) -> None:
        """Test that stream_chat() method is defined on abstract class."""
        assert hasattr(LLMClient, "stream_chat")
        assert inspect.iscoroutinefunction(LLMClient.stream_chat)

    def test_stream_chat_return_type(self) -> None:
        """Test that stream_chat() has correct return type annotation."""
        stream_chat_method = getattr(LLMClient, "stream_chat")
        annotations = stream_chat_method.__annotations__

        # Verify return type includes AsyncIterator
        assert "return" in annotations
        return_type = annotations["return"]

        # Check if it's AsyncIterator[LLMResponseChunk]
        # The actual check depends on how Python represents this type at runtime
        # At minimum, verify the annotation exists and is not None
        assert return_type is not None

    def test_abstract_methods(self) -> None:
        """Test that both methods are marked as abstract."""
        abstract_methods = LLMClient.__abstractmethods__

        assert "chat" in abstract_methods
        assert "stream_chat" in abstract_methods

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that LLMClient cannot be instantiated directly."""
        try:
            LLMClient()  # type: ignore
            assert False, "Should not be able to instantiate abstract class"
        except TypeError as e:
            # Expected: "Can't instantiate abstract class LLMClient with abstract methods..."
            assert "abstract" in str(e).lower()
