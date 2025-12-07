# Brainstorming Session: HAIA Personal Memory System

**Date**: 2025-12-06
**Participants**: Vincent (Product Owner), Claude Code (Scrum Master/Facilitator)
**Duration**: ~2 hours (Progressive questioning session)
**Session Type**: Feature Discovery & Architecture Design

---

## 1. Executive Summary

### Feature Overview
Transform HAIA from a homelab-focused technical assistant into a **personal AI companion** who progressively learns about Vincent across all life domains (personal, family, technical, homelab) and uses this knowledge to provide contextually-aware, personalized assistance.

### Key Decisions

1. **Vision Pivot**: HAIA is a general-purpose personal companion who happens to be an expert in Vincent's homelab, not a homelab specialist who reluctantly answers other questions
2. **Architecture**: Single PydanticAI agent (no delegation needed) with progressive memory system
3. **Memory Storage**: Neo4j graph database with vector search (hybrid approach for comprehensive + actionable memory)
4. **Extraction Strategy**: Selective Aggressive - extract everything ≥0.4 confidence, promote to structured nodes at ≥0.8
5. **Extraction Timing**: Post-conversation batch processing (cost-efficient) with hybrid heuristic detection
6. **Confirmation Strategy**: 70% auto-store, 20% inline contextual, 10% explicit confirmation (industry-standard tiered approach)
7. **Retrieval Strategy**: Three-tier system (critical/semantic/deep) with confidence filtering ≥0.6
8. **Two-Phase Deployment**: Phase 1 - Quick system prompt fix (remove "homelab specialty" framing), Phase 2 - Full memory system integration

### Strategic Goals
- ✅ HAIA knows Vincent personally (family, interests, preferences, goals)
- ✅ HAIA understands Vincent's homelab infrastructure deeply (dependencies, criticality, preferences)
- ✅ Memory grows organically through conversations (progressive learning)
- ✅ Context-aware responses (distinguishes personal vs technical relevance)
- ✅ Industry-standard architecture (graph + vectors) for sophisticated AI companion

---

## 2. Problem Statement & Context

### The Problem

**Current State - Problematic Behavior:**
```
User: "What's a good whisky for a beginner?"
HAIA: "While this isn't homelab-related, here's some advice on whisky..."
```
This makes Vincent feel like he's bothering HAIA with off-topic questions.

**Root Cause:**
- System prompt frames homelab as "specialty" and "area of deep expertise"
- `vincent_profile.yaml` contains 100% homelab infrastructure, 0% personal context
- Most prompt examples are technical/homelab-focused
- Model infers: homelab = main job, everything else = secondary

**Desired State:**
```
User: "What's a good whisky for a beginner?"
HAIA: "For beginners, I'd recommend starting with Irish whiskeys like Jameson or Tullamore Dew..."

User: "Should I upgrade prox0?"
HAIA: "Prox0 hosts zigbee2mqtt which is critical for your entire home automation.
       You mentioned preferring to test upgrades on prox2 first. Want to try
       the upgrade there to validate before touching prox0?"
```

### Target Vision

**HAIA as Personal Companion:**
- Sophisticated, capable, professional with subtle dry wit (female Jarvis)
- Versatile across all domains: philosophy, coding, homelab, family advice, general knowledge
- Progressively learns about Vincent: family, interests, preferences, goals, infrastructure
- Context-aware: understands when family context is relevant vs homelab dependency chains
- Memory-powered: "You mentioned exploring whisky 2 weeks ago - how's that going?"

### Success Metrics

**Immediate (Phase 1 - System Prompt Fix):**
- HAIA stops apologizing for non-homelab questions
- Natural conversation flow across all topics
- Maintains homelab expertise without framing it as "specialty"

