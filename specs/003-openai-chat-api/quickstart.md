# Quickstart Guide: OpenAI-Compatible Chat API

**Feature**: 003-openai-chat-api
**Date**: 2025-11-30
**Audience**: Developers implementing and testing this feature

## Overview

This guide covers development setup, testing, and troubleshooting for the HAIA Chat API.

---

## Prerequisites

**Required**:
- Python 3.11+
- `uv` package manager (already in use)
- Feature 001 (LLM Abstraction) - merged to main
- Feature 002 (Conversation Database) - merged to main

**Environment**:
- `.env` file with `HAIA_MODEL` and API keys configured
- SQLite database initialized (automatic on first run)
- LLM provider accessible (Anthropic API or local Ollama)

---

## Installation

### 1. Install Dependencies

```bash
# Add FastAPI dependencies
uv add fastapi uvicorn sse-starlette

# Add PydanticAI (if not already installed)
uv add "pydantic-ai[anthropic]"

# Add testing dependencies
uv add --dev httpx pytest-asyncio
```

### 2. Configure Environment

Create or update `.env`:

```bash
# LLM Configuration
HAIA_MODEL=anthropic:claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=your_api_key_here

# Or for local Ollama
# HAIA_MODEL=ollama:qwen2.5-coder
# OLLAMA_BASE_URL=http://localhost:11434

# Database (default is fine for development)
DATABASE_URL=sqlite+aiosqlite:///./haia.db

# API Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
```

### 3. Initialize Database

```bash
# Database will auto-initialize on first server start
# Or manually via alembic:
uv run alembic upgrade head
```

---

## Development

### Run the Server

```bash
# Development mode with auto-reload
uv run uvicorn haia.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uv run uvicorn haia.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Expected Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Access API Documentation

FastAPI auto-generates interactive API docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Testing

### Manual Testing with curl

#### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": 1701000000
}
```

#### 2. Non-Streaming Chat

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, what can you help me with?"}
    ],
    "temperature": 0.7,
    "max_tokens": 1024,
    "stream": false
  }'
