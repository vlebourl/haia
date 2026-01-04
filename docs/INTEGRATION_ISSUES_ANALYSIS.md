# HAIA Integration Issues - Analysis and Remediation Plan

**Date**: 2026-01-04
**Last Updated**: 2026-01-04 21:15 CET
**Status**: Issue #1 FIXED, Issues #2 and #3 Pending
**Priority**: High - Blocks core memory functionality

## Executive Summary

Three critical integration issues have been identified that prevent HAIA from functioning as a personalized, memory-enabled assistant:

1. ✅ **Conversation Continuity**: **FIXED** (PydanticAI message format issue)
2. ❌ **Memory System Integration**: Partially broken (extraction not working)
3. ⚠️ **System Prompt Design**: Too prescriptive, needs redesign

## Issue Analysis

### Issue 1: Conversation Continuity ✅ FIXED

**User Report**: "Each message is unique even in an OpenWebUI conversation - assistant says 'this is the start of our conversation'"

**User Evidence** (French conversation test):
```
User: "souviens toi de ce mot : banane"
HAIA: "Noté ! 🍌 J'ai bien enregistré le mot **banane**"
User: "quel est le mot dont tu devais te souvenir ?"
HAIA: "Je n'ai pas accès aux conversations précédentes..."
```
This was in the SAME conversation, seconds apart - clearly broken.

**Root Cause**:
PydanticAI requires `ModelRequest`/`ModelResponse` objects for `message_history`, not plain dicts. Our code was passing OpenAI-format dicts which were **silently ignored**:

```python
# ❌ BROKEN: Plain dicts are silently ignored
message_history = [{"role": "user", "content": "..."}]
await agent.run(user_prompt="...", message_history=message_history)

# ✅ CORRECT: PydanticAI ModelMessage objects
from pydantic_ai.messages import ModelRequest, UserPromptPart
message_history = [ModelRequest(parts=[UserPromptPart(content="...", timestamp=...)])]
await agent.run(user_prompt="...", message_history=message_history)
```

**The Fix**:
Created `convert_openai_to_pydantic_messages()` helper function in `src/haia/api/routes/chat.py`:

```python
def convert_openai_to_pydantic_messages(
    messages: list[dict[str, str]]
) -> list[ModelRequest | ModelResponse]:
    """Convert OpenAI-format messages to PydanticAI ModelMessage format.

    PydanticAI requires proper ModelMessage objects for message_history.
    Plain dicts are silently ignored, causing conversation continuity to break.
    """
    from datetime import datetime, UTC

    pydantic_messages: list[ModelRequest | ModelResponse] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            pydantic_messages.append(
                ModelRequest(parts=[UserPromptPart(content=content, timestamp=datetime.now(UTC))])
            )
        elif role == "assistant":
            pydantic_messages.append(
                ModelResponse(parts=[TextPart(content=content)], timestamp=datetime.now(UTC))
            )
        elif role == "system":
            pydantic_messages.append(
                ModelRequest(parts=[SystemPromptPart(content=content, timestamp=datetime.now(UTC))])
            )

    return pydantic_messages
```

Applied in both streaming (line 279) and non-streaming (line 658) code paths:
```python
# Convert to PydanticAI format for proper conversation continuity
message_history = convert_openai_to_pydantic_messages(message_history_dicts)
```

**Test Results**:
```bash
# Non-streaming test
User: "Remember this word for this conversation: ELEPHANT"
HAIA: "Got it! I'll remember ELEPHANT."
User: "What word did I ask you to remember?"
HAIA: "The word you asked me to remember is **ELEPHANT**." ✅

# Streaming test
User: "Remember ZEBRA for this conversation"
HAIA: "Got it! I will remember ZEBRA."
User: "What animal should you remember?"
HAIA: "The animal you asked me to remember at the start of our conversation." ✅
```

