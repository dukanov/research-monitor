# GitHub Actions Setup

## Автоматический запуск монитора

GitHub Action `daily-monitor.yml` автоматически:
- Запускается каждый день в 10:00 UTC
- Собирает новые материалы
- Коммитит изменения в `artifacts/`, `digests/full/` и `digests/summary/`
- Отправляет краткий саммари в Slack (если настроен `SLACK_WEBHOOK_URL`)

**Примечание:** Отправка в Slack встроена в `research-monitor` и происходит автоматически при наличии webhook URL.

## Настройка секретов

Перейдите в Settings → Secrets and variables → Actions и добавьте следующие секреты:

### 1. ANTHROPIC_API_KEY (обязательно)

API ключ от Claude для фильтрации и генерации дайджестов.

**Как получить:**
1. Зарегистрируйтесь на https://console.anthropic.com/
2. Перейдите в API Keys
3. Создайте новый ключ
4. Скопируйте и добавьте в GitHub Secrets

**Формат:** `sk-ant-api03-...`

### 2. GH_PAT (опционально)

Personal Access Token для повышенного rate limit GitHub API.

**Примечание:** GitHub Actions автоматически предоставляет `GITHUB_TOKEN`, но у него ограниченный rate limit. Если нужен больший лимит, создайте Personal Access Token.

**Как создать:**
1. Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Выберите scope: `public_repo` (для публичных репозиториев)
4. Скопируйте и добавьте в GitHub Secrets как `GH_PAT`

**Формат:** `ghp_...`

**Важно:** Нельзя использовать имена с префиксом `GITHUB_` - он зарезервирован системой.

### 3. SLACK_WEBHOOK_URL (опционально)

Webhook URL для отправки дайджестов в Slack.

**Как получить:**
1. Перейдите на https://api.slack.com/apps
2. Create New App → From scratch
3. Выберите workspace
4. В меню слева: Incoming Webhooks → Activate
5. Add New Webhook to Workspace
6. Выберите канал для постинга
7. Скопируйте Webhook URL
8. Добавьте в GitHub Secrets

**Формат:** `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`

## Ручной запуск

Вы можете запустить workflow вручную:
1. Actions → Daily Research Monitor
2. Run workflow → Run workflow

## Настройка расписания

По умолчанию запускается в 10:00 UTC. Чтобы изменить время, отредактируйте cron в `.github/workflows/daily-monitor.yml`:

```yaml
schedule:
  - cron: '0 10 * * *'  # Минуты Часы * * *
```

**Примеры:**
- `0 8 * * *` — 8:00 UTC
- `30 14 * * *` — 14:30 UTC
- `0 10 * * 1-5` — 10:00 UTC только по будням

**Часовые пояса:**
- UTC → MSK: добавить 3 часа (10:00 UTC = 13:00 MSK)
- Для 10:00 MSK используйте: `0 7 * * *`

## Проверка статуса

После первого запуска проверьте:
1. Actions → Daily Research Monitor → Latest run
2. Посмотрите логи каждого шага
3. Убедитесь, что коммиты появляются в репозитории
4. Проверьте канал в Slack

## Troubleshooting

### Ошибка "ANTHROPIC_API_KEY not found"
- Проверьте, что секрет добавлен в Settings → Secrets
- Убедитесь, что название точно `ANTHROPIC_API_KEY`

### Ошибка rate limit от GitHub API
- Добавьте персональный `GITHUB_TOKEN` с повышенным лимитом
- Или увеличьте `request_delay` в `config.yaml`

### Digest не отправляется в Slack
- Проверьте, что `SLACK_WEBHOOK_URL` добавлен в GitHub Secrets
- Проверьте формат webhook URL
- Убедитесь, что webhook активен в Slack App settings
- Проверьте права доступа приложения к каналу
- Посмотрите логи workflow: должно быть сообщение "✓ Дайджест отправлен в Slack"

### Нет новых коммитов
- Это нормально, если не найдено новых релевантных материалов
- Проверьте логи: если есть фраза "No changes to commit", значит ничего нового не нашлось
- Уведомление в Slack отправляется только если были найдены релевантные материалы

