"""
Antarmuka Dasar Text-to-Speech (TTS Provider) untuk Asisten Falak HILMI.
Menyediakan abstraksi seragam untuk berbagai engine suara:
- Microsoft Edge Neural TTS (Ardi & Gadis) dengan variasi mikro-prosodi alami
- Google Gemini / Cloud TTS
- Audio Cache & Offline Fallback
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TTSResult:
    audio_bytes: bytes
    media_type: str = "audio/mpeg"
    provider_name: str = "unknown"
    voice_name: str = "default"
    latency_ms: float = 0.0
    cached: bool = False
    error: Optional[str] = None
    is_success: bool = True


class TTSProvider(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def is_available(self) -> bool:
        """Mengecek ketersediaan dependensi, credential, atau konektivitas engine."""
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None,
        style: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        """
        Mensintesis teks bahasa lisan menjadi audio (mp3 bytes).
        Teks dijamin sudah dinormalisasi oleh SpokenTextNormalizer.
        """
        pass

    @abstractmethod
    def get_voices(self) -> List[Dict[str, Any]]:
        """Mengembalikan daftar suara yang didukung provider ini."""
        pass

