# Research Monitor

A system for monitoring updates in the field of speech synthesis from various sources with automatic filtering and digest generation.

## Sources

- 📚 **ArXiv RSS** - papers from cs.SD, eess.AS, cs.CL categories (filtered by 40+ keywords)
- 🐙 **GitHub (new repos)** - search by topics and keywords, created in the last 14 days, minimum 10⭐
- 📄 **HuggingFace Papers** - papers from the last 7 days (filtered by keywords)
- 🤖 **HuggingFace Trending** - trending TTS models, updated in the last 14 days

## Installation

```bash
uv sync
```

## Configuration

1. **API keys** (only these go in environment variables):

```bash
export ANTHROPIC_API_KEY=your_key_here
export GH_PAT=your_github_token           # optional, for higher rate limit
export SLACK_WEBHOOK_URL=your_webhook_url # optional, for notifications
```

2. **Everything else in `config.yaml`**:
   - Prompts for Claude (including your interests)
   - Source settings
   - Paths and filtering parameters

## Usage

### Basic usage

Generates a digest for the last day (creates two files: full digest and brief summary):

```bash
research-monitor
```

### Available options

```bash
research-monitor [OPTIONS]

Options:
  --days INTEGER      Monitoring period in days [default: 1]
  --output PATH       Path for saving the digest [default: digests/full/YYYY-MM-DD_HH-MM-SS_digest.md]
  --debug             Enable debug mode (saves debug data to debug/)
  --help              Show help
```

### Examples

```bash
# Digest for the last week
research-monitor --days 7

# With custom output file
research-monitor --output my-digest.md

# Debug mode
research-monitor --debug
```

### Output

Each run creates two files:
- **`digests/full/YYYY-MM-DD_HH-MM-SS_digest.md`** - full digest with all details
- **`digests/summary/YYYY-MM-DD_HH-MM-SS_summary.md`** - brief summary in Telegram channel style

If `SLACK_WEBHOOK_URL` is configured, the brief summary is automatically sent to Slack.

### Viewing results

```bash
# View full digests
ls -lt digests/full/

# View summaries
ls -lt digests/summary/

# Read the latest summary
cat digests/summary/$(ls -t digests/summary/ | head -1)

# View artifacts (parser findings)
ls -la artifacts/*/*.yaml
```

## How the system works

### Workflow

1. **Data collection** - sources gather new materials
2. **Deduplication** - check against artifacts, skip already seen URLs
3. **Claude filtering** - relevance scoring (70% threshold)
4. **Artifact saving** - relevant findings → YAML files
5. **Digest generation** - full digest + brief summary

### Artifacts (source findings)

Each finding is saved as a YAML file in `artifacts/`:

```
artifacts/
├── arxiv_rss/           # ArXiv papers
├── github_new/          # New repositories
├── huggingface_papers/  # HF papers
└── huggingface_trending/# Trending models
```

**Purpose:**
- 👀 **Transparency** - see what sources collect
- ♻️ **Deduplication** - automatic skip of already seen items (by URL)
- 📚 **History** - revisit past findings
- 🔍 **Debugging** - easy to inspect contents

**Artifact format:**

```yaml
title: Paper or Repository Title
url: https://...
type: paper/model/repository
source: github_new/arxiv_rss/etc
published_at: "2025-11-27"
relevance_score: 0.85
relevance_reason: "Description of why it's relevant"
summary: "Brief description"
highlights:
  - "Key point 1"
  - "Key point 2"
content: "Full text..."
```

## Architecture

The project follows Clean Architecture principles:

```
core/
  entities.py      # Domain entities (Item, FilterResult, DigestEntry)
  interfaces.py    # Port interfaces (ItemSource, LLMClient, DigestGenerator)
  seen_tracker.py  # Tracking seen items to avoid duplicates

adapters/
  sources/         # Source implementations (ItemSource)
    arxiv_rss_source.py      # ArXiv RSS feeds
    github_source.py         # GitHub search
    hf_papers_source.py      # HuggingFace papers
    hf_trending_source.py    # HuggingFace trending models
    filters.py               # Keyword filtering helpers
  llm/             # LLM client implementation (LLMClient)
    claude_client.py
  digest/          # Digest generator (DigestGenerator)
    markdown_generator.py
  notifications/   # Notification service implementations (NotificationService)
    slack_notifier.py        # Slack webhook notifications

use_cases.py       # Business logic (MonitoringService, DigestService)
config.py          # Configuration management
cli.py             # CLI entry point
```

## Rate limit handling

The system automatically handles rate limits from Claude API:
- Request batching (2 concurrent by default)
- Minimum delay between requests (1.5s)
- Retry with exponential backoff on 429 errors (starting at 2s)
- Up to 5 retry attempts

Rate limit settings are hardcoded in `config.py` for stable operation.

See also: [USAGE.md](USAGE.md)

## GitHub Actions automation

Configured to run automatically every day at 10:00 UTC:
- 📡 Collects new materials
- 💾 Commits artifacts and digests
- 💬 Sends summary to Slack

**Setting up secrets:**

In Settings → Secrets and variables → Actions add:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for filtering |
| `SLACK_WEBHOOK_URL` | Optional | Webhook for sending to Slack |
| `GH_PAT` | Optional | Personal Access Token for GitHub (higher rate limit) |

See also: [.github/SETUP.md](.github/SETUP.md)

## Testing

```bash
pytest
```
