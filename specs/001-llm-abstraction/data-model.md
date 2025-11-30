# Data Model: LLM Abstraction Layer

**Feature**: LLM Abstraction Layer
**Date**: 2025-11-30
**Status**: Complete

## Overview

This document defines all Pydantic models used in the LLM abstraction layer. All models provide type safety, validation, and serialization for LLM client operations.

---

## Core Message Models

### Message

Represents a single message in a conversation.

```python
from pydantic import BaseModel, Field

class Message(BaseModel):
    """A single message in a conversation."""

    role: str = Field(
        ...,
        description="Message role: 'system', 'user', or 'assistant'",
        pattern="^(system|user|assistant)$"
    )
    content: str = Field(
        ...,
        description="Message content (text)",
        min_length=1
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "assistant", "content": "I'm doing well, thank you!"},
                {"role": "system", "content": "You are a helpful assistant."}
            ]
        }
    }
```

**Validation Rules**:
- `role` must be one of: "system", "user", "assistant"
- `content` must be non-empty string

**Usage**:
```python
msg = Message(role="user", content="Hello!")
```

---

## Response Models

### TokenUsage

Token usage statistics for an LLM API call.

```python
class TokenUsage(BaseModel):
    """Token usage statistics from LLM API call."""

    prompt_tokens: int = Field(..., description="Tokens in the input prompt", ge=0)
    completion_tokens: int = Field(..., description="Tokens in the generated completion", ge=0)
    total_tokens: int = Field(..., description="Total tokens used (prompt + completion)", ge=0)

    @property
    def cost_estimate(self) -> float:
        """Rough cost estimate (varies by provider/model)."""
        # Anthropic Claude Haiku: $0.25/M input, $1.25/M output
        input_cost = (self.prompt_tokens / 1_000_000) * 0.25
        output_cost = (self.completion_tokens / 1_000_000) * 1.25
        return input_cost + output_cost

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prompt_tokens": 47,
                    "completion_tokens": 65,
                    "total_tokens": 112
                }
            ]
        }
    }
```

**Validation Rules**:
- All token counts must be >= 0
- `total_tokens` should equal `prompt_tokens + completion_tokens` (validated in provider implementations)

---

### LLMResponse

Unified response from any LLM provider.

```python
class LLMResponse(BaseModel):
    """Unified response from LLM provider."""

    content: str = Field(..., description="Generated text content", min_length=1)
    model: str = Field(..., description="Model identifier used for generation")
    usage: TokenUsage = Field(..., description="Token usage statistics")
    finish_reason: str | None = Field(
        None,
        description="Reason generation stopped: 'stop', 'length', 'tool_calls', etc."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "Hello! I'm doing well, thank you for asking.",
                    "model": "claude-haiku-4-5-20251001",
                    "usage": {
                        "prompt_tokens": 47,
                        "completion_tokens": 65,
                        "total_tokens": 112
                    },
                    "finish_reason": "stop"
                }
            ]
        }
    }
```

**Fields**:
- `content`: The generated text (non-empty)
- `model`: Provider-specific model identifier (e.g., "claude-haiku-4-5-20251001", "qwen2.5-coder")
- `usage`: Token usage statistics
- `finish_reason`: Why generation stopped (optional)
  - `"stop"`: Natural completion
  - `"length"`: Hit max_tokens limit
  - `"tool_calls"`: Model invoked tools (future feature)
  - `null`: Reason unknown

---

### LLMResponseChunk

Single chunk in a streaming response (future feature).

```python
class LLMResponseChunk(BaseModel):
    """A single chunk in a streaming LLM response."""

    content: str = Field(..., description="Incremental content chunk")
    finish_reason: str | None = Field(
        None,
        description="Only set on final chunk: 'stop', 'length', etc."
    )
    usage: TokenUsage | None = Field(
        None,
        description="Only set on final chunk: final token usage"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"content": "Hello", "finish_reason": None, "usage": None},
                {"content": " there!", "finish_reason": None, "usage": None},
                {
                    "content": "",
                    "finish_reason": "stop",
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15
                    }
                }
            ]
        }
    }
```

**Streaming Semantics**:
- Multiple chunks yielded during generation
- `content` contains incremental text (word, phrase, or sentence)
- Final chunk has `finish_reason` and `usage` set
- Final chunk may have empty `content`

