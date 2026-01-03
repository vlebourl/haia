# Migration Guide: Session 9 → Session 10

**From**: Context Optimization (Session 9)
**To**: Hybrid Temporal Memory (Session 10)
**Date**: 2026-01-03

---

## Overview

Session 10 builds on Session 9's context optimization by adding **automated memory lifecycle management** and **theme discovery**. This migration guide documents breaking changes, new features, and upgrade procedures.

---

## Summary of Changes

### New Features (Session 10)

#### Phase 8: Memory Consolidation (US6)
- **Three-tier lifecycle management**: SHORT_TERM → LONG_TERM → ARCHIVED
- **Priority-based transitions**: Access frequency + recency + confidence
- **Three decay strategies**: ExponentialDecay, EbbinghausDecay, LinearDecay
- **Automated scheduling**: Daily consolidation jobs at 3 AM

#### Phase 9: Theme Discovery (US7)
- **DBSCAN clustering**: Automatic semantic theme discovery
- **LLM-generated labels**: Human-readable theme descriptions (3-8 words)
- **Quality validation**: Silhouette score filtering (>0.5)
- **REST API**: 5 endpoints for theme exploration
- **Automated scheduling**: Weekly theme discovery on Sundays at 2 AM

### Session 9 Features (Retained)

All Session 9 features remain functional:
- ✅ Deduplication (exact + similarity-based)
- ✅ Re-ranking (multi-factor relevance scoring)
- ✅ Token budget management
- ✅ Access tracking

---

## Breaking Changes

### 1. Database Schema Changes

**New Memory Properties**:
```cypher
// Added in Session 10
tier: string                    // "short_term" | "long_term" | "archived"
tier_updated_at: datetime       // When tier was last changed
consolidation_score: float      // Most recent priority score
```

**Migration Required**: ✅ **YES**

**Migration Script**:
```cypher
// Add tier properties to existing memories
MATCH (m:Memory)
WHERE m.tier IS NULL
SET m.tier = "short_term",
    m.tier_updated_at = datetime(),
    m.consolidation_score = NULL
```

**Run Migration**:
```bash
# In Neo4j Browser or via neo4j-admin
cat <<'EOF' | cypher-shell -u neo4j -p $NEO4J_PASSWORD
MATCH (m:Memory)
WHERE m.tier IS NULL
SET m.tier = "short_term",
    m.tier_updated_at = datetime(),
    m.consolidation_score = NULL
EOF
```

### 2. New Node Types

**Theme Nodes** (Session 10):
```cypher
(t:Theme {
  theme_id: string,
  label: string,
  description: string,
  cluster_id: int,
  memory_count: int,
  silhouette_score: float,
  status: string,  // "active" | "stale" | "archived"
  created_at: datetime,
  updated_at: datetime
})
```

**Migration Required**: ⚠️ **NO** (automatically created by theme discovery)

**New Relationships**:
```cypher
(m:Memory)-[r:BELONGS_TO_THEME {
  distance_to_centroid: float,
  assigned_at: datetime
}]->(t:Theme)
```

### 3. Configuration Changes

**New Required Environment Variables**:

```env
# Memory Consolidation (Phase 8)
CONSOLIDATION_ENABLED=true
CONSOLIDATION_SCHEDULE=0 3 * * *
CONSOLIDATION_PROMOTION_THRESHOLD=0.7
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.2
CONSOLIDATION_SHORT_TERM_DAYS=7
DECAY_STRATEGY=exponential
DECAY_BASE_HALF_LIFE_DAYS=43.3

# Theme Discovery (Phase 9)
THEME_DISCOVERY_ENABLED=true
THEME_DISCOVERY_SCHEDULE=0 2 * * 0
THEME_LABELING_MODEL=anthropic:claude-haiku-4-5-20251001
DBSCAN_EPS=0.3
DBSCAN_MIN_SAMPLES=3
MIN_THEME_CLUSTER_SIZE=3
MIN_SILHOUETTE_SCORE=0.5

# Feature Flag
HYBRID_TEMPORAL_MEMORY=true
```