**Long-term (Phase 2 - Memory System):**
- HAIA remembers personal facts (family, interests, preferences)
- HAIA recalls technical context (infrastructure, decisions, preferences)
- HAIA distinguishes relevance (doesn't mention son during Ceph troubleshooting)
- HAIA grows smarter over time (memory accumulation measurable)
- Conversation quality improves with tenure (personalization increases)

---

## 3. Brainstorming Results

### 3.1 Core Insights & Key Moments

#### Discovery 1: It's Not About Delegation, It's About Personality

**Initial Question:** "Should HAIA delegate to a specialized homelab agent?"

**Breakthrough:** No architectural changes needed. The problem is:
- System prompt wording ("Homelab Specialty")
- Missing personal context layer
- No memory of preferences/relationships

**Decision:** Fix prompt + add progressive memory system. Single agent is correct.

---

#### Discovery 2: Progressive Learning Over Upfront Configuration

**Question:** "How much personal information should HAIA know upfront?"

**Vincent's Vision:** "HAIA should learn about me organically through conversations, categorizing and storing relevant information to build comprehensive knowledge over time."

**Key Insight:** This requires a **memory system**, not just better prompts. Need to:
1. Identify memorable facts during conversations
2. Categorize (personal/technical/preference/etc.)
3. Store persistently in retrievable format
4. Inject relevant memories into future conversations
5. Grow understanding progressively

---

#### Discovery 3: Conversation Boundaries Are Fuzzy

**Challenge:** Backend is stateless (OpenWebUI doesn't send conversation IDs)

**Solution:** Hybrid heuristic detection:
```python
Trigger memory extraction when:
1. >10min since last request AND
2. Message history changed significantly (message count dropped >50% or different first message)
```

**Pragmatic Decision:** Accept "good enough" conversation boundaries rather than breaking OpenAI compatibility.

---

#### Discovery 4: Comprehensive Memory Requires Graph + Vectors

**Question:** "What technology for memory storage?"

**Industry Analysis:**
- **Vector DB alone** (ChromaDB): Good semantic search, no relationships (6/10 power, 5/10 vision alignment)
- **Graph DB alone** (Neo4j): Great relationships, weak fuzzy matching (8/10 power, 7/10 vision alignment)
- **Hybrid Graph+Vector** (Neo4j 5.x with vector search): Best of both worlds (9.5/10 power, 9.5/10 vision alignment)

**Decision:** Neo4j with native vector search
- Models explicit relationships (family, infrastructure dependencies, preferences)
- Semantic search for fuzzy matching
- Context-aware queries combining structure + semantics
- Industry standard for sophisticated AI companions

**Example Use Case:**
```cypher
// Query: "Help me plan this weekend"
// Combines:
- Family commitments (graph: Vincent -> father_of -> Son -> soccer Saturdays)
- Recent interests (vector: whisky exploration)
- Homelab maintenance (graph: Nextcloud backup overdue)

// Result: "Your son has soccer Saturday morning. You mentioned exploring
//          whisky recently. Nextcloud backup has been pending for 3 weeks
//          (you usually do this monthly). Want to tackle that Sunday?"
```

---

#### Discovery 5: Industry-Standard Confirmation Patterns

**Research Finding:** Leading AI memory systems use tiered confirmation:
- ChatGPT: Aggressive extraction, user reviews afterward
- Google Assistant: Selective confirmation for high-impact facts
- Notion AI: Contextual suggestions during conversation
- Mem.ai: Store everything, surface intelligently

**Decision:** Hybrid tiered approach:
- **70% auto-store** - Low-impact facts, high confidence (silent)
- **20% inline contextual** - Medium impact (confirm naturally in conversation)
- **10% explicit confirmation** - High impact or contradictions (ask directly)

**Example - Inline Contextual:**
```
User: "My son plays soccer on Saturdays"
HAIA: "That's great! Soccer is wonderful at that age. I'll remember
       his Saturday schedule so I don't suggest conflicting plans.

       Regarding your homelab question..."
```

---

### 3.2 Memory Architecture Design

#### Node Types (Comprehensive Categories)

**Personal Domain:**
- `Person` - Vincent, family members (relationship, age, embedding)
- `Interest` - Hobbies, topics of interest (category, proficiency level, active status)
- `LifeGoal` - Personal/professional goals (domain, status, priority)
- `Event` - Recurring or one-time events (schedule, importance)

**Technical Domain:**
- `Infrastructure` - VMs, LXCs, nodes, services (type, host, criticality)
- `TechPreference` - Tool/technology choices (domain, preference, context, rationale)
- `WorkingStyle` - Approaches to tasks (debugging, planning, learning)

**Knowledge Domain:**
- `Fact` - Structured facts (content, category, confidence, source)
- `Conversation` - Past conversations (summary, timestamp, topic embedding)
- `Decision` - Important decisions (question, choice, reasoning, outcome)

#### Relationship Types (Making it Actionable)

**Personal:**
- `(Vincent)-[:FATHER_OF]->(Son)`
- `(Vincent)-[:INTERESTED_IN {level, since}]->(Interest)`
- `(Person)-[:PARTICIPATES_IN]->(Event)`

**Technical:**
- `(Service)-[:RUNS_ON]->(Infrastructure)`
- `(Service)-[:REQUIRES]->(Service)`
- `(Service)-[:DEPENDS_ON {criticality}]->(Infrastructure)`
- `(Vincent)-[:PREFERS {context, strength}]->(TechPreference)`

**Knowledge:**
- `(Fact)-[:ABOUT]->(Person|Infrastructure|Interest)`
- `(Fact)-[:CONTRADICTS]->(Fact)` - Track corrections
- `(Decision)-[:AFFECTS]->(Infrastructure|LifeGoal)`
- `(Conversation)-[:DISCUSSED]->(Interest|Infrastructure|Person)`

#### Extraction Rules (Selective Aggressive)

**Confidence Thresholds:**
```python
EXPLICIT = 1.0      # "I prefer X", "My son is Y"
STRONG = 0.8        # Pattern across 2+ mentions
MODERATE = 0.6      # Single clear mention
WEAK = 0.4          # Inference or ambiguous
SPECULATIVE = 0.2   # Tentative ("maybe", "might")
```

**What to Extract:**
1. **Preferences** - Explicit statements ("I prefer LXC over Docker for...")
2. **Personal Facts** - Family, relationships, interests
3. **Technical Context** - Infrastructure criticality, dependencies
4. **Decisions** - Important choices and their reasoning
5. **Corrections** - When user updates previous information
6. **Relationships** - Dependencies, requirements, affects

**Storage Strategy:**
- Everything ≥0.4 confidence gets stored (comprehensive)
- Low confidence (<0.6) stored as unstructured `Fact` nodes
- High confidence (≥0.8) promoted to structured typed nodes (`TechPreference`, `Interest`, etc.)
- Confidence scores track over time (multiple mentions strengthen)

#### Retrieval Strategy (Three-Tier System)

**Tier 1: Critical Context** (Always loaded, <100ms)
```cypher
// Load explicit mentions
MATCH (entity) WHERE entity.name IN query_entities
RETURN entity

// Examples:
- "prox0" mentioned → Load Infrastructure node
- "son" mentioned → Load Person node + relationships
```

**Tier 2: Semantic Relevance** (Smart loading, <200ms)
```cypher
// Vector search for related concepts
MATCH (memory)
WHERE memory.embedding <-> query_embedding < 0.3
RETURN memory

// Graph traversal from Tier 1 nodes
MATCH (tier1_node)-[*1..2]-(related)
RETURN related

// Examples:
- Query about "containers" → Finds LXC preference memory
- Query about prox0 → Traverses to zigbee2mqtt dependency
```

**Tier 3: Deep Context** (On-demand, <500ms)
```cypher
// Only when query indicates need ("remember when...", "tell me about...")
// Full conversation history search
// Extended graph traversal (3+ hops)
```

**Filtering:**
- Minimum confidence: 0.6 for retrieval (don't surface weak memories)
- Boost recent memories (temporal decay)
- Boost user-confirmed memories (explicit approval)

#### Context Injection Format (Hybrid Structured + Natural)

**Rationale:** Industry research shows LLMs perform best with structured markdown + natural language descriptions.

**Format:**
```markdown
## Vincent's Context (Retrieved Memories)

### Personal
- **Family**: Father of son who plays soccer Saturday mornings
- **Current Interests**: Exploring whisky (beginner level, started 2 weeks ago), photography
- **Schedule Note**: Weekends often include family activities

### Technical Preferences
- **Containers**: Prefers LXC for single-service deployments, Docker Compose for multi-container stacks
- **Distributions**: Primary choice is Debian/Ubuntu for stability
- **Working Style**: Likes to test changes on prox2 before applying to critical nodes (mentioned 3x, high confidence)

### Infrastructure Context
**Critical Services** (requires extra caution):
- `prox0`: Hosts zigbee2mqtt (LXC 100) - entire home automation depends on this
- `Nextcloud` (VM 111 on prox2): Contains irreplaceable personal data

**Important Services**:
- `Home Assistant` (VM 101): Central automation hub, requires zigbee2mqtt
- Media stack (VM 102): *arr suite, important but non-critical

### Recent Conversations
- 2 days ago: Discussed whisky recommendations (identified interest)
- 1 week ago: Mentioned concern about Nextcloud backup strategy
```

---

### 3.3 Implementation Phases

#### Phase 1: System Prompt Fix (Immediate - This Week)

**Objective:** Stop apologizing for non-homelab questions

**Changes:**
1. Update `.env` HAIA_SYSTEM_PROMPT:
   - Remove "Homelab Specialty (your area of deep expertise)" framing
   - Reposition homelab as ONE capability among many
   - Add diverse examples (philosophy, whisky, family advice)
   - Emphasize versatility and companionship

2. Test conversational flow:
   - Ask general questions (whisky, philosophy, family)
   - Verify no "this isn't homelab-related" disclaimers
   - Ensure homelab expertise remains intact

**Effort:** 1-2 hours
**Impact:** Immediate UX improvement

---

#### Phase 2: Memory System (Next Feature - 2-3 Weeks)

**Components:**

**2.1 Infrastructure Setup**
- Deploy Neo4j 5.x container with vector search enabled
- Configure plugins (APOC, Graph Data Science)
- Set up persistence and backup strategy
- Estimated: 1-2 days

**2.2 Memory Extraction Service**
```python
# src/haia/memory/extractor.py
class MemoryExtractor:
    async def analyze_conversation(self, messages: List[Message]) -> List[Memory]:
        """Extract memories from conversation transcript"""

    async def categorize_memory(self, content: str) -> MemoryCategory:
        """Classify memory type and confidence"""

    async def determine_confirmation_needed(self, memory: Memory) -> ConfirmationTier:
        """Apply decision matrix for confirmation strategy"""
```
- Estimated: 3-4 days

**2.3 Conversation Boundary Detection**
```python
# src/haia/memory/boundaries.py
class ConversationBoundaryDetector:
    async def should_extract_memories(self) -> bool:
        """Hybrid heuristic: 10min idle + message history change"""

    async def track_request_metadata(self, request: ChatRequest):
        """Track timestamps and message counts"""
```
- Estimated: 1-2 days

**2.4 Neo4j Storage Layer**
```python
# src/haia/memory/storage.py
class MemoryGraph:
    async def store_memory(self, memory: Memory):
        """Create nodes and relationships in Neo4j"""

    async def generate_embedding(self, content: str) -> Vector:
        """Generate embeddings for semantic search"""

    async def retrieve_relevant_memories(self, query: str) -> List[Memory]:
        """Three-tier retrieval strategy"""
```
- Estimated: 4-5 days

**2.5 Context Injection**
```python
# src/haia/memory/context.py
class MemoryContextBuilder:
    async def build_context(self, query: str) -> str:
        """Format memories as markdown for agent context"""

    async def apply_tiered_retrieval(self, query: str) -> TieredMemories:
        """Execute tier 1, 2, 3 retrieval"""
```
- Estimated: 2-3 days

**2.6 Confirmation UX**
```python
# src/haia/memory/confirmation.py
class ConfirmationManager:
    async def inline_contextual_confirm(self, memory: Memory) -> str:
        """Embed confirmation in conversation naturally"""

    async def batch_summary_review(self, memories: List[Memory]) -> str:
        """End-of-conversation summary for review"""
```
- Estimated: 2-3 days

**2.7 Memory Management Commands**
```python
# Slash commands for user control
/memory review          # View all memories by category
/memory search [query]  # Semantic search across memories
/memory forget [topic]  # Delete category of memories
/memory export          # Download as JSON
/memory stats           # Show graph statistics
```
- Estimated: 2-3 days

**Total Estimated Effort:** 16-21 days (3-4 weeks calendar time)

**Note:** Session 3 expanded to include Docker Compose stack setup (+1 day) for production-ready containerized deployment.

---

## 4. Decisions & Rationale

### Decision 1: Single Agent Architecture (No Delegation)
**Options Considered:**
- A) HAIA delegates to specialized homelab agent
- B) Single agent with memory system

**Decision:** B - Single agent
**Rationale:**
- Problem is prompt framing and missing memory, not architecture
- Delegation adds complexity without solving core issue
- PydanticAI agent can handle multiple domains elegantly
- Memory system provides context switching naturally

---

### Decision 2: Neo4j with Vector Search (Hybrid Graph+Vector)
**Options Considered:**
- A) Pure vector database (ChromaDB) - 6/10 power, 5/10 vision alignment
- B) Pure graph database (Neo4j) - 8/10 power, 7/10 vision alignment
- C) Hybrid (Neo4j with vector search) - 9.5/10 power, 9.5/10 vision alignment
- D) SQL + pgvector - 6.5/10 power, 6/10 vision alignment
- E) Separate Neo4j + ChromaDB - 10/10 power, 9/10 vision alignment (complexity overhead)

