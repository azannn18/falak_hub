"""
HILTRON FalakHub — Multi-Provider LLM Router with Layered Fallback & Circuit Breaker.
Orchestrates Gemini (primary) -> OpenAI-compatible (backup) -> Ollama (local) -> Offline Expert (fallback).
"""

import os
import time
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator

from ai.llm.base import LLMProvider, LLMResult
from ai.llm.gemini_provider import GeminiProvider
from ai.llm.openai_compat_provider import OpenAICompatProvider
from ai.llm.ollama_provider import OllamaProvider
from ai.llm.offline_provider import OfflineProvider

logger = logging.getLogger("hiltron.llm_router")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class CircuitBreaker:
    """Simple 3-state circuit breaker per provider (CLOSED, OPEN, HALF_OPEN)."""

    def __init__(self, failure_threshold: int = 3, cooldown_sec: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        # {provider_name: {"state": "CLOSED", "failures": 0, "cooldown_until": 0.0}}
        self._states: Dict[str, Dict[str, Any]] = {}

    def _get_entry(self, name: str) -> Dict[str, Any]:
        if name not in self._states:
            self._states[name] = {"state": "CLOSED", "failures": 0, "cooldown_until": 0.0}
        return self._states[name]

    def can_try(self, name: str) -> bool:
        entry = self._get_entry(name)
        now = time.time()
        if entry["state"] == "OPEN":
            if now >= entry["cooldown_until"]:
                entry["state"] = "HALF_OPEN"
                logger.info(f"[CircuitBreaker] {name} entering HALF_OPEN probe state.")
                return True
            return False
        return True

    def record_success(self, name: str):
        entry = self._get_entry(name)
        if entry["state"] != "CLOSED":
            logger.info(f"[CircuitBreaker] {name} recovered! Circuit reset to CLOSED.")
        entry["state"] = "CLOSED"
        entry["failures"] = 0
        entry["cooldown_until"] = 0.0

    def record_failure(self, name: str, error: str = ""):
        entry = self._get_entry(name)
        entry["failures"] += 1
        logger.warning(f"[CircuitBreaker] {name} failure count: {entry['failures']}/{self.failure_threshold} ({error})")
        if entry["failures"] >= self.failure_threshold:
            entry["state"] = "OPEN"
            entry["cooldown_until"] = time.time() + self.cooldown_sec
            logger.error(f"[CircuitBreaker] {name} TRIPPED! Disabled for {self.cooldown_sec}s.")


class QueryCache:
    """In-memory TTL cache for general non-dynamic queries."""

    def __init__(self, ttl_hours: float = 24.0):
        self.ttl_sec = ttl_hours * 3600.0
        # {cache_key: (LLMResult, expiry_time)}
        self._cache: Dict[str, tuple[LLMResult, float]] = {}

    @staticmethod
    def _make_key(query: str, is_detailed: bool) -> str:
        clean = " ".join(query.lower().strip().split())
        return f"{clean}__detailed={is_detailed}"

    def get(self, query: str, is_detailed: bool) -> Optional[LLMResult]:
        key = self._make_key(query, is_detailed)
        if key in self._cache:
            res, expiry = self._cache[key]
            if time.time() < expiry:
                return res
            del self._cache[key]
        return None

    def set(self, query: str, is_detailed: bool, result: LLMResult):
        key = self._make_key(query, is_detailed)
        self._cache[key] = (result, time.time() + self.ttl_sec)


class LLMRouter:
    def __init__(self, brain: Any, config_path: Optional[Path] = None):
        self.brain = brain
        self.config_path = config_path or (Path(__file__).resolve().parent.parent.parent / "config" / "llm.yaml")
        self.config: Dict[str, Any] = self._load_config()

        cb_cfg = self.config.get("circuit_breaker", {})
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_cfg.get("failure_threshold", 3),
            cooldown_sec=cb_cfg.get("cooldown_sec", 60.0)
        )

        cache_cfg = self.config.get("cache", {})
        self.cache_enabled = cache_cfg.get("enabled", True)
        self.cache = QueryCache(ttl_hours=cache_cfg.get("ttl_hours", 24.0))

        # Initialize available providers dictionary
        self.providers: Dict[str, LLMProvider] = {}
        self._init_providers()

    def _load_config(self) -> Dict[str, Any]:
        cfg: Dict[str, Any] = {
            "priority": ["gemini", "openai_compat", "ollama", "offline_expert"],
            "timeout": 8.0,
            "circuit_breaker": {"failure_threshold": 3, "cooldown_sec": 60.0},
            "cache": {"enabled": True, "ttl_hours": 24.0},
            "providers": {
                "gemini": {"model": "gemini-2.0-flash", "enable_grounding": True},
                "openai_compat": {"name": "groq", "model": "llama-3.3-70b-versatile", "base_url": "https://api.groq.com/openai/v1"},
                "ollama": {"base_url": "http://localhost:11434", "model": "llama3.2"},
                "offline_expert": {"model": "hiltron-falak-expert-v2"}
            }
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_cfg = yaml.safe_load(f) or {}
                    if "llm" in file_cfg:
                        cfg.update(file_cfg["llm"])
            except Exception as e:
                logger.warning(f"Error loading {self.config_path}: {e}")

        # Env variable overrides
        env_priority = os.getenv("LLM_PRIORITY")
        if env_priority:
            cfg["priority"] = [p.strip() for p in env_priority.split(",") if p.strip()]

        env_timeout = os.getenv("LLM_TIMEOUT")
        if env_timeout:
            try:
                cfg["timeout"] = float(env_timeout)
            except ValueError:
                pass

        return cfg

    def _init_providers(self):
        timeout = float(self.config.get("timeout", 8.0))
        p_cfg = self.config.get("providers", {})

        # 1. Gemini Provider
        gemini_cfg = p_cfg.get("gemini", {})
        gemini_model = os.getenv("GEMINI_MODEL") or gemini_cfg.get("model", "gemini-2.0-flash")
        self.providers["gemini"] = GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=gemini_model,
            timeout=timeout
        )

        # 2. OpenAI-Compatible Provider (Groq / OpenRouter / DeepSeek / OpenAI)
        compat_cfg = p_cfg.get("openai_compat", {})
        base_url = (
            os.getenv("GROQ_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or compat_cfg.get("base_url")
        )
        api_key = (
            os.getenv("GROQ_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
        compat_model = (
            os.getenv("GROQ_MODEL")
            or os.getenv("OPENROUTER_MODEL")
            or os.getenv("OPENAI_MODEL")
            or compat_cfg.get("model", "llama-3.3-70b-versatile")
        )
        compat_name = compat_cfg.get("name", "openai_compat")
        self.providers["openai_compat"] = OpenAICompatProvider(
            name=compat_name,
            base_url=base_url,
            api_key=api_key,
            model=compat_model,
            timeout=timeout
        )

        # 3. Local Ollama Provider
        ollama_cfg = p_cfg.get("ollama", {})
        ollama_base = os.getenv("OLLAMA_BASE_URL") or ollama_cfg.get("base_url", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL") or ollama_cfg.get("model", "llama3.2")
        self.providers["ollama"] = OllamaProvider(
            base_url=ollama_base,
            model=ollama_model,
            timeout=timeout + 2.0
        )

        # 4. Offline Falak Expert Engine Wrapper
        self.providers["offline_expert"] = OfflineProvider(brain=self.brain)

    def get_priority_list(self) -> List[str]:
        return self.config.get("priority", ["gemini", "openai_compat", "ollama", "offline_expert"])

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_grounding: bool = False,
        temperature: float = 0.7,
        max_output_tokens: int = 300,
        is_cacheable: bool = False,
        is_detailed: bool = False,
        **opts
    ) -> LLMResult:
        """
        Executes layered generation with automatic failover and circuit breaker.
        """
        last_user_query = ""
        for m in reversed(messages):
            if m.get("role") in ["user", "human"]:
                last_user_query = m.get("content", "")
                break

        # Check Cache for static/general non-personal queries
        if is_cacheable and self.cache_enabled and last_user_query:
            cached_res = self.cache.get(last_user_query, is_detailed)
            if cached_res:
                logger.info(f"[LLMRouter] Cache hit for: '{last_user_query[:40]}...'")
                res_copy = LLMResult(
                    text=cached_res.text,
                    usage=cached_res.usage,
                    provider_name=f"{cached_res.provider_name} (cached)",
                    model_name=cached_res.model_name,
                    latency_ms=0.5,
                    sources=cached_res.sources,
                    is_success=True
                )
                return res_copy

        priority = self.get_priority_list()
        last_error = ""

        for provider_name in priority:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            # Check if provider credentials exist
            if not provider.is_available():
                continue

            # Check circuit breaker
            if not self.circuit_breaker.can_try(provider_name):
                logger.info(f"[LLMRouter] Circuit OPEN for '{provider_name}'. Skipping to next.")
                continue

            # Special case: Ollama probe
            if provider_name == "ollama":
                is_ollama_up = await provider.check_server_health()
                if not is_ollama_up:
                    continue

            logger.info(f"[LLMRouter] Trying provider: '{provider_name}' (model: {provider.model})")
            result = await provider.generate(
                messages=messages,
                system=system,
                tools=tools,
                enable_grounding=enable_grounding,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **opts
            )

            if result.is_success and result.text and result.text.strip():
                self.circuit_breaker.record_success(provider_name)
                logger.info(f"[LLMRouter] Provider '{provider_name}' SUCCEEDED in {result.latency_ms}ms.")

                # Populate in-memory cache if query is eligible (do not cache offline_expert)
                if is_cacheable and self.cache_enabled and last_user_query and provider_name != "offline_expert":
                    self.cache.set(last_user_query, is_detailed, result)

                return result
            else:
                last_error = result.error or "Empty response"
                self.circuit_breaker.record_failure(provider_name, last_error)
                logger.warning(f"[LLMRouter] Provider '{provider_name}' failed: {last_error}. Falling back...")

        # If all prior providers failed, invoke offline_expert directly
        offline_provider = self.providers.get("offline_expert")
        if offline_provider:
            logger.info("[LLMRouter] All remote providers failed. Executing local offline_expert fallback.")
            return await offline_provider.generate(
                messages=messages,
                system=system,
                tools=tools,
                enable_grounding=False,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **opts
            )

        return LLMResult(
            text="Mohon maaf, semua layanan AI sedang tidak dapat dihubungi saat ini.",
            provider_name="none",
            error=last_error,
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
    ) -> AsyncIterator[tuple[str, str]]:
        """
        Yields (chunk_text, provider_name) tuples with automatic fallback if a provider yields nothing.
        """
        priority = self.get_priority_list()

        for provider_name in priority:
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_available():
                continue

            if not self.circuit_breaker.can_try(provider_name):
                continue

            if provider_name == "ollama":
                if not await provider.check_server_health():
                    continue

            logger.info(f"[LLMRouter] Streaming from provider: '{provider_name}'")
            yielded_any = False

            try:
                async for chunk in provider.stream(
                    messages=messages,
                    system=system,
                    tools=tools,
                    enable_grounding=enable_grounding,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    **opts
                ):
                    if chunk:
                        yielded_any = True
                        yield (chunk, provider_name)

                if yielded_any:
                    self.circuit_breaker.record_success(provider_name)
                    return
                else:
                    self.circuit_breaker.record_failure(provider_name, "Stream produced zero chunks")
            except Exception as e:
                self.circuit_breaker.record_failure(provider_name, str(e))
                logger.warning(f"[LLMRouter] Stream exception on '{provider_name}': {e}. Falling back...")

        # Ultimate fallback stream from offline provider
        offline_provider = self.providers.get("offline_expert")
        if offline_provider:
            async for chunk in offline_provider.stream(
                messages=messages,
                system=system,
                tools=tools,
                enable_grounding=False,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **opts
            ):
                yield (chunk, "offline_expert")
