# Memory Consolidation Lifecycle

**Session 14, User Story 6**

Automatic memory tier management system that prevents unbounded database growth while preserving important memories through priority-based lifecycle transitions.

## Overview

The consolidation system implements a **three-tier memory lifecycle**:

```
SHORT_TERM (new, <7 days) → LONG_TERM (important) → ARCHIVED (low-priority)
```

Memories automatically transition between tiers based on a **priority score** calculated from:
- **Access frequency** (40%): How often the memory is retrieved
- **Recency** (30%): How recently the memory was accessed (with decay)
- **Confidence** (30%): Original extraction confidence

## Architecture

### Components

1. **`models.py`** - Pydantic models for consolidation data structures
2. **`decay.py`** - Decay strategies for recency scoring
3. **`consolidator.py`** - Core consolidation service and orchestration

### Tier System

**SHORT_TERM**
- New memories (<7 days old)
- Waiting period before promotion eligibility
- Default tier for all extracted memories

**LONG_TERM**
- Promoted from SHORT_TERM when priority ≥0.7
- Important, frequently accessed memories
- Active memories used in conversations

**ARCHIVED**
- Demoted from LONG_TERM when priority <0.2
- Low-priority, rarely accessed memories
- Preserved for historical queries

### Priority Scoring Formula

```python
priority_score = (
    0.40 * access_frequency +  # Normalized by max access count
    0.30 * recency_score +      # From decay strategy
    0.30 * confidence           # Original extraction confidence
)
```

**Thresholds**:
- Promotion: `priority_score >= 0.7` (SHORT_TERM → LONG_TERM)
- Archival: `priority_score < 0.2` (LONG_TERM → ARCHIVED)

## Decay Strategies

Three mathematical models for calculating recency scores:

### ExponentialDecay (Default)

Adaptive half-life based on access patterns:
```python
effective_half_life = base_half_life * (1 + log(1 + access_count))
decay_score = 0.5 ** (days_elapsed / effective_half_life)
```

**Parameters**:
- `base_half_life_days`: 43.3 days (≈6 weeks)

**Behavior**: Frequently accessed memories decay slower

### EbbinghausDecay

Based on Hermann Ebbinghaus's forgetting curve:
```python
stability = base_stability * (1 + 0.5 * access_count)
retention = exp(-days_elapsed / stability)
```

**Parameters**:
- `base_stability_days`: 30.0 days

**Behavior**: Classic forgetting curve with access-based stability boost

### LinearDecay

Simple linear decay with access multiplier:
```python
base_decay = 1.0 - (days_elapsed / max_days)
access_multiplier = 1.0 + (access_count * 0.05)
score = base_decay * access_multiplier  # clamped to [0, 1]
```

**Parameters**:
- `max_days`: 365.0 days (1 year)

**Behavior**: Linear decay with 5% boost per access

## Usage

### Programmatic

```python
from haia.consolidation.consolidator import MemoryConsolidator
from haia.consolidation.decay import ExponentialDecay
from haia.services.neo4j import Neo4jService

# Initialize consolidator
consolidator = MemoryConsolidator(
    neo4j_service=neo4j,
    decay_strategy=ExponentialDecay(base_half_life_days=43.3),
    promotion_threshold=0.7,
    archival_threshold=0.2,
    short_term_days=7,
)

# Run consolidation
report = await consolidator.run_consolidation()

# View results
print(report.summary())
# Consolidation Report (2026-01-03T03:00:00Z):
#   Processed: 100 memories
#   Promoted:  28 (28.0%)
#   Archived:  19 (19.0%)
#   Unchanged: 53 (53.0%)
#   Execution: 1250ms
```

### Automated Scheduling

Consolidation runs automatically via **APScheduler** (daily at 3 AM by default):

```python
from haia.interfaces.scheduler import HAIAScheduler

scheduler = HAIAScheduler(
    neo4j_service=neo4j,
    consolidation_enabled=True,
    consolidation_schedule="0 3 * * *",  # Daily at 3 AM
    promotion_threshold=0.7,
    archival_threshold=0.2,
)

scheduler.start()
```

### Manual Trigger

```python
# Trigger consolidation manually
await scheduler.run_job_now("memory_consolidation")
```

## Configuration

### Environment Variables

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
DECAY_BASE_STABILITY_DAYS=30.0  # For Ebbinghaus decay
DECAY_MAX_DAYS=365.0            # For linear decay

