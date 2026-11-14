"""
HILTRON FalakHub — Official Google GenAI SDK Provider (Gemini 2.0).
Supports Asynchronous Generation, Streaming, and Google Search Grounding.
"""

import os
import time
import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator

from ai.llm.base import LLMProvider, LLMResult

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        timeout: float = 8.0
    ):
        super().__init__(name="gemini", model=model, timeout=timeout)
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self._client: Optional[Any] = None
        if self.api_key and genai is not None:
            self._client = genai.Client(api_key=self.api_key)

    def is_available(self) -> bool:
        return bool(self.api_key and self._client is not None)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Any]:
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "").strip()
            if not content:
                continue
            gemini_role = "user" if role in ["user", "human"] else "model"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part.from_text(text=content)]
                )
            )
        return contents

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_grounding: bool = False,
        temperature: float = 0.7,
        max_output_tokens: int = 300,
        **opts
    ) -> LLMResult:
        if not self.is_available():
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                error="GEMINI_API_KEY is not configured or google-genai SDK not available.",
                is_success=False
            )

        start_time = time.perf_counter()
        try:
            contents = self._convert_messages(messages)
            if not contents:
                return LLMResult(
                    text="",
                    provider_name=self.name,
                    model_name=self.model,
                    error="Empty messages passed to Gemini.",
                    is_success=False
                )

            config_kwargs: Dict[str, Any] = {
                "system_instruction": system,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens
            }

            # Grounding with Google Search (if requested and no custom function tools)
            if enable_grounding:
                config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
            elif tools:
                # Custom tools if provided
                config_kwargs["tools"] = tools

            config = types.GenerateContentConfig(**config_kwargs)

            # Asynchronous call with timeout
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config
                ),
                timeout=self.timeout
            )

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            raw_text = response.text or ""

            # Extract Token Usage
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                usage["prompt_tokens"] = getattr(um, "prompt_token_count", 0) or 0
                usage["completion_tokens"] = getattr(um, "candidates_token_count", 0) or 0
                usage["total_tokens"] = getattr(um, "total_token_count", 0) or 0

            # Extract Grounding Sources if present
            sources: List[Dict[str, str]] = []
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                    gm = candidate.grounding_metadata
                    if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                        for chunk in gm.grounding_chunks:
                            if hasattr(chunk, "web") and chunk.web:
                                uri = getattr(chunk.web, "uri", "") or ""
                                title = getattr(chunk.web, "title", "") or uri
                                if uri:
                                    sources.append({"title": title, "uri": uri})

            return LLMResult(
                text=raw_text.strip(),
                usage=usage,
                provider_name=self.name,
                model_name=self.model,
                latency_ms=latency_ms,
                sources=sources,
                is_success=True
            )

        except asyncio.TimeoutError:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                latency_ms=latency_ms,
                error=f"Gemini API timed out after {self.timeout}s.",
                is_success=False
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                latency_ms=latency_ms,
                error=f"Gemini API error: {str(e)}",
                is_success=False
            )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        system: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_grounding: bool = False,
        temperature: float = 0.7,
        max_output_tokens: int = 300,
        **opts
    ) -> AsyncIterator[str]:
        if not self.is_available():
            return

        try:
            contents = self._convert_messages(messages)
            if not contents:
                return

            config_kwargs: Dict[str, Any] = {
                "system_instruction": system,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens
            }
            if enable_grounding:
                config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
            elif tools:
                config_kwargs["tools"] = tools

            config = types.GenerateContentConfig(**config_kwargs)

            response_stream = await self._client.aio.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config
            )

            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            # Yield nothing on error so fallback can handle or stream ends gracefully
            pass

