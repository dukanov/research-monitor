"""Business logic use cases."""

import asyncio
import json
from datetime import date, datetime
from pathlib import Path

from research_monitor.core import (
    DigestEntry,
    DigestGenerator,
    FilterResult,
    Item,
    ItemSource,
    LLMClient,
)


class MonitoringService:
    """Service for monitoring and filtering items from various sources."""
    
    def __init__(
        self,
        sources: list[ItemSource],
        llm_client: LLMClient,
        interests: str,
        relevance_threshold: float = 0.6,
        debug_dir: Path | None = None,
        concurrent_requests: int = 5,
    ) -> None:
        self.sources = sources
        self.llm_client = llm_client
        self.interests = interests
        self.relevance_threshold = relevance_threshold
        self.debug_dir = debug_dir
        self.concurrent_requests = concurrent_requests
    
    async def collect_and_filter(self, since: date) -> list[FilterResult]:
        """Collect items from all sources and filter by relevance."""
        print("\n" + "=" * 70)
        print("📥 ЭТАП 1: СБОР ДАННЫХ ИЗ ИСТОЧНИКОВ")
        print("=" * 70)
        
        # Fetch from all sources in parallel
        all_items: list[Item] = []
        items_by_source: dict[str, list[Item]] = {}
        
        for source in self.sources:
            emoji = getattr(source, 'emoji', '🔍')
            name = getattr(source, 'name', source.__class__.__name__)
            print(f"\n{emoji} Парсинг: {name}")
            
            try:
                items = await source.fetch_items(since)
                all_items.extend(items)
                items_by_source[name] = items
                print(f"  └─ Найдено: {len(items)} элементов")
            except Exception as e:
                print(f"  └─ ❌ Ошибка: {e}")
                items_by_source[name] = []
        
        print(f"\n✓ Всего собрано: {len(all_items)} элементов")
        
        # Show summary by source
        if items_by_source:
            print("\nРаспределение по источникам:")
            for name, items in items_by_source.items():
                emoji = next((s.emoji for s in self.sources if getattr(s, 'name', '') == name), '•')
                print(f"  {emoji} {name}: {len(items)}")
        
        # Save collected items for debug
        if self.debug_dir:
            self._save_collected_items(all_items)
        
        # Filter items by relevance
        print("\n" + "=" * 70)
        print("🔍 ЭТАП 2: ФИЛЬТРАЦИЯ РЕЛЕВАНТНОСТИ (LLM)")
        print("=" * 70)
        print(f"Проверка {len(all_items)} элементов батчами по {self.concurrent_requests}")
        
        filter_results = await self._filter_items_batched(all_items)
        
        # Process all filter results
        print("\n" + "=" * 70)
        print("📊 ЭТАП 3: АГРЕГАЦИЯ РЕЗУЛЬТАТОВ")
        print("=" * 70)
        
        all_filter_results = []
        relevant_results = []
        errors = []
        
        for result in filter_results:
            if isinstance(result, Exception):
                errors.append(result)
                continue
            
            all_filter_results.append(result)
            
            if result.is_relevant and result.relevance_score >= self.relevance_threshold:
                relevant_results.append(result)
        
        # Print summary
        print(f"\n✓ Проверено элементов: {len(all_filter_results)}")
        print(f"✓ Релевантных: {len(relevant_results)}")
        print(f"✗ Нерелевантных: {len(all_filter_results) - len(relevant_results)}")
        if errors:
            print(f"⚠️  Ошибок при проверке: {len(errors)}")
        
        # Save filter results for debug
        if self.debug_dir:
            self._save_filter_results(all_filter_results, relevant_results)
        
        return relevant_results
    
    async def _filter_items_batched(self, items: list[Item]) -> list[FilterResult | Exception]:
        """Filter items in batches to avoid overwhelming the API."""
        results: list[FilterResult | Exception] = []
        
        total_batches = (len(items) + self.concurrent_requests - 1) // self.concurrent_requests
        
        for i in range(0, len(items), self.concurrent_requests):
            batch = items[i:i + self.concurrent_requests]
            batch_num = i // self.concurrent_requests + 1
            
            print(f"\n  Батч {batch_num}/{total_batches}:")
            for idx, item in enumerate(batch, 1):
                emoji = "📄" if item.type.value == "paper" else "🤖" if item.type.value == "model_card" else "💻"
                print(f"    {idx}. {emoji} {item.title[:60]}...")
            
            batch_tasks = [
                self.llm_client.check_relevance(item, self.interests)
                for item in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Show results for this batch
            relevant_in_batch = sum(1 for r in batch_results if not isinstance(r, Exception) and r.is_relevant)
            print(f"    └─ Релевантных в батче: {relevant_in_batch}/{len(batch)}")
            
            results.extend(batch_results)
        
        return results
    
    def _save_collected_items(self, items: list[Item]) -> None:
        """Save collected items to debug directory."""
        if not self.debug_dir:
            return
        
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.debug_dir / f"collected_items_{timestamp}.json"
        
        items_data = []
        for item in items:
            items_data.append({
                "type": item.type.value,
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "discovered_at": item.discovered_at.isoformat(),
                "metadata": item.metadata,
                "content_length": len(item.content),
                "content_preview": item.content[:500] + "..." if len(item.content) > 500 else item.content,
            })
        
        output_file.write_text(
            json.dumps(items_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"📁 Debug: Collected items saved to {output_file}")
    
    def _save_filter_results(
        self, all_results: list[FilterResult], relevant_results: list[FilterResult]
    ) -> None:
        """Save filter results to debug directory."""
        if not self.debug_dir:
            return
        
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save all filter results
        all_results_data = []
        for result in all_results:
            all_results_data.append({
                "title": result.item.title,
                "url": result.item.url,
                "type": result.item.type.value,
                "source": result.item.source,
                "is_relevant": result.is_relevant,
                "relevance_score": result.relevance_score,
                "reason": result.reason,
            })
        
        # Sort by relevance score
        all_results_data.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        output_file = self.debug_dir / f"filter_results_{timestamp}.json"
        output_file.write_text(
            json.dumps({
                "total_checked": len(all_results),
                "relevant_count": len(relevant_results),
                "threshold": self.relevance_threshold,
                "results": all_results_data,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"📁 Debug: Filter results saved to {output_file}")
        
        # Print detailed summary to console
        print(f"\n" + "─" * 70)
        print(f"📊 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ФИЛЬТРАЦИИ")
        print("─" * 70)
        
        if relevant_results:
            print(f"\n✓ Релевантные ({len(relevant_results)}):")
            for result in sorted(relevant_results, key=lambda x: x.relevance_score, reverse=True):
                emoji = "📄" if result.item.type.value == "paper" else "🤖" if result.item.type.value == "model_card" else "💻"
                print(f"  {emoji} [{result.relevance_score:.0%}] {result.item.title}")
                print(f"     └─ {result.reason}")
        
        not_relevant = [r for r in all_results if not r.is_relevant or r.relevance_score < self.relevance_threshold]
        if not_relevant:
            print(f"\n✗ Нерелевантные (топ-10 из {len(not_relevant)}):")
            for result in sorted(not_relevant, key=lambda x: x.relevance_score, reverse=True)[:10]:
                emoji = "📄" if result.item.type.value == "paper" else "🤖" if result.item.type.value == "model_card" else "💻"
                print(f"  {emoji} [{result.relevance_score:.0%}] {result.item.title[:60]}")
                print(f"     └─ {result.reason}")


class DigestService:
    """Service for generating digests from filtered items."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        digest_generator: DigestGenerator,
    ) -> None:
        self.llm_client = llm_client
        self.digest_generator = digest_generator
    
    async def generate_digest(
        self, filter_results: list[FilterResult], digest_date: date
    ) -> str:
        """Generate digest from filtered results."""
        # Create digest entries with summaries and highlights
        entries: list[DigestEntry] = []
        
        for result in filter_results:
            # Generate summary and highlights in parallel
            summary_task = self.llm_client.generate_summary(result.item)
            highlights_task = self.llm_client.extract_highlights(result.item)
            
            summary, highlights = await asyncio.gather(
                summary_task, highlights_task, return_exceptions=True
            )
            
            if isinstance(summary, Exception):
                summary = f"Ошибка при генерации резюме: {summary}"
            
            if isinstance(highlights, Exception):
                highlights = []
            
            entry = DigestEntry(
                item=result.item,
                summary=summary,
                relevance_score=result.relevance_score,
                highlights=highlights,
            )
            entries.append(entry)
        
        # Generate final digest
        digest = await self.digest_generator.generate(entries, digest_date)
        
        return digest
    
    def save_digest(self, digest: str, output_path: Path) -> None:
        """Save digest to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(digest, encoding="utf-8")
        print(f"Digest saved to {output_path}")

