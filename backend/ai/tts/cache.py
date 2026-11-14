"""
Sistem Cache Audio Disk untuk Text-to-Speech HILMI.
Menyimpan hasil sintesis frasa umum (misal: salam, sapaan, respon hisab konstan)
untuk memangkas latensi dari ~1000ms ke < 5ms serta menjaga sistem tetap
bisa berbicara ketika koneksi internet cloud TTS terganggu.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional


class TTSAudioCache:
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            base_dir = Path(__file__).resolve().parent
            self.cache_dir = base_dir / "cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(self, text: str, voice: str, rate: str, pitch: str) -> str:
        raw = f"{voice}::{rate}::{pitch}::{text.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, text: str, voice: str = "id-ID-ArdiNeural", rate: str = "+0%", pitch: str = "+0Hz") -> Optional[bytes]:
        """Mengambil data audio jika ada dalam cache."""
        key = self._make_key(text, voice, rate, pitch)
        file_path = self.cache_dir / f"{key}.mp3"
        if file_path.is_file():
            try:
                return file_path.read_bytes()
            except Exception:
                return None
        return None

    def set(self, text: str, audio_bytes: bytes, voice: str = "id-ID-ArdiNeural", rate: str = "+0%", pitch: str = "+0Hz") -> None:
        """Menyimpan data audio ke disk cache."""
        if not audio_bytes:
            return
        key = self._make_key(text, voice, rate, pitch)
        file_path = self.cache_dir / f"{key}.mp3"
        try:
            file_path.write_bytes(audio_bytes)
        except Exception:
            pass

    def clear(self) -> int:
        """Membersihkan file cache."""
        count = 0
        for f in self.cache_dir.glob("*.mp3"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        return count

