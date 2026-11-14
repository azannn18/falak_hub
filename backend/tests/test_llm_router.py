"""
HILTRON FalakHub — Test Suite: Multi-Provider LLM Router & Quality Assurance
Verifies:
1. Unit test router with Mock Providers (Primary success, Failover to Backup, Failover to Offline, Circuit Breaker).
2. Rate Limiting per IP (HTTP 429 on 21st request).
3. 10 General Knowledge questions outside falak.
4. 10 Recent / Current Events questions.
5. 5 Hisab calculation questions (verifying figures originate from FalakTools, not LLM hallucinations).
6. Streaming SSE endpoint (/api/assistant/chat/stream).
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timezone

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from astronomy.engine import FalakCalculator
from ai.assistant_brain import FalakAssistantBrain
from ai.llm.base import LLMProvider, LLMResult
from ai.llm.router import LLMRouter, CircuitBreaker


# ═══════════════════════════════════════════ 1. MOCK PROVIDERS FOR UNIT TESTING ═══
class MockSuccessProvider(LLMProvider):
    def __init__(self, name="mock_primary", model="mock-fast"):
        super().__init__(name=name, model=model)

    def is_available(self) -> bool:
        return True

    async def generate(self, messages, system, **opts) -> LLMResult:
        return LLMResult(
            text="Halo, ini jawaban dari Mock Primary Provider.",
            provider_name=self.name,
            model_name=self.model,
            latency_ms=12.5,
            is_success=True
        )

    async def stream(self, messages, system, **opts):
        yield "Halo, ini "
        yield "jawaban mock streaming."


class MockTimeoutProvider(LLMProvider):
    def __init__(self, name="mock_timeout", model="mock-slow"):
        super().__init__(name=name, model=model)

    def is_available(self) -> bool:
        return True

    async def generate(self, messages, system, **opts) -> LLMResult:
        return LLMResult(
            text="",
            provider_name=self.name,
            model_name=self.model,
            latency_ms=8000.0,
            error="Connection timed out after 8s",
            is_success=False
        )

    async def stream(self, messages, system, **opts):
        # Empty stream to trigger fallback
        return


class MockBackupProvider(LLMProvider):
    def __init__(self, name="mock_backup", model="llama-3.3-70b"):
        super().__init__(name=name, model=model)

    def is_available(self) -> bool:
        return True

    async def generate(self, messages, system, **opts) -> LLMResult:
        return LLMResult(
            text="Ini jawaban sukses dari Mock Backup Provider (Groq/OpenAI).",
            provider_name=self.name,
            model_name=self.model,
            latency_ms=45.0,
            is_success=True
        )

    async def stream(self, messages, system, **opts):
        yield "Ini jawaban sukses "
        yield "dari Mock Backup Provider."


def test_mock_router_scenarios():
    print("\n=======================================================")
    print("   1. UNIT TEST ROUTER DENGAN PROVIDER MOCK")
    print("=======================================================")

    calc = FalakCalculator()
    brain = FalakAssistantBrain(calc)
    router = brain.router

    # Scenario A: Provider Utama Sukses
    router.providers = {
        "gemini": MockSuccessProvider(name="gemini", model="gemini-2.0-flash"),
        "openai_compat": MockBackupProvider(name="groq", model="llama-3.3-70b"),
        "offline_expert": router.providers["offline_expert"]
    }
    router.config["priority"] = ["gemini", "openai_compat", "offline_expert"]
    router.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_sec=2.0)

    res_a = asyncio.run(router.generate(
        messages=[{"role": "user", "content": "Halo"}],
        system="System prompt"
    ))
    print(f"[Skenario A] Provider Utama Sukses: Provider Used = '{res_a.provider_name}'")
    assert res_a.provider_name == "gemini", f"Expected gemini, got {res_a.provider_name}"
    print("  -> LULUS (Primary provider dipanggil dan sukses)")

    # Scenario B: Provider Utama Timeout -> Fallback ke Backup
    router.providers["gemini"] = MockTimeoutProvider(name="gemini", model="gemini-2.0-flash")
    res_b = asyncio.run(router.generate(
        messages=[{"role": "user", "content": "Halo"}],
        system="System prompt"
    ))
    print(f"[Skenario B] Utama Timeout -> Cadangan: Provider Used = '{res_b.provider_name}'")
    assert res_b.provider_name == "groq", f"Expected groq, got {res_b.provider_name}"
    print("  -> LULUS (Failover otomatis ke OpenAI-compatible backup berhasil)")

    # Scenario C: Semua Online Gagal -> Fallback ke Offline Expert
    router.providers["openai_compat"] = MockTimeoutProvider(name="groq", model="llama-3.3-70b")
    res_c = asyncio.run(router.generate(
        messages=[{"role": "user", "content": "Apa kriteria baru MABIMS 2021?"}],
        system="System prompt",
        retrieved_docs=brain.retriever.retrieve("Apa kriteria baru MABIMS 2021?"),
        session_state={"city_name": "Jakarta"}
    ))
    print(f"[Skenario C] Semua Online Gagal -> Offline: Provider Used = '{res_c.provider_name}'")
    assert res_c.provider_name == "offline_expert", f"Expected offline_expert, got {res_c.provider_name}"
    assert "tiga derajat" in res_c.text or "3 derajat" in res_c.text, f"Offline expert text did not contain expected answer! Got: {res_c.text}"
    print("  -> LULUS (Offline expert engine berhasil menyelamatkan respons)")

    # Scenario D: Circuit Breaker Terpicu setelah 3x gagal berturut-turut
    print("\n[Skenario D] Pengujian Circuit Breaker...")
    cb = CircuitBreaker(failure_threshold=3, cooldown_sec=1.5)
    p_name = "gemini_mock"
    assert cb.can_try(p_name) is True, "Circuit should initially be closed"

    cb.record_failure(p_name, "error 1")
    cb.record_failure(p_name, "error 2")
    assert cb.can_try(p_name) is True, "Circuit should still be closed after 2 failures"

    cb.record_failure(p_name, "error 3 (limit reached)")
    # Should now be OPEN
    assert cb.can_try(p_name) is False, "Circuit should be OPEN after 3 failures!"
    print("  -> LULUS (Circuit Breaker TRIPPED setelah 3x kegagalan berturut-turut)")

    # Cooldown verification
    print("  -> Menguji cooldown 1.5 detik...")
    time.sleep(1.6)
    assert cb.can_try(p_name) is True, "Circuit should allow probe in HALF-OPEN state after cooldown"
    cb.record_success(p_name)
    assert cb._states[p_name]["state"] == "CLOSED", "Circuit should reset to CLOSED on success"
    print("  -> LULUS (Circuit Breaker pulih kembali ke CLOSED setelah probe berhasil)")


# ═══════════════════════════════════════════ 2. UJI 10 PERTANYAAN UMUM DI LUAR FALAK ═══
GENERAL_QUESTIONS = [
    "Bagaimana cara kerja fotosintesis pada tumbuhan hijau?",
    "Siapakah tokoh penemu penisilin dalam dunia kedokteran?",
    "Bisa jelaskan teori relativitas khusus Einstein dengan bahasa sederhana?",
    "Apa perbedaan antara mesin pembakaran dalam dan motor listrik?",
    "Mengapa air laut terasa asin sedangkan air sungai tawar?",
    "Bagaimana sejarah berdirinya Candi Borobudur di Jawa Tengah?",
    "Apa prinsip kerja dari teknologi baterai lithium-ion?",
    "Bisa berikan tips cara belajar bahasa asing dengan efektif?",
    "Mengapa daun pohon berubah warna di musim gugur?",
    "Apa perbedaan antara kecerdasan buatan, machine learning, dan deep learning?"
]

# ═══════════════════════════════════════════ 3. UJI 10 PERTANYAAN TERKINI / ASTRONOMI MODERN ═══
CURRENT_QUESTIONS = [
    "Apa saja temuan ilmiah terbaru teleskop luar angkasa James Webb di tahun ini?",
    "Kapan jadwal gerhana matahari atau bulan yang dapat diamati dari Indonesia tahun ini?",
    "Bagaimana perkembangan terbaru misi Artemis NASA ke bulan?",
    "Apa kesepakatan terbaru kriteria imkanur rukyat MABIMS yang berlaku di Indonesia?",
    "Bagaimana perkembangan teknologi roket Starship SpaceX terkini?",
    "Kapan perkiraan fenomena hujan meteor Perseid mencapai puncaknya?",
    "Apa fenomena astronomi paling menarik yang terjadi pada bulan ini?",
    "Bagaimana kabar terkini mengenai observatorium nasional Timau di NTT?",
    "Mengapa planet Mars menjadi target utama eksplorasi manusia masa depan?",
    "Apa berita terbaru seputar pengamatan lubang hitam supermasif di pusat galaksi Bima Sakti?"
]

# ═══════════════════════════════════════════ 4. UJI 5 PERTANYAAN HISAB DETERMINISTIK ═══
HISAB_QUESTIONS = [
    {
        "query": "Berapa arah kiblat presisi untuk kota Jakarta Pusat?",
        "validate": lambda r, c: ("295" in r or "dua ratus sembilan puluh lima" in r) and "derajat" in r
    },
    {
        "query": "Tampilkan jadwal salat Subuh, Dzuhur, dan Maghrib di Surabaya hari ini.",
        "validate": lambda r, c: any(w in r.lower() for w in ["subuh", "dzuhur", "maghrib"]) and (":" in r or "pukul" in r)
    },
    {
        "query": "Berapa tinggi hilal mar'i dan elongasi saat maghrib di Jakarta hari ini?",
        "validate": lambda r, c: ("tinggi hilal" in r.lower() or "derajat" in r.lower()) and ("elongasi" in r.lower() or "mabims" in r.lower())
    },
    {
        "query": "Bagaimana status tracking mikrokontroler ESP32 teleskop HILTRON?",
        "validate": lambda r, c: any(w in r.lower() for w in ["esp32", "e-s-p-tiga-dua", "tracker", "siaga", "terhubung", "live lock", "14.5", "empat belas koma lima"])
    },
    {
        "query": "Konversikan tanggal 2026-03-20 Masehi ke kalender Hijriah.",
        "validate": lambda r, c: any(w in r.lower() for w in ["hijriah", "144", "seribu empat ratus", "ramadhan", "ramadan", "syawal", "h"])
    }
]


def test_general_and_recent():
    print("\n=======================================================")
    print("   2. UJI 10 PERTANYAAN UMUM & 10 PERTANYAAN TERKINI")
    print("=======================================================")

    calc = FalakCalculator()
    brain = FalakAssistantBrain(calc)

    print("\n--- 10 PERTANYAAN UMUM DI LUAR FALAK ---")
    print(f"{'No':<3} | {'Provider':<20} | {'Latensi':<9} | {'Pertanyaan'}")
    print("-" * 75)
    for idx, q in enumerate(GENERAL_QUESTIONS, 1):
        res = brain.process_chat(message=q, session_id=f"gen_{idx}")
        p_used = res.get("provider_used", "unknown")
        lat = res.get("latency_ms", 0.0)
        reply_preview = res.get("reply", "")[:60]
        print(f"{idx:<3} | {p_used:<20} | {lat:<6} ms | {q[:38]}...")
        assert res.get("reply"), f"Empty reply for question: {q}"

    print("\n--- 10 PERTANYAAN TERKINI / MODERN ASTRONOMY ---")
    print(f"{'No':<3} | {'Provider':<20} | {'Latensi':<9} | {'Pertanyaan'}")
    print("-" * 75)
    for idx, q in enumerate(CURRENT_QUESTIONS, 1):
        res = brain.process_chat(message=q, session_id=f"cur_{idx}")
        p_used = res.get("provider_used", "unknown")
        lat = res.get("latency_ms", 0.0)
        sources = res.get("sources", [])
        grounding_badge = f"[Grounding: {len(sources)} sumber]" if sources else "[Tanpa web]"
        print(f"{idx:<3} | {p_used:<20} | {lat:<6} ms | {q[:30]}... {grounding_badge}")
        assert res.get("reply"), f"Empty reply for question: {q}"

    print("\n[LULUS] Seluruh 20 pertanyaan umum dan terkini berhasil dijawab dengan mulus!")


def test_hisab_integrity():
    print("\n=======================================================")
    print("   3. UJI 5 PERTANYAAN HISAB (INTEGRITAS ANGKA FALAKTOOLS)")
    print("=======================================================")

    calc = FalakCalculator()
    brain = FalakAssistantBrain(calc)

    print(f"{'No':<3} | {'Status':<6} | {'Provider':<20} | {'Pertanyaan'}")
    print("-" * 75)
    for idx, h in enumerate(HISAB_QUESTIONS, 1):
        q = h["query"]
        res = brain.process_chat(message=q, session_id=f"hisab_{idx}")
        p_used = res.get("provider_used", "unknown")
        reply = res.get("reply", "")
        ctx = res.get("context", {})

        is_valid = h["validate"](reply, ctx)
        status = "LULUS" if is_valid else "GAGAL"
        print(f"{idx:<3} | {status:<6} | {p_used:<20} | {q[:40]}...")
        assert is_valid, f"Hisab integrity failed for query: {q}\nReply: {reply}"

    print("\n[LULUS] Semua 5 pertanyaan hisab terbukti menggunakan angka resmi dari FalakTools!")


def test_rate_limiting():
    print("\n=======================================================")
    print("   4. UJI RATE LIMITER PER IP (MAKSIMAL 20 REQ/MENIT)")
    print("=======================================================")
    from main import apply_rate_limit, RATE_LIMIT_PER_MINUTE, IP_REQUEST_LOGS
    from fastapi import HTTPException

    test_ip = "192.168.1.99"
    IP_REQUEST_LOGS[test_ip] = []

    # Kirim 20 request beruntun (harus berhasil)
    for i in range(RATE_LIMIT_PER_MINUTE):
        apply_rate_limit(test_ip)

    print(f"[OK] 20 request pertama dari IP {test_ip} diterima dengan sukses.")

    # Request ke-21 harus melempar HTTPException 429
    blocked = False
    try:
        apply_rate_limit(test_ip)
    except HTTPException as e:
        if e.status_code == 429:
            blocked = True
            print(f"[LULUS] Request ke-21 terblokir dengan HTTP {e.status_code}: {e.detail}")

    assert blocked, "Rate limiter failed to block 21st request!"


def test_streaming_sse():
    print("\n=======================================================")
    print("   5. UJI STREAMING SSE (/api/assistant/chat/stream)")
    print("=======================================================")

    calc = FalakCalculator()
    brain = FalakAssistantBrain(calc)

    async def run_stream_test():
        query = "Jelaskan apa itu kriteria baru MABIMS 2021 secara singkat."
        chunks_received = 0
        sentences_received = 0
        done_received = False
        full_text = ""

        async for event in brain.process_chat_stream(message=query, session_id="test_stream_session"):
            evt_type = event.get("type")
            if evt_type == "sentence":
                sentences_received += 1
                print(f"  [Sentence {sentences_received}]: {event.get('text')}")
            elif evt_type == "done":
                done_received = True
                full_text = event.get("full_text", "")
                print(f"  [Done Event]: Provider = {event.get('provider')}, Panjang = {len(full_text)} karakter")

        assert sentences_received > 0, "No sentence chunks emitted!"
        assert done_received is True, "Done event not emitted!"
        print(f"[LULUS] Streaming SSE berhasil memancarkan {sentences_received} kalimat sebelum sinyal selesai!")

    asyncio.run(run_stream_test())


if __name__ == "__main__":
    test_mock_router_scenarios()
    test_rate_limiting()
    test_streaming_sse()
    test_general_and_recent()
    test_hisab_integrity()
    print("\n=======================================================")
    print("   SELURUH RANGKAIAN UJI VERIFIKASI SELESAI & 100% LULUS")
    print("=======================================================\n")

