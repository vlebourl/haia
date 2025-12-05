# Research: OpenAI-Compatible Chat API with Streaming

**Phase**: 0 - Research & Technical Decisions
**Date**: 2025-11-30
**Context**: Planning for Feature 003 - OpenAI-Compatible Chat API

## Overview

This document consolidates research findings and technical decisions for implementing the OpenAI-compatible chat API with streaming support. All decisions align with the HAIA constitution and leverage existing components from Features 001 (LLM Abstraction) and 002 (Conversation Database).

---

## Decision 1: FastAPI + SSE for Streaming

**Context**: Need to implement both streaming (SSE) and non-streaming HTTP responses

**Decision**: Use FastAPI with `sse-starlette` for Server-Sent Events

**Rationale**:
- FastAPI provides async-first design (constitution compliance)
- Native Pydantic integration for type-safe request/response (constitution requirement)
- `sse-starlette` is the standard SSE library for FastAPI/Starlette
- OpenAPI documentation auto-generation from Pydantic models
- Mature ecosystem with extensive testing support

**Alternatives Considered**:
- **Flask + Flask-SSE**: Rejected - not async-native, requires gevent/eventlet workarounds
- **aiohttp**: Rejected - less mature than FastAPI, manual OpenAPI docs, less compact code
- **Websockets**: Rejected - OpenAI API uses HTTP + SSE, not WebSockets

**Implementation Pattern**:
```python
# Non-streaming endpoint
@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    if not request.stream:
        # Return full response
        return await generate_response(request)
    else:
        # Return SSE stream
        return EventSourceResponse(stream_generator(request))
```

**References**:
- FastAPI SSE: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
- sse-starlette: https://github.com/sysid/sse-starlette

---

## Decision 2: PydanticAI Agent Integration

**Context**: Need to initialize PydanticAI agent with LLM client and configure system prompt

**Decision**: Single global agent instance initialized at startup, injected via FastAPI dependency

**Rationale**:
- Agent initialization is stateless (only needs LLM client config)
- System prompt is constant across all requests
- Startup initialization ensures fail-fast if configuration invalid
- Dependency injection allows easy mocking in tests
- Avoids recreating agent on every request (performance)

**Alternatives Considered**:
- **Per-request agent creation**: Rejected - unnecessary overhead, agent has no per-request state
- **Singleton pattern**: Rejected - dependency injection is more testable and FastAPI-idiomatic

**Implementation Pattern**:
```python
# src/haia/agent.py
def create_agent(llm_client: LLMClient) -> Agent:
    """Create PydanticAI agent with homelab system prompt."""
    return Agent(
        model=llm_client,
        system_prompt=HOMELAB_ASSISTANT_PROMPT,
    )

# src/haia/api/deps.py
_agent: Agent | None = None

def get_agent() -> Agent:
    """FastAPI dependency for agent injection."""
    if _agent is None:
        raise RuntimeError("Agent not initialized")
    return _agent

# src/haia/api/app.py
@app.on_event("startup")
async def startup():
    global _agent
    llm_client = create_client(settings)
    _agent = create_agent(llm_client)
```

**References**:
- PydanticAI docs: https://ai.pydantic.dev/
- FastAPI dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/

---

## Decision 3: OpenAI API Compatibility Layer

**Context**: Need exact OpenAI API schema for OpenWebUI integration

**Decision**: Implement subset of OpenAI Chat Completions API (v1) with focus on used fields

**Rationale**:
- OpenWebUI only uses core fields: messages, model, temperature, max_tokens, stream
- Full API compatibility unnecessary (e.g., function calling, JSON mode not needed yet)
- Start with minimal implementation, expand as needed
- Pydantic models enforce schema compliance

**API Subset to Implement**:

**Request**:
- `messages: list[Message]` (role, content) - REQUIRED
- `model: str` - OPTIONAL (ignored, use HAIA_MODEL from config)
- `temperature: float` - OPTIONAL (default 0.7)
- `max_tokens: int` - OPTIONAL (default 1024)
- `stream: bool` - OPTIONAL (default False)

**Response (Non-Streaming)**:
- `id: str` - Generated conversation ID
- `object: str` - Always "chat.completion"
- `created: int` - Unix timestamp
- `model: str` - Echo from request or config
- `choices: list[Choice]` - Single choice with message
- `usage: TokenUsage` - prompt_tokens, completion_tokens, total_tokens

**Response (Streaming)**:
- `id: str` - Conversation ID
- `object: str` - Always "chat.completion.chunk"
- `created: int` - Unix timestamp
- `model: str` - Echo from request or config
- `choices: list[ChoiceDelta]` - Partial content deltas
- Final chunk includes `finish_reason: "stop"` and `usage`

