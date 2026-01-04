# Web Search User Guide

**Feature Status**: ✅ Production Ready (Session 15)
**User Stories**: US1 (Current Information), US2 (Documentation Discovery), US3 (Multi-Source Verification)

## Overview

HAIA's web search integration enables fetching current information beyond the LLM's training data cutoff. The system automatically detects when web search is needed and queries multiple search backends with intelligent failover, caching, and result ranking.

### Key Capabilities

1. **Automatic Intent Detection**: HAIA determines when to search the web based on query patterns
2. **Multi-Backend Support**: Four search engines with automatic failover (Tavily, Brave, DuckDuckGo, Google CSE)
3. **Intelligent Caching**: Avoids redundant searches with pattern-based TTL strategies
4. **Documentation Discovery**: Prioritizes official documentation sources
5. **Multi-Source Verification**: Cross-references information from multiple backends

## Quick Start

### Basic Configuration

Add to your `.env` file:

```bash
# Enable web search (default: true)
SEARCH_ENABLED=true

# Tavily API key (recommended for best accuracy)
SEARCH_TAVILY_API_KEY=tvly-your_api_key_here

# Backend priority (Tavily first for AI-optimized results)
SEARCH_BACKEND_PRIORITY=tavily,brave,google_cse
```

### Getting API Keys

**Tavily** (Recommended - AI-optimized):
1. Visit https://tavily.com
2. Sign up for free tier (1000 searches/month)
3. Copy API key to `SEARCH_TAVILY_API_KEY`

**Brave Search** (Optional - fast, reliable):
1. Visit https://brave.com/search/api/
2. Free tier: 2000 queries/month
3. Copy API key to `SEARCH_BRAVE_API_KEY`

**Google CSE** (Optional - comprehensive):
1. Visit https://programmablesearchengine.google.com/
2. Create search engine and get API key
3. Add `SEARCH_GOOGLE_CSE_API_KEY` and `SEARCH_GOOGLE_CSE_ENGINE_ID`

**DuckDuckGo** (Included - no API key needed):
- Free, no rate limits
- Works out of the box
- Less accurate for version/date queries

## Usage Examples

### Example 1: Current Version Queries

```python
# Ask HAIA about current software versions
User: "What is the latest version of Docker Engine?"

# HAIA automatically:
# 1. Detects version query intent
# 2. Triggers web search via Tavily
# 3. Returns current, accurate information

HAIA: "The latest version of Docker Engine is 29.0, released in November 2025.
According to the official Docker release notes, this version includes..."

# Source attribution included in response
```

**How it works**:
- Intent detection: Query contains "latest version" trigger
- Search backend: Tavily (AI-optimized for accuracy)
- Cache: Result cached for 1 hour (version queries)
- RAG: LLM receives explicit instruction to prioritize search results

### Example 2: Documentation Discovery

```python
# Ask about official documentation
User: "Show me the Proxmox VE storage configuration guide"

# HAIA automatically:
# 1. Detects documentation query intent
# 2. Whitelists official domains (proxmox.com, pve.proxmox.com)
# 3. Ranks official docs highest (+0.40 bonus)

HAIA: "Here's the official Proxmox VE storage configuration guide:

**Proxmox VE Storage** (proxmox.com)
The storage configuration in Proxmox VE...

You can find the complete guide at: https://pve.proxmox.com/wiki/Storage
"
```

**How it works**:
- Intent detection: Query contains "guide" trigger
- Domain filtering: Only proxmox.com, pve.proxmox.com allowed
- Enhanced scoring: Official docs get +0.40 relevance boost
- Cache: Result cached for 24 hours (documentation)

### Example 3: Security Updates

```python
# Ask about security advisories
User: "Are there any recent security advisories for Proxmox VE?"

# HAIA automatically:
# 1. Detects security query intent
# 2. Uses short cache TTL (5 minutes)
# 3. Filters for authoritative sources

HAIA: "Based on recent searches:

**Proxmox VE Security Advisory** (Published: 2025-12-15)
Critical security update addressing CVE-2025-XXXXX...
"
```

