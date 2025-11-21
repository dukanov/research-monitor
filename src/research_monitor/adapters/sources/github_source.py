"""GitHub feed source for monitoring starred repositories."""

from datetime import date, datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from research_monitor.core import Item, ItemSource, ItemType


class GitHubSource(ItemSource):
    """Fetch repositories from GitHub feed of followed users."""
    
    emoji = "🐙"
    name = "GitHub"
    
    def __init__(self, token: Optional[str] = None, max_items: int = 50) -> None:
        self.token = token
        self.max_items = max_items
        self.api_base = "https://api.github.com"
        
    async def fetch_items(self, since: date) -> list[Item]:
        """Fetch starred repositories from followed users' feed."""
        items: list[Item] = []
        
        # Get user's feed of starred repos
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = self._get_headers()
            
            # Fetch user's timeline events (includes stars from followed users)
            response = await client.get(
                f"{self.api_base}/users/USER/received_events",
                headers=headers,
            )
            
            if response.status_code == 401:
                # Try to get current user's feed instead
                response = await client.get(
                    f"{self.api_base}/events",
                    headers=headers,
                )
            
            if response.status_code != 200:
                return items
            
            events = response.json()
            
            for event in events[:self.max_items]:
                if event.get("type") != "WatchEvent":
                    continue
                
                created_at = datetime.fromisoformat(
                    event["created_at"].replace("Z", "+00:00")
                )
                
                if created_at.date() < since:
                    continue
                
                repo_data = event.get("repo", {})
                repo_name = repo_data.get("name")
                
                if not repo_name:
                    continue
                
                # Fetch repository details
                repo_info = await self._fetch_repo_details(client, repo_name, headers)
                if repo_info:
                    items.append(repo_info)
        
        return items
    
    async def _fetch_repo_details(
        self, client: httpx.AsyncClient, repo_name: str, headers: dict[str, str]
    ) -> Optional[Item]:
        """Fetch detailed information about a repository."""
        try:
            # Get repo metadata
            repo_response = await client.get(
                f"{self.api_base}/repos/{repo_name}",
                headers=headers,
            )
            
            if repo_response.status_code != 200:
                return None
            
            repo = repo_response.json()
            
            # Get README
            readme_response = await client.get(
                f"{self.api_base}/repos/{repo_name}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw"},
            )
            
            readme_content = ""
            if readme_response.status_code == 200:
                readme_content = readme_response.text[:10000]  # Limit to 10k chars
            
            # Combine description and README
            description = repo.get("description", "")
            topics = ", ".join(repo.get("topics", []))
            
            content = f"""Description: {description}

Topics: {topics}

README:
{readme_content}
"""
            
            return Item(
                type=ItemType.REPOSITORY,
                title=repo["full_name"],
                url=repo["html_url"],
                content=content,
                source="github",
                discovered_at=datetime.now(timezone.utc),
                metadata={
                    "stars": str(repo.get("stargazers_count", 0)),
                    "language": repo.get("language", ""),
                    "updated_at": repo.get("updated_at", ""),
                }
            )
        except Exception as e:
            print(f"Error fetching repo {repo_name}: {e}")
            return None
    
    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers

