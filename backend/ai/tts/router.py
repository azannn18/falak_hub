"""
Multi-Provider TTS Router dengan Fallback Otomatis, Circuit Breaker,
Normalizer Bahasa Lisan, dan Audio Caching untuk Asisten Falak HILMI.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from ai.speech_text import normalize_spoken_text

from .base import TTSProvider, TTSResult
from .cache import TTSAudioCache
from .edge_tts_provider import EdgeTTSProvider
from .gemini_tts_provider import GeminiTTSProvider

logger = logging.getLogger("hiltron.tts.router")


class TTSCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"[TTS CircuitBreaker] TRIPPED! Disabled for {self.cooldown_sec}s.")

    def is_available(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.cooldown_sec:
                self.state = "HALF_OPEN"
                logger.info("[TTS CircuitBreaker] Entering HALF_OPEN probe state.")
                return True
            return False
        return True  # HALF_OPEN


class TTSRouter:
    def __init__(
        self,
        providers: Optional[List[TTSProvider]] = None,
        cache_dir: Optional[str] = None,
        enable_cache: bool = True
    ):
        self.enable_cache = enable_cache
        self.cache = TTSAudioCache(cache_dir=cache_dir)
        self.circuit_breakers: Dict[str, TTSCircuitBreaker] = {}

        if providers is not None:
            self.providers = providers
        else:
            # Default provider order: Edge TTS (cepat, responsif, dialek Indonesia alami)
            # diikuti Gemini TTS jika API key tersedia.
            self.providers = [
                EdgeTTSProvider(default_voice="id-ID-ArdiNeural", enable_natural_prosody=True),
                GeminiTTSProvider(default_voice="Puck")
            ]

        for p in self.providers:
            self.circuit_breakers[p.name] = TTSCircuitBreaker(failure_threshold=3, cooldown_sec=20.0)

    def get_provider(self, name: str) -> Optional[TTSProvider]:
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def get_voices(self) -> List[Dict[str, Any]]:
        """Mengumpulkan seluruh suara dari provider yang aktif."""
        voices = []
        seen_ids = set()
        for p in self.providers:
            if p.is_available():
                for v in p.get_voices():
                    if v["id"] not in seen_ids:
                        v_copy = dict(v)
                        v_copy["provider"] = p.name
                        voices.append(v_copy)
                        seen_ids.add(v["id"])
        return voices

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = "+0%",
        pitch: Optional[str] = "+0Hz",
        volume: Optional[str] = "+0%",
        style: Optional[str] = None,
        use_cache: bool = True,
        normalize: bool = True,
        preferred_provider: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        """
        Mensintesis teks menjadi audio dengan normalisasi lisan, caching,
        dan failover berlapis antar provider.
        """
        if not text or not text.strip():
            return TTSResult(
                audio_bytes=b"",
                provider_name="none",
                is_success=False,
                error="Teks kosong untuk disintesis."
            )

        # 1. Normalisasi teks ke bentuk lisan yang enak didengar telinga
        spoken_text = normalize_spoken_text(text) if normalize else text.strip()

        voice_val = voice or "id-ID-ArdiNeural"
        rate_val = rate or "+0%"
        pitch_val = pitch or "+0Hz"

        # 2. Cek Cache Audio Disk (Sub-5ms retrieval)
        if self.enable_cache and use_cache:
            cached_audio = self.cache.get(
                text=spoken_text,
                voice=voice_val,
                rate=rate_val,
                pitch=pitch_val
            )
            if cached_audio:
                return TTSResult(
                    audio_bytes=cached_audio,
                    media_type="audio/mpeg",
                    provider_name="cache",
                    voice_name=voice_val,
                    latency_ms=1.5,
                    cached=True,
                    is_success=True
                )

        # 3. Urutkan provider (utamakan preferred_provider jika diminta)
        candidate_providers = list(self.providers)
        if preferred_provider:
            candidate_providers.sort(key=lambda p: 0 if p.name == preferred_provider else 1)

        start_time = time.perf_counter()
        last_error = None

        # 4. Coba provider satu per satu
        for p in candidate_providers:
            cb = self.circuit_breakers.get(p.name)
            if cb and not cb.is_available():
                logger.info(f"[TTSRouter] Melewati provider '{p.name}' karena circuit breaker terbuka.")
                continue

            if not p.is_available():
                continue

            try:
                logger.info(f"[TTSRouter] Mensintesis audio via provider '{p.name}'...")
                res = await p.synthesize(
                    text=spoken_text,
                    voice=voice_val,
                    rate=rate_val,
                    pitch=pitch_val,
                    volume=volume,
                    style=style,
                    **kwargs
                )

                if res.is_success and res.audio_bytes:
                    if cb:
                        cb.record_success()

                    # Simpan ke cache untuk panggilan berikutnya
                    if self.enable_cache and use_cache:
                        self.cache.set(
                            text=spoken_text,
                            audio_bytes=res.audio_bytes,
                            voice=voice_val,
                            rate=rate_val,
                            pitch=pitch_val
                        )

                    logger.info(
                        f"[TTSRouter] Sukses via '{p.name}' dalam {res.latency_ms}ms "
                        f"({len(res.audio_bytes)} bytes)"
                    )
                    return res

                # Provider mengembalikan kegagalan
                last_error = res.error
                if cb:
                    cb.record_failure()
                logger.warning(f"[TTSRouter] Provider '{p.name}' gagal: {res.error}. Mencoba cadangan...")

            except Exception as e:
                last_error = str(e)
                if cb:
                    cb.record_failure()
                logger.warning(f"[TTSRouter] Exception pada provider '{p.name}': {e}. Mencoba cadangan...")

        total_latency = round((time.perf_counter() - start_time) * 1000, 2)
        return TTSResult(
            audio_bytes=b"",
            provider_name="all_failed",
            voice_name=voice_val,
            latency_ms=total_latency,
            cached=False,
            is_success=False,
            error=last_error or "Seluruh provider TTS gagal menghasilkan audio."
        )


# Singleton
_tts_router_instance: Optional[TTSRouter] = None


def get_tts_router() -> TTSRouter:
    global _tts_router_instance
    if _tts_router_instance is None:
        _tts_router_instance = TTSRouter()
    return _tts_router_instance