**Decision:** C - Neo4j 5.x with native vector search
**Rationale:**
- Relationships matter for personal companion (family, infrastructure dependencies)
- Semantic search needed for fuzzy matching (interests, preferences)
- Industry standard for sophisticated AI agents (Google Assistant, enterprise AI)
- Single system simpler than separate graph + vector (95% power, 50% complexity)
- Can always split later if needed

---

### Decision 3: Post-Conversation Batch Processing
**Options Considered:**
- A) Real-time extraction during conversation (higher cost, immediate learning)
- B) Post-conversation batch processing (cost-efficient, delayed learning)
- C) Hybrid (critical facts real-time, detailed analysis background)

**Decision:** B - Post-conversation batch processing
**Rationale:**
- Vincent specified cost-consciousness
- Batch processing still feels responsive (extracts within minutes of conversation end)
- Can add manual "remember" triggers for immediate needs
- Industry trend: most systems extract asynchronously (ChatGPT, Notion AI)

---

### Decision 4: Tiered Confirmation Strategy (70/20/10)
**Options Considered:**
- A) Always confirm (safe but annoying)
- B) Never confirm (seamless but risky)
- C) Tiered approach (70% auto, 20% inline, 10% explicit)

**Decision:** C - Industry-standard tiered approach
**Rationale:**
- **70% auto-store:** Low-risk facts (interests, general preferences) - silent
- **20% inline contextual:** Medium impact (family facts, important preferences) - confirm naturally in conversation flow
- **10% explicit:** High impact (contradictions, critical infrastructure changes) - ask directly
- Matches industry leaders (Google Assistant, Notion AI, ChatGPT)
- Balances convenience with control

