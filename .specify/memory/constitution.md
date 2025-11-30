<!--
Sync Impact Report - Constitution Update
Version: 0.0.0 → 1.0.0
Rationale: MAJOR - Initial constitution ratification establishing core governance

Changes:
- NEW: All 7 core principles defined (Model-Agnostic, Safety-First, Compact Code, Type Safety, Async-First, MCP Extensibility, Observability)
- NEW: Technical Stack section established
- NEW: Code Quality Standards section established
- NEW: Security Requirements section established (includes local-only sensitive data requirement)
- NEW: Governance rules established

Templates Status:
- ✅ plan-template.md: Constitution Check section exists, compatible
- ✅ spec-template.md: User scenarios align with safety principles
- ✅ tasks-template.md: Task organization supports principle-driven development
- ⚠ README.md: Should reference constitution for contributors (manual follow-up)
- ⚠ CLAUDE.md: Already aligned with principles (no changes needed)
- ⚠ .gitignore: Must be created/updated to exclude .env, local configs, sensitive data

Follow-up Actions:
- Create .gitignore with .env, *.local, local_config.json, etc.
- Set up pre-commit hooks for secret scanning (optional but recommended)

Deferred Items: None
-->

# HAIA Constitution

## Core Principles

### I. Model-Agnostic Design

The agent MUST work seamlessly with any PydanticAI-supported model. Development uses Anthropic API (`claude-haiku-4-5-20251001`) for cost-efficient iteration; production targets local Ollama models (`qwen2.5-coder:7b`, `qwen2.5-coder:14b`, `llama3.1:8b`) for privacy and zero ongoing cost.

**Requirements**:
- Model selection via `HAIA_MODEL` environment variable only
- No model-specific code paths or assumptions
- Graceful degradation if preferred model unavailable
- Test critical paths with both Anthropic and Ollama models

### II. Safety-First Operations

Destructive operations MUST require explicit confirmation. The system distinguishes between safe read operations and risky write operations.

**Non-negotiable rules**:
- Read operations (query status, list resources, fetch metrics) are always safe
- Write operations (restart services, modify configs, delete resources) require user approval
- Approval mechanism integrated via PydanticAI's human-in-the-loop support
- Dry-run mode MUST be available for all write operations
- Audit logging for all approved actions

### III. Compact, Clear, Efficient Code

Code MUST be short, clear, and efficient. Style MUST be compact while maintaining readability.

**Best practices**:
- Prefer concise expressions over verbose implementations
- Use list/dict comprehensions instead of explicit loops where appropriate
- Avoid unnecessary abstractions and premature optimization
- Follow PEP 8 with line length limit of 100 characters
- Use `ruff` formatter for consistent compact style
- Remove unused imports and dead code immediately

### IV. Type Safety (NON-NEGOTIABLE)

Full type annotations are MANDATORY. All data structures MUST be Pydantic models.

**Requirements**:
- Every function has complete type hints (parameters and return values)
- All data structures are Pydantic `BaseModel` subclasses
- Run `mypy` in strict mode (`--strict` flag)
- No `Any` types except when interfacing with untyped libraries
- Use `TypedDict` for dictionary structures with known keys
- Generic types fully parameterized (e.g., `list[str]` not `list`)

**Rationale**: Type safety moves errors from runtime to development time, provides IDE autocomplete, and serves as inline documentation.

### V. Async-First Architecture

All I/O operations MUST be async. The entire application uses `asyncio` and async libraries.

**Requirements**:
- Use `httpx` for HTTP requests (not `requests`)
- All API clients are async classes with async methods
- Database operations use async drivers
- File I/O uses `aiofiles` when appropriate
- PydanticAI tools and instructions use `async def`
- Background scheduler uses async-compatible task definitions

**Rationale**: Async enables efficient handling of concurrent homelab monitoring tasks without blocking.

### VI. MCP Extensibility

New tool integrations MUST prefer MCP servers over custom implementations when community servers exist.

**Decision tree**:
1. Check MCP ecosystem for existing server → use it
2. Tool requires homelab-specific logic → custom `@agent.tool`
3. Tool is generic but no MCP server exists → consider contributing MCP server

**MCP integration**:
- Configure servers in `mcp_config.json`
- Prefer `MCPServerStreamableHTTP` transport (recommended)
- Use `MCPServerStdio` for subprocess-based servers
- Document all MCP servers in `docs/mcp-servers.md`

### VII. Observability

All agent actions, API calls, and decision points MUST be logged with structured output.

