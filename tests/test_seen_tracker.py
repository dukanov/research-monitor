"""Tests for seen items tracker."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from research_monitor.core import Item, ItemType, SeenItemsTracker


def test_seen_tracker_basic() -> None:
    """Test basic seen tracking functionality."""
    with TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        tracker = SeenItemsTracker(storage_dir)
        
        item1 = Item(
            type=ItemType.REPOSITORY,
            title="test/repo",
            url="https://github.com/test/repo",
            content="Test content",
            source="github",
            discovered_at=datetime.now(timezone.utc),
            metadata={},
        )
        
        # Initially not seen
        assert not tracker.is_seen(item1)
        
        # Mark as seen
        tracker.mark_seen(item1)
        assert tracker.is_seen(item1)
        
        # Check artifact file exists
        artifacts = list(storage_dir.glob("github/*.yaml"))
        assert len(artifacts) == 1
        
        # Load from new tracker instance
        tracker2 = SeenItemsTracker(storage_dir)
        assert tracker2.is_seen(item1)


def test_filter_unseen() -> None:
    """Test filtering unseen items."""
    with TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        tracker = SeenItemsTracker(storage_dir)
        
        items = [
            Item(
                type=ItemType.REPOSITORY,
                title=f"test/repo{i}",
                url=f"https://github.com/test/repo{i}",
                content="Test",
                source="github",
                discovered_at=datetime.now(timezone.utc),
                metadata={},
            )
            for i in range(5)
        ]
        
        # Mark first 2 as seen
        tracker.mark_seen(items[0])
        tracker.mark_seen(items[1])
        
        # Filter
        unseen, filtered_count = tracker.filter_unseen(items)
        
        assert len(unseen) == 3
        assert filtered_count == 2
        assert items[2] in unseen
        assert items[3] in unseen
        assert items[4] in unseen

