# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

HAIA (Homelab AI Assistant) is a **standalone Python application** that provides an AI assistant for homelab infrastructure administration, monitoring, and troubleshooting. It runs as an API server with OpenWebUI-compatible endpoints, allowing chat-based interaction through web interfaces like OpenWebUI.

**Target Infrastructure:**
- Proxmox VE clusters with Ceph storage
- Home Assistant and ESPHome devices
- Docker/Podman workloads
- Monitoring stacks (Prometheus, Grafana, Alertmanager)

## Core Architectural Decisions

### Framework: PydanticAI

This project uses **PydanticAI** (not LangChain or other frameworks). Key reasons:
- Type-safe tool definitions with Pydantic models
- Native MCP client support for extensible tooling
- Clean dependency injection for API clients
- Lightweight and designed for structured outputs

### Model Strategy: Development vs Production

**Development**: Anthropic API with `claude-haiku-4-5-20251001` for cost-efficient iteration.

**Production**: Local Ollama models for privacy and zero ongoing cost (`qwen2.5-coder:7b`, `qwen2.5-coder:14b`, or `llama3.1:8b`).

The agent must be **model-agnostic**—switching between Anthropic and Ollama should only require changing `HAIA_MODEL` environment variable.

### Hybrid Tool Architecture

HAIA uses two types of tools:

1. **Custom PydanticAI Tools** (`@agent.tool` decorator)
   - Complex, stateful operations specific to the homelab
   - Multi-step workflows requiring custom logic
   - Tight integration with existing Python code
   - Located in: `src/haia/tools/`

2. **MCP Servers** (via PydanticAI `toolsets`)
   - Standardized, reusable tools from the MCP ecosystem
   - Community servers for common tasks (filesystem, Docker, databases)
   - Custom MCP servers for Proxmox, Home Assistant (future)
   - Configured in: `mcp_config.json`

When adding new capabilities, **prefer MCP servers** if community implementations exist. Only create custom tools for homelab-specific logic.

### Application Type: Standalone API Server

HAIA is a **standalone application**, not a library. It runs as a long-running service exposing:

1. **OpenAI-Compatible API** (primary interface)
   - `/v1/chat/completions` endpoint for OpenWebUI integration
   - Allows interaction via any OpenAI-compatible chat UI
   - FastAPI-based server on port 8000 (configurable)

2. **Background Scheduler** (APScheduler)
   - Periodic infrastructure health checks
   - Proactive alerting via Telegram/Discord
   - Automated monitoring workflows

**Note:** Interactive CLI is not part of the initial implementation. The focus is on the API server + OpenWebUI frontend.

### MCP Integration

PydanticAI supports three MCP transport mechanisms:
- `MCPServerStreamableHTTP`: HTTP-based servers (recommended)
- `MCPServerSSE`: SSE-based servers (deprecated)
- `MCPServerStdio`: Subprocess-based servers

Configuration loaded from `mcp_config.json` with format:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/home"]
    },
    "docker": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## Project Structure

```
src/haia/
├── agent.py              # PydanticAI agent setup
├── config.py             # Configuration management (pydantic-settings)
├── deps.py               # Dependency injection container
├── main.py               # Entry point
│
├── models/               # Pydantic models
│   └── memory.py         # Neo4j graph entity models (7 node types)
│
├── services/             # Core services
│   └── neo4j.py          # Neo4j async service (CRUD, relationships)
│
├── tools/                # Custom @agent.tool functions
│   ├── proxmox.py        # Proxmox VE operations
│   ├── homeassistant.py  # Home Assistant integration
│   ├── docker.py         # Container management
│   └── system.py         # System diagnostics
│
├── clients/              # API clients for external services
│   ├── proxmox.py        # Proxmox API client (async)
│   ├── homeassistant.py  # HA REST API client (async)
│   └── alertmanager.py   # Alertmanager client (async)
│
├── interfaces/           # User-facing interfaces
│   ├── api.py            # FastAPI server (OpenAI-compatible /v1/chat)
│   └── scheduler.py      # Background scheduler (APScheduler)
│
└── notifications/        # Notification backends
    ├── base.py           # Abstract notifier
    ├── telegram.py
    └── discord.py

database/
├── schema/               # Neo4j schema definitions
│   ├── init-schema.cypher   # Constraints, indexes, schema version
│   ├── verify-schema.cypher # Verification queries
│   └── README.md            # Schema documentation (7 node types)
│
└── backups/              # Backup automation
    ├── backup.sh         # Automated backup with 7-day rotation
    ├── restore.sh        # Full database restoration
    └── README.md         # Backup/recovery procedures

deployment/
├── Dockerfile            # HAIA production image
├── docker-compose.yml    # Production stack (HAIA + Neo4j)
├── docker-compose.dev.yml # Development overrides (hybrid mode)
├── docker-install.sh     # Single-command deployment
└── README.md             # Deployment documentation
```

