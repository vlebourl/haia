# Theme Discovery System

**Session 14, User Story 7**

Automatic semantic theme discovery using DBSCAN clustering on memory embeddings with LLM-generated theme labels for exploring patterns in the memory corpus.

## Overview

The theme discovery system automatically identifies **semantic clusters** in your memories using:
- **DBSCAN clustering** on 768-dimensional embedding vectors
- **Silhouette score** validation for cluster quality
- **LLM-generated labels** (3-8 words, human-readable)
- **Weekly scheduling** (Sundays 2 AM by default)

**Use Cases**:
- Discover recurring topics in conversations
- Identify knowledge domains (Docker, Proxmox, Home Assistant, etc.)
- Explore memory patterns and trends
- Find related memories by theme

## Architecture

### Components

1. **`models.py`** - Pydantic models for themes and clustering
2. **`theme_clusterer.py`** - DBSCAN clustering service with LLM labeling
3. **`discovery_api.py`** - REST API for theme exploration

### Workflow

```
┌─────────────────┐
│ Fetch Memories  │  Query all memories with embeddings
│  with Embeddings│  from Neo4j (SHORT_TERM + LONG_TERM)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Run DBSCAN     │  Cluster memories by cosine distance
│   Clustering    │  (eps=0.3, min_samples=3)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Calculate      │  Validate cluster quality
│  Silhouette     │  (score >0.5 = good separation)
│   Scores        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │  LLM creates human-readable labels
│  Theme Labels   │  (3-8 words, descriptive)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Store Themes   │  Create Theme nodes in Neo4j
│   in Neo4j      │  + BELONGS_TO_THEME relationships
└─────────────────┘
```

## DBSCAN Clustering

**DBSCAN** (Density-Based Spatial Clustering of Applications with Noise):
- Groups memories with similar embeddings
- Automatically determines number of clusters
- Identifies outliers (noise points)

### Parameters

**`eps`** (epsilon) - Distance threshold:
- **Default**: 0.3 (cosine distance)
- **Lower** (e.g., 0.2): Tighter clusters, more themes
- **Higher** (e.g., 0.4): Looser clusters, fewer themes

**`min_samples`** - Minimum cluster core size:
- **Default**: 3 memories
- **Lower** (e.g., 2): More small themes
- **Higher** (e.g., 5): Fewer, larger themes

**`min_cluster_size`** - Post-clustering filter:
- **Default**: 3 memories
- Themes with fewer memories are discarded

**`min_silhouette_score`** - Quality threshold:
- **Default**: 0.5 (good separation)
- **Range**: -1 (poor) to 1 (excellent)
- Themes below threshold are discarded

## Theme Structure

### Theme Model

```python
class Theme(BaseModel):
    theme_id: str             # Unique identifier
    label: str                # Human-readable label (3-8 words)
    description: str          # Detailed description (1-2 sentences)
    cluster_id: int           # DBSCAN cluster ID
    memory_count: int         # Number of memories in theme
    silhouette_score: float   # Quality score (0.0-1.0)
    status: ClusterStatus     # ACTIVE | STALE | ARCHIVED
    created_at: datetime      # When discovered
    updated_at: datetime      # Last re-clustering
```

### Theme Status

- **ACTIVE**: Current, valid theme from latest clustering
- **STALE**: Outdated theme from previous clustering
- **ARCHIVED**: Historical theme, no longer active

### Neo4j Schema

**Theme Node**:
```cypher
(t:Theme {
  theme_id: string,
  label: string,
  description: string,
  cluster_id: int,
  memory_count: int,
  silhouette_score: float,
  status: string,
  created_at: datetime,
  updated_at: datetime
})
```

**BELONGS_TO_THEME Relationship**:
```cypher
(m:Memory)-[r:BELONGS_TO_THEME {
  distance_to_centroid: float,
  assigned_at: datetime
}]->(t:Theme)
```

## Usage

### Programmatic

```python
from haia.discovery.theme_clusterer import ThemeClusterer
from haia.discovery.models import ClusteringConfig
from haia.services.neo4j import Neo4jService

# Initialize clusterer
config = ClusteringConfig(
    eps=0.3,
    min_samples=3,
    min_cluster_size=3,
    min_silhouette_score=0.5,
)

clusterer = ThemeClusterer(
    neo4j_service=neo4j,
    labeling_model="anthropic:claude-haiku-4-5-20251001",
    config=config,
)

# Run clustering
report = await clusterer.run_clustering()

# View results
print(report.summary())
# Theme Discovery Report (2026-01-05T02:00:00Z):
#   Analyzed:   150 memories
#   Discovered: 8 themes
#   Outliers:   12 (8.0%)
#   Quality:    0.64 avg silhouette score
#   Execution:  2450ms
```

