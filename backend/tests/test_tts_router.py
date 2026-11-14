"""
Unit Test Suite untuk Multi-Provider TTS Router & Caching Audio HILMI.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.tts.base import TTSProvider, TTSResult
from ai.tts.cache import TTSAudioCache
from ai.tts.edge_tts_provider import EdgeTTSProvider
from ai.tts.router import TTSRouter, TTSCircuitBreaker


class MockFastTTSProvider(TTSProvider):
    def __init__(self, name="mock_fast", succeed=True):
        super().__init__(name=name)
        self.succeed = succeed
        self.call_count = 0

    def is_available(self) -> bool:
        return True

    def get_voices(self):
        return [{"id": "mock-voice-1", "name": "Mock Voice", "gender": "Male"}]

    async def synthesize(self, text, **kwargs) -> TTSResult:
        self.call_count += 1
        if self.succeed:
            return TTSResult(
                audio_bytes=b"MOCK_MP3_AUDIO_DATA_" + text.encode("utf-8"),
                provider_name=self.name,
                voice_name="mock-voice-1",
                latency_ms=10.0,
                cached=False,
                is_success=True
            )
        return TTSResult(
            audio_bytes=b"",
            provider_name=self.name,
            is_success=False,
            error="Mock failure"
        )


class TestTTSSystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache = TTSAudioCache(cache_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_cache_operations(self):
        text = "Assalamu'alaikum sahabat falak."
        # Before set
        self.assertIsNone(self.cache.get(text))

        # After set
        dummy_audio = b"\xff\xfb\x90\x44DUMMY_MP3"
        self.cache.set(text, dummy_audio)
        cached = self.cache.get(text)
        self.assertEqual(cached, dummy_audio)

        # Different voice should miss
        miss = self.cache.get(text, voice="id-ID-GadisNeural")
        self.assertIsNone(miss)

    def test_02_circuit_breaker(self):
        cb = TTSCircuitBreaker(failure_threshold=3, cooldown_sec=1.0)
        self.assertTrue(cb.is_available())
        self.assertEqual(cb.state, "CLOSED")

        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, "CLOSED")
        self.assertTrue(cb.is_available())

        cb.record_failure()
        self.assertEqual(cb.state, "OPEN")
        self.assertFalse(cb.is_available())

        # Success resets
        cb.record_success()
        self.assertEqual(cb.state, "CLOSED")
        self.assertTrue(cb.is_available())

    def test_03_router_with_mock_and_cache(self):
        async def _run():
            provider = MockFastTTSProvider("mock_fast", succeed=True)
            router = TTSRouter(providers=[provider], cache_dir=self.temp_dir, enable_cache=True)

            # First call -> hit provider
            raw_text = "Tinggi hilal adalah 3.2° dengan elongasi ≥ 6.4°."
            res1 = await router.synthesize(raw_text)
            self.assertTrue(res1.is_success)
            self.assertFalse(res1.cached)
            self.assertEqual(res1.provider_name, "mock_fast")
            self.assertEqual(provider.call_count, 1)

            # Second call -> hit cache (<5ms)
            res2 = await router.synthesize(raw_text)
            self.assertTrue(res2.is_success)
            self.assertTrue(res2.cached)
            self.assertEqual(res2.provider_name, "cache")
            self.assertEqual(provider.call_count, 1)  # Provider not called again!

        asyncio.run(_run())

    def test_04_router_fallback(self):
        async def _run():
            p_fail = MockFastTTSProvider("failing_provider", succeed=False)
            p_backup = MockFastTTSProvider("backup_provider", succeed=True)
            router = TTSRouter(providers=[p_fail, p_backup], cache_dir=self.temp_dir, enable_cache=False)

            res = await router.synthesize("Uji coba fallback.")
            self.assertTrue(res.is_success)
            self.assertEqual(res.provider_name, "backup_provider")
            self.assertEqual(p_fail.call_count, 1)
            self.assertEqual(p_backup.call_count, 1)

        asyncio.run(_run())

    def test_05_edge_tts_provider_micro_prosody(self):
        provider = EdgeTTSProvider(enable_natural_prosody=True)
        r, p = provider._apply_micro_prosody("+0%", "+0Hz")
        # Should apply jitter within range
        self.assertTrue(r.endswith("%"))
        self.assertTrue(p.endswith("Hz"))

        # Explicit non-zero should not be touched
        r_explicit, p_explicit = provider._apply_micro_prosody("+10%", "-5Hz")
        self.assertEqual(r_explicit, "+10%")
        self.assertEqual(p_explicit, "-5Hz")


if __name__ == "__main__":
    unittest.main()
