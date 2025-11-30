# Research: LLM Abstraction Layer

**Feature**: LLM Abstraction Layer
**Date**: 2025-11-30
**Status**: Complete

## Overview

This document consolidates research findings for implementing a model-agnostic LLM client abstraction layer supporting multiple providers (Anthropic, Ollama, OpenAI, Gemini).

---

## Decision 1: Anthropic SDK Integration

**Decision**: Use `anthropic` SDK's `AsyncAnthropic` client for Anthropic Claude integration

**Rationale**:
- Official Python SDK with full async support
- Built-in retry logic (2 retries by default for 429, 500+ errors)
- Structured error hierarchy for precise error handling
- Timeout configuration at client and per-request levels
- Token usage metadata included in all responses

**Implementation Details**:

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    api_key=api_key,
    timeout=30.0,  # 30 seconds (default is 600s)
    max_retries=2
)

message = await client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello"}
    ],
    system="You are a helpful assistant.",  # Top-level param, NOT a message role
    temperature=0.7
)

# Token usage extraction
input_tokens = message.usage.input_tokens
output_tokens = message.usage.output_tokens
```

**Key Differences from Other Providers**:
- System prompts are a **top-level parameter**, not a message with `role: "system"`
- Requires `max_tokens` parameter (mandatory)
- Error types: `APIConnectionError`, `RateLimitError`, `APIStatusError`, `APITimeoutError`

**Alternatives Considered**:
- Direct HTTP API calls via `httpx`: Rejected - SDK handles retries, errors, streaming better
- LangChain's Anthropic integration: Rejected - adds unnecessary dependency

---

## Decision 2: Ollama HTTP API Integration

**Decision**: Use `httpx` to call Ollama's HTTP API directly (no official Python SDK)

**Rationale**:
- No official Python SDK exists
- HTTP API is simple and well-documented
- `httpx` provides async HTTP client with timeout support
- Allows full control over request/response handling

**Implementation Details**:

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen2.5-coder",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "stream": False
        },
        timeout=30.0
    )
    data = response.json()

    content = data["message"]["content"]
    # Token usage from performance metrics
    input_tokens = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)
```

**Key Differences from Other Providers**:
- System prompts **are** messages with `role: "system"` (unlike Anthropic)
- Token usage inferred from `prompt_eval_count` and `eval_count` (not explicit `usage` object)
- Errors return `{"error": "message"}` in response body (HTTP 200 for streaming, even on errors)
- Local deployment (default: `localhost:11434`)

**Error Handling**:
- HTTP 400: Invalid parameters
- HTTP 404: Model not found
- HTTP 429: Rate limiting
- HTTP 500: Internal server error
- HTTP 502: Unreachable cloud model (for remote Ollama instances)

**Alternatives Considered**:
- Ollama Python client library (community): Rejected - not officially maintained, adds dependency
- OpenAI-compatible endpoint (`/v1/chat/completions`): Considered for future, but custom endpoint provides more control

---

## Decision 3: Error Mapping Strategy

**Decision**: Use exception chaining with `raise ... from e` for provider error mapping

**Rationale**:
- Preserves full stack trace for debugging
- Python's exception chaining is standard practice (PEP 3134)
- Allows programmatic access to original error via `original_error` attribute
- Cleaner than nested try-except blocks

**Implementation Pattern**:

```python
import contextvars
import uuid
from typing import Any

# Correlation ID tracking
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)

def _get_correlation_id() -> str:
    corr_id = correlation_id_var.get()
    return corr_id or str(uuid.uuid4())

# Base exception
class LLMError(Exception):
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

# Specific error types
class AuthenticationError(LLMError):
    """API authentication failed."""
    pass

class RateLimitError(LLMError):
    """API rate limit exceeded."""
    pass

class TimeoutError(LLMError):
    """API request timed out."""
    pass

class ValidationError(LLMError):
    """Response validation failed."""
    pass

class ServiceUnavailableError(LLMError):
    """Provider service unavailable."""
    pass

# Error mapping example
try:
    response = await anthropic_client.messages.create(...)
except anthropic.APIStatusError as e:
    if e.status_code == 401:
        raise AuthenticationError(
            "Anthropic authentication failed",
            provider="anthropic",
            original_error=e
        ) from e
    elif e.status_code == 429:
        raise RateLimitError(
            "Anthropic rate limit exceeded",
            provider="anthropic",
            original_error=e
        ) from e
```

**Correlation ID Strategy**:
- Use `contextvars.ContextVar` for async-safe correlation ID tracking
- Generate UUID v4 if not set in context
- FastAPI middleware should set correlation ID from `X-Correlation-ID` header or generate new
- All exceptions automatically include correlation ID

**Alternatives Considered**:
- Decorator-based error mapping: Rejected - less explicit, harder to customize per-method
- Error mapper class: Rejected - over-engineered for this use case
- Suppress original error with `raise ... from None`: Rejected - loses debugging information

---

## Decision 4: Response Format Unification

**Decision**: Create unified `LLMResponse` Pydantic model that maps provider-specific responses

**Rationale**:
- Provides consistent interface regardless of provider
- Pydantic validation ensures response correctness
- Easy to extend with new fields without breaking consumers

**Unified Model**:

