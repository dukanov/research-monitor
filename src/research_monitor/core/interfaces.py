"""Core interfaces for adapters."""

from abc import ABC, abstractmethod
from datetime import date

from research_monitor.core.entities import DigestEntry, FilterResult, Item


class ItemSource(ABC):
    """Interface for fetching items from various sources."""
    
    @abstractmethod
    async def fetch_items(self, since: date) -> list[Item]:
        """Fetch items since given date."""
        pass


class LLMClient(ABC):
    """Interface for LLM operations."""
    
    @abstractmethod
    async def check_relevance(self, item: Item, interests: str) -> FilterResult:
        """Check if item is relevant to given interests."""
        pass
    
    @abstractmethod
    async def generate_summary(self, item: Item) -> str:
        """Generate brief summary of the item."""
        pass
    
    @abstractmethod
    async def extract_highlights(self, item: Item) -> list[str]:
        """Extract key highlights from the item."""
        pass


class DigestGenerator(ABC):
    """Interface for generating digests."""
    
    @abstractmethod
    async def generate(self, entries: list[DigestEntry], date: date) -> str:
        """Generate digest from entries."""
        pass