**How it works**:
- Intent detection: Query contains "security" + "advisory"
- Short cache TTL: 5 minutes (security info changes quickly)
- Source filtering: Prioritizes security.proxmox.com

### Example 4: Troubleshooting with Current Info

```python
# Troubleshoot with latest information
User: "My Ceph cluster shows 'slow ops' warnings. What's the recommended fix in the latest docs?"

# HAIA combines:
# 1. Web search for latest Ceph documentation
# 2. Memory retrieval for your cluster config
# 3. Contextual recommendations

HAIA: "Based on the latest Ceph documentation (v18.2):

The 'slow ops' warning typically indicates...

For your cluster (based on previous discussions):
- You're running Ceph Quincy on Proxmox 8.x
- Your OSDs are using HDDs with SSD journals
- Recommended: Check OSD disk latency with 'ceph osd perf'
..."
```

**How it works**:
- Web search: Finds latest Ceph docs
- Memory integration: Recalls your infrastructure details
- Combined response: Current docs + personalized context

### Example 5: Comparing Multiple Sources

```python
# Get perspectives from multiple sources
User: "Should I use ext4 or ZFS for Proxmox storage?"

# HAIA:
# 1. Queries multiple backends (Tavily, Brave, Google CSE)
# 2. Aggregates results
# 3. Shows cross-verified information

HAIA: "Based on multiple sources:

**ZFS Advantages** (Cross-verified by 3 sources ✓):
- Built-in compression and deduplication
- Native snapshots
- Better data integrity protection

**ext4 Advantages** (Cross-verified by 2 sources):
- Lower memory overhead
- Simpler configuration
- Better performance for small random writes

Official Proxmox recommendation: ZFS for production, ext4 for testing
Sources: proxmox.com, reddit.com/r/Proxmox, serverfault.com
"
```

**How it works**:
- Multi-source search: Queries all configured backends
- Deduplication: Same URLs merged with source attribution
- Cross-verification: Results marked with ✓ when found by multiple backends

## Advanced Configuration

### Cache TTL Strategies

Control how long search results are cached:

```bash
# In .env file
SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_TTL_SECONDS=86400  # Default: 24 hours

# Pattern-based TTL (automatic):
# - Version queries: 1 hour
# - Security queries: 5 minutes
# - Documentation: 24 hours
# - General queries: 24 hours
```

### Backend Priority

Order backends by preference:

```bash
# Tavily first (AI-optimized, most accurate)
SEARCH_BACKEND_PRIORITY=tavily,brave,google_cse

# Brave first (fast, reliable for general queries)
SEARCH_BACKEND_PRIORITY=brave,tavily,duckduckgo

# Free-only (no API keys needed)
SEARCH_BACKEND_PRIORITY=duckduckgo
```

### Result Limits

Control how many results are fetched and displayed:

```bash
SEARCH_DEFAULT_MAX_RESULTS=10  # Fetch from backend
SEARCH_DEFAULT_TOP_RESULTS=5   # Present to LLM
SEARCH_MIN_RELEVANCE_SCORE=0.3 # Filter low-quality results
```

### Domain Filtering

Whitelist/blacklist specific domains:

```python
# Programmatically via tool parameters
{
  "query": "Proxmox storage guide",
  "allowed_domains": ["proxmox.com", "pve.proxmox.com"],
  "blocked_domains": ["forum.spam.com"]
}
```

## Intent Detection Patterns

HAIA automatically triggers web search when it detects these patterns:

### Version/Current Info Triggers
- "latest version of..."
- "current release..."
- "newest build..."
- "what version is..."
- "recent update..."

### Documentation Triggers
- "documentation for..."
- "official guide..."
- "how to configure..."
- "setup instructions..."
- "API reference..."

### Security/CVE Triggers
- "security advisory..."
- "CVE for..."
- "vulnerability in..."
- "patch for..."

### Comparison/Research Triggers
- "compare X and Y"
- "difference between..."
- "which is better..."
- "pros and cons of..."

### Exclusion Patterns (Won't Trigger Search)
- "What is..." (definition questions)
- "How do I..." (procedural questions about known topics)
- "Explain..." (conceptual questions)
- "Why does..." (cause/reason questions)

