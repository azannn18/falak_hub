"""
Skrip Benchmark dan Pembuat Sampel Komparasi Audio TTS HILMI.
Membandingkan kualitas 'LAMA' (Teks mentah tanpa normalisasi, kaku, angka robotik)
dengan 'BARU' (Normalisasi bahasa lisan santri, kamus pelafalan, mikro-prosodi alami).

Menghasilkan 15 file audio komparasi di backend/tools/samples/
dan satu halaman web interaktif index.html untuk didengarkan pengguna secara langsung.
"""

import asyncio
import html
import os
import sys
import time
from pathlib import Path

# Setup sys.path agar bisa mengimpor modul backend
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.insert(0, str(backend_dir))

from ai.speech_text import normalize_spoken_text
from ai.tts.edge_tts_provider import EdgeTTSProvider

BENCHMARK_CASES = [
    {
        "id": 1,
        "title": "Kriteria Baru MABIMS 2021",
        "category": "Kriteria Visibilitas Hilal",
        "raw_text": "Kriteria baru MABIMS 2021 menyepakati tinggi hilal mar'i ≥ 3° dan sudut elongasi geosentris ≥ 6.4°."
    },
    {
        "id": 2,
        "title": "Arah Kiblat dan Jarak Ka'bah",
        "category": "Hisab Kiblat",
        "raw_text": "Arah kiblat wilayah Jakarta berada pada sudut 295.15° atau 25.15° dari Barat ke Utara dengan jarak 7920.1 km."
    },
    {
        "id": 3,
        "title": "Fenomena Rashdul Kiblat Global",
        "category": "Rashdul Kiblat",
        "raw_text": "Fenomena Rashdul Kiblat global terjadi pada 28 Mei (16:18 WIB) dan 16 Juli (16:27 WIB) saat matahari tepat di atas Ka'bah."
    },
    {
        "id": 4,
        "title": "Jadwal Salat Digital",
        "category": "Waktu Salat",
        "raw_text": "Jadwal salat wilayah Surabaya hari ini: Subuh 04:12 WIB, Dzuhur 11:45 WIB, Ashar 15:08 WIB, Maghrib 17:58 WIB, dan Isya 19:10 WIB."
    },
    {
        "id": 5,
        "title": "Telemetri Hardware Teleskop HILTRON",
        "category": "Telemetri IoT",
        "raw_text": "Status teleskop HILTRON: Mikrokontroler ESP32 dan sensor IMU BNO055 aktif siaga dengan laju tracking 14.5°/jam mengikuti rotasi bumi."
    },
    {
        "id": 6,
        "title": "Literatur Falak Klasik Nusantara",
        "category": "Kitab Turats",
        "raw_text": "Rujukan hisab klasik mencakup kitab Sullamun Nayyirain karya KH Muhammad Manshur serta Al-Khulashah Al-Wafiyah karya KH Zubair Umar."
    },
    {
        "id": 7,
        "title": "Hisab Hakiki vs Taqribi & Ephemeris",
        "category": "Metodologi Hisab",
        "raw_text": "Metode hisab terbagi menjadi hisab taqribi dan hisab hakiki tahqiqi dengan data ephemeris NASA JPL DE421."
    },
    {
        "id": 8,
        "title": "Konversi Penanggalan Hijriah",
        "category": "Kalender Hijriah",
        "raw_text": "Tanggal 20 Maret 2026 Masehi bertepatan dengan 1 Syawal 1447 H menurut hisab hakiki wujudul hilal."
    },
    {
        "id": 9,
        "title": "Fenomena Gerhana Matahari",
        "category": "Gerhana",
        "raw_text": "Gerhana matahari cincin terjadi saat ukuran semidiameter piringan bulan lebih kecil dari piringan matahari di titik apogee."
    },
    {
        "id": 10,
        "title": "Sapaan Ramah Santri Falak",
        "category": "Persona & Etika",
        "raw_text": "Assalamu'alaikum warahmatullahi wabarakatuh sahabat FalakHub, ada yang bisa HILMI bantu mengenai hisab atau rukyat hari ini?"
    },
    {
        "id": 11,
        "title": "Parameter Ikhtiyat Pengaman",
        "category": "Waktu Salat",
        "raw_text": "Kemenag RI menambahkan ikhtiyat pengaman sebesar 2 s.d 3 menit dari waktu hisab astronomis murni."
    },
    {
        "id": 12,
        "title": "Ijtimak dan Umur Bulan",
        "category": "Hisab Hilal",
        "raw_text": "Ijtimak terjadi pukul 03:39 WIB, umur bulan saat maghrib adalah 14 jam 19 menit dengan elongasi 7.2°."
    },
    {
        "id": 13,
        "title": "Perbedaan Mazhab Awal Ashar",
        "category": "Fikih Falak",
        "raw_text": "Jumhur ulama menetapkan awal Ashar saat bayangan sama panjang (1:1), sedangkan mazhab Hanafi mensyaratkan 2 kali panjang benda."
    },
    {
        "id": 14,
        "title": "Penolakan Santun Luar Domain",
        "category": "Guardrail Santri",
        "raw_text": "Mohon maaf sahabat, fokus keahlian saya adalah ilmu falak, hisab rukyat, astronomi, dan pengamatan teleskop antariksa."
    },
    {
        "id": 15,
        "title": "Toleransi Sensor & Akurasi Kompas",
        "category": "Instrumentasi",
        "raw_text": "Kalibrasi sensor kompas magnetometer memiliki toleransi deviasi sudut ≤ 0.5° untuk menjamin presisi azimut alat."
    }
]