**Migration Required**: ✅ **YES**

**Migration Steps**:
1. Copy new variables from `.env.example` to `.env`
2. Adjust thresholds based on your memory corpus size
3. Restart HAIA service to pick up new configuration

### 4. Scheduler Integration

**New Scheduled Jobs**:
- `memory_consolidation` (daily at 3 AM)
- `theme_discovery` (weekly Sundays at 2 AM)

**Migration Required**: ⚠️ **NO** (automatically registered by HAIAScheduler)

**Verification**:
```python
from haia.interfaces.scheduler import HAIAScheduler

scheduler = HAIAScheduler(neo4j_service=neo4j)
scheduler.start()

# List all jobs
jobs = scheduler.scheduler.get_jobs()
for job in jobs:
    print(f"{job.id}: {job.next_run_time}")
```

---

## Upgrade Procedure

### Step 1: Backup Database

**CRITICAL**: Back up Neo4j database before upgrading

```bash
# Create backup
./database/backups/backup.sh

# Verify backup
ls -lh database/backups/
# Should show: haia-backup-YYYYMMDD-HHMMSS.dump
```

### Step 2: Update Code

```bash
# Pull latest code
git fetch origin
git checkout 010-us6-consolidation  # Or main if merged

# Update dependencies
uv sync

# Verify version
grep version pyproject.toml
# Should show: version = "1.0.0-session10"
```

### Step 3: Migrate Database Schema

```bash
# Apply schema migration
cat <<'EOF' | docker exec -i haia-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD
MATCH (m:Memory)
WHERE m.tier IS NULL
SET m.tier = "short_term",
    m.tier_updated_at = datetime(),
    m.consolidation_score = NULL;

// Verify migration
MATCH (m:Memory)
RETURN count(m) as total_memories,
       count(m.tier) as memories_with_tier;
EOF
```

**Expected Output**:
```
total_memories | memories_with_tier
---------------|-------------------
      150      |        150
```

### Step 4: Update Configuration

```bash
# Update .env with new variables
cp .env .env.session9.backup
cat .env.example >> .env

# Edit .env to set values
nano .env
# - Set CONSOLIDATION_ENABLED=true
# - Set THEME_DISCOVERY_ENABLED=true
# - Set THEME_LABELING_MODEL=anthropic:claude-haiku-4-5-20251001
# - Adjust thresholds as needed
```

### Step 5: Restart Services

```bash
# Production (Docker)
docker compose -f deployment/docker-compose.yml restart haia

# Development
# Stop existing process (Ctrl+C)
uv run uvicorn haia.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Step 6: Verify Upgrade

```bash
# Check scheduler is running
curl http://localhost:8000/health
# Should return: {"status":"healthy","version":"1.0.0-session10"}

# Trigger consolidation manually (optional)
curl -X POST http://localhost:8000/consolidation/run

# Trigger theme discovery manually (optional)
curl -X POST http://localhost:8000/discovery/themes/refresh
```

### Step 7: Monitor First Run

**Watch logs for consolidation**:
```bash
# Look for consolidation job execution
docker logs -f haia | grep consolidation

# Expected output:
# INFO: Starting scheduled memory consolidation job
# INFO: Fetched 150 memories for consolidation
# INFO: ✓ PROMOTED: abc12345... → LONG_TERM (score: 0.782)
# INFO: ✓ ARCHIVED: def67890... → ARCHIVED (score: 0.156)
# INFO: Memory consolidation complete: 42 promoted, 31 archived (2450ms)
```

**Watch logs for theme discovery**:
```bash
# Look for theme discovery job execution
docker logs -f haia | grep "theme"

