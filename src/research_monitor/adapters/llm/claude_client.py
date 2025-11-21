"""Claude API client for relevance checking and summarization."""

import asyncio
import json
from typing import Any

import httpx

from research_monitor.config import Settings
from research_monitor.core import FilterResult, Item, LLMClient


class ClaudeClient(LLMClient):
    """Claude API client implementation."""
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.anthropic_api_key
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens
        self.temperature = settings.claude_temperature
        self.base_url = "https://api.anthropic.com/v1"
        self.max_retries = settings.claude_max_retries
        self.initial_retry_delay = settings.claude_initial_retry_delay
        self.request_delay = settings.claude_request_delay
        self._last_request_time = 0.0
        
    async def check_relevance(self, item: Item, interests: str) -> FilterResult:
        """Check if item is relevant to given interests."""
        prompt = self._build_relevance_prompt(item, interests)
        
        response = await self._call_api(
            prompt=prompt,
            system="You are an expert in speech synthesis research. Analyze the provided content and determine its relevance to the given interests. Respond with a JSON object containing: is_relevant (boolean), score (float 0-1), and reason (string)."
        )
        
        try:
            result = json.loads(response)
            return FilterResult(
                item=item,
                is_relevant=result["is_relevant"],
                relevance_score=result["score"],
                reason=result["reason"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback if LLM doesn't return proper JSON
            return FilterResult(
                item=item,
                is_relevant=False,
                relevance_score=0.0,
                reason=f"Failed to parse relevance response: {e}"
            )
    
    async def generate_summary(self, item: Item) -> str:
        """Generate brief summary of the item."""
        prompt = f"""Content to summarize:

Title: {item.title}
URL: {item.url}
Type: {item.type}

Content:
{item.content[:8000]}

Generate a brief, informative summary in Russian (2-4 sentences) focusing on key technical contributions and practical applications."""
        
        return await self._call_api(
            prompt=prompt,
            system="You are a technical writer specializing in speech synthesis. Write concise summaries in Russian."
        )
    
    async def extract_highlights(self, item: Item) -> list[str]:
        """Extract key highlights from the item."""
        prompt = f"""Content to analyze:

Title: {item.title}
Type: {item.type}

Content:
{item.content[:8000]}

Extract 3-5 key highlights as bullet points in Russian. Focus on:
- Main technical innovations
- Practical applications
- Performance improvements
- Novel approaches

Respond with a JSON array of strings."""
        
        response = await self._call_api(
            prompt=prompt,
            system="You are a research analyst. Extract key points concisely."
        )
        
        try:
            highlights = json.loads(response)
            if isinstance(highlights, list):
                return highlights[:5]
            return [response]
        except json.JSONDecodeError:
            # If not JSON, split by lines
            lines = [line.strip("- ").strip() for line in response.split("\n") if line.strip()]
            return lines[:5]
    
    def _build_relevance_prompt(self, item: Item, interests: str) -> str:
        """Build prompt for relevance checking."""
        return f"""Analyze the following item for relevance:

INTERESTS:
{interests}

ITEM:
Title: {item.title}
Type: {item.type}
URL: {item.url}
Source: {item.source}

Content (first 8000 chars):
{item.content[:8000]}

Determine if this item is relevant to the interests described above.

Respond with JSON:
{{
    "is_relevant": true/false,
    "score": 0.0-1.0,
    "reason": "Brief explanation in Russian"
}}"""
    
    async def _call_api(self, prompt: str, system: str) -> str:
        """Call Claude API with retry logic and rate limiting."""
        # Rate limiting: ensure minimum delay between requests
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < self.request_delay:
            await asyncio.sleep(self.request_delay - time_since_last_request)
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/messages",
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "max_tokens": self.max_tokens,
                            "temperature": self.temperature,
                            "system": system,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                        },
                    )
                    
                    self._last_request_time = asyncio.get_event_loop().time()
                    
                    # Success case
                    if response.status_code == 200:
                        data = response.json()
                        return data["content"][0]["text"]
                    
                    # Rate limit - retry with backoff
                    if response.status_code == 429:
                        retry_after = self._get_retry_delay(response, attempt)
                        print(f"⏳ Rate limit hit, retrying after {retry_after:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    # Server errors - retry with backoff
                    if response.status_code >= 500:
                        retry_delay = self.initial_retry_delay * (2 ** attempt)
                        print(f"⚠️  Server error {response.status_code}, retrying after {retry_delay:.1f}s")
                        await asyncio.sleep(retry_delay)
                        continue
                    
                    # Other errors - raise immediately
                    response.raise_for_status()
                    
            except httpx.HTTPStatusError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    retry_delay = self.initial_retry_delay * (2 ** attempt)
                    print(f"⚠️  HTTP error, retrying after {retry_delay:.1f}s")
                    await asyncio.sleep(retry_delay)
                    continue
                raise
            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    retry_delay = self.initial_retry_delay * (2 ** attempt)
                    print(f"⚠️  Network error, retrying after {retry_delay:.1f}s")
                    await asyncio.sleep(retry_delay)
                    continue
                raise
        
        # If we exhausted all retries
        if last_exception:
            raise last_exception
        raise RuntimeError("Failed to call API after all retries")
    
    def _get_retry_delay(self, response: httpx.Response, attempt: int) -> float:
        """Calculate retry delay from response headers or use exponential backoff."""
        # Check for Retry-After header
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        
        # Exponential backoff
        return self.initial_retry_delay * (2 ** attempt)

