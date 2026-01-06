# Brainstorming Session: LiteLLM Proxy Integration

**Date:** 2026-01-05
**Facilitator:** Claude Sonnet 4.5 (Scrum Master Agent)
**Participant:** Vincent Le Bourlot
**Session Duration:** ~45 minutes
**Feature:** LiteLLM Proxy Integration - Full proxy mode for cost management, load balancing, and observability

---

## 1. Executive Summary

### Problem Statement
HAIA currently uses LLMs directly via PydanticAI across 4 usage points (main chat, memory extraction, relationship inference, theme discovery). This creates several critical issues:

**Primary Pain Point:**
- **Shared Anthropic API quota with work (Claude Code)** → When work sessions hit rate limits, HAIA becomes **completely unusable** until quota resets
- **Availability crisis:** HAIA can go offline during work hours

**Secondary Issues:**
- All queries use the same model (inefficient resource allocation)
- No cost visibility or tracking
- No ability to switch providers transparently
- Cannot leverage different model strengths for different tasks

### Proposed Solution
Implement LiteLLM as a **full proxy** between HAIA and LLM providers to enable:
- **Intelligent model routing** by task complexity
- **Automatic fallbacks** across multiple providers (Anthropic, Google, Mistral, OpenAI, Ollama)
- **Cost tracking and budget management**
- **Request caching** for background tasks
- **Comprehensive observability**

### Expected Outcomes
- ✅ HAIA stays available even during work hours (via fallback providers)
- ✅ 30-50% cost reduction through intelligent routing
- ✅ Full visibility into cost per feature
- ✅ Quality maintained via smart model selection

---

## 2. Context & Background

### Current Architecture
```
OpenWebUI → HAIA API (PydanticAI) → Direct LLM API calls
```

**4 LLM Usage Points:**
1. **Main Chat** - User conversations via OpenWebUI
2. **Memory Extraction** - Extract structured memories from conversations
3. **Relationship Inference** - Find connections between memories
4. **Theme Discovery** - Cluster memories into themes (nightly batch job)

**Current Providers:**
- Anthropic Claude (Haiku for development)
- Google Gemini (embeddings only, not for LLM calls yet)

**Deployment Stack:**
- Docker Compose with 3 containers: haia-api, haia-neo4j, haia-webui
- Ollama running on **host machine** at localhost:11434 (not containerized)

### Available Resources

**API Keys Configured:**
- ✅ Anthropic (Claude Haiku/Sonnet/Opus)
- ✅ Google Gemini (currently embeddings, can use for LLM)
- ✅ Mistral (API access)
- ✅ OpenAI (GPT models)

**Local Models (Ollama on host:11434):**
- `gemma3:latest`
- `ministral-3`

**Constraints:**
- Anthropic quota shared with work Claude Code sessions
- GTX 1080 GPU (limited for heavy local models)
- Cost-conscious but willing to pay for quality

---

## 3. User Stories

### Epic: Multi-Provider LLM Proxy

#### User Story 1: Availability During Work Hours (P0 - Critical)
**As** Vincent
**I want** HAIA to automatically fallback to alternative providers when Anthropic hits rate limits
**So that** HAIA remains usable during work hours even when Claude Code sessions consume the shared quota

**Acceptance Criteria:**
- When Anthropic returns rate limit error, LiteLLM automatically retries with next provider in fallback chain
- User sees no interruption in service (transparent fallback)
- Chat continues with acceptable quality using Gemini/Mistral/Ollama
- Background tasks queue for retry if all paid providers fail

**Success Metrics:**
- HAIA uptime: 99.5% (vs current ~70% during work hours)
- Fallback triggered rate: < 10% of requests under normal conditions
- User-perceived response time: < 3s even during fallbacks

---

#### User Story 2: Intelligent Cost Optimization (P0)
**As** Vincent
**I want** different LLM tasks to use appropriately-powered models
**So that** I optimize cost without sacrificing quality on critical tasks

**Acceptance Criteria:**
- Simple tasks (chat with basic questions) route to Gemini Pro or Mistral
- Critical tasks (memory extraction, relationships) use Sonnet for accuracy
- Complex reasoning (theme discovery) uses Gemini Pro/Sonnet
- Cost savings of 30-50% vs always-using-Sonnet baseline

**Routing Strategy:**
```
Main Chat:              Gemini Pro → Sonnet (fallback)
Memory Extraction:      Sonnet → Gemini Pro → Mistral Large → Fail
Relationship Inference: Sonnet → Gemini Pro → Mistral Large → Fail
Theme Discovery:        Gemini Pro → Sonnet (fallback)
```

