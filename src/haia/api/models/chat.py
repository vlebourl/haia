"""Pydantic models for chat API requests and responses."""

import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    """A single message in the chat conversation (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "What VMs are running on my Proxmox cluster?",
            }
        }
    )

    role: str = Field(..., description="Message role: 'system', 'user', or 'assistant'")
    content: str = Field(..., min_length=1, description="Message content")


class TokenUsage(BaseModel):
    """Token usage statistics (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"prompt_tokens": 15, "completion_tokens": 42, "total_tokens": 57}}
    )

    prompt_tokens: int = Field(..., ge=0, description="Tokens in the prompt")
    completion_tokens: int = Field(..., ge=0, description="Tokens in the completion")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "haia",
                "messages": [
                    {"role": "user", "content": "What is Proxmox?"}
                ],
                "stream": False,
            }
        }
    )

    model: str = Field(..., description="Model identifier (e.g., 'haia')")
    messages: list[ChatMessage] = Field(..., min_length=1, description="Conversation messages")
    stream: bool = Field(False, description="Enable SSE streaming responses")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")

    @field_validator("messages")
    @classmethod
    def validate_messages_not_empty(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        """Ensure messages array is not empty."""
        if not v:
            raise ValueError("messages array must contain at least one message")
        return v


class Choice(BaseModel):
    """A single choice in the chat completion response (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Proxmox VE is an open-source virtualization platform.",
                },
                "finish_reason": "stop",
            }
        }
    )

    index: int = Field(..., ge=0, description="Choice index (0 for non-streaming)")
    message: ChatMessage = Field(..., description="Assistant response message")
    finish_reason: Literal["stop", "length", "content_filter"] = Field(
        ..., description="Reason completion finished"
    )


class ChatCompletionResponse(BaseModel):
    """Response model for chat completions (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "haia",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Proxmox VE is a virtualization platform.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 10,
                    "total_tokens": 25,
                },
            }
        }
    )

    id: str = Field(..., description="Unique completion ID")
    object: Literal["chat.completion"] = Field(
        "chat.completion", description="Object type (always 'chat.completion')"
    )
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used for completion")
    choices: list[Choice] = Field(..., description="Array of completion choices")
    usage: TokenUsage = Field(..., description="Token usage statistics")

    @classmethod
    def from_agent_result(
        cls,
        content: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        finish_reason: Literal["stop", "length", "content_filter"] = "stop",
    ) -> "ChatCompletionResponse":
        """Factory method to create response from agent result.

        Args:
            content: Assistant response content
            model: Model identifier
            prompt_tokens: Number of tokens in prompt
            completion_tokens: Number of tokens in completion
            finish_reason: Reason completion finished

        Returns:
            ChatCompletionResponse instance
        """
        return cls(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            object="chat.completion",
            created=int(time.time()),
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )


class MessageDelta(BaseModel):
    """Delta content in a streaming chunk (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "assistant",
                "content": "Proxmox ",
            }
        }
    )

    role: str | None = Field(None, description="Message role (only in first chunk)")
    content: str | None = Field(None, description="Incremental content delta")


class ChoiceDelta(BaseModel):
    """A single choice delta in a streaming chunk (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "index": 0,
                "delta": {"content": "Proxmox "},
                "finish_reason": None,
            }
        }
    )

    index: int = Field(..., ge=0, description="Choice index (0 for single response)")
    delta: MessageDelta = Field(..., description="Incremental message delta")
    finish_reason: Literal["stop", "length", "content_filter"] | None = Field(
        None, description="Reason completion finished (only in last chunk)"
    )


class ChatCompletionChunk(BaseModel):
    """Streaming chunk model for SSE responses (OpenAI format)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "haia",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "Proxmox "},
                        "finish_reason": None,
                    }
                ],
            }
        }
    )

    id: str = Field(..., description="Unique completion ID (same for all chunks)")
    object: Literal["chat.completion.chunk"] = Field(
        "chat.completion.chunk", description="Object type (always 'chat.completion.chunk')"
    )
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used for completion")
    choices: list[ChoiceDelta] = Field(..., description="Array of delta choices")
    usage: TokenUsage | None = Field(None, description="Token usage (only in final chunk)")

    @classmethod
    def from_delta(
        cls,
        content: str,
        model: str,
        chunk_id: str,
        finish_reason: Literal["stop", "length", "content_filter"] | None = None,
        role: str | None = None,
    ) -> "ChatCompletionChunk":
        """Factory method to create chunk from content delta.

        Args:
            content: Incremental content to send
            model: Model identifier
            chunk_id: Unique ID for this completion (same across all chunks)
            finish_reason: Completion finish reason (only for final chunk)
            role: Message role (only for first chunk)

        Returns:
            ChatCompletionChunk instance
        """
        return cls(
            id=chunk_id,
            object="chat.completion.chunk",
            created=int(time.time()),
            model=model,
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=MessageDelta(role=role, content=content),
                    finish_reason=finish_reason,
                )
            ],
        )

    @classmethod
    def create_final_chunk(
        cls,
        model: str,
        chunk_id: str,
        usage: TokenUsage,
    ) -> "ChatCompletionChunk":
        """Factory method to create final chunk with usage stats.

        Args:
            model: Model identifier
            chunk_id: Unique ID for this completion
            usage: Token usage statistics

        Returns:
            ChatCompletionChunk with finish_reason and usage
        """
        return cls(
            id=chunk_id,
            object="chat.completion.chunk",
            created=int(time.time()),
            model=model,
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=MessageDelta(content=""),
                    finish_reason="stop",
                )
            ],
            usage=usage,
        )
