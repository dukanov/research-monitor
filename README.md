# Research Monitor

Система мониторинга обновлений в области синтеза речи из различных источников с автоматической фильтрацией и генерацией дайджестов.

## Источники

- 🐙 **GitHub Feed** - репозитории, которые отмечают интересные пользователи
- 📄 **HuggingFace Daily Papers** - ежедневные статьи (с фильтрацией по 30+ speech/audio ключевым словам)
- 🤖 **HuggingFace Models** - трендовые TTS модели (сортировка по trending score, только обновленные за последние 2 недели)

## Установка

```bash
uv sync
```

## Конфигурация

Создайте файл `.env` и добавьте API ключи:

```bash
ANTHROPIC_API_KEY=your_key_here
GITHUB_TOKEN=your_token_here  # опционально
```

Отредактируйте `interests.md` под свои интересы.

## Использование

### Генерация дайджеста за последний день

```bash
research-monitor run
```

### За последние N дней

```bash
research-monitor run --days 7
```

### С указанием выходного файла

```bash
research-monitor run --output my-digest.md
```

### Просмотр конфигурации

```bash
research-monitor config
```

## Архитектура

```
core/
  entities.py      # Domain entities (Item, FilterResult, DigestEntry)
  interfaces.py    # Port interfaces (ItemSource, LLMClient, DigestGenerator)

adapters/
  sources/         # Source implementations
    github_source.py
    hf_papers_source.py
    hf_trending_source.py
  llm/             # LLM client implementation
    claude_client.py
  digest/          # Digest generator
    markdown_generator.py

use_cases.py       # Business logic (MonitoringService, DigestService)
config.py          # Configuration management
cli.py             # CLI entry point
```

## Обработка rate limits

Система автоматически обрабатывает rate limits от Claude API:
- Батчинг запросов (2 одновременно по умолчанию)
- Минимальная задержка между запросами (1.5s)
- Retry с exponential backoff при 429 ошибках (старт с 2s)
- До 5 повторных попыток

Настройки жёстко заданы в `config.py` для стабильной работы без rate limits.

Подробнее: [USAGE.md](USAGE.md)

## Тестирование

```bash
pytest
```