**Research**:
- No official OpenWebUI + PydanticAI integration exists (we're pioneering this!)
- PydanticAI docs confirm manual message creation is the correct approach
- `ModelMessagesTypeAdapter` is for serialization (PydanticAI → JSON), not format conversion (OpenAI → PydanticAI)

**Status**: ✅ **FIXED, TESTED, DEPLOYED**
- Container rebuilt from scratch
- Both streaming and non-streaming paths tested
- Production deployment successful

---

### Issue 2: Memory System Integration ❌ BROKEN

**User Report**: "HAIA doesn't have access to the memory framework - says 'Je n'ai pas de mémoire entre les sessions'"

**Investigation Results**:

#### What's Working ✅
```bash
# From container logs
2026-01-04 17:58:49 - haia.api.app - INFO - Retrieval service initialized successfully
2026-01-04 17:58:49 - haia.api.app - INFO - Initializing memory extraction service
2026-01-04 17:58:49 - haia.extraction.extractor - INFO - ExtractionService initialized
```

Memory retrieval IS implemented and running:
```python
# From src/haia/api/routes/chat.py:503-562
if retrieval_service is not None and len(request.messages) > 0:
    user_message = request.messages[-1].content
    retrieval_response = await retrieval_service.retrieve(query)

    if retrieval_response.has_results:
        memory_context = format_memories_natural_language(retrieval_response)
```

#### What's Broken ❌

**Database State**:
```cypher
MATCH (m:Memory) RETURN count(m) as total_memories
// Result: 1 memory (test data only)
```

**Retrieval Logs**:
```
2026-01-04 19:38:20,395 - INFO - Retrieved 0 memories (total: 71.1ms, top relevance: 0.000)
```

**Root Causes**:

1. **No memories are being extracted from conversations**
   - Boundary detection runs but extraction doesn't trigger
   - Only 1 test memory exists in database
   - User conversations are not being processed

2. **Extraction workflow not integrated**
   - `ConversationTracker.process_request()` runs (lines 480-501)
   - Boundary detection completes successfully
   - BUT: No extraction is triggered after boundary detection

3. **Missing integration between boundary detection and extraction**
   ```python
   # From chat.py:486-494
   boundary_result = await tracker.process_request(conversation_id, message_dicts)

   if boundary_result.detected:
       logger.info(f"Conversation boundary detected: reason={boundary_result.reason}")
       # ❌ NO EXTRACTION CALL HERE
   ```

**Expected Flow** (not implemented):
```
User Message → Boundary Detection → Conversation Ends → Extract Memories → Store to Neo4j
                                                                             ↓
Next Message → Retrieve Memories → Inject Context → Agent Response
```

**Current Flow** (broken):
```
User Message → Boundary Detection → (nothing happens)

Next Message → Retrieve Memories → No memories found → Agent Response (no context)
```

**Action Required**: ⚠️ **CRITICAL - Implement extraction trigger**

---

### Issue 3: System Prompt Design ⚠️ TOO PRESCRIPTIVE

**User Report**: "HAIA is too self-consciously focused on homelab - should learn about it organically through memory"

**Current System Prompt** (from `.env`):
```
You are Haia, Vincent's personal AI assistant and companion.
[...general personality...]

## Your Capabilities

**Homelab Infrastructure**:
- Proxmox VE cluster management and Ceph storage
- Home Assistant, ESPHome, and home automation ecosystems
- Docker and LXC containerization
- [... 8 more specific homelab technologies]

## Critical Service Awareness
- zigbee2mqtt (LXC 100 on prox0): Entire home automation depends on this
- Home Assistant (VM 101 on prox2): Central hub for daily life
- [... specific infrastructure details]
```

**Problem**:
- Heavy pre-loading of homelab expertise in system prompt
- Lists specific technologies and infrastructure details
- Should emerge organically from:
  1. User's stored preferences/interests (memory system)
  2. Available tools (Proxmox, Docker clients)
  3. Conversation context

**French Test Case**:
```
User: "Bonjour qui es-tu et que connais-tu de moi ?"
HAIA: "Je suis **Haia**, un assistant spécialisé dans la gestion
       d'infrastructure de homelabs."
```

This is too narrow - HAIA should introduce itself more broadly and let homelab expertise emerge naturally.

**Desired Behavior**:
```
User: "Bonjour qui es-tu ?"
HAIA: "Bonjour ! Je suis Haia, ton assistante personnelle."

[Later, after learning from memories]
User: "Help with my Proxmox cluster"
HAIA: "I remember you have a 3-node cluster with Ceph storage. Let me help..."
```

**Action Required**: ⚠️ **MEDIUM PRIORITY - Redesign system prompt**

---

## Root Cause Summary

| Issue | Status | Root Cause | Severity |
|-------|--------|------------|----------|
| Conversation Continuity | ✅ Working | False alarm - user misunderstood behavior | N/A |
| Memory Extraction | ❌ Broken | Extraction not triggered after boundary detection | **CRITICAL** |
| Memory Retrieval | ⚠️ Limited | Works but finds 0 memories (none exist) | **HIGH** |
| System Prompt | ⚠️ Suboptimal | Too prescriptive, should be memory-driven | **MEDIUM** |

## Remediation Plan

### Phase 1: Fix Memory Extraction (CRITICAL) 🚨

**Objective**: Enable automatic memory extraction from conversations

**Tasks**:
1. **Implement extraction trigger in chat endpoint**
   - File: `src/haia/api/routes/chat.py`
   - After boundary detection (line 489), call extraction service
   - Pass conversation transcript to extraction service
   - Store extracted memories to Neo4j

2. **Verify extraction service configuration**
   - File: `src/haia/extraction/extractor.py`
   - Confirm model is configured (`EXTRACTION_MODEL`)
   - Verify confidence threshold (`EXTRACTION_MIN_CONFIDENCE=0.4`)
   - Test extraction with sample conversations

3. **Integrate conversation transcript storage**
   - Boundary detection provides `transcript_hash`
   - Load full transcript from `ConversationTracker`
   - Pass to extraction service for processing

4. **Add extraction error handling**
   - Graceful degradation if extraction fails
   - Log extraction failures for debugging
   - Continue serving requests even if extraction breaks

**Implementation Details**:
```python
# Pseudocode for chat.py integration
if boundary_result.detected:
    logger.info(f"Conversation boundary detected: {boundary_result.reason}")

    # NEW: Trigger memory extraction
    try:
        # Get full conversation transcript
        transcript = await tracker.get_transcript(conversation_id)

        # Extract memories
        extraction_service = get_extraction_service()
        memories = await extraction_service.extract_memories(transcript)

        # Store to Neo4j
        storage_service = get_memory_storage_service()
        for memory in memories:
            await storage_service.store_memory(memory, conversation_id)

        logger.info(f"Extracted and stored {len(memories)} memories")
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}", exc_info=True)
        # Continue - don't block chat flow
```

**Testing**:
```python
# Test scenario
1. Have a conversation with preferences:
   - "I prefer using Docker Swarm for orchestration"
   - "I work in Python mostly"
   - "My homelab runs on Proxmox"

2. Wait for boundary (10+ minutes idle OR conversation hash change)

3. Check Neo4j:
   MATCH (m:Memory) RETURN m.content, m.memory_type, m.confidence

4. Expected: 3+ new memories with types: preference, technical_context
```

**Acceptance Criteria**:
- ✅ Memories are automatically extracted after conversation boundaries
- ✅ Extracted memories appear in Neo4j with embeddings
- ✅ Confidence scoring works correctly (>0.4 threshold)
- ✅ Memory types are correctly classified
- ✅ Extraction failures don't break chat flow

**Estimated Effort**: 4-6 hours
**Priority**: P0 - CRITICAL

---

### Phase 2: Verify Memory Retrieval Integration (HIGH) 🔍

**Objective**: Ensure memories are retrieved and injected into chat context

**Current State**: ✅ Already implemented in `chat.py:503-562`

**Tasks**:
1. **Verify retrieval is working with test memories**
   - Add 3-5 test memories manually to Neo4j
   - Ensure they have embeddings
   - Test retrieval with relevant queries

2. **Debug why existing memory isn't retrieved**
   - One preference memory exists: "I prefer using Docker Swarm"
   - Retrieval returns 0 results
   - Possible issues:
     - Missing embedding (check: `m.embedding IS NOT NULL`)
     - Similarity threshold too high (currently 0.65)
     - Index not configured correctly

3. **Tune retrieval parameters**
   ```python
   query = RetrievalQuery(
       query_text=user_message,
       top_k=5,
       min_similarity=0.65,  # May need to lower
       min_confidence=0.4,
   )
   ```

4. **Test hybrid retrieval mode**
   - Send requests with `metadata: {"hybrid_mode": true}`
   - Verify vector + BM25 + graph retrieval works
   - Confirm source attribution in context

**Testing**:
```bash
# 1. Add test memory with embedding
docker exec haia-neo4j cypher-shell -u neo4j -p haia_neo4j_secure_2024 "
CREATE (m:Memory {
  memory_id: 'test-123',
  content: 'Vincent prefers Docker Swarm over Kubernetes',
  memory_type: 'preference',
  confidence: 0.95,
  created_at: datetime(),
  has_embedding: true
})
"

# 2. Generate embedding via HAIA embedding service
# (implementation needed in backfill worker)

# 3. Test retrieval
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic:claude-haiku-4-5-20251001",
    "messages": [{"role": "user", "content": "What container orchestration do I prefer?"}]
  }'

# Expected: HAIA responds "You prefer Docker Swarm over Kubernetes"
```

**Acceptance Criteria**:
- ✅ Test memories with embeddings are retrieved successfully
- ✅ Retrieved memories appear in agent context
- ✅ Agent responses reference memory content naturally
- ✅ Hybrid retrieval mode works with source attribution
- ✅ Retrieval latency <100ms P95

**Estimated Effort**: 2-3 hours
**Priority**: P1 - HIGH

---

### Phase 3: Redesign System Prompt (MEDIUM) 🎨

**Objective**: Create a more versatile, memory-driven system prompt

**Current Issues**:
1. Too much pre-loaded homelab knowledge
2. Lists specific technologies and infrastructure
3. Should let expertise emerge from memories + tools

**Proposed New Design**:

```markdown
# Base System Prompt (Versatile Companion)

You are Haia, Vincent's personal AI assistant and companion.

## Core Personality
- Professional yet warm, competent with subtle charm
- Versatile across many domains - adapt to the conversation
- Natural, conversational - speak like a real person
- Subtle dry wit when appropriate, never forced
- Genuinely helpful because that's what companions do

## Communication Style
- Match detail level to question complexity
- Be conversational and concise for casual questions
- Provide thorough explanations for complex topics
- Use "Vincent" naturally for greetings and important matters

## Safety Protocol
- **ALWAYS confirm** before destructive operations
- Read-only operations need no confirmation
- For critical system changes, emphasize risks
- Explain what will happen before asking for confirmation

## Adaptive Expertise
Your knowledge spans many domains. Let the conversation guide where you focus:
- Technical topics: Provide clear examples and step-by-step guidance
- General questions: Engage conversationally with relevant context
- Complex problems: Offer thorough analysis with trade-offs

You have access to:
- Full conversation history for context
- Past conversation memories to personalize responses
- Specialized tools when relevant (web search, infrastructure APIs)

## How to Use Memory
When you have context from past conversations:
- Reference it naturally without explicitly mentioning "memory"
- Use it to inform suggestions and understand preferences
- Ask for clarification if past context seems contradictory

## Important Notes
- Admit knowledge gaps gracefully
- Ask clarifying questions rather than assume
- Suggest improvements when relevant, don't overwhelm
- During critical issues, stay focused - charm can wait
```

**What's Removed**:
- ❌ Explicit "homelab infrastructure assistant" label
- ❌ Detailed list of homelab technologies
- ❌ Specific infrastructure details (zigbee2mqtt, LXC numbers, etc.)

**What Emerges from Context**:
- ✅ Available tools (Proxmox client, Docker client, Home Assistant client)
- ✅ Memory content ("Vincent runs a 3-node Proxmox cluster")
- ✅ Conversation flow (user asks about Ceph → homelab context activated)

**Implementation**:
1. Update `DEFAULT_SYSTEM_PROMPT` in `src/haia/agent.py`
2. Update `HAIA_SYSTEM_PROMPT` in `.env` (for production)
3. Remove homelab profile loading (or make it memory-based)
4. Test with diverse conversation types:
   - Homelab questions → should still provide expert help
   - General questions → should be conversational, not homelab-focused
   - French conversations → should adapt naturally

**Testing Scenarios**:
```
# Test 1: General introduction (should be broad)
User: "Hello, who are you?"
Expected: "I'm Haia, your personal AI assistant and companion."

# Test 2: Technical question (homelab expertise emerges)
User: "Help me configure Ceph replication"
Expected: [Uses memory of 3-node cluster, provides expert guidance]

# Test 3: Non-technical (should adapt)
User: "Recommend a good whisky for a gift"
Expected: [Conversational, helpful, no mention of infrastructure]

# Test 4: Memory integration
User: "What container platform should I use?"
Expected: [References memory: "You mentioned preferring Docker Swarm"]
```

**Acceptance Criteria**:
- ✅ HAIA introduces itself broadly, not as "homelab specialist"
- ✅ Homelab expertise emerges naturally from context
- ✅ Responds appropriately to non-technical topics
- ✅ Uses memory content to inform responses
- ✅ Maintains personality and charm across all domains

**Estimated Effort**: 3-4 hours (including testing)
**Priority**: P2 - MEDIUM

---

## Implementation Order

### Sprint 1: Core Memory Functionality (CRITICAL)
**Duration**: 1-2 days
**Goal**: Get memory extraction and retrieval working

1. ✅ Phase 1, Task 1: Implement extraction trigger in chat endpoint (4h)
2. ✅ Phase 1, Task 2: Verify extraction service configuration (1h)
3. ✅ Phase 1, Task 3: Integrate transcript storage (2h)
4. ✅ Phase 1, Task 4: Add error handling (1h)
5. ✅ Phase 2, Task 1-2: Verify retrieval with test memories (2h)
6. ✅ Phase 2, Task 3: Tune retrieval parameters (1h)

**Total Estimated Effort**: 11 hours
**Deliverable**: Memory system fully functional (extraction + retrieval)

### Sprint 2: System Prompt Redesign (POLISH)
**Duration**: 0.5-1 day
**Goal**: Make HAIA more versatile and memory-driven

1. ✅ Phase 3: Redesign base system prompt (1h)
2. ✅ Phase 3: Update agent.py and .env configuration (1h)
3. ✅ Phase 3: Test across diverse conversation types (2h)

**Total Estimated Effort**: 4 hours
**Deliverable**: Versatile system prompt that adapts via memory

---

## Testing Strategy

### Unit Tests
```python
# test_memory_extraction_integration.py
async def test_extraction_triggered_on_boundary():
    """Verify extraction runs after boundary detection"""

async def test_memories_stored_to_neo4j():
    """Verify extracted memories are persisted"""

async def test_extraction_error_handling():
    """Verify graceful degradation on extraction failure"""
```

### Integration Tests
```python
# test_e2e_memory_lifecycle.py
async def test_conversation_to_memory_to_retrieval():
    """End-to-end: conversation → boundary → extract → store → retrieve"""

async def test_memory_context_injection():
    """Verify memories appear in agent context"""

async def test_hybrid_retrieval_with_memories():
    """Verify hybrid mode retrieves memories correctly"""
```

### Manual Testing
1. **Conversation Flow**:
   - Have multi-turn conversation with preferences
   - Wait for boundary (or trigger manually)
   - Check Neo4j for new memories
   - Ask question that should trigger memory retrieval
   - Verify agent uses memory context

2. **System Prompt**:
   - Test broad introduction
   - Test technical homelab question
   - Test non-technical question
   - Verify appropriate adaptation in each case

---

## Success Metrics

### Memory Extraction
- [ ] 90%+ of conversations result in extracted memories
- [ ] Average 3-5 memories extracted per conversation
- [ ] <5% extraction failure rate
- [ ] All memory types represented (preference, technical_context, decision, etc.)

### Memory Retrieval
- [ ] Relevant memories retrieved in 80%+ of cases
- [ ] P95 retrieval latency <100ms
- [ ] Memory context improves response quality (subjective evaluation)
- [ ] No false positives (irrelevant memories)

### System Prompt
- [ ] HAIA doesn't self-identify as "homelab specialist" unless contextual
- [ ] Successfully answers diverse questions (not just homelab)
- [ ] Homelab expertise emerges naturally when needed
- [ ] User feedback: "feels more like a companion, less like a tool"

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Extraction service failures break chat | HIGH | MEDIUM | Graceful degradation - log error, continue without memories |
| Boundary detection triggers too frequently | MEDIUM | LOW | Tune idle threshold, require multiple signals |
| Retrieved memories are irrelevant | MEDIUM | MEDIUM | Lower similarity threshold, improve ranking algorithm |
| System prompt change degrades homelab expertise | MEDIUM | LOW | Extensive testing, keep memories rich with technical context |
| Extraction latency impacts user experience | LOW | LOW | Run extraction async, don't block response |

---

## Dependencies

### Internal
- `ConversationTracker` - boundary detection (existing, working)
- `ExtractionService` - memory extraction (existing, needs integration)
- `RetrievalService` - semantic search (existing, working)
- `MemoryStorageService` - Neo4j persistence (existing, working)

### External
- Ollama embedding service (nomic-embed-text) - **working**
- Neo4j database with vector index - **working**
- Anthropic API (for extraction LLM) - **configured**

### Configuration
- `EXTRACTION_MODEL` - Model for extraction (default: HAIA_MODEL)
- `EXTRACTION_MIN_CONFIDENCE` - Threshold (default: 0.4)
- `SEARCH_ENABLED` - Web search toggle (already working)
- `HAIA_SYSTEM_PROMPT` - Base prompt (needs update)

---

## Rollback Plan

If critical issues arise:

1. **Memory Extraction Issues**:
   ```python
   # Add feature flag
   MEMORY_EXTRACTION_ENABLED=false

   # Graceful degradation in chat.py
   if settings.memory_extraction_enabled and boundary_result.detected:
       await extract_memories(...)
   ```

2. **Retrieval Issues**:
   ```python
   # Disable memory retrieval temporarily
   MEMORY_RETRIEVAL_ENABLED=false

   # System continues without memory context
   ```

3. **System Prompt Issues**:
   ```bash
   # Revert to previous HAIA_SYSTEM_PROMPT in .env
   git checkout HEAD~1 -- .env
   docker compose restart haia
   ```

---

## Appendix: Technical Details

### Memory Extraction Flow
```
┌─────────────────┐
│ User Message    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Boundary Check  │
│ (idle + hash)   │
└────────┬────────┘
         │ boundary detected
         ▼
┌─────────────────┐
│ Load Transcript │
│ from Tracker    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract Memories│
│ (LLM + scoring) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Store to Neo4j  │
│ with embeddings │
└─────────────────┘
```

### Memory Retrieval Flow
```
┌─────────────────┐
│ User Query      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Retrieve (5)    │
│ min_sim=0.65    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Format Context  │
│ as NL markdown  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Inject to Agent │
│ as system msg   │
└─────────────────┘
```

### Database Schema (Memory Nodes)
```cypher
CREATE (m:Memory {
  memory_id: <uuid>,
  content: <string>,
  memory_type: <enum: preference|technical_context|decision|personal_fact|correction>,
  confidence: <float 0.0-1.0>,
  created_at: <datetime>,
  source_conversation_id: <string>,
  embedding: <vector[768]>,  # nomic-embed-text
  has_embedding: <boolean>,
  access_count: <int>,
  last_accessed_at: <datetime>
})
```

---

## Questions for User

Before proceeding with implementation:

1. **Priority Confirmation**: Agree with P0 (extraction) → P1 (retrieval tuning) → P2 (prompt redesign) order?

2. **System Prompt Direction**: Confirm removing explicit homelab focus from base prompt, letting it emerge from memories?

3. **Testing Approach**: Prefer automated tests first, or manual testing to validate behavior?

4. **Rollout Strategy**: Implement all at once, or phase 1 first then evaluate?

5. **Performance Targets**: Are the P95 latency targets acceptable (<100ms retrieval, <1s extraction)?

---

## Conclusion

The memory system architecture is sound - all components exist and are initialized correctly. The critical gap is **triggering memory extraction after conversation boundaries**. Once this is fixed and tested, HAIA will have a fully functional memory system that enables personalized, context-aware conversations.

The system prompt redesign is a secondary polish item that will make HAIA feel more like a versatile companion rather than a specialized homelab tool. Combined with working memory, this will create the intended user experience: an AI that learns about you organically and adapts naturally to your needs.

**Recommended Action**: Proceed with Sprint 1 (memory functionality) immediately, then evaluate Sprint 2 (prompt redesign) based on user feedback.