# Expected output:
# INFO: Starting scheduled theme discovery job
# INFO: Fetched 150 memories with embeddings
# INFO: DBSCAN clustering: 8 clusters discovered, 12 outliers
# INFO: Generated theme label: Docker container management preferences
# INFO: Created 8 theme nodes in Neo4j
# INFO: Theme discovery job complete: 8 themes, avg silhouette=0.64 (2450ms)
```

---

## Compatibility Matrix

| Component | Session 9 | Session 10 | Compatible |
|-----------|-----------|------------|-----------|
| Neo4j 5.15+ | ✅ | ✅ | ✅ |
| Python 3.11+ | ✅ | ✅ | ✅ |
| PydanticAI | 1.25+ | 1.25+ | ✅ |
| Ollama (nomic-embed-text) | ✅ | ✅ | ✅ |
| Anthropic API (optional) | ✅ | ✅ | ✅ |
| Memory schema | Basic | Extended | ⚠️ Migration required |
| .env configuration | Basic | Extended | ⚠️ Update required |

---

## Rollback Procedure

If issues arise, rollback to Session 9:

### Step 1: Restore Database Backup

```bash
# Stop HAIA service
docker compose -f deployment/docker-compose.yml stop haia

# Restore backup
./database/backups/restore.sh haia-backup-YYYYMMDD-HHMMSS.dump

# Restart Neo4j
docker compose -f deployment/docker-compose.yml restart neo4j
```

### Step 2: Revert Code

```bash
# Checkout Session 9 code
git checkout <session-9-commit-hash>

# Downgrade dependencies
uv sync

# Revert configuration
cp .env.session9.backup .env
```

### Step 3: Restart Services

```bash
docker compose -f deployment/docker-compose.yml start haia
```

---

## Testing Upgrade

### Pre-Upgrade Checklist

- [ ] Backup Neo4j database created
- [ ] Current memory count documented: `______` memories
- [ ] Current conversation count: `______` conversations
- [ ] .env backed up to .env.session9.backup
- [ ] Session 9 commit hash recorded: `______________________`

### Post-Upgrade Checklist

- [ ] Database migration applied successfully
- [ ] All memories have `tier` property set
- [ ] Scheduler shows 2 new jobs (consolidation, theme_discovery)
- [ ] First consolidation run completed without errors
- [ ] First theme discovery run completed without errors
- [ ] Themes created in Neo4j (check via Neo4j Browser)
- [ ] Discovery API endpoints responding
- [ ] No errors in logs

### Validation Queries

**Check memory tier distribution**:
```cypher
MATCH (m:Memory)
RETURN m.tier as tier, count(*) as count
ORDER BY count DESC
```

**Check themes created**:
```cypher
MATCH (t:Theme)
RETURN t.label, t.memory_count, t.silhouette_score
ORDER BY t.memory_count DESC
```

**Check theme relationships**:
```cypher
MATCH (m:Memory)-[r:BELONGS_TO_THEME]->(t:Theme)
RETURN t.label, count(m) as memory_count
ORDER BY memory_count DESC
```

---

## New API Endpoints

### Discovery API

**List Themes**:
```bash
curl "http://localhost:8000/discovery/themes?status=active&limit=50"
```

**Get Theme Details**:
```bash
curl "http://localhost:8000/discovery/themes/{theme_id}"
```

**Get Theme Memories**:
```bash
curl "http://localhost:8000/discovery/themes/{theme_id}/memories?limit=20"
```

**Get Theme Statistics**:
```bash
curl "http://localhost:8000/discovery/themes/{theme_id}/stats"
```

**Manual Clustering Trigger**:
```bash
curl -X POST "http://localhost:8000/discovery/themes/refresh"
```

---

## Performance Impact

### Expected Changes

**Consolidation Job** (daily at 3 AM):
- **Duration**: ~3.5s for 1000 memories, ~35s for 10,000 memories
- **CPU**: Moderate spike during execution
- **I/O**: Batched Neo4j writes (100 memories per transaction)

**Theme Discovery Job** (weekly Sundays at 2 AM):
- **Duration**: ~20s for 100 memories, ~30s for 100 memories
- **CPU**: High during DBSCAN clustering and silhouette calculation
- **Network**: LLM API calls for theme labeling (1 call per theme)

**Runtime Impact**:
- No impact on chat API latency
- No impact on memory retrieval performance
- Scheduled jobs run in background

---

## Troubleshooting

### Issue: Migration script fails with "Property tier already exists"

**Cause**: Migration already applied or partial migration

**Solution**:
```cypher
// Check current state
MATCH (m:Memory)
RETURN count(m) as total, count(m.tier) as with_tier

