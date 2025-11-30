# HAIA - Homelab AI Assistant

## Project Initialization Document

This document provides all the context needed to initialize the HAIA project using Claude Code. It should be used to:

1. Create the initial README.md
2. Run `/speckit.constitution` to establish project principles

---

## Project Overview

**HAIA** (Homelab AI Assistant) is a Python-based AI assistant designed to help administrate, monitor, and troubleshoot homelab infrastructure. It uses local LLMs via Ollama and leverages the Model Context Protocol (MCP) for extensible tool integration.

### Core Purpose

- Monitor homelab infrastructure state (Proxmox VMs, containers, services)
- Report problems and anomalies proactively
- Warn users via notifications (Telegram, Discord, etc.)
- Suggest solutions for common issues
- Execute approved remediation actions
- Provide an interactive interface for homelab queries

### Target Infrastructure

- **Virtualization**: Proxmox VE cluster with Ceph storage
- **Home Automation**: Home Assistant with ESPHome devices
- **Containers**: Docker/Podman workloads
- **Monitoring**: Prometheus, Grafana, Alertmanager (existing stack)
- **Networking**: Standard homelab networking (VLANs, DNS, etc.)

---

## Technical Architecture

### Framework Choice: PydanticAI

HAIA uses **PydanticAI** as its agent framework because:

- Type-safe tool definitions with Pydantic models
- Native MCP client support for extensible tooling
- Clean dependency injection for API clients
- Lightweight compared to LangChain
- Structured outputs by design

### LLM Backend

**Development Phase**: Anthropic API with the cheapest model (`claude-haiku-4-5-20251001`) to minimize costs while iterating on the architecture.

**Production Goal**: Local inference via Ollama for privacy and cost-free operation:

- **Primary**: `qwen2.5-coder:7b` or `qwen2.5-coder:14b` (excellent for technical tasks)
- **Alternative**: `llama3.1:8b` (good general reasoning)
- **Lightweight**: `mistral:7b` (for resource-constrained setups)

The agent should be model-agnostic—switching between Anthropic and Ollama should only require changing the model string in configuration.

### Tool Architecture: Hybrid Approach

HAIA combines two types of tools:

1. **Custom PydanticAI Tools** (`@agent.tool`)
   - Complex, stateful operations specific to the homelab
   - Multi-step workflows requiring custom logic
   - Tight integration with existing Python code

2. **MCP Servers** (via `toolsets`)
   - Standardized, reusable tools from the MCP ecosystem
   - Community servers for common tasks (filesystem, Docker, databases)
   - Custom MCP servers for Proxmox, Home Assistant (future)

### MCP Integration

PydanticAI supports three MCP transport mechanisms:

- **MCPServerStreamableHTTP**: For HTTP-based MCP servers (recommended)
- **MCPServerSSE**: For SSE-based servers (deprecated)
- **MCPServerStdio**: For subprocess-based servers

Configuration can be loaded from a JSON file:

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

---

## Project Structure

```
haia/
├── README.md
├── pyproject.toml
├── mcp_config.json              # MCP server definitions
├── .env.example                 # Environment template
│
├── src/
│   └── haia/
│       ├── __init__.py
│       ├── main.py              # Entry point
│       ├── agent.py             # PydanticAI agent setup
│       ├── config.py            # Configuration management
│       ├── deps.py              # Dependency injection container
│       │
│       ├── tools/               # Custom @agent.tool functions
│       │   ├── __init__.py
│       │   ├── proxmox.py       # Proxmox VE operations
│       │   ├── homeassistant.py # Home Assistant integration
│       │   ├── docker.py        # Container management
│       │   └── system.py        # System diagnostics
│       │
│       ├── clients/             # API clients for external services
│       │   ├── __init__.py
│       │   ├── proxmox.py       # Proxmox API client
│       │   ├── homeassistant.py # HA REST API client
│       │   └── alertmanager.py  # Alertmanager client
│       │
│       ├── interfaces/          # User-facing interfaces
│       │   ├── __init__.py
│       │   ├── cli.py           # Interactive CLI (REPL)
│       │   ├── api.py           # REST API (FastAPI)
│       │   └── scheduler.py     # Scheduled monitoring jobs
│       │
│       └── notifications/       # Notification backends
│           ├── __init__.py
│           ├── base.py          # Abstract notifier
│           ├── telegram.py
│           └── discord.py
│
├── mcp_servers/                 # Custom MCP servers (optional, future)
│   └── README.md
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_agent.py
│   └── test_tools/
│       └── test_proxmox.py
│
└── docs/
    ├── architecture.md
    ├── configuration.md
    └── mcp-servers.md
```

---

## Key Dependencies

```toml
[project]
name = "haia"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "pydantic-ai[mcp]",          # Agent framework with MCP support
    "httpx",                      # Async HTTP client
    "pydantic-settings",          # Configuration management
    "typer[all]",                 # CLI framework
    "rich",                       # Terminal formatting
    "fastapi",                    # REST API (optional)
    "uvicorn",                    # ASGI server (optional)
    "apscheduler",                # Task scheduling
    "proxmoxer",                  # Proxmox API client
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
    "mypy",
]
```

---

## Constitution Principles

Use these principles when running `/speckit.constitution`:

### Core Principles

1. **Model-Agnostic**: The agent works with any PydanticAI-supported model. Development uses Anthropic API (Haiku) for cost efficiency; production targets local Ollama for privacy and zero ongoing cost.

