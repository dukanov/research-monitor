"""CLI entry point for research monitor."""

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer

from research_monitor.adapters.digest import MarkdownDigestGenerator
from research_monitor.adapters.llm import ClaudeClient
from research_monitor.adapters.notifications import SlackNotifier
from research_monitor.adapters.sources import (
    ArXivRSSSource,
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
    no_slack: bool = typer.Option(False, "--no-slack", help="Disable Slack notifications"),
) -> None:
    """Monitor speech synthesis research updates and generate digest."""
    asyncio.run(async_run(days, output, debug, no_slack))


def app() -> None:
    """CLI entry point."""
    typer.run(main)


async def async_run(days: int, output: Optional[Path], debug: bool, no_slack: bool) -> None:
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
        print(f"  ✓ GitHub Token - для парсинга GitHub feed")
    else:
        print(f"  ⚠️  GitHub Token - не найден (ограниченный rate limit)")
    
    if no_slack:
        print(f"  ⚠️  SLACK_WEBHOOK_URL - отключен опцией --no-slack")
    elif settings.slack_webhook_url:
        print(f"  ✓ SLACK_WEBHOOK_URL - для отправки уведомлений")
    else:
        print(f"  ⚠️  SLACK_WEBHOOK_URL - не найден (уведомления отключены)")
    
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
    sources = []
    
    # Get shared keywords for filtering
    speech_keywords = settings.speech_keywords
    
    # ArXiv RSS (if enabled)
    if settings.arxiv_enabled:
        sources.append(
            ArXivRSSSource(
                categories=settings.arxiv_categories,
                max_items=settings.arxiv_max_items,
                filter_by_keywords=settings.arxiv_filter_by_keywords,
                keywords=speech_keywords,
            )
        )
    
    # GitHub
    sources.append(
        GitHubSource(
            token=settings.github_token,
            max_items=settings.max_items_per_source,
            topics=settings.github_topics,
            keywords=settings.github_keywords,
            search_days=settings.github_search_days,
            min_stars=settings.github_min_stars,
            request_delay=settings.github_request_delay,
        )
    )
    
    # HuggingFace Papers
    sources.append(
        HFPapersSource(
            max_items=settings.max_items_per_source,
            search_days=settings.hf_papers_search_days,
            keywords=speech_keywords,
        )
    )
    
    # HuggingFace Trending
    sources.append(
        HFTrendingSource(
            max_items=settings.max_items_per_source,
            max_days_old=settings.hf_models_max_days_old
        )
    )
    
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
    
    # Initialize notification service if webhook is configured and not disabled
    notification_service = SlackNotifier(settings.slack_webhook_url) if (settings.slack_webhook_url and not no_slack) else None
    
    digest_service = DigestService(
        llm_client=llm_client,
        digest_generator=digest_generator,
        notification_service=notification_service,
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
    
    digest, entries = await digest_service.generate_digest(relevant_results, digest_date)
    
    # Save digest
    if output is None:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output = settings.full_digests_dir / f"{timestamp}_digest.md"
    
    digest_service.save_digest(digest, output)
    
    # Generate digest summary
    print("\n" + "=" * 70)
    print("✨ ЭТАП 5: ГЕНЕРАЦИЯ КРАТКОГО САММАРИ")
    print("=" * 70)
    print(f"Создание краткого саммари в стиле Telegram-каналов...")
    
    try:
        digest_summary = await digest_service.generate_digest_summary(entries)
        
        # Save digest summary to summary directory with same timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        summary_output = settings.summary_digests_dir / f"{timestamp}_summary.md"
        digest_service.save_digest(digest_summary, summary_output)
        print(f"✓ Саммари сохранен: {summary_output}")
        
        # Send notification if configured
        if notification_service:
            await digest_service.send_notification(digest_summary, digest_date)
    except Exception as e:
        print(f"⚠️  Ошибка при генерации саммари: {e}")
    
    # Save artifacts ONLY after successful digest generation
    monitoring_service.save_artifacts(all_filter_results)
    
    print("\n" + "=" * 70)
    print(f"✅ ГОТОВО!")
    print("=" * 70)
    print(f"📄 Дайджест сохранен: {output}")
    if 'summary_output' in locals():
        print(f"✨ Саммари сохранен: {summary_output}")
    if debug:
        print(f"🔍 Debug данные: {settings.debug_dir}/")
    print()


if __name__ == "__main__":
    app()

