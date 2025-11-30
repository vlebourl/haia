# Brainstorming Session: HAIA MVP Chat Feature

**Date**: 2025-11-30
**Participants**: Project Team
**Facilitator**: Scrum Master / Claude Code
**Duration**: Interactive Session
**Session Type**: MVP Scope Definition & Architecture Planning

---

## 1. Executive Summary

### Feature Overview
Build the Minimum Viable Product (MVP) for HAIA - a chat interface that allows homelab administrators to interact with an AI assistant through an OpenAI-compatible API. The MVP focuses on core chat functionality with a well-designed architecture that enables future extensibility.

### Key Decisions
1. **Simplified Storage**: SQLite instead of PostgreSQL for faster MVP delivery
2. **Single Model**: Anthropic Claude only (with abstraction layer for future providers)
3. **No Streaming**: Defer SSE streaming to post-MVP to reduce complexity
4. **Persistent Conversations**: Smart context windowing (last 20 messages) for ongoing troubleshooting
5. **Single User**: No authentication or multi-user support in MVP
6. **Expert Persona**: Casual, concise, proactive assistant assuming expert-level knowledge

### Strategic Goals
- ✅ Validate core concept: AI-powered homelab assistant
- ✅ Establish solid architectural foundation (LLMClient abstraction)
- ✅ Enable OpenWebUI integration for immediate usability
- ✅ Fast time-to-value: Get working chat in hands of user quickly

---

## 2. Problem Statement & Context

### The Problem
Homelab administrators need an AI assistant that:
- Understands infrastructure context (Proxmox, Docker, networking)
- Provides expert-level troubleshooting assistance
- Maintains conversation continuity across sessions
- Respects privacy with local LLM support (future)
- Integrates with existing tools (OpenWebUI)

### Current State
- Project has constitution and roadmap defined
- No working code yet - greenfield development
- Architecture decisions documented in CLAUDE.md
- Target users: Expert-level homelab administrators

### Target Users
- **Primary**: Solo homelab operators running Proxmox clusters
- **Technical Level**: Expert - comfortable with Linux, virtualization, containers
- **Preferred Interaction**: Casual but efficient - "senior colleague" vibe
- **Use Cases**: Troubleshooting, status checks, configuration guidance

### Success Metrics
- User can chat with AI through OpenWebUI
- Conversation history persists across sessions
- Responses are contextually relevant (uses last 20 messages)
- AI persona feels appropriate (casual expert, concise)
- Architecture supports adding new models/features easily

---

## 3. Brainstorming Results

### 3.1 Core Ideas & Insights

#### Scope Simplification
**Original Roadmap**: 4 LLM providers, PostgreSQL, streaming, complex infra
**MVP Reality**: Single provider, SQLite, no streaming, core chat only

**Key Insight**: "Just chatting with the AI with the right persona" - the user explicitly identified that the MVP should prove the chat interaction works well, not demonstrate all technical capabilities.

#### Architectural Decisions

**LLMClient Abstraction (Fundamental)**
- Build abstraction layer even for single model
- Rationale: Architectural foundation - not premature optimization
- Future-proof: Adding Ollama/OpenAI/Gemini later is trivial
- Clean separation: Business logic independent of LLM provider

**PydanticAI Integration (Option A)**
```
FastAPI /v1/chat/completions
    ↓
PydanticAI Agent (persona + system prompts)
    ↓
PydanticAI Model Adapter
    ↓
LLMClient (abstract interface)
    ↓
AnthropicClient (Claude Haiku/Sonnet)
    ↓
Anthropic API
```

**Why Option A over direct LLM use:**
- Enables future tool use (Proxmox, MCP servers)
- Structured prompt management
- Built-in conversation handling
- Aligns with roadmap Phase 2+ features

#### Conversation Strategy

**Persistent with Context Windowing**
- Store ALL messages in SQLite (full history)
- Load LAST 20 messages into LLM context
- Single continuous conversation thread
- No session management complexity

**Rationale for this approach:**
- Homelab troubleshooting spans hours/days
- Expert users need continuity ("the VM you mentioned yesterday")
- 20 messages ≈ 10 back-and-forth exchanges ≈ typical troubleshooting session
- Token-efficient while maintaining useful context

#### Persona Design

**"Senior DevOps Buddy" Character:**
- 🗣️ **Casual**: "Check Ceph first - probably rebalancing again"
- ⚡ **Concise**: No fluff, straight to actionable advice
- 🔮 **Proactive**: Spots patterns, suggests checks
- 🎯 **Expert-level**: Assumes user knows their infrastructure

