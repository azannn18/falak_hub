"""
HILTRON FalakHub — Astronomical & Falak Computation Tools for HILMI AI Assistant.
Provides deterministic calculation tools for Hilal Ephemeris, Prayer Times, Qibla Azimuth,
Hijri-Gregorian Conversion, and ESP32 Tracker IoT Telemetry.
All numbers are calculated mathematically, avoiding LLM hallucinations.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

try:
    from hijridate import Gregorian, Hijri
except ImportError:
    Gregorian = None
    Hijri = None

from astronomy.engine import FalakCalculator


class FalakTools:
    def __init__(self, calculator: FalakCalculator):
        self.calc = calculator

    def hitung_hilal(self, lat: float, lon: float, date_str: str) -> Dict[str, Any]:
        """
        Menghitung hisab hilal mar'i dan status MABIMS pada waktu matahari terbenam (ghurub)
        untuk koordinat pengamat dan tanggal tertentu (format YYYY-MM-DD).
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)

        eph = self.calc.calculate_ephemeris(lat, lon, dt)
        hijri = self.calc.get_hijri_date(dt)

        return {
            "status": "success",
            "tanggal_masehi": dt.strftime("%Y-%m-%d"),
            "tanggal_hijriah": hijri.get("formatted", ""),
            "lintang": round(lat, 4),
            "bujur": round(lon, 4),
            "sunset_utc": eph.get("sunset_utc"),
            "tinggi_hilal_mari_derajat": round(eph.get("arcv", 0.0), 2),
            "elongasi_geosentris_derajat": round(eph.get("arcl", 0.0), 2),
            "elongasi_toposentris_derajat": round(eph.get("arcl_topocentric", 0.0), 2),
            "iluminasi_persen": round(eph.get("illumination", 0.0) * 100, 2),
            "azimuth_bulan_derajat": round(eph.get("sunset_moon_az", 0.0), 2),
            "azimuth_matahari_derajat": round(eph.get("sunset_sun_az", 0.0), 2),
            "status_mabims": eph.get("mabims_status", "Belum Wujud"),
            "memenuhi_imkanur_rukyat": bool(eph.get("is_visible", False)),
            "keterangan": (
                f"Tinggi hilal {round(eph.get('arcv', 0.0), 2)}° dan elongasi {round(eph.get('arcl', 0.0), 2)}°. "
                f"Kriteria MABIMS 2021 (min tinggi 3°, elongasi 6,4°): {eph.get('mabims_status')}."
            )
        }

    def hitung_kiblat(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Menghitung arah kiblat presisi dari koordinat pengamat ke Ka'bah di Mekkah
        menggunakan rumus spherical trigonometry.
        """
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        kaaba_lat = math.radians(21.422487)
        kaaba_lon = math.radians(39.826206)

        d_lon = kaaba_lon - lon_rad
        y = math.sin(d_lon)
        x = math.cos(lat_rad) * math.tan(kaaba_lat) - math.sin(lat_rad) * math.cos(d_lon)
        qibla_deg = (math.degrees(math.atan2(y, x)) + 360) % 360

        # Hitung jarak great-circle ke Ka'bah (haversine)
        d_lat = kaaba_lat - lat_rad
        a = math.sin(d_lat / 2) ** 2 + math.cos(lat_rad) * math.cos(kaaba_lat) * math.sin(d_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_km = 6371.0 * c

        # Arah kardinal relatif di Indonesia (sekitar Barat Laut)
        kardinal = "Barat Laut" if 270 <= qibla_deg <= 315 else "Barat"

        return {
            "status": "success",
            "lintang_pengamat": round(lat, 4),
            "bujur_pengamat": round(lon, 4),
            "azimuth_kiblat_derajat": round(qibla_deg, 2),
            "sudut_dari_barat_ke_utara": round(qibla_deg - 270, 2) if qibla_deg >= 270 else 0,
            "arah_kardinal": kardinal,
            "jarak_ke_kabah_km": round(distance_km, 1),
            "rashdul_kiblat_global": "28 Mei (16:18 WIB) dan 16 Juli (16:27 WIB)"
        }

    def hitung_waktu_salat(
        self,
        lat: float,
        lon: float,
        date_str: str,
        tz_offset: float = 7.0
    ) -> Dict[str, Any]:
        """
        Menghitung jadwal waktu salat astronomis standar Kemenag RI (Subuh -20°, Isya -18°,
        ikhtiyat 2 menit) untuk tanggal dan koordinat tertentu.
        """
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            target_date = datetime.now()

        # Day of year
        day_of_year = target_date.timetuple().tm_yday

        # Approximate Solar Declination (Cooper 1969)
        b_rad = math.radians((360 / 365) * (day_of_year - 81))
        delta_deg = 23.45 * math.sin(b_rad)
        delta_rad = math.radians(delta_deg)

        # Approximate Equation of Time (Meeus/Spencer) in minutes
        b_eot = math.radians((360 / 365) * (day_of_year - 1))
        eot = (
            229.18 * (
                0.000075
                + 0.001868 * math.cos(b_eot)
                - 0.032077 * math.sin(b_eot)
                - 0.014615 * math.cos(2 * b_eot)
                - 0.040849 * math.sin(2 * b_eot)
            )
        )

        # Meridian transit (Dzuhur) in local solar time
        # dzuhur_utc = 12 - (lon / 15) - (eot / 60)
        # local standard time = dzuhur_utc + tz_offset
        dzuhur_hours = 12.0 + tz_offset - (lon / 15.0) - (eot / 60.0)

        lat_rad = math.radians(lat)

        def hour_angle(alt_deg: float) -> Optional[float]:
            alt_rad = math.radians(alt_deg)
            cos_h = (math.sin(alt_rad) - math.sin(lat_rad) * math.sin(delta_rad)) / (
                math.cos(lat_rad) * math.cos(delta_rad)
            )
            if cos_h < -1.0 or cos_h > 1.0:
                return None
            return math.degrees(math.acos(cos_h)) / 15.0

        # Standard altitude parameters:
        # Subuh: -20° (Kemenag RI)
        # Terbit (Syuruq): -0.833°
        # Dhuha: +4.5°
        # Maghrib: -0.833°
        # Isya: -18° (Kemenag RI)
        h_subuh = hour_angle(-20.0)
        h_terbit = hour_angle(-0.833)
        h_dhuha = hour_angle(4.5)
        h_maghrib = hour_angle(-0.833)
        h_isya = hour_angle(-18.0)

        # Ashar altitude: cot(h) = 1 + tan(|lat - delta|) -> h = atan(1 / (1 + tan(|lat - delta|)))
        phi_minus_delta = abs(lat_rad - delta_rad)
        h_ashar_deg = math.degrees(math.atan(1.0 / (1.0 + math.tan(phi_minus_delta))))
        h_ashar = hour_angle(h_ashar_deg)

        def format_time(hours_val: Optional[float], ikhtiyat_mins: int = 2) -> str:
            if hours_val is None:
                return "--:--"
            total_mins = int(round(hours_val * 60)) + ikhtiyat_mins
            hh = (total_mins // 60) % 24
            mm = total_mins % 60
            return f"{hh:02d}:{mm:02d}"

        subuh_str = format_time(dzuhur_hours - h_subuh if h_subuh else None, 2)
        # Imsak is 10 mins before Subuh
        if h_subuh:
            imsak_mins = int(round((dzuhur_hours - h_subuh) * 60)) - 10 + 2
            imsak_str = f"{(imsak_mins // 60) % 24:02d}:{imsak_mins % 60:02d}"
        else:
            imsak_str = "--:--"

        terbit_str = format_time(dzuhur_hours - h_terbit if h_terbit else None, -2)
        dhuha_str = format_time(dzuhur_hours - h_dhuha if h_dhuha else None, 2)
        dzuhur_str = format_time(dzuhur_hours, 2)
        ashar_str = format_time(dzuhur_hours + h_ashar if h_ashar else None, 2)
        maghrib_str = format_time(dzuhur_hours + h_maghrib if h_maghrib else None, 2)
        isya_str = format_time(dzuhur_hours + h_isya if h_isya else None, 2)

        return {
            "status": "success",
            "tanggal": target_date.strftime("%Y-%m-%d"),
            "koordinat": {"lat": round(lat, 4), "lon": round(lon, 4)},
            "zona_waktu": f"UTC+{int(tz_offset)}",
            "metode": "Standar Kementerian Agama RI (Subuh -20°, Isya -18°, Ikhtiyat +2 menit)",
            "jadwal": {
                "imsak": imsak_str,
                "subuh": subuh_str,
                "terbit": terbit_str,
                "dhuha": dhuha_str,
                "dzuhur": dzuhur_str,
                "ashar": ashar_str,
                "maghrib": maghrib_str,
                "isya": isya_str
            }
        }

    def konversi_hijriah(self, date_str: str, to_hijri: bool = True) -> Dict[str, Any]:
        """
        Konversi kalender antara Masehi dan Hijriah menggunakan algoritma Umm al-Qura.
        """
        if Gregorian is None:
            return {"status": "error", "message": "Pustaka hijridate tidak tersedia."}

        try:
            if to_hijri:
                parts = [int(p) for p in date_str.split("-")]
                g = Gregorian(parts[0], parts[1], parts[2])
                h = g.to_hijri()
                return {
                    "status": "success",
                    "arah_konversi": "Masehi ke Hijriah",
                    "masehi": date_str,
                    "hijriah": {
                        "hari": h.day,
                        "bulan_angka": h.month,
                        "nama_bulan": h.month_name(),
                        "tahun": h.year,
                        "formatted": f"{h.day} {h.month_name()} {h.year} H"
                    }
                }
            else:
                # Format: YYYY-MM-DD in Hijri
                parts = [int(p) for p in date_str.split("-")]
                h = Hijri(parts[0], parts[1], parts[2])
                g = h.to_gregorian()
                return {
                    "status": "success",
                    "arah_konversi": "Hijriah ke Masehi",
                    "hijriah": date_str,
                    "masehi": {
                        "hari": g.day,
                        "bulan_angka": g.month,
                        "nama_bulan": g.month_name(),
                        "tahun": g.year,
                        "formatted": f"{g.day} {g.month_name()} {g.year} M"
                    }
                }
        except Exception as e:
            return {"status": "error", "message": f"Gagal konversi tanggal: {str(e)}"}

    def status_tracker(self, telemetry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Membaca status real-time hardware tracker teleskop otomatis ESP32 + BNO055 + GPS.
        """
        if not telemetry:
            return {
                "status": "success",
                "connected": False,
                "mode": "Standby / Offline Simulator",
                "azimuth_motor_deg": 0.0,
                "altitude_motor_deg": 0.0,
                "live_tracking": False,
                "kompensasi_rotasi_bumi": "14.51°/jam (Sideris)",
                "imu_bno055": "Siaga",
                "gps_fix": "No Fix (Simulasi)",
                "keterangan": "Tracker teleskop ESP32 dalam status siaga offline. Siap diaktifkan untuk Celestial Live Lock."
            }

        return {
            "status": "success",
            "connected": telemetry.get("connected", False),
            "mode": "Celestial Live Lock" if telemetry.get("live_tracking") else "Manual/Idle",
            "azimuth_motor_deg": telemetry.get("azimuth", 0.0),
            "altitude_motor_deg": telemetry.get("altitude", 0.0),
            "live_tracking": telemetry.get("live_tracking", False),
            "kompensasi_rotasi_bumi": "14.51°/jam",
            "imu_bno055": "Terkalibrasi Penuh (Level 3)" if telemetry.get("calibrated") else "Kalibrasi Standar",
            "gps_fix": "3D Fix" if telemetry.get("gps_fix") else "Searching Satellites",
            "keterangan": "Tracker terhubung aktif dengan firmware HILTRON ESP32 v1.2."
        }

