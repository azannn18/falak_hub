"""
HILTRON FalakHub — Base LLM Provider Abstraction.
Defines unified interface, result data structures, and streaming contracts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncIterator


@dataclass
class LLMResult:
    """Unified result format across all LLM providers."""
    text: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    provider_name: str = "unknown"
    model_name: str = "unknown"
    latency_ms: float = 0.0
    sources: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None
    is_success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "sources": self.sources or [],
            "error": self.error,
            "is_success": self.is_success
        }


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, name: str, model: str, timeout: float = 8.0):
        self.name = name
        self.model = model
        self.timeout = timeout

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is configured and available for use."""
        pass

    @abstractmethod
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
        """
        Executes a full generation call.
        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system: System instructions
            tools: Optional list of function schemas
            enable_grounding: Whether to enable search grounding (if supported)
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens in response
        """
        pass

    @abstractmethod
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
        """
        Yields text chunks as they arrive from the provider.
        """
        pass

