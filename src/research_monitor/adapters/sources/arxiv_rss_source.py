"""ArXiv RSS feed source for academic papers."""

import re
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

import httpx

from research_monitor.adapters.sources.filters import is_speech_related
from research_monitor.core import Item, ItemSource, ItemType


class ArXivRSSSource(ItemSource):
    """Fetch papers from ArXiv RSS feeds."""
    
    emoji = "📚"
    name = "ArXiv RSS"
    
    # ArXiv category mappings
    CATEGORIES = {
        "cs.SD": "Sound (cs.SD)",
        "cs.CL": "Computation and Language (cs.CL)",
        "eess.AS": "Audio and Speech Processing (eess.AS)",
        "cs.LG": "Machine Learning (cs.LG)",
        "cs.AI": "Artificial Intelligence (cs.AI)",
    }
    
    def __init__(
        self,
        categories: list[str] | None = None,
        max_items: int = 50,
        filter_by_keywords: bool = True,
        keywords: list[str] | None = None,
    ) -> None:
        self.categories = categories or ["cs.SD", "eess.AS", "cs.CL"]
        self.max_items = max_items
        self.filter_by_keywords = filter_by_keywords
        self.keywords = keywords or []
        self.base_url = "http://export.arxiv.org/rss"
        
    async def fetch_items(self, since: date) -> list[Item]:
        """Fetch papers from ArXiv RSS feeds."""
        items: list[Item] = []
        seen_arxiv_ids: set[str] = set()
        
        print(f"  └─ Категории: {', '.join(self.CATEGORIES.get(cat, cat) for cat in self.categories)}")
        print(f"  └─ Фильтрация по ключевым словам: {'✓' if self.filter_by_keywords else '✗'}")
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            filtered_count = 0
            
            for category in self.categories:
                try:
                    # Fetch RSS feed
                    url = f"{self.base_url}/{category}"
                    response = await client.get(url)
                    
                    if response.status_code != 200:
                        print(f"  └─ {category}: HTTP {response.status_code}")
                        continue
                    
                    # Parse RSS/Atom feed
                    papers = self._parse_feed(response.text)
                    
                    if not papers:
                        print(f"  └─ {category}: статьи не найдены")
                        continue
                    
                    category_count = 0
                    
                    for paper in papers:
                        # Stop if we have enough items
                        if len(items) >= self.max_items:
                            break
                        
                        arxiv_id = paper.get("id", "")
                        if not arxiv_id or arxiv_id in seen_arxiv_ids:
                            continue
                        
                        seen_arxiv_ids.add(arxiv_id)
                        
                        title = paper.get("title", "Unknown")
                        abstract = paper.get("abstract", "")
                        
                        # Filter by keywords if enabled
                        if self.filter_by_keywords:
                            if not is_speech_related(title, abstract, self.keywords):
                                filtered_count += 1
                                continue
                        
                        # Build content
                        authors = paper.get("authors", [])
                        authors_str = ", ".join(authors) if authors else "Unknown"
                        
                        content = f"""Title: {title}

Authors: {authors_str}

Abstract:
{abstract}

ArXiv ID: {arxiv_id}
Published: {paper.get('published', 'Unknown')}
Categories: {paper.get('categories', 'Unknown')}
"""
                        
                        items.append(Item(
                            type=ItemType.PAPER,
                            title=title,
                            url=paper.get("link", f"https://arxiv.org/abs/{arxiv_id}"),
                            content=content,
                            source="arxiv_rss",
                            discovered_at=datetime.now(timezone.utc),
                            metadata={
                                "arxiv_id": arxiv_id,
                                "published": paper.get("published", ""),
                                "authors": authors_str,
                                "categories": paper.get("categories", ""),
                            }
                        ))
                        category_count += 1
                    
                    if category_count > 0:
                        print(f"  └─ {self.CATEGORIES.get(category, category)}: найдено {category_count} релевантных")
                    
                    # Stop if we have enough items
                    if len(items) >= self.max_items:
                        break
                        
                except Exception as e:
                    print(f"  └─ {category}: ошибка - {e}")
                    continue
            
            if filtered_count > 0:
                print(f"  └─ Всего отфильтровано по ключевым словам: {filtered_count}")
        
        return items
    
    def _parse_feed(self, xml_content: str) -> list[dict]:
        """Parse ArXiv RSS 2.0 feed XML."""
        papers = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # ArXiv uses RSS 2.0 format
            # Find all item elements (no namespace needed for RSS 2.0)
            items = root.findall('.//item')
            
            for item in items:
                try:
                    # Extract basic info
                    title_elem = item.find('title')
                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                    
                    # Description contains the abstract
                    description_elem = item.find('description')
                    description = description_elem.text if description_elem is not None and description_elem.text else ""
                    
                    # Extract abstract from description (format: "arXiv:ID Announce Type: ...\nAbstract: ...")
                    abstract = ""
                    if description:
                        # Try to extract text after "Abstract:"
                        abstract_match = re.search(r'Abstract:\s*(.*)', description, re.DOTALL)
                        if abstract_match:
                            abstract = abstract_match.group(1).strip()
                        else:
                            abstract = description
                    
                    # Get link
                    link_elem = item.find('link')
                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    
                    # Extract ArXiv ID from link or guid
                    arxiv_id = ""
                    if link:
                        # Link format: https://arxiv.org/abs/2401.12345
                        match = re.search(r'(\d+\.\d+)', link)
                        if match:
                            arxiv_id = match.group(1)
                    
                    # Get published date (pubDate in RSS)
                    pubdate_elem = item.find('pubDate')
                    published = pubdate_elem.text if pubdate_elem is not None and pubdate_elem.text else ""
                    
                    # Get categories (in RSS format)
                    categories = []
                    for category_elem in item.findall('category'):
                        if category_elem.text:
                            categories.append(category_elem.text.strip())
                    
                    # Try to extract authors from description
                    # ArXiv RSS doesn't always have separate author fields
                    authors = []
                    # Could be enhanced by parsing from description if needed
                    
                    papers.append({
                        "id": arxiv_id,
                        "title": title,
                        "abstract": abstract,
                        "link": link,
                        "published": published,
                        "authors": authors,  # Empty for RSS format
                        "categories": ", ".join(categories),
                    })
                    
                except Exception as e:
                    # Skip malformed entries
                    continue
                    
        except Exception as e:
            print(f"  └─ Ошибка парсинга XML: {e}")
        
        return papers

