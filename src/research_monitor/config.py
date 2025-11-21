"""Configuration management."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # API Keys
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    github_token: Optional[str] = Field(None, alias="GITHUB_TOKEN")
    
    # Claude settings
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096
    claude_temperature: float = 0.7
    claude_max_retries: int = 5
    claude_initial_retry_delay: float = 2.0  # Start with 2s on first retry
    claude_request_delay: float = 1.5  # 1.5s between requests to avoid rate limits
    
    # Paths
    interests_file: Path = Field(default=Path("interests.md"))
    output_dir: Path = Field(default=Path("digests"))
    debug_dir: Path = Field(default=Path("debug"))
    
    # Monitoring settings
    max_items_per_source: int = 30  # Reduced to avoid rate limits
    relevance_threshold: float = 0.6
    save_debug_data: bool = False
    concurrent_llm_requests: int = 2  # Conservative: 2 parallel requests to avoid rate limits
    
    # Source-specific settings
    hf_models_max_days_old: int = 14  # Only models updated within last N days (2 weeks)
    
    def load_interests(self) -> str:
        """Load interests from file."""
        if not self.interests_file.exists():
            raise FileNotFoundError(f"Interests file not found: {self.interests_file}")
        return self.interests_file.read_text(encoding="utf-8")


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()