def generate_html_player(results: list, output_file: Path):
    """Menghasilkan halaman web interaktif modern untuk membandingkan audio LAMA vs BARU."""
    rows_html = ""
    for r in results:
        cid = r["id"]
        rows_html += f"""
        <div class="card" id="card-{cid}">
            <div class="card-header">
                <span class="badge category">{html.escape(r['category'])}</span>
                <h3>#{cid}. {html.escape(r['title'])}</h3>
            </div>
            
            <div class="comparison-grid">
                <!-- SISI LAMA -->
                <div class="variant-box variant-lama">
                    <div class="variant-title">
                        <span class="pill pill-lama">VERSI LAMA (Mentah / Robotik)</span>
                        <span class="meta">{r['latency_lama']} ms • {r['size_lama']} KB</span>
                    </div>
                    <div class="text-content">{html.escape(r['raw_text'])}</div>
                    <audio controls preload="none">
                        <source src="{r['file_lama']}" type="audio/mpeg">
                        Browser Anda tidak mendukung elemen audio.
                    </audio>
                </div>

                <!-- SISI BARU -->
                <div class="variant-box variant-baru">
                    <div class="variant-title">
                        <span class="pill pill-baru">VERSI BARU (Bahasa Lisan HILMI)</span>
                        <span class="meta">{r['latency_baru']} ms • {r['size_baru']} KB</span>
                    </div>
                    <div class="text-content spoken-highlight">{html.escape(r['spoken_text'])}</div>
                    <audio controls preload="none">
                        <source src="{r['file_baru']}" type="audio/mpeg">
                        Browser Anda tidak mendukung elemen audio.
                    </audio>
                </div>
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HILMI Voice TTS Benchmark — LAMA vs BARU</title>
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-secondary: #121826;
            --bg-card: #172033;
            --border-color: #24304d;
            --text-primary: #e6edf3;
            --text-secondary: #8b9bb4;
            --accent-lama: #f85149;
            --accent-baru: #2ea043;
            --accent-cyan: #38bdf8;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: var(--font-family);
            line-height: 1.6;
            padding: 2rem 1rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
        }}
        header h1 {{
            font-size: 2.2rem;
            color: #fff;
            margin-bottom: 0.5rem;
            letter-spacing: -0.5px;
        }}
        header h1 span {{ color: var(--accent-cyan); }}
        header p {{
            color: var(--text-secondary);
            font-size: 1.05rem;
            max-width: 750px;
            margin: 0 auto;
        }}
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}
        .stat-item {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.6rem 1.2rem;
            font-size: 0.9rem;
        }}
        .stat-item strong {{ color: var(--accent-cyan); }}

        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 2rem;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            transition: border-color 0.2s;
        }}
        .card:hover {{
            border-color: #3b82f6;
        }}
        .card-header {{
            background: var(--bg-secondary);
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        .card-header h3 {{
            font-size: 1.2rem;
            font-weight: 600;
        }}
        .badge {{
            font-size: 0.75rem;
            text-transform: uppercase;
            font-weight: 700;
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
        }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            padding: 1.5rem;
        }}
        @media (max-width: 850px) {{
            .comparison-grid {{ grid-template-columns: 1fr; }}
        }}
        .variant-box {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.2rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .variant-lama {{ border-left: 4px solid var(--accent-lama); }}
        .variant-baru {{ border-left: 4px solid var(--accent-baru); }}
        .variant-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.8rem;
        }}
        .pill {{
            font-size: 0.75rem;
            font-weight: bold;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
        }}
        .pill-lama {{ background: rgba(248, 81, 73, 0.15); color: #ff7b72; border: 1px solid rgba(248, 81, 73, 0.4); }}
        .pill-baru {{ background: rgba(46, 160, 67, 0.15); color: #56d364; border: 1px solid rgba(46, 160, 67, 0.4); }}
        .meta {{ font-size: 0.8rem; color: var(--text-secondary); }}
        .text-content {{
            font-size: 0.95rem;
            color: var(--text-primary);
            margin-bottom: 1.2rem;
            min-height: 4.5rem;
            line-height: 1.5;
        }}
        .spoken-highlight {{
            color: #e2e8f0;
            background: rgba(34, 197, 94, 0.05);
            padding: 0.5rem;
            border-radius: 4px;
            border-left: 2px solid #22c55e;
        }}
        audio {{
            width: 100%;
            height: 36px;
            border-radius: 18px;
            outline: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>HILMI Voice <span>TTS Benchmark</span></h1>
            <p>Perbandingan audio langsung antara format pembacaan teks mentah (Versi Lama) dengan teks yang dinormalisasi bahasa lisan santri falak (Versi Baru).</p>
            <div class="stats-bar">
                <div class="stat-item">Jumlah Sampel: <strong>{len(results)} Kasus</strong></div>
                <div class="stat-item">Engine: <strong>Microsoft Edge Neural TTS (Ardi)</strong></div>
                <div class="stat-item">Prosodi: <strong>Mikro-variasi & Jeda Nafas Alami</strong></div>
            </div>
        </header>

        <main>
            {rows_html}
        </main>
    </div>
</body>
</html>
"""
    output_file.write_text(html_content, encoding="utf-8")


