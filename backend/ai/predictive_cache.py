import json
import geobuf
import numpy as np
from datetime import datetime
from astronomy.engine import FalakCalculator

class PredictiveCache:
    def __init__(self, calculator: FalakCalculator):
        self.calc = calculator
        self.cache = {}
        self.logs = []
        
    def train(self, query_logs):
        """Mock training to reduce Vercel serverless size (removed scikit-learn)."""
        self.logs.extend(query_logs)

    def generate_global_grid(self, dt: datetime, resolution: int = 5):
        """
        Generate a grid of ephemeris data.
        To avoid massive computation, we use a coarse resolution globally.
        Returns a GeoJSON FeatureCollection encoded as Geobuf.
        """
        cache_key = f"{dt.year}-{dt.month}-{dt.day}_res{resolution}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        features = []
        # Generate grid
        for lat in range(-90, 91, resolution):
            for lon in range(-180, 181, resolution):
                # We skip polar regions for simplicity in this demo if they fail sunset calculation
                if abs(lat) > 65:
                    continue
                
                try:
                    data = self.calc.calculate_ephemeris(lat, lon, dt)
                    color = "#EF4444" # Belum Wujud
                    if data["mabims_status"] == "Imkanur Rukyat (MABIMS)":
                        color = "#10B981"
                    elif data["mabims_status"] == "Wujudul Hilal":
                        color = "#3B82F6"
                        
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "properties": {
                            "arcv": data["arcv"],
                            "arcl": data["arcl"],
                            "status": data["mabims_status"],
                            "color": color
                        }
                    }
                    features.append(feature)
                except Exception:
                    pass

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        # Serialize to Geobuf for highly optimized over-the-wire transfer
        pbf = geobuf.encode(geojson)
        self.cache[cache_key] = pbf
        return pbf