**Alternatives Considered**:
- **Full OpenAI API**: Rejected - YAGNI, adds complexity for unused features
- **Custom API format**: Rejected - breaks OpenWebUI compatibility

**References**:
- OpenAI Chat API: https://platform.openai.com/docs/api-reference/chat
- OpenWebUI source: https://github.com/open-webui/open-webui

---

## Decision 4: Conversation ID Handling

**Context**: OpenAI API doesn't have conversation IDs, but we need to persist conversations

**Decision**: Use OpenAI `id` field as conversation_id; auto-generate if not provided

**Rationale**:
- OpenWebUI sends consistent `id` field for same conversation
- If client doesn't provide ID, generate UUID for new conversation
- Maps cleanly to database `conversation.id`
- Stateless API - no session management needed

**Implementation Pattern**:
```python
async def handle_chat(request: ChatCompletionRequest, db: AsyncSession):
    # Get or create conversation
    conversation_id = request.id or str(uuid.uuid4())
    conversation = await repo.get_conversation(conversation_id)
    if not conversation:
        conversation = await repo.create_conversation()

    # Load context (20 messages)
    context_messages = await repo.get_context_messages(conversation.id)

    # Process with agent
    response = await agent.run(messages=context_messages + [request.messages[-1]])

    # Save to database
    await repo.add_message(conversation.id, role="user", content=request.messages[-1].content)
    await repo.add_message(conversation.id, role="assistant", content=response.content)
```

**Alternatives Considered**:
- **Custom header**: Rejected - not OpenAI compatible
- **URL path parameter**: Rejected - OpenAI uses POST body only

---

## Decision 5: Error Handling Strategy

**Context**: Need to handle LLM errors, database errors, validation errors gracefully

**Decision**: Three-layer error handling with typed exceptions and HTTP status mapping

**Error Categories**:
1. **Validation Errors** (400 Bad Request)
   - Invalid request format
   - Empty messages
   - Invalid parameters
   - Handled by Pydantic automatically

2. **LLM Provider Errors** (mapped from Feature 001 errors)
   - AuthenticationError → 401 Unauthorized
   - RateLimitError → 429 Too Many Requests
   - TimeoutError → 504 Gateway Timeout
   - ServiceUnavailableError → 503 Service Unavailable
   - Other LLMError → 500 Internal Server Error

3. **Database Errors** (500 Internal Server Error)
   - Connection failures
   - Query timeouts
   - Integrity violations

**Implementation Pattern**:
```python
from haia.llm.errors import LLMError, RateLimitError, AuthenticationError
from haia.api.models.errors import ErrorResponse

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        return await process_chat(request)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key")
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    except LLMError as e:
        logger.error("LLM error", exc_info=e, extra={"correlation_id": get_correlation_id()})
        raise HTTPException(status_code=503, detail="AI service unavailable")
    except Exception as e:
        logger.exception("Unexpected error", extra={"correlation_id": get_correlation_id()})
        raise HTTPException(status_code=500, detail="Internal server error")
```

**Rationale**:
- Uses existing LLM error types from Feature 001 (no duplication)
- HTTP status codes follow OpenAI API conventions
- Structured logging for debugging
- User-friendly error messages (no stack traces leaked)

**References**:
- FastAPI exception handling: https://fastapi.tiangolo.com/tutorial/handling-errors/

---

## Decision 6: Dependency Injection Architecture

**Context**: Need to inject database sessions, LLM client, agent into endpoints

**Decision**: Use FastAPI dependency injection with `Depends()` pattern

**Dependencies**:
1. **Database Session** (`get_db`) - Already exists in Feature 002
2. **Agent** (`get_agent`) - New, initialized at startup
3. **Correlation ID** (`get_correlation_id`) - New, from request header or auto-generated

**Implementation Pattern**:
```python
# src/haia/api/deps.py
from haia.db.session import get_db
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id")

async def get_correlation_id(
    x_correlation_id: str | None = Header(None)
) -> str:
    """Get or generate correlation ID for request tracing."""
    cid = x_correlation_id or str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid

# Endpoint usage
@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_agent),
    correlation_id: str = Depends(get_correlation_id),
):
    logger.info("Chat request", extra={"correlation_id": correlation_id})
    # ... process request
```

**Rationale**:
- FastAPI-idiomatic pattern
- Testable (can override dependencies in tests)
- Automatic cleanup (db session closed by get_db generator)
- Type-safe (mypy validates dependency signatures)