**Requirements**:
- Use Python `logging` module with structured JSON output
- Include correlation IDs for request tracing
- Log level: INFO for actions, DEBUG for decisions, ERROR for failures
- Integrate with existing Prometheus/Grafana stack via metrics
- Export metrics: request count, latency, tool usage, error rates
- Store conversation history for debugging and improvement

**Graceful degradation**: If LLM unavailable, system falls back to cached/static responses for basic queries.

## Technical Stack

### Core Dependencies

- **Python 3.11+**: Modern Python with full type hints support
- **PydanticAI**: Agent framework (latest stable version, currently 1.25.1+)
- **FastAPI**: OpenAI-compatible API server
- **httpx**: Async HTTP client for all network requests
- **pydantic-settings**: Configuration management via environment variables
- **uvicorn**: ASGI server for production deployment
- **APScheduler**: Background task scheduling
- **proxmoxer**: Proxmox API client (async mode)

### Framework Constraints

- **PydanticAI is the ONLY agent framework** - No LangChain, no AutoGen, no alternatives
- **FastAPI is the ONLY web framework** - No Flask, no Django
- Reference latest PydanticAI documentation for feature availability: https://ai.pydantic.dev/

### Configuration Management

- All configuration via `pydantic-settings` `BaseSettings` classes
- Environment variables or `.env` file for secrets
- No hardcoded credentials or API keys
- `mcp_config.json` for MCP server definitions
- Validate configuration at startup (fail-fast if misconfigured)

## Code Quality Standards

### Testing

Unit tests for tools, integration tests for agent workflows.

**Requirements**:
- Use `pytest` with `pytest-asyncio` plugin
- Test coverage: aim for >80% on core logic (tools, clients)
- Mock external APIs (Proxmox, Home Assistant) in tests
- Integration tests validate end-to-end agent workflows
- Tests MUST pass before merging to main branch

### Linting and Formatting

**Tools**:
- `ruff check src/` for linting (enforces PEP 8, security rules)
- `ruff format src/` for automatic formatting (compact style)
- `mypy --strict src/` for type checking

**Pre-commit**: Configure pre-commit hooks to run ruff and mypy automatically.

### Documentation

- Docstrings on all public functions (Google style preferred)
- Tool functions MUST have clear docstrings (passed to LLM as tool descriptions)
- Architecture decisions documented in `docs/` directory
- README updated when adding user-facing features

## Security Requirements

### Secrets Management

**All sensitive information MUST remain local-only. Only public-safe content may be pushed to remote.**

- Secrets ONLY via environment variables or `.env` files
- Never commit `.env` to version control (`.gitignore` MUST enforce)
- Never commit configuration with real hostnames, IPs, or tokens
- Use `.env.example` template with placeholder values only
- Rotate API tokens when compromised
- Git pre-commit hooks MUST scan for common secret patterns
- Review all commits for accidental credential exposure before push

### Principle of Least Privilege

- API tokens scoped to minimum required permissions
- Proxmox tokens: read-only for monitoring, specific write perms for actions
- Home Assistant long-lived tokens with limited scope
- No root/admin credentials in application

### Input Validation

- All user inputs validated via Pydantic models before processing
- Sanitize inputs to prevent injection attacks
- Validate MCP server responses before use
- Rate-limit API endpoints to prevent abuse

### No Arbitrary Code Execution

- Agent cannot execute arbitrary shell commands
- Whitelisted commands only (e.g., systemctl status, docker ps)
- Use libraries over shell commands (e.g., `proxmoxer` not `ssh`)
- Audit any shell execution with security review

## Governance

### Amendment Procedure

1. Propose amendment via pull request with rationale
2. Update constitution version following semantic versioning
3. Identify affected templates and code
4. Update dependent templates and documentation
5. Merge only after review and approval

### Versioning Policy

- **MAJOR**: Backward-incompatible principle changes or removals
- **MINOR**: New principles added or existing ones materially expanded
- **PATCH**: Clarifications, typos, non-semantic refinements

### Compliance Review

- All pull requests MUST verify compliance with constitution
- Complex features require spec-kit workflow (`/speckit.specify`, `/speckit.plan`, `/speckit.tasks`)
- Constitution supersedes all other practices
- Violations must be justified and documented or corrected

### Runtime Guidance

- See `CLAUDE.md` for AI assistant development guidance
- See `README.md` for user-facing documentation
- See `docs/architecture.md` for technical deep-dives

**Version**: 1.0.0 | **Ratified**: 2025-11-30 | **Last Amended**: 2025-11-30
