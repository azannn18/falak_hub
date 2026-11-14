"""
HILTRON FalakHub — Test Suite: Assistant Quality & Verification (30 Test Cases)
Verifies:
1. 30 test cases across 6 categories (Dasar, Context Follow-up, Awam, Off-topic, Unanswered, Tool Calculation).
2. Online mode (if GEMINI_API_KEY available) and Offline mode.
3. Response variation across 5 identical questions (no robotic repetition).
4. Endpoint /api/assistant/chat compatibility and response schema.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from astronomy.engine import FalakCalculator
from ai.assistant_brain import FalakAssistantBrain


TEST_CASES = [
    # ── Kategori 1: Pertanyaan Falak Dasar (5) ──
    {
        "id": "TC_01",
        "category": "Falak Dasar",
        "query": "Apa perbedaan antara hisab dan rukyat dalam penentuan awal bulan Hijriah?",
        "check": lambda reply: any(w in reply.lower() for w in ["hisab", "rukyat", "hitung", "melihat", "matematis", "visual"])
    },
    {
        "id": "TC_02",
        "category": "Falak Dasar",
        "query": "Berapa parameter kriteria baru MABIMS 2021 untuk imkanur rukyat?",
        "check": lambda reply: "3" in reply and ("6" in reply or "elongasi" in reply.lower())
    },
    {
        "id": "TC_03",
        "category": "Falak Dasar",
        "query": "Apa perbedaan antara posisi hilal toposentris dan geosentris?",
        "check": lambda reply: any(w in reply.lower() for w in ["pusat bumi", "permukaan", "pengamat", "paralaks", "beda lihat", "toposentris", "geosentris"])
    },
    {
        "id": "TC_04",
        "category": "Falak Dasar",
        "query": "Mengapa kriteria lama MABIMS 2 derajat ditinggalkan?",
        "check": lambda reply: any(w in reply.lower() for w in ["lama", "2", "3", "senja", "visibilitas", "rendah", "kontras", "2021"])
    },
    {
        "id": "TC_05",
        "category": "Falak Dasar",
        "query": "Apa yang dimaksud dengan ijtimak atau konjungsi astronomis?",
        "check": lambda reply: any(w in reply.lower() for w in ["ijtimak", "konjungsi", "bujur ekliptika", "bulan mati", "sama", "matahari"])
    },

    # ── Kategori 2: Pertanyaan Lanjutan Bergantung Konteks (Multi-turn Context) (5) ──
    {
        "id": "TC_06",
        "category": "Context Follow-up",
        "setup_query": "Berapa arah kiblat dari Jakarta?",
        "query": "Kalau di Surabaya bagaimana?",
        "check": lambda reply: ("surabaya" in reply.lower() or "29" in reply) and ("derajat" in reply.lower() or "kiblat" in reply.lower())
    },
    {
        "id": "TC_07",
        "category": "Context Follow-up",
        "setup_query": "Tampilkan jadwal salat hari ini di Jakarta",
        "query": "Kalau di Bandung jam berapa saja?",
        "check": lambda reply: any(w in reply.lower() for w in ["bandung", "subuh", "dzuhur", "ashar", "maghrib", "isya"])
    },
    {
        "id": "TC_08",
        "category": "Context Follow-up",
        "setup_query": "Apa itu kriteria Wujudul Hilal?",
        "query": "Lalu bagaimana dengan kriteria NU?",
        "check": lambda reply: any(w in reply.lower() for w in ["nu", "nahdlatul ulama", "rukyat", "imkanur rukyat", "mabims", "fi'li"])
    },
    {
        "id": "TC_09",
        "category": "Context Follow-up",
        "setup_query": "Bagaimana posisi hilal saat maghrib hari ini?",
        "query": "Bisa jelaskan lebih detail tentang syarat elongasi?",
        "check": lambda reply: any(w in reply.lower() for w in ["elongasi", "derajat", "sudut", "matahari", "bulan", "jarak"])
    },
    {
        "id": "TC_10",
        "category": "Context Follow-up",
        "setup_query": "Teleskop HILTRON ditenagai apa?",
        "query": "Bagaimana cara kalibrasi sensornya?",
        "check": lambda reply: any(w in reply.lower() for w in ["kalibrasi", "bno055", "angka 8", "magnetometer", "leveling", "gps"])
    },

    # ── Kategori 3: Pertanyaan Awam / FAQ (5) ──
    {
        "id": "TC_11",
        "category": "Awam / FAQ",
        "query": "Kenapa awal puasa Ramadhan dan Idul Fitri di Indonesia bisa berbeda?",
        "check": lambda reply: any(w in reply.lower() for w in ["kriteria", "wujudul hilal", "imkanur rukyat", "mabims", "rukyat", "ijtihad", "perbedaan"])
    },
    {
        "id": "TC_12",
        "category": "Awam / FAQ",
        "query": "Apa itu hilal sebenarnya?",
        "check": lambda reply: any(w in reply.lower() for w in ["sabit", "tipis", "bulan baru", "terbenam", "sunset", "maghrib"])
    },
    {
        "id": "TC_13",
        "category": "Awam / FAQ",
        "query": "Kenapa hilal kadang tidak kelihatan padahal sudah terjadi ijtimak?",
        "check": lambda reply: any(w in reply.lower() for w in ["rendah", "cahaya senja", "kontras", "awan", "elongasi", "silau", "uap"])
    },
    {
        "id": "TC_14",
        "category": "Awam / FAQ",
        "query": "Mengapa tinggi hilal di Sabang selalu lebih tinggi daripada di Merauke?",
        "check": lambda reply: any(w in reply.lower() for w in ["sabang", "merauke", "terbenam", "barat", "timur", "selisih", "jam"])
    },
    {
        "id": "TC_15",
        "category": "Awam / FAQ",
        "query": "Kapan terjadinya peristiwa rashdul kiblat global di mana bayangan matahari mengarah ke Ka'bah?",
        "check": lambda reply: any(w in reply.lower() for w in ["28 mei", "16 juli", "mei", "juli", "bayangan", "istiwa"])
    },

    # ── Kategori 4: Pertanyaan di Luar Topik / Off-topic (5) ──
    {
        "id": "TC_16",
        "category": "Di Luar Topik",
        "query": "Bisa kasih resep rendang daging sapi yang empuk?",
        "check": lambda reply: any(w in reply.lower() for w in ["santri", "astronomi", "falak", "salat", "fokus", "langit", "maghrib", "resep", "keahlian"])
    },
    {
        "id": "TC_17",
        "category": "Di Luar Topik",
        "query": "Siapa yang menang pertandingan sepak bola semalam?",
        "check": lambda reply: any(w in reply.lower() for w in ["astronomi", "falak", "observatorium", "hilal", "benda langit", "fokus", "keahlian"])
    },
    {
        "id": "TC_18",
        "category": "Di Luar Topik",
        "query": "Berapa harga saham perbankan hari ini?",
        "check": lambda reply: any(w in reply.lower() for w in ["falak", "astronomi", "keahlian", "langit", "hilmi", "salat", "fokus"])
    },
    {
        "id": "TC_19",
        "category": "Di Luar Topik",
        "query": "Bisa bantu tulis puisi cinta romantis?",
        "check": lambda reply: any(w in reply.lower() for w in ["bintang", "bulan", "langit", "astronomi", "santri", "falak", "keahlian"])
    },
    {
        "id": "TC_20",
        "category": "Di Luar Topik",
        "query": "Bagaimana cara memperbaiki karburator motor mogok?",
        "check": lambda reply: any(w in reply.lower() for w in ["falak", "astronomi", "teleskop", "benda langit", "keahlian", "santri", "fokus"])
    },

    # ── Kategori 5: Pertanyaan Tidak Ada Jawaban / Low Confidence (5) ──
    {
        "id": "TC_21",
        "category": "Tak Terjawab / Honest",
        "query": "Berapa jumlah atom hidrogen pada molekul protein titin secara pasti menurut falak?",
        "check": lambda reply: any(w in reply.lower() for w in ["mohon maaf", "belum menemukan", "belum memiliki", "afwan", "bantu sahabat", "hisab hilal"])
    },
    {
        "id": "TC_22",
        "category": "Tak Terjawab / Honest",
        "query": "Siapa nama penjual kurma di pasar Madinah pada tahun 1820?",
        "check": lambda reply: any(w in reply.lower() for w in ["mohon maaf", "belum", "data", "rujukan", "afwan", "membantu"])
    },
    {
        "id": "TC_23",
        "category": "Tak Terjawab / Honest",
        "query": "Bagaimana hisab orbit satelit Jupiter Ganymede menurut kitab Sullamun Nayyirain?",
        "check": lambda reply: any(w in reply.lower() for w in ["sullamun", "taqribi", "mohon maaf", "belum", "khazanah", "matahari dan bulan", "afwan"])
    },
    {
        "id": "TC_24",
        "category": "Tak Terjawab / Honest",
        "query": "Berapa frekuensi kuantum gelombang gravitasi lubang hitam di rasi Andromeda?",
        "check": lambda reply: any(w in reply.lower() for w in ["mohon maaf", "belum", "data", "afwan", "falak", "bantu"])
    },
    {
        "id": "TC_25",
        "category": "Tak Terjawab / Honest",
        "query": "Bagaimana cara meretas sandi WiFi tetangga menggunakan ilmu falak?",
        "check": lambda reply: any(w in reply.lower() for w in ["mohon maaf", "tidak", "fokus", "ilmu falak", "akhlak", "santri", "afwan", "keahlian"])
    },

    # ── Kategori 6: Perhitungan Real Hilal / Kiblat / Salat / Tracker (5) ──
    {
        "id": "TC_26",
        "category": "Perhitungan Real",
        "query": "Hitung arah kiblat presisi untuk kota Jakarta Pusat.",
        "check": lambda reply: ("295" in reply or "dua ratus sembilan puluh lima" in reply) and ("derajat" in reply.lower() or "utara" in reply.lower())
    },
    {
        "id": "TC_27",
        "category": "Perhitungan Real",
        "query": "Berapa jadwal waktu salat Dzuhur, Ashar, dan Maghrib di Surabaya hari ini?",
        "check": lambda reply: any(w in reply.lower() for w in ["dzuhur", "ashar", "maghrib"]) and any(w in reply.lower() for w in ["11:", "12:", "14:", "15:", "17:", "18:", "sebelas", "dua belas", "empat belas", "lima belas", "tujuh belas", "delapan belas", "pukul"])
    },
    {
        "id": "TC_28",
        "category": "Perhitungan Real",
        "query": "Berapa tinggi hilal mar'i dan elongasi saat maghrib di Jakarta hari ini?",
        "check": lambda reply: ("tinggi" in reply.lower() or "derajat" in reply.lower()) and ("elongasi" in reply.lower() or "mabims" in reply.lower())
    },
    {
        "id": "TC_29",
        "category": "Perhitungan Real",
        "query": "Bagaimana status tracking mikrokontroler ESP32 teleskop HILTRON?",
        "check": lambda reply: any(w in reply.lower() for w in ["esp32", "tracker", "siaga", "terhubung", "live lock", "rotasi bumi"])
    },
    {
        "id": "TC_30",
        "category": "Perhitungan Real",
        "query": "Konversikan tanggal 2026-03-20 Masehi ke penanggalan Hijriah.",
        "check": lambda reply: any(w in reply.lower() for w in ["hijriah", "144", "ramadhan", "syawal", "syakban", "syaban", "h"])
    }
]


def run_test_suite(mode: str = "offline") -> dict:
    print(f"\n=======================================================")
    print(f"   MENJALANKAN TEST SUITE ASISTEN HILMI — MODE: {mode.upper()}")
    print(f"=======================================================")

    calc = FalakCalculator()
    brain = FalakAssistantBrain(calc)

    if mode == "offline":
        brain.set_api_key("")  # Force offline engine
    else:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            print("[Warning] GEMINI_API_KEY tidak ditemukan di environment, beralih ke mode offline.")
            brain.set_api_key("")
        else:
            brain.set_api_key(api_key)

    results = []
    passed_count = 0

    for tc in TEST_CASES:
        t_id = tc["id"]
        cat = tc["category"]
        query = tc["query"]
        session_id = f"session_{t_id}_{mode}"

        # Setup turn jika ada konteks multi-turn
        if "setup_query" in tc:
            brain.process_chat(
                message=tc["setup_query"],
                lat=-6.175392,
                lon=106.827153,
                session_id=session_id
            )

        # Process chat
        res = brain.process_chat(
            message=query,
            lat=-6.175392,
            lon=106.827153,
            session_id=session_id
        )

        reply = res["reply"]
        engine = res["engine"]

        # Run verification check
        try:
            is_passed = tc["check"](reply)
        except Exception:
            is_passed = False

        if is_passed:
            passed_count += 1
            status = "LULUS"
        else:
            status = "GAGAL"

        results.append({
            "id": t_id,
            "category": cat,
            "query": query,
            "reply": reply[:100] + ("..." if len(reply) > 100 else ""),
            "engine": engine,
            "status": status
        })

    # Print summary table
    print(f"{'ID':<6} | {'Kategori':<18} | {'Status':<6} | {'Engine':<24} | {'Pertanyaan'}")
    print("-" * 85)
    for r in results:
        print(f"{r['id']:<6} | {r['category']:<18} | {r['status']:<6} | {r['engine']:<24} | {r['query'][:26]}...")

    print(f"\nHASIL AKHIR: {passed_count} dari {len(TEST_CASES)} tes LULUS ({passed_count / len(TEST_CASES) * 100:.1f}%)")
    return {
        "mode": mode,
        "total": len(TEST_CASES),
        "passed": passed_count,
        "results": results
    }


def test_response_variation():
    print("\n=======================================================")
    print("   UJI VARIATIF JAWABAN (5 PERTANYAAN IDENTIK)")
    print("=======================================================")
    calc = FalakCalculator()
    brain = FalakAssistantBrain(calc)
    brain.set_api_key("")  # Test offline variations

    query = "Apa parameter kriteria baru MABIMS 2021?"
    replies = []
    for i in range(5):
        res = brain.process_chat(
            message=query,
            session_id=f"var_test_{i}"
        )
        replies.append(res["reply"])
        print(f"\n[Variasi {i+1}]:\n{res['reply']}")

    unique_replies = set(replies)
    print(f"\nJumlah jawaban unik dari 5 panggilan: {len(unique_replies)}/5")
    if len(unique_replies) > 1:
        print("[LULUS] Jawaban memiliki variasi bahasa dan tidak repetitif!")
    else:
        print("[GAGAL] Jawaban 100% identik.")


def test_api_endpoint_schema():
    print("\n=======================================================")
    print("   UJI SKEMA ENDPOINT /api/assistant/chat")
    print("=======================================================")
    from main import assistant_chat, AssistantChatRequest

    req = AssistantChatRequest(
        message="Berapa arah kiblat dari Jakarta?",
        latitude=-6.175392,
        longitude=106.827153,
        date=datetime.now(timezone.utc).isoformat(),
        history=[{"role": "user", "content": "Halo Hilmi"}],
        session_id="test_schema_session"
    )
    res = assistant_chat(req)
    if asyncio.iscoroutine(res):
        res = asyncio.run(res)
    assert "reply" in res, "Field 'reply' missing!"
    assert "engine" in res, "Field 'engine' missing!"
    assert "context" in res, "Field 'context' missing!"
    assert "timestamp" in res, "Field 'timestamp' missing!"
    print(f"[LULUS] Schema valid! Engine: {res['engine']}")
    print(f"Reply: {res['reply'][:65]}...")
    print(f"Context: {res['context']}")


if __name__ == "__main__":
    # 1. Jalankan mode offline
    offline_results = run_test_suite(mode="offline")

    # 2. Jalankan mode online jika API key tersedia
    if os.getenv("GEMINI_API_KEY"):
        run_test_suite(mode="online")

    # 3. Uji variasi respon
    test_response_variation()

    # 4. Uji endpoint FastAPI
    test_api_endpoint_schema()
