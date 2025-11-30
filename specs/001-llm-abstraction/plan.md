# Implementation Plan: LLM Abstraction Layer

**Branch**: `001-llm-abstraction` | **Date**: 2025-11-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-llm-abstraction/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a model-agnostic LLM client abstraction layer that enables seamless switching between LLM providers (Anthropic, Ollama, OpenAI, Gemini) via configuration. The abstraction provides a unified interface for chat completion requests with consistent error handling, response formatting, and observability across all providers. MVP implementation focuses on Anthropic Claude, with the architecture designed to support additional providers without code changes to consumers.

**Technical Approach**: Abstract base class (`LLMClient`) with provider-specific implementations, factory pattern for instantiation, Pydantic models for type safety, async-first design, comprehensive error mapping, and structured logging with correlation IDs.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `pydantic` v2 (data validation, type safety)
- `httpx` (async HTTP client for Ollama)
- `anthropic` SDK (Anthropic Claude provider)
- `openai` SDK (OpenAI provider - post-MVP)
- `google-generativeai` SDK (Gemini provider - post-MVP)

**Storage**: N/A (stateless client, no persistence in this layer)
**Testing**: `pytest` with `pytest-asyncio` plugin, mock provider APIs
**Target Platform**: Linux server (part of FastAPI-based API server)
**Project Type**: Single project (library component within larger application)
**Performance Goals**:
- LLM API calls complete within 30 seconds (configurable timeout)
- Concurrent requests supported without blocking
- Minimal overhead from abstraction layer (<10ms added latency)

**Constraints**:
- Must support async/await exclusively (no sync methods)
- All inputs/outputs must be Pydantic models (strict type safety)
- Provider-agnostic message format (no provider-specific features in MVP)
- Fail-fast on initialization errors (invalid config = startup failure)

**Scale/Scope**:
- 4 provider implementations planned (Anthropic MVP, then Ollama, OpenAI, Gemini)
- ~500-800 lines of code estimated (abstraction + providers + errors)
- Single-user MVP, designed for multi-user future

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Model-Agnostic Design ✅

**Status**: PASS - This feature implements the foundation for model-agnostic design

**Compliance**:
- ✅ Model selection via `HAIA_MODEL` environment variable (factory pattern reads config)
- ✅ No model-specific code paths in abstraction (each provider implements same interface)
- ✅ Graceful degradation designed (clear errors if provider unavailable)
- ✅ Testing strategy includes multiple providers (Anthropic in MVP, Ollama validation in Phase 2)

### Principle II: Safety-First Operations ✅

**Status**: PASS - All operations are read-only (LLM API calls)

**Compliance**:
- ✅ LLM client performs only read operations (sends messages, receives responses)
- ✅ No write operations to infrastructure (no restarts, no config changes)
- N/A User approval not needed (no destructive actions possible)
- ✅ Audit logging implemented (all LLM calls logged with correlation IDs)

### Principle III: Compact, Clear, Efficient Code ✅

**Status**: PASS - Design prioritizes simplicity

**Compliance**:
- ✅ Minimal abstraction (single base class, no complex inheritance)
- ✅ Factory pattern is standard, proven design (not over-engineered)
- ✅ No premature optimization (streaming interface defined but implementation deferred)
- ✅ Clear error types (specific exceptions vs generic errors)

**Design decisions for compactness**:
- Use abstract base class (ABC) instead of protocols (simpler for this use case)
- Error mapping via simple dict lookup (no complex error handling frameworks)
- Single factory function instead of full factory class

### Principle IV: Type Safety (NON-NEGOTIABLE) ✅

**Status**: PASS - Full type annotations with Pydantic models

**Compliance**:
- ✅ All function signatures fully typed (parameters and return values)
- ✅ All data structures are Pydantic `BaseModel` subclasses (Message, LLMResponse, LLMError)
- ✅ Mypy strict mode required (will be validated in tasks phase)
- ✅ No `Any` types (provider-specific SDKs may have Any, but our interface doesn't)
- ✅ Generic types fully parameterized (`list[Message]`, not `list`)

### Principle V: Async-First Architecture ✅

**Status**: PASS - All methods are async

**Compliance**:
- ✅ All LLM client methods use `async def` (no sync methods)
- ✅ HTTP requests via `httpx` (async HTTP client)
- ✅ Provider SDKs used in async mode (`anthropic.AsyncAnthropic`, `openai.AsyncOpenAI`)
- ✅ Streaming uses async generators (`AsyncIterator[LLMResponseChunk]`)

### Principle VI: MCP Extensibility N/A

**Status**: N/A - This feature does not involve MCP servers

**Rationale**: The LLM abstraction layer is infrastructure, not a tool. MCP extensibility applies to agent tools (Proxmox, Home Assistant, etc.), not to the LLM client itself.

### Principle VII: Observability ✅

**Status**: PASS - Comprehensive logging required

**Compliance**:
- ✅ Structured logging with correlation IDs (every LLM call logged)
- ✅ Metadata logged: provider name, model, latency, token usage, error types
- ✅ Log levels: INFO for calls, ERROR for failures
- ✅ Integration with Prometheus/Grafana planned (metrics: request count, latency, error rates)

**Additional observability**:
- Request/response validation failures logged with schema details
- Provider-specific error codes preserved in logs for debugging
- Timeout tracking for performance monitoring

---

**GATE RESULT**: ✅ PASS - All applicable principles satisfied. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-llm-abstraction/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - provider SDK research
├── data-model.md        # Phase 1 output - Pydantic models design
├── quickstart.md        # Phase 1 output - usage guide
├── contracts/           # Phase 1 output - API contracts
│   └── llm_client.json  # OpenAPI-style interface definition
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/haia/
├── llm/
│   ├── __init__.py           # Public exports: LLMClient, create_client, Message, LLMResponse
│   ├── client.py             # Abstract LLMClient base class
│   ├── models.py             # Pydantic models: Message, LLMResponse, LLMResponseChunk
│   ├── errors.py             # Error classes: LLMError, AuthenticationError, RateLimitError, etc.
│   ├── factory.py            # create_client() factory function
│   └── providers/
│       ├── __init__.py       # Provider exports
│       ├── anthropic.py      # AnthropicClient implementation (MVP)
│       ├── ollama.py         # OllamaClient implementation (post-MVP)
│       ├── openai.py         # OpenAIClient implementation (post-MVP)
│       └── gemini.py         # GeminiClient implementation (post-MVP)
│
└── config.py                 # Configuration (depends on this for HAIA_MODEL)

tests/unit/llm/
├── test_models.py            # Test Pydantic model validation
├── test_factory.py           # Test provider selection logic
├── test_anthropic.py         # Test AnthropicClient (mocked API)
└── test_errors.py            # Test error mapping

tests/integration/
└── test_llm_providers.py     # Integration tests with real API calls (optional, requires API keys)
```

**Structure Decision**: Single project structure selected. The LLM abstraction layer is a library component within the larger HAIA application, not a standalone service. It follows Python package conventions with clear separation between public interface (`__init__.py` exports), implementation (`client.py`, `providers/`), and data models (`models.py`, `errors.py`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations - Constitution Check passed. No complexity justification needed.

---

*Constitution Check completed. Proceeding to Phase 0: Research & Design Decisions.*