You can override intent detection by being explicit:
- "Search the web for..." (force search)
- "Based on your training..." (skip search)

## Performance Characteristics

### Latency

| Backend | Average Latency | Notes |
|---------|----------------|-------|
| Cache Hit | <10ms | In-memory lookup |
| Tavily | 300-1000ms | AI-optimized, accurate |
| Brave | 200-800ms | Fast, reliable |
| DuckDuckGo | 500-1500ms | Free, variable speed |
| Google CSE | 400-1200ms | Comprehensive |

### Cache Hit Rate

Typical cache hit rates:
- **Development**: 30-40% (frequent code changes)
- **Production**: 60-80% (stable queries)

Optimize cache hits by:
1. Using consistent query phrasing
2. Avoiding time-specific queries
3. Leveraging pattern-based TTL

### Rate Limits

Backend rate limits (free tiers):

| Backend | Requests/Second | Requests/Month | Cost |
|---------|----------------|----------------|------|
| Tavily | ~10 | 1,000 | Free tier |
| Brave | 15 | 2,000 | Free tier |
| DuckDuckGo | Unlimited | Unlimited | Free |
| Google CSE | Variable | 100/day | Free |

## Troubleshooting

### Search Not Triggering

**Symptom**: HAIA doesn't search when you expect it to

**Solutions**:
1. Check `SEARCH_ENABLED=true` in `.env`
2. Verify query matches intent patterns (see above)
3. Force search: "Search the web for..."
4. Check logs: `docker logs haia-api | grep "Intent detection"`

### No Results Returned

**Symptom**: Search returns empty results

**Solutions**:
1. Check API key configuration:
   ```bash
   docker exec haia-api env | grep SEARCH_TAVILY_API_KEY
   ```
2. Verify backend health:
   ```bash
   # Check logs for authentication errors
   docker logs haia-api | grep -i "authentication\|api key"
   ```
3. Try different backend:
   ```bash
   SEARCH_BACKEND_PRIORITY=duckduckgo,brave,tavily
   ```

### Outdated Results

**Symptom**: Getting stale information

**Solutions**:
1. Clear cache:
   ```bash
   # Restart container to clear in-memory cache
   docker restart haia-api
   ```
2. Reduce cache TTL:
   ```bash
   SEARCH_CACHE_TTL_SECONDS=3600  # 1 hour instead of 24
   ```
3. Disable cache temporarily:
   ```bash
   SEARCH_CACHE_ENABLED=false
   ```

### Rate Limit Errors

**Symptom**: "Rate limit exceeded" errors

**Solutions**:
1. Configure multiple backends for failover:
   ```bash
   SEARCH_BACKEND_PRIORITY=tavily,brave,duckduckgo
   ```
2. Enable caching to reduce API calls:
   ```bash
   SEARCH_CACHE_ENABLED=true
   ```
3. Check rate limit status in logs:
   ```bash
   docker logs haia-api | grep "rate limit"
   ```

## Integration with Memory System

Web search results integrate seamlessly with HAIA's memory system:

### Memory Extraction

```python
User: "What's the latest Proxmox VE version?"
HAIA: "Proxmox VE 8.1 was released in November 2024..."

# Later, HAIA extracts memory:
Memory {
  type: "technical_context",
  content: "User is interested in Proxmox VE versions",
  confidence: 0.8
}
```

### Personalized Search

```python
# HAIA remembers your infrastructure:
Memory: "User runs Proxmox VE 8.0 on cluster prox0, prox1, prox2"

# Future searches are contextualized:
User: "Are there any breaking changes in the latest version?"
HAIA: "Searching for Proxmox VE 8.1 changelog..."
      "Based on your current version (8.0), here are the breaking changes..."
```

## Best Practices

### 1. Configure Tavily for Best Accuracy

Tavily provides AI-optimized search results with the highest accuracy:

```bash
SEARCH_TAVILY_API_KEY=tvly-your_key_here
SEARCH_BACKEND_PRIORITY=tavily,brave,google_cse
```

### 2. Use Specific Queries

**Good**:
- "Latest Docker Engine version"
- "Proxmox VE 8.1 release notes"
- "Ceph slow ops troubleshooting guide"

