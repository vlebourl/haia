# Implementation Plan: OpenAI-Compatible Chat API with Streaming

**Branch**: `003-openai-chat-api` | **Date**: 2025-11-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-openai-chat-api/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature implements a FastAPI server exposing an OpenAI-compatible `/v1/chat/completions` endpoint with Server-Sent Events (SSE) streaming support. It integrates PydanticAI agent for chat processing, loads conversation history from the database (20-message context window), and provides OpenWebUI compatibility. The implementation includes both streaming and non-streaming response modes, comprehensive error handling, and complete observability through correlation IDs and structured logging.

**Primary Technical Approach**:
- FastAPI for HTTP API server with SSE streaming via `sse-starlette`
- PydanticAI agent initialized with LLM client from Feature 001 (abstraction layer)
- Conversation persistence via Feature 002 (database repository)
- Dependency injection for database sessions and LLM clients
- OpenAI request/response schema validation with Pydantic models
- Correlation ID tracking through contextvars for request tracing

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `fastapi` (web framework)
- `uvicorn` (ASGI server)
- `sse-starlette` (Server-Sent Events for streaming)
- `pydantic-ai` (agent framework)
- Existing: `haia.llm` (LLM abstraction layer from Feature 001)
- Existing: `haia.db` (conversation database from Feature 002)
- Existing: `haia.config` (settings management)

**Storage**: SQLite via existing `haia.db` module (async SQLAlchemy)
**Testing**: `pytest` with `pytest-asyncio`, `pytest-mock`, `httpx.AsyncClient` for API testing
**Target Platform**: Linux server (homelab environment), containerizable with Docker
**Project Type**: Single project - API server component within existing `src/haia/` structure
**Performance Goals**:
- Response latency < 5 seconds (95th percentile) for simple queries
- Streaming time-to-first-byte < 500ms
- 10 concurrent requests without degradation
- Database ops < 100ms

**Constraints**:
- Must be OpenAI API compatible for OpenWebUI integration
- SSE streaming must handle client disconnections gracefully
- Must maintain 20-message context window (from Feature 002)
- Must work with both Anthropic and Ollama providers (from Feature 001)
- CORS enabled for web clients
- Zero implementation leakage into spec (abstraction maintained)

**Scale/Scope**:
- Single homelab user (1-10 concurrent conversations)
- ~1000 messages per conversation expected
- 24/7 operation with 99% uptime target
- Memory-efficient (no leaks during 1000 requests)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Model-Agnostic Design ✅
- **Compliance**: Uses existing `haia.llm.factory.create_client()` from Feature 001
- **Verification**: Agent accepts any `LLMClient` implementation, no provider-specific code in API layer
- **Testing**: Integration tests will validate both Anthropic and Ollama providers

### II. Safety-First Operations ✅
- **Compliance**: This feature has no write operations to infrastructure (read-only chat)
- **Future Note**: When homelab tools are added (Proxmox restart, etc.), they will require approval
- **Current State**: Chat API is inherently safe - only generates text responses

### III. Compact, Clear, Efficient Code ✅
- **Compliance**:
  - FastAPI endpoints are naturally concise (single function per endpoint)
  - Pydantic models for request/response validation reduce boilerplate
  - SSE streaming uses async generators (compact pattern)
  - Line length limit: 100 characters (ruff enforced)
- **Structure**: Minimal abstraction - direct FastAPI → Agent → Database flow

### IV. Type Safety (NON-NEGOTIABLE) ✅
- **Compliance**:
  - All FastAPI endpoints use Pydantic models for request/response
  - Agent context uses typed dependency injection
  - Database types from Feature 002 (already type-safe)
  - LLM client types from Feature 001 (already type-safe)
- **Validation**: `mypy --strict` will be run on all new code
- **Models Required**:
  - `ChatCompletionRequest` (OpenAI format)
  - `ChatCompletionResponse` (OpenAI format)
  - `ChatCompletionChunk` (SSE streaming format)
  - `ErrorResponse` (error details)

