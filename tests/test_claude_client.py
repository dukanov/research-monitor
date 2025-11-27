"""Tests for Claude client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from research_monitor.adapters.llm import ClaudeClient
from research_monitor.config import Settings
from research_monitor.core import DigestEntry, Item, ItemType


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        settings = Settings()
        # Set values directly in claude config object
        settings.claude.max_retries = 3
        settings.claude.initial_retry_delay = 0.1  # Faster for tests
        settings.claude.request_delay = 0.05
        return settings


@pytest.fixture
def test_item() -> Item:
    """Create test item."""
    return Item(
        type=ItemType.REPOSITORY,
        title="Test Repo",
        url="https://github.com/test/repo",
        content="Speech synthesis research",
        source="github",
        discovered_at=datetime.now(timezone.utc),
        metadata={},
    )


@pytest.mark.asyncio
async def test_check_relevance_success(mock_settings: Settings, test_item: Item) -> None:
    """Test successful relevance check."""
    client = ClaudeClient(mock_settings)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{
                "text": '{"is_relevant": true, "score": 0.9, "reason": "Test reason"}'
            }]
        }
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        result = await client.check_relevance(test_item, "test interests")
        
        assert result.is_relevant is True
        assert result.relevance_score == 0.9
        assert result.reason == "Test reason"


@pytest.mark.asyncio
async def test_check_relevance_retry_on_429(mock_settings: Settings, test_item: Item) -> None:
    """Test retry logic on 429 error."""
    client = ClaudeClient(mock_settings)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        # First call returns 429, second succeeds
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {}
        
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {
            "content": [{
                "text": '{"is_relevant": true, "score": 0.8, "reason": "After retry"}'
            }]
        }
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = [
            mock_response_429,
            mock_response_ok,
        ]
        mock_client_class.return_value = mock_client
        
        result = await client.check_relevance(test_item, "test interests")
        
        assert result.is_relevant is True
        assert result.relevance_score == 0.8
        assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_rate_limiting(mock_settings: Settings) -> None:
    """Test that requests are rate limited."""
    client = ClaudeClient(mock_settings)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "test response"}]
        }
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        import time
        start = time.time()
        
        # Make two quick requests
        await client._call_api("test", "system")
        await client._call_api("test", "system")
        
        elapsed = time.time() - start
        
        # Should take at least request_delay seconds due to rate limiting
        assert elapsed >= mock_settings.claude_request_delay


@pytest.mark.asyncio
async def test_generate_digest_summary(mock_settings: Settings, test_item: Item) -> None:
    """Test digest summary generation."""
    client = ClaudeClient(mock_settings)
    
    test_entry = DigestEntry(
        item=test_item,
        summary="Brief summary",
        relevance_score=0.9,
        highlights=["Key point 1", "Key point 2"],
    )
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{
                "text": "📄 **Test Repo** — Interesting speech synthesis research. [Link](url)"
            }]
        }
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        summary = await client.generate_digest_summary([test_entry])
        
        assert "Test Repo" in summary
        assert "📄" in summary
        assert mock_client.post.call_count == 1