**Example Interaction:**
```
User: "VMs running slow on node2"
HAIA: "Node2 CPU pinned? Check `pvesh get /nodes/node2/status`.
      Also verify Ceph isn't rebalancing - that'll murder VM I/O.
      `ceph -s` should show HEALTH_OK and no recovery ops."
```

### 3.2 Ideas Categorized

#### Must Have (P0 - MVP Blockers)
1. ✅ **Configuration Management** - pydantic-settings, .env for API key
2. ✅ **LLMClient Abstraction** - Abstract base + AnthropicClient implementation
3. ✅ **PydanticAI Agent Setup** - Agent initialization with homelab persona
4. ✅ **SQLite Database** - Conversations table, messages table
5. ✅ **FastAPI Chat Endpoint** - `/v1/chat/completions` (OpenAI-compatible)
6. ✅ **Context Window Logic** - Load last 20 messages for each request

#### Should Have (P1 - Important but not blockers)
- 📋 **Logging & Observability** - Structured logs for debugging
- 📋 **Error Handling** - Graceful LLM failures, API errors
- 📋 **Environment Setup Docs** - README with setup instructions
- 📋 **Basic Testing** - Unit tests for LLMClient, integration test for chat flow

#### Could Have (P2 - Nice to have)
- 💡 **Configuration Validation** - Fail-fast on startup with clear error messages
- 💡 **Health Check Endpoint** - `/health` for monitoring
- 💡 **CORS Configuration** - For OpenWebUI web client
- 💡 **Docker Compose** - Easy local development setup

#### Won't Have (Deferred to Post-MVP)
- ❌ **Streaming Responses** - SSE implementation (future)
- ❌ **Multi-Model Support** - Ollama, OpenAI, Gemini providers (future)
- ❌ **PostgreSQL** - Production database (future)
- ❌ **User Authentication** - Multi-user support (future)
- ❌ **Proxmox Tools** - Agent tools for infrastructure (Phase 2)
- ❌ **MCP Servers** - Extensibility framework (Phase 2)
- ❌ **Background Scheduler** - Proactive monitoring (Phase 3)

### 3.3 Risk Analysis

#### Technical Risks

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| PydanticAI learning curve slows development | Medium | Medium | Study PydanticAI docs first, start with simple agent setup |
| Anthropic API costs during dev/testing | Low | High | Use Claude Haiku (cheapest), implement request logging to track costs |
| LLMClient abstraction over-engineered | Low | Medium | Keep interface minimal - only methods actually needed for MVP |
| Context window (20 msgs) insufficient | Medium | Low | Make configurable, test with real troubleshooting scenarios |
| Persona prompts don't feel right | Medium | Medium | Iterate on system prompts, test with real homelab questions |
| SQLite performance issues | Low | Low | SQLite handles chat history easily, no complex queries |

#### Scope Risks

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| Scope creep - adding features mid-MVP | High | Medium | Stick to defined scope, document ideas for post-MVP |
| "One more model" syndrome | Medium | Medium | Firm decision: Anthropic only, add others after MVP validates concept |
| Pressure to add Proxmox tools early | Medium | Medium | Explain: MVP validates chat, tools come in Phase 2 |

#### User Acceptance Risks

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| Persona too casual or not casual enough | Medium | Low | Test early, adjust system prompts based on feedback |
| Context window feels "forgetful" | Medium | Low | Make configurable (20 is starting point), can increase if needed |
| Lacks streaming - feels slow | Low | Low | Defer streaming - MVP users understand it's v1 |

---

## 4. Prioritization & Roadmap Alignment

### MoSCoW Prioritization

#### Must Have
- Configuration management with pydantic-settings
- LLMClient abstract interface + AnthropicClient
- PydanticAI agent with persona system prompts
- SQLite database schema (conversations, messages)
- FastAPI `/v1/chat/completions` endpoint
- Conversation history loading (last 20 messages)
- OpenAI-compatible request/response format
- Basic error handling

#### Should Have
- Structured logging with correlation IDs
- Configuration validation at startup
- README with setup instructions
- Basic unit tests for critical paths
- CORS configuration for web clients

#### Could Have
- Health check endpoint
- Docker Compose for local dev
- Message timestamp tracking
- Conversation metadata (created_at, updated_at)

#### Won't Have (This Release)
- Streaming, multi-model, PostgreSQL, auth, tools, MCP, scheduler

### Roadmap Impact

**Original Roadmap Phases:**
- Phase 0: Configuration, LLM Abstraction (4 providers), Agent, PostgreSQL
- Phase 1: OpenAI API with streaming