### V. Async-First Architecture ✅
- **Compliance**:
  - All FastAPI endpoints are `async def`
  - Database operations use async SQLAlchemy (from Feature 002)
  - LLM client calls are async (from Feature 001)
  - PydanticAI agent runs in async mode
  - SSE streaming uses async generators
- **No Blocking**: httpx async client already used in Feature 001, no sync HTTP calls

### VI. MCP Extensibility ⏳
- **Current Status**: N/A for this feature (no tools yet)
- **Future Integration**: When adding homelab tools (Phase 2+), MCP servers will be preferred
- **Agent Setup**: PydanticAI agent initialized but without tools in MVP

### VII. Observability ✅
- **Compliance**:
  - Correlation IDs via `contextvars` for request tracing (FR-014)
  - Structured logging for all requests, responses, errors
  - Log levels: INFO for requests, DEBUG for agent decisions, ERROR for failures
  - Database conversation history provides full audit trail
- **Future**: Prometheus metrics (request count, latency, error rates) can be added later

### Post-Design Re-Check: ✅

**Status**: All constitution principles remain satisfied after design phase

**Verified**:
- ✅ Type Safety: All Pydantic models defined with full type hints (see data-model.md)
- ✅ Async-First: All endpoints and flows use async/await (see research.md)
- ✅ Compact Code: FastAPI patterns promote concise implementation
- ✅ Model-Agnostic: Uses existing LLM abstraction layer (no provider-specific code)
- ✅ Observability: Correlation IDs via contextvars, structured logging throughout
- ✅ Safety-First: Chat API is read-only (no infrastructure writes)
- ✅ No new violations introduced during design phase

**Design Artifacts**:
- `research.md` - 10 technical decisions documented
- `data-model.md` - 12 Pydantic models with full type safety
- `contracts/openapi.yaml` - OpenAPI 3.1 specification
- `quickstart.md` - Development and testing guide

## Project Structure

### Documentation (this feature)

```text
specs/003-openai-chat-api/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── openapi.yaml     # OpenAI-compatible API contract
├── checklists/
│   └── requirements.md  # Spec quality validation (already complete)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/haia/
├── agent.py             # NEW: PydanticAI agent initialization
├── api/                 # NEW: FastAPI application
│   ├── __init__.py
│   ├── app.py           # FastAPI app creation, startup/shutdown
│   ├── routes/          # API endpoints
│   │   ├── __init__.py
│   │   ├── chat.py      # /v1/chat/completions endpoint
│   │   └── health.py    # /health endpoint
│   ├── models/          # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── chat.py      # Chat request/response/chunk models
│   │   └── errors.py    # Error response models
│   └── deps.py          # Dependency injection (db sessions, LLM clients)
├── main.py              # NEW: Application entry point (uvicorn launcher)
├── config.py            # EXISTS: May need additional fields for API server
├── llm/                 # EXISTS: From Feature 001
├── db/                  # EXISTS: From Feature 002
└── __init__.py

tests/
├── unit/
│   └── api/             # NEW: Unit tests for API components
│       ├── test_models.py
│       ├── test_chat_endpoint.py
│       └── test_deps.py
├── integration/
│   └── api/             # NEW: Integration tests
│       ├── test_chat_flow.py
│       ├── test_streaming.py
│       └── test_persistence.py
└── contract/            # NEW: OpenAPI contract validation
    └── test_openai_compatibility.py
```

**Structure Decision**: Single project structure (Option 1) is used because HAIA is a standalone API server. All code lives under `src/haia/` with a new `api/` module for the HTTP layer. The existing `llm/` and `db/` modules are integrated via dependency injection. This maintains clean separation while keeping everything in one deployable unit.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations identified. All constitution principles are satisfied.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

**Phase 0 (Research) and Phase 1 (Design) outputs follow in separate files:**
- `research.md` - Technical decisions and best practices
- `data-model.md` - Request/response/entity models
- `contracts/openapi.yaml` - API specification
- `quickstart.md` - Development and testing guide
