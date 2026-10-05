import urllib.request
import json
try:
    req = urllib.request.Request("https://falak-hub-hbqg.vercel.app/api/ephemeris?lat=-6.2&lon=106.8&date=2026-09-30")
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print("Status:", e.code)
    print("Error body:", e.read().decode())
except Exception as e:
    print("Error:", str(e))
