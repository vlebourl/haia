# HAIA - Homelab AI Assistant

A standalone AI assistant application for homelab administration, monitoring, and troubleshooting. Built with PydanticAI and powered by local LLMs via Ollama. Exposes an OpenWebUI-compatible API for chat-based interaction.

## Features

- 🖥️ **Infrastructure Monitoring**: Track Proxmox VMs, containers, and services
- 🚨 **Proactive Alerts**: Get notified about problems before they escalate
- 🔧 **Troubleshooting Assistance**: AI-powered suggestions for common issues
- 🏠 **Home Assistant Integration**: Control and query your smart home
- 🔌 **Extensible via MCP**: Add new capabilities through Model Context Protocol servers

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key (for development) or Ollama (for production)
- Access to your homelab APIs (Proxmox, Home Assistant, etc.)

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
# Start the API server (OpenWebUI-compatible)
haia serve

# The API will be available at http://localhost:8000
# Compatible with OpenWebUI - point it to http://localhost:8000/v1
```

## Architecture

HAIA is a **standalone application** that runs as an API server, compatible with OpenWebUI and other OpenAI-compatible frontends.

**Core Components:**

- **PydanticAI** - Agent framework with type-safe tool definitions
- **FastAPI** - OpenAI-compatible API endpoints
- **MCP Servers** - Extensible, standardized tool integration
- **Ollama** - Local LLM inference (or Anthropic for development)

```
┌──────────────────────────────────────────────┐
│         OpenWebUI / Chat Interface           │
└────────────────┬─────────────────────────────┘
                 │ HTTP (OpenAI-compatible API)
┌────────────────▼─────────────────────────────┐
│         FastAPI Server (/v1/chat)            │
├──────────────────────────────────────────────┤
│         HAIA Agent (PydanticAI)              │
│   Model: configurable (Anthropic/Ollama)     │
├──────────────────────────────────────────────┤
│                  Tools                       │
│  ┌─────────────────┐  ┌──────────────────┐   │
│  │ Custom Tools    │  │ MCP Servers      │   │
│  │ @agent.tool     │  │ (via toolsets)   │   │
│  │ - Proxmox ops   │  │ - Filesystem     │   │
│  │ - HA integration│  │ - Docker         │   │
│  │ - Alerting      │  │ - Prometheus     │   │
│  └─────────────────┘  └──────────────────┘   │
├──────────────────────────────────────────────┤
│     Background: Scheduler (APScheduler)      │
│        - Periodic infrastructure checks      │
│        - Proactive alerting                  │
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