**Less Effective**:
- "Docker stuff"
- "Proxmox problems"
- "Storage help"

### 3. Leverage Cache for Repeated Queries

If you frequently ask about the same topic, queries are cached:

```python
# First query: 800ms (live search)
User: "Latest Python version"

# Second query: <10ms (cache hit)
User: "Latest Python version"
```

### 4. Force Fresh Results When Needed

For time-sensitive information:

```python
User: "Search the web for latest security advisories"
# Forces fresh search, bypasses cache
```

### 5. Use Domain Filtering for Official Docs

When you need authoritative sources:

```python
User: "Official Proxmox storage documentation only"
# Automatically whitelists proxmox.com, pve.proxmox.com
```

## API Reference

### Web Search Tool Parameters

```python
{
  "query": str,                    # Search query (required)
  "backend_preference": str,       # Specific backend (optional)
  "max_results": int,              # Max results (default: 10)
  "time_range": str,               # "day"|"week"|"month"|"year"|"any"
  "allowed_domains": List[str],    # Domain whitelist
  "blocked_domains": List[str],    # Domain blacklist
  "use_cache": bool                # Enable caching (default: true)
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_ENABLED` | `true` | Enable web search feature |
| `SEARCH_TAVILY_API_KEY` | - | Tavily API key |
| `SEARCH_BRAVE_API_KEY` | - | Brave Search API key |
| `SEARCH_GOOGLE_CSE_API_KEY` | - | Google CSE API key |
| `SEARCH_GOOGLE_CSE_ENGINE_ID` | - | Google CSE engine ID |
| `SEARCH_BACKEND_PRIORITY` | `tavily,brave,google_cse` | Backend order |
| `SEARCH_CACHE_ENABLED` | `true` | Enable caching |
| `SEARCH_CACHE_TTL_SECONDS` | `86400` | Cache TTL (24h) |
| `SEARCH_DEFAULT_MAX_RESULTS` | `10` | Results to fetch |
| `SEARCH_DEFAULT_TOP_RESULTS` | `5` | Results to show |
| `SEARCH_MIN_RELEVANCE_SCORE` | `0.3` | Filter threshold |
| `SEARCH_REQUEST_TIMEOUT_SECONDS` | `10` | HTTP timeout |

## FAQ

### Q: Do I need API keys?

**A**: No, DuckDuckGo works without API keys. However, Tavily provides significantly better accuracy for version queries and documentation discovery.

### Q: How much does it cost?

**A**: Free tiers are generous:
- Tavily: 1,000 searches/month free
- Brave: 2,000 searches/month free
- DuckDuckGo: Unlimited free
- Google CSE: 100 searches/day free

With caching, typical usage: 50-200 searches/month.

### Q: Can I disable web search?

**A**: Yes, set `SEARCH_ENABLED=false` in `.env`:

```bash
SEARCH_ENABLED=false
```

### Q: How do I monitor search usage?

**A**: Check logs for search activity:

```bash
# View recent searches
docker logs haia-api | grep "web_search"

# View cache hit rate
docker logs haia-api | grep "Cache hit"

# View backend usage
docker logs haia-api | grep "Attempting search"
```

### Q: Can I use only free backends?

**A**: Yes, use DuckDuckGo only:

```bash
SEARCH_BACKEND_PRIORITY=duckduckgo
```

Note: Accuracy may be lower for version/date queries.

### Q: How does failover work?

**A**: If primary backend fails, HAIA automatically tries the next backend in priority order:

```
1. Try Tavily → [Rate Limit Error]
2. Try Brave → [Success!]
```

Failover happens in <2 seconds.

## Related Documentation

- [Memory Management Guide](USER_GUIDE_MEMORY_MANAGEMENT.md) - How web search integrates with memory
- [Deployment Guide](../deployment/README.md) - Production deployment with Docker
- [Architecture Overview](architecture/README.md) - Technical deep-dive

## Support

For issues or questions:
1. Check [GitHub Issues](https://github.com/vlebourl/haia/issues)
2. Review logs: `docker logs haia-api`
3. Enable debug logging: `LOG_LEVEL=DEBUG` in `.env`
