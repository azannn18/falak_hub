"""
HILTRON FalakHub — Unit Test Suite: Spoken Text Normalizer (speech_text.py)
Verifies 43 comprehensive test cases across:
1. Markdown and formatting cleanup
2. Number-to-words (integers, negative numbers, large numbers)
3. Decimals and geographical coordinates
4. Astronomical degrees, angles, percentages, and distances
5. Comparison operators and rates (≥ 3°, 14.51°/jam)
6. Digital prayer times and time zones (06:15 WIB, 17:29)
7. Dates, years, Gregorian, and Hijri calendar (2021, 1448 H, 28 Mei)
8. Pronunciation lexicon (ESP32, BNO055, MABIMS, HILTRON, hisab, rukyat)
9. Sentence rhythm, pacing, and colon removal
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from ai.speech_text import SpokenTextNormalizer, integer_to_words, decimal_to_words


class TestSpokenTextNormalizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpokenTextNormalizer()

    # ── 1. MARKDOWN, HTML & VISUAL ARTIFACTS CLEANUP (5 KASUS) ──
    def test_01_strip_markdown_bold_and_italic(self):
        text = "Posisi **hilal** sangat *jelas* dan ***terang***."
        res = self.norm.clean_markdown_and_artifacts(text)
        self.assertNotIn("*", res)
        self.assertIn("hilal", res)

    def test_02_strip_markdown_code_and_backticks(self):
        text = "Nilai azimuth adalah `295.15` derajat."
        res = self.norm.clean_markdown_and_artifacts(text)
        self.assertNotIn("`", res)
        self.assertIn("295.15", res)

    def test_03_strip_grounding_citations_and_urls(self):
        text = "Berdasarkan rujukan [1] dan https://kemenag.go.id terkait hisab."
        res = self.norm.clean_markdown_and_artifacts(text)
        self.assertNotIn("[1]", res)
        self.assertNotIn("https://", res)

    def test_04_strip_markdown_headers_and_bullets(self):
        text = "### Jadwal Salat\n* Subuh\n* Dzuhur"
        res = self.norm.clean_markdown_and_artifacts(text)
        self.assertNotIn("#", res)
        self.assertNotIn("*", res)

    def test_05_convert_parentheses_to_spoken_pause(self):
        text = "Kriteria Imkanur Rukyat (MABIMS) telah disepakati."
        res = self.norm.clean_markdown_and_artifacts(text)
        self.assertNotIn("(", res)
        self.assertNotIn(")", res)
        self.assertIn(", MABIMS,", res)

    # ── 2. INTEGER NUMBERS TO WORDS (5 KASUS) ──
    def test_06_integer_zero_and_single_digit(self):
        self.assertEqual(integer_to_words(0), "nol")
        self.assertEqual(integer_to_words(7), "tujuh")

    def test_07_integer_teens_and_tens(self):
        self.assertEqual(integer_to_words(11), "sebelas")
        self.assertEqual(integer_to_words(15), "lima belas")
        self.assertEqual(integer_to_words(40), "empat puluh")
        self.assertEqual(integer_to_words(73), "tujuh puluh tiga")

    def test_08_integer_hundreds(self):
        self.assertEqual(integer_to_words(100), "seratus")
        self.assertEqual(integer_to_words(295), "dua ratus sembilan puluh lima")

    def test_09_integer_thousands_and_millions(self):
        self.assertEqual(integer_to_words(1000), "seribu")
        self.assertEqual(integer_to_words(7920), "tujuh ribu sembilan ratus dua puluh")

    def test_10_negative_numbers(self):
        self.assertEqual(integer_to_words(-6), "minus enam")
        self.assertEqual(integer_to_words(-20), "minus dua puluh")

    # ── 3. DECIMALS & COORDINATES (5 KASUS) ──
    def test_11_decimal_two_digits(self):
        self.assertEqual(decimal_to_words("295.15"), "dua ratus sembilan puluh lima koma satu lima")

    def test_12_decimal_comma_format(self):
        self.assertEqual(decimal_to_words("6,4"), "enam koma empat")

    def test_13_decimal_with_zero(self):
        self.assertEqual(decimal_to_words("0.05"), "nol koma nol lima")

    def test_14_negative_decimal_latitude(self):
        self.assertEqual(decimal_to_words("-6.20"), "minus enam koma dua nol")

    def test_15_long_decimal_coordinate(self):
        self.assertEqual(decimal_to_words("106.84"), "seratus enam koma delapan empat")

    # ── 4. ASTRONOMICAL DEGREES, ANGLES & DISTANCES (5 KASUS) ──
    def test_16_degree_symbol_integer(self):
        res = self.norm.normalize("Tinggi hilal adalah 3°.")
        self.assertIn("tiga derajat", res)
        self.assertNotIn("3°", res)

    def test_17_degree_decimal_point(self):
        res = self.norm.normalize("Azimuth kiblat sebesar 295.15 derajat.")
        self.assertIn("dua ratus sembilan puluh lima koma satu lima derajat", res)

    def test_18_percentage_illumination(self):
        res = self.norm.normalize("Fraksi iluminasi bulan sebesar 1.5%.")
        self.assertIn("satu koma lima persen", res)
        self.assertNotIn("%", res)

    def test_19_distance_kilometers(self):
        res = self.norm.normalize("Jarak lurus ke Ka'bah sekitar 7920.1 km.")
        self.assertIn("tujuh ribu sembilan ratus dua puluh koma satu kilometer", res)
        self.assertNotIn("km", res)

    def test_20_arcseconds_and_arcminutes(self):
        res = self.norm.normalize("Diameter sudut bulan adalah 30' busur.")
        self.assertIn("tiga puluh menit busur", res)

    # ── 5. COMPARISON OPERATORS & RATES (5 KASUS) ──
    def test_21_greater_than_or_equal_degree(self):
        res = self.norm.normalize("Syarat tinggi hilal ≥ 3° di ufuk barat.")
        self.assertIn("minimal tiga derajat", res)
        self.assertNotIn("≥", res)

    def test_22_less_than_or_equal_degree(self):
        res = self.norm.normalize("Toleransi hisab ≤ 0.5°.")
        self.assertIn("maksimal nol koma lima derajat", res)
        self.assertNotIn("≤", res)

    def test_23_earth_rotation_speed_rate(self):
        res = self.norm.normalize("Kompensasi rotasi bumi 14.51°/jam secara stabil.")
        self.assertIn("empat belas koma lima satu derajat per jam", res)
        self.assertNotIn("/jam", res)

    def test_24_greater_than_elongation(self):
        res = self.norm.normalize("Sudut elongasi > 6.4 derajat.")
        self.assertIn("lebih dari enam koma empat derajat", res)

    def test_25_slash_as_or_in_mode(self):
        res = self.norm.normalize("Beroperasi dalam mode Standby / Offline Simulator.")
        self.assertIn("Standby atau Offline", res)
        self.assertNotIn("/", res)

    # ── 6. DIGITAL PRAYER TIMES & TIME ZONES (5 KASUS) ──
    def test_26_morning_prayer_time_with_tz(self):
        res = self.norm.normalize("Waktu Subuh masuk pukul 04:15 WIB.")
        self.assertIn("pukul empat lewat lima belas menit W-I-B", res)

    def test_27_dusk_prayer_time(self):
        res = self.norm.normalize("Maghrib pukul 17:29.")
        self.assertIn("pukul tujuh belas lewat dua puluh sembilan menit", res)

    def test_28_exact_hour_time(self):
        res = self.norm.normalize("Istiwa terjadi pukul 12:00 WIB.")
        self.assertIn("pukul dua belas tepat W-I-B", res)

    def test_29_consecutive_prayer_times_list(self):
        res = self.norm.normalize("Dzuhur pukul 11:16, Ashar pukul 14:38.")
        self.assertIn("pukul sebelas lewat enam belas menit", res)
        self.assertIn("pukul empat belas lewat tiga puluh delapan menit", res)

    def test_30_time_without_explicit_pukul_prefix(self):
        res = self.norm.normalize("Matahari terbenam pada 17:45 WITA.")
        self.assertIn("pukul tujuh belas lewat empat puluh lima menit Wita", res)

    # ── 7. DATES, YEARS & CALENDAR CONVERSIONS (5 KASUS) ──
    def test_31_gregorian_four_digit_year(self):
        res = self.norm.normalize("Kesepakatan MABIMS tahun 2021.")
        self.assertIn("dua ribu dua puluh satu", res)

    def test_32_hijri_year_with_h_suffix(self):
        res = self.norm.normalize("Tahun baru 1448 H telah tiba.")
        self.assertIn("seribu empat ratus empat puluh delapan Hijriah", res)
        self.assertNotIn("1448 H", res)

    def test_33_calendar_day_and_month(self):
        res = self.norm.normalize("Fenomena Rashdul Kiblat terjadi pada 28 Mei.")
        self.assertIn("tanggal dua puluh delapan Mei", res)

    def test_34_calendar_day_and_july_month(self):
        res = self.norm.normalize("Pengamatan kedua pada 16 Juli.")
        self.assertIn("tanggal enam belas Juli", res)

    def test_35_hijri_date_day_and_month(self):
        res = self.norm.normalize("Awal 1 Ramadan ditentukan lewat sidang.")
        self.assertIn("tanggal satu Ramadan", res)

    # ── 8. PRONUNCIATION LEXICON REPLACEMENTS (5 KASUS) ──
    def test_36_lexicon_esp32_microcontroller(self):
        res = self.norm.normalize("Teleskop digerakkan mikrokontroler ESP32.")
        self.assertIn("E-S-P tiga puluh dua", res)

    def test_37_lexicon_bno055_sensor(self):
        res = self.norm.normalize("Orientasi diukur sensor BNO055.")
        self.assertIn("B-N-O nol lima lima", res)

    def test_38_lexicon_mabims_acronym(self):
        res = self.norm.normalize("Sesuai kriteria MABIMS terbaru.")
        self.assertIn("Mabims", res)

    def test_39_lexicon_hiltron_brand(self):
        res = self.norm.normalize("Observatorium HILTRON FalakHub.")
        self.assertIn("Hiltron", res)

    def test_40_lexicon_falak_terms_azimuth_rukyat(self):
        res = self.norm.normalize("Hitung azimuth dan lakukan rukyatul hilal.")
        self.assertIn("azimut", res)
        self.assertIn("rukyatul hilal", res)

    # ── 9. SENTENCE PACING & RHYTHM OPTIMIZATION (3 KASUS) ──
    def test_41_replace_colons_with_pause(self):
        text = "Berikut jadwal salat akurat: Subuh pukul 04:15 WIB."
        res = self.norm.normalize(text)
        self.assertNotIn("akurat:", res)
        self.assertIn("akurat, yaitu", res)

    def test_42_split_overly_long_compound_sentence(self):
        long_sentence = (
            "Kriteria baru MABIMS 2021 menyepakati bahwa hilal dianggap mungkin terlihat jika saat maghrib tinggi hilal mar'i minimal 3 derajat "
            "dan sudut elongasi geosentris minimal 6,4 derajat karena nilai tersebut memperhitungkan refraksi atmosfer dan kontras cahaya di ufuk."
        )
        res = self.norm.normalize(long_sentence)
        # Should split at conjunction 'karena' into two sentences
        self.assertIn(". Karena", res)

    def test_43_full_realistic_qibla_query_normalization(self):
        text = "Dari koordinat Jakarta, arah kiblat presisi mengarah pada azimuth 295.15 derajat dari Utara sejati. Jarak lurus ke Ka'bah sekitar 7920.1 km."
        res = self.norm.normalize(text)
        self.assertIn("dua ratus sembilan puluh lima koma satu lima derajat", res)
        self.assertIn("tujuh ribu sembilan ratus dua puluh koma satu kilometer", res)
        self.assertIn("Ka'bah", res)
        self.assertNotIn("295.15", res)
        self.assertNotIn("7920.1", res)
        self.assertNotIn("km", res)


if __name__ == "__main__":
    unittest.main()

