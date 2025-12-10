// Migration 011: Create BM25 Full-Text Index and Temporal Indexes
// Created: 2025-12-10
// Purpose: Add full-text search capability and temporal query indexes
// Session: 10 - Hybrid Temporal Memory System
// Phase: 1 - Temporal Foundation & BM25

// =============================================================================
// BM25 FULL-TEXT INDEX FOR KEYWORD SEARCH
// =============================================================================
// Neo4j full-text index uses BM25-like scoring for keyword relevance

// Create full-text index on Memory.content
// Index name: memory_content_fulltext
// Analyzer: english (stemming, stop words for English language)
CREATE FULLTEXT INDEX memory_content_fulltext IF NOT EXISTS
FOR (m:Memory)
ON EACH [m.content]
OPTIONS {
  indexConfig: {
    `fulltext.analyzer`: 'english',
    `fulltext.eventually_consistent`: false
  }
};

// Verify full-text index creation
SHOW INDEXES
YIELD name, type, labelsOrTypes, properties, options
WHERE name = 'memory_content_fulltext'
RETURN name, type, labelsOrTypes, properties, options;

// =============================================================================
// TEMPORAL QUERY INDEXES
// =============================================================================
// Speed up temporal filtering and range queries

// Index on valid_from for temporal range queries
CREATE INDEX memory_valid_from_index IF NOT EXISTS
FOR (m:Memory)
ON (m.valid_from);

// Index on valid_until for temporal range queries
CREATE INDEX memory_valid_until_index IF NOT EXISTS
FOR (m:Memory)
ON (m.valid_until);

// Index on learned_at for ingestion time queries
CREATE INDEX memory_learned_at_index IF NOT EXISTS
FOR (m:Memory)
ON (m.learned_at);

// Composite index for common temporal query pattern:
// "memories valid at time T" = WHERE valid_from <= T AND (valid_until IS NULL OR valid_until > T)
CREATE INDEX memory_temporal_range_index IF NOT EXISTS
FOR (m:Memory)
ON (m.valid_from, m.valid_until);

// Verify temporal indexes
SHOW INDEXES
YIELD name, type, labelsOrTypes, properties
WHERE name STARTS WITH 'memory_' AND type = 'RANGE'
RETURN name, type, labelsOrTypes, properties;

// =============================================================================
// INDEX VALIDATION AND STATISTICS
// =============================================================================

// Wait for indexes to come online (full-text indexes populate asynchronously)
// Check index state
SHOW INDEXES
YIELD name, state, populationPercent
WHERE name STARTS WITH 'memory_'
RETURN name, state, populationPercent
ORDER BY name;

// Count indexed memories
MATCH (m:Memory)
RETURN
    count(m) AS total_memories,
    count(m.content) AS memories_with_content,
    count(m.valid_from) AS memories_with_valid_from,
    count(m.valid_until) AS memories_with_valid_until,
    count(m.learned_at) AS memories_with_learned_at;

// Test full-text index with sample query (if memories exist)
// This verifies the index is working
CALL db.index.fulltext.queryNodes('memory_content_fulltext', 'docker')
YIELD node, score
RETURN node.memory_id AS memory_id, score, node.content AS content
LIMIT 5;

// =============================================================================
// PERFORMANCE NOTES
// =============================================================================
// - Full-text index uses ~10-20% extra storage for analyzed tokens
// - Temporal indexes are lightweight (datetime values, small overhead)
// - Composite index improves temporal range queries by 10-50x
// - Full-text queries typically <50ms for datasets under 100k memories
// - Eventually_consistent=false ensures immediate consistency (slight write overhead)
// =============================================================================

// =============================================================================
// USAGE EXAMPLES
// =============================================================================

// Example 1: BM25 keyword search
// CALL db.index.fulltext.queryNodes('memory_content_fulltext', 'docker container deployment')
// YIELD node, score
// RETURN node.memory_id, node.content, score
// ORDER BY score DESC
// LIMIT 10;

// Example 2: Temporal query - memories valid on specific date
// WITH datetime('2024-10-15T00:00:00Z') AS target_time
// MATCH (m:Memory)
// WHERE m.valid_from <= target_time
//   AND (m.valid_until IS NULL OR m.valid_until > target_time)
// RETURN m.memory_id, m.content, m.valid_from, m.valid_until;

// Example 3: Combined BM25 + temporal filtering
// WITH datetime('2024-10-15T00:00:00Z') AS target_time
// CALL db.index.fulltext.queryNodes('memory_content_fulltext', 'proxmox cluster')
// YIELD node, score
// WHERE node.valid_from <= target_time
//   AND (node.valid_until IS NULL OR node.valid_until > target_time)
// RETURN node.memory_id, node.content, score
// ORDER BY score DESC
// LIMIT 10;

// =============================================================================
