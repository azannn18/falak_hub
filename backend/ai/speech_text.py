"""
HILTRON FalakHub — Spoken Text Normalizer for Voice AI (HILMI).
Converts raw LLM responses and astronomical calculation outputs into natural,
fluent, human-like spoken Indonesian text ready for Neural TTS synthesis.
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


# ═══════════════════════════════════════════ 1. BILANGAN TERBILANG INDONESIA ═══
SATUAN = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]


def integer_to_words(n: int) -> str:
    """Mengubah bilangan bulat non-negatif ke teks terbilang bahasa Indonesia."""
    if n < 0:
        return f"minus {integer_to_words(abs(n))}"
    if n == 0:
        return "nol"
    if n < 12:
        return SATUAN[n]
    if n < 20:
        return f"{integer_to_words(n - 10)} belas"
    if n < 100:
        belas = n % 10
        rem = f" {integer_to_words(belas)}" if belas != 0 else ""
        return f"{integer_to_words(n // 10)} puluh{rem}"
    if n < 200:
        rem = f" {integer_to_words(n - 100)}" if n > 100 else ""
        return f"seratus{rem}"
    if n < 1000:
        rem = f" {integer_to_words(n % 100)}" if (n % 100) != 0 else ""
        return f"{integer_to_words(n // 100)} ratus{rem}"
    if n < 2000:
        rem = f" {integer_to_words(n - 1000)}" if n > 1000 else ""
        return f"seribu{rem}"
    if n < 1_000_000:
        rem = f" {integer_to_words(n % 1000)}" if (n % 1000) != 0 else ""
        return f"{integer_to_words(n // 1000)} ribu{rem}"
    if n < 1_000_000_000:
        rem = f" {integer_to_words(n % 1_000_000)}" if (n % 1_000_000) != 0 else ""
        return f"{integer_to_words(n // 1_000_000)} juta{rem}"
    if n < 1_000_000_000_000:
        rem = f" {integer_to_words(n % 1_000_000_000)}" if (n % 1_000_000_000) != 0 else ""
        return f"{integer_to_words(n // 1_000_000_000)} miliar{rem}"
    return str(n)


def decimal_to_words(num_str: str) -> str:
    """Mengubah bilangan desimal (misal '295.15' atau '6,4') ke teks lisan alami."""
    cleaned = num_str.replace(",", ".")
    is_negative = cleaned.startswith("-")
    if is_negative:
        cleaned = cleaned[1:]

    prefix = "minus " if is_negative else ""

    if "." not in cleaned:
        try:
            return f"{prefix}{integer_to_words(int(cleaned))}"
        except ValueError:
            return num_str

    parts = cleaned.split(".", 1)
    int_part = int(parts[0]) if parts[0] else 0
    dec_digits = parts[1]

    int_words = integer_to_words(int_part)
    digit_words_map = {
        "0": "nol", "1": "satu", "2": "dua", "3": "tiga", "4": "empat",
        "5": "lima", "6": "enam", "7": "tujuh", "8": "delapan", "9": "sembilan"
    }
    dec_words = " ".join(digit_words_map.get(d, d) for d in dec_digits)
    return f"{prefix}{int_words} koma {dec_words}"


# ═══════════════════════════════════════════ 2. SPONTANEOUS TEXT NORMALIZER ═══

class SpokenTextNormalizer:
    """
    Normalizer teks komprehensif untuk mengubah teks visual teknis falak
    menjadi teks lisan yang luwes, alami, dan berirama enak didengar.
    """

    def __init__(self, lexicon_path: Optional[Path] = None):
        self.lexicon_path = lexicon_path or (Path(__file__).resolve().parent / "pronunciation_lexicon.json")
        self.lexicon_entries = self._load_lexicon()

    def _load_lexicon(self) -> List[Dict[str, str]]:
        if self.lexicon_path.exists():
            try:
                with open(self.lexicon_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("entries", [])
            except Exception:
                pass
        return []

    def clean_markdown_and_artifacts(self, text: str) -> str:
        """Menghapus markdown, tag HTML, sitasi, tautan web, emoji, dan simbol visual kaku."""
        if not text:
            return ""

        t = text

        # 1. Sitasi grounding dan URL web
        t = re.sub(r"\[\d+\]", "", t)
        t = re.sub(r"https?://\S+", "", t)

        # 2. Markdown links [text](url) -> text
        t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)

        # 3. Headers, bullet points, numbering list visual
        t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
        t = re.sub(r"^\s*[-*•]\s*", "", t, flags=re.MULTILINE)
        t = re.sub(r"^\s*\d+\.\s*", "", t, flags=re.MULTILINE)

        # 4. Bold, italic, inline code, code blocks
        t = re.sub(r"```[\s\S]*?```", "", t)
        t = re.sub(r"`(.*?)`", r"\1", t)
        t = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", t)
        t = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", t)
        t = re.sub(r"~~(.*?)~~", r"\1", t)

        # 5. LaTeX / Math delimiters ($x$, $$x$$)
        t = re.sub(r"\$\$(.*?)\$\$", r"\1", t)
        t = re.sub(r"\$(.*?)\$", r"\1", t)

        # 6. Bersihkan tanda kurung yang mengurung akronim atau istilah:
        # e.g. "(MABIMS)" -> ", MABIMS,"
        # e.g. "(imkanur rukyat)" -> ", imkanur rukyat,"
        t = re.sub(r"\(([^\)]+)\)", r", \1, ", t)

        # 7. Garis miring yang berarti "atau": "Standby / Offline" -> "Standby atau Offline"
        t = re.sub(r"\s+/\s+", " atau ", t)

        # 8. Hapus karakter kutip ganda atau tanda kutip markdown
        t = re.sub(r'["“”]', "", t)

        return t.strip()

    def normalize_times(self, text: str) -> str:
        """
        Mengubah format jam digital (e.g. '03:39', '06:15 WIB', '17:29')
        menjadi ucapan lisan alami: 'pukul tiga lebih tiga puluh sembilan menit'.
        """
        def replace_time(match):
            hour = int(match.group(1))
            minute = int(match.group(2))
            tz = match.group(3)

            hour_words = integer_to_words(hour)
            if minute == 0:
                min_words = "tepat"
            elif minute == 15:
                min_words = "lewat lima belas menit"
            elif minute == 30:
                min_words = "lewat tiga puluh menit"
            else:
                min_words = f"lewat {integer_to_words(minute)} menit"

            tz_words = ""
            if tz:
                tz_clean = tz.upper()
                if tz_clean == "WIB":
                    tz_words = " W-I-B"
                elif tz_clean == "WITA":
                    tz_words = " Wita"
                elif tz_clean == "WIT":
                    tz_words = " W-I-T"
                elif tz_clean == "UTC":
                    tz_words = " U-T-C"

            return f"pukul {hour_words} {min_words}{tz_words}"

        # Regex waktu: 'pukul HH:MM', 'jam HH:MM', atau 'HH:MM WIB'
        t = re.sub(r"(?:(?:pukul|jam)\s+)?([012]?\d):([0-5]\d)(?:\s*(WIB|WITA|WIT|UTC))?", replace_time, text, flags=re.IGNORECASE)
        return t

    def normalize_comparisons_and_rates(self, text: str) -> str:
        """
        Mengubah simbol perbandingan matematika dan laju perubahan:
        e.g. '≥ 3°' -> 'minimal tiga derajat'
        e.g. '14.5°/jam' -> 'empat belas koma lima derajat per jam'
        """
        t = text

        # Laju rotasi derajat/jam
        def replace_deg_rate(m):
            num = decimal_to_words(m.group(1))
            return f"{num} derajat per jam"

        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:°|derajat)\s*/\s*jam", replace_deg_rate, t, flags=re.IGNORECASE)

        # Laju km/jam
        def replace_km_rate(m):
            num = decimal_to_words(m.group(1))
            return f"{num} kilometer per jam"

        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*km\s*/\s*jam", replace_km_rate, t, flags=re.IGNORECASE)

        # Perbandingan derajat: ≥ 3°, >= 3 derajat, dll.
        def replace_gte_deg(m):
            num = decimal_to_words(m.group(1))
            return f"minimal {num} derajat"

        t = re.sub(r"(?:≥|>=|minimal)\s*(\d+(?:[.,]\d+)?)\s*(?:°|derajat)?", replace_gte_deg, t, flags=re.IGNORECASE)

        def replace_lte_deg(m):
            num = decimal_to_words(m.group(1))
            return f"maksimal {num} derajat"

        t = re.sub(r"(?:≤|<=|maksimal)\s*(\d+(?:[.,]\d+)?)\s*(?:°|derajat)?", replace_lte_deg, t, flags=re.IGNORECASE)

        def replace_gt_deg(m):
            num = decimal_to_words(m.group(1))
            return f"lebih dari {num} derajat"

        t = re.sub(r">\s*(\d+(?:[.,]\d+)?)\s*(?:°|derajat)?", replace_gt_deg, t)

        def replace_lt_deg(m):
            num = decimal_to_words(m.group(1))
            return f"kurang dari {num} derajat"

        t = re.sub(r"<\s*(\d+(?:[.,]\d+)?)\s*(?:°|derajat)?", replace_lt_deg, t)

        return t

    def normalize_astronomy_units(self, text: str) -> str:
        """
        Mengubah satuan astronomi dan sudut (derajat, persen, kilometer) ke kata lisan:
        e.g. '295.15°' -> 'dua ratus sembilan puluh lima koma satu lima derajat'
        e.g. '7920.1 km' -> 'tujuh ribu sembilan ratus dua puluh koma satu kilometer'
        e.g. '98.5%' -> 'sembilan puluh delapan koma lima persen'
        """
        t = text

        # Derajat dengan simbol ° atau kata derajat
        def replace_deg(m):
            num = decimal_to_words(m.group(1))
            return f"{num} derajat"

        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*°", replace_deg, t)
        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*derajat\b", replace_deg, t, flags=re.IGNORECASE)

        # Persen
        def replace_percent(m):
            num = decimal_to_words(m.group(1))
            return f"{num} persen"

        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*%", replace_percent, t)
        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*persen\b", replace_percent, t, flags=re.IGNORECASE)

        # Jarak kilometer
        def replace_km(m):
            num = decimal_to_words(m.group(1))
            return f"{num} kilometer"

        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*km\b", replace_km, t, flags=re.IGNORECASE)
        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*kilometer\b", replace_km, t, flags=re.IGNORECASE)

        # Detik busur / menit busur
        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*[\"″](?:\s*busur)?", lambda m: f"{decimal_to_words(m.group(1))} detik busur", t)
        t = re.sub(r"(\d+(?:[.,]\d+)?)\s*['′](?:\s*busur)?", lambda m: f"{decimal_to_words(m.group(1))} menit busur", t)

        return t

    def normalize_dates_and_years(self, text: str) -> str:
        """
        Mengubah penanggalan Hijriah dan Masehi ke ucapan lisan alami:
        e.g. '1448 H' -> 'seribu empat ratus empat puluh delapan Hijriah'
        e.g. '2026 M' -> 'dua ribu dua puluh enam Masehi'
        e.g. '2021' -> 'dua ribu dua puluh satu'
        """
        t = text

        # Tahun Hijriah: 1448 H / 1443 Hijriah
        def replace_hijri_year(m):
            y = integer_to_words(int(m.group(1)))
            return f"{y} Hijriah"

        t = re.sub(r"\b(1[34]\d{2})\s*(?:H|Hijriah)\b", replace_hijri_year, t, flags=re.IGNORECASE)

        # Tahun Masehi: 2026 M / 2021 Masehi
        def replace_greg_year(m):
            y = integer_to_words(int(m.group(1)))
            return f"{y} Masehi"

        t = re.sub(r"\b(19\d{2}|20\d{2})\s*(?:M|Masehi)\b", replace_greg_year, t, flags=re.IGNORECASE)

        # Tanggal kalender: '28 Mei' -> 'dua puluh delapan Mei', '16 Juli' -> 'enam belas Juli'
        months = "Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember"
        hijri_months = "Muharram|Safar|Rabiul\\s*Awal|Rabiul\\s*Akhir|Jumadil\\s*Awal|Jumadil\\s*Akhir|Rajab|Syaban|Ramadan|Ramadhan|Syawal|Zulkaidah|Dzulqa'dah|Zulhijjah|Dzulhijjah"
        all_months = f"{months}|{hijri_months}"

        def replace_day_month(m):
            day_words = integer_to_words(int(m.group(1)))
            month = m.group(2)
            return f"tanggal {day_words} {month}"

        t = re.sub(rf"\b(?:tanggal\s+)?([123]?\d)\s+({all_months})\b", replace_day_month, t, flags=re.IGNORECASE)

        # Tahun standalone (4 digit): 1900-2099 atau 1300-1499
        def replace_standalone_year(m):
            num = int(m.group(1))
            return integer_to_words(num)

        t = re.sub(r"\b(19\d{2}|20\d{2}|14\d{2})\b", replace_standalone_year, t)

        return t

    def normalize_standalone_numbers(self, text: str) -> str:
        """Mengubah angka murni (desimal maupun bulat) yang tersisa menjadi terbilang."""
        t = text

        # Angka desimal (misal 53.78 atau 0.05)
        def replace_remaining_decimal(m):
            return decimal_to_words(m.group(0))

        t = re.sub(r"\b-?\d+[.,]\d+\b", replace_remaining_decimal, t)

        # Angka bulat tersisa
        def replace_remaining_int(m):
            val = int(m.group(0))
            # Jangan ubah jika bagian dari string bertanda hubung tertentu yang sudah diolah
            return integer_to_words(val)

        t = re.sub(r"\b\d+\b", replace_remaining_int, t)

        return t

    def apply_lexicon(self, text: str) -> str:
        """Menerapkan kamus ejaan lisan dan fonetik istilah falak & hardware."""
        t = text
        for entry in self.lexicon_entries:
            pattern = entry.get("pattern")
            spoken = entry.get("spoken")
            if pattern and spoken:
                t = re.sub(pattern, spoken, t)
        return t

    def optimize_rhythm_and_pacing(self, text: str) -> str:
        """
        Menyempurnakan tanda baca agar TTS bernapas secara alami:
        - Memecah kalimat terlalu panjang (>25 kata) di kata sambung alami
        - Menghilangkan titik dua yang kaku
        - Mengatur spasi koma dan titik
        """
        t = text

        # 1. Hilangkan titik dua ':' yang biasa dipakai di list, ubah jadi koma
        t = re.sub(r"\s*:\s*", ", yaitu ", t)

        # 2. Rapikan spasi tanda baca
        t = re.sub(r"\s*([,.;?!])", r"\1", t)
        t = re.sub(r"([,.;?!])(?=[^\s\d])", r"\1 ", t)

        # 3. Rapikan tanda hubung ganda atau aneh
        t = re.sub(r"\s+-\s+", ", ", t)

        # 4. Potong kalimat majemuk panjang (> 25 kata) di konjungsi alami jika belum ada tanda titik
        sentences = re.split(r"([.!?]+[\s\n]+)", t)
        optimized_sentences = []

        for part in sentences:
            if not part:
                continue
            words = part.split()
            if len(words) > 25:
                # Cari kata sambung pemotong di tengah kalimat
                split_conjunctions = [" karena ", " sehingga ", " namun ", " sementara ", " sedangkan ", " lalu ", " maka "]
                subpart = part
                for conj in split_conjunctions:
                    if conj in subpart:
                        subpart = subpart.replace(conj, f". {conj.strip().capitalize()} ", 1)
                        break
                optimized_sentences.append(subpart)
            else:
                optimized_sentences.append(part)

        result = "".join(optimized_sentences)

        # 5. Normalisasi spasi berlebih
        result = re.sub(r"[ \t]+", " ", result).strip()

        return result

    def normalize(self, text: str) -> str:
        """
        Menjalankan seluruh pipeline normalisasi teks siap ucap.
        Urutan eksekusi dirancang sangat teliti agar aturan spesifik
        dijalankan sebelum aturan angka umum.
        """
        if not text:
            return ""

        # Langkah 1: Bersihkan artefak visual markdown, tabel, dan tanda kurung
        t = self.clean_markdown_and_artifacts(text)

        # Langkah 2: Normalisasi perbandingan sudut dan laju (≥ 3°, 14.5°/jam)
        t = self.normalize_comparisons_and_rates(t)

        # Langkah 3: Normalisasi waktu dan jam digital (06:15 WIB, 17:29)
        t = self.normalize_times(t)

        # Langkah 4: Normalisasi satuan sudut, derajat, dan jarak (295.15°, 7920.1 km, 98%)
        t = self.normalize_astronomy_units(t)

        # Langkah 5: Normalisasi penanggalan dan tahun (1448 H, 2026 M, 28 Mei)
        t = self.normalize_dates_and_years(t)

        # Langkah 6: Normalisasi angka sisa (desimal & bilangan bulat)
        t = self.normalize_standalone_numbers(t)

        # Langkah 7: Terapkan kamus pelafalan fonetik istilah falak & hardware
        t = self.apply_lexicon(t)

        # Langkah 8: Optimasi ritme, pemenggalan kalimat panjang, dan jeda napas
        t = self.optimize_rhythm_and_pacing(t)

        return t


# Singleton instance default
_default_normalizer = None

def get_spoken_normalizer() -> SpokenTextNormalizer:
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = SpokenTextNormalizer()
    return _default_normalizer

def normalize_spoken_text(text: str) -> str:
    """Fungsi pembantu cepat untuk menormalisasi teks ke bahasa lisan siap ucap."""
    return get_spoken_normalizer().normalize(text)
