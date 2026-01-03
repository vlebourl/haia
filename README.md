# HAIA - Homelab AI Assistant

A standalone AI assistant application for homelab administration, monitoring, and troubleshooting. Built with PydanticAI and powered by local LLMs via Ollama. Exposes an OpenWebUI-compatible API for chat-based interaction.

## Features

- 🧠 **Memory System**: HAIA learns from conversations and provides personalized responses
  - Automatic memory extraction from conversations
  - Bi-temporal tracking with automatic contradiction resolution
  - Dynamic LLM-generated memory types (zero hardcoded categories)
  - BM25 full-text search + embedding-based semantic retrieval
  - Context optimization with deduplication and re-ranking
  - Three-tier lifecycle management (SHORT_TERM → LONG_TERM → ARCHIVED)
  - Automatic theme discovery with DBSCAN clustering
  - Point-in-time queries: "What did I know on date X?"
  - Neo4j graph database for persistent memory storage
- 💬 **OpenAI-Compatible API**: Chat interface compatible with OpenWebUI and other clients
- 🖥️ **Infrastructure Monitoring**: Track Proxmox VMs, containers, and services (coming soon)
- 🚨 **Proactive Alerts**: Get notified about problems before they escalate (coming soon)
- 🔧 **Troubleshooting Assistance**: AI-powered suggestions for common issues (coming soon)
- 🏠 **Home Assistant Integration**: Control and query your smart home (coming soon)
- 🔌 **Extensible via MCP**: Add new capabilities through Model Context Protocol servers (coming soon)

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for Neo4j database)
- Anthropic API key (for development) or Ollama (for production)
- Ollama with nomic-embed-text model (for memory embeddings)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/haia.git
cd haia

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your configuration
# - ANTHROPIC_API_KEY (for development)
# - HAIA_MODEL=anthropic:claude-haiku-4-5-20251001 (or ollama:qwen2.5-coder for local)
# - PROXMOX_HOST, PROXMOX_USER, PROXMOX_TOKEN
# - HOMEASSISTANT_URL, HOMEASSISTANT_TOKEN
```

### Running

```bash
# One-command deployment (production)
./deployment/docker-install.sh

# Or for development (Neo4j in Docker, HAIA native)
docker compose -f deployment/docker-compose.dev.yml up neo4j -d
uv run uvicorn haia.api.app:app --reload --host 0.0.0.0 --port 8000

