"""HuggingFace trending models source."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from research_monitor.core import Item, ItemSource, ItemType


class HFTrendingSource(ItemSource):
    """Fetch trending TTS models from HuggingFace."""
    
    emoji = "🤖"
    name = "HuggingFace Trending"
    
    def __init__(self, max_items: int = 50, max_days_old: int = 14) -> None:
        self.max_items = max_items
        self.base_url = "https://huggingface.co"
        self.api_url = "https://huggingface.co/api"
        self.max_days_old = max_days_old  # Only models updated within this many days
        
    async def fetch_items(self, since: date) -> list[Item]:
        """Fetch trending text-to-speech models, filtered by last modified date."""
        items: list[Item] = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.max_days_old)
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                # Fetch models without explicit sort to get trending ones (default behavior)
                # The API returns models with trendingScore when sort is not specified
                params = {
                    "pipeline_tag": "text-to-speech",
                    "limit": 100,  # Fetch more to have enough after date filtering
                }
                
                response = await client.get(
                    f"{self.api_url}/models",
                    params=params,
                )
                
                if response.status_code != 200:
                    print(f"  └─ HTTP {response.status_code}")
                    # Fallback to scraping
                    return await self._scrape_trending_models(client, cutoff_date)
                
                models = response.json()
                
                # Sort by trendingScore if available (client-side)
                models_with_score = [m for m in models if "trendingScore" in m]
                if models_with_score:
                    models = sorted(models_with_score, key=lambda m: m.get("trendingScore", 0), reverse=True)
                
                filtered_count = 0
                
                for model in models:
                    # Stop if we have enough items
                    if len(items) >= self.max_items:
                        break
                    
                    try:
                        model_id = model.get("id") or model.get("modelId")
                        if not model_id:
                            continue
                        
                        # Filter by last modified date
                        # Need to fetch model details to get lastModified
                        model_details = await self._fetch_model_details(client, model_id)
                        
                        if not model_details:
                            continue
                        
                        last_modified_str = model_details.get("lastModified")
                        
                        if last_modified_str:
                            try:
                                last_modified = datetime.fromisoformat(
                                    last_modified_str.replace("Z", "+00:00")
                                )
                                
                                if last_modified < cutoff_date:
                                    filtered_count += 1
                                    continue
                            except Exception:
                                # If can't parse date, include the model
                                pass
                        
                        # Fetch model card content
                        model_content = await self._fetch_model_card(client, model_id)
                        
                        if model_content:
                            trending_score = model.get("trendingScore", 0)
                            items.append(Item(
                                type=ItemType.MODEL_CARD,
                                title=model_id,
                                url=f"{self.base_url}/{model_id}",
                                content=model_content,
                                source="huggingface_trending",
                                discovered_at=datetime.now(timezone.utc),
                                metadata={
                                    "likes": str(model_details.get("likes", 0)),
                                    "downloads": str(model_details.get("downloads", 0)),
                                    "trending_score": str(trending_score),
                                    "last_modified": last_modified_str if last_modified_str else "unknown",
                                }
                            ))
                    except Exception as e:
                        print(f"  └─ Ошибка обработки модели: {e}")
                        continue
                
                if filtered_count > 0:
                    print(f"  └─ Отфильтровано старых моделей (>{self.max_days_old} дней): {filtered_count}")
                        
            except Exception as e:
                print(f"  └─ Ошибка: {e}")
        
        return items
    
    async def _fetch_model_details(
        self, client: httpx.AsyncClient, model_id: str
    ) -> Optional[dict]:
        """Fetch detailed model info including lastModified."""
        try:
            response = await client.get(f"{self.api_url}/models/{model_id}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
    
    async def _fetch_model_card(
        self, client: httpx.AsyncClient, model_id: str
    ) -> Optional[str]:
        """Fetch model card content."""
        try:
            # Try to get README via API
            response = await client.get(
                f"{self.base_url}/{model_id}/raw/main/README.md"
            )
            
            if response.status_code == 200:
                return response.text[:10000]  # Limit to 10k chars
            
            # Fallback to scraping model page
            response = await client.get(f"{self.base_url}/{model_id}")
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract model card content
            model_card = soup.find("div", class_="prose") or soup.find("article")
            
            if model_card:
                return model_card.get_text(separator="\n", strip=True)[:10000]
            
            return soup.get_text(separator="\n", strip=True)[:10000]
            
        except Exception as e:
            print(f"Error fetching model card for {model_id}: {e}")
            return None
    
    async def _scrape_trending_models(
        self, client: httpx.AsyncClient, cutoff_date: datetime
    ) -> list[Item]:
        """Fallback: scrape trending models page."""
        items: list[Item] = []
        
        try:
            url = f"{self.base_url}/models?pipeline_tag=text-to-speech&sort=trending"
            response = await client.get(url)
            
            if response.status_code != 200:
                return items
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find model cards
            model_elements = soup.find_all("article", limit=self.max_items)
            
            for element in model_elements:
                try:
                    link = element.find("a", href=True)
                    if not link:
                        continue
                    
                    model_path = link["href"]
                    if model_path.startswith("/"):
                        model_path = model_path[1:]
                    
                    model_content = await self._fetch_model_card(client, model_path)
                    
                    if model_content:
                        items.append(Item(
                            type=ItemType.MODEL_CARD,
                            title=model_path,
                            url=f"{self.base_url}/{model_path}",
                            content=model_content,
                            source="huggingface_trending",
                            discovered_at=datetime.now(timezone.utc),
                            metadata={}
                        ))
                except Exception as e:
                    print(f"Error processing model element: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error scraping trending models: {e}")
        
        return items