---

### Decision 5: Selective Aggressive Extraction (Option C)
**Options Considered:**
- A) Conservative (high confidence only)
- B) Aggressive (extract everything, track confidence)
- C) Selective aggressive (extract broadly ≥0.4, structure tightly ≥0.8)

**Decision:** C - Selective aggressive
**Rationale:**
- Extract comprehensively (≥0.4 confidence) to avoid missing information
- Store low-confidence as unstructured `Fact` nodes
- Promote to structured types when confidence increases (≥0.8)
- Retrieve only ≥0.6 confidence (filter out noise)
- Industry consensus: over-collection better than missing info (users can review/delete)

---

### Decision 6: Two-Phase Deployment
**Options Considered:**
- A) Quick prompt fix only
- B) Bundle prompt fix with memory system
- C) Two-phase: prompt fix now, memory system later

**Decision:** C - Two-phase approach
**Rationale:**
- **Phase 1 (immediate):** Fix system prompt - stops apologizing behavior this week
- **Phase 2 (3-4 weeks):** Full memory system - comprehensive solution
- Get quick wins while building toward vision
- Validate prompt improvements before investing in memory system
- De-risks: if prompt fix alone solves 80% of problem, can adjust memory scope

---

## 5. Risks & Mitigation

### Risk 1: Conversation Boundary Detection Inaccuracy
**Risk:** Hybrid heuristic (10min + history change) might extract at wrong times
**Impact:** Medium - Could miss conversations or extract mid-session
**Probability:** Medium - Stateless API limits detection accuracy
**Mitigation:**
- Add manual "/remember" trigger for explicit memory capture
- Monitor extraction logs for patterns
- Adjust heuristics based on real usage (tune timeout, message count thresholds)
- Future: If OpenWebUI adds conversation ID header, upgrade detection logic

### Risk 2: Memory Extraction Quality
**Risk:** LLM might misinterpret statements or extract irrelevant facts
**Impact:** High - Poor memory quality reduces trust in HAIA
**Probability:** Medium - LLMs can hallucinate or misunderstand context
**Mitigation:**
- Confidence scoring on all memories (filter low-confidence from retrieval)
- User review interface (/memory review) to audit and correct
- Contradiction detection (flag when new fact conflicts with existing)
- Conservative promotion to structured nodes (require ≥0.8 confidence)
- Iterate extraction prompts based on observed quality

### Risk 3: Neo4j Operational Complexity
**Risk:** Graph database adds infrastructure complexity (backup, monitoring, scaling)
**Impact:** Medium - Could slow development or cause operational issues
**Probability:** Low-Medium - Neo4j is mature but requires learning
**Mitigation:**
- Use Docker Compose for local deployment (simple setup)
- Implement automated backups to NAS
- Start with single instance (no clustering needed for single user)
- Monitor memory graph size (alert if > 10k nodes, may need optimization)
- Document operational procedures (backup, restore, query optimization)