## Technical Constraints

- **Python 3.11+**: Modern Python with full type hints
- **Async-First**: All I/O operations are async (`asyncio`, `httpx`)
- **Pydantic Models**: All data structures are Pydantic models
- **Type Safety**: Full type annotations, run `mypy` in strict mode
- **No Heavy Frameworks**: Avoid LangChain; PydanticAI is the only agent framework

## Key Dependencies

- `pydantic-ai[mcp]` - Agent framework with MCP support
- `httpx` - Async HTTP client
- `pydantic-settings` - Configuration management
- `fastapi` - OpenAI-compatible API server
- `uvicorn` - ASGI server
- `apscheduler` - Background task scheduling
- `proxmoxer` - Proxmox API client

## Safety and Security

- **Safety-First**: Read operations are always safe; write operations require explicit confirmation
- **Secrets Management**: Environment variables or `.env` files only—never commit secrets
- **Principle of Least Privilege**: API tokens should have minimal required permissions
- **Input Validation**: All user inputs validated via Pydantic before processing
- **No Arbitrary Code Execution**: The agent cannot execute arbitrary shell commands unless explicitly whitelisted

## Development Workflow

This project uses **spec-kit** for structured development:

1. `/speckit.constitution` - Establish project principles
2. `/speckit.specify` - Define feature specifications
3. `/speckit.plan` - Create technical implementation plans
4. `/speckit.tasks` - Generate actionable task breakdowns
5. `/speckit.implement` - Execute implementation

When implementing features:
- Start with the minimal viable functionality
- Focus on type safety and async patterns
- Integrate with existing monitoring/logging
- Test with both Anthropic and Ollama models when possible

## Configuration

Model selection via `HAIA_MODEL` environment variable:
- Development: `anthropic:claude-haiku-4-5-20251001`
- Production: `ollama:qwen2.5-coder` or `ollama:qwen2.5-coder:14b`

All configuration managed through `pydantic-settings` with environment variables or `.env` file.

## Observability

- All agent actions must be logged
- Integration with existing monitoring stack (Prometheus metrics, structured logging)
- Graceful degradation if LLM is unavailable (cached/static responses for basic queries)

## Active Technologies

### Memory System (006-docker-neo4j-stack)
- **Neo4j 5.15 Graph Database** with async Python driver (`neo4j` package)
  - Connection pooling (50 connections) with exponential backoff retry
  - Docker volume persistence: `neo4j-data`, `neo4j-logs`, `neo4j-backups`
  - Single-command deployment via `./deployment/docker-install.sh`

- **Graph Schema**: 7 node types with UNIQUE constraints and indexes
  - Person, Interest, Infrastructure, TechPreference, Fact, Decision, Conversation
  - 9 relationship types: INTERESTED_IN, OWNS, PREFERS, HAS_FACT, MADE_DECISION, EXTRACTED, DEPENDS_ON, SUPERSEDES, RELATED_TO
  - Schema versioning with automated verification (database/schema/init-schema.cypher)

- **CRUD Operations**: Type-safe async methods in `Neo4jService`
  - Generic: create_node, read_node, update_node, delete_node
  - Specific: create_person, create_interest, create_infrastructure, etc.
  - Relationships: create_relationship + 9 domain-specific helpers (link_person_interest, link_infrastructure_dependency, etc.)

- **Backup/Recovery**: Automated with 7-day rotation
  - `database/backups/backup.sh` - neo4j-admin dump with integrity verification
  - `database/backups/restore.sh` - Full restoration with safety backups
  - Cron-compatible for daily scheduled backups

- **Development Workflow**: Hybrid deployment mode
  - Neo4j in Docker container (exposed ports 7474, 7687)
  - HAIA runs natively for hot-reload (`uv run uvicorn`)
  - Use `docker compose -f deployment/docker-compose.dev.yml up neo4j`

### Previous Features
- N/A (stateless client, no persistence in this layer) (001-llm-abstraction)
- Stateless API design - client manages conversation history (003-openai-chat-api)
- Versatile companion system prompt - homelab as one capability among many (004-system-prompt-redesign)

## Recent Changes
- 001-llm-abstraction: Added Python 3.11+
