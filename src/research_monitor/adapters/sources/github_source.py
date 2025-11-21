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
        min_stars: int = 5,
        request_delay: float = 7,
    ) -> None:
        self.token = token
        self.max_items = max_items
        self.topics = topics or []
        self.keywords = keywords or []
        self.search_days = search_days
        self.min_stars = min_stars
        self.request_delay = request_delay
        self.api_base = "https://api.github.com"
        
    async def fetch_items(self, since: date) -> list[Item]:
        """Search repositories by topics and keywords."""
        seen_urls: set[str] = set()
        items: list[Item] = []
        
        # Calculate search period (fixed search_days instead of since parameter)
        from datetime import timedelta
        search_since = date.today() - timedelta(days=self.search_days)
        
        print(f"  └─ Период поиска: {search_since.isoformat()} - {date.today().isoformat()}")
        print(f"  └─ Минимум звёзд: {self.min_stars}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = self._get_headers()
            
            total_queries = len(self.topics) + len(self.keywords)
            print(f"  └─ Запросов: {len(self.topics)} topics + {len(self.keywords)} keywords = {total_queries}")
            if not self.token and total_queries > 1:
                print(f"  └─ Задержка между запросами: {self.request_delay}s (без токена - 10 req/min)")
            
            # Search by topics
            for i, topic in enumerate(self.topics):
                if i > 0:  # Delay after first request
                    await self._rate_limit_delay()
                    
                topic_items = await self._search_by_query(
                    client, headers, f"topic:{topic}", search_since
                )
                for item in topic_items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        items.append(item)
                        
            # Search by keywords
            for keyword in self.keywords:
                await self._rate_limit_delay()
                
                keyword_items = await self._search_by_query(
                    client, headers, f"{keyword} in:description,readme", search_since
                )
                for item in keyword_items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        items.append(item)
        
        print(f"  └─ Найдено уникальных репозиториев: {len(items)}")
        
        # Sort by stars (metadata contains stars count) and limit to max_items
        items.sort(key=lambda x: int(x.metadata.get("stars", 0)), reverse=True)
        
        if len(items) > self.max_items:
            print(f"  └─ Ограничено топ-{self.max_items} по звездам")
        
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
            # Build search query with date and stars filters
            date_filter = f"created:{since.isoformat()}..{date.today().isoformat()}"
            stars_filter = f"stars:>={self.min_stars}"
            full_query = f"{query} {date_filter} {stars_filter}"
            
            # Search repositories (sorted by stars descending)
            response = await client.get(
                f"{self.api_base}/search/repositories",
                headers=headers,
                params={"q": full_query, "sort": "stars", "order": "desc", "per_page": 30},
            )
            
            if response.status_code != 200:
                print(f"  └─ ⚠️  GitHub API error: {response.status_code} for query: {query}")
                if response.status_code == 403:
                    print(f"      Rate limit или требуется аутентификация")
                return items
            
            data = response.json()
            total_count = data.get("total_count", 0)
            items_found = len(data.get("items", []))
            
            if total_count > 0:
                print(f"  └─ '{query}': {items_found} репо (всего: {total_count})")
            
            # Use data from search results directly (no additional requests needed)
            for repo in data.get("items", []):
                try:
                    item = self._create_item_from_search_result(repo)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"      ⚠️  Ошибка обработки {repo.get('full_name', '?')}: {e}")
                    
        except Exception as e:
            print(f"Error searching with query '{query}': {e}")
            
        return items
    
    def _create_item_from_search_result(self, repo: dict) -> Optional[Item]:
        """Create item from search API result (no additional requests)."""
        try:
            description = repo.get("description") or "No description"
            topics = repo.get("topics", [])
            topics_str = ", ".join(topics) if topics else "No topics"
            
            # Build content from search result data
            content = f"""Description: {description}

Topics: {topics_str}

Language: {repo.get("language", "Not specified")}
Stars: {repo.get("stargazers_count", 0)}
"""
            
            # Parse created_at as discovery time
            created_at_str = repo.get("created_at", "")
            if created_at_str:
                discovered_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            else:
                discovered_at = datetime.now(timezone.utc)
            
            return Item(
                type=ItemType.REPOSITORY,
                title=repo["full_name"],
                url=repo["html_url"],
                content=content,
                source="github_new",
                discovered_at=discovered_at,
                metadata={
                    "stars": str(repo.get("stargazers_count", 0)),
                    "language": repo.get("language", ""),
                    "created_at": repo.get("created_at", ""),
                }
            )
        except Exception as e:
            print(f"      ⚠️  Ошибка создания Item: {e}")
            return None
    
    async def _rate_limit_delay(self) -> None:
        """Apply rate limit delay between requests."""
        import asyncio
        if not self.token:
            # Without token: 10 requests per minute, need delay
            await asyncio.sleep(self.request_delay)
        else:
            # With token: 30 requests per minute, minimal delay
            await asyncio.sleep(2)
    
    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers

