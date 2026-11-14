"""
HILTRON FalakHub — Offline Expert Engine LLM Provider Wrapper.
Wraps the deterministic local Falak Expert Engine & Knowledge Base into LLMProvider interface.
Always available (100% offline, zero latency, 100% reliable).
"""

import time
import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator

from ai.llm.base import LLMProvider, LLMResult


class OfflineProvider(LLMProvider):
    def __init__(self, brain: Any):
        super().__init__(name="offline_expert", model="hiltron-falak-expert-v2", timeout=1.0)
        self.brain = brain

    def is_available(self) -> bool:
        # Offline expert is always available locally
        return True

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
        start_time = time.perf_counter()

        # Extract the user message (prefer explicit user_query, fallback to message content)
        last_user_msg = opts.get("user_query", "").strip()
        if not last_user_msg:
            for m in reversed(messages):
                if m.get("role") in ["user", "human"]:
                    c = m.get("content", "")
                    if 'Pertanyaan Pengguna: "' in c:
                        last_user_msg = c.split('Pertanyaan Pengguna: "')[-1].rstrip('"').strip()
                    else:
                        last_user_msg = c
                    break

        if not last_user_msg:
            return LLMResult(
                text="",
                provider_name=self.name,
                model_name=self.model,
                error="No user message found.",
                is_success=False
            )

        # Retrieve extra kwargs passed from assistant_brain (e.g. retrieved_docs, tool_data, session_state, is_calc)
        retrieved_docs = opts.get("retrieved_docs", [])
        tool_data = opts.get("tool_data", {})
        session_state = opts.get("session_state", {})
        is_calc = opts.get("is_calculation_intent", False)

        reply_text = self.brain.generate_offline_expert_response(
            user_message=last_user_msg,
            retrieved_docs=retrieved_docs,
            tool_data=tool_data,
            session_state=session_state,
            is_calculation_intent=is_calc
        )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return LLMResult(
            text=reply_text,
            usage={"prompt_tokens": len(last_user_msg.split()), "completion_tokens": len(reply_text.split()), "total_tokens": len(last_user_msg.split()) + len(reply_text.split())},
            provider_name=self.name,
            model_name=self.model,
            latency_ms=latency_ms,
            is_success=True
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
        res = await self.generate(messages, system, tools, enable_grounding, temperature, max_output_tokens, **opts)
        if not res.text:
            return

        # Simulate natural streaming by chunking words/sentences
        words = res.text.split(" ")
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i:i+3]) + " "
            yield chunk
            await asyncio.sleep(0.02)  # Tiny pause for natural TTS feeder