**References**:
- FastAPI dependency injection: https://fastapi.tiangolo.com/tutorial/dependencies/

---

## Decision 7: CORS Configuration

**Context**: OpenWebUI runs in browser, needs CORS headers

**Decision**: Enable CORS for all origins in development, configurable for production

**Rationale**:
- OpenWebUI is typically on different port/domain than HAIA API
- Development: allow all origins for ease of testing
- Production: configure allowed origins via environment variable
- FastAPI's `CORSMiddleware` handles preflight requests automatically

**Implementation Pattern**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # ["*"] in dev, specific domains in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Security Note**: Production should restrict origins to actual OpenWebUI deployment URL

**References**:
- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/

---

## Decision 8: Correlation ID Implementation

**Context**: Need request tracing for observability (FR-014)

**Decision**: Use `contextvars` for correlation ID propagation across async calls

**Rationale**:
- `contextvars` is async-safe (unlike thread-local storage)
- Automatically propagates through async call chain
- Can be accessed from logging formatters
- Works with FastAPI's async request handling

**Implementation Pattern**:
```python
import contextvars
import logging

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="unknown")

class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_var.get()
        return True

# Logging config
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.addFilter(CorrelationIdFilter())
```

**Rationale**:
- Automatic correlation ID in all log messages
- No manual passing through function parameters
- Works across async boundaries

**References**:
- Python contextvars: https://docs.python.org/3/library/contextvars.html

---

## Decision 9: System Prompt Design

**Context**: Need to define HAIA's role and capabilities for the agent

**Decision**: Static system prompt emphasizing homelab expertise and safety

**System Prompt Content**:
```text
You are HAIA (Homelab AI Assistant), an AI assistant specialized in helping with
homelab infrastructure administration and troubleshooting.

Your expertise includes:
- Proxmox VE cluster management
- Ceph storage systems
- Home Assistant automation
- Docker and Podman containers
- Linux system administration
- Network configuration and debugging
- Monitoring with Prometheus and Grafana

When answering questions:
- Be concise and precise
- Provide step-by-step instructions when appropriate
- Warn about destructive operations before suggesting them
- Ask clarifying questions if the request is ambiguous
- Admit when you don't know something rather than guessing

You have access to the conversation history to maintain context across messages.
```

**Rationale**:
- Sets clear expectations for agent behavior
- Emphasizes safety (warn about destructive operations)
- Defines domain of expertise
- Instructs agent to use conversation context

**Future**: When tools are added, system prompt will list available tools and when to use them

---

## Decision 10: Streaming Implementation Pattern

**Context**: Need to stream LLM responses via SSE while saving to database

**Decision**: Collect streamed chunks for database save, yield to client in real-time

**Implementation Pattern**:
```python
async def stream_chat_response(
    request: ChatCompletionRequest,
    agent: Agent,
    db: AsyncSession,
    conversation_id: str,
):
    """Stream chat response via SSE while collecting for database."""
    collected_content = []

    async for chunk in agent.run_stream(messages=request.messages):
        # Collect for database
        if chunk.delta.content:
            collected_content.append(chunk.delta.content)

        # Yield to client
        yield {
            "event": "message",
            "data": chunk.model_dump_json()
        }

    # Save to database after streaming completes
    full_response = "".join(collected_content)
    await repo.add_message(conversation_id, role="assistant", content=full_response)

    # Send final chunk with usage stats
    yield {
        "event": "message",
        "data": json.dumps({"finish_reason": "stop", "usage": {...}})
    }
    yield {"event": "done", "data": "[DONE]"}
```

**Rationale**:
- Client sees immediate streaming updates
- Database gets complete message after generation
- Follows OpenAI SSE format (event: message, data: JSON)
- Handles client disconnections (async generator cleanup)

**Error Handling**: If streaming fails mid-response, send error event and close stream

**References**:
- SSE format: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events

---

## Summary of Technical Decisions

All research complete. Key technologies and patterns:

1. **Web Framework**: FastAPI + sse-starlette
2. **Agent Integration**: Global agent instance, dependency injection
3. **API Format**: OpenAI Chat Completions v1 subset
4. **Conversation Tracking**: OpenAI `id` field maps to conversation_id
5. **Error Handling**: Three-layer with HTTP status mapping
6. **Dependency Injection**: FastAPI `Depends()` pattern
7. **CORS**: Middleware with configurable origins
8. **Observability**: contextvars for correlation IDs
9. **System Prompt**: Static homelab assistant role definition
10. **Streaming**: Async generators with SSE, collect for database

**Ready for Phase 1**: Data model and contract design
