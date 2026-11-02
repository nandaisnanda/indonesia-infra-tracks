"""Fetch Indonesian toll roads (highway=motorway) from OpenStreetMap via Overpass.

Output: data/osm_motorway.geojson  (raw material, no opening dates yet)

Usage:  pip install requests
        python scripts/fetch_osm.py
"""
import json
import sys
from pathlib import Path

import requests

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:300];
area["ISO3166-1"="ID"][admin_level=2]->.id;
way["highway"="motorway"](area.id);
out tags geom;
"""
OUT = Path(__file__).resolve().parent.parent / "data" / "osm_motorway.geojson"
KEEP_TAGS = ("name", "ref", "operator", "oneway", "opening_date", "start_date")


def main() -> int:
    print("Querying Overpass (can take 1-3 minutes)...")
    headers = {"User-Agent": "infra-lines/1.0 (30DayMapChallenge; contact: anandashabrinaputrig@mail.ugm.ac.id)",
               "Accept": "application/json"}
    r = requests.post(OVERPASS, data={"data": QUERY}, headers=headers, timeout=360)
    r.raise_for_status()
    ways = [e for e in r.json().get("elements", []) if e.get("type") == "way" and e.get("geometry")]
    if not ways:
        print("No data. Try again later or switch the Overpass mirror.", file=sys.stderr)
        return 1

    features = []
    for w in ways:
        tags = w.get("tags", {})
        props = {k: tags.get(k) for k in KEEP_TAGS}
        props["osm_id"] = w["id"]
        # Columns to fill in QGIS:
        props.update({"nama": tags.get("name"), "seksi": None, "tgl_operasi": None,
                      "panjang_km": None, "sumber": None})
        coords = [[round(p["lon"], 6), round(p["lat"], 6)] for p in w["geometry"]]
        features.append({"type": "Feature", "properties": props,
                         "geometry": {"type": "LineString", "coordinates": coords}})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    with_date = sum(1 for f in features if f["properties"]["opening_date"] or f["properties"]["start_date"])
    print(f"Saved {len(features)} ways -> {OUT}")
    print(f"{with_date} ways already have opening_date/start_date in OSM (fill in the rest manually).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