```

**Expected Response**:
```json
{
  "id": "conv_abc123",
  "object": "chat.completion",
  "created": 1701000000,
  "model": "anthropic:claude-haiku-4-5-20251001",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "I'm HAIA, your Homelab AI Assistant..."
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
```

#### 3. Streaming Chat

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -N \
  -d '{
    "messages": [
      {"role": "user", "content": "Explain Proxmox VE in 3 sentences"}
    ],
    "stream": true
  }'
```

**Expected Response** (SSE stream):
```
data: {"id":"conv_xyz","object":"chat.completion.chunk","created":1701000000,"model":"anthropic:claude-haiku-4-5-20251001","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"conv_xyz","object":"chat.completion.chunk","created":1701000000,"model":"anthropic:claude-haiku-4-5-20251001","choices":[{"index":0,"delta":{"content":"Proxmox"},"finish_reason":null}]}

data: {"id":"conv_xyz","object":"chat.completion.chunk","created":1701000000,"model":"anthropic:claude-haiku-4-5-20251001","choices":[{"index":0,"delta":{"content":" VE"},"finish_reason":null}]}

...

data: {"id":"conv_xyz","object":"chat.completion.chunk","created":1701000000,"model":"anthropic:claude-haiku-4-5-20251001","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":12,"completion_tokens":38,"total_tokens":50}}

data: [DONE]
```

#### 4. Conversation Persistence

```bash
# First message
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "My name is Alice"}
    ]
  }'

# Second message (should remember name)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "My name is Alice"},
      {"role": "assistant", "content": "Nice to meet you, Alice!"},
      {"role": "user", "content": "What is my name?"}
    ]
  }'
```

**Expected**: Assistant should respond with "Alice"

---

### Automated Testing

#### Unit Tests

```bash
# Run all API unit tests
uv run pytest tests/unit/api/ -v

# Run specific test file
uv run pytest tests/unit/api/test_chat_endpoint.py -v

# Run with coverage
uv run pytest tests/unit/api/ --cov=haia.api --cov-report=html
```

#### Integration Tests

```bash
# Run all API integration tests
uv run pytest tests/integration/api/ -v

# Run streaming tests
uv run pytest tests/integration/api/test_streaming.py -v

# Run persistence tests
uv run pytest tests/integration/api/test_persistence.py -v
```

#### Contract Tests

```bash
# Validate OpenAPI compliance
uv run pytest tests/contract/test_openai_compatibility.py -v
```

---

## OpenWebUI Integration

### Configure OpenWebUI to use HAIA

1. **Access OpenWebUI**: http://localhost:3000 (or your OpenWebUI URL)

2. **Add HAIA as Provider**:
   - Settings → Connections
   - Add New Connection
   - Type: OpenAI API Compatible
   - Base URL: `http://haia.local:8000/v1`
   - API Key: (optional, leave blank for now)

3. **Test Connection**:
   - Select HAIA model from dropdown
   - Send a test message
   - Verify streaming works

### Example OpenWebUI Configuration

```yaml
# OpenWebUI docker-compose.yml snippet
services:
  openwebui:
    environment:
      - OPENAI_API_BASE_URL=http://haia:8000/v1
      - OPENAI_API_KEY=optional
```

---

## Troubleshooting

### Server won't start

**Symptom**: `RuntimeError: Agent not initialized`

**Cause**: LLM client initialization failed

**Solution**:
1. Check `HAIA_MODEL` in `.env`
2. Verify API key for Anthropic or Ollama is running
3. Check logs for specific error

```bash
# Check configuration
uv run python -c "from haia.config import settings; print(settings)"

# Test LLM client directly
uv run python -c "from haia.llm.factory import create_client; from haia.config import settings; client = create_client(settings)"
```

---

### Database errors

**Symptom**: `OperationalError: no such table`

**Solution**: Run migrations

```bash
uv run alembic upgrade head
```

---

### CORS errors in browser

**Symptom**: Browser console shows CORS policy errors

**Solution**: Add OpenWebUI URL to `CORS_ORIGINS` in `.env`

```bash
CORS_ORIGINS=["http://localhost:3000", "http://openwebui.local"]
```

---

### Streaming not working

**Symptom**: SSE connection closes immediately or no chunks received

**Debugging**:
```bash
# Test streaming endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -N \
  -d '{"messages":[{"role":"user","content":"test"}],"stream":true}' \
  -v
```

**Check**:
1. `-N` flag in curl (disables buffering)
2. `Accept: text/event-stream` header present
3. Server logs for exceptions during streaming

---

### Conversation context not working

**Symptom**: Agent doesn't remember previous messages

**Debugging**:
```bash
# Check database
sqlite3 haia.db "SELECT COUNT(*) FROM messages;"
sqlite3 haia.db "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 5;"
```

**Verify**:
1. Messages being saved to database
2. Conversation ID consistent across requests
3. Context window loading correctly (check logs)

---

### Performance issues

**Symptom**: Responses take > 5 seconds

**Check**:
1. **Database**: `SELECT COUNT(*) FROM messages` - if > 10,000, consider cleanup
2. **LLM Provider**: Test provider latency directly
3. **Network**: Ping Anthropic API or Ollama server

```bash
# Test LLM latency
time curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5-20251001","messages":[{"role":"user","content":"test"}],"max_tokens":10}'
```

---

## Development Workflow

### Typical Development Cycle

1. **Make changes** to `src/haia/api/` files
2. **Server auto-reloads** (if using `--reload`)
3. **Test manually** via curl or Swagger UI
4. **Run tests**: `uv run pytest tests/unit/api/ -v`
5. **Commit changes** to feature branch

### Code Quality Checks

```bash
# Type checking
uv run mypy --strict src/haia/api/

# Linting
uv run ruff check src/haia/api/

# Formatting
uv run ruff format src/haia/api/

# All checks
uv run mypy --strict src/haia/api/ && uv run ruff check src/haia/api/ && uv run pytest tests/unit/api/
```

---

## Performance Testing

### Load Test with httpx

```python
# tests/performance/test_chat_load.py
import asyncio
import httpx

async def send_request(client, i):
    response = await client.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": f"Test {i}"}],
            "stream": False
        }
    )
    return response.status_code

async def load_test():
    async with httpx.AsyncClient() as client:
        tasks = [send_request(client, i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        print(f"Completed {len(results)} requests")
        print(f"Success rate: {results.count(200) / len(results) * 100}%")

asyncio.run(load_test())
```

**Run**:
```bash
uv run python tests/performance/test_chat_load.py
```

**Expected**: All 10 requests succeed in < 10 seconds total

---

## Next Steps

After completing this feature:
1. **Test with OpenWebUI** - Verify full integration
2. **Run `/speckit.tasks`** - Generate implementation tasks
3. **Performance tuning** - Optimize if latency > 5s
4. **Add tools** - Integrate Proxmox, Home Assistant tools (Feature 004+)

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat)
- [Server-Sent Events Spec](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [OpenWebUI GitHub](https://github.com/open-webui/open-webui)
