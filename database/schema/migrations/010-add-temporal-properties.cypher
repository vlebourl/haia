// Migration 010: Add Bi-Temporal Properties to Memory Nodes
// Created: 2025-12-10
// Purpose: Add temporal tracking properties for memory validity periods and superseding chains
// Session: 10 - Hybrid Temporal Memory System
// Phase: 1 - Temporal Foundation & BM25

// =============================================================================
// BI-TEMPORAL PROPERTIES
// =============================================================================
// Tracking both:
// - Event time (when information was valid in the real world)
// - Ingestion time (when we learned about it)

// Add valid_from property (when this memory became true)
// Default: Use created_at for existing memories
MATCH (m:Memory)
WHERE m.valid_from IS NULL
SET m.valid_from = COALESCE(m.created_at, datetime())
RETURN count(m) AS memories_with_valid_from;

// Add valid_until property (when this memory stopped being true)
// NULL means currently valid
MATCH (m:Memory)
WHERE m.valid_until IS NULL
SET m.valid_until = NULL  // Explicitly set to NULL (currently valid)
RETURN count(m) AS memories_with_valid_until;

// Add learned_at property (when we ingested this information)
// Default: Use created_at for existing memories
MATCH (m:Memory)
WHERE m.learned_at IS NULL
SET m.learned_at = COALESCE(m.created_at, datetime())
RETURN count(m) AS memories_with_learned_at;

// =============================================================================
// SUPERSEDING CHAIN PROPERTIES
// =============================================================================
// Track which memories supersede/are superseded by others

// Add superseded_at property (timestamp when this memory was superseded)
// NULL means not superseded
MATCH (m:Memory)
WHERE m.superseded_at IS NULL
SET m.superseded_at = NULL  // Explicitly set to NULL (not superseded)
RETURN count(m) AS memories_with_superseded_at;

// Add superseded_by property (ID of memory that supersedes this one)
// NULL means not superseded
MATCH (m:Memory)
WHERE m.superseded_by IS NULL
SET m.superseded_by = NULL  // Explicitly set to NULL (not superseded)
RETURN count(m) AS memories_with_superseded_by;

// =============================================================================
// VALIDATION QUERIES
// =============================================================================

// Verify all Memory nodes have temporal properties
MATCH (m:Memory)
RETURN
    count(m) AS total_memories,
    count(m.valid_from) AS has_valid_from,
    count(m.learned_at) AS has_learned_at,
    sum(CASE WHEN m.valid_until IS NOT NULL THEN 1 ELSE 0 END) AS has_valid_until_set,
    sum(CASE WHEN m.superseded_by IS NOT NULL THEN 1 ELSE 0 END) AS has_superseded_by_set;

// Report on temporal state
MATCH (m:Memory)
RETURN
    sum(CASE WHEN m.valid_until IS NULL THEN 1 ELSE 0 END) AS currently_valid_memories,
    sum(CASE WHEN m.valid_until IS NOT NULL THEN 1 ELSE 0 END) AS superseded_memories,
    sum(CASE WHEN m.superseded_by IS NOT NULL THEN 1 ELSE 0 END) AS memories_with_superseding_chain;

// =============================================================================
// MIGRATION NOTES
// =============================================================================
// - All existing memories are marked as valid from their creation date
// - All existing memories are marked as currently valid (valid_until = NULL)
// - All existing memories are marked as learned at creation time
// - No superseding relationships exist for existing memories
// - Future memories will have these properties set at creation time
// =============================================================================