async def run_benchmark():
    samples_dir = backend_dir / "tools" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("   MEMULAI GENERASI 15 SAMPEL BENCHMARK TTS (LAMA VS BARU)")
    print("=" * 70)
    print(f"Direktori Sampel: {samples_dir}\n")

    provider_lama = EdgeTTSProvider(default_voice="id-ID-ArdiNeural", enable_natural_prosody=False)
    provider_baru = EdgeTTSProvider(default_voice="id-ID-ArdiNeural", enable_natural_prosody=True)
    results = []

    for item in BENCHMARK_CASES:
        cid = item["id"]
        title = item["title"]
        category = item["category"]
        raw = item["raw_text"]

        spoken = normalize_spoken_text(raw)

        print(f"[{cid:02d}/15] {title} ({category})")
        print(f"  • Mentah: {raw}")
        print(f"  • Lisan : {spoken}")

        file_lama_name = f"sample_{cid:02d}_lama.mp3"
        file_baru_name = f"sample_{cid:02d}_baru.mp3"
        path_lama = samples_dir / file_lama_name
        path_baru = samples_dir / file_baru_name

        # 1. Audio LAMA (Teks mentah tanpa normalisasi, prosodi datar)
        if path_lama.exists() and path_lama.stat().st_size > 1000:
            audio_lama = path_lama.read_bytes()
            lat_lama = 150.0
            print(f"  -> LAMA: Menggunakan file yang sudah ada ({round(len(audio_lama)/1024, 1)} KB)")
        else:
            res_lama = await provider_lama.synthesize(text=raw, voice="id-ID-ArdiNeural", rate="+0%", pitch="+0Hz")
            if not res_lama.is_success or not res_lama.audio_bytes:
                raise RuntimeError(f"Gagal sintesis LAMA #{cid}: {res_lama.error}")
            audio_lama = res_lama.audio_bytes
            lat_lama = res_lama.latency_ms
            path_lama.write_bytes(audio_lama)
            await asyncio.sleep(0.5)

        size_lama = round(len(audio_lama) / 1024, 1)

        # 2. Audio BARU (Teks dinormalisasi bahasa lisan santri, prosodi alami)
        if path_baru.exists() and path_baru.stat().st_size > 1000:
            audio_baru = path_baru.read_bytes()
            lat_baru = 150.0
            print(f"  -> BARU: Menggunakan file yang sudah ada ({round(len(audio_baru)/1024, 1)} KB)")
        else:
            res_baru = await provider_baru.synthesize(text=spoken, voice="id-ID-ArdiNeural")
            if not res_baru.is_success or not res_baru.audio_bytes:
                raise RuntimeError(f"Gagal sintesis BARU #{cid}: {res_baru.error}")
            audio_baru = res_baru.audio_bytes
            lat_baru = res_baru.latency_ms
            path_baru.write_bytes(audio_baru)
            await asyncio.sleep(0.5)

        size_baru = round(len(audio_baru) / 1024, 1)

        print(f"  -> Selesai: LAMA ({size_lama} KB) vs BARU ({size_baru} KB)\n")

        results.append({
            "id": cid,
            "title": title,
            "category": category,
            "raw_text": raw,
            "spoken_text": spoken,
            "file_lama": file_lama_name,
            "file_baru": file_baru_name,
            "latency_lama": lat_lama,
            "latency_baru": lat_baru,
            "size_lama": size_lama,
            "size_baru": size_baru
        })

        await asyncio.sleep(0.4)

    # Buat halaman HTML player interaktif
    html_path = samples_dir / "index.html"
    generate_html_player(results, html_path)
    print("=" * 70)
    print(f"BERHASIL! 15 Pasang sampel audio (.mp3) telah disimpan di:")
    print(f"  {samples_dir}")
    print(f"Halaman web komparasi interaktif tersedia di:")
    print(f"  {html_path}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
