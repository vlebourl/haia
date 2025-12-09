-- ============================================================================
-- Neo4j Vector Index Creation for HAIA Memory Retrieval System
-- Feature: 008-memory-retrieval
-- Purpose: Create vector indexes for semantic search on Memory nodes
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Memory Embeddings Vector Index (Primary)
-- ----------------------------------------------------------------------------

-- Create vector index for Memory nodes (768 dimensions, cosine similarity)
CREATE VECTOR INDEX memory_embeddings IF NOT EXISTS
FOR (m:Memory) ON (m.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine',
  `vector.quantization.enable`: true,
  `vector.hnsw.m`: 16,
  `vector.hnsw.ef_construction`: 100
}};

-- ----------------------------------------------------------------------------
-- 2. Additional Vector Indexes for Related Node Types
-- ----------------------------------------------------------------------------

-- Interest embeddings (for semantic interest matching)
CREATE VECTOR INDEX interest_embeddings IF NOT EXISTS
FOR (i:Interest) ON (i.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine',
  `vector.quantization.enable`: true
}};

-- TechPreference embeddings (for technical preference matching)
CREATE VECTOR INDEX tech_pref_embeddings IF NOT EXISTS
FOR (tp:TechPreference) ON (tp.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine',
  `vector.quantization.enable`: true
}};

-- Fact embeddings (for factual information retrieval)
CREATE VECTOR INDEX fact_embeddings IF NOT EXISTS
FOR (f:Fact) ON (f.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine',
  `vector.quantization.enable`: true
}};

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- List all vector indexes
SHOW INDEXES
WHERE type = 'VECTOR'
YIELD name, labelsOrTypes, properties, options, state, populationPercent
RETURN name, labelsOrTypes, properties, options, state, populationPercent;

-- Check memory_embeddings index status
SHOW INDEXES
WHERE name = 'memory_embeddings'
YIELD name, state, populationPercent
RETURN name, state, populationPercent;

-- ============================================================================
-- 3. Backfill Progress Tracking (Session 8 - User Story 2)
-- ============================================================================

-- Create/update backfill progress tracking node
-- Usage: Track embedding generation progress for existing memories
MERGE (p:EmbeddingBackfillProgress {id: 'main'})
ON CREATE SET
  p.started_at = datetime(),
  p.last_updated_at = datetime(),
  p.total_memories = 0,
  p.processed_memories = 0,
  p.failed_memories = 0,
  p.status = 'in_progress'
ON MATCH SET
  p.last_updated_at = datetime()
RETURN p;

-- Query memories without embeddings (used by backfill worker)
-- Returns batch of memories that need embedding generation
-- MATCH (m:Memory)
-- WHERE m.has_embedding IS NULL OR m.has_embedding = false
-- RETURN m.id as memory_id, m.content as content, m.type as memory_type
-- LIMIT 25;

-- Update backfill progress after batch processing
-- Usage: Call after each batch completes
-- MATCH (p:EmbeddingBackfillProgress {id: 'main'})
-- SET
--   p.processed_memories = p.processed_memories + $batch_processed,
--   p.failed_memories = p.failed_memories + $batch_failed,
--   p.last_updated_at = datetime()
-- RETURN p;

-- Get backfill progress statistics
MATCH (p:EmbeddingBackfillProgress {id: 'main'})
OPTIONAL MATCH (m:Memory)
RETURN
  p.started_at as started_at,
  p.last_updated_at as last_updated_at,
  p.processed_memories as processed,
  p.failed_memories as failed,
  COUNT(m) as total_memories,
  COUNT(CASE WHEN m.has_embedding = true THEN 1 END) as memories_with_embeddings,
  COUNT(CASE WHEN m.has_embedding IS NULL OR m.has_embedding = false THEN 1 END) as memories_without_embeddings;

-- Mark backfill as complete
-- Usage: Call when no more memories need processing
-- MATCH (p:EmbeddingBackfillProgress {id: 'main'})
-- SET
--   p.status = 'completed',
--   p.completed_at = datetime(),
--   p.last_updated_at = datetime()
-- RETURN p;

-- ============================================================================
-- Usage Notes
-- ============================================================================
--
-- 1. Run this script via cypher-shell or Neo4j Browser after Neo4j startup
-- 2. Vector indexes are created asynchronously - check state with SHOW INDEXES
-- 3. Expected states: POPULATING → ONLINE
-- 4. Quantization reduces memory usage by ~4x with minimal accuracy loss
-- 5. HNSW parameters:
--    - m=16: Trade-off between speed and accuracy (default)
--    - ef_construction=100: Index build quality (higher = better but slower)
-- 6. Backfill progress tracking:
--    - EmbeddingBackfillProgress node tracks batch processing progress
--    - Query memories_without_embeddings to get next batch
--    - Update progress after each batch completes
--    - Check progress statistics to monitor backfill status
--
-- ============================================================================
