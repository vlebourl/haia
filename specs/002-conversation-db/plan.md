# Implementation Plan: Conversation Database Persistence

**Branch**: `002-conversation-db` | **Date**: 2025-11-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-conversation-db/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a persistent conversation storage layer using SQLite with async SQLAlchemy to store chat messages with automatic context window management (20-message limit for LLM context). The system maintains complete conversation history in the database while intelligently managing which messages are included in the LLM context window for optimal performance. Supports automatic schema initialization, migrations via Alembic, and graceful error handling.

**Technical Approach**: Repository pattern with async SQLAlchemy models, automatic context window tracking via query logic, Alembic migrations for schema versioning, connection pooling for concurrent async operations.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `sqlalchemy[asyncio]>=2.0` (async ORM)
- `aiosqlite>=0.17` (async SQLite driver)
- `alembic>=1.12` (database migrations)
- `pydantic>=2.0` (data validation, already available)

**Storage**: SQLite database file (configurable location via `DATABASE_URL` environment variable)
**Testing**: `pytest` with `pytest-asyncio` plugin, mock async database sessions
**Target Platform**: Linux server (part of HAIA FastAPI application)
**Project Type**: Single project (library component within larger application)

**Performance Goals**:
- Conversation retrieval < 100ms for 1000+ message conversations
- Async database operations with no blocking
- Connection pooling to handle concurrent API requests
- Context window query optimization (retrieve only last 20 messages efficiently)

**Constraints**:
- Must use async operations exclusively (no sync database calls)
- Must handle concurrent writes safely (async SQLAlchemy manages locking)
- Database file must be created automatically on first startup
- Migrations must apply automatically on application start

**Scale/Scope**:
- Single user MVP (no multi-user support)
- Expected: hundreds of messages per conversation
- Thousands of total messages across all conversations
- ~300-500 lines of code (models + repository + migrations)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Model-Agnostic Design N/A

**Status**: N/A - This feature does not interact with LLM models

**Rationale**: Database persistence layer is infrastructure, consumed by LLM abstraction layer but doesn't make model-specific assumptions.

### Principle II: Safety-First Operations ✅

**Status**: PASS - All database operations are safe (read/write to local file)

**Compliance**:
- ✅ Database operations are local file writes (safe, no infrastructure impact)
- ✅ No destructive operations (messages stored permanently, deletions out of scope)
- N/A User approval not needed (local data persistence)
- ✅ Audit logging via SQLAlchemy events for all writes

### Principle III: Compact, Clear, Efficient Code ✅

**Status**: PASS - Repository pattern keeps code organized and minimal

**Compliance**:
- ✅ Repository pattern avoids code duplication
- ✅ SQLAlchemy ORM eliminates boilerplate SQL
- ✅ Context window logic centralized in repository query
- ✅ No premature abstractions (direct SQLAlchemy usage)

**Design decisions for compactness**:
- Use SQLAlchemy declarative models (not manual table definitions)
- Repository class with focused methods (create_conversation, add_message, get_context)
- Alembic auto-generates migrations (no manual SQL)

### Principle IV: Type Safety (NON-NEGOTIABLE) ✅

**Status**: PASS - Full type annotations with Pydantic models

**Compliance**:
- ✅ All repository methods fully typed (async def → ReturnType)
- ✅ SQLAlchemy models use Mapped[] annotations (SQLAlchemy 2.0 style)
- ✅ Pydantic models for data transfer (ConversationCreate, MessageCreate)
- ✅ Mypy strict mode compatible (no Any types)

### Principle V: Async-First Architecture ✅

**Status**: PASS - All database operations are async

**Compliance**:
- ✅ AsyncEngine and async_sessionmaker from SQLAlchemy
- ✅ All repository methods use `async def`
- ✅ `aiosqlite` driver for async SQLite access
- ✅ Async context managers for session lifecycle

### Principle VI: MCP Extensibility N/A

**Status**: N/A - Database layer is not exposed as MCP tool

**Rationale**: Internal infrastructure component. Future MCP tools (conversation search, export) would consume this layer but the database itself isn't an MCP server.

### Principle VII: Observability ✅

**Status**: PASS - Database operations logged

**Compliance**:
- ✅ SQLAlchemy event hooks log all queries (DEBUG level)
- ✅ Repository methods log key operations (INFO level)
- ✅ Error handling logs failures with context
- ✅ Metrics: query count, latency, error rates (future Prometheus integration)

**Additional observability**:
- Migration success/failure logged at startup
- Conversation/message counts tracked for monitoring
- Database file size monitoring (alert if excessive growth)

---

**GATE RESULT**: ✅ PASS - All applicable principles satisfied. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/002-conversation-db/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - SQLAlchemy async patterns
├── data-model.md        # Phase 1 output - database schema design
├── quickstart.md        # Phase 1 output - usage guide
├── contracts/           # Phase 1 output - repository interface
│   └── repository.json  # Repository method specifications
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/haia/
├── db/
│   ├── __init__.py           # Public exports: get_db, Repository
│   ├── models.py             # SQLAlchemy models: Conversation, Message
│   ├── repository.py         # Repository class with async methods
│   ├── session.py            # Database session management, engine creation
│   └── migrations/           # Alembic migration files
│       ├── env.py            # Alembic environment config
│       ├── script.py.mako    # Migration template
│       └── versions/         # Migration version files
│           └── 001_initial_schema.py
│
├── config.py                 # Configuration (DATABASE_URL already defined)
└── llm/                      # Existing LLM abstraction layer

tests/unit/db/
├── test_models.py            # Test model validation and relationships
├── test_repository.py        # Test repository methods (mocked sessions)
└── test_session.py           # Test session lifecycle

tests/integration/
└── test_db_persistence.py    # Integration tests with real SQLite database
```

**Structure Decision**: Single project structure selected. Database layer is a library component within the larger HAIA application, similar to the LLM abstraction layer. Follows existing project conventions with clear separation between models, repository logic, and session management.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations - Constitution Check passed. No complexity justification needed.

---

*Constitution Check completed. Proceeding to Phase 0: Research & Design Decisions.*