### Automated Scheduling

Theme discovery runs automatically via **APScheduler** (weekly Sundays at 2 AM):

```python
from haia.interfaces.scheduler import HAIAScheduler

scheduler = HAIAScheduler(
    neo4j_service=neo4j,
    theme_discovery_enabled=True,
    theme_discovery_schedule="0 2 * * 0",  # Weekly Sundays 2 AM
    dbscan_eps=0.3,
    dbscan_min_samples=3,
)

scheduler.start()
```

### Manual Trigger

```python
# Trigger clustering manually
await scheduler.run_job_now("theme_discovery")
```

## Discovery API

RESTful API for exploring discovered themes.

### List Themes

```http
GET /discovery/themes?status=active&limit=50
```

**Response**:
```json
[
  {
    "theme_id": "theme_abc123",
    "label": "Docker container management preferences",
    "description": "User preferences for Docker container orchestration, networking, and deployment strategies",
    "cluster_id": 2,
    "memory_count": 12,
    "silhouette_score": 0.68,
    "status": "active",
    "created_at": "2026-01-05T02:00:00Z",
    "updated_at": "2026-01-05T02:00:00Z"
  }
]
```

### Get Theme Details

```http
GET /discovery/themes/{theme_id}
```

**Response**: Single `Theme` object with full details

### Get Memories in Theme

```http
GET /discovery/themes/{theme_id}/memories?limit=20
```

**Response**:
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

### Get Theme Statistics

```http
GET /discovery/themes/{theme_id}/stats
```

**Response**:
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

### Manual Clustering Trigger

```http
POST /discovery/themes/refresh
```

**Response**:
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

## Configuration

### Environment Variables

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

### Tuning Guidelines

**More Themes** (discover smaller, specific topics):
- Lower `DBSCAN_EPS` (e.g., 0.2)
- Lower `MIN_THEME_CLUSTER_SIZE` (e.g., 2)
- Lower `MIN_SILHOUETTE_SCORE` (e.g., 0.4)

**Fewer Themes** (broader, general topics):
- Raise `DBSCAN_EPS` (e.g., 0.4)
- Raise `DBSCAN_MIN_SAMPLES` (e.g., 5)
- Raise `MIN_THEME_CLUSTER_SIZE` (e.g., 5)

**Higher Quality** (strict cluster separation):
- Raise `MIN_SILHOUETTE_SCORE` (e.g., 0.6)
- Lower `DBSCAN_EPS` for tighter clusters

**More Outliers OK** (allow noise):
- Keep default settings
- Outliers = memories that don't fit any theme

## Observability

Clustering job logs detailed execution information:

```
INFO: Starting scheduled theme discovery job
INFO: Fetched 150 memories with embeddings
INFO: DBSCAN clustering: 8 clusters discovered, 12 outliers
INFO: Generated theme label: Docker container management preferences
INFO: Generated theme label: Proxmox VM configuration best practices
...
INFO: Created 8 theme nodes in Neo4j
INFO: Created 138 BELONGS_TO_THEME relationships
INFO: Theme discovery job complete: 8 themes, 12 outliers, avg silhouette=0.64 (2450ms)
```

**Clustering Report**:
```
Theme Discovery Report (2026-01-05T02:00:00Z):
  Analyzed:   150 memories
  Discovered: 8 themes
  Outliers:   12 (8.0%)
  Quality:    0.64 avg silhouette score
  Execution:  2450ms
```

## Performance

**Benchmarks** (from acceptance tests):
- **100 memories**: <30 seconds clustering time
- **50 memories**: ~5-10 seconds
- **30 memories**: <5 seconds

**Scalability**:
- DBSCAN: O(n log n) with spatial indexing
- Silhouette calculation: O(n²) (sampled to max 1000 memories)
- LLM labeling: O(k) where k = number of clusters

## Silhouette Score Interpretation

**Score Ranges**:
- **0.7-1.0**: Strong, well-separated clusters (excellent)
- **0.5-0.7**: Reasonable cluster structure (good)
- **0.2-0.5**: Weak cluster structure (acceptable)
- **<0.2**: No meaningful clustering (poor)

