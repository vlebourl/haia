# HAIA Development Roadmap

**Last Updated**: 2025-11-30
**Version**: 0.1.0

## Overview

This roadmap outlines the planned development of HAIA (Homelab AI Assistant). Features are organized by phase, with dependencies clearly marked.

**Current Focus**: Building the MVP chat interface with multi-model support and conversation persistence.

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

#### [P0] LLM Abstraction Layer

**Description**: Model-agnostic LLM client abstraction supporting Anthropic, Ollama, OpenAI, and Google Gemini through a unified interface.

**User Value**: Enables seamless switching between LLM providers via configuration without code changes. Supports both cloud APIs (development) and local models (production).

**Implementation Approach**:
- Create `LLMClient` abstract base class with common interface
- Implement provider-specific clients: `AnthropicClient`, `OllamaClient`, `OpenAIClient`, `GeminiClient`
- Factory pattern for client instantiation based on `HAIA_MODEL` config
- Support streaming responses across all providers
- Handle provider-specific error handling with unified error types
- Located in: `src/haia/llm/client.py` and `src/haia/llm/providers/`

**Dependencies**:
- ✅ Configuration Management (Phase 0)
- 📦 `anthropic` SDK
- 📦 `openai` SDK
- 📦 `google-generativeai` SDK
- 📦 `httpx` for Ollama HTTP API

**Constitution Compliance**:
- Model-Agnostic Design: Core principle - unified interface across all providers
- Type Safety: All client methods fully typed with Pydantic models for inputs/outputs
- Async-First: All LLM calls are async methods
- Observability: Log all LLM calls with provider, model, latency, token usage

**Effort Estimate**: M - Multiple provider integrations, abstraction design, error handling

**Priority**: P0 - Foundational for all AI features

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
- ✅ LLM Abstraction Layer (Phase 0)
- 📦 `pydantic-ai` library

**Constitution Compliance**:
- Type Safety: Agent context and responses use Pydantic models
- Async-First: Agent uses async LLM client interface
- Model-Agnostic: Works with any LLMClient implementation

**Effort Estimate**: S - Standard PydanticAI setup with custom LLM integration

**Priority**: P0 - Required for MVP chat feature

---

#### [P0] Database Setup for Conversation Storage

**Description**: PostgreSQL database schema and async client for storing conversation history, messages, and session metadata.

**User Value**: Enables persistent multi-turn conversations that users can resume later.

**Implementation Approach**:
- Use PostgreSQL for relational conversation storage
- Async database client using SQLAlchemy 2.0 (async mode) or asyncpg
- Schema: `conversations` (session_id, user_id, created_at, metadata), `messages` (id, conversation_id, role, content, timestamp)
- Alembic for database migrations
- Connection pool configuration in `config.py`
- Located in: `src/haia/db/` with models in `src/haia/db/models.py`

**Dependencies**:
- ✅ Configuration Management (Phase 0)
- 📦 `sqlalchemy[asyncio]` or `asyncpg`
- 📦 `alembic` for migrations
- 📦 PostgreSQL database

**Constitution Compliance**:
- Type Safety: All database models are Pydantic + SQLAlchemy models
- Async-First: All database operations async
- Security: Database credentials via environment variables only

**Effort Estimate**: M - Database design, migrations, async client setup

**Priority**: P0 - Required for persistent conversation history in MVP

---

### Phase 1: MVP [Next]

#### [P1] OpenAI-Compatible Chat API with Streaming

**Description**: FastAPI server exposing `/v1/chat/completions` endpoint with SSE streaming support, compatible with OpenWebUI and other OpenAI clients.

**User Value**: Allows users to interact with HAIA through any OpenAI-compatible chat interface (OpenWebUI, LibreChat, etc.). Streaming provides real-time response feedback.

**Implementation Approach**:
- FastAPI server with `/v1/chat/completions` POST endpoint
- Support OpenAI request format: messages array, model selection, temperature, etc.
- SSE (Server-Sent Events) streaming for real-time token delivery
- Non-streaming fallback for clients that don't support SSE
- Integrate with PydanticAI agent for message processing
- Load conversation history from database for multi-turn context
- Save new messages to database after response generation
- Error handling for LLM failures, rate limits, database errors
- CORS configuration for web clients
- Located in: `src/haia/interfaces/api.py`

**Dependencies**:
- ✅ Configuration Management (Phase 0)
- ✅ LLM Abstraction Layer (Phase 0)
- ✅ PydanticAI Agent Setup (Phase 0)
- ✅ Database Setup (Phase 0)
- 📦 `fastapi` framework
- 📦 `uvicorn` ASGI server
- 📦 `sse-starlette` for SSE streaming

**Constitution Compliance**:
- Type Safety: Request/response models use Pydantic
- Async-First: All endpoints are async, non-blocking I/O
- Observability: Log all requests with correlation IDs, track latency and errors
- Security: Input validation on all request fields, rate limiting (future)

**Effort Estimate**: L - Complex streaming implementation, OpenAI format compatibility, database integration, error handling

**Priority**: P1 - Core MVP feature, highest user value

---

### Phase 2: Core Features [Planned]

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

_(None yet - project just starting)_

---

## Changelog

- **2025-11-30**: Initial roadmap created with Phase 0 foundation and Phase 1 MVP chat feature
  - Added LLM abstraction layer for multi-model support (Anthropic, Ollama, OpenAI, Gemini)
  - Added database setup for persistent conversation storage
  - Added OpenAI-compatible chat API with streaming support
  - Defined Phase 2 (Proxmox, MCP) and Phase 3 (scheduler, notifications)
