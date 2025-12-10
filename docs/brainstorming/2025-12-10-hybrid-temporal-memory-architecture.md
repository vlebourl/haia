# Brainstorming Session: Hybrid Temporal Memory Architecture

**Date:** December 10, 2025
**Facilitator:** Claude (Scrum Master Agent)
**Participants:** User (Product Owner/Developer)
**Duration:** ~2 hours
**Session Type:** Feature Design & Architecture Planning

---

## Executive Summary

Brainstorming session to transform HAIA's memory system from hardcoded categories to a **self-organizing, hybrid temporal architecture**. The user identified that the current system has extensive hardcoding that limits adaptability and prevents the system from evolving naturally. Research into industry best practices (Mem0, Graphiti/Zep) revealed proven patterns for dynamic, LLM-driven memory systems.

**Outcome:** 5-phase implementation plan (6-10 weeks) that eliminates all hardcoded categories and implements self-organizing memory with bi-temporal tracking, hybrid retrieval, and automatic consolidation.

---

## Problem Statement

### User's Vision
"I want HAIA to learn who I am, what I do, what I work with, etc. - self-evolving, self-categorizing, self-organizing."

### Issues Identified
Through code analysis, we discovered **extensive hardcoding** across the memory system:

1. **5 hardcoded memory categories** (preference, personal_fact, technical_context, decision, correction)
2. **7 hardcoded Neo4j node types** (Person, Interest, Infrastructure, TechPreference, Fact, Decision, Conversation)
3. **9 hardcoded relationship types** (INTERESTED_IN, OWNS, PREFERS, etc.)
4. **15+ hardcoded numeric thresholds** (confidence, similarity, decay rates)
5. **14 English-only pattern detection phrases** (correction indicators, stopwords)
6. **Hardcoded type weights** for relevance scoring

**Impact:** Cannot adapt to new domains, user vocabulary, or evolving needs without code changes in 5+ files.

---

## Research Phase

### Industry Best Practices (2025)

**Key Findings:**
- **Mem0**: 26% accuracy improvement, 90% token reduction, dynamic extraction, memory consolidation
- **Graphiti/Zep**: Temporally-aware graphs, no predefined entity types, <300ms latency
- **Neo4j MCP**: LLM-first intelligence, simple atomic operations, flexible properties
- **Self-organizing**: DBSCAN clustering for emergent themes without predefined categories