2. **Safety-First**: Never execute destructive operations without explicit confirmation. Read operations are always safe; write operations require approval.

3. **Observability**: All agent actions are logged. Integration with existing monitoring stack (Prometheus metrics, structured logging).

4. **Graceful Degradation**: If the LLM is unavailable, the system should still function for basic queries and scheduled checks using cached/static responses.

5. **Configuration as Code**: All configuration in version-controlled files. No magic or hidden state.

### Technical Constraints

1. **Python 3.11+**: Modern Python with full type hints.

2. **Async-First**: All I/O operations are async. Use `asyncio` and `httpx`.

3. **Pydantic Models**: All data structures are Pydantic models for validation and serialization.

4. **No Heavy Frameworks**: Avoid LangChain, prefer lightweight solutions. PydanticAI is the only agent framework.

5. **MCP for Extensibility**: New tool integrations should prefer MCP servers over custom implementations when community servers exist.

### Code Quality

1. **Type Safety**: Full type annotations. Run `mypy` in strict mode.

2. **Testing**: Unit tests for tools, integration tests for agent workflows. Use `pytest-asyncio`.

3. **Linting**: Use `ruff` for linting and formatting.

4. **Documentation**: Docstrings for all public functions. Architecture decisions documented in `docs/`.

### Security

1. **Secrets Management**: Use environment variables or `.env` files. Never commit secrets.

2. **Principle of Least Privilege**: API tokens should have minimal required permissions.

3. **Input Validation**: All user inputs validated via Pydantic before processing.

4. **No Arbitrary Code Execution**: The agent cannot execute arbitrary shell commands unless explicitly whitelisted.

---

## README Content

Use this as the basis for the initial README.md:

```markdown
# HAIA - Homelab AI Assistant

An intelligent assistant for homelab administration, monitoring, and troubleshooting. Built with PydanticAI and powered by local LLMs via Ollama.

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
# Interactive CLI
haia

# Or run the API server
haia serve
```

## Architecture

HAIA uses a hybrid tool architecture:

- **PydanticAI** for the agent framework with type-safe tool definitions
- **MCP Servers** for extensible, standardized tool integration
- **Ollama** for local LLM inference

```
┌─────────────────────────────────────────────┐
│           HAIA Agent (PydanticAI)           │
│    Model: configurable (Anthropic/Ollama)   │
├─────────────────────────────────────────────┤
│                   Tools                     │
│  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Custom Tools    │  │ MCP Servers      │  │
│  │ @agent.tool     │  │ (via toolsets)   │  │
│  │ - Proxmox ops   │  │ - Filesystem     │  │
│  │ - HA integration│  │ - Docker         │  │
│  │ - Complex logic │  │ - Prometheus     │  │
│  └─────────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────┤
│     Interfaces: CLI | REST API | Scheduler  │
└─────────────────────────────────────────────┘
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
```

---

## Spec-Kit Constitution Prompt

When running `/speckit.constitution`, use this prompt:

```
HAIA is a Python-based homelab AI assistant using PydanticAI.

Core principles:
- Model-agnostic: Works with Anthropic API (Haiku for dev) or Ollama (production)
- Safety-first: Read operations always safe, write operations require confirmation
- Async-first: All I/O is async using asyncio and httpx
- Type-safe: Full type annotations, Pydantic models everywhere, mypy strict mode
- MCP-extensible: Prefer MCP servers for new integrations when available

Technical constraints:
- Python 3.11+ with modern features
- PydanticAI is the only agent framework (no LangChain)
- Configuration via pydantic-settings and environment variables
- Model selection via config: HAIA_MODEL env var (e.g., "anthropic:claude-haiku-4-5-20251001" or "ollama:qwen2.5-coder")
- Testing with pytest and pytest-asyncio
- Linting with ruff

Code organization:
- src/haia/ layout with clear separation: agent, tools, clients, interfaces
- Custom tools in tools/ directory using @agent.tool decorator
- API clients in clients/ directory as async classes
- User interfaces in interfaces/ (CLI via typer, API via FastAPI)

Security:
- Secrets via environment variables only
- Input validation via Pydantic
- No arbitrary shell command execution
- Principle of least privilege for API tokens
```

---

## Next Steps After Initialization

1. **Run `/speckit.constitution`** with the prompt above
2. **Run `/speckit.specify`** to define the initial feature set
3. **Run `/speckit.plan`** to create the technical implementation plan
4. **Run `/speckit.tasks`** to generate actionable tasks
5. **Run `/speckit.implement`** to start building

### Suggested Initial Feature: Basic CLI with Proxmox Status

For the first `/speckit.specify`, focus on:

```
Build the foundational HAIA CLI that can:
1. Connect to Anthropic API (claude-haiku-4-5-20251001) and verify the model is available
2. Connect to a Proxmox cluster and list VMs/containers with their status
3. Answer natural language questions about the homelab state
4. Display results in a rich terminal format

This is the minimal viable assistant that proves the architecture works.
The model should be configurable via HAIA_MODEL env var for future Ollama migration.
```

---

## References

- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [PydanticAI MCP Client](https://ai.pydantic.dev/mcp/client/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Ollama](https://ollama.ai/)
- [Proxmoxer](https://github.com/proxmoxer/proxmoxer)
- [GitHub Spec Kit](https://github.com/github/spec-kit)
