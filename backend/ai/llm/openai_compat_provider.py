"""
HILTRON FalakHub — Generic OpenAI-Compatible LLM Provider.
Used for Groq, OpenRouter, DeepSeek, Together AI, or standard OpenAI endpoints.
Fully Asynchronous via httpx, supports JSON responses and SSE streaming.
"""

import os
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncIterator

from ai.llm.base import LLMProvider, LLMResult


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        name: str = "openai_compat",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 8.0
    ):
        super().__init__(name=name, model=model, timeout=timeout)
        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("GROQ_BASE_URL")
            or "https://api.groq.com/openai/v1"
        ).rstrip("/")
        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or ""
        ).strip()

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _prepare_payload(
        self,
        messages: List[Dict[str, str]],
        system: str,
        temperature: float,
        max_output_tokens: int,
        stream: bool = False
    ) -> Dict[str, Any]:
        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "").strip()
            if content:
                formatted_messages.append({
                    "role": "assistant" if role in ["assistant", "model"] else "user",
                    "content": content
                })

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": stream
        }
        return payload

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
                error=f"{self.name} API key or base_url is not configured.",
                is_success=False
            )

        start_time = time.perf_counter()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = self._prepare_payload(messages, system, temperature, max_output_tokens, stream=False)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=headers, json=payload)
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if res.status_code != 200:
                    return LLMResult(
                        text="",
                        provider_name=self.name,
                        model_name=self.model,
                        latency_ms=latency_ms,
                        error=f"HTTP {res.status_code}: {res.text[:200]}",
                        is_success=False
                    )

                data = res.json()
                choices = data.get("choices", [])
                if not choices:
                    return LLMResult(
                        text="",
                        provider_name=self.name,
                        model_name=self.model,
                        latency_ms=latency_ms,
                        error="No choices returned from model.",
                        is_success=False
                    )

                reply_text = choices[0].get("message", {}).get("content", "") or ""
                raw_usage = data.get("usage", {})
                usage = {
                    "prompt_tokens": raw_usage.get("prompt_tokens", 0),
                    "completion_tokens": raw_usage.get("completion_tokens", 0),
                    "total_tokens": raw_usage.get("total_tokens", 0)
                }

                return LLMResult(
                    text=reply_text.strip(),
                    usage=usage,
                    provider_name=self.name,
                    model_name=self.model,
                    latency_ms=latency_ms,
                    is_success=True
                )

        except httpx.TimeoutException:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                latency_ms=latency_ms,
                error=f"Timeout after {self.timeout}s calling {self.name}.",
                is_success=False
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                latency_ms=latency_ms,
                error=f"{self.name} error: {str(e)}",
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

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = self._prepare_payload(messages, system, temperature, max_output_tokens, stream=True)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except Exception:
                            continue
        except Exception:
            pass

