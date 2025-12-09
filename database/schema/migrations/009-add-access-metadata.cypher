// Migration 009: Add Access Tracking Metadata to Memory Nodes
// Feature: Context Optimization (Session 9)
// Date: 2025-12-09
// Purpose: Add last_accessed and access_count properties to all Memory nodes
//          for usage-based relevance re-ranking

// ============================================================================
// Step 1: Add access tracking properties to existing Memory nodes
// ============================================================================

// Initialize all existing Memory nodes with access tracking properties
MATCH (m:Memory)
WHERE m.last_accessed IS NULL OR m.access_count IS NULL
SET m.last_accessed = NULL,
    m.access_count = 0
RETURN count(m) as updated_memory_count;

// ============================================================================
// Step 2: Create index on last_accessed for efficient queries (optional optimization)
// ============================================================================

// Create index for efficient last_accessed queries (used by Ranker service)
CREATE INDEX memory_last_accessed IF NOT EXISTS
FOR (m:Memory) ON (m.last_accessed);

// Create index for efficient access_count queries (used by frequency scoring)
CREATE INDEX memory_access_count IF NOT EXISTS
FOR (m:Memory) ON (m.access_count);

// ============================================================================
// Step 3: Verify migration
// ============================================================================

// Count Memory nodes with access tracking properties
MATCH (m:Memory)
RETURN
    count(m) as total_memories,
    count(m.access_count) as memories_with_access_count,
    count(m.last_accessed) as memories_with_last_accessed_set;

// Sample a few Memory nodes to verify structure
MATCH (m:Memory)
RETURN
    m.memory_id,
    m.memory_type,
    m.access_count,
    m.last_accessed
LIMIT 5;

// ============================================================================
// Migration Complete
// ============================================================================

// Expected results:
// - All Memory nodes have access_count = 0 (integer)
// - All Memory nodes have last_accessed = NULL (initially)
// - Indexes created on last_accessed and access_count for performance
// - No data loss or corruption

// Next steps:
// - Update Memory Pydantic model with new properties
// - Update ExtractedMemory model with access tracking fields
// - Implement AccessTracker service for tracking updates
// - Integrate Ranker service for multi-factor relevance scoring
