"""
HILTRON — Falak AI Assistant Brain (Hilmi) v3.0
Integrates Multi-Provider LLM Router (Gemini + Groq/OpenAI-compat + Ollama + Offline Expert),
Google Search Grounding, Two-Stage Astronomical Intent Engine, Multi-turn Memory,
In-Memory Response Caching, Security Guardrails, and Voice Preprocessing.
"""

import os
import math
import json
import re
import random
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, AsyncIterator

from astronomy.engine import FalakCalculator
from ai.knowledge_retriever import FalakKnowledgeRetriever
from ai.falak_tools import FalakTools
from ai.llm.base import LLMResult
from ai.llm.router import LLMRouter
from ai.speech_text import normalize_spoken_text


def clean_text_for_tts(text: str) -> str:
    """
    Membersihkan dan menormalisasi teks menjadi bahasa lisan percakapan santun
    menggunakan SpokenTextNormalizer dan Pronunciation Lexicon.
    """
    if not text:
        return ""
    return normalize_spoken_text(text)


def check_prompt_injection(message: str) -> bool:
    """Mendeteksi upaya jailbreak, hacking, atau pembocoran instruksi sistem dasar."""
    low = message.lower()
    patterns = [
        "ignore all previous instructions",
        "ignore previous instructions",
        "system prompt",
        "reveal your prompt",
        "show your instructions",
        "bocorkan instruksi",
        "tampilkan system prompt",
        "you are now dan",
        "jailbreak",
        "bypass safety",
        "abaikan instruksi sebelumnya",
        "meretas",
        "bobol",
        "sandi wifi",
        "hack sandi",
        "crack password"
    ]
    return any(p in low for p in patterns)