# Priority score weights (must sum to ~1.0)
CONSOLIDATION_ACCESS_WEIGHT=0.40     # Access frequency weight
CONSOLIDATION_RECENCY_WEIGHT=0.30    # Recency score weight
CONSOLIDATION_CONFIDENCE_WEIGHT=0.30 # Confidence weight
```

### Tuning Guidelines

**More Aggressive Promotion** (retain more in LONG_TERM):
- Lower `promotion_threshold` (e.g., 0.6)
- Increase `access_weight` (value access patterns more)

**More Aggressive Archival** (archive more aggressively):
- Raise `archival_threshold` (e.g., 0.3)
- Increase `recency_weight` (archive old memories faster)

**Slower Decay** (memories stay "fresh" longer):
- Increase `base_half_life_days` (e.g., 60)
- Use `EbbinghausDecay` with higher `base_stability_days`

**Faster Decay** (memories age quickly):
- Decrease `base_half_life_days` (e.g., 30)
- Use `LinearDecay` with lower `max_days`

## Observability

All consolidation decisions are logged with detailed reasoning:

```
INFO: ✓ PROMOTED: abc12345... → LONG_TERM (score: 0.782)
      HIGH PRIORITY (score: 0.782). Access frequency: 0.85, Recency: 0.72,
      Confidence: 0.90. Exceeds promotion threshold 0.7. Promoting to LONG_TERM.

INFO: ✓ ARCHIVED: def67890... → ARCHIVED (score: 0.156)
      LOW PRIORITY (score: 0.156). Access frequency: 0.05, Recency: 0.12,
      Confidence: 0.40. Below archival threshold 0.2. Archiving to ARCHIVED.
```

**Consolidation Report Summary**:
```
Consolidation Report (2026-01-03T03:00:00Z):
  Processed: 150 memories
  Promoted:  42 (28.0%)
  Archived:  31 (20.7%)
  Unchanged: 77 (51.3%)
  Execution: 2450ms
```

## Performance

**Benchmarks** (from acceptance tests):
- **1000 memories**: <5 seconds consolidation time
- **100 memories**: ~1.5 seconds
- **50 memories**: <1 second

**Scalability**: Linear time complexity O(n) where n = total memories

## Database Schema

### Memory Node Properties

```cypher
(m:Memory {
  memory_id: string,
  tier: string,  // "short_term" | "long_term" | "archived"
  tier_updated_at: datetime,
  consolidation_score: float,  // Last calculated priority score
  access_count: int,
  last_accessed: datetime,
  created_at: datetime
})
```

### Consolidation Metadata

- `tier`: Current memory tier (updated by consolidation)
- `tier_updated_at`: When tier was last changed
- `consolidation_score`: Most recent priority score
- `access_count`: Number of times retrieved (tracked by AccessTracker)
- `last_accessed`: Most recent access timestamp

## Testing

### Unit Tests

```bash
# Run consolidation unit tests
uv run pytest tests/unit/test_consolidation*.py -v
```

### Integration Tests

```bash
# Run acceptance validation tests (requires Neo4j)
RUN_INTEGRATION_TESTS=1 NEO4J_PASSWORD=your_password \
  uv run pytest tests/integration/test_us6_validation.py -v
```

**Acceptance Tests**:
- T113: Promotion logic (~30% promoted)
- T114: Archival logic (~20% archived)
- T115: Priority formula validation
- T116: Decay strategy validation
- T117: Observability logging
- T118: Performance (<5s for 1000 memories)
- T119: Archived memory retrieval

## Troubleshooting

### No memories promoted/archived

**Cause**: Thresholds too strict or decay too slow

**Solution**:
- Check `promotion_threshold` and `archival_threshold` values
- Verify `short_term_days` eligibility (memories must be ≥7 days old)
- Review decay strategy parameters (adjust half-life/stability)
- Check logs for priority scores

### Consolidation job not running

**Cause**: Scheduler not started or job disabled

**Solution**:
- Verify `CONSOLIDATION_ENABLED=true`
- Check scheduler status: `scheduler.get_jobs()`
- Review logs for scheduler startup messages
- Manually trigger: `await scheduler.run_job_now("memory_consolidation")`

### Performance degradation

**Cause**: Too many memories being evaluated

**Solution**:
- Consolidation runs in O(n) time - expected for large datasets
- Consider increasing `short_term_days` to reduce evaluation frequency
- Monitor `execution_time_ms` in reports
- Run consolidation during off-peak hours (adjust `CONSOLIDATION_SCHEDULE`)

## References

- **Specification**: `specs/010-hybrid-temporal-memory/spec.md` (User Story 6)
- **Tasks**: `specs/010-hybrid-temporal-memory/tasks.md` (Phase 8: T097-T119)
- **Models**: `src/haia/consolidation/models.py`
- **Decay Strategies**: `src/haia/consolidation/decay.py`
- **Consolidator Service**: `src/haia/consolidation/consolidator.py`
- **Scheduler Integration**: `src/haia/interfaces/scheduler.py`