**Simplified MVP Roadmap:**
- **Phase 0-MVP**: Configuration, LLM Abstraction (Anthropic only), Agent, SQLite
- **Phase 1-MVP**: OpenAI API (no streaming)

**Post-MVP Additions (in order):**
1. Add streaming support to chat endpoint
2. Add Ollama provider to LLMClient
3. Migrate SQLite → PostgreSQL
4. Add remaining providers (OpenAI, Gemini)
5. Continue with original Phase 2 (Proxmox tools, MCP)

---

## 5. Implementation Strategy

### 5.1 Technical Approach

#### Project Structure
```
src/haia/
├── config.py              # Configuration (pydantic-settings)
├── llm/
│   ├── client.py          # LLMClient abstract base class
│   └── providers/
│       └── anthropic.py   # AnthropicClient implementation
├── agent.py               # PydanticAI agent setup + persona
├── db/
│   ├── models.py          # SQLAlchemy models (conversations, messages)
│   └── database.py        # Async SQLite client
├── interfaces/
│   └── api.py             # FastAPI /v1/chat/completions endpoint
└── main.py                # Entry point (uvicorn server)
```

#### Component Breakdown

**1. Configuration Management (`config.py`)**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    model_name: str = "claude-haiku-4-5-20251001"
    context_window_size: int = 20
    database_url: str = "sqlite+aiosqlite:///./haia.db"

    class Config:
        env_file = ".env"
```

**2. LLMClient Abstraction (`llm/client.py`)**
```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class Message(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str

class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict  # tokens, etc.

class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7
    ) -> LLMResponse:
        """Send chat messages and get response"""
        pass
```

**3. Anthropic Implementation (`llm/providers/anthropic.py`)**
```python
import anthropic
from ..client import LLMClient, Message, LLMResponse

class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7
    ) -> LLMResponse:
        # Convert messages to Anthropic format
        # Call API
        # Return LLMResponse
        pass
```

**4. PydanticAI Agent Setup (`agent.py`)**
```python
from pydantic_ai import Agent
from .llm.client import LLMClient

HOMELAB_PERSONA = """You are HAIA, a senior DevOps engineer's AI assistant.

Your style:
- Casual and direct - talk like a senior colleague
- Concise - get to the point, no fluff
- Proactive - spot issues and suggest checks
- Expert-level - assume user knows their infrastructure

Focus on:
- Proxmox VE, Ceph storage
- Docker/Podman containers
- Linux system administration
- Network troubleshooting

Always provide actionable commands and specific checks.
"""

def create_agent(llm_client: LLMClient) -> Agent:
    # Create PydanticAI agent with custom LLM adapter
    # Set system prompt to HOMELAB_PERSONA
    # Return configured agent
    pass
```

**5. Database Schema (`db/models.py`)**
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int]
    role: Mapped[str]  # "user" | "assistant" | "system"
    content: Mapped[str]
    timestamp: Mapped[datetime]
```

**6. FastAPI Endpoint (`interfaces/api.py`)**
```python
from fastapi import FastAPI
from pydantic import BaseModel

class ChatCompletionRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    temperature: float = 0.7

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # Load last 20 messages from DB
    # Append request.messages
    # Call PydanticAI agent
    # Save assistant response to DB
    # Return OpenAI-compatible response
    pass
```

### 5.2 Development Phases

#### Phase 1: Foundation (Week 1)
**Goal**: Core infrastructure ready
- Set up project structure (uv, pyproject.toml)
- Implement configuration management
- Create LLMClient abstract interface
- Implement AnthropicClient
- Write unit tests for LLMClient

**Validation**: Can instantiate AnthropicClient and make test API call

#### Phase 2: Database & Agent (Week 1)
**Goal**: Storage and AI agent working
- Set up SQLite database with Alembic
- Create SQLAlchemy models
- Implement PydanticAI agent with persona
- Test agent with sample conversations

**Validation**: Agent responds with appropriate persona

#### Phase 3: API Integration (Week 2)
**Goal**: Working chat endpoint
- Implement FastAPI server
- Create `/v1/chat/completions` endpoint
- Integrate conversation history loading
- Implement OpenAI-compatible response format
- Add CORS configuration

**Validation**: Can chat via curl/Postman

#### Phase 4: Testing & Polish (Week 2)
**Goal**: Production-ready MVP
- Integration tests for full chat flow
- Error handling for edge cases
- README with setup instructions
- Docker Compose for easy deployment
- Test with OpenWebUI

**Validation**: OpenWebUI successfully connects and chats

### 5.3 Testing Strategy

#### Unit Tests
- `LLMClient` interface contract
- `AnthropicClient` API calls (mocked)
- Database CRUD operations
- Message formatting/conversion

