"""Slack notification adapter."""

import re
from datetime import date
from typing import Optional

import httpx

from research_monitor.core.interfaces import NotificationService


class SlackNotifier(NotificationService):
    """Send notifications to Slack via webhook."""
    
    def __init__(self, webhook_url: Optional[str] = None) -> None:
        """Initialize Slack notifier.
        
        Args:
            webhook_url: Slack webhook URL. If None, notifications are skipped.
        """
        self.webhook_url = webhook_url
    
    def _convert_markdown_to_mrkdwn(self, text: str) -> str:
        """Convert markdown to Slack mrkdwn format.
        
        Args:
            text: Markdown text
            
        Returns:
            Text in Slack mrkdwn format
        """
        # Convert markdown links [text](url) to Slack format <url|text>
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
        
        # Convert markdown bold **text** to Slack bold *text*
        text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
        
        # Italic is already the same format in both (_text_)
        
        return text
    
    async def send_digest(self, digest_summary: str, digest_date: date) -> None:
        """Send digest summary to Slack.
        
        Args:
            digest_summary: The digest summary text (in markdown)
            digest_date: Date of the digest
        """
        if not self.webhook_url:
            # Silently skip if no webhook configured
            return
        
        # Convert markdown to Slack mrkdwn format
        slack_summary = self._convert_markdown_to_mrkdwn(digest_summary)
        
        # Format message
        formatted_date = digest_date.strftime('%d.%m.%Y')
        message = f"📡 *Research Digest — {formatted_date}*\n\n{slack_summary}"
        
        # Send to Slack
        payload = {
            "text": message,
            "mrkdwn": True,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                print(f"✓ Дайджест отправлен в Slack")
            except httpx.HTTPError as e:
                print(f"⚠️  Ошибка отправки в Slack: {e}")

