"""Configuration management using pydantic-settings."""

from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TruncationStrategy(str, Enum):
    """Strategy for handling token budget overflow."""

    HARD_CUTOFF = "hard_cutoff"  # Stop including memories when budget reached
    TRUNCATE = "truncate"  # Truncate individual memories to fit budget


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # LLM Configuration
    haia_model: str = Field(
        ...,
        description="Model selection: 'provider:model' format",
        examples=["anthropic:claude-haiku-4-5-20251001", "ollama:qwen2.5-coder"],
    )
    anthropic_api_key: str | None = Field(
        None, description="Anthropic API key (required if using anthropic provider)"
    )
    ollama_base_url: str = Field(
        "http://localhost:11434", description="Ollama server base URL"
    )
    llm_timeout: float = Field(
        30.0,
        description="LLM API request timeout in seconds",
        ge=1.0,
        le=600.0,
    )

    # System Prompt Configuration
    haia_system_prompt: str | None = Field(
        None,
        description="Custom system prompt (overrides default if provided)",
    )
    haia_profile_path: str = Field(
        "haia_profile.yaml",
        description="Path to personal homelab profile YAML file",
    )

    # Application Configuration
    context_window_size: int = Field(
        20, description="Number of messages to keep in context window", ge=1
    )
    database_url: str = Field(
        "sqlite+aiosqlite:///./haia.db", description="Database connection URL"
    )
    host: str = Field("0.0.0.0", description="API server host")
    port: int = Field(8000, description="API server port", ge=1, le=65535)

    # Conversation Boundary Detection Configuration
    transcript_storage_dir: str = Field(
        "data/transcripts",
        description="Directory for storing conversation transcripts",
    )
    boundary_idle_threshold_minutes: int = Field(
        10,
        description="Minimum idle time (minutes) to consider for boundary detection",
        ge=1,
        le=1440,
    )
    boundary_message_drop_threshold: float = Field(
        0.5,
        description="Minimum message count drop (fraction) to trigger boundary",
        ge=0.0,
        le=1.0,
    )
    boundary_max_tracked_conversations: int = Field(
        1000,
        description="Maximum number of conversations to track in memory (LRU eviction)",
        ge=10,
        le=100000,
    )

    # Neo4j Configuration
    neo4j_uri: str = Field(
        "bolt://localhost:7687",
        description="Neo4j connection URI",
    )
    neo4j_user: str = Field(
        "neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        ...,
        description="Neo4j password (required)",
    )

    # LiteLLM Proxy Configuration (Session 16)
    litellm_proxy_url: str | None = Field(
        None,
        description="LiteLLM proxy URL (e.g., http://litellm:4000)",
    )
    litellm_master_key: str | None = Field(
        None,
        description="LiteLLM admin API key for proxy access",
    )

    # Memory Extraction Configuration
    extraction_model: str | None = Field(
        None,
        description="Model for memory extraction (defaults to haia_model if not set)",
    )
    extraction_min_confidence: float = Field(
        0.4,
        description="Minimum confidence threshold for extracted memories",
        ge=0.0,
        le=1.0,
    )

    # Embedding Configuration (Session 8 - Memory Retrieval)
    embedding_provider: str = Field(
        "google",
        description="Embedding provider: 'google' (API, recommended for GTX 1080) or 'ollama' (local, requires RTX GPU)",
    )
    embedding_model: str = Field(
        "ollama:nomic-embed-text",
        description="Embedding model in 'provider:model' format (deprecated - use embedding_provider + google_embedding_model)",
    )
    embedding_dim: int = Field(
        768,
        description="Embedding vector dimensions",
        ge=1,
    )
    retrieval_top_k: int = Field(
        10,
        description="Number of memories to retrieve in semantic search",
        ge=1,
        le=100,
    )
    retrieval_min_similarity: float = Field(
        0.65,
        description="Minimum cosine similarity threshold for retrieval",
        ge=0.0,
        le=1.0,
    )
    retrieval_min_confidence: float = Field(
        0.4,
        description="Minimum confidence threshold for retrieved memories",
        ge=0.0,
        le=1.0,
    )

    # Memory Type Weights (Session 8 - User Story 3: Relevance Filtering)
    memory_type_weight_preference: float = Field(
        1.2,
        description="Relevance weight multiplier for preference memories",
        ge=0.0,
        le=10.0,
    )
    memory_type_weight_technical_context: float = Field(
        1.1,
        description="Relevance weight multiplier for technical context memories",
        ge=0.0,
        le=10.0,
    )
    memory_type_weight_decision: float = Field(
        1.0,
        description="Relevance weight multiplier for decision memories (baseline)",
        ge=0.0,
        le=10.0,
    )
    memory_type_weight_personal_fact: float = Field(
        0.9,
        description="Relevance weight multiplier for personal fact memories",
        ge=0.0,
        le=10.0,
    )
    memory_type_weight_correction: float = Field(
        1.3,
        description="Relevance weight multiplier for correction memories (highest priority)",
        ge=0.0,
        le=10.0,
    )

    # Google API Configuration (Session 11 - Type Clustering with Google Embeddings)
    google_api_key: str | None = Field(
        None,
        description="Google Gemini API key (required for type clustering with Google embeddings)",
    )
    google_embedding_model: str = Field(
        "text-embedding-004",
        description="Google embedding model name (768-dim, used for retrieval and type clustering)",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("haia_model")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        """Ensure HAIA_MODEL has 'provider:model' format."""
        if ":" not in v:
            raise ValueError(f"Invalid HAIA_MODEL format: {v}. Expected 'provider:model'")
        provider, model = v.split(":", 1)
        if not provider or not model:
            raise ValueError(
                f"Invalid HAIA_MODEL format: {v}. Provider and model must be non-empty"
            )
        return v


class ContextOptimizationConfig(BaseSettings):
    """Configuration for context optimization features (Session 9).

    Includes settings for:
    - Memory deduplication (P1)
    - Advanced relevance re-ranking (P2)
    - Token budget management (P3)
    - Access pattern tracking
    """

    # Deduplication (P1)
    dedup_enabled: bool = Field(
        default=True, description="Enable memory deduplication"
    )
    dedup_similarity_threshold: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for duplicates (0.90-0.95 recommended)",
    )

    # Re-ranking (P2)
    reranking_enabled: bool = Field(
        default=True, description="Enable advanced re-ranking"
    )
    recency_decay_days: float = Field(
        default=30.0,
        gt=0.0,
        description="Half-life for recency decay (days)",
    )
    similarity_weight: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Weight for similarity score in re-ranking",
    )
    confidence_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for confidence score in re-ranking",
    )
    recency_weight: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for recency score in re-ranking",
    )
    frequency_weight: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for frequency score in re-ranking",
    )

    # Token budget (P3)
    token_budget_enabled: bool = Field(
        default=False, description="Enable token budgeting"
    )
    memory_token_budget: int | None = Field(
        default=None,
        gt=0,
        description="Max tokens for memory context (None = unlimited)",
    )
    token_budget_strategy: TruncationStrategy = Field(
        default=TruncationStrategy.HARD_CUTOFF,
        description="Strategy for handling budget overflow",
    )

    # Access tracking
    access_tracking_enabled: bool = Field(
        default=True, description="Track memory access patterns"
    )
    access_tracking_async: bool = Field(
        default=True, description="Async background access tracking"
    )

    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_OPT_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class TypeClusteringConfig(BaseSettings):
    """Configuration for semantic type clustering (Session 11).

    Automatically clusters semantically similar memory types using DBSCAN
    and Google Gemini embeddings to prevent vocabulary explosion.
    """

    # Type Clustering
    type_clustering_enabled: bool = Field(
        default=True, description="Enable automatic type clustering"
    )
    type_clustering_min_size: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Minimum types required per cluster",
    )
    type_clustering_similarity_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for clustering (0.75-0.85 recommended)",
    )
    type_clustering_schedule: str = Field(
        default="0 4 * * *",
        description="Cron expression for clustering schedule (default: daily at 4 AM)",
    )

    # Embedding Provider
    type_embedding_provider: str = Field(
        default="google",
        description="Embedding provider: 'google' (API, recommended) or 'local' (sentence-transformers)",
    )
    google_embedding_model: str = Field(
        default="text-embedding-004",
        description="Google embedding model name (768-dim)",
    )

    # Type Expansion for Retrieval
    type_expansion_enabled: bool = Field(
        default=True, description="Enable semantic type expansion in retrieval"
    )
    type_expansion_similarity: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum similarity for semantic neighbors",
    )
    type_expansion_max_neighbors: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum semantic neighbors to include in query expansion",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class RelationshipInferenceConfig(BaseSettings):
    """Configuration for LLM-driven relationship inference (Session 12).

    Automatically discovers semantic relationships between memories using
    LLM analysis rather than hardcoded rules.
    """

    # Relationship Inference
    relationship_inference_enabled: bool = Field(
        default=True, description="Enable automatic relationship inference"
    )
    relationship_min_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for storing relationships",
    )
    relationship_model: str | None = Field(
        default=None,
        description="Model for relationship inference (defaults to extraction_model or haia_model if not set)",
    )
    relationship_max_pairs: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum memory pairs to analyze per conversation (cost control)",
    )

    # Temporal Conflict Detection
    temporal_conflict_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for temporal conflict detection",
    )

    model_config = SettingsConfigDict(
        env_prefix="RELATIONSHIP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class HybridRetrievalConfig(BaseSettings):
    """Configuration for hybrid retrieval system (Session 13).

    Combines vector search, BM25 keyword matching, and graph traversal
    using Reciprocal Rank Fusion for improved recall and precision.
    """

    # Hybrid Retrieval
    hybrid_retrieval_enabled: bool = Field(
        default=True, description="Enable hybrid retrieval mode"
    )
    hybrid_default_methods: str = Field(
        default="vector,bm25,graph",
        description="Default enabled methods (comma-separated: vector,bm25,graph)",
    )
    hybrid_graph_max_depth: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Maximum hops for graph traversal (1-3)",
    )
    hybrid_rrf_k: int = Field(
        default=60,
        ge=1,
        description="RRF constant parameter (standard: 60)",
    )
    hybrid_enable_apoc: bool = Field(
        default=True,
        description="Try APOC plugin first, fallback to native Cypher if unavailable",
    )

    model_config = SettingsConfigDict(
        env_prefix="HYBRID_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LiteLLMBudgetConfig(BaseSettings):
    """Configuration for LiteLLM budget management (Session 16 - LiteLLM Integration).

    Controls monthly spending limits, alerts, and over-budget behavior for
    LiteLLM proxy routing across multiple providers.
    """

    # Budget Configuration
    enabled: bool = Field(default=True, description="Enable budget tracking")
    monthly_limit_usd: float = Field(
        default=50.0, ge=0.0, description="Hard stop at this amount"
    )
    alert_threshold_80: bool = Field(
        default=True, description="Alert at 80% of budget"
    )
    alert_threshold_95: bool = Field(
        default=True, description="Alert at 95% of budget"
    )
    alert_notification_channel: str = Field(
        default="telegram", description="Where to send alerts"
    )
    budget_reset_day: int = Field(
        default=1, ge=1, le=31, description="Day of month to reset (1-31)"
    )
    over_budget_behavior: str = Field(
        default="ollama_only",
        description="Behavior when over budget: ollama_only, block_all, queue_critical",
    )
    critical_features: list[str] = Field(
        default_factory=lambda: ["extraction", "relationships"],
        description="Features that always queue when over budget",
    )

    model_config = SettingsConfigDict(
        env_prefix="LITELLM_BUDGET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class SearchBackendSettings(BaseSettings):
    """Configuration for web search backends (Session 14 - Web Search Integration).

    Supports multiple search backends with automatic failover:
    - Brave Search API (recommended, paid)
    - DuckDuckGo (free, fallback)
    - Tavily API (AI-optimized, paid)
    - Google Custom Search Engine (expensive, last resort)
    """

    # Search Feature Toggle
    search_enabled: bool = Field(
        default=True, description="Enable web search functionality"
    )

    # Backend API Keys
    brave_api_key: str | None = Field(
        None, description="Brave Search API key"
    )
    tavily_api_key: str | None = Field(
        None, description="Tavily API key"
    )
    google_cse_api_key: str | None = Field(
        None, description="Google Custom Search Engine API key"
    )
    google_cse_engine_id: str | None = Field(
        None, description="Google CSE Search Engine ID (CX parameter)"
    )

    # Backend Priority (lower number = higher priority)
    backend_priority: str = Field(
        default="brave,duckduckgo,tavily,google_cse",
        description="Comma-separated backend priority list",
    )

    # Cache Configuration
    search_cache_enabled: bool = Field(
        default=True, description="Enable search result caching"
    )
    search_cache_ttl_seconds: int = Field(
        default=86400,
        gt=0,
        description="Default cache TTL in seconds (24 hours)",
    )
    search_cache_redis_url: str | None = Field(
        None, description="Optional Redis URL for distributed caching (None = in-memory)"
    )

    # Cost Management
    search_monthly_budget_usd: float = Field(
        default=10.0,
        ge=0.0,
        description="Monthly budget for search API costs (USD)",
    )
    search_daily_budget_usd: float = Field(
        default=1.0,
        ge=0.0,
        description="Daily budget for search API costs (USD)",
    )
    search_alert_threshold_percent: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Budget alert threshold (percent)",
    )

    # Rate Limiting
    search_max_queries_per_minute: int = Field(
        default=30,
        gt=0,
        description="Max search queries per minute (global)",
    )

    # Result Processing
    search_default_max_results: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of results to fetch from backend",
    )
    search_default_top_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of results to present to user/LLM",
    )
    search_min_relevance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score to include result",
    )

    # Timeouts
    search_request_timeout_seconds: int = Field(
        default=10,
        gt=0,
        description="HTTP request timeout for backend APIs",
    )

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instances
settings = Settings()
context_optimization_config = ContextOptimizationConfig()
type_clustering_config = TypeClusteringConfig()
relationship_inference_config = RelationshipInferenceConfig()
hybrid_retrieval_config = HybridRetrievalConfig()
litellm_budget_config = LiteLLMBudgetConfig()
search_backend_settings = SearchBackendSettings()
