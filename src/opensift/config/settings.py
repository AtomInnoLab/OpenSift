"""Application settings — Pydantic-based configuration with YAML and env var support.

Configuration is loaded from (in order of precedence):
  1. Environment variables (OPENSIFT_ prefix)
  2. YAML config file (if specified)
  3. Default values
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class ServerSettings(BaseModel):
    """HTTP server configuration."""

    host: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=8080, description="Server port")
    workers: int = Field(default=4, description="Number of worker processes")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")


class AISettings(BaseModel):
    """WisModel configuration.

    OpenSift uses WisModel for two core tasks:
      1. Query Planning — generating search queries and screening criteria
      2. Result Verification — validating papers against criteria

    WisModel is the only supported model, specifically trained via SFT + GRPO
    with state-of-the-art query-planning and result-verification capabilities.
    """

    api_key: str = Field(default="", description="WisModel API key")
    model_planner: str = Field(
        default="WisModel-20251110",
        description="WisModel version for query planning / criteria generation",
    )
    model_verifier: str = Field(
        default="WisModel-20251110",
        description="WisModel version for result verification",
    )
    base_url: str = Field(
        default="http://wis-apihub-v2.dev.atominnolab.com/api/v1/resource/WisModel/v1",
        description="WisModel API endpoint",
    )
    max_tokens: int = Field(default=4096, description="Maximum tokens per LLM call")
    temperature: float = Field(default=0.1, description="LLM temperature for generation")


class AdapterConfig(BaseModel):
    """Configuration for a single search adapter."""

    enabled: bool = Field(default=True, description="Whether this adapter is active")
    hosts: list[str] = Field(default_factory=list, description="Backend host URLs")
    index_pattern: str = Field(default="*", description="Index/collection pattern")
    username: str | None = Field(default=None, description="Authentication username")
    password: str | None = Field(default=None, description="Authentication password")
    api_key: str | None = Field(default=None, description="API key authentication")
    extra: dict[str, Any] = Field(default_factory=dict, description="Adapter-specific options")

    @field_validator("hosts", mode="before")
    @classmethod
    def _parse_hosts(cls, v: Any) -> list[str]:
        """Parse hosts from JSON string (env var) or list."""
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(h) for h in parsed]
            except (json.JSONDecodeError, TypeError):
                pass
            # Single host as plain string
            return [v] if v else []
        return list(v)


class SearchSettings(BaseModel):
    """Search behavior configuration."""

    default_adapter: str = Field(default="atomwalker", description="Default search adapter name")
    adapters: dict[str, AdapterConfig] = Field(default_factory=dict, description="Adapter configurations")
    max_concurrent_queries: int = Field(default=10, description="Max concurrent sub-queries")


class ObservabilitySettings(BaseModel):
    """Observability configuration."""

    log_level: str = Field(default="info", description="Log level: debug, info, warning, error")
    log_format: str = Field(default="json", description="Log format: json, console")


class Settings(BaseSettings):
    """Root application settings.

    Configuration is loaded from environment variables with the OPENSIFT_ prefix.
    Nested settings use double underscores: OPENSIFT_SERVER__PORT=9090

    Example:
        OPENSIFT_SERVER__PORT=9090
        OPENSIFT_AI__API_KEY=sk-...
        OPENSIFT_SEARCH__DEFAULT_ADAPTER=atomwalker
    """

    model_config = {
        "env_prefix": "OPENSIFT_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    # Application metadata
    app_name: str = Field(default="OpenSift", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")

    # Component settings
    server: ServerSettings = Field(default_factory=ServerSettings)
    ai: AISettings = Field(default_factory=AISettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Settings:
        """Load settings from a YAML configuration file.

        Values from the YAML file are used as defaults; environment variables
        still take precedence.

        Args:
            path: Path to the YAML config file.

        Returns:
            Populated Settings instance.
        """
        import yaml  # type: ignore[import-untyped]

        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)
