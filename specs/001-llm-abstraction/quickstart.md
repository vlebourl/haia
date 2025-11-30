# Quickstart: LLM Abstraction Layer

**Feature**: LLM Abstraction Layer
**Audience**: Developers integrating the LLM client
**Last Updated**: 2025-11-30

## Overview

The LLM abstraction layer provides a model-agnostic interface for chat completion across multiple LLM providers (Anthropic, Ollama, OpenAI, Gemini). This guide shows how to use the abstraction layer in your code.

---

## Installation

Add required dependencies to `pyproject.toml`:

```toml
[project]
dependencies = [
    "pydantic>=2.0",
    "httpx>=0.25",
    "anthropic>=0.40",  # For Anthropic provider
    # Post-MVP:
    # "openai>=1.0",
    # "google-generativeai>=0.3",
]
```

---

## Configuration

Set up environment variables or `.env` file:

```bash
# Model selection (provider:model format)
HAIA_MODEL=anthropic:claude-haiku-4-5-20251001

# Anthropic credentials (required if using anthropic provider)
ANTHROPIC_API_KEY=sk-ant-api03-...

# Ollama configuration (post-MVP)
OLLAMA_BASE_URL=http://localhost:11434

# Timeout configuration
LLM_TIMEOUT=30.0
```

Create settings class (in `src/haia/config.py`):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    haia_model: str
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout: float = 30.0

    model_config = SettingsConfigDict(env_file=".env")

# Global settings instance
settings = Settings()
```

---

## Basic Usage

### 1. Initialize LLM Client

```python
from haia.llm import create_client
from haia.config import settings

# Create client based on HAIA_MODEL configuration
client = create_client(settings)
```

### 2. Send Chat Messages

```python
from haia.llm import Message

# Create messages
messages = [
    Message(role="user", content="Hello, how are you?")
]

# Get response
response = await client.chat(messages=messages)

# Access response
print(response.content)  # "I'm doing well, thank you for asking!"
print(f"Used {response.usage.total_tokens} tokens")
```

### 3. Multi-turn Conversation

```python
# Build conversation history
messages = [
    Message(role="user", content="What is Python?"),
    Message(role="assistant", content="Python is a high-level programming language..."),
    Message(role="user", content="What are its main uses?")
]

response = await client.chat(messages=messages)
print(response.content)
```

### 4. With System Prompt

```python
# System prompts provide instructions to the LLM
# NOTE: Some providers (Anthropic) handle system prompts differently
# The abstraction layer normalizes this

from haia.llm import Message

messages = [
    Message(role="system", content="You are a concise technical assistant."),
    Message(role="user", content="Explain async/await in Python.")
]

response = await client.chat(
    messages=messages,
    temperature=0.5,  # Lower temperature for more focused responses
    max_tokens=256
)
```

---

## Error Handling

### Basic Error Handling

```python
from haia.llm import (
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    ValidationError,
    ServiceUnavailableError,
    LLMError
)

try:
    response = await client.chat(messages=[user_msg])
except AuthenticationError as e:
    # Handle auth failures (401, 403)
    print(f"Authentication failed: {e}")
    print(f"Provider: {e.provider}")
    print(f"Correlation ID: {e.correlation_id}")

except RateLimitError as e:
    # Handle rate limits (429)
    print(f"Rate limited: {e}")
    # Implement backoff/retry logic

except TimeoutError as e:
    # Handle timeouts
    print(f"Request timed out after {settings.llm_timeout}s: {e}")

except ValidationError as e:
    # Handle malformed responses
    print(f"Invalid response from provider: {e}")

except ServiceUnavailableError as e:
    # Handle provider outages (500, 502, 503)
    print(f"Provider unavailable: {e}")

except LLMError as e:
    # Catch-all for other LLM errors
    print(f"LLM error: {e}")
    # Log error details
    error_dict = e.to_dict()
    logger.error("LLM request failed", extra=error_dict)
```

### Accessing Original Errors

```python
try:
    response = await client.chat(messages=[user_msg])
except LLMError as e:
    # Original provider-specific error is preserved
    original = e.original_error
    if original:
        print(f"Original error type: {type(original).__name__}")
        print(f"Original error message: {str(original)}")

    # For debugging/logging
    print(f"Correlation ID for tracing: {e.correlation_id}")
```

---

## Advanced Usage

### Custom Parameters

```python
response = await client.chat(
    messages=messages,
    temperature=0.8,      # Creativity level (0.0-1.0)
    max_tokens=2048       # Maximum response length
)
```

### Checking Token Usage

```python
response = await client.chat(messages=messages)

usage = response.usage
print(f"Prompt tokens: {usage.prompt_tokens}")
print(f"Completion tokens: {usage.completion_tokens}")
print(f"Total tokens: {usage.total_tokens}")

# Rough cost estimate (provider-dependent)
cost = usage.cost_estimate
print(f"Estimated cost: ${cost:.6f}")
```

### Checking Finish Reason

```python
response = await client.chat(messages=messages, max_tokens=50)

if response.finish_reason == "length":
    print("Warning: Response was truncated due to max_tokens limit")
elif response.finish_reason == "stop":
    print("Response completed normally")
```

---

## Switching Providers

Switching providers is as simple as changing configuration:

### Switch to Ollama (Post-MVP)

```bash
# In .env
HAIA_MODEL=ollama:qwen2.5-coder
OLLAMA_BASE_URL=http://localhost:11434
```

Code remains unchanged:

```python
from haia.llm import create_client
from haia.config import settings

