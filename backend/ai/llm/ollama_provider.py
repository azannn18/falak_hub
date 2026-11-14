"""
HILTRON FalakHub — Local Ollama Provider.
Connects to local Ollama instance on http://localhost:11434.
Automatically probes availability; active only when Ollama is detected running.
"""

import os
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncIterator

from ai.llm.base import LLMProvider, LLMResult


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: str = "llama3.2",
        timeout: float = 10.0
    ):
        super().__init__(name="ollama", model=model, timeout=timeout)
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self._last_probe_time: float = 0.0
        self._is_server_up: bool = False
        self._probe_ttl_sec: float = 30.0

    async def check_server_health(self) -> bool:
        """Lightweight probe to check if Ollama daemon is running on localhost."""
        now = time.time()
        if now - self._last_probe_time < self._probe_ttl_sec:
            return self._is_server_up

        self._last_probe_time = now
        try:
            async with httpx.AsyncClient(timeout=0.6) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                self._is_server_up = (res.status_code == 200)
        except Exception:
            self._is_server_up = False

        return self._is_server_up

    def is_available(self) -> bool:
        """Returns True if Ollama was detected running during recent probe."""
        # Note: router will also call check_server_health() asynchronously
        return self._is_server_up

    def _prepare_messages(self, messages: List[Dict[str, str]], system: str) -> List[Dict[str, str]]:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "").strip()
            if content:
                formatted.append({
                    "role": "assistant" if role in ["assistant", "model"] else "user",
                    "content": content
                })
        return formatted

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
        is_up = await self.check_server_health()
        if not is_up:
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                error=f"Ollama server not reachable at {self.base_url}.",
                is_success=False
            )

        start_time = time.perf_counter()
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages, system),
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_output_tokens
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if res.status_code != 200:
                    return LLMResult(
                        text="",
                        provider_name=self.name,
                        model_name=self.model,
                        latency_ms=latency_ms,
                        error=f"Ollama returned HTTP {res.status_code}: {res.text[:150]}",
                        is_success=False
                    )

                data = res.json()
                reply_text = data.get("message", {}).get("content", "") or ""
                prompt_eval = data.get("prompt_eval_count", 0)
                eval_count = data.get("eval_count", 0)

                return LLMResult(
                    text=reply_text.strip(),
                    usage={
                        "prompt_tokens": prompt_eval,
                        "completion_tokens": eval_count,
                        "total_tokens": prompt_eval + eval_count
                    },
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
                error=f"Timeout after {self.timeout}s calling Ollama.",
                is_success=False
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                latency_ms=latency_ms,
                error=f"Ollama error: {str(e)}",
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
        is_up = await self.check_server_health()
        if not is_up:
            return

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages, system),
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_output_tokens
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception:
            pass