**Per-Theme Scores**: Each theme has its own silhouette score showing quality

## Testing

### Unit Tests

```bash
# Run discovery unit tests
uv run pytest tests/unit/test_discovery*.py -v
```

### Integration Tests

```bash
# Run acceptance validation tests (requires Neo4j + Anthropic API)
RUN_INTEGRATION_TESTS=1 NEO4J_PASSWORD=your_password \
  ANTHROPIC_API_KEY=your_key \
  uv run pytest tests/integration/test_us7_validation.py -v
```

**Acceptance Tests**:
- T134-T135: Clustering 50 memories across 5 topics (3-7 clusters)
- T136: Silhouette score quality (>0.4)
- T137: Human-readable theme labels (3-8 words)
- T139: Edge case handling (insufficient data)
- T140: Performance (<30s for 100 memories)

## Troubleshooting

### No themes discovered

**Causes**:
- Not enough memories with embeddings
- Memories too dissimilar (all outliers)
- `DBSCAN_EPS` too low (clusters too tight)
- `MIN_THEME_CLUSTER_SIZE` too high

**Solutions**:
- Check memory count: Need at least `MIN_THEME_CLUSTER_SIZE * 2` memories
- Increase `DBSCAN_EPS` (e.g., 0.35 or 0.4)
- Lower `MIN_THEME_CLUSTER_SIZE` (e.g., 2)
- Review logs for outlier count

### All memories are outliers

**Cause**: DBSCAN parameters too restrictive

**Solution**:
- Increase `DBSCAN_EPS` (e.g., 0.4)
- Lower `DBSCAN_MIN_SAMPLES` (e.g., 2)
- Check embedding quality (all vectors should be unit-normalized)

### Poor theme labels

**Cause**: LLM labeling model issues

**Solutions**:
- Verify `THEME_LABELING_MODEL` configuration
- Check API key validity (Anthropic)
- Review sample memories in cluster (logs show first 10)
- Consider using a more powerful model (e.g., sonnet instead of haiku)

### Clustering job not running

**Cause**: Scheduler not started or job disabled

**Solution**:
- Verify `THEME_DISCOVERY_ENABLED=true`
- Check scheduler status: `scheduler.get_jobs()`
- Review logs for scheduler startup messages
- Manually trigger: `await scheduler.run_job_now("theme_discovery")`

### Low silhouette scores

**Causes**:
- Overlapping clusters (poor separation)
- `DBSCAN_EPS` too high (clusters too loose)
- Heterogeneous memory content

**Solutions**:
- Lower `DBSCAN_EPS` for tighter clusters
- Raise `MIN_SILHOUETTE_SCORE` to filter poor clusters
- Accept lower scores if themes are still meaningful (labels may be good despite low scores)

## Example Themes

From a homelab memory corpus (150 memories):

1. **"Docker container orchestration and networking"** (12 memories, score: 0.68)
   - Container deployment strategies
   - Network configuration preferences
   - Volume management approaches

2. **"Proxmox VM provisioning and HA setup"** (11 memories, score: 0.72)
   - VM template preferences
   - High availability configuration
   - Resource allocation strategies

3. **"Home Assistant automation workflows"** (10 memories, score: 0.65)
   - Smart home integrations
   - Automation triggers and actions
   - Sensor configurations

4. **"Monitoring and alerting infrastructure"** (9 memories, score: 0.58)
   - Prometheus metrics collection
   - Grafana dashboard preferences
   - Alert routing configuration

5. **"Backup strategies and retention policies"** (8 memories, score: 0.61)
   - Backup tools and schedules
   - Retention rules
   - Verification procedures

## References

- **Specification**: `specs/010-hybrid-temporal-memory/spec.md` (User Story 7)
- **Tasks**: `specs/010-hybrid-temporal-memory/tasks.md` (Phase 9: T120-T140)
- **Models**: `src/haia/discovery/models.py`
- **Clustering Service**: `src/haia/discovery/theme_clusterer.py`
- **Discovery API**: `src/haia/interfaces/discovery_api.py`
- **Scheduler Integration**: `src/haia/interfaces/scheduler.py`
- **DBSCAN Algorithm**: [scikit-learn DBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html)
- **Silhouette Score**: [scikit-learn silhouette_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html)