**Rationale:**
- Chat: Gemini Pro handles most conversations well, saves Anthropic quota
- Extraction/Relationships: Critical accuracy → prefer Sonnet, fallback to quality alternatives
- Theme Discovery: Complex reasoning but not critical path → Gemini Pro primary

---

#### User Story 3: Cost Visibility & Budget Control (P1)
**As** Vincent
**I want** detailed cost tracking and budget alerts
**So that** I can understand spending patterns and prevent budget overruns

**Acceptance Criteria:**
- Dashboard shows cost breakdown by feature (chat, extraction, relationships, themes)
- Model usage distribution visible (which models used how often)
- Monthly budget configurable ($50/month initial)
- Alert at 80% budget consumption
- Hard stop at 100% budget → fallback to Ollama only

**Dashboards Required:**
1. **Cost by Feature**
   ```
   Chat:          $12.50 (60%)
   Extraction:    $5.00 (24%)
   Relationships: $2.50 (12%)
   Themes:        $1.00 (4%)
   ```

2. **Model Distribution**
   ```
   Gemini Pro:  45% of calls
   Sonnet:      30%
   Mistral:     19%
   Haiku:       6%
   ```

3. **Rate Limit Proximity**
   ```
   ⚠️ Anthropic quota: 85% (resets in 4h)
   ```

4. **Fallback Success Rates**
   ```
   Primary success:   92%
   Fallback triggered: 8%
   Complete failures:  0.1%
   ```

---

#### User Story 4: Request Caching for Cost Reduction (P1)
**As** the system
**I want** to cache LLM responses for deterministic background tasks
**So that** repeated operations don't incur unnecessary API costs

**Acceptance Criteria:**
- Theme Discovery: 24-hour cache (same memory set = same themes)
- Memory Extraction: Permanent cache (same conversation = same memories)
- Relationship Inference: 7-day cache (memory pairs stable)
- Chat: No caching (dynamic, user expects fresh responses)

**Expected Savings:**
- Theme Discovery: ~90% cost reduction (runs nightly on mostly same data)
- Memory Extraction: ~30% savings (re-processing during development)
- Relationship Inference: ~50% savings (many duplicate pair evaluations)

---

#### User Story 5: Graceful Degradation (P2)
**As** Vincent
**I want** HAIA to degrade gracefully during provider outages
**So that** I maintain basic functionality even during major incidents

**Failure Scenarios & Handling:**

**Scenario 1: Complete Provider Failure**
- **Chat:** Degrade to Ollama (gemma3/ministral-3)
  - User experience: Slower, less sophisticated but functional
  - Better than complete outage

- **Background Tasks:** Alert + queue for retry
  - Memory extraction paused until provider returns
  - Preserves data quality (no garbage from weak models)
  - Operator notified via logs/alerts

**Scenario 2: Budget Exhaustion**
- **Trigger:** Monthly budget ($50) exceeded
- **Action:** Hard stop paid APIs → Ollama-only mode
- **Alert:** Urgent notification to operator
- **Impact:** Degraded but operational

**Scenario 3: Single Provider Degradation**
- **Example:** Anthropic slow but not failing
- **Action:** LiteLLM timeout (5s) → automatic fallback
- **User impact:** Slight delay, transparent switch

---

## 4. Technical Architecture

### Proposed Architecture
```
┌─────────────┐
│  OpenWebUI  │
└──────┬──────┘
       │
       v
┌─────────────────────────────────────────────┐
│  HAIA API (PydanticAI)                      │
│  - Chat endpoint                            │
│  - Memory extraction                        │
│  - Relationship inference                   │
│  - Theme discovery                          │
└──────┬──────────────────────────────────────┘
       │
       v
┌─────────────────────────────────────────────┐
│  LiteLLM Proxy (Docker container)           │
│  - Model routing                            │
│  - Fallback chains                          │
│  - Cost tracking                            │
│  - Request caching                          │
│  - Budget enforcement                       │
└──────┬──────────────────────────────────────┘
       │
       ├─> Anthropic (Claude Haiku/Sonnet/Opus)
       ├─> Google Gemini (Pro/Flash)
       ├─> Mistral (Large/Medium)
       ├─> OpenAI (GPT-4o/GPT-4o-mini)
       └─> Ollama (host:11434 - gemma3, ministral-3)
```

