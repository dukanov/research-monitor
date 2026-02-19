# GitHub Actions Setup

## Automatic monitor execution

GitHub Action `daily-monitor.yml` automatically:
- Runs every day at 10:00 UTC
- Collects new materials
- Commits changes to `artifacts/`, `digests/full/` and `digests/summary/`
- Sends brief summary to Slack (if `SLACK_WEBHOOK_URL` is configured)

**Note:** Slack notifications are built into `research-monitor` and happen automatically when a webhook URL is present.

## Setting up secrets

Go to Settings → Secrets and variables → Actions and add the following secrets:

### 1. ANTHROPIC_API_KEY (required)

Claude API key for filtering and digest generation.

**How to get:**
1. Sign up at https://console.anthropic.com/
2. Go to API Keys
3. Create a new key
4. Copy and add to GitHub Secrets

**Format:** `sk-ant-api03-...`

### 2. GH_PAT (optional)

Personal Access Token for higher GitHub API rate limit.

**Note:** GitHub Actions automatically provides `GITHUB_TOKEN`, but it has a limited rate limit. If you need a higher limit, create a Personal Access Token.

**How to create:**
1. Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Select scope: `public_repo` (for public repositories)
4. Copy and add to GitHub Secrets as `GH_PAT`

**Format:** `ghp_...`

**Important:** You cannot use names with the `GITHUB_` prefix — it is reserved by the system.

### 3. SLACK_WEBHOOK_URL (optional)

Webhook URL for sending digests to Slack.

**How to get:**
1. Go to https://api.slack.com/apps
2. Create New App → From scratch
3. Select workspace
4. In the left menu: Incoming Webhooks → Activate
5. Add New Webhook to Workspace
6. Select channel for posting
7. Copy the Webhook URL
8. Add to GitHub Secrets

**Format:** `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`

## Manual run

You can run the workflow manually:
1. Actions → Daily Research Monitor
2. Run workflow → Run workflow

## Schedule configuration

By default, runs at 10:00 UTC. To change the time, edit the cron in `.github/workflows/daily-monitor.yml`:

```yaml
schedule:
  - cron: '0 10 * * *'  # Minutes Hours * * *
```

**Examples:**
- `0 8 * * *` — 8:00 UTC
- `30 14 * * *` — 14:30 UTC
- `0 10 * * 1-5` — 10:00 UTC weekdays only

**Time zones:**
- UTC → MSK: add 3 hours (10:00 UTC = 13:00 MSK)
- For 10:00 MSK use: `0 7 * * *`

## Checking status

After the first run, check:
1. Actions → Daily Research Monitor → Latest run
2. Review logs for each step
3. Make sure commits appear in the repository
4. Check the Slack channel

## Troubleshooting

### Error "ANTHROPIC_API_KEY not found"
- Check that the secret is added in Settings → Secrets
- Make sure the name is exactly `ANTHROPIC_API_KEY`

### GitHub API rate limit error
- Add a personal `GITHUB_TOKEN` with a higher limit
- Or increase `request_delay` in `config.yaml`

### Digest not being sent to Slack
- Check that `SLACK_WEBHOOK_URL` is added to GitHub Secrets
- Verify the webhook URL format
- Make sure the webhook is active in Slack App settings
- Check the app's permissions for the channel
- Review workflow logs: there should be a message "Digest sent to Slack"

### No new commits
- This is normal if no new relevant materials were found
- Check logs: if you see "No changes to commit", nothing new was found
- Slack notification is only sent if relevant materials were found
