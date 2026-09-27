import math
from datetime import datetime, timezone
from skyfield.api import load, wgs84
from skyfield import almanac
from hijridate import Gregorian

class FalakCalculator:
    def __init__(self):
        # Load the ephemeris (DE421) and timescale
        self.eph = load('de421.bsp')
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
        
        # y=0 means sunset, y=1 means sunrise
        sunset_times = [ti for ti, yi in zip(t, y) if yi == 0]
        
        if not sunset_times:
            sunset_t = self.ts.utc(dt.year, dt.month, dt.day, 18, 0, 0)
        else:
            sunset_t = sunset_times[0]
            
        # 1. Calculate positions at sunset
        astrometric_sun = observer.at(sunset_t).observe(self.sun)
        app_sun = astrometric_sun.apparent()
        sun_alt, sun_az, _ = app_sun.altaz()
        
        astrometric_moon = observer.at(sunset_t).observe(self.moon)
        app_moon = astrometric_moon.apparent()
        moon_alt, moon_az, _ = app_moon.altaz()
        
        # 2. ARCV (Arc of Vision) -> Moon Altitude at sunset
        arcv = moon_alt.degrees
        
        # 3. ARCL (Arc of Light) -> Elongation
        elongation = app_sun.separation_from(app_moon).degrees
        arcl = elongation
        
        # 4. Illumination Fraction
        illumination = almanac.fraction_illuminated(self.eph, 'moon', sunset_t)
        
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
        
        # Get Hijri Date
        hijri_date = self.get_hijri_date(sunset_t.utc_datetime())
        
        # GMST in hours for Earth Rotation
        gmst = sunset_t.gast
            
        return {
            "time_utc": sunset_t.utc_datetime().isoformat(),
            "gmst_hours": gmst,
            "sun_alt": sun_alt.degrees,
            "sun_az": sun_az.degrees,
            "moon_alt": moon_alt.degrees,
            "moon_az": moon_az.degrees,
            "arcv": arcv,
            "arcl": arcl,
            "illumination": illumination,
            "mabims_status": status,
            "is_visible": imkanur_rukyat,
            "hijri": hijri_date
        }