### Docker Compose Integration
```yaml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: haia-litellm
    ports:
      - "4000:4000"  # LiteLLM proxy endpoint
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
      - ./data/litellm:/app/data  # Cost tracking database
    environment:
      - DATABASE_URL=sqlite:////app/data/litellm.db
    extra_hosts:
      - "host.docker.internal:host-gateway"  # For Ollama access
    depends_on:
      - neo4j
    networks:
      - haia-network
```

### LiteLLM Configuration Strategy

**Model Definitions:**
```yaml
model_list:
  # Chat - Cost optimized with quality fallback
  - model_name: chat-primary
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GOOGLE_API_KEY

  - model_name: chat-fallback
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY

  # Memory Extraction - Quality first
  - model_name: extraction-primary
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: extraction-fallback-1
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GOOGLE_API_KEY

  - model_name: extraction-fallback-2
    litellm_params:
      model: mistral/mistral-large-latest
      api_key: os.environ/MISTRAL_API_KEY

  # Relationship Inference - Same as extraction
  - model_name: relationships-primary
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY

  # Theme Discovery - Complex reasoning
  - model_name: theme-primary
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GOOGLE_API_KEY

  # Local Ollama fallback (last resort)
  - model_name: ollama-fallback
    litellm_params:
      model: ollama/gemma3:latest
      api_base: http://host.docker.internal:11434
```

**Budget Configuration:**
```yaml
budgets:
  - budget_id: monthly_total
    max_budget: 50.0  # USD
    budget_duration: 30d
    soft_budget: 40.0  # Alert at $40
```

**Caching Configuration:**
```yaml
cache:
  type: redis  # Or in-memory for MVP
  host: redis  # Add redis container
  port: 6379
  ttl: 86400  # 24 hours default

cache_responses:
  - model: extraction-primary
    ttl: null  # Permanent cache (conversation text immutable)

  - model: relationships-primary
    ttl: 604800  # 7 days

  - model: theme-primary
    ttl: 86400  # 24 hours
```

---

## 5. Implementation Decisions

### Decision 1: Full Proxy Mode vs Library Integration
**Decision:** Full Proxy Mode
**Rationale:**
- Centralized control and configuration
- No code changes in HAIA (just change base URLs)
- Easy to add new providers
- Better separation of concerns
- Works with any LLM client (PydanticAI, direct APIs)

**Alternative Considered:** Library integration (litellm Python package)
**Why Rejected:** Requires code changes throughout HAIA, tighter coupling

---

### Decision 2: Routing Strategy - Task-Based Fixed Routing
**Decision:** Fixed routing per task type (not dynamic per-request complexity)
**Rationale:**
- Simple to implement and understand
- Predictable cost structure
- Avoids latency of pre-classification
- Can evolve to adaptive routing in v2

**Creative Idea Deferred to v2:**
- First message in chat uses Sonnet (returns complexity hint)
- Subsequent messages use suggested model
- Would require PydanticAI structured output changes

---

### Decision 3: Critical Task Fallback - Paid APIs Only
**Decision:** Memory Extraction and Relationship Inference fallback to paid APIs, NOT Ollama
**Rationale:**
- These tasks are foundation of memory system (garbage in, garbage out)
- Ollama quality insufficient for structured extraction accuracy
- Willing to pay for reliability on critical path
- Fallback chain: Sonnet → Gemini Pro → Mistral Large → Fail (queue for retry)

**Chat and Theme Discovery:** Can fallback to Ollama if needed (user-facing but not data-critical)

---

### Decision 4: Budget Exhaustion - Hard Stop + Ollama Fallback
**Decision:** At budget limit, stop paid APIs and fallback to Ollama for all tasks
**Rationale:**
- Prevents unexpected charges
- Maintains basic functionality
- Operator alerted to take action (increase budget or investigate usage spike)

**Alternative Considered:** Complete shutdown
**Why Rejected:** Better to have degraded service than no service

---

### Decision 5: Phased Rollout - MVP First
**Decision:** MVP includes core features, defer advanced features to v2
**MVP Scope:**
- Multi-provider routing with fallbacks
- Cost tracking and budget limits
- Basic caching (simple TTL-based)
- Prometheus metrics export

**v2 Features (Deferred):**
- Advanced prompt caching (Redis)
- A/B testing framework
- Custom routing logic (per-request complexity)
- Team-based budgets
- Virtual keys for multi-user

---

## 6. Risks & Mitigation Strategies

