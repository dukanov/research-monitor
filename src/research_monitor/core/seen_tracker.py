"""Tracker for already seen items to avoid duplicates."""

import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Set

import yaml

from research_monitor.core.entities import Item


class SeenItemsTracker:
    """Track already seen items as individual YAML artifacts."""
    
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self._ensure_structure()
    
    def _ensure_structure(self) -> None:
        """Create directory structure for artifacts."""
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories by source
            for source in ["github", "huggingface_papers", "huggingface_trending"]:
                (self.storage_dir / source).mkdir(exist_ok=True)
    
    def is_seen(self, item: Item) -> bool:
        """Check if item was already seen."""
        artifact_path = self._get_artifact_path(item)
        return artifact_path.exists()
    
    def mark_seen(self, item: Item) -> None:
        """Mark item as seen by saving artifact."""
        self._save_artifact(item)
    
    def mark_seen_with_relevance(
        self, item: Item, is_relevant: bool, relevance_score: float, reason: str
    ) -> None:
        """Mark item as seen with relevance check results."""
        self._save_artifact(item, is_relevant, relevance_score, reason)
    
    def mark_batch_seen(self, items: list[Item]) -> None:
        """Mark multiple items as seen at once."""
        for item in items:
            self._save_artifact(item)
    
    def _save_artifact(
        self,
        item: Item,
        is_relevant: Optional[bool] = None,
        relevance_score: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Save item as YAML artifact."""
        try:
            artifact_path = self._get_artifact_path(item)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare artifact data
            artifact = {
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "type": item.type.value,
                "date_discovered": item.discovered_at.isoformat(),
                "date_seen": date.today().isoformat(),
                "metadata": item.metadata,
                "content_preview": item.content[:500] if len(item.content) > 500 else item.content,
                "content_length": len(item.content),
                "llm_content_sent": min(8000, len(item.content)),  # How much was sent to LLM
            }
            
            # Add relevance data if checked
            if is_relevant is not None:
                artifact["relevance_checked"] = True
                artifact["is_relevant"] = is_relevant
                artifact["relevance_score"] = relevance_score
                artifact["reason"] = reason
            else:
                artifact["relevance_checked"] = False
            
            # Save as YAML
            with open(artifact_path, "w", encoding="utf-8") as f:
                yaml.dump(artifact, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                
        except Exception as e:
            print(f"⚠️  Warning: Could not save artifact {item.title}: {e}")
    
    def filter_unseen(self, items: list[Item]) -> tuple[list[Item], int]:
        """Filter out already seen items.
        
        Returns:
            Tuple of (unseen_items, filtered_count)
        """
        unseen = []
        filtered_count = 0
        
        for item in items:
            if self.is_seen(item):
                filtered_count += 1
            else:
                unseen.append(item)
        
        return unseen, filtered_count
    
    def _get_artifact_path(self, item: Item) -> Path:
        """Get path for artifact file."""
        # Create safe filename from title and URL hash
        safe_title = re.sub(r'[^\w\s-]', '', item.title)
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        safe_title = safe_title[:50]  # Limit length
        
        # Use URL hash for uniqueness
        url_hash = hashlib.md5(item.url.encode()).hexdigest()[:8]
        
        filename = f"{safe_title}_{url_hash}.yaml"
        
        return self.storage_dir / item.source / filename
    
    def get_stats(self) -> dict:
        """Get statistics about seen items."""
        sources = {}
        total = 0
        
        for source_dir in self.storage_dir.iterdir():
            if source_dir.is_dir():
                count = len(list(source_dir.glob("*.yaml")))
                sources[source_dir.name] = count
                total += count
        
        return {
            "total_seen": total,
            "by_source": sources,
        }
    
    def list_artifacts(self, source: Optional[str] = None, limit: int = 20) -> list[dict]:
        """List artifacts with metadata.
        
        Args:
            source: Filter by source name (None for all)
            limit: Maximum number to return
        """
        artifacts = []
        
        search_dirs = []
        if source:
            search_dir = self.storage_dir / source
            if search_dir.exists():
                search_dirs.append(search_dir)
        else:
            search_dirs = [d for d in self.storage_dir.iterdir() if d.is_dir()]
        
        for source_dir in search_dirs:
            for artifact_path in sorted(source_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True):
                if len(artifacts) >= limit:
                    break
                
                try:
                    with open(artifact_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        data["artifact_file"] = str(artifact_path.relative_to(self.storage_dir))
                        artifacts.append(data)
                except Exception:
                    continue
        
        return artifacts[:limit]
    
    def prune_old(self, days: int = 90) -> int:
        """Remove artifacts older than N days.
        
        Returns:
            Number of artifacts removed
        """
        cutoff = date.today()
        removed = 0
        
        for source_dir in self.storage_dir.iterdir():
            if not source_dir.is_dir():
                continue
            
            for artifact_path in source_dir.glob("*.yaml"):
                try:
                    with open(artifact_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        date_seen_str = data.get("date_seen")
                        
                        if not date_seen_str:
                            continue
                        
                        date_seen = date.fromisoformat(date_seen_str)
                        days_old = (cutoff - date_seen).days
                        
                        if days_old > days:
                            artifact_path.unlink()
                            removed += 1
                except Exception:
                    continue
        
        return removed

