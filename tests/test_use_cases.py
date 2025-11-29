"""Tests for use cases."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from research_monitor.core import FilterResult, Item, ItemType
from research_monitor.use_cases import DigestService, MonitoringService


@pytest.mark.asyncio
async def test_monitoring_service_collect_and_filter() -> None:
    """Test monitoring service collects and filters items."""
    # Create mock source
    mock_source = AsyncMock()
    test_item = Item(
        type=ItemType.REPOSITORY,
        title="Test Repo",
        url="https://github.com/test/repo",
        content="Speech synthesis repo",
        source="github",
        discovered_at=datetime.now(timezone.utc),
        metadata={},
    )
    mock_source.fetch_items.return_value = [test_item]
    
    # Create mock LLM client
    mock_llm = AsyncMock()
    mock_llm.check_relevance.return_value = FilterResult(
        item=test_item,
        is_relevant=True,
        relevance_score=0.9,
        reason="Relevant to speech synthesis",
    )
    
    # Create service
    service = MonitoringService(
        sources=[mock_source],
        llm_client=mock_llm,
        interests="Test interests",
        relevance_threshold=0.6,
    )
    
    # Test collection and filtering
    relevant_results, all_results = await service.collect_and_filter(date.today())
    
    assert len(relevant_results) == 1
    assert len(all_results) == 1
    assert relevant_results[0].is_relevant
    assert relevant_results[0].relevance_score == 0.9
    mock_source.fetch_items.assert_called_once()
    mock_llm.check_relevance.assert_called_once()


@pytest.mark.asyncio
async def test_digest_service_generate() -> None:
    """Test digest service generates digest."""
    test_item = Item(
        type=ItemType.REPOSITORY,
        title="Test Repo",
        url="https://github.com/test/repo",
        content="Speech synthesis repo",
        source="github",
        discovered_at=datetime.now(timezone.utc),
        metadata={},
    )
    
    filter_result = FilterResult(
        item=test_item,
        is_relevant=True,
        relevance_score=0.9,
        reason="Relevant",
    )
    
    # Create mock LLM client
    mock_llm = AsyncMock()
    mock_llm.generate_summary.return_value = "Test summary"
    mock_llm.extract_highlights.return_value = ["Highlight 1", "Highlight 2"]
    
    # Create mock digest generator
    mock_generator = AsyncMock()
    mock_generator.generate.return_value = "# Test Digest"
    
    # Create service
    service = DigestService(
        llm_client=mock_llm,
        digest_generator=mock_generator,
    )
    
    # Test digest generation
    digest, entries = await service.generate_digest([filter_result], date.today())
    
    assert digest == "# Test Digest"
    assert len(entries) == 1
    assert entries[0].item == test_item
    assert entries[0].summary == "Test summary"
    assert entries[0].highlights == ["Highlight 1", "Highlight 2"]
    mock_llm.generate_summary.assert_called_once()
    mock_llm.extract_highlights.assert_called_once()
    mock_generator.generate.assert_called_once()


@pytest.mark.asyncio
async def test_digest_service_generate_summary() -> None:
    """Test digest service generates digest summary."""
    test_item = Item(
        type=ItemType.PAPER,
        title="Test Paper",
        url="https://arxiv.org/test",
        content="Speech synthesis paper",
        source="arxiv",
        discovered_at=datetime.now(timezone.utc),
        metadata={},
    )
    
    from research_monitor.core import DigestEntry
    
    test_entry = DigestEntry(
        item=test_item,
        summary="Test summary",
        relevance_score=0.9,
        highlights=["Highlight 1", "Highlight 2"],
    )
    
    # Create mock LLM client
    mock_llm = AsyncMock()
    mock_llm.generate_digest_summary.return_value = "📄 **Test Paper** — Brief summary. [Link](url)"
    
    # Create mock digest generator
    mock_generator = AsyncMock()
    
    # Create service
    service = DigestService(
        llm_client=mock_llm,
        digest_generator=mock_generator,
    )
    
    # Test digest summary generation
    summary = await service.generate_digest_summary([test_entry])
    
    assert "Test Paper" in summary
    assert "📄" in summary
    mock_llm.generate_digest_summary.assert_called_once_with([test_entry])


@pytest.mark.asyncio
async def test_digest_service_send_notification_with_service() -> None:
    """Test digest service sends notification when notification service is configured."""
    # Create mock notification service
    mock_notifier = AsyncMock()
    
    # Create service with notification
    service = DigestService(
        llm_client=AsyncMock(),
        digest_generator=AsyncMock(),
        notification_service=mock_notifier,
    )
    
    # Test notification sending
    await service.send_notification("Test digest", date.today())
    
    mock_notifier.send_digest.assert_called_once_with("Test digest", date.today())


@pytest.mark.asyncio
async def test_digest_service_send_notification_without_service() -> None:
    """Test digest service does not fail when notification service is None."""
    # Create service without notification
    service = DigestService(
        llm_client=AsyncMock(),
        digest_generator=AsyncMock(),
        notification_service=None,
    )
    
    # Test notification sending doesn't fail
    await service.send_notification("Test digest", date.today())
    
    # Should not raise any errors