### Risk 1: PydanticAI + LiteLLM Compatibility
**Risk Level:** HIGH
**Description:** PydanticAI may not work seamlessly with LiteLLM proxy (OpenAI-compatible endpoint)
**Impact:** Implementation blocked or requires significant refactoring

**Mitigation:**
- **Pre-Implementation POC:** Test PydanticAI agent against LiteLLM proxy with simple model before full implementation
- **Fallback Plan:** If incompatible, use LiteLLM Python library instead of proxy (requires more code changes)
- **Timeline:** 1-2 hours POC before spec/planning

---

### Risk 2: Ollama Host Network Access from Container
**Risk Level:** MEDIUM
**Description:** LiteLLM container may not be able to reach Ollama on host:11434
**Impact:** Local fallback unavailable, defeats availability goal

**Mitigation:**
- Use `extra_hosts: host.docker.internal:host-gateway` in docker-compose
- Alternative: Run Ollama in container alongside LiteLLM
- Test network connectivity during POC phase

---

### Risk 3: Cost Spike Detection Lag
**Risk Level:** MEDIUM
**Description:** Budget alerts may not trigger fast enough to prevent significant overrun
**Impact:** Unexpected bill at month-end

**Mitigation:**
- Set soft budget at 80% ($40 of $50)
- Daily cost review during first month
- Implement request rate limiting in addition to budget caps
- Monitor Prometheus metrics actively

---

### Risk 4: Caching Staleness
**Risk Level:** LOW
**Description:** Cached responses become stale if underlying data changes
**Impact:** Incorrect theme clustering or memory extraction

**Mitigation:**
- Conservative TTLs (24h for themes, 7d for relationships)
- Cache invalidation strategy for memory updates
- Monitor cache hit rates and accuracy correlation

---

### Risk 5: Provider API Changes
**Risk Level:** LOW
**Description:** LLM provider changes API schema or pricing
**Impact:** Routing breaks or costs spike unexpectedly

**Mitigation:**
- LiteLLM handles provider API changes (abstraction layer)
- Monitor LiteLLM release notes
- Have fallback to alternative providers ready

---

## 7. Success Criteria & Metrics

### Critical Success Metrics (Must Achieve)

**Availability:**
- ✅ HAIA uptime: **≥ 99%** (vs current ~70% during work hours)
- ✅ Fallback success rate: **≥ 95%** (when primary provider fails)
- ✅ Zero complete outages due to rate limits

**Cost Optimization:**
- ✅ Cost reduction: **30-50%** vs always-using-Sonnet baseline
- ✅ Monthly spend: **≤ $50** (within budget)
- ✅ Cost per chat session: **≤ $0.10** average

**Quality Maintenance:**
- ✅ Memory extraction accuracy: **≥ 95%** (manual validation on sample)
- ✅ User-perceived chat quality: **No degradation** vs direct Sonnet

### Observability Metrics (Must Have Visibility)

**Cost Tracking:**
- Total spend (daily, monthly)
- Cost per feature (chat, extraction, relationships, themes)
- Cost per provider (Anthropic, Google, Mistral, OpenAI)
- Cost per model (Sonnet, Gemini Pro, etc.)
- Budget utilization (% of monthly limit)

**Performance:**
- Request latency (p50, p95, p99)
- Fallback trigger rate
- Cache hit rate
- Requests per minute (by feature)

**Provider Health:**
- Success rate per provider
- Error rate per provider
- Rate limit proximity (Anthropic, Google)
- Provider-specific latency

---

## 8. Next Steps & Action Items

### Immediate Actions (Before Spec)

**1. POC: PydanticAI + LiteLLM Compatibility** (1-2 hours)
- [ ] Set up minimal LiteLLM container
- [ ] Configure single model (Gemini Pro)
- [ ] Test PydanticAI agent connection via OpenAI-compatible endpoint
- [ ] Validate structured outputs work correctly
- **Owner:** Development
- **Deadline:** Before starting spec
- **Blocker:** Yes - determines technical approach

**2. Network Testing: Container → Host Ollama** (30 mins)
- [ ] Test `host.docker.internal` access from container
- [ ] Validate Ollama API reachable at host:11434
- [ ] Confirm model availability (gemma3, ministral-3)
- **Owner:** Development
- **Deadline:** During POC phase

### Specification Phase

**3. Create Feature Specification** (2-3 hours)
- [ ] Run `/speckit.specify` with brainstorming output
- [ ] Define detailed user stories with acceptance criteria
- [ ] Document technical architecture
- [ ] Define API contracts (HAIA ↔ LiteLLM)
- [ ] Create test plan
- **Owner:** Development
- **Inputs:** This brainstorming document