---

## Error Models

### LLMError

Base exception for all LLM-related errors.

```python
from typing import Any
import contextvars
import uuid

# Correlation ID context
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'correlation_id', default=None
)

def _get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    corr_id = correlation_id_var.get()
    return corr_id or str(uuid.uuid4())

class LLMError(Exception):
    """Base exception for LLM abstraction layer errors."""

    def __init__(
        self,
        message: str,
        *,
        correlation_id: str | None = None,
        provider: str | None = None,
        original_error: Exception | None = None,
        **extra_context: Any
    ):
        super().__init__(message)
        self.message = message
        self.correlation_id = correlation_id or _get_correlation_id()
        self.provider = provider
        self.original_error = original_error
        self.extra_context = extra_context

    def __str__(self) -> str:
        parts = [self.message]
        if self.provider:
            parts.append(f"[provider={self.provider}]")
        if self.correlation_id:
            parts.append(f"[correlation_id={self.correlation_id}]")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "provider": self.provider,
            "correlation_id": self.correlation_id,
            "extra_context": self.extra_context
        }
```

---

### Specific Error Types

```python
class AuthenticationError(LLMError):
    """API authentication failed (401, 403)."""
    pass

class RateLimitError(LLMError):
    """API rate limit exceeded (429)."""
    pass

class TimeoutError(LLMError):
    """API request timed out."""
    pass

class ValidationError(LLMError):
    """Response validation failed (malformed data)."""
    pass

class ServiceUnavailableError(LLMError):
    """Provider service unavailable (500, 502, 503)."""
    pass

class ResourceNotFoundError(LLMError):
    """Requested resource not found (404)."""
    pass

class InvalidRequestError(LLMError):
    """Invalid request parameters (400)."""
    pass
```

**Error Hierarchy**:
```
Exception
└── LLMError (base)
    ├── AuthenticationError (401, 403)
    ├── RateLimitError (429)
    ├── TimeoutError (timeout)
    ├── ValidationError (malformed response)
    ├── ServiceUnavailableError (500, 502, 503)
    ├── ResourceNotFoundError (404)
    └── InvalidRequestError (400)
```

---

## Configuration Models

### LLMConfig

Configuration for LLM client initialization (from pydantic-settings).

```python
from pydantic import Field, field_validator

class LLMConfig(BaseModel):
    """LLM client configuration."""

    haia_model: str = Field(
        ...,
        description="Model selection: 'provider:model' format",
        examples=["anthropic:claude-haiku-4-5-20251001", "ollama:qwen2.5-coder"]
    )
    anthropic_api_key: str | None = Field(
        None,
        description="Anthropic API key (required if using anthropic provider)"
    )
    ollama_base_url: str = Field(
        "http://localhost:11434",
        description="Ollama server base URL"
    )
    llm_timeout: float = Field(
        30.0,
        description="LLM API request timeout in seconds",
        ge=1.0,
        le=600.0
    )

    @field_validator("haia_model")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        """Ensure HAIA_MODEL has 'provider:model' format."""
        if ":" not in v:
            raise ValueError(f"Invalid HAIA_MODEL format: {v}. Expected 'provider:model'")
        provider, model = v.split(":", 1)
        if not provider or not model:
            raise ValueError(f"Invalid HAIA_MODEL format: {v}. Provider and model must be non-empty")
        return v
```

**Validation**:
- `haia_model` must contain colon separator
- `llm_timeout` must be between 1 and 600 seconds
- `anthropic_api_key` required if provider is "anthropic" (validated in factory)

---

## Entity Relationships

```
┌─────────────────┐
│  LLMClient      │ (abstract)
│  (interface)    │
└────────┬────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         │              │              │              │
┌────────▼────────┐ ┌──▼──────────┐ ┌─▼──────────┐ ┌─▼──────────┐
│ AnthropicClient │ │ OllamaClient│ │OpenAIClient│ │GeminiClient│
└─────────────────┘ └─────────────┘ └────────────┘ └────────────┘
         │
         │ uses
         ▼
┌─────────────────┐      ┌──────────────┐
│ Message         │      │ LLMResponse  │
│ - role          │◄─────│ - content    │
│ - content       │      │ - model      │
└─────────────────┘      │ - usage      │
                         │ - finish_    │
                         │   reason     │
                         └──────┬───────┘
                                │
                                │ contains
                                ▼
                         ┌──────────────┐
                         │ TokenUsage   │
                         │ - prompt_    │
                         │   tokens     │
                         │ - completion_│
                         │   tokens     │
                         │ - total_     │
                         │   tokens     │
                         └──────────────┘
```

