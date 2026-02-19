# Setup and usage

## Environment variables (.env)

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
GITHUB_TOKEN=ghp_...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # For sending notifications to Slack
```

## Configuration

Main parameters are hardcoded in `src/research_monitor/config.py`:

```python
# Rate limiting for Claude API (optimized for stable operation)
claude_max_retries: int = 5
claude_initial_retry_delay: float = 2.0      # Initial retry delay
claude_request_delay: float = 1.5            # Minimum delay between requests

# Monitoring
max_items_per_source: int = 30               # Max items per source
relevance_threshold: float = 0.6             # Relevance threshold (0.0-1.0)
concurrent_llm_requests: int = 2             # Concurrent LLM requests

# Directories
output_dir: Path = Path("digests")
debug_dir: Path = Path("debug")
interests_file: Path = Path("interests.md")
```

To change settings, edit `config.py` directly.

## Commands

```bash
# Basic run
uv run research-monitor

# With debug
uv run research-monitor --debug

# Last week
uv run research-monitor --days 7

# Custom output file
uv run research-monitor --output my-digest.md

# Without Slack notifications
uv run research-monitor --no-slack
```

## Rate limit handling

The system handles rate limits automatically (defaults are optimized):
- Pauses between requests (1.5s)
- Sends requests in batches (2 concurrent)
- Retries on 429 errors with exponential backoff (starting at 2s)
- Reads Retry-After header from API

If rate limits still occur, change in `config.py`:
1. `concurrent_llm_requests = 1` (very slow, but reliable)
2. `claude_request_delay = 2.5` (longer delay)
3. `max_items_per_source = 15` (fewer items)
