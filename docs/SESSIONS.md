# HAIA Memory System - Specification Sessions

**Overview:** This document contains ready-to-use prompts for all 7 specification sessions of the HAIA Personal Memory System. Each session is designed to be completed in 3-5 days and can be executed using the `/speckit.specify` command.

**Source:** Generated from brainstorming session on 2025-12-06
**Reference:** See `docs/brainstorming/2025-12-06-haia-personal-memory-system.md` for full context

---

## Session Workflow

For each session below:

1. **Copy the prompt** from the session you're working on
2. **Run `/speckit.specify`** with the prompt
3. **Review** the generated specification
4. **Run `/speckit.plan`** to create implementation plan
5. **Run `/speckit.tasks`** to generate actionable tasks
6. **Implement, test, and ship** that component
7. **Move to next session**

---

## Dependency Graph

```
Session 1 (Prompt Fix)
   ↓ [can ship immediately]

Session 2 (Boundaries) ──┐
Session 3 (Docker+Neo4j)──┤
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

## Session 1: System Prompt Personality Fix

**Status:** ✅ COMPLETE (2025-12-07)
**Priority:** IMMEDIATE (ship this week)
**Effort:** 1-2 days (actual: ~3 hours)
**Dependencies:** None

### Prompt for `/speckit.specify`:

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

### Success Criteria:
- HAIA answers whisky questions naturally (no "not homelab-related" disclaimers)
- **Homelab responses remain expert-level quality** (same technical depth as before)
- **Critical service awareness unchanged** (still warns about zigbee2mqtt, prox0, etc.)
- Smooth topic transitions across domains
- Conversational flow feels natural across all topics
- **No regression in homelab expertise** (validate with technical questions)

### Key Changes:
- Update `.env` HAIA_SYSTEM_PROMPT
- **Remove:** "Homelab Specialty (your area of deep expertise)" framing
- **Keep:** All homelab knowledge, critical service warnings, technical depth
- **Reframe:** "You're versatile across many domains" (homelab is ONE expertise area)
- **Add:** Diverse examples showing versatility (philosophy, whisky, family, general knowledge)
- **Maintain:** All existing personality traits and communication style

### Testing Plan:
1. **Non-homelab validation:** Ask 5 diverse questions (whisky, philosophy, family, hobbies, general knowledge)
   - ✓ No apologetic disclaimers
   - ✓ Natural, engaged responses
2. **Homelab expertise validation:** Ask 3 technical homelab questions
   - ✓ Same technical depth as before
   - ✓ Critical service warnings still present (zigbee2mqtt, prox0)
   - ✓ Infrastructure knowledge intact
3. **Topic transition validation:** Mix domains in single conversation
   - ✓ Smooth transitions
   - ✓ Maintains context across topics
4. **Regression testing:** Compare homelab responses before/after prompt change
   - ✓ No loss of technical detail
   - ✓ Same cautious approach to critical services

### Completion Summary (2025-12-07):

**Implementation**:
- Updated `.env` HAIA_SYSTEM_PROMPT variable (line 59: "Homelab Infrastructure" replaces "Homelab Specialty")
- Added 5 diverse conversation examples (philosophy, whisky, family, photography, quantum computing)
- Repositioned examples: 6 non-homelab before 2 homelab (75% non-homelab)
- All homelab knowledge preserved verbatim (9 bullet points)
- All critical service warnings preserved verbatim (4 services)

**Validation Results**:
- ✅ SC-001 PASSED: 5/5 non-homelab questions (100%) with zero disclaimers
  - Whisky: Natural recommendations, no apologies
  - Philosophy: Sophisticated engagement with free will discussion
  - Family: Practical work-life balance advice
  - Photography: Enthusiastic brainstorming, naturally mentioned homelab tools
  - Quantum computing: Clear technical explanation
- ✅ Homelab expertise validated: Backup strategy question showed full technical depth maintained
- ✅ Natural topic transitions: Photography → homelab tools mentioned without meta-commentary

**Files Modified**:
- `.env` (system prompt only - not committed, contains API key)
- `.gitignore` (added specs/ to ignore list)

**Backup**: `.env.backup.2025-12-07`

**Documentation**: `specs/004-system-prompt-redesign/` (local-only, removed from git history for privacy)

**Git History**:
- PR #5 merged to main (2025-12-07)
- Specs folder removed from all git history (contains personal infrastructure details)
- Feature branch deleted

**Outcome**:
- ✅ HAIA now responds naturally across all topics without apologetic disclaimers
- ✅ Homelab expertise and critical service awareness fully preserved
- ✅ Feature LIVE in production
- ✅ Sensitive infrastructure details removed from public repository

---

## Session 2: Conversation Boundary Detection

**Status:** Blocked until Session 1 complete (optional - can develop in parallel)
**Priority:** High
**Effort:** 2-3 days
**Dependencies:** None (independent component)

### Prompt for `/speckit.specify`:

```
Conversation Boundary Detection - Implement hybrid heuristic to detect conversation
endings in stateless OpenAI-compatible API. Track request timestamps and message
history metadata. Trigger extraction when >10min idle AND message history changed
significantly (message count dropped >50% OR first message hash differs). Store
transcript for extraction. No actual memory extraction yet - just boundary detection
and transcript capture.
```

### Success Criteria:
- Correctly detects conversation endings in 90% of test cases
- Captures full conversation transcripts for extraction
- Logs trigger events with metadata for debugging
- No false positives during long multi-turn conversations

### Key Components:
- Request metadata tracking (timestamps, message counts, hashes)
- Hybrid heuristic algorithm (time + history analysis)
- Transcript storage (in-memory or temporary file system)
- Logging and observability

### Testing Plan:
1. Simulate 10 conversations with varied patterns (short, long, interrupted)
2. Verify boundary detection accuracy
3. Confirm transcript completeness
4. Test edge cases (rapid requests, very long gaps, message edits)

---

## Session 3: Docker Compose Stack & Neo4j Infrastructure

**Status:** Blocked until ready to start memory system infrastructure
**Priority:** High (foundation for Sessions 4-7)
**Effort:** 4-5 days
**Dependencies:** None (can develop in parallel with Session 2)

### Prompt for `/speckit.specify`:

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

### Success Criteria:
- `docker-compose up` starts both services successfully
- HAIA accessible on http://localhost:8000
- Neo4j web UI accessible on http://localhost:7474
- Services communicate via Docker network
- Persistence works across container restarts
- Can run HAIA locally for development (connects to containerized Neo4j)
- Backup script creates daily Neo4j dumps
- Health checks report service status correctly
- Schema documented with Cypher examples
- Can create/read all node types via Python

### Key Components:
- `Dockerfile` for HAIA container
- `docker-compose.yml` for full stack
- `docker-compose.dev.yml` for development overrides
- `.dockerignore` file
- Neo4j schema definition (Cypher)
- Python Neo4j driver integration
- CRUD operations for all node types
- Backup automation script
- `deployment/docker-install.sh` installation script

### Testing Plan:
1. Test full stack deployment (`docker-compose up`)
2. Verify service communication (HAIA → Neo4j queries)
3. Test persistence (restart containers, verify data intact)
4. Test backup/restore cycle
5. Test development workflow (native HAIA + container Neo4j)
6. Validate schema with test data creation

---

## Session 4: Memory Extraction Engine

**Status:** Blocked until Session 2 complete
**Priority:** High
**Effort:** 4-5 days
**Dependencies:** Session 2 (needs conversation transcripts)

### Prompt for `/speckit.specify`:

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

### Success Criteria:
- Extracts 10+ memory types from test conversations
- Confidence scoring accurate (manual validation on 20 test conversations)
- Categorizes memories correctly (≥85% accuracy)
- Extraction completes in <10 seconds for 20-message conversation
- Handles edge cases (ambiguity, contradictions, corrections)

### Key Components:
- PydanticAI extraction agent with specialized prompts
- Confidence calculation algorithm
- Memory categorization logic (personal/technical/preference/decision)
- Extraction rules for each memory type
- JSON output format
- Batch processing for conversation transcripts

### Testing Plan:
1. Create 20 diverse test conversations (personal, technical, mixed)
2. Run extraction on all test cases
3. Manually validate extraction quality (accuracy, confidence, categories)
4. Test performance (latency for various conversation lengths)
5. Test edge cases (ambiguous statements, contradictions, rapid topic changes)

---

## Session 5: Memory Storage & Confirmation

**Status:** Blocked until Sessions 3 & 4 complete
**Priority:** High
**Effort:** 4-5 days
**Dependencies:** Session 3 (Neo4j schema), Session 4 (extraction engine)

### Prompt for `/speckit.specify`:

```
Memory Storage & Confirmation - Store extracted memories in Neo4j graph database.
Generate embeddings via OpenAI Embeddings API. Implement tiered confirmation strategy:
70% auto-store (silent), 20% inline contextual (embed in conversation), 10% explicit
(ask directly). Decision matrix based on confidence + impact + contradiction. Create
confirmation response templates. Store confirmed memories with metadata (timestamp,
confidence, source). Implement contradiction detection (CONTRADICTS relationship).
Support manual "/remember" trigger for immediate storage.
```

### Success Criteria:
- Memories stored correctly in Neo4j with all metadata
- Confirmation tiers applied accurately based on decision matrix
- User accepts ≥80% of inline confirmations (natural phrasing)
- Manual "/remember" trigger works instantly
- Embeddings generated and stored for all memories
- Contradiction detection flags conflicts correctly

### Key Components:
- Neo4j storage operations (create nodes, relationships)
- OpenAI Embeddings API integration
- Tiered confirmation decision matrix
- Confirmation response templates (auto/inline/explicit)
- CONTRADICTS relationship detection
- Manual trigger handler ("/remember" command)
- Metadata tracking (timestamp, confidence, source)

### Testing Plan:
1. Test auto-store tier (70% - silent storage)
2. Test inline contextual confirmation (20% - natural flow)
3. Test explicit confirmation (10% - direct questions)
4. Test contradiction detection (update old memories)
5. Test manual "/remember" trigger
6. Verify embedding generation and storage

---

## Session 6: Memory Retrieval & Context Injection

**Status:** Blocked until Session 5 complete
**Priority:** High
**Effort:** 4-5 days
**Dependencies:** Session 5 (stored memories in Neo4j)

### Prompt for `/speckit.specify`:

```
Memory Retrieval & Context Injection - Implement three-tier retrieval strategy for
loading relevant memories. Tier 1: Critical context (entity mentions, always load,
<100ms). Tier 2: Semantic relevance (vector search top 10 + graph traversal 1-2 hops,
<200ms). Tier 3: Deep context (on-demand for "remember when" queries, <500ms). Filter
retrieval by confidence ≥0.6. Format memories as hybrid structured markdown for agent
context injection (Personal, Technical Preferences, Infrastructure Context, Recent
Conversations sections). Inject into PydanticAI agent's system prompt before each request.
```

### Success Criteria:
- Retrieval P95 latency <200ms for tier 1+2
- Relevant memories injected (manual validation on test queries)
- Agent uses memories in responses naturally
- Irrelevant memories filtered out (≥90% precision)
- Context injection doesn't degrade response quality

### Key Components:
- Tier 1 retrieval (critical context, entity matching)
- Tier 2 retrieval (vector search + graph traversal)
- Tier 3 retrieval (deep context, on-demand)
- Confidence filtering (≥0.6 threshold)
- Markdown formatting (hybrid structured + natural)
- PydanticAI integration (system prompt injection)

### Testing Plan:
1. Benchmark retrieval latency (P50, P95, P99)
2. Test tier 1 (entity mentions trigger correct memories)
3. Test tier 2 (semantic search finds related concepts)
4. Test tier 3 (deep queries like "remember when...")
5. Validate precision (relevant memories only)
6. Test agent responses (uses memories naturally)

---

## Session 7: Memory Management Interface (Optional)

**Status:** Optional - Nice to have, not required for MVP
**Priority:** Low (can defer to future iteration)
**Effort:** 2-3 days
**Dependencies:** Session 6 (full memory system working)

### Prompt for `/speckit.specify`:

```
Memory Management Commands - Implement slash commands for memory control: /memory review
(view all by category), /memory search [query] (semantic search), /memory forget [topic]
(delete category), /memory export (download JSON), /memory stats (graph statistics).
Format output as readable summaries with edit/delete options. Support category filtering,
date ranges, confidence thresholds. Provide visualization suggestions for graph structure.
```

### Success Criteria:
- All commands work as specified
- User can audit and correct memories easily
- Export format is human-readable (JSON or YAML)
- Memory deletion is immediate and permanent
- Statistics show useful insights (node counts, relationships, confidence distribution)

### Key Components:
- `/memory review` command (list all memories by category)
- `/memory search` command (semantic search)
- `/memory forget` command (delete by category/topic)
- `/memory export` command (download as JSON)
- `/memory stats` command (graph statistics)
- Formatted output (readable summaries)
- Edit/delete operations
- Filtering options (category, date, confidence)

### Testing Plan:
1. Test each command independently
2. Test filtering and search accuracy
3. Test deletion (verify cascade deletes relationships)
4. Test export/import round-trip
5. Test statistics accuracy
6. Manual UX testing (ease of use)

---

## Implementation Notes

### Development vs Production

**Development Mode:**
- Run HAIA natively (faster iteration)
- Neo4j in container (consistent environment)
- Hot reload enabled
- Detailed logging

**Production Mode:**
- Full Docker Compose stack
- Automated restarts
- Health monitoring
- Backup automation

### Environment Variables Required

**HAIA:**
- `ANTHROPIC_API_KEY` (required for LLM)
- `HAIA_MODEL` (e.g., "anthropic:claude-haiku-4-5-20251001")
- `HAIA_SYSTEM_PROMPT` (personality prompt)
- `HAIA_PROFILE_PATH` (path to vincent_profile.yaml)
- `NEO4J_URI` (e.g., "bolt://neo4j:7687" or "bolt://localhost:7687")
- `NEO4J_USER` (default: "neo4j")
- `NEO4J_PASSWORD` (generated or set)

**Neo4j:**
- `NEO4J_AUTH` (user/password)
- `NEO4J_PLUGINS` (APOC, Graph Data Science)
- `NEO4J_dbms_memory_heap_max__size` (e.g., "2G")

### Validation Strategy

Each session should include:

1. **Unit Tests** - Test functions in isolation
2. **Integration Tests** - Test component end-to-end
3. **Manual Validation** - Real conversation testing
4. **Performance Tests** - Latency, throughput benchmarks
5. **Acceptance Criteria** - Clear pass/fail metrics

### Timeline Summary

| Session | Effort | Can Start After | Critical Path |
|---------|--------|----------------|---------------|
| 1 | 1-2 days | Immediately | Yes |
| 2 | 2-3 days | Immediately | Yes |
| 3 | 4-5 days | Immediately | Yes |
| 4 | 4-5 days | Session 2 | Yes |
| 5 | 4-5 days | Sessions 3+4 | Yes |
| 6 | 4-5 days | Session 5 | Yes |
| 7 | 2-3 days | Session 6 | No (optional) |

**Minimum Critical Path:** 16-21 days (Sessions 1-6)
**With Optional Session 7:** 18-24 days

**Parallel Opportunities:**
- Sessions 2 & 3 can be developed in parallel (independent)
- Session 1 ships independently (quick win)

---

## Quick Reference

**Start Session 1 NOW:**
```bash
/speckit.specify System Prompt Redesign - Update HAIA's system prompt to position her as a versatile personal companion while MAINTAINING her deep homelab expertise. Remove "Homelab Specialty (your area of deep expertise)" framing that makes her apologize for non-homelab questions. Reposition homelab as ONE capability among many (general conversation, technical expertise, homelab infrastructure). Keep ALL existing homelab knowledge, critical service warnings (zigbee2mqtt, Home Assistant, Nextcloud, prox0), and technical depth. Add diverse conversation examples (philosophy, whisky, family advice, general knowledge) to demonstrate versatility. Maintain existing personality (sophisticated, dry wit, professional). Test that she responds naturally to ALL topics without apologetic disclaimers while PRESERVING expert-level homelab responses with same technical depth as before.
```

**Next Steps After Session 1:**
- Develop Sessions 2 & 3 in parallel
- Session 2: Conversation boundary detection
- Session 3: Docker Compose + Neo4j infrastructure

**Memory System Goes Live:**
- After Session 6 completes, full memory system is operational
- Session 7 is polish/UX enhancement (optional)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-06
**Source:** Brainstorming session with comprehensive architecture design
**Next Review:** After Session 3 completion (validate approach before Sessions 4-6)
