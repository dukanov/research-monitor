"""Claude API client for relevance checking and summarization."""

import asyncio
import json
import re
from typing import Any

import httpx

from research_monitor.config import Settings
from research_monitor.core import DigestEntry, FilterResult, Item, LLMClient


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
        # Use prompt from config
        prompt_template = self.settings.prompts.relevance_check.get("user", "")
        system_prompt = self.settings.prompts.relevance_check.get("system", "")
        
        # Format prompt with item data
        prompt = prompt_template.format(
            title=item.title,
            type=item.type,
            url=item.url,
            source=item.source,
            content=item.content[:8000],
        )
        
        response = await self._call_api(prompt=prompt, system=system_prompt)
        
        # Extract JSON from markdown code block if present
        json_text = self._extract_json(response)
        
        try:
            result = json.loads(json_text)
            return FilterResult(
                item=item,
                is_relevant=result["is_relevant"],
                relevance_score=result["score"],
                reason=result["reason"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Log the problematic response
            print(f"  ⚠️  Claude вернул невалидный JSON:")
            # Show first and last part of response to see structure
            if len(response) > 500:
                print(f"     Начало ответа: {response[:250]}...")
                print(f"     Конец ответа: ...{response[-250:]}")
            else:
                print(f"     Полный ответ: {response}")
            print(f"     Извлеченный JSON: {json_text[:200]}..." if len(json_text) > 200 else f"     Извлеченный JSON: {json_text}")
            print(f"     Ошибка: {type(e).__name__}: {e}")
            
            # Fallback if LLM doesn't return proper JSON
            return FilterResult(
                item=item,
                is_relevant=False,
                relevance_score=0.0,
                reason=f"Failed to parse response: {str(e)[:100]}"
            )
    
    async def generate_summary(self, item: Item) -> str:
        """Generate brief summary of the item."""
        prompt_template = self.settings.prompts.summary.get("user", "")
        system_prompt = self.settings.prompts.summary.get("system", "")
        
        prompt = prompt_template.format(
            title=item.title,
            url=item.url,
            type=item.type,
            content=item.content[:8000],
        )
        
        return await self._call_api(prompt=prompt, system=system_prompt)
    
    async def extract_highlights(self, item: Item) -> list[str]:
        """Extract key highlights from the item."""
        prompt_template = self.settings.prompts.highlights.get("user", "")
        system_prompt = self.settings.prompts.highlights.get("system", "")
        
        prompt = prompt_template.format(
            title=item.title,
            type=item.type,
            content=item.content[:8000],
        )
        
        response = await self._call_api(prompt=prompt, system=system_prompt)
        
        # Extract JSON from markdown code block if present
        json_text = self._extract_json(response)
        
        try:
            highlights = json.loads(json_text)
            if isinstance(highlights, list):
                return [str(h) for h in highlights[:5]]
            elif isinstance(highlights, dict):
                # If dict, try to extract values
                return [str(v) for v in highlights.values()][:5]
            return [str(highlights)]
        except json.JSONDecodeError as e:
            print(f"  ⚠️  Failed to parse highlights JSON: {e}")
            print(f"     Response: {response[:200]}...")
            # If not JSON, try to split by lines or bullet points
            lines = [
                line.strip("- •*").strip()
                for line in json_text.split("\n")
                if line.strip() and not line.strip().startswith(("```", "{", "["))
            ]
            return lines[:5] if lines else ["Failed to extract highlights"]
    
    async def generate_digest_summary(self, digest_entries: list[DigestEntry]) -> str:
        """Generate brief digest summary in Telegram channel style."""
        prompt_template = self.settings.prompts.digest_summary.get("user", "")
        system_prompt = self.settings.prompts.digest_summary.get("system", "")
        
        # Prepare entries data for the prompt
        entries_data = []
        for entry in digest_entries:
            entry_data = {
                "title": entry.item.title,
                "url": entry.item.url,
                "type": entry.item.type.value,
                "summary": entry.summary,
                "relevance_score": entry.relevance_score,
            }
            entries_data.append(entry_data)
        
        prompt = prompt_template.format(
            entries_json=json.dumps(entries_data, ensure_ascii=False, indent=2),
            count=len(entries_data),
        )
        
        return await self._call_api(prompt=prompt, system=system_prompt)
    
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
    
    def _fix_json(self, text: str) -> str:
        """Try to fix common JSON issues."""
        # Remove trailing commas before } or ]
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return text
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from markdown code block or raw text."""
        # Strategy 1: Try to find JSON in markdown code block
        code_block_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if code_block_match:
            candidate = code_block_match.group(1).strip()
            return self._fix_json(candidate)
        
        # Strategy 2: Try to find JSON object with required fields (more specific)
        # Look for is_relevant field which is required in response
        json_with_fields = re.search(
            r'\{[^}]*"is_relevant"\s*:\s*(?:true|false)[^}]*\}',
            text,
            re.DOTALL
        )
        if json_with_fields:
            candidate = self._fix_json(json_with_fields.group(0))
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Try to find any JSON object or array
        json_object_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_object_match:
            candidate = self._fix_json(json_object_match.group(0))
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        
        json_array_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', text, re.DOTALL)
        if json_array_match:
            candidate = self._fix_json(json_array_match.group(0))
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Return as is (last resort)
        return self._fix_json(text.strip())

