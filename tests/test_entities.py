"""Tests for core entities."""

from datetime import datetime, timezone

import pytest

from research_monitor.core import Item, ItemType


def test_item_creation() -> None:
    """Test creating a valid item."""
    item = Item(
        type=ItemType.REPOSITORY,
        title="Test Repo",
        url="https://github.com/test/repo",
        content="Test content",
        source="github",
        discovered_at=datetime.now(timezone.utc),
        metadata={"stars": "100"},
    )
    
    assert item.title == "Test Repo"
    assert item.type == ItemType.REPOSITORY
    assert item.metadata["stars"] == "100"


def test_item_validation() -> None:
    """Test item validation."""
    with pytest.raises(ValueError, match="Title cannot be empty"):
        Item(
            type=ItemType.REPOSITORY,
            title="",
            url="https://github.com/test/repo",
            content="Test content",
            source="github",
            discovered_at=datetime.now(timezone.utc),
            metadata={},
        )
    
    with pytest.raises(ValueError, match="URL cannot be empty"):
        Item(
            type=ItemType.REPOSITORY,
            title="Test",
            url="",
            content="Test content",
            source="github",
            discovered_at=datetime.now(timezone.utc),
            metadata={},
        )

