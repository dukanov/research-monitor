"""HuggingFace daily papers source."""

import json
from datetime import date, datetime, timezone

import httpx
from bs4 import BeautifulSoup

from research_monitor.core import Item, ItemSource, ItemType


class HFPapersSource(ItemSource):
    """Fetch daily papers from HuggingFace."""
    
    emoji = "📄"
    name = "HuggingFace Papers"
    
    # Keywords for speech/audio filtering
    SPEECH_KEYWORDS = [
        # Core speech terms
        "speech synthesis", "text-to-speech", "tts", "vocoder", 
        "voice cloning", "voice conversion", "speech-to-speech",
        "speech generation", "neural speech",
        
        # Speech recognition
        "speech recognition", "automatic speech recognition", "asr system",
        
        # Audio/voice specific
        "audio synthesis", "acoustic model", "speaker embedding",
        "prosody", "phoneme", "mel-spectrogram", "waveform generation",
        
        # Emotional/expressive speech
        "emotional speech", "expressive speech", "speech emotion",
        "affective speech", "emotional tts",
        
        # Dubbing and translation
        "dubbing", "speech dubbing", "voice dubbing",
        "speech translation",
        
        # Zero-shot and few-shot
        "zero-shot speech", "zero-shot tts", "zero-shot voice",
        "few-shot speech", "in-context speech",
        
        # Multilingual
        "multilingual speech", "multilingual tts", "cross-lingual speech",
        
        # Music (related domain)
        "music generation", "music synthesis", "singing voice",
        "singing synthesis", "vocal synthesis",
        
        # Quality metrics
        "speech quality", "naturalness", "intelligibility",
        "speaker similarity", "voice quality",
    ]
    
    def __init__(
        self,
        max_items: int = 50,
        filter_by_keywords: bool = True,
        search_days: int = 7,
    ) -> None:
        self.max_items = max_items
        self.base_url = "https://huggingface.co"
        self.filter_by_keywords = filter_by_keywords
        self.search_days = search_days
        
    async def fetch_items(self, since: date) -> list[Item]:
        """Fetch papers from HuggingFace daily papers for last N days."""
        from datetime import timedelta
        
        items: list[Item] = []
        seen_paper_ids: set[str] = set()
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=self.search_days)
        
        print(f"  └─ Период поиска: {start_date.isoformat()} - {end_date.isoformat()} ({self.search_days} дн.)")
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                filtered_count = 0
                
                # Fetch papers for each day
                for day_offset in range(self.search_days):
                    current_date = end_date - timedelta(days=day_offset)
                    
                    # Fetch papers for this date
                    if day_offset == 0:
                        # Today: use default endpoint
                        url = f"{self.base_url}/papers"
                    else:
                        # Archive: use date parameter
                        url = f"{self.base_url}/papers?date={current_date.isoformat()}"
                    
                    response = await client.get(url)
                    
                    if response.status_code != 200:
                        print(f"  └─ {current_date}: HTTP {response.status_code}")
                        continue
                    
                    # Extract JSON data from HTML
                    papers_data = self._extract_papers_from_html(response.text)
                    
                    if not papers_data:
                        continue
                    
                    day_count = 0
                    # Process papers from this day
                    for paper_data in papers_data:
                        try:
                            paper_id = paper_data.get("paper", {}).get("id")
                            if not paper_id or paper_id in seen_paper_ids:
                                continue
                            
                            seen_paper_ids.add(paper_id)
                            
                            title = paper_data.get("title", "Unknown")
                            summary = paper_data.get("summary", "")
                            
                            # Filter by keywords if enabled
                            if self.filter_by_keywords:
                                if not self._is_speech_related(title, summary):
                                    filtered_count += 1
                                    continue
                            
                            # Stop if we have enough items
                            if len(items) >= self.max_items:
                                break
                            
                            paper_url = f"{self.base_url}/papers/{paper_id}"
                            
                            # Build content from available data
                            content = f"""Title: {title}

Summary:
{summary}

Paper ID: {paper_id}
"""
                            
                            # Add upvotes and other metadata
                            upvotes = paper_data.get("paper", {}).get("upvotes", 0)
                            
                            items.append(Item(
                                type=ItemType.PAPER,
                                title=title,
                                url=paper_url,
                                content=content,
                                source="huggingface_papers",
                                discovered_at=datetime.now(timezone.utc),
                                metadata={
                                    "upvotes": str(upvotes),
                                    "paper_id": paper_id,
                                    "published_date": current_date.isoformat(),
                                }
                            ))
                            day_count += 1
                            
                        except Exception as e:
                            continue
                    
                    if day_count > 0:
                        print(f"  └─ {current_date}: найдено {day_count} релевантных")
                    
                    # Stop if we have enough items
                    if len(items) >= self.max_items:
                        break
                
                if filtered_count > 0:
                    print(f"  └─ Всего отфильтровано по ключевым словам: {filtered_count}")
                        
            except Exception as e:
                print(f"  └─ Ошибка: {e}")
        
        return items
    
    def _extract_papers_from_html(self, html: str) -> list[dict]:
        """Extract papers data from React hydration JSON in HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Find the div with data-target="DailyPapers"
            hydrate_div = soup.find("div", {"class": "SVELTE_HYDRATER", "data-target": "DailyPapers"})
            
            if not hydrate_div:
                print(f"  └─ DailyPapers div не найден")
                return []
            
            data_props = hydrate_div.get("data-props")
            if not data_props:
                print(f"  └─ data-props пуст")
                return []
            
            # Parse JSON
            props_data = json.loads(data_props)
            
            # Extract daily papers array
            daily_papers = props_data.get("dailyPapers", [])
            
            if not daily_papers:
                print(f"  └─ dailyPapers массив пуст или отсутствует")
            
            return daily_papers
            
        except Exception as e:
            print(f"  └─ Ошибка парсинга JSON: {e}")
            return []
    
    def _is_speech_related(self, title: str, summary: str) -> bool:
        """Check if paper is related to speech/audio based on keywords."""
        text = f"{title} {summary}".lower()
        
        return any(keyword.lower() in text for keyword in self.SPEECH_KEYWORDS)

