"""CLI entry point for research monitor."""

import asyncio
from datetime import date, timedelta
from pathlib import Path

import typer

from research_monitor.adapters.digest import MarkdownDigestGenerator
from research_monitor.adapters.llm import ClaudeClient
from research_monitor.adapters.sources import (
    GitHubSource,
    HFPapersSource,
    HFTrendingSource,
)
from research_monitor.config import get_settings
from research_monitor.use_cases import DigestService, MonitoringService

app = typer.Typer(help="Monitor speech synthesis research updates")


@app.command()
def run(
    days: int = typer.Option(1, "--days", "-d", help="Number of days to look back"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file path"),
    debug: bool = typer.Option(False, "--debug", help="Save debug data (collected items and filter results)"),
) -> None:
    """Run monitoring and generate digest."""
    asyncio.run(async_run(days, output, debug))


async def async_run(days: int, output: Path | None, debug: bool) -> None:
    """Async implementation of run command."""
    settings = get_settings()
    
    # Header
    print("\n" + "=" * 70)
    print("🎙️  RESEARCH MONITOR - Speech Synthesis Updates")
    print("=" * 70)
    
    # Load interests
    interests = settings.load_interests()
    
    # Calculate date range
    since = date.today() - timedelta(days=days)
    digest_date = date.today()
    
    print(f"\n⚙️  Настройки:")
    print(f"  • Период: {since.strftime('%d.%m.%Y')} - {digest_date.strftime('%d.%m.%Y')} ({days} дн.)")
    print(f"  • Интересы: {settings.interests_file}")
    print(f"  • Порог релевантности: {settings.relevance_threshold:.0%}")
    print(f"  • Макс. элементов на источник: {settings.max_items_per_source}")
    print(f"  • Батч размер (LLM): {settings.concurrent_llm_requests}")
    
    if debug:
        print(f"  • 🔍 Debug mode: {settings.debug_dir}")
    
    # Initialize sources
    sources = [
        GitHubSource(token=settings.github_token, max_items=settings.max_items_per_source),
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
    
    # Initialize services
    monitoring_service = MonitoringService(
        sources=sources,
        llm_client=llm_client,
        interests=interests,
        relevance_threshold=settings.relevance_threshold,
        debug_dir=settings.debug_dir if debug else None,
        concurrent_requests=settings.concurrent_llm_requests,
    )
    
    digest_generator = MarkdownDigestGenerator()
    digest_service = DigestService(
        llm_client=llm_client,
        digest_generator=digest_generator,
    )
    
    # Collect and filter items
    filter_results = await monitoring_service.collect_and_filter(since)
    
    if not filter_results:
        print("\n" + "=" * 70)
        print("❌ НЕ НАЙДЕНО РЕЛЕВАНТНЫХ МАТЕРИАЛОВ")
        print("=" * 70)
        return
    
    # Generate digest
    print("\n" + "=" * 70)
    print("📝 ЭТАП 4: ГЕНЕРАЦИЯ ДАЙДЖЕСТА")
    print("=" * 70)
    print(f"Создание резюме и хайлайтов для {len(filter_results)} релевантных элементов...")
    
    digest = await digest_service.generate_digest(filter_results, digest_date)
    
    # Save digest
    if output is None:
        output = settings.output_dir / f"digest_{digest_date.strftime('%Y-%m-%d')}.md"
    
    digest_service.save_digest(digest, output)
    
    print("\n" + "=" * 70)
    print(f"✅ ГОТОВО!")
    print("=" * 70)
    print(f"📄 Дайджест сохранен: {output}")
    if debug:
        print(f"🔍 Debug данные: {settings.debug_dir}/")
    print()


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()
    
    print("Current configuration:")
    print(f"  Claude model: {settings.claude_model}")
    print(f"  Interests file: {settings.interests_file}")
    print(f"  Output directory: {settings.output_dir}")
    print(f"  Debug directory: {settings.debug_dir}")
    print(f"  Max items per source: {settings.max_items_per_source}")
    print(f"  Relevance threshold: {settings.relevance_threshold}")
    print(f"  GitHub token: {'✓ Set' if settings.github_token else '✗ Not set'}")
    print(f"  Anthropic API key: {'✓ Set' if settings.anthropic_api_key else '✗ Not set'}")


if __name__ == "__main__":
    app()

