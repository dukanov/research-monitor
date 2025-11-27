"""Business logic use cases."""

import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from research_monitor.core import (
    DigestEntry,
    DigestGenerator,
    FilterResult,
    Item,
    ItemSource,
    LLMClient,
    NotificationService,
    SeenItemsTracker,
)


class MonitoringService:
    """Service for monitoring and filtering items from various sources."""
    
    def __init__(
        self,
        sources: list[ItemSource],
        llm_client: LLMClient,
        interests: str,
        relevance_threshold: float = 0.6,
        debug_dir: Optional[Path] = None,
        seen_tracker: Optional[SeenItemsTracker] = None,
    ) -> None:
        self.sources = sources
        self.llm_client = llm_client
        self.interests = interests
        self.relevance_threshold = relevance_threshold
        self.debug_dir = debug_dir
        self.seen_tracker = seen_tracker
    
    def save_artifacts(self, filter_results: list[FilterResult]) -> None:
        """Save artifacts after successful digest generation."""
        if not self.seen_tracker or not filter_results:
            return
        
        print(f"\n💾 Сохранение {len(filter_results)} проверенных артефактов...")
        
        # Save with relevance info
        for result in filter_results:
            self.seen_tracker.mark_seen_with_relevance(
                result.item,
                is_relevant=result.is_relevant,
                relevance_score=result.relevance_score,
                reason=result.reason,
            )
        
        relevant_count = sum(1 for r in filter_results if r.is_relevant)
        print(f"✓ Артефакты сохранены в {self.seen_tracker.storage_dir}")
        print(f"  • Релевантных: {relevant_count}")
        print(f"  • Нерелевантных: {len(filter_results) - relevant_count}")
    
    async def collect_and_filter(self, since: date) -> tuple[list[FilterResult], list[FilterResult]]:
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
        
        # Filter out already seen items
        if self.seen_tracker:
            print("\n" + "=" * 70)
            print("🔍 ФИЛЬТРАЦИЯ УЖЕ ПРОСМОТРЕННЫХ")
            print("=" * 70)
            
            unseen_items, seen_count = self.seen_tracker.filter_unseen(all_items)
            
            if seen_count > 0:
                print(f"✓ Отфильтровано уже просмотренных: {seen_count}")
                print(f"✓ Новых элементов: {len(unseen_items)}")
                
                # Show stats
                stats = self.seen_tracker.get_stats()
                print(f"\nВсего в истории: {stats['total_seen']} элементов")
                if stats['by_source']:
                    for source, count in stats['by_source'].items():
                        print(f"  • {source}: {count}")
            else:
                print("✓ Все элементы новые")
            
            all_items = unseen_items
        
        # Save collected items for debug (before filtering)
        if self.debug_dir:
            self._save_collected_items(all_items)
        
        # Filter items by relevance (sequential)
        print("\n" + "=" * 70)
        print("🔍 ЭТАП 2: ФИЛЬТРАЦИЯ РЕЛЕВАНТНОСТИ (LLM)")
        print("=" * 70)
        print(f"Проверка {len(all_items)} элементов последовательно...")
        
        filter_results = await self._filter_items_sequential(all_items)
        
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
        
        # Count items marked as relevant by LLM (regardless of threshold)
        llm_relevant_count = sum(1 for r in all_filter_results if r.is_relevant)
        
        # Print summary
        print(f"\n✓ Проверено элементов: {len(all_filter_results)}")
        print(f"✓ Помечено релевантными (LLM): {llm_relevant_count}")
        print(f"✓ Прошло порог {int(self.relevance_threshold*100)}%: {len(relevant_results)}")
        print(f"✗ Нерелевантных: {len(all_filter_results) - llm_relevant_count}")
        if errors:
            print(f"⚠️  Ошибок при проверке: {len(errors)}")
        
        # Save filter results for debug
        if self.debug_dir:
            self._save_filter_results(all_filter_results, relevant_results)
        
        return relevant_results, all_filter_results
    
    async def _filter_items_sequential(self, items: list[Item]) -> list[FilterResult | Exception]:
        """Filter items one by one (easier to debug)."""
        results: list[FilterResult | Exception] = []
        
        for i, item in enumerate(items, 1):
            emoji = "📄" if item.type.value == "paper" else "🤖" if item.type.value == "model_card" else "💻"
            print(f"\n  [{i}/{len(items)}] {emoji} {item.title[:70]}...")
            print(f"  └─ URL: {item.url}")
            
            try:
                result = await self.llm_client.check_relevance(item, self.interests)
                
                if result.is_relevant:
                    print(f"  ✓ Релевантен: {result.relevance_score:.0%} - {result.reason}")
                else:
                    print(f"  ✗ Нерелевантен: {result.relevance_score:.0%} - {result.reason}")
                
                results.append(result)
            except Exception as e:
                print(f"  ⚠️  Ошибка: {e}")
                results.append(e)
        
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
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.llm_client = llm_client
        self.digest_generator = digest_generator
        self.notification_service = notification_service
    
    async def generate_digest(
        self, filter_results: list[FilterResult], digest_date: date
    ) -> tuple[str, list[DigestEntry]]:
        """Generate digest from filtered results.
        
        Returns:
            Tuple of (digest content, digest entries)
        """
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
        
        return digest, entries
    
    async def generate_digest_summary(self, entries: list[DigestEntry]) -> str:
        """Generate brief digest summary in Telegram channel style."""
        return await self.llm_client.generate_digest_summary(entries)
    
    async def send_notification(self, digest_summary: str, digest_date: date) -> None:
        """Send notification with digest summary.
        
        Args:
            digest_summary: The digest summary text
            digest_date: Date of the digest
        """
        if self.notification_service:
            await self.notification_service.send_digest(digest_summary, digest_date)
    
    def save_digest(self, digest: str, output_path: Path) -> None:
        """Save digest to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(digest, encoding="utf-8")
        print(f"Digest saved to {output_path}")

