"""Tests for ArXiv RSS source."""

import pytest
from datetime import date

from research_monitor.adapters.sources import ArXivRSSSource
from research_monitor.core import ItemType


@pytest.fixture
def source():
    """Create ArXiv RSS source instance."""
    return ArXivRSSSource(
        categories=["cs.SD"],
        max_items=5,
        filter_by_keywords=True,
        keywords=["speech", "tts", "audio", "voice"],
    )


@pytest.fixture
def source_no_filter():
    """Create ArXiv RSS source without keyword filtering."""
    return ArXivRSSSource(
        categories=["cs.SD"],
        max_items=5,
        filter_by_keywords=False,
        keywords=[],
    )


@pytest.mark.asyncio
async def test_fetch_items_with_filter(source):
    """Test fetching items with keyword filtering."""
    items = await source.fetch_items(since=date.today())
    
    # Should return some items (network dependent)
    assert isinstance(items, list)
    
    # Check structure if items found
    if items:
        item = items[0]
        assert item.type == ItemType.PAPER
        assert item.title
        assert item.url
        assert item.content
        assert item.source == "arxiv_rss"
        assert "arxiv_id" in item.metadata
        
        # Verify speech-related (should pass keyword filter)
        content_lower = f"{item.title} {item.content}".lower()
        assert any(
            keyword in content_lower 
            for keyword in ["speech", "tts", "audio", "voice", "acoustic"]
        )


@pytest.mark.asyncio
async def test_fetch_items_no_filter(source_no_filter):
    """Test fetching items without keyword filtering."""
    items = await source_no_filter.fetch_items(since=date.today())
    
    # Should return items
    assert isinstance(items, list)
    
    # Without filter, should get more diverse results
    if items:
        assert all(item.type == ItemType.PAPER for item in items)
        assert all(item.source == "arxiv_rss" for item in items)


def test_is_speech_related():
    """Test keyword matching logic."""
    from research_monitor.adapters.sources.filters import is_speech_related
    
    keywords = ["speech", "tts", "audio", "voice", "vocoder"]
    
    # Should match
    assert is_speech_related(
        "Zero-Shot Text-to-Speech Synthesis",
        "We present a novel TTS model",
        keywords
    )
    
    assert is_speech_related(
        "Some Paper",
        "emotional speech synthesis with neural vocoder",
        keywords
    )
    
    # Should not match
    assert not is_speech_related(
        "Image Classification",
        "A new CNN architecture for computer vision",
        keywords
    )


def test_parse_feed():
    """Test RSS 2.0 feed parsing."""
    source = ArXivRSSSource()
    
    # Mock RSS 2.0 feed XML (ArXiv format)
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>cs.SD updates on arXiv.org</title>
    <item>
      <title>Test Paper Title</title>
      <link>https://arxiv.org/abs/2401.12345</link>
      <description>arXiv:2401.12345v1 Announce Type: new 
Abstract: This is a test abstract about speech synthesis and neural vocoders.</description>
      <guid>oai:arXiv.org:2401.12345v1</guid>
      <category>cs.SD</category>
      <category>eess.AS</category>
      <pubDate>Mon, 15 Jan 2024 00:00:00 -0500</pubDate>
    </item>
  </channel>
</rss>
"""
    
    papers = source._parse_feed(mock_xml)
    
    assert len(papers) == 1
    paper = papers[0]
    
    assert paper["id"] == "2401.12345"
    assert paper["title"] == "Test Paper Title"
    assert "speech synthesis" in paper["abstract"]
    assert "neural vocoders" in paper["abstract"]
    assert paper["link"] == "https://arxiv.org/abs/2401.12345"
    assert paper["published"] == "Mon, 15 Jan 2024 00:00:00 -0500"
    assert "cs.SD, eess.AS" == paper["categories"]


def test_parse_feed_malformed():
    """Test parsing with malformed XML."""
    source = ArXivRSSSource()
    
    # Empty feed
    papers = source._parse_feed("")
    assert papers == []
    
    # Invalid XML
    papers = source._parse_feed("not xml")
    assert papers == []
    
    # Valid XML but no items
    papers = source._parse_feed('<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>')
    assert papers == []


def test_multiple_categories():
    """Test source with multiple categories."""
    source = ArXivRSSSource(
        categories=["cs.SD", "eess.AS", "cs.CL"],
        max_items=10,
    )
    
    assert len(source.categories) == 3
    assert "cs.SD" in source.categories
    assert "eess.AS" in source.categories
    assert "cs.CL" in source.categories


def test_filters_empty_keywords():
    """Test that empty keywords list means no filtering."""
    from research_monitor.adapters.sources.filters import is_speech_related
    
    # Empty keywords - should always return True
    assert is_speech_related(
        "Image Classification",
        "Computer vision paper",
        []
    )
    
    # With keywords - should filter
    keywords = ["speech", "audio"]
    assert not is_speech_related(
        "Image Classification",
        "Computer vision paper",
        keywords
    )
    
    assert is_speech_related(
        "Speech Synthesis",
        "Audio generation",
        keywords
    )

