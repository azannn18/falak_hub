"""
Provider Google Gemini Audio / TTS untuk Asisten Falak HILMI.
Memanfaatkan kemampuan multimodal audio dari SDK resmi google-genai
dengan arahan gaya ekspresif bahasa alami (santun, hangat, wibawa).
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from .base import TTSProvider, TTSResult

logger = logging.getLogger("hiltron.tts.gemini")


class GeminiTTSProvider(TTSProvider):
    VOICES = [
        {
            "id": "Puck",
            "name": "Gemini Puck (Energetic Santri)",
            "gender": "Male",
            "lang": "id-ID",
            "description": "Suara Gemini dengan intonasi hangat dan ekspresif"
        },
        {
            "id": "Charon",
            "name": "Gemini Charon (Deep Wibawa)",
            "gender": "Male",
            "lang": "id-ID",
            "description": "Suara Gemini dengan nada berat, tenang dan penuh wibawa"
        },
        {
            "id": "Aoede",
            "name": "Gemini Aoede (Santun Santriwati)",
            "gender": "Female",
            "lang": "id-ID",
            "description": "Suara Gemini wanita ramah, lembut dan artikulatif"
        }
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        default_voice: str = "Puck"
    ):
        super().__init__(name="gemini_tts")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.default_voice = default_voice
        self._client = None

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import google.genai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None and self.is_available():
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def get_voices(self) -> List[Dict[str, Any]]:
        return self.VOICES

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = "+0%",
        pitch: Optional[str] = "+0Hz",
        volume: Optional[str] = "+0%",
        style: Optional[str] = "Bicara santun, hangat, tenang dan jelas seperti santri falak terpelajar.",
        **kwargs
    ) -> TTSResult:
        if not self.is_available():
            return TTSResult(
                audio_bytes=b"",
                provider_name=self.name,
                is_success=False,
                error="GEMINI_API_KEY tidak dikonfigurasi atau SDK google-genai belum terpasang."
            )

        selected_voice = voice or self.default_voice
        start_time = time.perf_counter()

        try:
            client = self._get_client()
            if not client:
                raise ValueError("Client Gemini tidak dapat diinisialisasi")

            prompt = (
                f"Ucapkan kalimat berikut dalam bahasa Indonesia dengan nada santun, "
                f"hangat, artikulasi jelas, dan berwibawa: \"{text}\""
            )

            # Eksekusi async via threadpool untuk menghindari blocking event loop
            def call_genai():
                from google.genai import types
                config = types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=selected_voice
                            )
                        )
                    )
                )
                return client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config
                )

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, call_genai)

            # Ekstrak data audio dari inline_data part
            audio_bytes = None
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.data:
                        audio_bytes = part.inline_data.data
                        break
                if audio_bytes:
                    break

            if not audio_bytes:
                raise ValueError("Tidak ada part audio yang diterima dari respons Gemini")

            latency = round((time.perf_counter() - start_time) * 1000, 2)
            return TTSResult(
                audio_bytes=audio_bytes,
                media_type="audio/wav",
                provider_name=self.name,
                voice_name=selected_voice,
                latency_ms=latency,
                cached=False,
                is_success=True
            )

        except Exception as e:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(f"[GeminiTTS] Gagal menghasilkan audio: {e}")
            return TTSResult(
                audio_bytes=b"",
                media_type="audio/mpeg",
                provider_name=self.name,
                voice_name=selected_voice,
                latency_ms=latency,
                cached=False,
                is_success=False,
                error=str(e)
            )

