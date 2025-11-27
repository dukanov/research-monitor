"""Slack notification adapter."""

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
    
    async def send_digest(self, digest_summary: str, digest_date: date) -> None:
        """Send digest summary to Slack.
        
        Args:
            digest_summary: The digest summary text
            digest_date: Date of the digest
        """
        if not self.webhook_url:
            # Silently skip if no webhook configured
            return
        
        # Format message
        formatted_date = digest_date.strftime('%d.%m.%Y')
        message = f"📡 *Research Digest — {formatted_date}*\n\n{digest_summary}"
        
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

