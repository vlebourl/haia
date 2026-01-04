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

## Memory Extraction System

HAIA automatically extracts and stores user preferences, technical context, and other memories from conversations:

**Architecture**:
- **Boundary Detection**: Hybrid heuristic detects conversation endings (>10min idle + message drop or hash change)
- **Extraction Service**: PydanticAI agent with structured output extracts memories using LLM
- **Neo4j Storage**: Memories stored as graph nodes with relationships to conversations

**Confidence Scoring**:
- Multi-factor algorithm combining LLM scores with deterministic boosts/penalties
- Base threshold: 0.4 (selective/aggressive strategy)
- Explicit statements: +0.1 boost
- Multiple mentions: +0.05 per mention (max +0.2)
- Contradictions: -0.3 penalty
- Corrections: Fixed 0.8 confidence

**Memory Categories**:
1. `preference` - Tool choices, workflow preferences, conventions
2. `personal_fact` - Personal information, interests, hobbies
3. `technical_context` - Infrastructure details, dependencies, architectures
4. `decision` - Architecture decisions with rationale
5. `correction` - Corrections of previously stated information

**Configuration** (`.env`):
- `EXTRACTION_MODEL`: Model for extraction (defaults to `HAIA_MODEL` - Haiku recommended for cost)
- `EXTRACTION_MIN_CONFIDENCE`: Minimum confidence threshold (default: 0.4)

**Location**:
- Models: `src/haia/extraction/models.py`
- Confidence: `src/haia/extraction/confidence.py`
- Prompts: `src/haia/extraction/prompts.py`
- Service: `src/haia/extraction/extractor.py`
- Storage: `src/haia/services/memory_storage.py`
- Integration: `src/haia/memory/tracker.py:_extract_and_store_memories()`

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
- Python 3.11+ + PydanticAI 1.25.1+, pydantic, httpx (for async operations) (007-memory-extraction)
- N/A (extraction service only - does not persist data, outputs JSON) (007-memory-extraction)
- Python 3.11+ (existing project standard) + PydanticAI 1.25.1+, httpx (Ollama client), neo4j (async driver with vector support) (008-memory-retrieval)
- Neo4j 5.11+ with vector index support (existing from Session 6-7) (008-memory-retrieval)
- Python 3.11+ (existing project standard) + PydanticAI 1.25.1+, httpx (async HTTP), neo4j (async driver), tiktoken (token counting) (009-context-optimization)
- Neo4j 5.15+ graph database with vector index (existing from Session 6-8) (009-context-optimization)
- Python 3.11+ + neo4j (async driver with APOC support), asyncio (parallel execution) (011-hybrid-retrieval)
- Neo4j 5.15+ with vector index, BM25 fulltext index, and graph relationships (011-hybrid-retrieval)
- Python 3.11+ + httpx (async HTTP), PydanticAI @agent.tool integration, duckduckgo-search library (012-web-search)
- Multi-backend search: Brave Search API, DuckDuckGo, Tavily (AI-optimized), Google CSE with automatic failover (012-web-search)
- Python 3.11+ (existing project standard) + PydanticAI 1.25.1+, FastAPI (existing), httpx (async HTTP) (013-streaming-tool-status)
- N/A (stateless streaming response modification) (013-streaming-tool-status)
- Neo4j 5.15+ graph database (existing, already has Memory and Conversation nodes) (014-extraction-integration)

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

### Context Optimization (009-context-optimization)
- **Deduplicator** (`src/haia/context/deduplicator.py`)
  - Removes exact duplicates (same memory_id)
  - Detects similar memories via cosine similarity (default threshold: 0.92)
  - Handles superseded corrections (corrections override original memories)
  - Returns DeduplicationResult with stats (duplicate_count, similar_count, superseded_count)

- **Ranker** (`src/haia/context/ranker.py`)
  - Multi-factor relevance scoring: 40% similarity + 25% confidence + 20% recency + 15% frequency
  - Exponential recency decay (half-life: 43.3 days ≈ 6 weeks)
  - Logarithmic frequency scaling (diminishing returns for high access counts)
  - Customizable weights via ScoreWeights model

- **BudgetManager** (`src/haia/context/budget_manager.py`)
  - Token counting with tiktoken (cl100k_base encoding for GPT-4/Claude)
  - HARD_CUTOFF strategy: Remove memories that don't fit budget
  - TRUNCATE strategy: Shorten content proportionally to relevance
  - Default budget: 2000 tokens with 50-token buffer for overhead

- **AccessTracker** (`src/haia/context/access_tracker.py`)
  - Records memory access timestamps and frequency in Neo4j
  - Supports frequency-based re-ranking
  - Non-blocking: Failures don't break retrieval
  - Methods: record_access(), get_access_metadata(), get_usage_stats()

- **Integration**: All features integrated into RetrievalService with opt-in flags
  - enable_dedup=True (default)
  - enable_rerank=True (default)
  - track_access=True (default)
  - token_budget=None (optional, disabled by default)

### Hybrid Retrieval System (011-hybrid-retrieval)
- **GraphTraversalService** (`src/haia/services/graph_traversal.py`)
  - Discovers contextually relevant memories by following graph relationships
  - Supports APOC multi-hop traversal (2-3 hops) with automatic fallback to native 1-hop Cypher
  - Follows RELATED_TO, DEPENDS_ON, SUPERSEDES relationships
  - Excludes seed nodes from results, returns distance-ranked memories

