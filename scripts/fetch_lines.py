"""Fetch Indonesian line infrastructure from Overpass, one layer at a time.

Layers (output data/raw_<layer>.geojson):
  rail    railway=rail|light_rail|subway|narrow_gauge   (existing and new lines)
  trunk   highway=trunk                                  (national arterial roads)
  primary highway=primary                                (national / provincial arterials)

Large layers are split into regions so one Overpass query stays small.

Usage:  python scripts/fetch_lines.py rail
        python scripts/fetch_lines.py trunk primary
"""
import json
import sys
import time
from pathlib import Path

import requests

OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "infra-lines/1.0 (30DayMapChallenge; contact: anandashabrinaputrig@mail.ugm.ac.id)",
           "Accept": "application/json"}
DATA = Path(__file__).resolve().parent.parent / "data"

# south, west, north, east
REGIONS = {
    "sumatera": (-6.2, 94.5, 6.2, 109.0),
    "jawa": (-9.0, 105.0, -5.5, 115.0),
    "bali-nusa": (-11.2, 114.6, -7.9, 125.5),
    "kalimantan": (-4.5, 108.0, 4.5, 119.5),
    "sulawesi": (-6.5, 118.5, 3.0, 126.5),
    "maluku-papua": (-9.5, 125.5, 3.0, 141.5),
}
LAYERS = {
    "rail": '["railway"~"^(rail|light_rail|subway|narrow_gauge)$"]',
    "trunk": '["highway"="trunk"]',
    "primary": '["highway"="primary"]',
}
KEEP = ("name", "ref", "operator", "railway", "highway", "service", "usage", "start_date",
        "opening_date", "construction", "bridge", "tunnel", "electrified", "gauge", "surface")


def query(body: str, tries: int = 4) -> dict:
    for i in range(tries):
        try:
            r = requests.post(OVERPASS, data={"data": body}, headers=HEADERS, timeout=420)
            if r.status_code == 200:
                return r.json()
            print(f"  HTTP {r.status_code}, retry in {20 * (i + 1)}s")
        except requests.RequestException as e:
            print(f"  {type(e).__name__}, retry in {20 * (i + 1)}s")
        time.sleep(20 * (i + 1))
    raise SystemExit("Overpass keeps failing; try again later or change the mirror")


def fetch_layer(layer: str) -> None:
    seen, feats = set(), []
    for region, (s, w, n, e) in REGIONS.items():
        print(f"{layer} / {region} ...")
        body = (f'[out:json][timeout:400];area["ISO3166-1"="ID"][admin_level=2]->.id;'
                f'way{LAYERS[layer]}(area.id)({s},{w},{n},{e});out tags geom;')
        for el in query(body).get("elements", []):
            if el["id"] in seen or not el.get("geometry"):
                continue
            seen.add(el["id"])
            tags = el.get("tags", {})
            props = {k: tags[k] for k in KEEP if k in tags}
            props["osm_id"] = el["id"]
            coords = [[round(p["lon"], 5), round(p["lat"], 5)] for p in el["geometry"]]
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": "LineString", "coordinates": coords}})
        print(f"  total so far: {len(feats)}")
        time.sleep(5)
    out = DATA / f"raw_{layer}.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                              separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(feats)} ways -> {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    names = sys.argv[1:] or ["rail"]
    bad = [n for n in names if n not in LAYERS]
    if bad:
        sys.exit(f"Unknown layer: {bad}. Choose from {list(LAYERS)}")
    for n in names:
        fetch_layer(n)
