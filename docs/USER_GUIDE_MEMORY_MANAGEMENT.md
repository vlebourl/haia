# User Guide: Memory Management in HAIA

This guide explains how to configure and tune HAIA's memory consolidation and theme discovery systems.

## Table of Contents

1. [Memory Consolidation Configuration](#memory-consolidation-configuration)
2. [Theme Discovery Configuration](#theme-discovery-configuration)
3. [Using the Discovery API](#using-the-discovery-api)
4. [Tuning Guidelines](#tuning-guidelines)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Scenarios](#advanced-scenarios)

---

## Memory Consolidation Configuration

### Overview

Memory consolidation automatically manages your memory database by transitioning memories between three tiers:

```
SHORT_TERM (new, <7 days) → LONG_TERM (important) → ARCHIVED (low-priority)
```

This prevents unbounded database growth while preserving important memories.

### Basic Configuration

Add these settings to your `.env` file:

```env
# Enable/disable consolidation
CONSOLIDATION_ENABLED=true
CONSOLIDATION_SCHEDULE=0 3 * * *  # Cron: Daily at 3 AM

# Tier transition thresholds
CONSOLIDATION_PROMOTION_THRESHOLD=0.7   # Score >= 0.7: SHORT_TERM → LONG_TERM
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.2    # Score < 0.2: LONG_TERM → ARCHIVED

# Consolidation rules
CONSOLIDATION_SHORT_TERM_DAYS=7  # Minimum days before SHORT_TERM can be promoted

# Decay strategy
DECAY_STRATEGY=exponential  # exponential | ebbinghaus | linear
DECAY_BASE_HALF_LIFE_DAYS=43.3  # For exponential decay
```

### Understanding the Priority Score

The consolidation system calculates a priority score for each memory:

```
priority_score = (
    0.40 * access_frequency +  # How often retrieved (normalized by max)
    0.30 * recency_score +     # How recently accessed (with decay)
    0.30 * confidence          # Original extraction confidence
)
```

**Score ranges:**
- **0.7-1.0**: High priority → Promote to LONG_TERM
- **0.2-0.7**: Medium priority → Keep in current tier
- **0.0-0.2**: Low priority → Archive from LONG_TERM

### Choosing a Decay Strategy

#### ExponentialDecay (Recommended)

Adaptive half-life based on access patterns - frequently accessed memories decay slower.

```env
DECAY_STRATEGY=exponential
DECAY_BASE_HALF_LIFE_DAYS=43.3  # ≈6 weeks
```

**Use when:**
- You want memories to "earn" longer retention through frequent access
- Your conversation patterns are irregular

**Parameters:**
- Lower `DECAY_BASE_HALF_LIFE_DAYS` (e.g., 30): Faster decay, more aggressive archival
- Higher `DECAY_BASE_HALF_LIFE_DAYS` (e.g., 60): Slower decay, retain memories longer

#### EbbinghausDecay

Based on Hermann Ebbinghaus's forgetting curve - classic memory decay model.

```env
DECAY_STRATEGY=ebbinghaus
DECAY_BASE_STABILITY_DAYS=30.0
```

**Use when:**
- You want a psychologically-grounded decay model
- You access memories regularly and consistently

#### LinearDecay

Simple linear decay with access multiplier - predictable and easy to understand.

```env
DECAY_STRATEGY=linear
DECAY_MAX_DAYS=365.0  # 1 year
```

**Use when:**
- You want predictable, consistent decay behavior
- You prefer simplicity over adaptive behavior

### Tuning Thresholds

#### More Aggressive Promotion (retain more in LONG_TERM)

```env
CONSOLIDATION_PROMOTION_THRESHOLD=0.6    # Lower threshold
CONSOLIDATION_ACCESS_WEIGHT=0.50         # Value access patterns more
CONSOLIDATION_RECENCY_WEIGHT=0.25
CONSOLIDATION_CONFIDENCE_WEIGHT=0.25
```

**Effect:**
- More memories promoted to LONG_TERM
- Database grows larger but retains more context

#### More Aggressive Archival (archive more aggressively)

```env
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.3     # Higher threshold
CONSOLIDATION_RECENCY_WEIGHT=0.40        # Archive old memories faster
CONSOLIDATION_ACCESS_WEIGHT=0.30
CONSOLIDATION_CONFIDENCE_WEIGHT=0.30
```

**Effect:**
- More memories archived
- Smaller database, but may lose context

#### Slower Decay (memories stay "fresh" longer)

```env
DECAY_BASE_HALF_LIFE_DAYS=60             # Increase for exponential
DECAY_BASE_STABILITY_DAYS=45             # Increase for ebbinghaus
```

**Effect:**
- Memories retain high recency scores longer
- Less aggressive archival

### Manual Triggering

You can manually trigger consolidation using Python:

```python
from haia.interfaces.scheduler import HAIAScheduler

scheduler = HAIAScheduler(neo4j_service=neo4j)
await scheduler.run_job_now("memory_consolidation")
```

---

## Theme Discovery Configuration

### Overview

Theme discovery automatically identifies semantic clusters in your memories using DBSCAN clustering and generates human-readable theme labels.

### Basic Configuration

Add these settings to your `.env` file:

```env
# Enable/disable theme discovery
THEME_DISCOVERY_ENABLED=true
THEME_DISCOVERY_SCHEDULE=0 2 * * 0  # Cron: Weekly Sundays 2 AM

# Theme labeling
THEME_LABELING_MODEL=anthropic:claude-haiku-4-5-20251001

# DBSCAN clustering parameters
DBSCAN_EPS=0.3              # Distance threshold (cosine distance)
DBSCAN_MIN_SAMPLES=3        # Minimum cluster core size
MIN_THEME_CLUSTER_SIZE=3    # Minimum memories per theme
MIN_SILHOUETTE_SCORE=0.5    # Quality threshold
```

### Understanding DBSCAN Parameters

#### `DBSCAN_EPS` (epsilon) - Distance Threshold

Controls how similar memories must be to form a cluster (cosine distance):

```env
DBSCAN_EPS=0.3  # Default
```

**Lower values (e.g., 0.2):**
- Tighter, more specific clusters
- More themes discovered
- Smaller themes with highly similar memories

**Higher values (e.g., 0.4):**
- Looser, more general clusters
- Fewer themes discovered
- Larger themes with moderately similar memories

**Recommended ranges:**
- **0.2-0.25**: Very specific topics (e.g., "Docker Swarm orchestration")
- **0.3-0.35**: Balanced (e.g., "Docker container management")
- **0.4-0.45**: Broad topics (e.g., "Containerization and orchestration")

#### `DBSCAN_MIN_SAMPLES` - Minimum Cluster Core Size

Number of memories required to form a dense core:

```env
DBSCAN_MIN_SAMPLES=3  # Default
```

**Lower values (e.g., 2):**
- More small themes
- Easier to form clusters
- Risk of noise being classified as themes

**Higher values (e.g., 5):**
- Fewer, larger themes
- Stricter cluster formation
- More memories classified as outliers

#### `MIN_THEME_CLUSTER_SIZE` - Post-Clustering Filter

Minimum memories required for a cluster to become a theme:

```env
MIN_THEME_CLUSTER_SIZE=3  # Default
```

- Filters out very small clusters after DBSCAN runs
- Independent of `DBSCAN_MIN_SAMPLES`
- Use to discard insignificant themes

#### `MIN_SILHOUETTE_SCORE` - Quality Threshold

Cluster quality validation (-1 to 1):

```env
MIN_SILHOUETTE_SCORE=0.5  # Default
```

**Score interpretation:**
- **0.7-1.0**: Excellent cluster separation
- **0.5-0.7**: Good cluster structure (recommended threshold)
- **0.2-0.5**: Weak cluster structure
- **<0.2**: Poor clustering

**Lower threshold (e.g., 0.4):**
- More themes accepted
- May include lower-quality clusters
- Useful for exploratory analysis

**Higher threshold (e.g., 0.6):**
- Only high-quality themes
- Stricter validation
- Fewer themes overall

### Tuning for Specific Goals

#### Goal: Discover More Themes (smaller, specific topics)

```env
DBSCAN_EPS=0.2                    # Tighter clusters
DBSCAN_MIN_SAMPLES=2              # Lower core size
MIN_THEME_CLUSTER_SIZE=2          # Accept smaller themes
MIN_SILHOUETTE_SCORE=0.4          # Relaxed quality
```

#### Goal: Discover Fewer Themes (broader, general topics)

```env
DBSCAN_EPS=0.4                    # Looser clusters
DBSCAN_MIN_SAMPLES=5              # Higher core size
MIN_THEME_CLUSTER_SIZE=5          # Require larger themes
MIN_SILHOUETTE_SCORE=0.5          # Standard quality
```

#### Goal: Highest Quality Themes Only

```env
DBSCAN_EPS=0.25                   # Tight clusters
DBSCAN_MIN_SAMPLES=3              # Standard core
MIN_THEME_CLUSTER_SIZE=3          # Standard size
MIN_SILHOUETTE_SCORE=0.6          # High quality threshold
```

#### Goal: Allow More Outliers (exploratory mode)

```env
DBSCAN_EPS=0.3                    # Standard
DBSCAN_MIN_SAMPLES=2              # Lower core size
MIN_THEME_CLUSTER_SIZE=2          # Accept smaller themes
MIN_SILHOUETTE_SCORE=0.4          # Relaxed quality
```

### Manual Triggering

Trigger theme discovery manually:

```python
from haia.interfaces.scheduler import HAIAScheduler

scheduler = HAIAScheduler(neo4j_service=neo4j, theme_discovery_enabled=True)
await scheduler.run_job_now("theme_discovery")
```

---

## Using the Discovery API

HAIA exposes REST API endpoints for exploring discovered themes.

### List All Themes

```bash
curl "http://localhost:8000/discovery/themes?status=active&limit=50"
```

**Response:**
```json
[
  {
    "theme_id": "theme_abc123",
    "label": "Docker container management preferences",
    "description": "User preferences for Docker container orchestration...",
    "cluster_id": 2,
    "memory_count": 12,
    "silhouette_score": 0.68,
    "status": "active",
    "created_at": "2026-01-05T02:00:00Z",
    "updated_at": "2026-01-05T02:00:00Z"
  }
]
```

**Parameters:**
- `status`: Filter by theme status (`active`, `stale`, `archived`)
- `limit`: Maximum themes to return (default: 50)

### Get Theme Details

```bash
curl "http://localhost:8000/discovery/themes/{theme_id}"
```

Returns detailed information about a specific theme.

### Get Memories in Theme

```bash
curl "http://localhost:8000/discovery/themes/{theme_id}/memories?limit=20"
```

**Response:**
```json
[
  {
    "memory_id": "mem_xyz789",
    "content": "I prefer using docker compose for container orchestration",
    "memory_type": "preference",
    "confidence": 0.85,
    "created_at": "2026-01-02T10:30:00Z",
    "distance_to_centroid": 0.15
  }
]
```

Memories sorted by distance to cluster centroid (most representative first).

### Get Theme Statistics

```bash
curl "http://localhost:8000/discovery/themes/{theme_id}/stats"
```

**Response:**
```json
{
  "total_memories": 12,
  "memory_types": ["preference", "technical_context"],
  "avg_confidence": 0.82,
  "earliest_memory": "2025-12-15T08:00:00Z",
  "latest_memory": "2026-01-04T14:30:00Z",
  "type_distribution": [
    {"memory_type": "preference", "count": 8},
    {"memory_type": "technical_context", "count": 4}
  ]
}
```

### Manually Trigger Clustering

```bash
curl -X POST "http://localhost:8000/discovery/themes/refresh"
```

**Response:**
```json
{
  "status": "completed",
  "timestamp": "2026-01-05T10:15:00Z",
  "memories_analyzed": 150,
  "themes_discovered": 8,
  "outliers_count": 12,
  "avg_silhouette_score": 0.64,
  "execution_time_ms": 2450.5
}
```

---

## Tuning Guidelines

### Scenario: "I have thousands of memories, consolidation is slow"

**Solution 1: Increase consolidation interval**
```env
CONSOLIDATION_SCHEDULE=0 3 * * 0  # Weekly instead of daily
```

**Solution 2: More aggressive archival**
```env
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.3  # Archive more aggressively
DECAY_BASE_HALF_LIFE_DAYS=30          # Faster decay
```

**Solution 3: Reduce SHORT_TERM waiting period**
```env
CONSOLIDATION_SHORT_TERM_DAYS=3  # Promote/archive earlier
```

### Scenario: "No themes are being discovered"

**Cause 1: Not enough memories with embeddings**
- Need at least `MIN_THEME_CLUSTER_SIZE * 2` memories
- Check: How many memories have embeddings?

**Cause 2: DBSCAN parameters too strict**

**Solution:**
```env
DBSCAN_EPS=0.35                   # Increase distance threshold
DBSCAN_MIN_SAMPLES=2              # Lower core size
MIN_THEME_CLUSTER_SIZE=2          # Accept smaller themes
MIN_SILHOUETTE_SCORE=0.4          # Relax quality threshold
```

**Cause 3: Memories too dissimilar (all outliers)**
- Check logs for outlier count
- May indicate diverse, unrelated conversation topics

### Scenario: "All my memories are outliers"

**Cause:** DBSCAN parameters too restrictive

**Solution:**
```env
DBSCAN_EPS=0.4                    # Much higher distance threshold
DBSCAN_MIN_SAMPLES=2              # Lower core requirement
```

**Alternative:** Your memories may genuinely be very diverse - this is okay! Outliers are expected when conversation topics don't cluster naturally.

### Scenario: "Theme labels are poor quality"

**Cause:** LLM labeling model issues

**Solution 1: Use a more powerful model**
```env
THEME_LABELING_MODEL=anthropic:claude-sonnet-4-5-20251001  # Instead of haiku
```

**Solution 2: Check API key validity**
```bash
# Verify Anthropic API key is set correctly
echo $ANTHROPIC_API_KEY
```

**Solution 3: Review sample memories**
- Check logs for the first 10 memories in each cluster
- Ensure they're actually similar enough to have a coherent label

### Scenario: "Consolidation is too aggressive, I'm losing context"

**Solution: More conservative settings**
```env
CONSOLIDATION_PROMOTION_THRESHOLD=0.6   # Promote more easily
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.15   # Archive less aggressively
DECAY_BASE_HALF_LIFE_DAYS=60            # Slower decay
CONSOLIDATION_ACCESS_WEIGHT=0.50        # Value access patterns more
CONSOLIDATION_RECENCY_WEIGHT=0.20
CONSOLIDATION_CONFIDENCE_WEIGHT=0.30
```

### Scenario: "I want themes to update more frequently"

**Solution:**
```env
THEME_DISCOVERY_SCHEDULE=0 2 * * *  # Daily at 2 AM instead of weekly
```

**Warning:** This increases computational cost. Consider:
- Database size (100+ memories)
- Available compute resources
- Theme stability (daily updates may be too volatile)

---

## Troubleshooting

### Consolidation Job Not Running

**Check 1: Is consolidation enabled?**
```bash
grep CONSOLIDATION_ENABLED .env
# Should be: CONSOLIDATION_ENABLED=true
```

**Check 2: Is scheduler started?**
```python
# In your application logs, look for:
# "INFO: Scheduler started with X jobs"
```

**Check 3: Manually trigger to test**
```python
from haia.interfaces.scheduler import HAIAScheduler
scheduler = HAIAScheduler(...)
await scheduler.run_job_now("memory_consolidation")
```

### Theme Discovery Job Not Running

**Check 1: Is theme discovery enabled?**
```bash
grep THEME_DISCOVERY_ENABLED .env
# Should be: THEME_DISCOVERY_ENABLED=true
```

**Check 2: Verify API key**
```bash
grep ANTHROPIC_API_KEY .env
# Should have a valid key for LLM labeling
```

**Check 3: Check logs for errors**
```bash
# Look for theme discovery errors in application logs
grep "theme_discovery" /var/log/haia/app.log
```

### Low Silhouette Scores

**Cause:** Overlapping clusters, poor separation

**Solution 1: Tighter clusters**
```env
DBSCAN_EPS=0.25  # Lower epsilon for tighter clusters
```

**Solution 2: Filter poor clusters**
```env
MIN_SILHOUETTE_SCORE=0.6  # Raise threshold to discard poor clusters
```

**Solution 3: Accept lower scores if labels are good**
- Silhouette scores are a guideline, not absolute
- Check if theme labels are still meaningful despite low scores

### No Memories Promoted/Archived

**Cause 1: Thresholds too strict**

**Solution:**
```env
CONSOLIDATION_PROMOTION_THRESHOLD=0.6   # Lower promotion threshold
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.25   # Raise archival threshold
```

**Cause 2: Memories too young**
- SHORT_TERM memories need to be ≥7 days old (by default)
- Check `CONSOLIDATION_SHORT_TERM_DAYS` setting

**Cause 3: Decay too slow**
- Recency scores may still be too high
- Lower `DECAY_BASE_HALF_LIFE_DAYS` for faster decay

### Performance Degradation

**Consolidation is O(n) time complexity** - expected for large datasets

**Solution 1: Run during off-peak hours**
```env
CONSOLIDATION_SCHEDULE=0 3 * * *  # Adjust schedule
```

**Solution 2: Reduce evaluation frequency**
```env
CONSOLIDATION_SHORT_TERM_DAYS=14  # Only evaluate memories ≥14 days old
```

**Solution 3: Monitor execution time**
- Check `execution_time_ms` in consolidation reports
- Expected: <5s for 1000 memories

---

## Advanced Scenarios

### Scenario: Different Decay for Different Memory Types

Currently not supported natively, but you can simulate with custom weights:

```env
# Prefer high-confidence memories (boost confidence weight)
CONSOLIDATION_CONFIDENCE_WEIGHT=0.40
CONSOLIDATION_ACCESS_WEIGHT=0.30
CONSOLIDATION_RECENCY_WEIGHT=0.30
```

### Scenario: Export Themes for External Analysis

Use the Discovery API to extract themes:

```bash
# Export all themes to JSON
curl "http://localhost:8000/discovery/themes?limit=1000" > themes.json

# Export memories for a specific theme
curl "http://localhost:8000/discovery/themes/{theme_id}/memories?limit=1000" > theme_memories.json
```

### Scenario: Manual Theme Curation

**Option 1: Adjust DBSCAN parameters and re-run**
```bash
# Update .env with new parameters
curl -X POST "http://localhost:8000/discovery/themes/refresh"
```

**Option 2: Mark themes as STALE/ARCHIVED in Neo4j**
```cypher
// In Neo4j Browser
MATCH (t:Theme {theme_id: "theme_to_archive"})
SET t.status = "archived"
```

### Scenario: Periodic Cleanup of ARCHIVED Memories

**Manual cleanup:**
```cypher
// Delete ARCHIVED memories older than 1 year
MATCH (m:Memory {tier: "archived"})
WHERE m.tier_updated_at < datetime() - duration('P365D')
DETACH DELETE m
```

**Automated cleanup (future feature):**
- Add to consolidation logic
- Configurable retention period for ARCHIVED tier

---

## Summary

### Key Consolidation Parameters

| Parameter | Default | Lower → Higher Effect |
|-----------|---------|----------------------|
| `CONSOLIDATION_PROMOTION_THRESHOLD` | 0.7 | Easier promotion → Harder promotion |
| `CONSOLIDATION_ARCHIVAL_THRESHOLD` | 0.2 | Less archival → More archival |
| `DECAY_BASE_HALF_LIFE_DAYS` | 43.3 | Faster decay → Slower decay |

### Key Theme Discovery Parameters

| Parameter | Default | Lower → Higher Effect |
|-----------|---------|----------------------|
| `DBSCAN_EPS` | 0.3 | Tighter clusters → Looser clusters |
| `DBSCAN_MIN_SAMPLES` | 3 | Easier clustering → Stricter clustering |
| `MIN_SILHOUETTE_SCORE` | 0.5 | More themes → Fewer themes (higher quality) |

### References

- [Consolidation Documentation](../src/haia/consolidation/README.md)
- [Theme Discovery Documentation](../src/haia/discovery/README.md)
- [Specification: 010-hybrid-temporal-memory](../specs/010-hybrid-temporal-memory/spec.md)