class FalakAssistantBrain:
    def __init__(self, calculator: FalakCalculator):
        self.calc = calculator
        self.tools = FalakTools(calculator)
        self.retriever = FalakKnowledgeRetriever()

        # In-memory session memory storage {session_id: dict}
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # Load offline city coordinates for location resolution
        self.cities: List[Dict[str, Any]] = self._load_offline_cities()

        # Path log unanswered queries
        self.log_dir = Path(__file__).resolve().parent.parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.unanswered_log_path = self.log_dir / "unanswered.jsonl"

        # Multi-Provider Router with Fallback & Circuit Breaker
        self.router = LLMRouter(brain=self)

    def _load_offline_cities(self) -> List[Dict[str, Any]]:
        cities_path = Path(__file__).resolve().parent.parent / "data" / "cities_offline.json"
        if cities_path.exists():
            try:
                with open(cities_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return [
            {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456, "aliases": ["jakarta", "dki"]},
            {"name": "Surabaya", "lat": -7.2575, "lon": 112.7521, "aliases": ["surabaya", "sby"]},
            {"name": "Bandung", "lat": -6.9175, "lon": 107.6191, "aliases": ["bandung"]},
            {"name": "Semarang", "lat": -6.9667, "lon": 110.4167, "aliases": ["semarang"]},
            {"name": "Yogyakarta", "lat": -7.7956, "lon": 110.3695, "aliases": ["jogja", "yogyakarta"]},
            {"name": "Banda Aceh", "lat": 5.5483, "lon": 95.3238, "aliases": ["aceh", "banda aceh"]},
            {"name": "Medan", "lat": 3.5952, "lon": 98.6722, "aliases": ["medan"]},
            {"name": "Makassar", "lat": -5.1477, "lon": 119.4327, "aliases": ["makassar", "ujung pandang"]}
        ]

    def set_api_key(self, key: str):
        """Metode bantuan untuk mengupdate API key Gemini di router."""
        if "gemini" in self.router.providers:
            p = self.router.providers["gemini"]
            p.api_key = key.strip()
            if hasattr(p, "_client") and key.strip():
                try:
                    from google import genai
                    p._client = genai.Client(api_key=key.strip())
                except Exception:
                    pass

    def resolve_city_in_text(self, text: str) -> Optional[Tuple[str, float, float]]:
        """Mendeteksi apakah nama kota Indonesia disebut dalam teks pertanyaan."""
        t_lower = text.lower()
        for c in self.cities:
            name_low = c["name"].lower().split(",")[0].strip()
            if re.search(rf"\b{re.escape(name_low)}\b", t_lower):
                return c["name"].split(",")[0].strip(), c["lat"], c["lon"]
            for alias in c.get("aliases", []):
                if re.search(rf"\b{re.escape(alias.lower())}\b", t_lower):
                    return c["name"].split(",")[0].strip(), c["lat"], c["lon"]
        return None

    def get_or_create_session(self, session_id: Optional[str]) -> Dict[str, Any]:
        sid = session_id or "default_session"
        if sid not in self.sessions:
            self.sessions[sid] = {
                "session_id": sid,
                "history": [],
                "state": {
                    "latitude": -6.175392,
                    "longitude": 106.827153,
                    "city_name": "Jakarta",
                    "active_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "active_topic": None
                }
            }
        return self.sessions[sid]

    def log_unanswered_query(self, message: str, confidence: float, reason: str):
        """Mencatat pertanyaan dengan confidence rendah atau tak terjawab untuk pembelajaran berkelanjutan."""
        try:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query": message,
                "confidence_score": round(confidence, 3),
                "reason": reason
            }
            with open(self.unanswered_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def detect_intent(self, user_message: str, previous_topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Klasifikasi intent fleksibel:
        - Membedakan pertanyaan kalkulasi hisab nyata vs pertanyaan konseptual/wawasan luas.
        """
        msg = user_message.lower().strip()

        is_concept_query = any(w in msg for w in [
            "apa perbedaan", "mengapa", "kenapa", "apa itu", "bagaimana kriteria",
            "kapan terjadinya", "sejarah", "tokoh", "biografi", "cara kalibrasi",
            "pengertian", "definisi", "syarat", "alasan", "faktor"
        ])

        # 1. Konversi Kalender Hijriah / Masehi
        if any(w in msg for w in ["konversikan", "konversi", "masehi ke hijriah", "hijriah ke masehi"]):
            return {"intent": "konversi_hijriah", "is_calculation": True}

        # 2. Hisab Hilal / Ketinggian Bulan
        if any(w in msg for w in ["hilal", "ramadhan", "syawal", "visibilitas", "ketinggian bulan"]):
            if not is_concept_query and any(w in msg for w in ["berapa tinggi", "hitung tinggi", "tinggi hilal", "elongasi", "hari ini"]):
                return {"intent": "hilal", "is_calculation": True}
            return {"intent": "hilal", "is_calculation": False}

        # 3. Jadwal Waktu Salat
        if any(w in msg for w in ["jadwal salat", "waktu salat", "jadwal sholat", "waktu sholat", "jam berapa saja", "subuh", "dzuhur", "ashar", "maghrib", "isya"]):
            return {"intent": "waktu_salat", "is_calculation": not is_concept_query}

        # 4. Arah Kiblat / Ka'bah
        if any(w in msg for w in ["kiblat", "qibla", "arah ka'bah", "derajat kiblat"]):
            if "rashdul" in msg or "bayangan" in msg or "kapan" in msg:
                return {"intent": "kiblat", "is_calculation": False}
            return {"intent": "kiblat", "is_calculation": not is_concept_query}

        # 5. Hardware Tracker Teleskop ESP32
        if any(w in msg for w in ["tracker", "teleskop", "esp32", "bno055", "stepper", "live lock"]):
            if "cara kalibrasi" in msg or "bagaimana cara" in msg:
                return {"intent": "tracker", "is_calculation": False}
            return {"intent": "tracker", "is_calculation": True}

        # 6. Pewarisan Konteks Lanjutan (Follow-up)
        if previous_topic and any(w in msg for w in ["kalau di", "bagaimana kalau", "terus kalau", "lalu bagaimana"]):
            return {"intent": previous_topic, "is_calculation": True}

        # 7. Pertanyaan Umum / Berita / Wawasan Luas
        return {"intent": "general_knowledge", "is_calculation": False}

    def execute_falak_tool(
        self,
        intent: str,
        lat: float,
        lon: float,
        date_str: str,
        telemetry: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Menjalankan fungsi kalkulator deterministik sesuai intent yang terdeteksi."""
        if intent == "hilal":
            return self.tools.hitung_hilal(lat, lon, date_str)
        elif intent == "waktu_salat":
            return self.tools.hitung_waktu_salat(lat, lon, date_str)
        elif intent == "kiblat":
            return self.tools.hitung_kiblat(lat, lon)
        elif intent == "konversi_hijriah":
            return self.tools.konversi_hijriah(date_str, to_hijri=True)
        elif intent == "tracker":
            return self.tools.status_tracker(telemetry)
        return {}

    def build_system_instruction(self, is_detailed_mode: bool = False) -> str:
        """
        Menyusun instruksi persona HILMI yang dioptimalkan khusus untuk percakapan lisan (Spoken-Style Prompting),
        hangat, santun khas santri, ilmiah, luwes, dan enak didengar telinga (Voice-First AI).
        """
        length_guide = (
            "Berikan penjelasan terstruktur dalam 4 hingga 6 kalimat yang mengalir nyaman didengar telinga, "
            "karena sahabat meminta penjelasan detail."
            if is_detailed_mode else
            "Jawab secara ringkas, to the point dalam 2 hingga 4 kalimat lisan yang padat dan bersahabat (maksimal 15 detik bicara)."
        )

        instruction = (
            "Anda adalah HILMI, asisten AI suara virtual dan astronom santri observatorium digital HILTRON FalakHub. "
            "Karakter Anda: santun khas santri Nusantara, ramah, berakhlak mulia, cerdas berwawasan luas seperti asisten AI serbabisa modern, "
            "dan ahli terpercaya dalam astronomi Islam (ilmu falak).\n\n"
            "=== PEDOMAN GAYA BICARA LISAN (SPOKEN-STYLE GUIDELINES) ===\n"
            "1. Tulis untuk Telinga, Bukan untuk Mata: Gunakan bahasa Indonesia lisan yang santun, luwes, dan mengalir seperti manusia sedang berbicara langsung, BUKAN teks artikel ensiklopedia atau buku teks kaku.\n"
            "2. Partikel & Penanda Tutur Lisan: Gunakan penanda tutur alami yang santun dan hangat (misalnya: 'Nah, sahabat...', 'Bismillah...', 'Alhamdulillah...', 'Mengenai hal tersebut...', 'Insya Allah...', 'Baik sahabat astronomi...'). Hindari pengulangan kata salam formal yang kaku di setiap giliran.\n"
            "3. Struktur Kalimat Bernafas: Susun kalimat dengan panjang sedang (8 hingga 20 kata per kalimat). Hindari kalimat majemuk beranak-pinak yang membuat suara TTS kehabisan nafas. Berikan jeda wajar dengan tanda koma dan titik yang tepat.\n"
            "4. DILARANG KERAS Format Visual: JANGAN PERNAH menggunakan simbol markdown bullet points (*, -), penomoran bertingkat (1., 2.), tanda pagar heading (#), tanda bintang tebal-miring (**kata**), tabel markdown, tanda kurung kurawal, atau rumus LaTeX ($x$). Tuliskan semuanya sebagai kalimat percakapan mengalir.\n"
            "5. Pengucapan Angka & Waktu: Sampaikan angka, derajat sudut, dan jam secara bersahabat (misalnya: 'sekitar tiga koma dua derajat', 'pukul empat sore lewat sepuluh menit').\n"
            f"6. Durasi & Panjang Ucapan: {length_guide}\n"
            "7. Integritas Data Hisab: Semua angka hisab (tinggi hilal, elongasi, jadwal salat, azimut kiblat, laju motor tracker) HARUS bersumber dari data kalkulasi astronomi nyata pada konteks. Jangan pernah mengarang angka hisab.\n"
            "8. Etika Fikih: Jangan memvonis penetapan 1 Ramadhan atau 1 Syawal secara mutlak atas nama pribadi. Sampaikan hisab ilmiahnya dan arahkan dengan santun untuk menunggu ketetapan resmi Sidang Isbat Kementerian Agama RI.\n\n"
            "=== CONTOH PERCAKAPAN LISAN ALAMI (FEW-SHOT EXAMPLES) ===\n"
            "Pengguna: 'Berapa tinggi hilal sore ini di Jakarta?'\n"
            "HILMI: 'Bismillah. Berdasarkan hisab untuk wilayah Jakarta saat maghrib nanti, tinggi hilal berada pada posisi dua koma delapan derajat, dengan elongasi geosentris lima koma satu derajat. Karena posisinya masih di bawah kriteria baru MABIMS, yaitu minimal tiga derajat dan elongasi enam koma empat derajat, kemungkinan besar hilal belum dapat teramati secara visual.'\n\n"
            "Pengguna: 'Ke mana arah kiblat dari Surabaya?'\n"
            "HILMI: 'Nah, untuk wilayah Surabaya, arah kiblat berada pada azimut dua ratus sembilan puluh empat derajat dari arah Utara sejati. Sahabat bisa memposisikan kompas teleskop sekitar dua puluh empat derajat condong ke utara dari arah barat persis.'\n\n"
            "Pengguna: 'Mengapa langit pada siang hari berwarna biru?'\n"
            "HILMI: 'Alhamdulillah, hal itu terjadi karena fenomena hamburan Rayleigh di atmosfer bumi kita. Molekul gas di udara menghamburkan cahaya biru bergelombang pendek jauh lebih kuat ke segala arah dibanding cahaya merah, sehingga langit tampak membiru cerah saat terkena sinar matahari.'"
        )
        return instruction

    def generate_offline_expert_response(
        self,
        user_message: str,
        retrieved_docs: List[Dict[str, Any]],
        tool_data: Dict[str, Any],
        session_state: Dict[str, Any],
        is_calculation_intent: bool
    ) -> str:
        """Mesin Pakar Falak Offline Lokal: 100% reliabel saat offline dengan template variatif."""
        msg = user_message.lower().strip()
        intent = session_state.get("active_topic") or "general_knowledge"

        openings = [
            "Bismillah.",
            "Alhamdulillah, pertanyaan yang sangat baik.",
            "Baik sahabat astronomi.",
            "Menarik sekali pertanyaannya.",
            "Mengenai hal tersebut,"
        ]
        chosen_opening = random.choice(openings)

        # 1. Sapaan / Identitas Santun
        if any(w in msg for w in ["assalamu", "halo", "hai", "siapa kamu", "nama kamu"]):
            sapaan_variations = [
                "Wa'alaikumussalam warahmatullahi wabarakatuh. Saya Hilmi, santri falak digital observatorium HILTRON. "
                "Senang sekali bisa mendampingi Anda belajar hisab hilal, jadwal salat, arah kiblat, maupun pelacakan teleskop.",

                "Assalamu'alaikum sahabat. Nama saya Hilmi, asisten astronomi Islam HILTRON FalakHub. "
                "Ada yang bisa saya bantu hitungkan seputar posisi hilal atau jadwal astronomi hari ini?",

                "Salam takzim sahabat falak. Saya Hilmi, rekan asisten digital observatorium Anda. "
                "Siap membantu hisab ephemeris, kriteria MABIMS, maupun kalibrasi arah kiblat."
            ]
            return clean_text_for_tts(random.choice(sapaan_variations))

        # 2. Pertanyaan Santun di Luar Topik (saat Offline Engine aktif)
        off_topic_words = [
            "resep masakan", "cara memasak", "cuaca hari ini", "ramalan cuaca", "sepak bola", "skor bola",
            "game online", "harga saham", "investasi saham", "crypto", "kripto", "bitcoin",
            "puisi cinta", "pacar", "sepeda motor", "karburator motor", "mobil antik", "bengkel mobil",
            "password wifi", "kata sandi"
        ]
        if any(w in msg for w in off_topic_words):
            return clean_text_for_tts(
                f"{chosen_opening} Pertanyaan yang menarik! Namun dalam mode offline observatorium HILTRON ini, "
                "fokus keahlian utama saya adalah seputar ilmu falak, hisab hilal, jadwal salat, dan pengoperasian teleskop. "
                "Ada yang ingin sahabat pelajari tentang peredaran matahari dan bulan hari ini?"
            )

        # 3. Pertanyaan Konseptual Knowledge Base
        if not is_calculation_intent and retrieved_docs and retrieved_docs[0].get("_retrieval_score", 0) >= 3.0:
            top_doc = retrieved_docs[0]
            summary = top_doc.get("ringkasan_singkat", "")
            detail = top_doc.get("penjelasan_lengkap", "")
            is_detail = any(w in msg for w in ["detail", "jelaskan", "lengkap", "rincian"])
            text_body = f"{summary} {detail}" if is_detail else summary

            variations = [
                f"{chosen_opening} {text_body}",
                f"{text_body}",
                f"Terkait hal tersebut, {text_body}"
            ]
            return clean_text_for_tts(random.choice(variations))

        # 4. Hitungan Nyata: Jadwal Salat
        if intent == "waktu_salat" and tool_data.get("jadwal"):
            j = tool_data["jadwal"]
            city = session_state.get("city_name", "Jakarta")
            variations = [
                f"{chosen_opening} Untuk wilayah {city}, jadwal salat hari ini adalah: "
                f"Subuh pukul {j['subuh']}, Terbit pukul {j['terbit']}, Dzuhur pukul {j['dzuhur']}, "
                f"Ashar pukul {j['ashar']}, Maghrib pukul {j['maghrib']}, dan Isya pukul {j['isya']} WIB.",

                f"Berdasarkan hisab standar Kementerian Agama untuk kawasan {city}, jadwal salat hari ini: "
                f"Imsak {j['imsak']}, Subuh {j['subuh']}, Dzuhur {j['dzuhur']}, Ashar {j['ashar']}, "
                f"Maghrib {j['maghrib']}, dan Isya {j['isya']}. Jadwal ini sudah dilengkapi ikhtiyat dua menit.",

                f"Berikut jadwal salat akurat untuk {city}: Subuh masuk pukul {j['subuh']}, "
                f"Dzuhur pukul {j['dzuhur']}, Ashar pukul {j['ashar']}, Maghrib pada pukul {j['maghrib']}, "
                f"dan Isya pukul {j['isya']}. Semoga ibadah kita lancar dan berkah."
            ]
            return clean_text_for_tts(random.choice(variations))

        # 5. Hitungan Nyata: Arah Kiblat
        if intent == "kiblat" and tool_data.get("azimuth_kiblat_derajat"):
            az = tool_data["azimuth_kiblat_derajat"]
            city = session_state.get("city_name", "lokasi Anda")
            jarak = tool_data.get("jarak_ke_kabah_km", 7900)
            variations = [
                f"{chosen_opening} Dari koordinat {city}, arah kiblat presisi mengarah pada azimuth {az} derajat "
                f"dari Utara sejati searah jarum jam, yaitu ke arah Barat Laut. Jarak lurus ke Ka'bah sekitar {jarak} kilometer.",

                f"Arah kiblat untuk wilayah {city} berada pada sudut {az} derajat dari arah Utara sejati. "
                f"Sebagai panduan visual, sahabat juga dapat memanfaatkan fenomena Rashdul Kiblat global pada tanggal 28 Mei dan 16 Juli.",

                f"Menghadap Ka'bah dari {city} memerlukan azimuth kompas sebesar {az} derajat. "
                f"Ini berada di antara arah Barat dan Utara, dengan jarak tempuh geodesik sekitar {jarak} kilometer ke Mekkah."
            ]
            return clean_text_for_tts(random.choice(variations))

        # 6. Hitungan Nyata: Hisab Hilal
        if intent == "hilal" and tool_data.get("tinggi_hilal_mari_derajat") is not None:
            alt = tool_data["tinggi_hilal_mari_derajat"]
            elon = tool_data["elongasi_geosentris_derajat"]
            status = tool_data["status_mabims"]
            tgl = tool_data.get("tanggal_hijriah", "")
            variations = [
                f"{chosen_opening} Menurut hisab ephemeris NASA JPL DE421 untuk tanggal {tgl}, "
                f"tinggi hilal mar'i saat matahari terbenam adalah {alt} derajat dengan sudut elongasi {elon} derajat. "
                f"Berdasarkan kriteria MABIMS 2021, statusnya adalah {status}.",

                f"Posisi hilal pada saat maghrib tercatat memiliki ketinggian {alt} derajat dan elongasi {elon} derajat. "
                f"Dengan parameter tersebut, status keterlihatan menurut standar MABIMS adalah {status}. "
                f"Untuk kepastian awal bulan, kita tetap menunggu hasil Sidang Isbat resmi pemerintah.",

                f"Data hisab astronomis menunjukkan tinggi hilal {alt} derajat serta jarak busur elongasi {elon} derajat. "
                f"Secara kriteria imkanur rukyat MABIMS baru, kondisi ini berstatus {status}."
            ]
            return clean_text_for_tts(random.choice(variations))

        # 7. Hitungan Nyata: Konversi Hijriah
        if intent == "konversi_hijriah" and tool_data.get("hijriah"):
            h = tool_data["hijriah"]
            m = tool_data.get("masehi", "")
            return clean_text_for_tts(
                f"Berdasarkan konversi kalender algoritma Umm al-Qura, tanggal {m} Masehi "
                f"bertepatan dengan tanggal {h.get('formatted', '')} Hijriah."
            )

        # 8. Hitungan Nyata: Status Tracker
        if intent == "tracker" and tool_data.get("status") == "success":
            mode = tool_data.get("mode", "Standby")
            conn = "sudah terhubung" if tool_data.get("connected") else "sedang dalam status siaga offline"
            variations = [
                f"Sistem pelacak teleskop HILTRON ditenagai mikrokontroler ESP32 yang saat ini {conn}. "
                f"Perangkat beroperasi dalam mode {mode} dengan kompensasi rotasi bumi 14,51 derajat per jam berbasis sensor BNO055 dan GPS NEO-6M.",

                f"Hardware tracker IoT HILTRON saat ini {conn} dengan mode {mode}. "
                f"Sistem siap melakukan penguncian benda langit otomatis untuk memandu lensa teleskop secara presisi."
            ]
            return clean_text_for_tts(random.choice(variations))

        # 9. Fallback Jujur (Unanswered)
        self.log_unanswered_query(
            message=user_message,
            confidence=retrieved_docs[0].get("_retrieval_score", 0.0) if retrieved_docs else 0.0,
            reason="Pertanyaan di luar cakupan knowledge base offline"
        )

        unanswered_variations = [
            f"{chosen_opening} Mohon maaf sahabat, untuk pertanyaan tersebut saya belum menemukan referensi kitab "
            "atau data astronomi yang cukup di memori offline saya. "
            "Namun saya sangat siap membantu sahabat seputar hisab hilal MABIMS, jadwal salat, arah kiblat, atau pengoperasian tracker teleskop. Ada yang ingin dihitung?",

            "Afwan sahabat, saya belum memiliki data rujukan yang pasti mengenai pertanyaan tersebut agar tidak keliru menjawab. "
            "Apakah sahabat ingin mengecek hisab posisi hilal, waktu salat daerah tertentu, atau arah kiblat saat ini?"
        ]
        return clean_text_for_tts(random.choice(unanswered_variations))

    async def process_chat_async(
        self,
        message: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        dt: Optional[datetime] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Memproses percakapan asisten HILMI secara asinkron dengan multi-provider fallback.
        """
        # Guardrail: Batasi panjang input (maksimal 500 karakter)
        sanitized_message = message[:500].strip()

        # Guardrail: Cek upaya prompt injection
        if check_prompt_injection(sanitized_message):
            refusal_text = (
                "Afwan sahabat, sebagai santri astronom di observatorium HILTRON, saya tetap berpegang "
                "pada etika santri dan amanah keilmuan. Ada yang bisa saya bantu seputar hisab hilal, "
                "waktu salat, atau astronomi Islam?"
            )
            return {
                "reply": refusal_text,
                "engine": "guardrail",
                "provider_used": "guardrail",
                "sources": [],
                "context": {"status": "guardrail_blocked"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        session = self.get_or_create_session(session_id)
        state = session["state"]

        # Batasi riwayat maksimal 8 giliran terakhir
        combined_history = list(session["history"])
        if history:
            combined_history = history[-8:]
        session["history"] = combined_history

        # 1. Update State Lokasi & Tanggal
        detected_city = self.resolve_city_in_text(sanitized_message)
        if detected_city:
            state["city_name"] = detected_city[0]
            state["latitude"] = detected_city[1]
            state["longitude"] = detected_city[2]
        elif lat is not None and lon is not None:
            state["latitude"] = lat
            state["longitude"] = lon
            state["city_name"] = f"Koordinat ({round(lat, 2)}, {round(lon, 2)})"

        if dt is not None:
            state["active_date"] = dt.strftime("%Y-%m-%d")

        obs_lat = state["latitude"]
        obs_lon = state["longitude"]
        obs_date_str = state["active_date"]

        # 2. Deteksi Intent (Strategi Dua Tahap)
        previous_topic = state.get("active_topic")
        intent_info = self.detect_intent(sanitized_message, previous_topic=previous_topic)
        intent = intent_info["intent"]
        is_calc = intent_info.get("is_calculation", False)

        if intent != "general_knowledge":
            state["active_topic"] = intent

        # 3. Knowledge Retrieval (RAG Ringan)
        retrieved_docs = self.retriever.retrieve(sanitized_message, top_k=3, min_score=1.0)

        # 4. Kalkulasi Tool Falak Nyata (Deterministik)
        tool_data = {}
        if intent in ["hilal", "waktu_salat", "kiblat", "konversi_hijriah", "tracker"]:
            tool_data = self.execute_falak_tool(intent, obs_lat, obs_lon, obs_date_str, telemetry)

        # 5. Susun Konteks Prompt untuk LLM
        is_detailed = any(w in sanitized_message.lower() for w in ["detail", "jelaskan lebih detail", "rincian", "lengkap", "panjang"])
        system_instruction = self.build_system_instruction(is_detailed)

        rag_section = self.retriever.format_for_prompt(retrieved_docs)
        tool_section = ""
        if tool_data:
            tool_section = (
                "=== HASIL KALKULASI ALAT ASTRONOMI NYATA (ANGKA RESMI) ===\n"
                f"{json.dumps(tool_data, indent=2, ensure_ascii=False, default=str)}\n"
                "Gunakan angka-angka presisi di atas sebagai fakta hitungan astronomis resmi."
            )

        state_section = (
            f"=== DATA STATUS PENGAMAT ===\n"
            f"- Lokasi: {state.get('city_name', 'Jakarta')} (Lat: {obs_lat}, Lon: {obs_lon})\n"
            f"- Tanggal Hisab: {obs_date_str}\n"
            f"- Topik Aktif Sebelumnya: {state.get('active_topic') or 'Baru Dimulai'}"
        )

        current_prompt = (
            f"{state_section}\n\n"
            f"{tool_section}\n\n"
            f"{rag_section}\n\n"
            f"Pertanyaan Pengguna Sekarang: \"{sanitized_message}\"\n\n"
            "Berikan jawaban santri astronom yang hangat, cerdas, berwawasan luas, dan ilmiah."
        )

        # Siapkan format pesan LLM
        messages = []
        for turn in combined_history:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
        messages.append({"role": "user", "content": current_prompt})

        # Strategi Grounding: Hanya aktifkan Google Search jika BUKAN kalkulasi hisab murni
        enable_grounding = (not is_calc)

        # Strategi Caching: Hanya cache pertanyaan umum/konseptual non-personal
        is_cacheable = (intent == "general_knowledge" and not is_calc and not detected_city)

        max_tokens = 600 if is_detailed else 250

        # Eksekusi via Multi-Provider Router dengan Fallback
        llm_result = await self.router.generate(
            messages=messages,
            system=system_instruction,
            tools=None,
            enable_grounding=enable_grounding,
            temperature=0.7,
            max_output_tokens=max_tokens,
            is_cacheable=is_cacheable,
            is_detailed=is_detailed,
            retrieved_docs=retrieved_docs,
            tool_data=tool_data,
            session_state=state,
            is_calculation_intent=is_calc,
            user_query=sanitized_message
        )

        clean_reply = clean_text_for_tts(llm_result.text)

        # Catat giliran percakapan ke riwayat session
        session["history"].append({"role": "user", "content": sanitized_message})
        session["history"].append({"role": "assistant", "content": clean_reply})
        if len(session["history"]) > 12:
            session["history"] = session["history"][-12:]

        context_res = {
            "city": state.get("city_name"),
            "latitude": obs_lat,
            "longitude": obs_lon,
            "date": obs_date_str,
            "active_topic": state.get("active_topic"),
            "intent": intent,
            "tool_data": tool_data,
            "retrieved_topics": [d.get("topik") for d in retrieved_docs]
        }

        return {
            "reply": clean_reply,
            "engine": f"{llm_result.provider_name}/{llm_result.model_name}",
            "provider_used": llm_result.provider_name,
            "sources": llm_result.sources or [],
            "latency_ms": llm_result.latency_ms,
            "context": context_res,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def process_chat(
        self,
        message: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        dt: Optional[datetime] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Wrapper sinkron untuk backward compatibility dan unit testing."""
        coro = self.process_chat_async(message, lat, lon, dt, telemetry, history, session_id)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    async def process_chat_stream(
        self,
        message: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        dt: Optional[datetime] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming generator: menghasilkan potongan kata/kalimat segera saat dibuat
        agar sintesis suara TTS di frontend dapat segera dimulai (sub-second TTS response).
        """
        sanitized_message = message[:500].strip()

        # Guardrail check
        if check_prompt_injection(sanitized_message):
            refusal = "Afwan sahabat, saya tetap berpegang pada amanah keilmuan dan etika santri."
            yield {"type": "sentence", "text": refusal, "provider": "guardrail"}
            yield {"type": "done", "full_text": refusal, "provider": "guardrail", "sources": []}
            return

        session = self.get_or_create_session(session_id)
        state = session["state"]

        detected_city = self.resolve_city_in_text(sanitized_message)
        if detected_city:
            state["city_name"] = detected_city[0]
            state["latitude"] = detected_city[1]
            state["longitude"] = detected_city[2]
        elif lat is not None and lon is not None:
            state["latitude"] = lat
            state["longitude"] = lon
            state["city_name"] = f"Koordinat ({round(lat, 2)}, {round(lon, 2)})"

        if dt is not None:
            state["active_date"] = dt.strftime("%Y-%m-%d")

        obs_lat = state["latitude"]
        obs_lon = state["longitude"]
        obs_date_str = state["active_date"]

        previous_topic = state.get("active_topic")
        intent_info = self.detect_intent(sanitized_message, previous_topic=previous_topic)
        intent = intent_info["intent"]
        is_calc = intent_info.get("is_calculation", False)

        if intent != "general_knowledge":
            state["active_topic"] = intent

        retrieved_docs = self.retriever.retrieve(sanitized_message, top_k=3, min_score=1.0)
        tool_data = {}
        if intent in ["hilal", "waktu_salat", "kiblat", "konversi_hijriah", "tracker"]:
            tool_data = self.execute_falak_tool(intent, obs_lat, obs_lon, obs_date_str, telemetry)

        is_detailed = any(w in sanitized_message.lower() for w in ["detail", "jelaskan", "lengkap"])
        system_instruction = self.build_system_instruction(is_detailed)

        rag_section = self.retriever.format_for_prompt(retrieved_docs)
        tool_section = f"=== HASIL KALKULASI ALAT ASTRONOMI NYATA ===\n{json.dumps(tool_data, indent=2, default=str)}\n" if tool_data else ""
        state_section = f"=== STATUS PENGAMAT ===\nLokasi: {state.get('city_name')} (Lat: {obs_lat}, Lon: {obs_lon})\nTanggal: {obs_date_str}"

        current_prompt = f"{state_section}\n\n{tool_section}\n\n{rag_section}\nPertanyaan Pengguna: \"{sanitized_message}\""

        combined_history = (history or session["history"])[-8:]
        messages = [{"role": turn.get("role", "user"), "content": turn.get("content", "")} for turn in combined_history]
        messages.append({"role": "user", "content": current_prompt})

        sentence_buffer = ""
        full_response_text = ""
        provider_used = "unknown"

        async for chunk, provider_name in self.router.stream(
            messages=messages,
            system=system_instruction,
            tools=None,
            enable_grounding=(not is_calc),
            temperature=0.7,
            max_output_tokens=600 if is_detailed else 250,
            retrieved_docs=retrieved_docs,
            tool_data=tool_data,
            session_state=state,
            is_calculation_intent=is_calc,
            user_query=sanitized_message
        ):
            provider_used = provider_name
            full_response_text += chunk
            sentence_buffer += chunk

            # Deteksi batas kalimat (. ! ? atau newline) untuk segera dipancarkan ke TTS
            match = re.search(r"([.!?]+[\s\n]+)", sentence_buffer)
            if match:
                end_idx = match.end()
                complete_sentence = sentence_buffer[:end_idx].strip()
                sentence_buffer = sentence_buffer[end_idx:]
                if complete_sentence:
                    cleaned_sentence = clean_text_for_tts(complete_sentence)
                    if cleaned_sentence:
                        yield {
                            "type": "sentence",
                            "text": cleaned_sentence,
                            "provider": provider_used
                        }

        # Sisa buffer terakhir jika ada
        if sentence_buffer.strip():
            cleaned_rem = clean_text_for_tts(sentence_buffer.strip())
            if cleaned_rem:
                yield {
                    "type": "sentence",
                    "text": cleaned_rem,
                    "provider": provider_used
                }

        final_clean = clean_text_for_tts(full_response_text)
        session["history"].append({"role": "user", "content": sanitized_message})
        session["history"].append({"role": "assistant", "content": final_clean})

        yield {
            "type": "done",
            "full_text": final_clean,
            "provider": provider_used,
            "sources": []
        }
