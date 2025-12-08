"""Configuration management using pydantic-settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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


# Global settings instance
settings = Settings()