#### Integration Tests
- Full chat flow: request → DB → Agent → DB → response
- Conversation history loading (verify last 20 messages)
- Error scenarios (API failure, DB error)

#### Manual Testing
- OpenWebUI integration
- Persona validation (does it feel right?)
- Context window effectiveness
- Error message clarity

---

## 6. Action Items & Ownership

### Immediate Actions (Next 24-48 hours)

| # | Action | Owner | Deadline | Status |
|---|--------|-------|----------|--------|
| 1 | Get Anthropic API key from console | User | 2025-12-01 | ⏳ Pending |
| 2 | Initialize project with uv/pyproject.toml | Dev | 2025-12-01 | ⏳ Pending |
| 3 | Create .env.example template | Dev | 2025-12-01 | ⏳ Pending |
| 4 | Implement config.py with pydantic-settings | Dev | 2025-12-01 | ⏳ Pending |
| 5 | Create LLMClient abstract interface | Dev | 2025-12-02 | ⏳ Pending |

### Short-term Actions (Week 1)

| # | Action | Owner | Deadline | Status |
|---|--------|-------|----------|--------|
| 6 | Implement AnthropicClient | Dev | 2025-12-03 | ⏳ Pending |
| 7 | Set up SQLite database with Alembic | Dev | 2025-12-04 | ⏳ Pending |
| 8 | Create SQLAlchemy models (conversations, messages) | Dev | 2025-12-04 | ⏳ Pending |
| 9 | Implement PydanticAI agent with persona | Dev | 2025-12-05 | ⏳ Pending |
| 10 | Test agent responses manually | Dev | 2025-12-05 | ⏳ Pending |

### Medium-term Actions (Week 2)

| # | Action | Owner | Deadline | Status |
|---|--------|-------|----------|--------|
| 11 | Create FastAPI server structure | Dev | 2025-12-06 | ⏳ Pending |
| 12 | Implement /v1/chat/completions endpoint | Dev | 2025-12-07 | ⏳ Pending |
| 13 | Add conversation history loading logic | Dev | 2025-12-08 | ⏳ Pending |
| 14 | Write integration tests | Dev | 2025-12-09 | ⏳ Pending |
| 15 | Create README with setup instructions | Dev | 2025-12-09 | ⏳ Pending |
| 16 | Test with OpenWebUI | User | 2025-12-10 | ⏳ Pending |

### Dependencies & Blockers

- **Blocker**: Need Anthropic API key before development can proceed
- **Dependency**: Database schema must be complete before API implementation
- **Dependency**: LLMClient must be working before PydanticAI integration

---

## 7. Key Decisions & Rationale

### Decision Log

| Decision | Rationale | Alternatives Considered | Trade-offs |
|----------|-----------|------------------------|------------|
| **SQLite over PostgreSQL** | Faster MVP, no external dependencies | PostgreSQL (future) | May need migration later, but SQLite sufficient for single-user |
| **Single model (Anthropic)** | Reduce complexity, focus on chat UX | Multi-model from start | Less flexibility initially, but abstraction layer makes adding models trivial later |
| **No streaming** | Simpler implementation, SSE complexity deferred | Streaming from day 1 | Slower perceived performance, but acceptable for MVP |
| **LLMClient abstraction** | Architectural foundation, enables future providers | Direct Anthropic integration | Slight over-engineering for MVP, but user explicitly wants this as "fundamental" |
| **PydanticAI integration** | Enables future tooling (Proxmox, MCP) | Direct LLM calls | More complex, but aligns with roadmap Phase 2+ |
| **20-message context window** | Balance between context and token cost | Full history, or 10/30/50 messages | Configurable, can adjust based on real usage |
| **Casual expert persona** | Matches target user (expert homelab admin) | Formal/verbose/beginner-friendly | May feel too casual for some, but user explicitly requested this |
| **Single continuous conversation** | Simplest for MVP | Multi-conversation management | No conversation organization, but matches troubleshooting workflow |

### Assumptions Made

1. **User has Anthropic API access** via existing subscription
2. **OpenWebUI is the primary UI** for MVP testing/usage
3. **Single-user deployment** is sufficient for validation
4. **20 messages ≈ typical troubleshooting session** (can adjust if wrong)
5. **SQLite performance** is adequate for chat message storage
6. **No auth needed** for homelab (trusted network assumption)

### Open Questions

