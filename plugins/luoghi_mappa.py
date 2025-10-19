from datasette import hookimpl
from datasette.utils.asgi import Response
import json

@hookimpl
def register_routes():
    return [(r"^/luoghi_mappa$", luoghi_mappa)]

async def luoghi_mappa(scope, receive, datasette):
    db = datasette.get_database("output")
    rows = await db.execute("""
        SELECT id, indirizzo, lat, lon
        FROM luogo
        WHERE indirizzo IS NOT NULL AND indirizzo <> ''
          AND lat IS NOT NULL AND lon IS NOT NULL
    """)

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "id": r["id"],
                "indirizzo": r["indirizzo"],
                "url": f"/output/luogo/{r['id']}"
            }
        })

    html = f"""
    <!doctype html><html><head>
      <meta charset="utf-8" />
      <title>Mappa luoghi</title>
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>#map{{height:100vh;width:100%}}</style>
    </head><body>
      <div id="map"></div>
      <script>
        const map = L.map('map').setView([55.6761,12.5683], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
          maxZoom: 19, attribution: '&copy; OpenStreetMap'
        }}).addTo(map);

        const data = {json.dumps({"type": "FeatureCollection", "features": features})};

        L.geoJSON(data, {{
          onEachFeature: (f, layer) => {{
            const p = f.properties;
            layer.bindPopup(`<strong>${{p.indirizzo}}</strong><br>
              <a href="${{p.url}}" target="_blank">➡️ Apri in Datasette</a>`);
          }}
        }}).addTo(map);
      </script>
    </body></html>"""
    return Response.html(html)
