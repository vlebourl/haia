# Data Model: OpenAI-Compatible Chat API

**Phase**: 1 - Design & Contracts
**Date**: 2025-11-30
**Context**: Pydantic models for Feature 003 - OpenAI-Compatible Chat API

## Overview

This document defines all Pydantic models for the chat API. Models are organized by:
- **Request Models**: Incoming API requests
- **Response Models**: Outgoing API responses
- **Internal Models**: Agent context and intermediate structures
- **Error Models**: Error responses

All models follow OpenAI Chat Completions API schema for compatibility.

---

## Request Models

### ChatMessage

Represents a single message in the conversation.

**Location**: `src/haia/api/models/chat.py`

```python
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    """A single message in the chat conversation (OpenAI format)."""

    role: str = Field(..., description="Message role: 'system', 'user', or 'assistant'")
    content: str = Field(..., min_length=1, description="Message content")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "What VMs are running on my Proxmox cluster?"
            }
        }
```

**Validation Rules**:
- `role` must be one of: "system", "user", "assistant"
- `content` must be non-empty string
- No maximum length (handled at endpoint level for token limits)

---

### ChatCompletionRequest

Main request model for `/v1/chat/completions` endpoint.

**Location**: `src/haia/api/models/chat.py`

```python
from pydantic import BaseModel, Field

class ChatCompletionRequest(BaseModel):
    """Request for chat completion (OpenAI format)."""

    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description="List of messages in the conversation"
    )
    model: str | None = Field(
        None,
        description="Model to use (ignored, uses HAIA_MODEL from config)"
    )
    temperature: float = Field(
        0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        1024,
        ge=1,
        le=4096,
        description="Maximum tokens to generate"
    )
    stream: bool = Field(
        False,
        description="Whether to stream the response via SSE"
    )

    # OpenAI compatibility fields (not used but accepted)
    top_p: float | None = Field(None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    stop: list[str] | str | None = None
    n: int | None = Field(None, ge=1)

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "Hello, what can you help me with?"}
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": False
            }
        }
```

**Validation Rules**:
- `messages` must have at least one message
- `temperature` between 0.0 and 2.0
- `max_tokens` between 1 and 4096
- Optional fields accepted for OpenAI compatibility but may be ignored

---

## Response Models

### TokenUsage

Token usage statistics for the response.

**Location**: `src/haia/api/models/chat.py`

```python
class TokenUsage(BaseModel):
    """Token usage statistics (OpenAI format)."""

    prompt_tokens: int = Field(..., ge=0, description="Tokens in the prompt")
    completion_tokens: int = Field(..., ge=0, description="Tokens in the completion")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt_tokens": 15,
                "completion_tokens": 42,
                "total_tokens": 57
            }
        }
```

---

### Choice

A single choice in the non-streaming response.

**Location**: `src/haia/api/models/chat.py`

```python
class Choice(BaseModel):
    """A single completion choice (OpenAI format)."""

    index: int = Field(0, description="Choice index (always 0 for single choice)")
    message: ChatMessage = Field(..., description="The generated message")
    finish_reason: str | None = Field(
        None,
        description="Reason for completion: 'stop', 'length', or 'error'"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I can help you with..."
                },
                "finish_reason": "stop"
            }
        }
```

**Validation Rules**:
- `finish_reason` one of: "stop" (normal), "length" (max tokens), "error" (generation failed)

---

### ChatCompletionResponse

Non-streaming response for chat completion.

**Location**: `src/haia/api/models/chat.py`

```python
from datetime import datetime

class ChatCompletionResponse(BaseModel):
    """Non-streaming chat completion response (OpenAI format)."""

    id: str = Field(..., description="Conversation ID")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[Choice] = Field(..., description="Completion choices")
    usage: TokenUsage = Field(..., description="Token usage statistics")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        model: str,
        message: ChatMessage,
        usage: TokenUsage,
        finish_reason: str = "stop"
    ) -> "ChatCompletionResponse":
        """Factory method to create response from components."""
        return cls(
            id=conversation_id,
            object="chat.completion",
            created=int(datetime.now().timestamp()),
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=message,
                    finish_reason=finish_reason
                )
            ],
            usage=usage
        )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv_123456",
                "object": "chat.completion",
                "created": 1701000000,
                "model": "anthropic:claude-haiku-4-5-20251001",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "I can help you with..."
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 42,
                    "total_tokens": 57
                }
            }
        }
```

---

### MessageDelta

Incremental content update for streaming responses.

**Location**: `src/haia/api/models/chat.py`

```python
class MessageDelta(BaseModel):
    """Incremental message update for streaming (OpenAI format)."""

    role: str | None = Field(None, description="Role (only in first chunk)")
    content: str | None = Field(None, description="Incremental content")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "assistant",
                "content": "I can"
            }
        }
```

---

### ChoiceDelta

A single choice delta in streaming response.

