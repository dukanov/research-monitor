"""CLI entry point for research monitor."""

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer

from research_monitor.adapters.digest import MarkdownDigestGenerator
from research_monitor.adapters.llm import ClaudeClient
from research_monitor.adapters.sources import (
    GitHubSource,
    HFPapersSource,
    HFTrendingSource,
)
from research_monitor.config import get_settings
from research_monitor.core import SeenItemsTracker
from research_monitor.use_cases import DigestService, MonitoringService


def main(
    days: int = 1,
    output: Optional[Path] = None,
    debug: bool = False,
) -> None:
    """Monitor speech synthesis research updates and generate digest."""
    asyncio.run(async_run(days, output, debug))


def app() -> None:
    """CLI entry point."""
    typer.run(main)


async def async_run(days: int, output: Optional[Path], debug: bool) -> None:
    """Async implementation of run command."""
    settings = get_settings()
    
    # Header
    print("\n" + "=" * 70)
    print("🎙️  RESEARCH MONITOR - Speech Synthesis Updates")
    print("=" * 70)
    
    # Show credentials status
    print(f"\n🔑 Креды:")
    if settings.anthropic_api_key:
        print(f"  ✓ ANTHROPIC_API_KEY - для фильтрации через Claude")
    else:
        print(f"  ✗ ANTHROPIC_API_KEY - не найден (фильтрация не будет работать)")
    
    if settings.github_token:
        print(f"  ✓ GITHUB_TOKEN - для парсинга GitHub feed")
    else:
        print(f"  ⚠️  GITHUB_TOKEN - не найден (будут собираться только публичные события)")
    
    # Calculate date range
    since = date.today() - timedelta(days=days)
    digest_date = date.today()
    
    print(f"\n⚙️  Настройки:")
    print(f"  • Период: {since.strftime('%d.%m.%Y')} - {digest_date.strftime('%d.%m.%Y')} ({days} дн.)")
    print(f"  • Порог релевантности: {settings.relevance_threshold:.0%}")
    print(f"  • Макс. элементов на источник: {settings.max_items_per_source}")
    
    if debug:
        print(f"  • 🔍 Debug mode: {settings.debug_dir}")
    
    # Initialize sources
    sources = [
        GitHubSource(
            token=settings.github_token,
            max_items=settings.max_items_per_source,
            topics=settings.github_topics,
            keywords=settings.github_keywords,
            search_days=settings.github_search_days,
        ),
        HFPapersSource(max_items=settings.max_items_per_source),
        HFTrendingSource(
            max_items=settings.max_items_per_source,
            max_days_old=settings.hf_models_max_days_old
        ),
    ]
    
    print(f"\n📡 Источники:")
    for source in sources:
        emoji = getattr(source, 'emoji', '•')
        name = getattr(source, 'name', source.__class__.__name__)
        print(f"  {emoji} {name}")
    
    # Initialize LLM client
    llm_client = ClaudeClient(settings)
    
    # Initialize seen items tracker
    seen_tracker = SeenItemsTracker(settings.artifacts_dir)
    
    # Initialize services
    monitoring_service = MonitoringService(
        sources=sources,
        llm_client=llm_client,
        interests="",  # Not used anymore, prompts are in config
        relevance_threshold=settings.relevance_threshold,
        debug_dir=settings.debug_dir if debug else None,
        seen_tracker=seen_tracker,
    )
    
    digest_generator = MarkdownDigestGenerator()
    digest_service = DigestService(
        llm_client=llm_client,
        digest_generator=digest_generator,
    )
    
    # Collect and filter items
    relevant_results, all_filter_results = await monitoring_service.collect_and_filter(since)
    
    if not relevant_results:
        print("\n" + "=" * 70)
        print("❌ НЕ НАЙДЕНО РЕЛЕВАНТНЫХ МАТЕРИАЛОВ")
        print("=" * 70)
        
        # Still save artifacts even if nothing relevant
        if all_filter_results:
            monitoring_service.save_artifacts(all_filter_results)
        
        return
    
    # Generate digest
    print("\n" + "=" * 70)
    print("📝 ЭТАП 4: ГЕНЕРАЦИЯ ДАЙДЖЕСТА")
    print("=" * 70)
    print(f"Создание резюме и хайлайтов для {len(relevant_results)} релевантных элементов...")
    
    digest = await digest_service.generate_digest(relevant_results, digest_date)
    
    # Save digest
    if output is None:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output = settings.output_dir / f"digest_{timestamp}.md"
    
    digest_service.save_digest(digest, output)
    
    # Save artifacts ONLY after successful digest generation
    monitoring_service.save_artifacts(all_filter_results)
    
    print("\n" + "=" * 70)
    print(f"✅ ГОТОВО!")
    print("=" * 70)
    print(f"📄 Дайджест сохранен: {output}")
    if debug:
        print(f"🔍 Debug данные: {settings.debug_dir}/")
    print()


if __name__ == "__main__":
    app()

