# HAIA Development Roadmap

**Last Updated**: 2025-12-08
**Version**: 0.2.0

## Overview

This roadmap outlines the planned development of HAIA (Homelab AI Assistant). Features are organized by phase, with dependencies clearly marked.

**Current Status**: Phase 1 MVP Complete - OpenAI-compatible API with streaming, conversation boundary detection, Neo4j memory infrastructure, and automatic memory extraction operational. **Memory retrieval and usage in conversations (Phase 2) is next.**

## Roadmap Phases

### Phase 0: Foundation [Current]

#### [P0] Configuration Management

**Description**: Core configuration system using pydantic-settings for environment variables and config files.

**User Value**: Allows users to configure API keys, model preferences, and service endpoints without modifying code.

**Implementation Approach**:
- Use `pydantic-settings` `BaseSettings` for typed configuration
- Support `.env` files and environment variables
- Validate configuration at startup (fail-fast)
- Separate configs: `AppConfig`, `ModelConfig`, `ServiceConfig`

**Dependencies**:
- 📦 `pydantic-settings` library

**Constitution Compliance**:
- Type Safety: All config fields fully typed with Pydantic models
- Security: No hardcoded secrets, .env excluded from git
- Model-Agnostic: Model selection via `HAIA_MODEL` environment variable

**Effort Estimate**: XS - Standard pydantic-settings pattern

**Priority**: P0 - Nothing works without configuration

---

#### [P0] PydanticAI Agent Setup

**Description**: Core PydanticAI agent initialization with LLM client integration and dependency injection.

**User Value**: Provides the foundation for all AI-powered interactions and tool use.

**Implementation Approach**:
- Initialize PydanticAI `Agent` with custom LLM client adapter
- Integrate `LLMClient` abstraction layer as agent's model provider
- Set up dependency injection container (`deps.py`) for API clients
- Configure agent system prompts for homelab assistant role
- Located in: `src/haia/agent.py`

**Dependencies**:
- ✅ Configuration Management (Phase 0)
- ✅ LLM Abstraction Layer - COMPLETED
- 📦 `pydantic-ai` library

**Constitution Compliance**:
- Type Safety: Agent context and responses use Pydantic models
- Async-First: Agent uses async LLM client interface
- Model-Agnostic: Works with any LLMClient implementation

**Effort Estimate**: S - Standard PydanticAI setup with custom LLM integration

**Priority**: P0 - Required for MVP chat feature

---

### Phase 1: MVP [Complete]

#### [P1] OpenAI-Compatible Chat API with Streaming ✅

