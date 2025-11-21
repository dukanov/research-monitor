"""Configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ClaudeConfig:
    """Claude API settings."""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7
    max_retries: int = 5
    initial_retry_delay: float = 2.0
    request_delay: float = 1.5


@dataclass
class PathsConfig:
    """Path settings."""
    output_dir: Path = Path("digests")
    debug_dir: Path = Path("debug")
    artifacts_dir: Path = Path("artifacts")


@dataclass
class MonitoringConfig:
    """Monitoring settings."""
    max_items_per_source: int = 30
    relevance_threshold: float = 0.6
    save_debug_data: bool = False


@dataclass
class SourcesConfig:
    """Source-specific settings."""
    huggingface_papers: dict = field(default_factory=lambda: {
        "filter_by_keywords": True,
        "max_items": 50,
    })
    huggingface_trending: dict = field(default_factory=lambda: {
        "max_days_old": 14,
        "max_items": 50,
    })
    github: dict = field(default_factory=lambda: {
        "max_items": 30,
    })


@dataclass
class PromptsConfig:
    """Prompts for LLM."""
    relevance_check: dict = field(default_factory=lambda: {
        "system": "You are an expert in speech synthesis research.",
        "user": "Analyze if this is relevant: {title}\n{content}",
    })
    summary: dict = field(default_factory=lambda: {
        "system": "You are a technical writer.",
        "user": "Summarize: {title}\n{content}",
    })
    highlights: dict = field(default_factory=lambda: {
        "system": "You are a research analyst.",
        "user": "Extract highlights: {title}\n{content}",
    })


@dataclass
class Settings:
    """Application settings."""
    
    # API Keys (from environment only)
    anthropic_api_key: str = ""
    github_token: Optional[str] = None
    
    # Config sections
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    prompts: PromptsConfig = field(default_factory=PromptsConfig)
    
    # Backward compatibility properties
    @property
    def claude_model(self) -> str:
        return self.claude.model
    
    @property
    def claude_max_tokens(self) -> int:
        return self.claude.max_tokens
    
    @property
    def claude_temperature(self) -> float:
        return self.claude.temperature
    
    @property
    def claude_max_retries(self) -> int:
        return self.claude.max_retries
    
    @property
    def claude_initial_retry_delay(self) -> float:
        return self.claude.initial_retry_delay
    
    @property
    def claude_request_delay(self) -> float:
        return self.claude.request_delay
    
    @property
    def output_dir(self) -> Path:
        return self.paths.output_dir
    
    @property
    def debug_dir(self) -> Path:
        return self.paths.debug_dir
    
    @property
    def artifacts_dir(self) -> Path:
        return self.paths.artifacts_dir
    
    @property
    def max_items_per_source(self) -> int:
        return self.monitoring.max_items_per_source
    
    @property
    def relevance_threshold(self) -> float:
        return self.monitoring.relevance_threshold
    
    @property
    def save_debug_data(self) -> bool:
        return self.monitoring.save_debug_data
    
    @property
    def hf_models_max_days_old(self) -> int:
        return self.sources.huggingface_trending.get("max_days_old", 14)


def load_config(config_path: Path = Path("config.yaml")) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_settings(config_path: Path = Path("config.yaml")) -> Settings:
    """Get application settings from YAML config and environment."""
    # Load YAML config
    config = load_config(config_path)
    
    # Get API keys from environment
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    github_token = os.getenv("GITHUB_TOKEN")
    
    # Build settings
    settings = Settings(
        anthropic_api_key=anthropic_api_key,
        github_token=github_token,
    )
    
    # Apply YAML config
    if "claude" in config:
        for key, value in config["claude"].items():
            setattr(settings.claude, key, value)
    
    if "paths" in config:
        for key, value in config["paths"].items():
            setattr(settings.paths, key, Path(value))
    
    if "monitoring" in config:
        for key, value in config["monitoring"].items():
            setattr(settings.monitoring, key, value)
    
    if "sources" in config:
        settings.sources = SourcesConfig(**config["sources"])
    
    if "prompts" in config:
        settings.prompts = PromptsConfig(**config["prompts"])
    
    return settings

