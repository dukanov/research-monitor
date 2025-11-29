# Настройка и использование

## Переменные окружения (.env)

```bash
# Обязательно
ANTHROPIC_API_KEY=sk-ant-...

# Опционально
GITHUB_TOKEN=ghp_...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # Для отправки уведомлений в Slack
```

## Настройка параметров

Основные параметры жёстко заданы в `src/research_monitor/config.py`:

```python
# Rate limiting для Claude API (оптимизировано под стабильную работу)
claude_max_retries: int = 5
claude_initial_retry_delay: float = 2.0      # Начальная задержка при retry
claude_request_delay: float = 1.5            # Минимальная задержка между запросами

# Мониторинг
max_items_per_source: int = 30               # Макс. элементов с каждого источника
relevance_threshold: float = 0.6             # Порог релевантности (0.0-1.0)
concurrent_llm_requests: int = 2             # Одновременных запросов к LLM

# Директории
output_dir: Path = Path("digests")
debug_dir: Path = Path("debug")
interests_file: Path = Path("interests.md")
```

Если нужно изменить - редактируйте `config.py` напрямую.

## Команды

```bash
# Базовый запуск
uv run research-monitor

# С отладкой
uv run research-monitor --debug

# За последнюю неделю
uv run research-monitor --days 7

# Свой выходной файл
uv run research-monitor --output my-digest.md

# Без отправки уведомлений в Slack
uv run research-monitor --no-slack
```

## Обработка rate limits

Система автоматически (дефолтные значения оптимизированы):
- Делает паузы между запросами (1.5s)
- Отправляет запросы батчами (2 одновременно)
- Повторяет при 429 ошибке с exponential backoff (старт 2s)
- Читает Retry-After заголовок от API

Если rate limits всё равно происходят, измените в `config.py`:
1. `concurrent_llm_requests = 1` (совсем медленно, но надёжно)
2. `claude_request_delay = 2.5` (ещё больше задержка)
3. `max_items_per_source = 15` (меньше элементов)

