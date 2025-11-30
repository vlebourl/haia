"""Unit tests for Pydantic API models validation."""

import pytest
from pydantic import ValidationError


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_valid_chat_message(self):
        """Test creating a valid chat message."""
        from haia.api.models.chat import ChatMessage

        message = ChatMessage(role="user", content="Hello, HAIA!")

        assert message.role == "user"
        assert message.content == "Hello, HAIA!"

    def test_empty_content_fails_validation(self):
        """Test that empty content fails validation."""
        from haia.api.models.chat import ChatMessage

        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="")

    def test_missing_required_fields(self):
        """Test that missing required fields fail validation."""
        from haia.api.models.chat import ChatMessage

        with pytest.raises(ValidationError):
            ChatMessage(role="user")  # type: ignore - testing validation

        with pytest.raises(ValidationError):
            ChatMessage(content="test")  # type: ignore - testing validation


class TestChatCompletionRequest:
    """Tests for ChatCompletionRequest model validation."""

    def test_valid_request_minimal_fields(self):
        """Test creating a valid request with minimal fields."""
        from haia.api.models.chat import ChatCompletionRequest

        request = ChatCompletionRequest(
            model="haia",
            messages=[
                {"role": "user", "content": "Hello"}
            ],
        )

        assert request.model == "haia"
        assert len(request.messages) == 1
        assert request.stream is False  # Default value

    def test_valid_request_with_stream_enabled(self):
        """Test creating request with streaming enabled."""
        from haia.api.models.chat import ChatCompletionRequest

        request = ChatCompletionRequest(
            model="haia",
            messages=[{"role": "user", "content": "Test"}],
            stream=True,
        )

        assert request.stream is True

    def test_empty_messages_fails_validation(self):
        """Test that empty messages array fails validation."""
        from haia.api.models.chat import ChatCompletionRequest

        with pytest.raises(ValidationError) as exc_info:
            ChatCompletionRequest(
                model="haia",
                messages=[],
            )

        # Should have validation error for messages
        assert "messages" in str(exc_info.value)

    def test_missing_model_field(self):
        """Test that missing model field fails validation."""
        from haia.api.models.chat import ChatCompletionRequest

        with pytest.raises(ValidationError):
            ChatCompletionRequest(  # type: ignore - testing validation
                messages=[{"role": "user", "content": "Test"}]
            )

    def test_missing_messages_field(self):
        """Test that missing messages field fails validation."""
        from haia.api.models.chat import ChatCompletionRequest

        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="haia")  # type: ignore - testing validation

    def test_multi_turn_conversation(self):
        """Test request with multi-turn conversation."""
        from haia.api.models.chat import ChatCompletionRequest

        request = ChatCompletionRequest(
            model="haia",
            messages=[
                {"role": "user", "content": "What is Docker?"},
                {"role": "assistant", "content": "Docker is a platform."},
                {"role": "user", "content": "Tell me more."},
            ],
        )

        assert len(request.messages) == 3

    def test_system_message_in_conversation(self):
        """Test request with system message."""
        from haia.api.models.chat import ChatCompletionRequest

        request = ChatCompletionRequest(
            model="haia",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
            ],
        )

        assert request.messages[0].role == "system"
        assert request.messages[1].role == "user"


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_valid_token_usage(self):
        """Test creating valid token usage."""
        from haia.api.models.chat import TokenUsage

        usage = TokenUsage(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30

    def test_negative_tokens_fails_validation(self):
        """Test that negative token counts fail validation."""
        from haia.api.models.chat import TokenUsage

        with pytest.raises(ValidationError):
            TokenUsage(
                prompt_tokens=-1,
                completion_tokens=10,
                total_tokens=9,
            )

        with pytest.raises(ValidationError):
            TokenUsage(
                prompt_tokens=10,
                completion_tokens=-1,
                total_tokens=9,
            )


class TestChoice:
    """Tests for Choice model (will be implemented in T025)."""

    @pytest.mark.skip(reason="Model not yet implemented - T025")
    def test_valid_choice(self):
        """Test creating a valid choice."""
        pass


class TestChatCompletionResponse:
    """Tests for ChatCompletionResponse model (will be implemented in T026)."""

    @pytest.mark.skip(reason="Model not yet implemented - T026")
    def test_valid_response(self):
        """Test creating a valid response."""
        pass


class TestStreamingModels:
    """Tests for streaming chunk models (T037)."""

    def test_message_delta_creation(self):
        """Test creating a MessageDelta."""
        from haia.api.models.chat import MessageDelta

        delta = MessageDelta(role="assistant", content="Hello")

        assert delta.role == "assistant"
        assert delta.content == "Hello"

    def test_message_delta_with_only_content(self):
        """Test MessageDelta with only content field."""
        from haia.api.models.chat import MessageDelta

        delta = MessageDelta(content="World")

        assert delta.content == "World"
        assert delta.role is None

    def test_choice_delta_creation(self):
        """Test creating a ChoiceDelta."""
        from haia.api.models.chat import ChoiceDelta, MessageDelta

        delta = ChoiceDelta(
            index=0,
            delta=MessageDelta(content="Test"),
            finish_reason=None,
        )

        assert delta.index == 0
        assert delta.delta.content == "Test"
        assert delta.finish_reason is None

    def test_choice_delta_with_finish_reason(self):
        """Test ChoiceDelta with finish_reason set."""
        from haia.api.models.chat import ChoiceDelta, MessageDelta

        delta = ChoiceDelta(
            index=0,
            delta=MessageDelta(content=""),
            finish_reason="stop",
        )

        assert delta.finish_reason == "stop"

    def test_chat_completion_chunk_creation(self):
        """Test creating a ChatCompletionChunk."""
        from haia.api.models.chat import ChatCompletionChunk, ChoiceDelta, MessageDelta

        chunk = ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1234567890,
            model="haia",
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=MessageDelta(content="Test "),
                    finish_reason=None,
                )
            ],
        )

        assert chunk.id == "chatcmpl-test"
        assert chunk.object == "chat.completion.chunk"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.content == "Test "

    def test_chat_completion_chunk_factory_method(self):
        """Test ChatCompletionChunk.from_delta factory method."""
        from haia.api.models.chat import ChatCompletionChunk

        chunk = ChatCompletionChunk.from_delta(
            content="Hello ",
            model="haia",
            chunk_id="test-123",
            finish_reason=None,
        )

        assert chunk.id == "test-123"
        assert chunk.model == "haia"
        assert chunk.choices[0].delta.content == "Hello "
        assert chunk.choices[0].finish_reason is None

    def test_final_chunk_with_usage(self):
        """Test final chunk with usage statistics."""
        from haia.api.models.chat import ChatCompletionChunk, TokenUsage

        chunk = ChatCompletionChunk.create_final_chunk(
            model="haia",
            chunk_id="test-final",
            usage=TokenUsage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
            ),
        )

        assert chunk.choices[0].finish_reason == "stop"
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 30


class TestErrorModels:
    """Tests for error response models."""

    def test_error_detail_creation(self):
        """Test creating an ErrorDetail."""
        from haia.api.models.errors import ErrorDetail

        error = ErrorDetail(
            message="Test error",
            type="test_error",
            code="ERR001",
        )

        assert error.message == "Test error"
        assert error.type == "test_error"
        assert error.code == "ERR001"

    def test_error_response_from_exception(self):
        """Test creating ErrorResponse from an exception."""
        from haia.api.models.errors import ErrorResponse

        exc = ValueError("Something went wrong")
        error_response = ErrorResponse.from_exception(
            exc,
            error_type="validation_error",
            code="VAL001",
        )

        assert error_response.error.message == "Something went wrong"
        assert error_response.error.type == "validation_error"
        assert error_response.error.code == "VAL001"
