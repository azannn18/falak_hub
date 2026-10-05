import os
import math
from datetime import datetime, timezone
from skyfield.api import Loader, wgs84
from skyfield.jpllib import SpiceKernel
from skyfield import almanac
from hijridate import Gregorian

class FalakCalculator:
    def __init__(self):
        # Create a loader that writes to /tmp to avoid Vercel read-only filesystem error
        load = Loader('/tmp')
        
        # Load the ephemeris (DE421) directly from the backend folder to avoid massive download timeout
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        eph_path = os.path.join(BASE_DIR, 'de421.bsp')
        self.eph = SpiceKernel(eph_path)
        
        # Load timescale (downloads tiny leap second files to /tmp)
        self.ts = load.timescale()
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
        moon_alt_sunset, _, _ = app_moon_sunset.altaz()
        
        astrometric_sun_sunset = observer.at(sunset_t).observe(self.sun)
        app_sun_sunset = astrometric_sun_sunset.apparent()
        
        # 2. ARCV (Arc of Vision) -> Moon Altitude at sunset
        arcv = moon_alt_sunset.degrees
        
        # 3. ARCL (Arc of Light) -> Elongation at sunset
        elongation = app_sun_sunset.separation_from(app_moon_sunset).degrees
        arcl = elongation
        
        # 4. Calculate Global Positions for the requested time `dt` (Real-Time)
        current_t = self.ts.from_datetime(dt)
        
        astrometric_sun = observer.at(current_t).observe(self.sun)
        app_sun = astrometric_sun.apparent()
        sun_alt, sun_az, _ = app_sun.altaz()
        sun_ra, sun_dec, _ = app_sun.radec()
        
        astrometric_moon = observer.at(current_t).observe(self.moon)
        app_moon = astrometric_moon.apparent()
        moon_alt, moon_az, _ = app_moon.altaz()
        moon_ra, moon_dec, _ = app_moon.radec()
        
        illumination = almanac.fraction_illuminated(self.eph, 'moon', current_t)
        
        # 5. MABIMS Criteria: Altitude > 3 deg, Elongation > 6.4 deg
        wujud = arcv > 0
        imkanur_rukyat = arcv >= 3.0 and arcl >= 6.4
        status = "Belum Wujud"
        if imkanur_rukyat:
            status = "Imkanur Rukyat (MABIMS)"
        elif wujud:
            status = "Wujudul Hilal"
            
        # Calculate Moon Age (time since last new moon)
        # Note: We'll approximate moon age based on illumination for simplicity here, 
        # or we could find previous new moon. Let's do a basic approx for UI.
        # A full cycle is ~29.53 days. 
        # For an exact calculation, one should find the last phase=0.
        
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
            "illumination": illumination,
            "mabims_status": status,
            "is_visible": imkanur_rukyat,
            "hijri": hijri_date
        }