**Status**: COMPLETE (PR #5, 2025-12-07)

**Description**: FastAPI server exposing `/v1/chat/completions` endpoint with SSE streaming support, compatible with OpenWebUI and other OpenAI clients. **Stateless design** - client manages conversation history.

**User Value**: Allows users to interact with HAIA through any OpenAI-compatible chat interface (OpenWebUI, LibreChat, etc.). Streaming provides real-time response feedback.

**Implementation Approach**:
- FastAPI server with `/v1/chat/completions` POST endpoint
- Support OpenAI request format: messages array, model selection, temperature, etc.
- SSE (Server-Sent Events) streaming for real-time token delivery
- Non-streaming fallback for clients that don't support SSE
- Integrate with PydanticAI agent for message processing
- **Stateless design**: Client sends full conversation history in each request
- Error handling for LLM failures, rate limits
- CORS configuration for web clients
- Located in: `src/haia/api/routes/chat.py`

**Dependencies**:
- ✅ Configuration Management (Phase 0)
- ✅ LLM Abstraction Layer - COMPLETED
- ✅ PydanticAI Agent Setup (Phase 0)
- 📦 `fastapi` framework
- 📦 `uvicorn` ASGI server
- 📦 `sse-starlette` for SSE streaming

**Constitution Compliance**:
- Type Safety: Request/response models use Pydantic
- Async-First: All endpoints are async, non-blocking I/O
- Observability: Log all requests with correlation IDs, track latency and errors
- Security: Input validation on all request fields, rate limiting (future)
- Stateless: No server-side session storage, client manages conversation history

**Effort Estimate**: M - Streaming implementation, OpenAI format compatibility, error handling

**Priority**: P1 - Core MVP feature, highest user value

---

#### [P1] Conversation Boundary Detection ✅

**Status**: COMPLETE (PR #6, 2025-12-07)

**Description**: Hybrid heuristic system to detect when conversations naturally end, enabling automatic memory extraction. Uses time gaps, message patterns, and content analysis to identify conversation boundaries without user intervention.

**User Value**: Enables HAIA to automatically capture and process conversation transcripts for memory extraction, creating a seamless learning experience.

**Implementation Approach**:
- Request metadata tracking (timestamps, message counts, content hashes)
- Hybrid detection algorithm combining:
  - Time-based triggers (30min gap → boundary likely)
  - Pattern analysis (conversation flow indicators)
  - Content similarity scoring
- Transcript accumulation in memory with conversation_id tracking
- Boundary event logging for observability
- Internal conversation_id generation (IP + User-Agent hash) for OpenWebUI compatibility
- Located in: `src/haia/api/routes/chat.py`

**Constitution Compliance**:
- Privacy: No persistent storage of transcripts (memory extraction stores structured facts only)
- Observability: All boundary detections logged with metadata
- Type Safety: All detection logic uses typed data structures

**Effort Estimate**: M - Algorithm development, testing edge cases, integration with chat endpoint

**Priority**: P1 - Foundation for memory system

---

#### [P1] Neo4j Memory Infrastructure ✅

**Status**: COMPLETE (PR #7, 2025-12-08)

**Description**: Docker Compose stack with HAIA + Neo4j 5.15 graph database. Implements complete memory graph schema (7 node types, 9 relationship types) with async Python CRUD operations, automated backups, and hybrid deployment support.

**User Value**: Provides persistent memory storage foundation, enabling HAIA to remember user preferences, infrastructure context, and past decisions across conversations.

**Implementation Approach**:
- Docker Compose orchestration:
  - HAIA container (FastAPI, Python 3.11, uvicorn)
  - Neo4j 5.15 container (official image with APOC plugin)
  - Shared Docker network with health checks
- Graph schema with 7 node types:
  - Person, Interest, Infrastructure, TechPreference, Fact, Decision, Conversation
- 9 relationship types (INTERESTED_IN, OWNS, PREFERS, HAS_FACT, MADE_DECISION, etc.)
- Async Neo4j Python driver with connection pooling (50 connections)
- Complete CRUD operations with retry logic and exponential backoff
- Volume persistence (neo4j-data, neo4j-logs, neo4j-backups)
- Automated backup/restore scripts with 7-day rotation
- Hybrid deployment: Production (full Docker stack) vs Development (Neo4j container + native HAIA)
- One-command deployment via `./deployment/docker-install.sh`
- Located in: `deployment/`, `database/schema/`, `src/haia/services/neo4j.py`, `src/haia/models/graph.py`

**Test Coverage**:
- 19 integration tests (full stack, schema validation, performance benchmarks)
- 50+ unit tests (CRUD operations, error handling, concurrent operations)

**Constitution Compliance**:
- Type Safety: All graph nodes use Pydantic models
- Async-First: Neo4j driver uses async mode throughout
- Observability: Connection status exposed via health endpoint
- Security: Neo4j credentials via environment variables only

**Effort Estimate**: L - Full stack setup, schema design, async operations, comprehensive testing

**Priority**: P1 - Critical infrastructure for memory system

---

#### [P1] Memory Extraction Engine ✅

**Status**: COMPLETE (PR #8, 2025-12-08)

**Description**: LLM-based automatic memory extraction from conversation transcripts using PydanticAI with multi-factor confidence scoring. Extracts 5 memory types (preference, personal_fact, technical_context, decision, correction) and stores them in Neo4j graph database.

**User Value**: HAIA automatically learns from conversations, extracting preferences, technical context, and decisions without manual input. Memories are stored with confidence scores for future retrieval.

**Implementation Approach**:
- ExtractionService: PydanticAI agent with structured output (ExtractionResult)
- Multi-factor confidence scoring algorithm:
  - Base confidence from LLM (0.0-1.0)
  - Explicit statement boost (+0.1)
  - Multi-mention boost (+0.05 per mention, max +0.2)
  - Contradiction penalty (-0.3)
  - Correction override (fixed 0.8)
  - Selective/aggressive strategy (≥0.4 threshold)
- MemoryStorageService: Async Neo4j persistence with graph relationships
- Integration with ConversationTracker for automatic boundary-triggered extraction
- Configuration: EXTRACTION_MODEL, EXTRACTION_MIN_CONFIDENCE environment variables
- Located in: `src/haia/extraction/`, `src/haia/services/memory_storage.py`

**Test Coverage**:
- 52 unit tests (models, confidence scoring)
- 9 integration tests with real Anthropic API
- End-to-end validation with Docker stack

**Constitution Compliance**:
- Type Safety: All extraction data structures use Pydantic models
- Async-First: All extraction and storage operations are async
- Model-Agnostic: Works with any LLM (Anthropic or Ollama)
- Observability: All extraction operations logged with metadata

**Effort Estimate**: L - LLM integration, confidence algorithm, comprehensive testing

**Priority**: P1 - Foundation for intelligent memory system

**Note**: Extracted memories are stored but NOT YET USED in conversations. Memory retrieval and context injection coming in Phase 2 (Sessions 8-9).

---

### Phase 2: Core Features [Planned]

#### [P2] Memory Retrieval System [Next - Session 8]

**Description**: Embedding-based semantic search for relevant memories. Query Neo4j using vector similarity to find contextually relevant memories for ongoing conversations.

**User Value**: HAIA can find and use relevant memories from past conversations, providing personalized responses based on learned preferences and context.

**Implementation Approach**:
- OpenAI embeddings API for memory content vectorization
- Neo4j vector index for similarity search
- Memory retrieval service with relevance scoring
- Top-K retrieval with configurable threshold
- Located in: `src/haia/retrieval/`

**Dependencies**:
- ✅ Memory Extraction Engine (Session 7)
- ✅ Neo4j Memory Infrastructure (Session 6)
- 📦 OpenAI API for embeddings

**Priority**: P2 - Required for memories to be useful

---

#### [P2] Context Integration [Session 9]

**Description**: Inject retrieved memories into conversation context, augmenting the agent's system prompt with relevant learned information.

**User Value**: HAIA remembers your preferences and provides personalized responses. "Use Docker" → HAIA automatically suggests Docker-based solutions.

**Implementation Approach**:
- Memory injection in chat endpoint before agent execution
- Dynamic system prompt augmentation with top memories
- Memory source attribution in responses
- Located in: `src/haia/api/routes/chat.py`, `src/haia/context/`

**Dependencies**:
- ✅ Memory Extraction Engine (Session 7)
- ⏳ Memory Retrieval System (Session 8)

**Priority**: P2 - Completes the memory learning loop

---

#### [P2] Basic Proxmox Integration

**Description**: Custom PydanticAI tools for querying Proxmox VE cluster status, VM/container listings, and resource metrics.

**User Value**: Users can ask "What VMs are running?" or "Show me cluster status" and get real-time information.

**Implementation Approach**:
- Async Proxmox API client using `proxmoxer` library
- Custom `@agent.tool` functions for read operations:
  - `list_vms()` - List all VMs with status
  - `get_vm_status(vm_id)` - Get detailed VM information
  - `get_cluster_resources()` - Show cluster-wide resource usage
- Located in: `src/haia/clients/proxmox.py` (client), `src/haia/tools/proxmox.py` (tools)

**Dependencies**:
- ✅ PydanticAI Agent Setup (Phase 0)
- ✅ Configuration Management (Phase 0)
- 📦 `proxmoxer` library

**Constitution Compliance**:
- Safety-First: All tools are read-only operations (no writes)
- Type Safety: All Proxmox responses mapped to Pydantic models
- Async-First: Proxmox client uses async mode

**Effort Estimate**: M - API client setup, multiple tools, error handling

**Priority**: P2 - Demonstrates homelab integration, high user interest

---

#### [P2] MCP Server Integration Framework

**Description**: Load and integrate MCP servers from `mcp_config.json` into the PydanticAI agent as toolsets.

**User Value**: Enables extensibility - users can add filesystem, Docker, database tools without writing code.

**Implementation Approach**:
- Parse `mcp_config.json` for server definitions
- Initialize MCP clients using PydanticAI's MCP support
- Support `MCPServerStreamableHTTP` and `MCPServerStdio` transports
- Attach MCP toolsets to PydanticAI agent
- Example servers: filesystem, Docker, Brave Search
- Located in: `src/haia/mcp/loader.py`

**Dependencies**:
- ✅ PydanticAI Agent Setup (Phase 0)
- ✅ Configuration Management (Phase 0)
- 📦 `pydantic-ai[mcp]` (MCP support)
- 📦 MCP server executables (npx-based or HTTP)

**Constitution Compliance**:
- MCP Extensibility: Core principle - prefer MCP servers for generic tools
- Type Safety: MCP tool schemas validated by PydanticAI
- Observability: Log all MCP server tool calls

**Effort Estimate**: M - MCP configuration parsing, multi-transport support, error handling for server failures

**Priority**: P2 - Demonstrates extensibility, enables community tools

---

### Phase 3: Advanced Features [Future]

#### [P3] Background Scheduler for Proactive Monitoring

**Description**: APScheduler-based background tasks for periodic infrastructure checks and proactive alerting.

**User Value**: Users get notified about problems before they escalate, without needing to ask.

**Implementation Approach**:
- APScheduler with async job support
- Example jobs: check VM status every 5 minutes, check Ceph health hourly
- Integration with notification backends (Telegram, Discord)
- Job configuration in `config.py` or separate YAML
- Located in: `src/haia/interfaces/scheduler.py`

**Dependencies**:
- ✅ PydanticAI Agent Setup (Phase 0)
- ⏳ Basic Proxmox Integration - Phase 2
- ⏳ Notification Backends - Phase 3
- 📦 `apscheduler` library

**Constitution Compliance**:
- Async-First: All scheduled jobs are async
- Observability: Log all job executions, failures, and alerts

**Effort Estimate**: M - Scheduler setup, job definitions, notification integration

**Priority**: P3 - Advanced automation, not required for initial usefulness

---

#### [P3] Notification Backends (Telegram, Discord)

**Description**: Abstract notification system with Telegram and Discord implementations for alerts.

**User Value**: Get notified about infrastructure issues on preferred communication platforms.

**Implementation Approach**:
- Abstract `Notifier` base class in `src/haia/notifications/base.py`
- Telegram implementation using `httpx` for Bot API
- Discord implementation using webhooks
- Configuration for bot tokens and channel IDs
- Located in: `src/haia/notifications/`

**Dependencies**:
- ✅ Configuration Management (Phase 0)
- 📦 `httpx` for async HTTP requests

**Constitution Compliance**:
- Type Safety: Notification payloads use Pydantic models
- Async-First: All notification sends are async
- Security: Bot tokens via environment variables

**Effort Estimate**: S - Simple API integrations with async HTTP

**Priority**: P3 - Nice-to-have for proactive alerting

---

### Phase 4: Future Considerations

- Home Assistant integration tools
- Alertmanager/Prometheus metrics querying
- Advanced Proxmox operations (VM start/stop/restart with approval)
- Docker/Podman container management
- Custom MCP servers for Proxmox and Home Assistant
- Web UI (alternative to OpenWebUI)
- Multi-user support with authentication
- RAG-based documentation search for homelab docs

---

## Completed Features

### ✅ LLM Abstraction Layer (Feature 001)

**Completed**: 2025-11-30
**PR**: #1
**Tasks**: 50/50
**Tests**: 81 passing

**Description**: Model-agnostic LLM client abstraction supporting Anthropic and Ollama providers with unified interface.

**Implementation**:
- `LLMClient` abstract base class with `chat()` and `stream_chat()` methods
- `AnthropicClient` implementation for Claude models via Anthropic API
- `OllamaClient` implementation for local models via Ollama HTTP API
- Factory pattern (`create_client()`) for provider instantiation based on `HAIA_MODEL` config
- Comprehensive error handling with typed exceptions
- Performance overhead < 0.1ms (99.6% under target)
- Full concurrency support validated
- Located in: `src/haia/llm/`

**Key Achievements**:
- ✅ Type-safe interface with Pydantic models
- ✅ Async-first implementation
- ✅ Provider switching via configuration only
- ✅ Comprehensive test coverage (81 tests)
- ✅ Production-ready code quality (mypy strict + ruff)

---

### ✅ OpenAI-Compatible Chat API with Streaming (Feature 003)

**Completed**: 2025-12-06
**PR**: #3
**Tests**: Integration tested

**Description**: Stateless FastAPI server with OpenAI-compatible `/v1/chat/completions` endpoint, SSE streaming support, and PydanticAI agent integration.

**Implementation**:
- FastAPI server with `/v1/chat/completions` endpoint
- SSE streaming for real-time token delivery
- Non-streaming mode for simple requests
- PydanticAI agent integration with message history
- Stateless design - client manages conversation history
- OpenWebUI compatible
- Located in: `src/haia/api/`

**Key Achievements**:
- ✅ OpenAI-compatible API format
- ✅ Streaming and non-streaming modes
- ✅ PydanticAI agent integration
- ✅ Stateless architecture (no database dependency)
- ✅ OpenWebUI tested and working

---

### ✅ Memory Extraction Engine (Session 7)

**Completed**: 2025-12-08
**PR**: #8
**Tests**: 52 unit + 9 integration = 61 passing

**Description**: Automatic memory extraction from conversations using LLM-based analysis with multi-factor confidence scoring and Neo4j graph storage.

**Implementation**:
- ExtractionService with PydanticAI structured output
- ConfidenceCalculator with multi-factor algorithm (explicit boost, multi-mention, contradiction penalty)
- MemoryStorageService for Neo4j graph persistence
- 5 memory types: preference, personal_fact, technical_context, decision, correction
- Selective/aggressive extraction strategy (≥0.4 confidence threshold)
- Automatic boundary-triggered extraction via ConversationTracker
- Configurable model and threshold via environment variables
- Located in: `src/haia/extraction/`, `src/haia/services/memory_storage.py`

**Key Achievements**:
- ✅ LLM-based extraction with structured output
- ✅ Multi-factor confidence scoring (8 factors)
- ✅ Neo4j graph database persistence
- ✅ Automatic extraction on conversation boundaries
- ✅ Comprehensive test coverage (61 tests)
- ✅ Production-ready deployment (Docker Compose stack)

**Note**: Memories are extracted and stored, but not yet retrieved or used in conversations. That's coming in Sessions 8-9 (Memory Retrieval and Context Integration).

---

## Changelog

- **2025-12-08**: ✅ **Completed Memory Extraction Engine (Session 7)**
  - ✅ Memory Extraction Engine (Session 7): 61 tests passing, PR #8 merged
    - LLM-based extraction with PydanticAI structured output
    - Multi-factor confidence scoring (8 factors, ≥0.4 threshold)
    - MemoryStorageService for Neo4j graph persistence
    - 5 memory types: preference, personal_fact, technical_context, decision, correction
    - Automatic boundary-triggered extraction
    - Configurable model and threshold via environment variables
  - **Note**: Memories are extracted and stored, but NOT YET USED in conversations
    - Memory retrieval (Session 8) and context injection (Session 9) coming next
    - This completes the "learning" part; "using" the learned memories is Phase 2
  - Updated deployment documentation and scripts
  - Fixed docker-install.sh to use HAIA_PORT from .env

- **2025-12-06**: ✅ **Completed OpenAI Chat API - Architectural Pivot to Stateless Design**
  - ✅ OpenAI-Compatible Chat API (Feature 003): Streaming and non-streaming support, PR #3 merged
    - FastAPI server with `/v1/chat/completions` endpoint
    - SSE streaming for real-time responses
    - PydanticAI agent integration
    - OpenWebUI compatible
  - **Architecture Decision**: Removed database persistence in favor of stateless design
    - Client (OpenWebUI) manages conversation history
    - Simpler deployment, no database migrations
    - Aligns with standard OpenAI API pattern
  - Updated roadmap to reflect stateless architecture
  - MVP now complete: Users can chat with HAIA via OpenWebUI

- **2025-11-30**: ✅ **Completed LLM Abstraction Layer**
  - ✅ LLM Abstraction Layer (Feature 001): 50/50 tasks, 81 tests passing, PR #1 merged
    - Anthropic and Ollama provider support
    - Performance < 0.1ms overhead, full concurrency support
  - Initial roadmap created with Phase 0 foundation and Phase 1 MVP chat feature
  - Defined LLM abstraction layer for multi-model support
  - Defined OpenAI-compatible chat API with streaming support
  - Defined Phase 2 (Proxmox, MCP) and Phase 3 (scheduler, notifications)
