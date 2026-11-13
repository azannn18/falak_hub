import os
import math
from datetime import datetime, timezone
from skyfield.api import Loader, wgs84
from skyfield.jpllib import SpiceKernel
from skyfield import almanac
from hijridate import Gregorian

try:
    from paths import get_app_data_dir, get_backend_dir
except ImportError:
    from backend.paths import get_app_data_dir, get_backend_dir

class FalakCalculator:
    def __init__(self):
        # Use writable OS app-data cache dir (compatible with Windows, Linux, and Vercel)
        skyfield_cache_dir = get_app_data_dir() / "skyfield"
        skyfield_cache_dir.mkdir(parents=True, exist_ok=True)
        load = Loader(str(skyfield_cache_dir))

        # Load the ephemeris (DE421) from backend dir (supports dev & PyInstaller bundle)
        eph_path = str(get_backend_dir() / 'de421.bsp')
        self.eph = SpiceKernel(eph_path)

        # Use Skyfield's built-in timescale so startup works 100% offline with zero downloads
        self.ts = load.timescale(builtin=True)
        self.earth = self.eph['earth']
        self.sun = self.eph['sun']
        self.moon = self.eph['moon']

    def get_hijri_date(self, dt: datetime):
        # Using Umm al-Qura calendar via hijridate
        hijri = Gregorian(dt.year, dt.month, dt.day).to_hijri()
        return {
            "day": hijri.day,
            "month_name": hijri.month_name(),
            "year": hijri.year,
            "formatted": f"{hijri.day} {hijri.month_name()} {hijri.year} H"
        }

    def calculate_ephemeris(self, lat: float, lon: float, dt: datetime):
        """
        Calculate precise ephemeris data for the observer at sunset on the given date.
        """
        observer = self.earth + wgs84.latlon(lat, lon)
        
        # Start and end of the day for sunset calculation
        t0 = self.ts.utc(dt.year, dt.month, dt.day, 0, 0, 0)
        t1 = self.ts.utc(dt.year, dt.month, dt.day, 23, 59, 59)
        
        # Find sunset
        f = almanac.sunrise_sunset(self.eph, wgs84.latlon(lat, lon))
        t, y = almanac.find_discrete(t0, t1, f)
        
        sunset_times = [ti for ti, yi in zip(t, y) if yi == 0]
        if not sunset_times:
            sunset_t = self.ts.utc(dt.year, dt.month, dt.day, 18, 0, 0)
        else:
            sunset_t = sunset_times[-1]
            
        # 1. Calculate MABIMS Criteria exactly at sunset
        astrometric_moon_sunset = observer.at(sunset_t).observe(self.moon)
        app_moon_sunset = astrometric_moon_sunset.apparent()
        # Menggunakan refraksi atmosfer standar (Tinggi Mar'i standar Kemenag RI / MABIMS)
        moon_alt_sunset_mari, moon_az_sunset, _ = app_moon_sunset.altaz(temperature_C=25.0, pressure_mbar=1010.0)
        
        astrometric_sun_sunset = observer.at(sunset_t).observe(self.sun)
        app_sun_sunset = astrometric_sun_sunset.apparent()
        sun_alt_sunset, sun_az_sunset, _ = app_sun_sunset.altaz(temperature_C=25.0, pressure_mbar=1010.0)
        
        # 2. ARCV (Arc of Vision) -> Moon Altitude at sunset (Tinggi Hilal Mar'i)
        arcv = moon_alt_sunset_mari.degrees
        
        # 3. ARCL (Arc of Light) -> Elongasi Geosentris (Sesuai Ketetapan Resmi Kemenag RI & MABIMS 2021)
        geo_sun = self.earth.at(sunset_t).observe(self.sun).apparent()
        geo_moon = self.earth.at(sunset_t).observe(self.moon).apparent()
        arcl_geocentric = geo_sun.separation_from(geo_moon).degrees
        arcl_topocentric = app_sun_sunset.separation_from(app_moon_sunset).degrees
        arcl = arcl_geocentric
        
        # 4. Calculate Global Positions for the requested time `dt` (Real-Time / Target)
        current_t = self.ts.from_datetime(dt)
        
        astrometric_sun = observer.at(current_t).observe(self.sun)
        app_sun = astrometric_sun.apparent()
        sun_alt, sun_az, _ = app_sun.altaz(temperature_C=25.0, pressure_mbar=1010.0)
        sun_ra, sun_dec, _ = app_sun.radec()
        
        astrometric_moon = observer.at(current_t).observe(self.moon)
        app_moon = astrometric_moon.apparent()
        moon_alt, moon_az, _ = app_moon.altaz(temperature_C=25.0, pressure_mbar=1010.0)
        moon_ra, moon_dec, _ = app_moon.radec()
        
        illumination = almanac.fraction_illuminated(self.eph, 'moon', current_t)
        
        # 5. MABIMS Criteria: Altitude >= 3 deg, Elongation >= 6.4 deg (Geosentris)
        wujud = arcv > 0
        imkanur_rukyat = arcv >= 3.0 and arcl >= 6.4
        status = "Belum Wujud"
        if imkanur_rukyat:
            status = "Imkanur Rukyat (MABIMS)"
        elif wujud:
            status = "Wujudul Hilal"
            
        # Get Hijri Date for the requested time
        hijri_date = self.get_hijri_date(current_t.utc_datetime())
        
        # GMST in hours for Earth Rotation at the requested time
        gmst = current_t.gast
            
        return {
            "time_utc": current_t.utc_datetime().isoformat(),
            "sunset_utc": sunset_t.utc_datetime().isoformat(),
            "gmst_hours": gmst,
            "sun_alt": sun_alt.degrees,
            "sun_az": sun_az.degrees,
            "sun_ra": sun_ra.hours,
            "sun_dec": sun_dec.degrees,
            "moon_alt": moon_alt.degrees,
            "moon_az": moon_az.degrees,
            "moon_ra": moon_ra.hours,
            "moon_dec": moon_dec.degrees,
            "arcv": arcv,
            "arcl": arcl,
            "arcl_geocentric": arcl_geocentric,
            "arcl_topocentric": arcl_topocentric,
            "sunset_sun_az": sun_az_sunset.degrees,
            "sunset_sun_alt": sun_alt_sunset.degrees,
            "sunset_moon_az": moon_az_sunset.degrees,
            "sunset_moon_alt": moon_alt_sunset_mari.degrees,
            "illumination": illumination,
            "mabims_status": status,
            "is_visible": imkanur_rukyat,
            "hijri": hijri_date
        }