// If some memories have tier but not all, complete migration
MATCH (m:Memory)
WHERE m.tier IS NULL
SET m.tier = "short_term",
    m.tier_updated_at = datetime()
```

### Issue: Consolidation job not running

**Symptoms**: No consolidation logs after 3 AM

**Solution**:
```bash
# Check if consolidation enabled
grep CONSOLIDATION_ENABLED .env

# Check scheduler status
curl http://localhost:8000/scheduler/jobs

# Manually trigger to test
curl -X POST http://localhost:8000/consolidation/run
```

### Issue: Theme discovery finds no themes

**Causes**:
1. Not enough memories with embeddings
2. DBSCAN parameters too restrictive

**Solution**:
```cypher
// Check memory count with embeddings
MATCH (m:Memory)
WHERE m.embedding IS NOT NULL
RETURN count(m)
// Should be >= MIN_THEME_CLUSTER_SIZE * 2

// If insufficient, relax parameters in .env:
DBSCAN_EPS=0.35                  # Increase from 0.3
DBSCAN_MIN_SAMPLES=2             # Decrease from 3
MIN_THEME_CLUSTER_SIZE=2         # Decrease from 3
```

### Issue: High LLM costs from theme labeling

**Cause**: Too many themes discovered

**Solution**:
```env
# In .env, make clustering more restrictive
DBSCAN_EPS=0.25                  # Tighter clusters
DBSCAN_MIN_SAMPLES=5             # Larger minimum cluster size
MIN_SILHOUETTE_SCORE=0.6         # Higher quality threshold
```

---

## Configuration Tuning Recommendations

### Small Deployments (<100 memories)

```env
# Relaxed consolidation (retain more in LONG_TERM)
CONSOLIDATION_PROMOTION_THRESHOLD=0.6
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.15
DECAY_BASE_HALF_LIFE_DAYS=60

# Relaxed theme discovery
DBSCAN_EPS=0.35
MIN_SILHOUETTE_SCORE=0.4
```

### Medium Deployments (100-1000 memories)

```env
# Balanced consolidation (default)
CONSOLIDATION_PROMOTION_THRESHOLD=0.7
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.2
DECAY_BASE_HALF_LIFE_DAYS=43.3

# Balanced theme discovery (default)
DBSCAN_EPS=0.3
MIN_SILHOUETTE_SCORE=0.5
```

### Large Deployments (>1000 memories)

```env
# Aggressive consolidation (keep database smaller)
CONSOLIDATION_PROMOTION_THRESHOLD=0.75
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.25
DECAY_BASE_HALF_LIFE_DAYS=30

# Strict theme discovery (fewer, higher-quality themes)
DBSCAN_EPS=0.25
DBSCAN_MIN_SAMPLES=5
MIN_SILHOUETTE_SCORE=0.6
```

---

## Support and Resources

### Documentation

- **Main README**: `README.md`
- **Consolidation Guide**: `src/haia/consolidation/README.md`
- **Theme Discovery Guide**: `src/haia/discovery/README.md`
- **User Guide**: `docs/USER_GUIDE_MEMORY_MANAGEMENT.md`
- **Performance Report**: `docs/PERFORMANCE_REPORT.md`
- **Validation Report**: `docs/VALIDATION_REPORT.md`

### Test Coverage

- **US6 Tests**: `tests/integration/test_us6_validation.py` (7 tests)
- **US7 Tests**: `tests/integration/test_us7_validation.py` (5 tests)

### Specification

- **Full Spec**: `specs/010-hybrid-temporal-memory/spec.md`
- **Task Breakdown**: `specs/010-hybrid-temporal-memory/tasks.md`

---

**Migration Document Version**: 1.0
**Last Updated**: 2026-01-03
**Contact**: See project README for support channels