**Sources:**
- [Mem0: Building Production-Ready AI Agents](https://arxiv.org/abs/2504.19413)
- [Graphiti: Build Real-Time Knowledge Graphs](https://github.com/getzep/graphiti)
- [Neo4j Agent Memory MCP Server](https://github.com/knowall-ai/mcp-neo4j-agent-memory)

---

## User Priorities

1. **Accuracy** (Priority #1) - Most important
2. **Adaptability** (Priority #2) - Self-evolving, infinite extensibility
3. **Cost** (Priority #3) - Token efficiency
4. **Speed** (Priority #4) - Sub-500ms acceptable

**User Decisions:**
- ✅ Timeline: "Take as long as needed" - focus on quality over speed
- ✅ Scope: Revolutionary change - "biggest changes for best results"
- ✅ Migration: No production data, clean implementation possible
- ✅ APOC Plugin: Approved for graph traversal
- ✅ LLM Costs: ~$0.01/memory for relationship inference acceptable

---

## Solution Architecture

### Target State
**Hybrid Temporal Memory System** combining:
- **Graphiti-style temporal graphs**: Bi-temporal tracking, dynamic schema
- **Mem0-style consolidation**: Short-term → long-term → archived tiers
- **LLM-first intelligence**: No hardcoded categories, dynamic extraction
- **Self-organization**: DBSCAN clustering for emergent themes

### Key Capabilities
1. **LLM-Driven Entity Extraction**: Infinite dynamic types (no enum constraints)
2. **Bi-Temporal Tracking**: valid_from/valid_until, learned_at timestamps
3. **Hybrid Retrieval**: Vector + BM25 + Graph traversal (RRF merged)
4. **Memory Consolidation**: Automatic promotion/archival based on access patterns
5. **Self-Organization**: Emergent clustering, LLM-generated theme summaries

---

## Implementation Plan

### Phase 1: Temporal Foundation & BM25 (3-4 days)
- Add bi-temporal properties to Memory nodes
- Implement BM25 full-text search index
- Create temporal indexes for time-based queries

### Phase 2: Dynamic Schema - LLM Entity Extraction (8-10 days)
- Remove MemoryCategory enum (no hardcoded types!)
- LLM-driven relationship inference
- Temporal conflict resolution (superseding logic)
- Remove all type-specific hardcoded weights

### Phase 3: Hybrid Retrieval (5-6 days)
- Graph traversal via APOC (2-hop expansion)
- Reciprocal Rank Fusion (RRF) merger
- Parallel hybrid retrieval (Vector + BM25 + Graph)

### Phase 4: Memory Consolidation (5-6 days)
- Memory tiers: short-term → long-term → archived
- Decay algorithms (exponential, access-based)
- Priority scoring (no hardcoded weights!)
- Daily scheduled consolidation job

### Phase 5: Self-Organization (5-6 days)
- DBSCAN clustering on embeddings
- LLM-generated cluster summaries
- Discovery API for emergent themes
- Theme-based retrieval

**Total Effort:** 6-10 weeks (42 story points)

---

## Key Decisions Made

### Technical Decisions
1. **Hybrid Architecture**: Combine Graphiti + Mem0 patterns (not either/or)
2. **LLM-First**: All categorization/relationship inference via LLM
3. **Neo4j + APOC**: Keep existing Neo4j, add APOC for graph traversal
4. **BM25 via Full-Text Index**: Start with Neo4j native, evaluate rank-bm25 later
5. **All Features Enabled**: No gradual rollout needed (no production data)

### Architecture Decisions
1. **No Hardcoded Categories**: Remove all Literal types, enums
2. **Bi-Temporal Model**: Track event time vs ingestion time separately
3. **RRF Merging**: Combine vector (1.0×) + BM25 (0.8×) + graph (0.6×) with k=60
4. **3-Tier Memory**: Short-term (<7 days), long-term (promoted), archived (decayed)
5. **DBSCAN Clustering**: eps=0.15, min_samples=3, cosine metric

### Process Decisions
1. **Quality Over Speed**: Take 6-10 weeks, no rushing
2. **Clean Implementation**: No backward compatibility, production-ready from day one
3. **Feature Flags Removed**: All features enabled by default (simplified)
4. **Iterative Review**: Demo each phase before proceeding to next

---

## Success Metrics

### Accuracy (Priority #1)
- Phase 2: LLM-generated types cover 95%+ of use cases
- Phase 3: RRF improves recall by 20%+ vs vector-only
- Phase 5: Silhouette score >0.5 for clustering quality

### Adaptability (Priority #2)
- Phase 2: Zero hardcoded categories (100% LLM-driven)
- Phase 4: 70%+ memories correctly promoted/archived
- Phase 5: Emergent themes match user mental model

### Cost (Priority #3)
- Phase 2: Relationship inference: ~$0.01 per memory
- Phase 5: Clustering: ~$0.05 per run (500 memories)

### Speed (Priority #4)
- Phase 3: Hybrid retrieval <500ms p95 latency
- Phase 4: Daily consolidation <5 minutes for 10k memories
- Phase 5: Discovery API <10s for 500 memories

---

## Risks & Mitigation

### Phase 2: Dynamic Schema (Medium Risk)
**Risk:** LLM may generate inconsistent entity types
**Mitigation:** Post-processing normalization, high confidence threshold (0.6+), quality monitoring

### Phase 3: Hybrid Retrieval (Medium Risk)
**Risk:** APOC dependency, increased latency
**Mitigation:** Graceful fallback if APOC missing, parallel async execution, latency monitoring

### Phase 4: Memory Consolidation (Medium Risk)
**Risk:** Aggressive archival may lose useful memories
**Mitigation:** Conservative thresholds (0.7 promote, 0.2 archive), manual review dashboard

---

## Dependencies

### External Dependencies
1. **Neo4j 5.11+** - Already present ✓
2. **APOC plugin** - Required for Phase 3
3. **scikit-learn** - Required for Phase 5

### Installation
```bash
uv add scikit-learn numpy
# docker-compose.yml: NEO4J_PLUGINS: '["apoc"]'
```

---

## Action Items

### Immediate (Week 1)
- [ ] Install APOC plugin in Neo4j (docker-compose change)
- [ ] Install scikit-learn via uv
- [ ] Review and approve implementation plan
- [ ] Create Phase 1 branch: `feature/temporal-foundation`

### Phase 1 (Week 1-2)
- [ ] Write temporal property migration (010-add-temporal-properties.cypher)
- [ ] Write BM25 full-text index migration (011-create-bm25-fulltext-index.cypher)
- [ ] Implement `search_memories_bm25()` in Neo4jService
- [ ] Update MemoryStorageService to track temporal fields
- [ ] Write unit + integration tests

### Phase 2 (Week 2-5)
- [ ] Remove MemoryCategory enum from extraction/models.py
- [ ] Remove Literal constraints (line 77-79)
- [ ] Write new dynamic extraction prompt
- [ ] Implement RelationshipInferenceService
- [ ] Implement TemporalManager
- [ ] Remove hardcoded id_field_map from Neo4jService
- [ ] Remove type-specific weight configs
- [ ] Write comprehensive tests

### Phase 3 (Week 5-7)
- [ ] Implement RRFMerger class
- [ ] Add `traverse_related_memories()` to Neo4jService
- [ ] Add `retrieve_hybrid()` to RetrievalService
- [ ] Update docker-compose with APOC
- [ ] Add configuration for hybrid retrieval
- [ ] Performance testing (<500ms latency)

### Phase 4 (Week 7-8)
- [ ] Implement decay algorithms (exponential, access-based)
- [ ] Implement MemoryConsolidator service
- [ ] Add consolidation job to scheduler
- [ ] Write tier migration (012-add-memory-tiers.cypher)
- [ ] Test promotion/archival logic

### Phase 5 (Week 8-9)
- [ ] Implement DBSCANClusterer
- [ ] Implement ClusterSummarizer (LLM-based)
- [ ] Create discovery API endpoints
- [ ] Add theme-based retrieval
- [ ] Test clustering quality (silhouette score)

### Final (Week 9-10)
- [ ] Integration testing across all phases
- [ ] Performance validation
- [ ] Documentation updates
- [ ] User acceptance testing

---

## Resources & References

### Research Papers
- [Mem0: Building Production-Ready AI Agents](https://arxiv.org/abs/2504.19413)
- [Zep: Temporal Knowledge Graph Architecture](https://arxiv.org/abs/2501.13956)

### GitHub Repositories
- [Graphiti by Zep AI](https://github.com/getzep/graphiti)
- [Mem0 Universal Memory Layer](https://github.com/mem0ai/mem0)
- [Neo4j Agent Memory MCP](https://github.com/knowall-ai/mcp-neo4j-agent-memory)

### Documentation
- [Building AI Agents That Actually Remember (2025)](https://medium.com/@nomannayeem/building-ai-agents-that-actually-remember-a-developers-guide-to-memory-management-in-2025-062fd0be80a1)
- [Neo4j Graphiti Blog Post](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)

### Implementation Plan
**Detailed Plan:** `/home/vlb/.claude/plans/hazy-tumbling-castle.md`

---

## Session Notes

### Key Insights
1. **Hardcoding is pervasive**: Not just memory categories, but relationships, thresholds, patterns across entire system
2. **Industry has solved this**: Mem0 and Graphiti provide proven architectures for dynamic, self-organizing memory
3. **Temporal awareness is critical**: Bi-temporal tracking enables handling contradictions, superseding, and point-in-time queries
4. **No production data = clean slate**: Can implement best practices from day one without migration complexity

### Challenges Discussed
1. **LLM Consistency**: How to ensure LLM generates consistent entity types? → Post-processing normalization, confidence thresholds
2. **Performance**: Will dynamic schema slow queries? → Proper indexing, hybrid retrieval parallelization
3. **Cost**: What's the LLM cost impact? → ~$0.01/memory for relationship inference (acceptable)
4. **Testing**: How to validate LLM generates good types? → 95%+ coverage target, manual review, quality metrics

### Design Trade-offs
1. **Mem0 vs Graphiti**: Chose hybrid approach combining both patterns
2. **BM25 Implementation**: Start with Neo4j full-text (native), can switch to rank-bm25 if needed
3. **Feature Flags**: Removed (not needed without production data)
4. **Timeline**: 6-10 weeks prioritizing quality over speed

---

## Follow-up Questions

None - all key decisions made during session.

---

## Appendix: Code Locations

### Files to Modify
- `/home/vlb/Python/haia/src/haia/extraction/models.py` - Remove Literal constraints
- `/home/vlb/Python/haia/src/haia/extraction/prompts.py` - Dynamic extraction prompt
- `/home/vlb/Python/haia/src/haia/services/neo4j.py` - Add BM25, graph traversal, remove hardcoding
- `/home/vlb/Python/haia/src/haia/services/memory_storage.py` - Temporal tracking
- `/home/vlb/Python/haia/src/haia/embedding/retrieval_service.py` - Hybrid retrieval
- `/home/vlb/Python/haia/src/haia/config.py` - Remove type-specific configs, add new configs
- `/home/vlb/Python/haia/deployment/docker-compose.yml` - Add APOC plugin

### Files to Create
- `/home/vlb/Python/haia/src/haia/services/relationship_inference.py`
- `/home/vlb/Python/haia/src/haia/services/temporal_manager.py`
- `/home/vlb/Python/haia/src/haia/retrieval/rrf_merger.py`
- `/home/vlb/Python/haia/src/haia/retrieval/models.py`
- `/home/vlb/Python/haia/src/haia/consolidation/models.py`
- `/home/vlb/Python/haia/src/haia/consolidation/decay.py`
- `/home/vlb/Python/haia/src/haia/consolidation/consolidator.py`
- `/home/vlb/Python/haia/src/haia/clustering/dbscan_clusterer.py`
- `/home/vlb/Python/haia/src/haia/clustering/cluster_summarizer.py`
- `/home/vlb/Python/haia/src/haia/api/routes/discovery.py`

### Database Migrations
- `/home/vlb/Python/haia/database/schema/migrations/010-add-temporal-properties.cypher`
- `/home/vlb/Python/haia/database/schema/migrations/011-create-bm25-fulltext-index.cypher`
- `/home/vlb/Python/haia/database/schema/migrations/012-add-memory-tiers.cypher`

---

**Session Completed:** December 10, 2025
**Status:** ✅ Plan Approved - Ready for Implementation
**Next Session:** Phase 1 Kickoff (Week 1)
