# Next Phase Planning - Feature Reorganization

**Date**: 2025-12-09
**Status**: Phase 2 Memory System COMPLETE - Rethinking Phase 3+

## Current Project State

### ✅ Complete
- Phase 0: Foundation (config, PydanticAI agent)
- Phase 1: MVP (OpenAI-compatible API, streaming, boundary detection)
- Phase 2: Memory System (extraction, retrieval, optimization)

### 🎯 Capabilities
- Chat interface via OpenWebUI
- Learns from conversations (extracts memories)
- Retrieves relevant memories (semantic search)
- Optimizes context (dedup, ranking, budgeting)
- Stateless API design
- Model-agnostic (Anthropic + Ollama)

### ❌ Missing
- **No actual homelab tools yet** - Can't query Proxmox, Home Assistant, etc.
- No proactive monitoring or alerting
- No MCP server integration (extensibility framework)
- No multi-provider LLM support (locked to Anthropic or Ollama)

---

## All Planned Features (Phase 3+)

### Category A: Homelab Integration (Original Phase 3)

#### A1. Basic Proxmox Integration
- **What**: Read-only Proxmox VE queries (VM list, status, cluster resources)
- **User Value**: "What VMs are running?", "Show cluster status"
- **Effort**: M (API client, multiple tools, error handling)
- **Dependencies**: None (just config + PydanticAI)

#### A2. Advanced Proxmox Operations
- **What**: Write operations (VM start/stop/restart) with user approval
- **User Value**: "Restart my Plex VM", "Start all media VMs"
- **Effort**: M (approval flow, safety checks, state management)
- **Dependencies**: A1 (Basic Proxmox)

#### A3. Home Assistant Integration
- **What**: Query entities, trigger automations, get state
- **User Value**: "Is garage door open?", "Turn off all lights"
- **Effort**: M (HA API client, entity discovery)
- **Dependencies**: None

#### A4. Docker/Podman Container Management
- **What**: List containers, check logs, restart services
- **User Value**: "Show me failing containers", "Restart nginx"
- **Effort**: M (Docker API client, log streaming)
- **Dependencies**: None

#### A5. Alertmanager/Prometheus Metrics
- **What**: Query current alerts, check metric values
- **User Value**: "Any active alerts?", "Show CPU usage for node1"
- **Effort**: S (simple HTTP queries)
- **Dependencies**: None

---

### Category B: Extensibility & Tooling (Original Phase 3)

#### B1. MCP Server Integration Framework
- **What**: Load MCP servers from config, attach as toolsets
- **User Value**: Add filesystem, GitHub, Brave Search without coding
- **Effort**: M (config parsing, multi-transport, error handling)
- **Dependencies**: None (PydanticAI MCP support exists)

#### B2. Custom MCP Servers (Proxmox, Home Assistant)
- **What**: Build MCP servers for homelab-specific tools
- **User Value**: Reusable across MCP ecosystem, not just HAIA
- **Effort**: L (MCP protocol, server development, packaging)
- **Dependencies**: B1 (MCP framework)

---

### Category C: Proactive Monitoring (Original Phase 4)

#### C1. Background Scheduler (APScheduler)
- **What**: Periodic jobs (check VM status every 5min, Ceph health hourly)
- **User Value**: Get notified before problems escalate
- **Effort**: M (scheduler setup, job definitions)
- **Dependencies**: Homelab tools (A1-A5), Notification (C2)

#### C2. Notification Backends (Telegram, Discord)
- **What**: Send alerts to chat platforms
- **User Value**: Get notified on phone/desktop about issues
- **Effort**: S (simple webhooks/bot APIs)
- **Dependencies**: None

---

### Category D: Infrastructure & Quality (Original Phase 5)

#### D0. Knowledge Graph Enhancement (NEW - From ROADMAP Research Notes)
- **What**: Activate existing graph schema - LLM entity extraction + relationship construction
- **User Value**: "What infrastructure do I own?", "Show dependencies", structured understanding
- **Effort**: L (entity extraction, relationship inference, hybrid retrieval, graph queries)
- **Dependencies**: Memory system (already exists)
- **Key Insight**: Rich Neo4j schema (7 node types, 9 relationships) already exists but unpopulated
- **Current State**: Only flat Memory nodes used, graph structure unused