```python
from pydantic import BaseModel

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMResponse(BaseModel):
    content: str
    model: str
    usage: TokenUsage
    finish_reason: str | None = None  # "stop", "length", "tool_calls", etc.

# Mapping from Anthropic
anthropic_response = await client.messages.create(...)
llm_response = LLMResponse(
    content=anthropic_response.content[0].text,  # Anthropic returns list of content blocks
    model=anthropic_response.model,
    usage=TokenUsage(
        prompt_tokens=anthropic_response.usage.input_tokens,
        completion_tokens=anthropic_response.usage.output_tokens,
        total_tokens=anthropic_response.usage.input_tokens + anthropic_response.usage.output_tokens
    ),
    finish_reason=anthropic_response.stop_reason
)

# Mapping from Ollama
ollama_response = await httpx_client.post(...).json()
llm_response = LLMResponse(
    content=ollama_response["message"]["content"],
    model=ollama_response["model"],
    usage=TokenUsage(
        prompt_tokens=ollama_response.get("prompt_eval_count", 0),
        completion_tokens=ollama_response.get("eval_count", 0),
        total_tokens=ollama_response.get("prompt_eval_count", 0) + ollama_response.get("eval_count", 0)
    ),
    finish_reason=ollama_response.get("done_reason")
)
```

**Key Mapping Challenges**:
- Anthropic content is list of blocks (`content[0].text`) vs Ollama string (`message["content"]`)
- Token field names differ: `input_tokens`/`output_tokens` vs `prompt_eval_count`/`eval_count`
- Finish reasons use different strings across providers (normalized to common set)

---

## Decision 5: Streaming Interface Design

**Decision**: Define streaming interface but implement only for Anthropic in MVP

**Rationale**:
- MVP doesn't use streaming (documented in brainstorming session)
- Interface must exist to avoid breaking changes when streaming is added post-MVP
- Anthropic SDK has excellent streaming support, easy to implement later

**Interface**:

```python
from typing import AsyncIterator
from pydantic import BaseModel

class LLMResponseChunk(BaseModel):
    content: str  # Incremental content
    finish_reason: str | None = None  # Only on final chunk

class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> LLMResponse:
        """Non-streaming chat completion."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> AsyncIterator[LLMResponseChunk]:
        """Streaming chat completion (yields chunks)."""
        pass
```

**MVP Implementation**:
- `chat()`: Fully implemented for Anthropic
- `stream_chat()`: Raises `NotImplementedError` with message "Streaming not implemented in MVP"
- Post-MVP: Implement streaming for all providers

---

## Decision 6: Configuration Integration

**Decision**: Factory function reads `HAIA_MODEL` from config and instantiates appropriate client

**Rationale**:
- Single point of provider selection logic
- Fail-fast if provider unsupported
- Easy to add new providers without changing call sites

**Factory Pattern**:

```python
from haia.config import Settings

def create_client(config: Settings) -> LLMClient:
    """Create LLM client based on HAIA_MODEL configuration."""

    # Parse provider:model format
    parts = config.haia_model.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid HAIA_MODEL format: {config.haia_model}. Expected 'provider:model'")

    provider, model = parts

    if provider == "anthropic":
        return AnthropicClient(
            api_key=config.anthropic_api_key,
            model=model,
            timeout=config.llm_timeout
        )
    elif provider == "ollama":
        return OllamaClient(
            base_url=config.ollama_base_url,
            model=model,
            timeout=config.llm_timeout
        )
    elif provider == "openai":
        raise NotImplementedError("OpenAI provider not implemented in MVP")
    elif provider == "gemini":
        raise NotImplementedError("Gemini provider not implemented in MVP")
    else:
        raise ValueError(f"Unsupported provider: {provider}")
```

**Configuration Fields Needed**:
- `HAIA_MODEL`: e.g., "anthropic:claude-haiku-4-5-20251001"
- `ANTHROPIC_API_KEY`: Anthropic API key
- `OLLAMA_BASE_URL`: Ollama server URL (default: "http://localhost:11434")
- `LLM_TIMEOUT`: Timeout in seconds (default: 30)

---

## Best Practices Applied

1. **Async-First**: All LLM operations are async
2. **Type Safety**: Pydantic models for all inputs/outputs
3. **Error Handling**: Specific exception types with correlation IDs
4. **Observability**: All LLM calls logged with metadata (handled in client implementations)
5. **Fail-Fast**: Invalid configuration raises errors at initialization
6. **Provider Agnostic**: Unified interface hides provider differences

---

## Implementation Checklist

- [x] Research Anthropic SDK async patterns ✅
- [x] Research Ollama HTTP API ✅
- [x] Design error mapping strategy ✅
- [x] Design unified response format ✅
- [x] Design streaming interface ✅
- [x] Design factory pattern ✅
- [ ] Implement Pydantic models (data-model.md)
- [ ] Implement base LLMClient abstract class
- [ ] Implement AnthropicClient
- [ ] Implement OllamaClient (post-MVP)
- [ ] Implement error classes
- [ ] Implement factory function
- [ ] Write unit tests
- [ ] Write integration tests

---

## References

- [Anthropic Python SDK Documentation](https://github.com/anthropics/anthropic-sdk-python)
- [Anthropic API Reference](https://docs.anthropic.com/)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [PEP 3134 – Exception Chaining](https://peps.python.org/pep-3134/)
- [Python contextvars Documentation](https://docs.python.org/3/library/contextvars.html)