**Location**: `src/haia/api/models/chat.py`

```python
class ChoiceDelta(BaseModel):
    """A single completion choice delta for streaming (OpenAI format)."""

    index: int = Field(0, description="Choice index")
    delta: MessageDelta = Field(..., description="Incremental message update")
    finish_reason: str | None = Field(
        None,
        description="Finish reason (only in final chunk)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "index": 0,
                "delta": {"content": "I can"},
                "finish_reason": None
            }
        }
```

---

### ChatCompletionChunk

Single streaming response chunk (SSE event data).

**Location**: `src/haia/api/models/chat.py`

```python
class ChatCompletionChunk(BaseModel):
    """Streaming chat completion chunk (OpenAI format)."""

    id: str = Field(..., description="Conversation ID")
    object: str = Field("chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[ChoiceDelta] = Field(..., description="Choice deltas")
    usage: TokenUsage | None = Field(
        None,
        description="Usage statistics (only in final chunk)"
    )

    @classmethod
    def create_content_chunk(
        cls,
        conversation_id: str,
        model: str,
        content: str,
        timestamp: int | None = None
    ) -> "ChatCompletionChunk":
        """Create content chunk."""
        return cls(
            id=conversation_id,
            object="chat.completion.chunk",
            created=timestamp or int(datetime.now().timestamp()),
            model=model,
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=MessageDelta(content=content)
                )
            ]
        )

    @classmethod
    def create_final_chunk(
        cls,
        conversation_id: str,
        model: str,
        usage: TokenUsage,
        timestamp: int | None = None
    ) -> "ChatCompletionChunk":
        """Create final chunk with usage and finish reason."""
        return cls(
            id=conversation_id,
            object="chat.completion.chunk",
            created=timestamp or int(datetime.now().timestamp()),
            model=model,
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=MessageDelta(),
                    finish_reason="stop"
                )
            ],
            usage=usage
        )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv_123456",
                "object": "chat.completion.chunk",
                "created": 1701000000,
                "model": "anthropic:claude-haiku-4-5-20251001",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "I can"},
                        "finish_reason": None
                    }
                ],
                "usage": None
            }
        }
```

---

## Error Models

### ErrorDetail

Detailed error information.

**Location**: `src/haia/api/models/errors.py`

```python
class ErrorDetail(BaseModel):
    """Detailed error information (OpenAI format)."""

    message: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error type identifier")
    code: str | None = Field(None, description="Error code")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Invalid API key provided",
                "type": "authentication_error",
                "code": "invalid_api_key"
            }
        }
```

---

### ErrorResponse

Error response wrapper.

**Location**: `src/haia/api/models/errors.py`

```python
class ErrorResponse(BaseModel):
    """Error response wrapper (OpenAI format)."""

    error: ErrorDetail = Field(..., description="Error details")

    @classmethod
    def from_exception(cls, exc: Exception, error_type: str, code: str | None = None) -> "ErrorResponse":
        """Create error response from exception."""
        return cls(
            error=ErrorDetail(
                message=str(exc),
                type=error_type,
                code=code
            )
        )

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "message": "Invalid API key provided",
                    "type": "authentication_error",
                    "code": "invalid_api_key"
                }
            }
        }
```

---

## Internal Models

### AgentContext

Dependency injection context for agent execution.

**Location**: `src/haia/api/deps.py`

```python
from dataclasses import dataclass
from haia.llm.client import LLMClient
from haia.db.repository import ConversationRepository

@dataclass
class AgentContext:
    """Context for agent execution with injected dependencies."""

    llm_client: LLMClient
    repository: ConversationRepository
    correlation_id: str
    model_name: str
```

**Note**: This is a dataclass, not a Pydantic model, because it's only used internally for dependency injection.

---

## Model Relationships

```text
ChatCompletionRequest
├── messages: list[ChatMessage]
└── (parameters: temperature, max_tokens, stream, etc.)

ChatCompletionResponse (non-streaming)
├── choices: list[Choice]
│   └── message: ChatMessage
└── usage: TokenUsage

ChatCompletionChunk (streaming)
├── choices: list[ChoiceDelta]
│   └── delta: MessageDelta
└── usage: TokenUsage | None (final chunk only)

ErrorResponse
└── error: ErrorDetail
```

---

## Validation Summary

All models include:
- ✅ Type hints for all fields (mypy strict compliance)
- ✅ Field validation (min_length, ge, le constraints)
- ✅ JSON schema examples for documentation
- ✅ Factory methods for common construction patterns
- ✅ OpenAI API compatibility (field names, structure)

**Database Mapping**:
- `ChatMessage.role` → `Message.role` (1:1)
- `ChatMessage.content` → `Message.content` (1:1)
- Conversation ID from response → `Conversation.id` (1:1)
- Token usage stored in `Message` metadata (future enhancement)

**Ready for**: Contract generation (OpenAPI spec)