- ✅ ~~Which LLM provider for MVP?~~ → Anthropic Claude
- ✅ ~~Streaming or no streaming?~~ → No streaming in MVP
- ✅ ~~PostgreSQL or SQLite?~~ → SQLite for MVP
- ✅ ~~Full LLM abstraction or direct integration?~~ → Full abstraction (fundamental architectural piece)
- ⏳ **Exact persona prompt wording** → Iterate during development
- ⏳ **Context window size** → Start with 20, tune based on usage
- ⏳ **Error message strategy** → Define during implementation

---

## 8. Follow-up & Next Steps

### Immediate Next Steps (Today)

1. **Get Anthropic API key**
   - Visit https://console.anthropic.com/
   - Create new API key
   - Store securely (will add to .env)

2. **Create feature specification**
   - Use `/speckit.specify` to create detailed spec for "LLM Abstraction Layer"
   - This is the most critical architectural component
   - Spec should include interface design, error handling, testing approach

3. **Update ROADMAP.md (Optional)**
   - Add "MVP-Simplified" section noting the scope reduction
   - Document SQLite → PostgreSQL migration path
   - Clarify single-model → multi-model progression

### Development Workflow

**Recommended spec-kit flow:**
1. `/speckit.specify` - LLM Abstraction Layer (start here)
2. `/speckit.plan` - Create technical implementation plan
3. `/speckit.tasks` - Break down into development tasks
4. `/speckit.implement` - Execute implementation

**OR: Rapid development approach:**
- Skip spec-kit for MVP (save time)
- Code directly using this brainstorming doc as guide
- Use spec-kit for Phase 2+ features

### Success Criteria Review

**MVP is successful when:**
- ✅ User can send message via OpenWebUI
- ✅ HAIA responds with appropriate casual expert persona
- ✅ Conversation history persists across browser sessions
- ✅ Responses feel contextually aware (references earlier messages)
- ✅ Setup is documented and reproducible
- ✅ Architecture supports adding new models/features easily

### Post-MVP Planning

**After MVP validation, prioritize:**
1. **Streaming responses** - Improve UX significantly
2. **Ollama integration** - Enable local models (privacy + cost)
3. **Basic Proxmox tool** - Demonstrate infrastructure integration value
4. **MCP framework** - Prove extensibility story

---

## Appendices

### A. Reference Materials

- **HAIA Constitution**: `.specify/memory/constitution.md`
- **Project Guidance**: `CLAUDE.md`
- **Full Roadmap**: `ROADMAP.md`
- **PydanticAI Docs**: https://ai.pydantic.dev/
- **Anthropic API Docs**: https://docs.anthropic.com/
- **OpenAI API Spec**: https://platform.openai.com/docs/api-reference/chat

### B. Glossary

- **MVP**: Minimum Viable Product - simplest version that proves concept
- **LLMClient**: Abstract interface for LLM providers (Anthropic, Ollama, etc.)
- **PydanticAI**: Agent framework with type-safe tool definitions
- **MCP**: Model Context Protocol - extensibility framework for tools
- **OpenWebUI**: Web-based chat interface compatible with OpenAI API
- **SSE**: Server-Sent Events - streaming protocol for real-time responses
- **Context Window**: Number of recent messages loaded into LLM for each request

### C. Technical Debt Tracker

| Item | Reason | Mitigation Plan | Priority |
|------|--------|-----------------|----------|
| SQLite instead of PostgreSQL | Faster MVP | Migrate to PostgreSQL when adding multi-user support | P2 |
| No streaming | Implementation complexity | Add SSE streaming in first post-MVP iteration | P1 |
| Single model only | Reduce scope | Add Ollama next (high priority), then OpenAI/Gemini | P1 |
| No authentication | Single-user assumption | Add auth when supporting multiple users | P3 |
| Hardcoded 20-message limit | Quick decision | Make configurable, expose in config.py | P2 |
| No conversation management | Simplicity | Add "new conversation" feature if users request | P3 |

### D. Session Retrospective

**What Worked Well:**
- ✅ Progressive questioning approach revealed true MVP scope
- ✅ User clearly articulated priorities (abstraction layer = fundamental)
- ✅ Scope reduction from roadmap to MVP was significant but validated
- ✅ Persona definition was clear and actionable

**What Could Be Improved:**
- ⚠️ Could have validated context window size with example scenarios
- ⚠️ Didn't discuss observability/logging in detail (deferred to implementation)

**Key Insights:**
- User values architectural integrity over rapid MVP (LLMClient abstraction)
- "Just chatting with the AI with the right persona" = focus on UX, not features
- Expert users need different interaction patterns than beginners
- Homelab troubleshooting is ongoing, not one-off - persistent context matters

---

**Document Status**: ✅ Complete
**Next Action**: Get Anthropic API key, then start implementation
**Review Date**: After MVP completion (≈2 weeks)
