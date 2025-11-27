"""Tests for Slack notifier adapter."""

from datetime import date
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from research_monitor.adapters.notifications import SlackNotifier


@pytest.mark.asyncio
async def test_send_digest_success() -> None:
    """Test successful Slack notification."""
    notifier = SlackNotifier("https://hooks.slack.com/services/test")
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        await notifier.send_digest("📄 Test summary", date(2025, 11, 27))
        
        # Verify API call
        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args.args[0] == "https://hooks.slack.com/services/test"
        
        payload = call_args.kwargs["json"]
        assert "text" in payload
        assert "Research Digest" in payload["text"]
        assert "27.11.2025" in payload["text"]
        assert "Test summary" in payload["text"]
        assert payload["mrkdwn"] is True


@pytest.mark.asyncio
async def test_send_digest_no_webhook() -> None:
    """Test that notification is skipped when no webhook is configured."""
    notifier = SlackNotifier(None)
    
    # Should not raise any errors
    await notifier.send_digest("Test summary", date(2025, 11, 27))


@pytest.mark.asyncio
async def test_send_digest_api_error() -> None:
    """Test handling of Slack API errors."""
    notifier = SlackNotifier("https://hooks.slack.com/services/test")
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=httpx.HTTPError("API Error"))
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        # Should handle error gracefully (print warning but not raise)
        await notifier.send_digest("Test summary", date(2025, 11, 27))


@pytest.mark.asyncio
async def test_send_digest_formatting() -> None:
    """Test message formatting."""
    notifier = SlackNotifier("https://hooks.slack.com/services/test")
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        summary = "📄 **Paper** — Test\n💻 **Repo** — Test"
        await notifier.send_digest(summary, date(2025, 11, 27))
        
        payload = mock_post.call_args.kwargs["json"]
        message = payload["text"]
        
        # Check formatting
        assert message.startswith("📡 *Research Digest")
        assert "27.11.2025" in message
        assert summary in message