# Same code, different provider!
client = create_client(settings)
response = await client.chat(messages=messages)
```

### Switch to OpenAI (Post-MVP)

```bash
# In .env
HAIA_MODEL=openai:gpt-4
OPENAI_API_KEY=sk-...
```

### Switch to Gemini (Post-MVP)

```bash
# In .env
HAIA_MODEL=gemini:gemini-pro
GOOGLE_API_KEY=...
```

---

## Streaming (Post-MVP)

Streaming API is defined in the interface but not implemented in MVP:

```python
# Post-MVP: Streaming responses
async for chunk in client.stream_chat(messages=messages):
    print(chunk.content, end="", flush=True)

    # Final chunk has finish_reason and usage
    if chunk.finish_reason:
        print(f"\nFinished: {chunk.finish_reason}")
        print(f"Total tokens: {chunk.usage.total_tokens}")
```

---

## Integration Patterns

### FastAPI Dependency Injection

```python
from fastapi import Depends, FastAPI
from haia.llm import LLMClient, create_client
from haia.config import settings

app = FastAPI()

def get_llm_client() -> LLMClient:
    """Dependency for LLM client."""
    return create_client(settings)

@app.post("/chat")
async def chat_endpoint(
    message: str,
    client: LLMClient = Depends(get_llm_client)
):
    from haia.llm import Message

    messages = [Message(role="user", content=message)]
    response = await client.chat(messages=messages)

    return {
        "response": response.content,
        "tokens": response.usage.total_tokens
    }
```

### Logging Integration

```python
import logging
import structlog
from haia.llm import create_client, LLMError

logger = structlog.get_logger()

async def chat_with_logging(messages):
    client = create_client(settings)

    try:
        response = await client.chat(messages=messages)

        # Log successful request
        logger.info(
            "llm_request_success",
            provider=response.model.split(":")[0],
            model=response.model,
            tokens=response.usage.total_tokens,
            finish_reason=response.finish_reason
        )

        return response

    except LLMError as e:
        # Log error with correlation ID
        logger.error(
            "llm_request_failed",
            error_type=type(e).__name__,
            provider=e.provider,
            correlation_id=e.correlation_id,
            message=str(e)
        )
        raise
```

### Retry Logic with Backoff

```python
import asyncio
from haia.llm import RateLimitError, TimeoutError, create_client

async def chat_with_retry(messages, max_retries=3):
    client = create_client(settings)

    for attempt in range(max_retries):
        try:
            return await client.chat(messages=messages)

        except RateLimitError:
            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = 2 ** attempt
                print(f"Rate limited. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise

        except TimeoutError:
            if attempt < max_retries - 1:
                print(f"Timeout. Retrying (attempt {attempt + 2}/{max_retries})...")
                await asyncio.sleep(1)
            else:
                raise
```

---

## Testing

### Mocking the LLM Client

```python
import pytest
from haia.llm import LLMClient, LLMResponse, TokenUsage, Message

class MockLLMClient(LLMClient):
    """Mock client for testing."""

    async def chat(self, messages, temperature=0.7, max_tokens=1024):
        # Return canned response
        return LLMResponse(
            content="Mocked response",
            model="mock:model",
            usage=TokenUsage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            ),
            finish_reason="stop"
        )

    async def stream_chat(self, messages, temperature=0.7, max_tokens=1024):
        raise NotImplementedError("Streaming not mocked")

# Use in tests
@pytest.mark.asyncio
async def test_chat_endpoint(client: TestClient):
    # Inject mock client
    app.dependency_overrides[get_llm_client] = lambda: MockLLMClient()

    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 200
    assert response.json()["response"] == "Mocked response"
```

---

## Troubleshooting

### Issue: AuthenticationError on Startup

**Problem**: `AuthenticationError: Anthropic authentication failed`

**Solution**:
1. Check `ANTHROPIC_API_KEY` is set correctly in `.env`
2. Verify API key is valid (check Anthropic console)
3. Ensure `.env` file is in correct directory
4. Check for typos in environment variable name

### Issue: ValueError: Unsupported provider

**Problem**: `ValueError: Unsupported provider: unknown`

**Solution**:
1. Check `HAIA_MODEL` format is `provider:model`
2. Ensure provider is supported: `anthropic`, `ollama` (MVP only)
3. For `openai` or `gemini`, these are post-MVP

### Issue: TimeoutError on Every Request

**Problem**: `TimeoutError: Request timed out`

**Solution**:
1. Check network connectivity to provider API
2. Increase `LLM_TIMEOUT` in configuration
3. For Ollama, ensure Ollama server is running locally
4. Check firewall settings

### Issue: Different Responses from Different Providers

**Problem**: Same prompt gives different responses when switching providers

**Solution**:
This is expected! Different models have different:
- Training data
- Capabilities
- Response styles
- Token limits

The abstraction layer ensures **interface consistency**, not **response consistency**.

---

## Best Practices

1. **Always use try-except**: LLM APIs can fail. Handle errors gracefully.

2. **Set correlation IDs**: Use correlation IDs for request tracing in distributed systems.

3. **Monitor token usage**: Track usage to avoid unexpected costs.

4. **Test with multiple providers**: Ensure your code works with different providers.

5. **Use appropriate timeouts**: Balance between responsiveness and allowing long generations.

6. **Log all LLM calls**: Essential for debugging and auditing.

7. **Handle rate limits**: Implement backoff/retry logic for rate limit errors.

8. **Validate responses**: Check `finish_reason` to detect truncated responses.

---

## Next Steps

- Read [data-model.md](./data-model.md) for detailed model specifications
- Check [research.md](./research.md) for provider-specific implementation details
- See [contracts/llm_client.json](./contracts/llm_client.json) for complete interface contract
- Proceed to implementation with `/speckit.tasks`

---

**Questions?** Refer to the specification in [spec.md](./spec.md) or implementation plan in [plan.md](./plan.md).
