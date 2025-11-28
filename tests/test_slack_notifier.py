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
        # Bold should be converted from ** to *
        assert "*Paper*" in message
        assert "*Repo*" in message


def test_convert_markdown_to_mrkdwn_links() -> None:
    """Test markdown link conversion to Slack format."""
    notifier = SlackNotifier("https://hooks.slack.com/services/test")
    
    # Test single link
    markdown = "Check out [this paper](https://arxiv.org/abs/123)"
    result = notifier._convert_markdown_to_mrkdwn(markdown)
    assert result == "Check out <https://arxiv.org/abs/123|this paper>"
    
    # Test multiple links
    markdown = "[First](http://example.com) and [Second](http://test.com)"
    result = notifier._convert_markdown_to_mrkdwn(markdown)
    assert result == "<http://example.com|First> and <http://test.com|Second>"


def test_convert_markdown_to_mrkdwn_bold() -> None:
    """Test markdown bold conversion to Slack format."""
    notifier = SlackNotifier("https://hooks.slack.com/services/test")
    
    # Test single bold
    markdown = "This is **bold text** here"
    result = notifier._convert_markdown_to_mrkdwn(markdown)
    assert result == "This is *bold text* here"
    
    # Test multiple bold
    markdown = "**First** and **Second** bold"
    result = notifier._convert_markdown_to_mrkdwn(markdown)
    assert result == "*First* and *Second* bold"


def test_convert_markdown_to_mrkdwn_combined() -> None:
    """Test combined markdown to mrkdwn conversion."""
    notifier = SlackNotifier("https://hooks.slack.com/services/test")
    
    markdown = "**Title**: Check [this link](http://example.com) with **bold text**"
    result = notifier._convert_markdown_to_mrkdwn(markdown)
    assert result == "*Title*: Check <http://example.com|this link> with *bold text*"