- **RRFMerger** (`src/haia/services/rrf_merger.py`)
  - Combines ranked results from multiple retrieval methods using Reciprocal Rank Fusion
  - Formula: `score(d) = Σ (1 / (k + rank_i(d)))` where k=60
  - Tracks source attribution (which methods found each memory)
  - Industry-standard algorithm (Elasticsearch, Milvus, Azure AI Search)

- **Hybrid Retrieval** (`RetrievalService.retrieve_hybrid()`)
  - Executes 3 retrieval methods in parallel: vector (semantic), BM25 (keyword), graph (relationships)
  - Graceful degradation: Continues if individual methods fail (raises error only if ALL fail)
  - Returns merged results with RRF scores and source attribution
  - Performance: p95 latency <500ms with all methods enabled

- **API Integration** (`src/haia/api/routes/chat.py`)
  - Chat API supports `metadata: {"hybrid_mode": true}` parameter
  - Automatic method selection: hybrid retrieval when enabled, vector-only when disabled
  - Memory context includes source attribution: `*(Found by: vector, bm25, graph)*`
  - Health endpoint reports `hybrid_retrieval: enabled/disabled` and `apoc_available: true/false`

- **Configuration** (`.env`)
  - `HYBRID_RETRIEVAL_ENABLED=true` - Global enable/disable
  - `HYBRID_DEFAULT_METHODS=vector,bm25,graph` - Default methods to use
  - `HYBRID_GRAPH_MAX_DEPTH=2` - Max graph traversal hops (1-3)
  - `HYBRID_RRF_K=60` - RRF constant parameter
  - `HYBRID_ENABLE_APOC=true` - Use APOC plugin when available

- **Usage Example**:
  ```bash
  curl -X POST /v1/chat/completions \
    -d '{"messages": [...], "metadata": {"hybrid_mode": true}}'
  ```

### Web Search Integration (012-web-search)
- **Multi-Backend Search**: Brave Search API, DuckDuckGo, Tavily (AI-optimized), Google Custom Search Engine
  - Automatic failover with priority ordering
  - Parallel multi-source queries for cross-verification
  - Rate limiting and cost tracking per backend

- **Search Orchestration** (`src/haia/services/search/selector.py`)
  - Priority-based backend selection with automatic failover
  - LRU cache with TTL (default: 24 hours, in-memory or Redis)
  - Relevance scoring (domain reputation + documentation bonus + recency + keywords)
  - Multi-source aggregation with source attribution

- **Cost Management** (`src/haia/services/search/metrics.py`)
  - Per-backend query counters and cost calculation
  - Daily/monthly budget tracking with alerts (80% warning, 95% critical)
  - Cache hit/miss tracking with hit rate calculation
  - Persistent JSON storage: `~/.haia/search_metrics.json`
  - Metrics API: `GET /search/metrics`

- **PydanticAI Tool Integration** (`src/haia/tools/search.py`)
  - `web_search(query, max_results)` - Autonomous agent tool
  - Intent detection patterns (version queries, errors, documentation, time-sensitive)
  - Documentation query detection with automatic domain whitelisting
  - Formatted markdown results with source attribution

- **Configuration** (`.env`):
  - `SEARCH_ENABLED=true` - Feature toggle
  - `SEARCH_BRAVE_API_KEY`, `SEARCH_TAVILY_API_KEY`, `SEARCH_GOOGLE_CSE_API_KEY` - Backend credentials
  - `SEARCH_BACKEND_PRIORITY=brave,duckduckgo,tavily,google_cse` - Failover order
  - `SEARCH_DAILY_BUDGET_USD=1.0`, `SEARCH_MONTHLY_BUDGET_USD=10.0` - Cost limits
  - `SEARCH_CACHE_ENABLED=true`, `SEARCH_CACHE_TTL_SECONDS=86400` - Cache settings

- **Usage Example**:
  ```python
  # Autonomous search triggered by agent
  user: "What's the latest Proxmox VE version?"
  # Agent detects "latest version" pattern and calls web_search()

  # Multi-source verification
  from haia.services.search.selector import SearchBackendSelector
  selector = SearchBackendSelector()
  response = await selector.multi_source_search(
      SearchRequest(query="Docker networking best practices")
  )
  # Results show: "✓ Verified by: brave, tavily (2 sources)"
  ```

- **Location**:
  - Models: `src/haia/models/search.py`
  - Backends: `src/haia/services/search/{brave,duckduckgo,tavily,google_cse}.py`
  - Selector: `src/haia/services/search/selector.py`
  - Cache: `src/haia/services/search/cache.py`
  - Metrics: `src/haia/services/search/metrics.py`
  - Tool: `src/haia/tools/search.py`
  - API: `src/haia/api/search_metrics.py`

### Previous Features
- N/A (stateless client, no persistence in this layer) (001-llm-abstraction)
- Stateless API design - client manages conversation history (003-openai-chat-api)
- Versatile companion system prompt - homelab as one capability among many (004-system-prompt-redesign)

## Recent Changes
- 012-web-search: Added multi-backend web search with cost tracking and autonomous agent integration (Session 15)
- 011-hybrid-retrieval: Added hybrid retrieval system (vector + BM25 + graph) with RRF merging (Session 13)
- 009-context-optimization: Added Deduplicator, Ranker, BudgetManager, AccessTracker (Session 9)
- 008-memory-retrieval: Added RetrievalService with semantic search (Session 8)
- 007-memory-extraction: Added memory extraction pipeline (Session 7)