**4. Implementation Planning** (1-2 hours)
- [ ] Run `/speckit.plan` for technical breakdown
- [ ] Identify critical path dependencies
- [ ] Estimate effort for each component
- [ ] Define rollout strategy (migrate one feature at a time)
- **Owner:** Development

### Implementation Phase

**5. MVP Implementation** (Estimated: 8-12 hours)
- [ ] Docker compose integration (litellm + redis)
- [ ] LiteLLM configuration file
- [ ] HAIA code changes (base URL updates)
- [ ] Monitoring dashboard setup
- [ ] Testing against all 4 LLM usage points
- [ ] Documentation update
- **Owner:** Development
- **Target:** Sprint 1

**6. Gradual Rollout** (1 week)
- [ ] Week 1: Theme Discovery only (non-critical, easy to validate)
- [ ] Week 2: Main Chat (user-facing, monitor quality)
- [ ] Week 3: Memory Extraction + Relationships (critical accuracy)
- [ ] Week 4: Full production with monitoring
- **Owner:** Development + Operations

**7. Post-Launch Monitoring** (2 weeks)
- [ ] Daily cost review
- [ ] Quality spot-checks (memory accuracy)
- [ ] Fallback rate monitoring
- [ ] User feedback collection
- **Owner:** Operations

---

## 9. Open Questions & Future Considerations

### Deferred to v2

**Advanced Features:**
- Adaptive routing (complexity-based model selection per request)
- Prompt caching with Redis for even more cost savings
- A/B testing framework for comparing model quality
- Multi-tenant budget management (if HAIA goes multi-user)
- Custom retry strategies beyond LiteLLM defaults

**Integration Opportunities:**
- Grafana dashboard for LiteLLM metrics
- Alertmanager integration for budget alerts
- Prometheus federation with existing homelab monitoring

### Unresolved Questions
- Should we add dedicated Anthropic API key just for HAIA? (Would solve shared quota issue immediately)
- Is $50/month realistic budget or should we start higher during testing?
- Do we need separate dev/staging/prod LiteLLM configs?

---

## 10. References & Resources

### Documentation
- LiteLLM Docs: https://docs.litellm.ai/
- PydanticAI Model Docs: https://ai.pydantic.dev/models/
- Docker Compose Networking: https://docs.docker.com/compose/networking/

### Related HAIA Features
- Session 007: Memory Extraction (extraction-primary model routing)
- Session 008: Memory Retrieval (theme-primary model routing)
- Session 012: Web Search Integration (cost optimization parallels)

### Cost References
- Anthropic Pricing: https://www.anthropic.com/pricing
- Google Gemini Pricing: https://ai.google.dev/pricing
- Mistral Pricing: https://mistral.ai/pricing
- OpenAI Pricing: https://openai.com/pricing

---

## Appendix: Session Notes

### Key Insights from Discussion

**Insight 1: Availability is Priority Zero**
- Original assumption: Cost optimization primary driver
- Reality: HAIA being unavailable during work hours is unacceptable
- This reframed entire architecture around fallbacks vs. just routing

**Insight 2: Quality Non-Negotiable for Memory System**
- Memory extraction and relationship inference are data foundations
- Bad data from weak models compounds over time
- Worth paying for Sonnet on critical path vs. risking Ollama quality

**Insight 3: Phased Approach De-Risks Implementation**
- Starting with all features at once = high failure risk
- Gradual rollout per LLM usage point allows validation
- Can roll back individual features independently

**Insight 4: Local Ollama is Safety Net, Not Primary**
- Ollama (gemma3, ministral-3) is ultimate fallback
- Not performant enough for primary routing
- Critical for availability but not cost optimization

### Evolution of Routing Strategy

**Initial idea:** Dynamic per-request complexity routing
**Evolved to:** Fixed routing by task type with quality-aware fallbacks
**Rationale:** Simpler, more predictable, easier to debug
**Future:** Can revisit adaptive routing in v2 with PydanticAI structured outputs

### Budget Discussion

**Starting point:** $50/month budget
**Considerations:**
- Should we start higher during testing/tuning phase?
- Need realistic baseline before setting hard limits
- **Decision:** Start with $50, adjust after first month data

---

**End of Brainstorming Document**

Generated: 2026-01-05
Next Step: POC validation → `/speckit.specify`
