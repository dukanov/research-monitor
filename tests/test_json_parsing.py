"""Tests for JSON parsing in Claude client."""

import json

import pytest

from research_monitor.adapters.llm import ClaudeClient
from research_monitor.config import Settings


@pytest.fixture
def claude_client() -> ClaudeClient:
    """Create Claude client instance for testing."""
    settings = Settings(anthropic_api_key="test-key")
    return ClaudeClient(settings)


def test_extract_json_from_markdown(claude_client: ClaudeClient) -> None:
    """Test extracting JSON from markdown code block."""
    text = '```json\n{"is_relevant": true, "score": 0.8}\n```'
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is True
    assert parsed["score"] == 0.8


def test_extract_json_from_markdown_without_language(claude_client: ClaudeClient) -> None:
    """Test extracting JSON from markdown code block without language tag."""
    text = '```\n{"is_relevant": false, "score": 0.2}\n```'
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is False


def test_extract_json_from_text_with_prefix(claude_client: ClaudeClient) -> None:
    """Test extracting JSON when there's text before it."""
    text = 'Here is the analysis:\n{"is_relevant": true, "score": 0.9, "reason": "test"}'
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is True
    assert parsed["score"] == 0.9


def test_extract_json_array(claude_client: ClaudeClient) -> None:
    """Test extracting JSON array."""
    text = 'Here are the highlights:\n["highlight 1", "highlight 2", "highlight 3"]'
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert len(parsed) == 3


def test_fix_json_trailing_comma(claude_client: ClaudeClient) -> None:
    """Test fixing trailing comma in JSON."""
    text = '{"is_relevant": true, "score": 0.8,}'
    result = claude_client._fix_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is True


def test_fix_json_trailing_comma_in_array(claude_client: ClaudeClient) -> None:
    """Test fixing trailing comma in JSON array."""
    text = '["item1", "item2", "item3",]'
    result = claude_client._fix_json(text)
    parsed = json.loads(result)
    assert len(parsed) == 3


def test_extract_json_nested_object(claude_client: ClaudeClient) -> None:
    """Test extracting nested JSON object."""
    text = 'Analysis: {"data": {"is_relevant": true}, "score": 0.7}'
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["data"]["is_relevant"] is True


def test_extract_json_plain_text_fallback(claude_client: ClaudeClient) -> None:
    """Test fallback for plain text without JSON."""
    text = "This is just plain text"
    result = claude_client._extract_json(text)
    assert result == "This is just plain text"


def test_extract_json_with_newlines(claude_client: ClaudeClient) -> None:
    """Test extracting JSON with newlines."""
    text = '''```json
{
  "is_relevant": true,
  "score": 0.85,
  "reason": "Very relevant"
}
```'''
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is True
    assert parsed["score"] == 0.85


def test_extract_json_from_markdown_response(claude_client: ClaudeClient) -> None:
    """Test extracting JSON from Claude's markdown response."""
    text = '''This paper is **highly relevant** to speech synthesis research.

## Core Relevance

**Primary Focus**: Speech synthesis system.

{"is_relevant": true, "score": 0.9, "reason": "Релевантная статья"}

Additional notes...'''
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is True
    assert parsed["score"] == 0.9


def test_extract_json_with_is_relevant_field(claude_client: ClaudeClient) -> None:
    """Test extracting JSON that specifically has is_relevant field."""
    text = '''Some markdown text here
    
    And the JSON at the end:
    {"is_relevant": false, "score": 0.2, "reason": "Нерелевантно"}'''
    result = claude_client._extract_json(text)
    parsed = json.loads(result)
    assert parsed["is_relevant"] is False
    assert parsed["score"] == 0.2