#### D1. LiteLLM Proxy Integration
- **What**: Multi-provider LLM support (Gemini, Claude, GPT-4) via proxy
- **User Value**: Load balancing, cost tracking, fallback routing
- **Effort**: M (proxy deployment, endpoint switching)
- **Dependencies**: None

#### D2. RAG-based Documentation Search
- **What**: Semantic search over homelab docs (Proxmox guides, runbooks)
- **User Value**: "How do I upgrade Proxmox?", "Show backup procedure"
- **Effort**: L (document ingestion, chunking, RAG pipeline)
- **Dependencies**: Memory system (reuse embeddings infrastructure)

#### D3. Web UI (Alternative to OpenWebUI)
- **What**: Custom web interface with HAIA-specific features
- **User Value**: Tailored UX, memory visualization, job control
- **Effort**: XL (frontend development, API integration)
- **Dependencies**: None

#### D4. Multi-user Support + Authentication
- **What**: User accounts, permissions, isolated memories
- **User Value**: Multiple homelab users with separate contexts
- **Effort**: L (auth system, multi-tenancy in Neo4j)
- **Dependencies**: None

---

## Key Questions for Reorganization

### 1. **Primary Goal**: What should Phase 3 accomplish?
- [ ] Option A: **Prove homelab utility** - Add 1-2 homelab integrations (Proxmox + HA)
- [ ] Option B: **Build extensibility** - MCP framework + 1 example tool
- [ ] Option C: **Complete the loop** - Add proactive monitoring (scheduler + alerts)
- [ ] Option D: **Enhance core** - RAG docs, LiteLLM proxy, better LLM support

### 2. **User Value**: What provides immediate value given current state?
- [ ] Homelab tools (finally make it a "homelab assistant")
- [ ] MCP extensibility (let users add their own tools)
- [ ] Proactive monitoring (autonomous problem detection)
- [ ] Better LLM support (Gemini, load balancing)

### 3. **Momentum**: What builds naturally on Phase 2 (Memory System)?
- [ ] RAG documentation (reuses embedding infrastructure)
- [ ] Memory-aware monitoring (learn from past incidents)
- [ ] Context-aware homelab operations (remember user preferences)

### 4. **Effort vs Impact**: What's the best ROI?
- Quick wins (S effort):
  - [ ] Prometheus/Alertmanager queries
  - [ ] Notification backends
  - [ ] Basic Proxmox read-only

- Medium effort, high impact (M effort):
  - [ ] MCP framework
  - [ ] Home Assistant integration
  - [ ] Background scheduler
  - [ ] LiteLLM proxy

- Large effort, uncertain impact (L-XL effort):
  - [ ] Custom MCP servers
  - [ ] RAG documentation
  - [ ] Web UI
  - [ ] Multi-user auth

