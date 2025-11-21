"""GitHub source for monitoring repositories by topics and keywords."""

from datetime import date, datetime, timezone
from typing import Optional

import httpx

from research_monitor.core import Item, ItemSource, ItemType


class GitHubSource(ItemSource):
    """Search GitHub repositories by topics and keywords."""
    
    emoji = "🐙"
    name = "GitHub (новые репо)"
    
    def __init__(
        self,
        token: Optional[str] = None,
        max_items: int = 50,
        topics: Optional[list[str]] = None,
        keywords: Optional[list[str]] = None,
        search_days: int = 14,
    ) -> None:
        self.token = token
        self.max_items = max_items
        self.topics = topics or []
        self.keywords = keywords or []
        self.search_days = search_days
        self.api_base = "https://api.github.com"
        
    async def fetch_items(self, since: date) -> list[Item]:
        """Search repositories by topics and keywords."""
        seen_urls: set[str] = set()
        items: list[Item] = []
        
        # Calculate search period (fixed search_days instead of since parameter)
        from datetime import timedelta
        search_since = date.today() - timedelta(days=self.search_days)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = self._get_headers()
            
            # Search by topics
            for topic in self.topics:
                topic_items = await self._search_by_query(
                    client, headers, f"topic:{topic}", search_since
                )
                for item in topic_items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        items.append(item)
                        
            # Search by keywords
            for keyword in self.keywords:
                keyword_items = await self._search_by_query(
                    client, headers, f"{keyword} in:description,readme", search_since
                )
                for item in keyword_items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        items.append(item)
        
        # Sort by stars (metadata contains stars count) and limit to max_items
        items.sort(key=lambda x: int(x.metadata.get("stars", 0)), reverse=True)
        return items[:self.max_items]
    
    async def _search_by_query(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        query: str,
        since: date,
    ) -> list[Item]:
        """Execute a search query and return items."""
        items: list[Item] = []
        
        try:
            # Build search query with date filter (by creation date)
            date_filter = f"created:{since.isoformat()}..{date.today().isoformat()}"
            full_query = f"{query} {date_filter}"
            
            # Search repositories (sorted by stars descending)
            response = await client.get(
                f"{self.api_base}/search/repositories",
                headers=headers,
                params={"q": full_query, "sort": "stars", "order": "desc", "per_page": 30},
            )
            
            if response.status_code != 200:
                return items
            
            data = response.json()
            
            for repo in data.get("items", []):
                # Fetch full repo details including README
                repo_item = await self._fetch_repo_details(
                    client, repo["full_name"], headers
                )
                if repo_item:
                    items.append(repo_item)
                    
        except Exception as e:
            print(f"Error searching with query '{query}': {e}")
            
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
            
            # Parse updated_at as discovery time
            updated_at = datetime.fromisoformat(
                repo["updated_at"].replace("Z", "+00:00")
            )
            
            return Item(
                type=ItemType.REPOSITORY,
                title=repo["full_name"],
                url=repo["html_url"],
                content=content,
                source="github_new",
                discovered_at=updated_at,
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

