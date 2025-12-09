# HAIA - Homelab AI Assistant

A standalone AI assistant application for homelab administration, monitoring, and troubleshooting. Built with PydanticAI and powered by local LLMs via Ollama. Exposes an OpenWebUI-compatible API for chat-based interaction.

## Features

- 🧠 **Memory System**: HAIA learns from conversations and provides personalized responses
  - Automatic memory extraction from conversations
  - Embedding-based semantic memory retrieval
  - Context optimization with deduplication and re-ranking
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
