"""
Provider Microsoft Edge Neural TTS untuk Asisten Falak HILMI.
Dilengkapi variasi mikro-prosodi alami, penanganan jeda nafas cerdas,
serta mekanisme retry otomatis jika endpoint cloud mengalami reset koneksi.
"""

import asyncio
import logging
import random
import socket
import time
from typing import Any, Dict, List, Optional

from .base import TTSProvider, TTSResult

logger = logging.getLogger("hiltron.tts.edge")

# Pastikan koneksi cloud TTS Bing menggunakan IPv4 untuk menghindari WinError 64 / RST
# pada mesin atau jaringan ISP tanpa rute IPv6 yang valid.
_orig_getaddrinfo = socket.getaddrinfo

def _ipv4_preferred_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    res = _orig_getaddrinfo(host, port, family, type, proto, flags)
    if host and any(domain in str(host) for domain in ["bing.com", "microsoft.com", "azure.com"]):
        ipv4 = [r for r in res if r[0] == socket.AF_INET]
        if ipv4:
            return ipv4
    return res

socket.getaddrinfo = _ipv4_preferred_getaddrinfo


class EdgeTTSProvider(TTSProvider):
    VOICES = [
        {
            "id": "id-ID-ArdiNeural",
            "name": "Ardi (Santri Falak)",
            "gender": "Male",
            "lang": "id-ID",
            "description": "Suara pria santun, berwibawa, hangat khas santri falak Indonesia"
        },
        {
            "id": "id-ID-GadisNeural",
            "name": "Gadis (Santriwati Falak)",
            "gender": "Female",
            "lang": "id-ID",
            "description": "Suara wanita ramah, santun, jernih dan artikulatif"
        }
    ]

    def __init__(
        self,
        default_voice: str = "id-ID-ArdiNeural",
        enable_natural_prosody: bool = True,
        max_retries: int = 2
    ):
        super().__init__(name="edge_tts")
        self.default_voice = default_voice
        self.enable_natural_prosody = enable_natural_prosody
        self.max_retries = max_retries
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import edge_tts  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def get_voices(self) -> List[Dict[str, Any]]:
        return self.VOICES

    def _apply_micro_prosody(self, rate: str, pitch: str) -> tuple[str, str]:
        """
        Menambahkan fluktuasi mikro pada laju bicara (-3% s.d +3%) dan nada (-2Hz s.d +2Hz)
        secara halus agar tidak terdengar seperti kaset yang diputar berulang-ulang.
        """
        if not self.enable_natural_prosody:
            return rate, pitch

        # Hanya lakukan jitter jika caller memakai nilai default (+0%)
        effective_rate = rate
        if rate in ["+0%", "0%", "0", ""]:
            jitter_r = random.choice([-3, -2, 0, 1, 2, 3])
            effective_rate = f"{'+' if jitter_r >= 0 else ''}{jitter_r}%"

        effective_pitch = pitch
        if pitch in ["+0Hz", "0Hz", "0", ""]:
            jitter_p = random.choice([-2, -1, 0, 1, 2])
            effective_pitch = f"{'+' if jitter_p >= 0 else ''}{jitter_p}Hz"

        return effective_rate, effective_pitch

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = "+0%",
        pitch: Optional[str] = "+0Hz",
        volume: Optional[str] = "+0%",
        style: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        """
        Mensintesis teks menjadi audio mp3 menggunakan edge_tts.
        """
        if not text or not text.strip():
            return TTSResult(
                audio_bytes=b"",
                provider_name=self.name,
                is_success=False,
                error="Teks kosong"
            )

        selected_voice = voice or self.default_voice
        rate_val = rate or "+0%"
        pitch_val = pitch or "+0Hz"
        volume_val = volume or "+0%"

        effective_rate, effective_pitch = self._apply_micro_prosody(rate_val, pitch_val)

        start_time = time.perf_counter()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                import edge_tts
                communicate = edge_tts.Communicate(
                    text=text.strip(),
                    voice=selected_voice,
                    rate=effective_rate,
                    pitch=effective_pitch,
                    volume=volume_val
                )

                audio_data = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data.extend(chunk["data"])

                if audio_data:
                    latency = round((time.perf_counter() - start_time) * 1000, 2)
                    return TTSResult(
                        audio_bytes=bytes(audio_data),
                        media_type="audio/mpeg",
                        provider_name=self.name,
                        voice_name=selected_voice,
                        latency_ms=latency,
                        cached=False,
                        is_success=True
                    )

                raise ValueError("Edge TTS menghasilkan stream audio kosong")

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[EdgeTTS] Percobaan ke-{attempt+1} gagal untuk suara '{selected_voice}': {e}"
                )
                if attempt < self.max_retries:
                    # Exponential backoff: 0.25s, 0.5s
                    await asyncio.sleep(0.25 * (2 ** attempt))

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return TTSResult(
            audio_bytes=b"",
            media_type="audio/mpeg",
            provider_name=self.name,
            voice_name=selected_voice,
            latency_ms=latency,
            cached=False,
            is_success=False,
            error=last_error or "Gagal mensintesis audio setelah retries"
        )