# The API will be available at http://localhost:8000
# Compatible with OpenWebUI - point it to http://localhost:8000/v1
```

### Memory System

HAIA automatically learns from your conversations:

1. **Extraction**: After conversations end, memories are extracted (preferences, technical context, decisions)
2. **Storage**: Memories stored in Neo4j graph database with confidence scores
3. **Retrieval**: Relevant memories retrieved using semantic search when you chat
4. **Optimization**: Memories deduplicated, re-ranked, and kept within token budget

Configuration:
```bash
# In .env file
EXTRACTION_MODEL=anthropic:claude-haiku-4-5-20251001  # LLM for extraction
EMBEDDING_MODEL=ollama:nomic-embed-text               # Embeddings for retrieval
NEO4J_PASSWORD=your_secure_password                    # Database password
```

#### Memory Consolidation Lifecycle

HAIA automatically manages memory tiers to prevent unbounded database growth while preserving important memories:

**Three-Tier System:**
```
SHORT_TERM (new, <7 days) → LONG_TERM (important) → ARCHIVED (low-priority)
```

**Priority Scoring:**
- **Access Frequency** (40%): How often the memory is retrieved
- **Recency** (30%): How recently accessed (with decay)
- **Confidence** (30%): Original extraction confidence

**Tier Transitions:**
- Promotion: `priority_score >= 0.7` (SHORT_TERM → LONG_TERM)
- Archival: `priority_score < 0.2` (LONG_TERM → ARCHIVED)
- Runs automatically daily at 3 AM (configurable)

**Decay Strategies:**
- **ExponentialDecay** (default): Adaptive half-life based on access patterns
- **EbbinghausDecay**: Classic forgetting curve with access-based stability
- **LinearDecay**: Simple linear decay with access multiplier

📖 See [Consolidation Documentation](src/haia/consolidation/README.md) for details.

#### Theme Discovery

HAIA automatically discovers semantic themes in your memories using DBSCAN clustering:

**Features:**
- Automatic clustering of similar memories by embedding similarity
- LLM-generated human-readable theme labels (3-8 words)
- Quality validation with silhouette scores
- Weekly automated discovery (Sundays 2 AM, configurable)
- REST API for theme exploration

**Example Themes:**
- "Docker container orchestration and networking"
- "Proxmox VM provisioning and HA setup"
- "Home Assistant automation workflows"
- "Monitoring and alerting infrastructure"

**Configuration:**
```bash
# In .env file
THEME_DISCOVERY_ENABLED=true
THEME_DISCOVERY_SCHEDULE=0 2 * * 0     # Weekly Sundays at 2 AM
THEME_LABELING_MODEL=anthropic:claude-haiku-4-5-20251001
DBSCAN_EPS=0.3                         # Distance threshold (0.0-1.0)
DBSCAN_MIN_SAMPLES=3                   # Minimum cluster core size
MIN_THEME_CLUSTER_SIZE=3               # Minimum memories per theme
MIN_SILHOUETTE_SCORE=0.5               # Quality threshold
```

📖 See [Theme Discovery Documentation](src/haia/discovery/README.md) for details.

## Architecture

HAIA is a **standalone application** that runs as an API server, compatible with OpenWebUI and other OpenAI-compatible frontends.

**Core Components:**

- **PydanticAI** - Agent framework with type-safe tool definitions
- **FastAPI** - OpenAI-compatible API endpoints
- **Neo4j** - Graph database for persistent memory storage
- **Ollama** - Local LLM inference (or Anthropic for development)
- **MCP Servers** - Extensible, standardized tool integration (planned)

```
┌──────────────────────────────────────────────┐
│         OpenWebUI / Chat Interface           │
└────────────────┬─────────────────────────────┘
                 │ HTTP (OpenAI-compatible API)
┌────────────────▼─────────────────────────────┐
│         FastAPI Server (/v1/chat)            │
│              + Memory Retrieval              │
├──────────────────────────────────────────────┤
│         HAIA Agent (PydanticAI)              │
│   Model: configurable (Anthropic/Ollama)     │
│        + Retrieved Memory Context            │
├──────────────────────────────────────────────┤
│            Memory System (Phase 2)           │
│  ┌──────────────────────────────────────┐    │
│  │ Extraction → Storage → Retrieval     │    │
│  │ Confidence → Embeddings → Ranking    │    │
│  │ Deduplication → Token Budget         │    │
│  └──────────────┬───────────────────────┘    │
│                 │                             │
│     ┌───────────▼──────────┐                 │
│     │  Neo4j Graph DB      │                 │
│     │  - Memory nodes      │                 │
│     │  - Vector index      │                 │
│     │  - Access tracking   │                 │
│     └──────────────────────┘                 │
├──────────────────────────────────────────────┤
│              Tools (Phase 3+)                │
│  ┌─────────────────┐  ┌──────────────────┐   │
│  │ Custom Tools    │  │ MCP Servers      │   │
│  │ @agent.tool     │  │ (via toolsets)   │   │
│  │ - Proxmox ops   │  │ - Filesystem     │   │
│  │ - HA integration│  │ - Docker         │   │
│  │ - Alerting      │  │ - Prometheus     │   │
│  └─────────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────┘
```

## MCP Servers

HAIA can connect to MCP servers for extended functionality. Configure in `mcp_config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/var/log"]
    }
  }
}
```

## Development

```bash
# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

MIT