### 5. **Dependencies**: What order makes sense?
- Some features are blockers:
  - Homelab tools → Proactive monitoring (can't monitor without tools)
  - MCP framework → Custom MCP servers
  - Notification backends ← Proactive monitoring (alerts need somewhere to go)

---

## Proposed New Phase Structure

### Option 1: "Homelab First" (Prove the Concept)
**Phase 3**: Core Homelab Integration
- Basic Proxmox Integration (read-only)
- Home Assistant Integration
- Prometheus/Alertmanager queries

**Phase 4**: Automation & Monitoring
- Notification backends
- Background scheduler
- Advanced Proxmox operations (with approval)

**Phase 5**: Extensibility & Polish
- MCP framework
- RAG documentation
- LiteLLM proxy

**Rationale**: Get useful homelab functionality ASAP, then add automation, then polish.

---

### Option 2: "Extensibility First" (Platform Play)
**Phase 3**: Extensibility Framework
- MCP Server Integration Framework
- Basic Proxmox via MCP (example)
- Notification backends

**Phase 4**: Community Tools
- Custom MCP servers (Proxmox, HA)
- RAG documentation
- Background scheduler

**Phase 5**: Advanced Features
- Multi-user support
- Web UI
- Advanced monitoring

**Rationale**: Build the platform, let community/users add tools, then scale.

---

### Option 3: "Balanced" (Homelab + Extensibility)
**Phase 3**: Core Value
- Basic Proxmox Integration (custom tools)
- MCP Server Integration Framework (for future)
- Notification backends

**Phase 4**: Autonomous Assistant
- Background scheduler
- Home Assistant integration
- Advanced Proxmox operations

**Phase 5**: Enhancement & Scale
- RAG documentation
- LiteLLM proxy
- Multi-user support

**Rationale**: Get immediate homelab value, prove MCP works, then add autonomy.

---

### Option 4: "Memory-Driven" (Build on Phase 2)
**Phase 3**: Memory-Enhanced Features
- RAG documentation search (reuse embeddings)
- Context-aware homelab tools (Proxmox + memory)
- LiteLLM proxy (better LLMs for extraction/retrieval)

**Phase 4**: Autonomous Learning
- Background scheduler with memory
- Incident learning (extract from monitoring)
- Proactive suggestions based on patterns

**Phase 5**: Full Intelligence
- Multi-user with shared/private memories
- Custom MCP servers
- Web UI with memory visualization

**Rationale**: Leverage the memory system that's already built, make HAIA smarter before broader.

---

### Option 5: "Knowledge Graph First" (Activate the Schema)
**Phase 3**: Structured Knowledge Graph
- LLM-based entity extraction (Person, Infrastructure, TechPreference, Interest nodes)
- Automatic relationship construction (OWNS, PREFERS, INTERESTED_IN, etc.)
- Hybrid retrieval (vector search + graph traversal combined)
- Entity resolution and deduplication across graph
- Graph-aware memory visualization

**Phase 4**: Intelligent Context
- RAG documentation with graph integration
- Memory analytics and insights ("What infrastructure do I own?")
- LiteLLM proxy (better LLMs for entity extraction)
- Context-aware suggestions based on graph patterns

**Phase 5**: External Integration
- Homelab tools that populate graph (Proxmox → Infrastructure nodes)
- MCP framework with graph integration
- Proactive monitoring with graph-based anomaly detection
- Multi-user with graph isolation

**Rationale**:
- **Zero new infrastructure** - Neo4j graph schema already exists, just needs population
- **Doubles down on strength** - Memory system is HAIA's differentiator, make it exceptional
- **Foundation for everything** - Rich graph enables smarter homelab tools, monitoring, RAG docs
- **Unique value** - No other homelab assistant has structured knowledge graph of user + infrastructure
- **Natural evolution** - Current flat memories → structured graph → intelligent graph queries

**Key Insight**:
Right now HAIA has a rich graph schema (7 node types, 9 relationship types) that's **completely unused**. Sessions 7-9 only populate flat Memory nodes. Activating the graph turns HAIA from "remembers facts" to "understands relationships between you, your infrastructure, and your preferences."

**Example Queries Enabled**:
- "What infrastructure do I own?" → traverse Person -OWNS-> Infrastructure
- "Show me all decisions about Docker" → traverse Decision -RELATED_TO-> TechPreference
- "What services depend on my NAS?" → traverse Infrastructure -DEPENDS_ON-> Infrastructure
- "What technologies do I prefer for monitoring?" → traverse Person -PREFERS-> TechPreference

**vs Current State** (flat vector search):
- "What infrastructure do I own?" → vector search for "infrastructure" in memory content (may miss things)
- No relationship queries possible
- No graph traversal
- No structured understanding

---

## Decision Template

Fill this out to guide reorganization:

**What is HAIA's primary value proposition right now?**
- [ ] Chat interface for homelab (needs tools)
- [ ] Intelligent assistant that learns (memory complete)
- [ ] Extensible platform (needs MCP)

**Who is the target user for Phase 3?**
- [ ] Me (vlb) - personal homelab assistant
- [ ] Homelab enthusiasts - general tool
- [ ] Developers - extensible platform

**What's the "wow" moment we want to deliver next?**
- [ ] "HAIA knows my Proxmox cluster is unhealthy"
- [ ] "I taught HAIA a new skill via MCP"
- [ ] "HAIA warned me before the disk filled up"
- [ ] "HAIA answered my question using my runbook docs"
- [ ] "HAIA understands the relationships between my infrastructure" (graph queries)

**What's blocking the most value?**
- [ ] No homelab integrations (can't actually help with homelab)
- [ ] No extensibility (locked to what we code)
- [ ] No autonomy (requires user to ask questions)
- [ ] LLM limitations (Haiku not smart enough)
- [ ] Unused graph schema (rich structure exists but unpopulated)

---

## Next Steps

1. **Review this document** and answer the key questions
2. **Choose a phase structure** (Option 1-5 or hybrid)
3. **Prioritize features** within chosen structure
4. **Update ROADMAP.md** with new Phase 3+ organization
5. **Create Session 10 spec** for first feature in new Phase 3

---

## Option Comparison Matrix

| Aspect | Option 1: Homelab First | Option 2: Extensibility | Option 3: Balanced | Option 4: Memory-Driven | Option 5: Knowledge Graph |
|--------|------------------------|------------------------|-------------------|------------------------|--------------------------|
| **Quick Win** | ✅ Proxmox queries | ❌ MCP framework complex | ✅ Proxmox + MCP | ⚠️ RAG docs (medium) | ⚠️ Entity extraction (large) |
| **New Dependencies** | Proxmoxer lib | MCP servers | Both | LiteLLM, docs | None (Neo4j exists) |
| **Builds on Phase 2** | ❌ New direction | ❌ New direction | ⚠️ Partial | ✅ Enhances memory | ✅✅ Activates existing schema |
| **Differentiator** | ⚠️ Generic homelab | ✅ Extensibility | ⚠️ Both but shallow | ✅ Smart memory | ✅✅ Structured knowledge graph |
| **User Value** | Immediate practical | Future flexibility | Compromise | Smarter assistant | Relationship understanding |
| **Phase 3 Effort** | M (3-4 features) | M-L (framework + example) | M (2-3 features) | L (RAG + tools) | L (entity extraction) |
| **Risk** | Diverges from memory | Complex framework | Scattered focus | Too much at once | Extraction quality |
| **Foundation Quality** | ⚠️ Rushed tools | ✅ Solid platform | ⚠️ Both half-done | ✅ Enhanced core | ✅✅ Completes vision |

**Key Observations**:
- **Option 5** is the only one that requires **zero new infrastructure** (Neo4j + schema already exist)
- **Option 5** is the only one that **completes the memory system vision** from original design
- **Options 1-3** diverge from memory work (Phase 2) to add external integrations
- **Option 4** tries to do too much at once (RAG + tools + LLM proxy)
- **Option 5** → enables smarter Phase 4 (homelab tools can populate graph, monitoring uses relationships)

**Recommendation Shift**:
After adding Option 5, I now lean toward **Option 5: "Knowledge Graph First"** because:

1. **Completes the architecture** - Original design had rich graph schema, Sessions 7-9 only used 10% of it
2. **Zero new dependencies** - Everything needed already exists in codebase
3. **Differentiates HAIA** - No other homelab assistant has structured knowledge graph
4. **Enables smarter Phase 4** - Homelab tools become graph-aware (Proxmox → Infrastructure nodes)
5. **Natural evolution** - Phase 2 built memory system, Phase 3 makes it understand structure
6. **Better foundation** - Rich graph → better homelab integration later vs rushed tools → retrofit graph later

**Counterargument**:
Option 5 delays tangible homelab value (no Proxmox/HA queries yet). But consider: would you rather have working but dumb homelab queries now, or wait slightly longer for homelab queries that understand your infrastructure relationships?