### Risk 4: Context Injection Overhead
**Risk:** Loading memories on every request could slow responses
**Impact:** Medium - User experience degradation if responses lag
**Probability:** Low - Tier 1/2 retrieval should be fast (<200ms)
**Mitigation:**
- Implement timeout guards (fail gracefully if retrieval > 500ms)
- Cache frequently accessed memories (Vincent's core preferences)
- Monitor retrieval latency (P95, P99 percentiles)
- Start with tier 1+2 only, add tier 3 if needed
- Fall back to no-memory response if retrieval fails

### Risk 5: Privacy and Data Sensitivity
**Risk:** Storing personal information (family, preferences) in database
**Impact:** High - Personal data security is critical
**Probability:** Low - Single user homelab environment (controlled access)
**Mitigation:**
- Neo4j authentication enabled (strong password)
- Database not exposed to external network
- Regular encrypted backups to separate location
- Document data retention policy (user can delete memories)
- Consider encryption at rest for sensitive categories (future enhancement)

### Risk 6: Scope Creep During Development
**Risk:** Memory system is complex, could expand beyond 3-4 weeks
**Impact:** Medium - Delays shipping value to user
**Probability:** Medium - Feature is ambitious for single developer
**Mitigation:**
- Strict MVP scope: Core extraction, storage, retrieval only
- Defer nice-to-have features (advanced confirmation UI, memory analytics)
- Use existing embedding API (OpenAI or Anthropic) - don't self-host initially
- Time-box each component (if > estimate, reassess scope)
- Ship iteratively: basic extraction → storage → retrieval → confirmation UX

---

## 6. Specification Session Breakdown

### How to Use This Section

The memory system is large. Break it into **6 independent specification sessions**, each deliverable in 3-5 days:

**Process for each session:**
1. Use `/speckit.specify` with the provided description
2. Review and refine the generated spec
3. Use `/speckit.plan` to create implementation plan
4. Use `/speckit.tasks` to generate actionable tasks
5. Implement, test, and ship that component
6. Move to next session

---

### Session 1: System Prompt Personality Fix (IMMEDIATE)

**Goal:** Stop apologizing for non-homelab questions

**Input for `/speckit.specify`:**
```
System Prompt Redesign - Update HAIA's system prompt to position her as a versatile
personal companion while MAINTAINING her deep homelab expertise. Remove "Homelab Specialty
(your area of deep expertise)" framing that makes her apologize for non-homelab questions.
Reposition homelab as ONE capability among many (general conversation, technical expertise,
homelab infrastructure). Keep ALL existing homelab knowledge, critical service warnings
(zigbee2mqtt, Home Assistant, Nextcloud, prox0), and technical depth. Add diverse conversation
examples (philosophy, whisky, family advice, general knowledge) to demonstrate versatility.
Maintain existing personality (sophisticated, dry wit, professional). Test that she responds
naturally to ALL topics without apologetic disclaimers while PRESERVING expert-level homelab
responses with same technical depth as before.
```

**Success Criteria:**
- HAIA answers whisky questions naturally (no "not homelab-related")
- **Homelab responses remain expert-level** (same technical depth as before)
- **Critical service awareness unchanged** (still warns about zigbee2mqtt, prox0, etc.)
- Smooth topic transitions
- **No regression in homelab expertise** (validate with technical questions)

**Dependencies:** None (can ship immediately)

**Estimated Effort:** 1-2 days

---

### Session 2: Conversation Boundary Detection

**Goal:** Detect when conversations end to trigger memory extraction

**Input for `/speckit.specify`:**
```
Conversation Boundary Detection - Implement hybrid heuristic to detect conversation
endings in stateless OpenAI-compatible API. Track request timestamps and message
history metadata. Trigger extraction when >10min idle AND message history changed
significantly (message count dropped >50% OR first message hash differs). Store
transcript for extraction. No actual memory extraction yet - just boundary detection
and transcript capture.
```

**Success Criteria:**
- Correctly detects conversation endings in 90% of cases
- Captures full conversation transcripts
- Logs trigger events for debugging

**Dependencies:** None (independent of memory storage)

**Estimated Effort:** 2-3 days

---

### Session 3: Docker Compose Stack & Neo4j Infrastructure

**Goal:** Production-ready containerized deployment + Neo4j setup

**Input for `/speckit.specify`:**
```
Docker Compose Stack & Neo4j Setup - Create production Docker Compose stack with two
services: HAIA (FastAPI app) and Neo4j (graph database with vector search). HAIA service
builds from Dockerfile (Python 3.11, installs dependencies via uv, runs uvicorn). Neo4j
service uses official neo4j:5.15 image with APOC and Graph Data Science plugins enabled.
Services connected via Docker network. Environment variables via .env file (ANTHROPIC_API_KEY,
NEO4J_PASSWORD, etc.). Volume mounts for Neo4j data persistence, HAIA logs, and config files.
Healthchecks for both services. Define graph schema for memory system (Person, Interest,
Infrastructure, TechPreference, Fact, Decision, Conversation nodes + relationships). Implement
basic Python CRUD operations for Neo4j using neo4j Python driver. Include backup strategy
(daily Neo4j dumps to backup volume). Support both containerized deployment (docker-compose up)
and local development (HAIA native + Neo4j container). Create docker-install.sh script for
one-command deployment.
```

**Success Criteria:**
- `docker-compose up` starts both services successfully
- HAIA accessible on http://localhost:8000
- Neo4j web UI accessible on http://localhost:7474
- Services communicate via Docker network
- Persistence works across container restarts
- Can run HAIA locally for development (connects to containerized Neo4j)
- Backup script creates daily Neo4j dumps
- Health checks report service status correctly

**Dependencies:** None (can develop in parallel)

**Estimated Effort:** 4-5 days (includes Docker Compose setup + Neo4j schema)

---

### Session 4: Memory Extraction Engine

**Goal:** Analyze conversations and extract structured memories

**Input for `/speckit.specify`:**
```
Memory Extraction Engine - Use PydanticAI to analyze conversation transcripts and
extract memories with confidence scoring. Implement extraction rules for: preferences
(explicit statements), personal facts (family, interests), technical context
(infrastructure, dependencies), decisions, corrections. Output structured memories
with type, content, confidence (0.0-1.0), category. Apply selective aggressive
strategy (≥0.4 confidence). Implement confidence calculation algorithm based on
explicit vs inferred, multiple mentions, contradictions. Return extraction results
as JSON for storage by separate component.
```

**Success Criteria:**
- Extracts 10+ memory types from test conversations
- Confidence scoring accurate (manual validation)
- Categorizes memories correctly (≥85% accuracy)
- Extraction completes in <10 seconds for 20-message conversation

**Dependencies:** Session 2 (needs transcripts)

**Estimated Effort:** 4-5 days

---

### Session 5: Memory Storage & Confirmation

**Goal:** Store memories in Neo4j with tiered confirmation UX

**Input for `/speckit.specify`:**
```
Memory Storage & Confirmation - Store extracted memories in Neo4j graph database.
Generate embeddings via OpenAI Embeddings API. Implement tiered confirmation strategy:
70% auto-store (silent), 20% inline contextual (embed in conversation), 10% explicit
(ask directly). Decision matrix based on confidence + impact + contradiction. Create
confirmation response templates. Store confirmed memories with metadata (timestamp,
confidence, source). Implement contradiction detection (CONTRADICTS relationship).
Support manual "/remember" trigger for immediate storage.
```

**Success Criteria:**
- Memories stored correctly in Neo4j
- Confirmation tiers applied accurately
- User accepts ≥80% of inline confirmations
- Manual trigger works instantly

**Dependencies:** Session 3 (Neo4j schema), Session 4 (extraction)

**Estimated Effort:** 4-5 days

---

### Session 6: Memory Retrieval & Context Injection

**Goal:** Retrieve relevant memories and inject into agent context

**Input for `/speckit.specify`:**
```
Memory Retrieval & Context Injection - Implement three-tier retrieval strategy for
loading relevant memories. Tier 1: Critical context (entity mentions, always load,
<100ms). Tier 2: Semantic relevance (vector search top 10 + graph traversal 1-2 hops,
<200ms). Tier 3: Deep context (on-demand for "remember when" queries, <500ms). Filter
retrieval by confidence ≥0.6. Format memories as hybrid structured markdown for agent
context injection (Personal, Technical Preferences, Infrastructure Context, Recent
Conversations sections). Inject into PydanticAI agent's system prompt before each request.
```

**Success Criteria:**
- Retrieval P95 latency <200ms (tier 1+2)
- Relevant memories injected (manual validation)
- Agent uses memories in responses naturally
- Irrelevant memories filtered out (≥90% precision)

**Dependencies:** Session 5 (stored memories in Neo4j)

**Estimated Effort:** 4-5 days

---

### Session 7: Memory Management Interface (OPTIONAL - NICE TO HAVE)

**Goal:** User commands to view, search, and manage memories

**Input for `/speckit.specify`:**
```
Memory Management Commands - Implement slash commands for memory control: /memory review
(view all by category), /memory search [query] (semantic search), /memory forget [topic]
(delete category), /memory export (download JSON), /memory stats (graph statistics).
Format output as readable summaries with edit/delete options. Support category filtering,
date ranges, confidence thresholds. Provide visualization suggestions for graph structure.
```

**Success Criteria:**
- All commands work as specified
- User can audit and correct memories
- Export format is human-readable
- Memory deletion is immediate and permanent

**Dependencies:** Session 6 (full memory system working)

**Estimated Effort:** 2-3 days

---

### Dependency Graph

```
Session 1 (Prompt Fix)
   ↓ [can ship immediately]

Session 2 (Boundaries) ──┐
Session 3 (Neo4j)      ──┤
                         ├──→ Session 4 (Extraction)
                         │         ↓
                         └────→ Session 5 (Storage)
                                    ↓
                              Session 6 (Retrieval)
                                    ↓
                              Session 7 (Management) [optional]
```

**Recommended Order:**
1. Session 1 → Ship immediately (quick win)
2. Session 2 & 3 in parallel → Infrastructure foundations
3. Session 4 → Extract memories (can test with mock storage)
4. Session 5 → Store + confirm
5. Session 6 → Retrieve + inject
6. Session 7 → Management UI (if time permits)

---

### Validation Strategy Per Session

Each session should include:
- **Unit tests**: Test functions in isolation
- **Integration tests**: Test component end-to-end
- **Manual validation**: Real conversation testing
- **Acceptance criteria**: Clear pass/fail metrics

**Example for Session 4 (Extraction):**
```python
# Unit test
def test_confidence_calculation():
    assert calculate_confidence(explicit=True, mentions=3) >= 0.8

# Integration test
def test_extract_from_conversation():
    transcript = load_test_conversation()
    memories = extractor.extract(transcript)
    assert len(memories) >= 5
    assert all(m.confidence >= 0.4 for m in memories)

# Manual validation
# Run extraction on 10 real conversations, manually verify:
# - Extracted memories are accurate (≥85%)
# - Confidence scores make sense
# - Categories are appropriate
```

---

## 7. Next Steps & Action Items

### Immediate Actions (This Week - Phase 1)

**Task 1: System Prompt Redesign** (Owner: Vincent, 2 hours)
- [ ] Update `.env` HAIA_SYSTEM_PROMPT
  - Remove "Homelab Specialty (your area of deep expertise)" language
  - Reframe: "You're versatile - from casual conversation and general knowledge questions to deep technical troubleshooting"
  - Add examples: philosophy question, whisky recommendation, family advice, homelab troubleshooting
  - Maintain existing personality (sophisticated, dry wit, professional)
- [ ] Test conversational improvements:
  - Ask 5 non-homelab questions (whisky, philosophy, family, hobbies, general knowledge)
  - Verify no apologetic disclaimers
  - Confirm homelab expertise still strong (ask technical question)
- [ ] Deploy updated prompt to production
- [ ] Document changes in CLAUDE.md "Recent Changes" section

**Task 2: Create Memory System Specification** (Owner: Vincent, 4 hours)
- [ ] Use `/speckit.specify` to create feature spec
  - Input: "Personal Memory System - Neo4j graph with vector search for progressive learning about Vincent across all life domains"
  - Ensure spec includes: extraction rules, confirmation strategy, retrieval tiers, context injection format
- [ ] Review generated spec for alignment with brainstorming decisions
- [ ] Add specific examples from this session

---

### Phase 2 Preparation (Next 1-2 Weeks)

**Task 3: Infrastructure Planning** (Owner: Vincent, 1 day)
- [ ] Design Neo4j Docker Compose configuration
  - Image: neo4j:5.15 (vector search support)
  - Plugins: APOC, Graph Data Science
  - Persistence: volume mapping to NAS
  - Authentication: strong password
- [ ] Plan backup strategy
  - Automated daily dumps to separate backup location
  - Test restore procedure
- [ ] Document Neo4j access and monitoring

**Task 4: Technical Research** (Owner: Vincent, 2 days)
- [ ] Explore Neo4j vector search documentation
  - Embedding index creation
  - Similarity search queries
  - Combine vector + graph queries
- [ ] Evaluate embedding API options
  - OpenAI embeddings API (simple, cost)
  - Anthropic embeddings (if available)
  - Local embedding model (Ollama + sentence-transformers)
- [ ] Prototype basic memory extraction
  - Use PydanticAI to analyze conversation transcript
  - Extract test facts with confidence scores
  - Validate extraction quality

**Task 5: Implement Memory System** (Owner: Vincent, 3-4 weeks)
- [ ] Follow implementation tasks from Section 3.3 (Phase 2)
- [ ] Use `/speckit.plan` to generate detailed implementation plan
- [ ] Use `/speckit.tasks` to break down into actionable tasks
- [ ] Track progress in GitHub issues

---

## 7. Key Metrics & Success Criteria

### Phase 1 Success Criteria (System Prompt Fix)

**Qualitative Metrics:**
- ✅ HAIA responds naturally to non-homelab questions without disclaimers
- ✅ Conversational flow feels seamless across topic domains
- ✅ Homelab expertise quality remains high (no regression)
- ✅ Vincent feels comfortable asking any type of question

**Testing Scenarios:**
1. Ask philosophical question → Natural response, no "off-topic" mention
2. Ask whisky recommendation → Helpful advice without apologizing
3. Ask family advice → Engaged, thoughtful response
4. Ask technical homelab question → Expert response as before
5. Mix topics in conversation → Smooth transitions

---

### Phase 2 Success Criteria (Memory System)

**Quantitative Metrics:**
- ✅ Memory extraction accuracy ≥85% (manual review of 20 conversations)
- ✅ Memory retrieval latency P95 <200ms (tier 1+2)
- ✅ Neo4j graph growth: 50-100 nodes after 1 month of daily use
- ✅ Context injection adds <500ms to response time
- ✅ Memory confirmation acceptance rate ≥80% (user approves most suggestions)

**Qualitative Metrics:**
- ✅ HAIA recalls personal facts naturally ("Your son's soccer schedule...")
- ✅ HAIA applies technical preferences contextually ("You prefer LXC for this...")
- ✅ HAIA distinguishes relevance (doesn't mention family during Ceph troubleshooting)
- ✅ Conversation quality improves over time (personalization increases)
- ✅ Vincent trusts HAIA's memory (feels known and understood)

**Testing Scenarios:**
1. **Personal Memory Recall:**
   - Week 1: Mention son's soccer schedule
   - Week 2: Ask "Help me plan this weekend"
   - Expected: HAIA mentions soccer Saturday, suggests Sunday activities

2. **Technical Preference Application:**
   - Week 1: Explain preference for LXC over Docker for single services
   - Week 2: Ask "Should I deploy service X?"
   - Expected: HAIA recommends LXC and mentions previous preference

3. **Infrastructure Context Awareness:**
   - Week 1: Discuss critical nature of zigbee2mqtt on prox0
   - Week 2: Ask "Should I upgrade prox0?"
   - Expected: HAIA warns about zigbee2mqtt impact, suggests testing elsewhere

4. **Context Relevance Filtering:**
   - Ask homelab question about Ceph storage
   - Expected: HAIA does NOT mention family or personal interests (stays focused)

5. **Progressive Learning:**
   - Week 1: Mention interest in photography
   - Week 3: Mention bought new camera lens
   - Week 5: HAIA asks "How's photography going with that new lens?"
   - Expected: HAIA demonstrates continuity and genuine interest

---

## 8. Appendix

### A. Industry Research Summary

**Systems Analyzed:**
1. **ChatGPT Memory (OpenAI)** - Aggressive extraction, user control via UI
2. **Google Assistant** - Selective confirmation, routine pattern storage
3. **Notion AI** - Contextual suggestions, batch review
4. **Mem.ai** - Store everything, smart surfacing

**Key Learnings:**
- Consensus on aggressive extraction (users prefer over-collection)
- Tiered confirmation reduces friction (only ask for high-impact)
- Post-hoc review interfaces critical for user trust
- Confidence scoring enables smart filtering
- Graph + vector becoming industry standard for personal AI

---

### B. Technology Stack

**Core Components:**
- **Neo4j 5.15+** - Graph database with native vector search
- **PydanticAI** - Agent framework (existing)
- **FastAPI** - API server (existing)
- **Embedding API** - OpenAI or Anthropic (TBD during Phase 2)

**New Dependencies:**
```python
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "neo4j>=5.15",           # Graph database driver
    "openai>=1.0",           # For embeddings (if chosen)
    # OR
    "sentence-transformers"  # For local embeddings (alternative)
]
```

**Infrastructure:**
```yaml
# docker-compose.yml (memory-stack.yml)
services:
  neo4j:
    image: neo4j:5.15-enterprise
    environment:
      NEO4J_AUTH: neo4j/strong_password_here
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*,gds.*"
    ports:
      - "7474:7474"  # Web UI
      - "7687:7687"  # Bolt protocol
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./backups:/backups
```

---

### C. Example Memory Queries

**Query 1: What depends on prox0?**
```cypher
MATCH (service)-[:RUNS_ON|REQUIRES*]->(prox0:Infrastructure {name: "prox0"})
RETURN service.name, service.criticality
ORDER BY service.criticality DESC
```

**Query 2: What are Vincent's active interests?**
```cypher
MATCH (vincent:Person {name: "Vincent"})-[:INTERESTED_IN]->(interest:Interest {active: true})
RETURN interest.name, interest.proficiency_level, interest.first_mentioned
ORDER BY interest.first_mentioned DESC
```

**Query 3: Semantic search for whisky-related memories**
```cypher
MATCH (memory:Memory)
WHERE memory.embedding <-> $query_embedding < 0.3
RETURN memory.content, memory.category, memory.confidence
ORDER BY memory.embedding <-> $query_embedding
LIMIT 10
```

**Query 4: Combined query - weekend planning**
```cypher
// Get family events
MATCH (event:Event)
WHERE event.schedule CONTAINS "Saturday" OR event.schedule CONTAINS "Sunday"
RETURN event AS family_events

UNION

// Get active goals
MATCH (vincent:Person {name: "Vincent"})-[:PURSUING]->(goal:LifeGoal {status: "active"})
RETURN goal AS active_goals

UNION

// Get infrastructure needing attention
MATCH (infra:Infrastructure)
WHERE infra.needs_attention = true
RETURN infra AS maintenance_items
```

---

### D. Conversation Heuristic Pseudocode

```python
class ConversationBoundaryDetector:
    """Detect conversation boundaries in stateless API"""

    def __init__(self):
        self.last_request_time = None
        self.last_message_count = 0
        self.last_first_message_hash = None

    async def should_extract_memories(self, request: ChatCompletionRequest) -> bool:
        """
        Hybrid heuristic for conversation boundary detection

        Returns True when:
        1. >10 minutes since last request AND
        2. Message history changed significantly
        """
        current_time = time.time()
        current_message_count = len(request.messages)
        current_first_message = hash(request.messages[0].content)

        # Check time delta
        if self.last_request_time is None:
            time_delta = 0
        else:
            time_delta = current_time - self.last_request_time

        # Check message history changes
        message_count_dropped = current_message_count < (self.last_message_count * 0.5)
        first_message_changed = current_first_message != self.last_first_message_hash

        # Update tracking
        self.last_request_time = current_time
        self.last_message_count = current_message_count
        self.last_first_message_hash = current_first_message

        # Trigger extraction if idle + history changed
        if time_delta > 600 and (message_count_dropped or first_message_changed):
            return True

        return False
```

---

### E. Memory Confidence Scoring Algorithm

```python
def calculate_confidence(extraction_context: ExtractionContext) -> float:
    """
    Calculate confidence score for extracted memory

    Factors:
    - Explicit vs inferred (0.3 boost for explicit)
    - Multiple mentions (0.1 boost per mention, max 0.3)
    - Contradiction signals (-0.4 penalty)
    - User confirmation (+0.2 if confirmed)
    """
    base_confidence = 0.5  # Start at moderate

    # Explicit statement boost
    if "I" in extraction_context.statement or "my" in extraction_context.statement:
        base_confidence += 0.3

    # Multiple mention boost
    mention_count = extraction_context.times_mentioned
    mention_boost = min(mention_count * 0.1, 0.3)
    base_confidence += mention_boost

    # Contradiction penalty
    if extraction_context.contradicts_existing:
        base_confidence -= 0.4

    # User confirmation boost
    if extraction_context.user_confirmed:
        base_confidence += 0.2

    # Uncertainty markers penalty
    if any(word in extraction_context.statement.lower() for word in ["maybe", "might", "possibly"]):
        base_confidence -= 0.2

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, base_confidence))
```

---

## Session Retrospective

**What Went Well:**
- Progressive questioning approach uncovered deep insights about vision
- Pivoted from "fix the prompt" to "build memory system" through good discovery
- Industry research validated architecture choices
- Two-phase deployment provides quick wins + long-term solution
- Clear decision documentation with rationale

**What Could Be Improved:**
- Could have explored knowledge graph option earlier
- Memory schema could use more concrete examples for each node type
- Testing strategy needs more detail (will add during spec phase)

**Key Takeaways:**
1. HAIA's evolution is about **companionship**, not just capabilities
2. Memory makes the difference between assistant and companion
3. Hybrid graph+vector is the architecture for sophisticated personal AI
4. Industry patterns (tiered confirmation, aggressive extraction) are proven

**Next Brainstorming Topics:**
- Detailed extraction prompt engineering (how to instruct LLM to categorize memories)
- Memory analytics dashboard design (visualize knowledge graph)
- Multi-domain agent tools (homelab MCP servers, personal productivity tools)

---

**Document Generated:** 2025-12-06
**Total Session Time:** ~2 hours
**Decisions Made:** 6 major architectural decisions
**Risks Identified:** 6 with mitigation strategies
**Next Phase:** System prompt fix (immediate), Memory system spec (next week)
