import time
import sqlite3
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

DB = "output.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

geolocator = Nominatim(user_agent="datasette_luoghi_mappa")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, swallow_exceptions=False)

rows = cur.execute("""
    SELECT id, indirizzo
    FROM luogo
    WHERE (lat IS NULL OR lon IS NULL)
      AND indirizzo IS NOT NULL AND indirizzo <> ''
""").fetchall()

for r in rows:
    full = f"{r['indirizzo']}, Copenhagen"
    try:
        loc = geocode(full, addressdetails=False, timeout=10)
        if loc:
            cur.execute(
                "UPDATE luogo SET lat=?, lon=? WHERE id=?",
                (loc.latitude, loc.longitude, r["id"])
            )
            conn.commit()
            print("OK:", r["id"], full, loc.latitude, loc.longitude)
        else:
            print("NO MATCH:", r["id"], full)
    except Exception as e:
        print("ERR:", r["id"], full, e)
        time.sleep(2)  # un piccolo backoff
conn.close()