---

## Usage Examples

### Creating Messages

```python
# System message
system_msg = Message(role="system", content="You are a helpful assistant.")

# User message
user_msg = Message(role="user", content="Hello, how are you?")

# Assistant message
assistant_msg = Message(role="assistant", content="I'm doing well, thank you!")

# Conversation history
conversation = [user_msg, assistant_msg]
```

### Processing Responses

```python
# Receive response from LLM client
response: LLMResponse = await client.chat(messages=[user_msg])

# Access content
print(response.content)  # "I'm doing well, thank you!"

# Check token usage
print(f"Used {response.usage.total_tokens} tokens")
print(f"Estimated cost: ${response.usage.cost_estimate:.6f}")

# Check why generation stopped
if response.finish_reason == "length":
    print("Warning: Response was truncated due to max_tokens limit")
```

### Error Handling

```python
try:
    response = await client.chat(messages=[user_msg])
except AuthenticationError as e:
    print(f"Auth failed: {e}")
    print(f"Provider: {e.provider}")
    print(f"Correlation ID: {e.correlation_id}")
    # Original error accessible for debugging
    print(f"Original error: {e.original_error}")
except RateLimitError as e:
    print(f"Rate limited: {e}")
    # Could implement retry logic here
except TimeoutError as e:
    print(f"Request timed out: {e}")
except LLMError as e:
    # Catch-all for other LLM errors
    print(f"LLM error: {e}")
    error_dict = e.to_dict()
    # Log structured error
```

---

## Field Constraints Summary

| Model | Field | Type | Constraints |
|-------|-------|------|-------------|
| Message | role | str | Must be "system", "user", or "assistant" |
| Message | content | str | Non-empty string |
| TokenUsage | prompt_tokens | int | >= 0 |
| TokenUsage | completion_tokens | int | >= 0 |
| TokenUsage | total_tokens | int | >= 0 |
| LLMResponse | content | str | Non-empty string |
| LLMResponse | model | str | Any non-empty string |
| LLMResponse | usage | TokenUsage | Valid TokenUsage object |
| LLMResponse | finish_reason | str \| None | Optional |
| LLMConfig | haia_model | str | Must contain ":" separator |
| LLMConfig | llm_timeout | float | 1.0 <= value <= 600.0 |

---

## Testing Considerations

### Model Validation Tests

```python
import pytest
from pydantic import ValidationError

def test_message_invalid_role():
    with pytest.raises(ValidationError):
        Message(role="invalid", content="test")

def test_message_empty_content():
    with pytest.raises(ValidationError):
        Message(role="user", content="")

def test_token_usage_negative():
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=-1, completion_tokens=10, total_tokens=9)

def test_llm_config_invalid_format():
    with pytest.raises(ValidationError):
        LLMConfig(haia_model="no_colon")
```

---

## Migration Path (Future)

### Adding Function Calling Support

```python
class ToolCall(BaseModel):
    """Function/tool call request from LLM."""
    id: str
    type: str = "function"
    function: dict[str, Any]  # Name, arguments

class Message(BaseModel):
    role: str
    content: str | None  # Make optional for tool calls
    tool_calls: list[ToolCall] | None = None  # New field

class LLMResponse(BaseModel):
    content: str | None  # Make optional for tool calls
    model: str
    usage: TokenUsage
    finish_reason: str | None
    tool_calls: list[ToolCall] | None = None  # New field
```

### Adding Multi-modal Support

```python
class MessageContent(BaseModel):
    """Content block in a message (text or image)."""
    type: str  # "text" or "image"
    text: str | None = None  # If type == "text"
    source: dict | None = None  # If type == "image"

class Message(BaseModel):
    role: str
    content: str | list[MessageContent]  # Support both formats
```

---

**Status**: All core models defined. Ready for implementation.
