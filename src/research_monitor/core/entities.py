"""Core domain entities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ItemType(str, Enum):
    """Type of monitored item."""
    
    REPOSITORY = "repository"
    PAPER = "paper"
    MODEL_CARD = "model_card"


@dataclass
class Item:
    """Base entity for monitored items."""
    
    type: ItemType
    title: str
    url: str
    content: str
    source: str
    discovered_at: datetime
    metadata: dict[str, str]
    
    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("Title cannot be empty")
        if not self.url:
            raise ValueError("URL cannot be empty")


@dataclass
class FilterResult:
    """Result of relevance filtering."""
    
    item: Item
    is_relevant: bool
    relevance_score: float
    reason: str
    

@dataclass
class DigestEntry:
    """Entry in the daily digest."""
    
    item: Item
    summary: str
    relevance_score: float
    highlights: list[str]

