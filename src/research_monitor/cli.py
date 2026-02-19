"""CLI entry point for research monitor."""

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import click

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


@click.command()
@click.option("--days", default=1, type=int, help="Number of days to look back")
@click.option("--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--no-slack", is_flag=True, help="Disable Slack notifications")
def main(days: int, output: Optional[Path], debug: bool, no_slack: bool) -> None:
    """Monitor speech synthesis research updates and generate digest."""
    asyncio.run(async_run(days, output, debug, no_slack))


def app() -> None:
    """CLI entry point."""
    main()


async def async_run(days: int, output: Optional[Path], debug: bool, no_slack: bool) -> None:
    """Async implementation of run command."""
    settings = get_settings()
    
    # Header
    print("\n" + "=" * 70)
    print("🎙️  RESEARCH MONITOR - Speech Synthesis Updates")
    print("=" * 70)
    
    # Show credentials status
    print(f"\n🔑 Credentials:")
    if settings.anthropic_api_key:
        print(f"  ✓ ANTHROPIC_API_KEY - for filtering via Claude")
    else:
        print(f"  ✗ ANTHROPIC_API_KEY - not found (filtering will not work)")

    if settings.github_token:
        print(f"  ✓ GitHub Token - for parsing GitHub feed")
    else:
        print(f"  ⚠️  GitHub Token - not found (limited rate limit)")

    if no_slack:
        print(f"  ⚠️  SLACK_WEBHOOK_URL - disabled by --no-slack option")
    elif settings.slack_webhook_url:
        print(f"  ✓ SLACK_WEBHOOK_URL - for sending notifications")
    else:
        print(f"  ⚠️  SLACK_WEBHOOK_URL - not found (notifications disabled)")
    
    # Calculate date range
    since = date.today() - timedelta(days=days)
    digest_date = date.today()
    
    print(f"\n⚙️  Settings:")
    print(f"  • Period: {since.strftime('%Y-%m-%d')} - {digest_date.strftime('%Y-%m-%d')} ({days} days)")
    print(f"  • Relevance threshold: {settings.relevance_threshold:.0%}")
    print(f"  • Max items per source: {settings.max_items_per_source}")
    
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
    
    print(f"\n📡 Sources:")
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
        print("❌ NO RELEVANT MATERIALS FOUND")
        print("=" * 70)
        
        # Still save artifacts even if nothing relevant
        if all_filter_results:
            monitoring_service.save_artifacts(all_filter_results)
        
        return
    
    # Generate digest
    print("\n" + "=" * 70)
    print("📝 STAGE 4: DIGEST GENERATION")
    print("=" * 70)
    print(f"Creating summaries and highlights for {len(relevant_results)} relevant items...")
    
    digest, entries = await digest_service.generate_digest(relevant_results, digest_date)
    
    # Save digest
    if output is None:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output = settings.full_digests_dir / f"{timestamp}_digest.md"
    
    digest_service.save_digest(digest, output)
    
    # Generate digest summary
    print("\n" + "=" * 70)
    print("✨ STAGE 5: BRIEF SUMMARY GENERATION")
    print("=" * 70)
    print(f"Creating brief summary in Telegram channel style...")
    
    try:
        digest_summary = await digest_service.generate_digest_summary(entries)
        
        # Save digest summary to summary directory with same timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        summary_output = settings.summary_digests_dir / f"{timestamp}_summary.md"
        digest_service.save_digest(digest_summary, summary_output)
        print(f"✓ Summary saved: {summary_output}")

        # Send notification if configured
        if notification_service:
            await digest_service.send_notification(digest_summary, digest_date)
    except Exception as e:
        print(f"⚠️  Error generating summary: {e}")
    
    # Save artifacts ONLY after successful digest generation
    monitoring_service.save_artifacts(all_filter_results)
    
    print("\n" + "=" * 70)
    print(f"✅ DONE!")
    print("=" * 70)
    print(f"📄 Digest saved: {output}")
    if 'summary_output' in locals():
        print(f"✨ Summary saved: {summary_output}")
    if debug:
        print(f"🔍 Debug data: {settings.debug_dir}/")
    print()


if __name__ == "__main__":
    app()

