"""Clean up the QGIS edit into data/tol.geojson for the web page.

Input : data/tol_edit.geojson  (QGIS output, tgl_operasi column filled as YYYY-MM-DD)
Output: data/tol.geojson       (lightweight, only the columns the web page uses)

What it does:
  - validate tgl_operasi (YYYY-MM-DD, 1978..this year) and CRS (lon/lat WGS84)
  - compute length per section (nama + seksi) WITHOUT double-counting directions:
      * if panjang_km is filled on any feature of that section -> use that number (BPJT)
      * otherwise -> geometry length, halved if the way is oneway (left+right carriageways)
    then split proportionally across features, so the web total = the section total
  - summarize km per era to compare with the official BPJT figures

Usage:  python scripts/build.py
"""
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "data" / "tol_edit.geojson", ROOT / "data" / "tol.geojson"
ERAS = [("Before 2004", "1900-01-01", "2004-10-20"), ("SBY", "2004-10-20", "2014-10-20"),
        ("Jokowi", "2014-10-20", "2024-10-20"), ("Prabowo", "2024-10-20", "2100-01-01")]


def line_km(coords):
    s = 0.0
    for (x1, y1, *_), (x2, y2, *_) in zip(coords, coords[1:]):
        p1, p2 = math.radians(y1), math.radians(y2)
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(x2 - x1) / 2) ** 2
        s += 2 * 6371 * math.asin(math.sqrt(h))
    return s


def geom_km(g):
    return line_km(g["coordinates"]) if g["type"] == "LineString" else sum(line_km(c) for c in g["coordinates"])


def valid(f):
    p, g = f.get("properties") or {}, f.get("geometry")
    d = str(p.get("tgl_operasi") or "")[:10]
    try:
        dt = date.fromisoformat(d)
    except ValueError:
        return None
    if not (1978 <= dt.year <= date.today().year):
        return None
    if not g or g["type"] not in ("LineString", "MultiLineString"):
        return None
    x, y = (g["coordinates"][0] if g["type"] == "LineString" else g["coordinates"][0][0])[:2]
    if not (94 <= x <= 142 and -12 <= y <= 7):
        return None  # not Indonesian lon/lat, check the export CRS (must be EPSG:4326)
    return d


def main() -> int:
    if not SRC.exists():
        print(f"Not found: {SRC}. Export from QGIS first (GeoJSON, EPSG:4326).", file=sys.stderr)
        return 1
    feats = json.loads(SRC.read_text(encoding="utf-8"))["features"]

    groups, skipped = defaultdict(list), 0
    for f in feats:
        d = valid(f)
        if d is None:
            skipped += 1
            continue
        p = f["properties"]
        p["tgl_operasi"] = d
        groups[(p.get("nama") or "Unnamed", p.get("seksi") or "")].append(f)

    out, totals = [], {e[0]: 0.0 for e in ERAS}
    for (nama, seksi), fs in groups.items():
        geo = [geom_km(f["geometry"]) for f in fs]
        given = [float(f["properties"]["panjang_km"]) for f in fs if f["properties"].get("panjang_km")]
        oneway = any(str(f["properties"].get("oneway")) == "yes" for f in fs)
        seksi_km = given[0] if given else sum(geo) / (2 if oneway else 1)
        d = min(f["properties"]["tgl_operasi"] for f in fs)
        era = next(e[0] for e in ERAS if e[1] <= d < e[2])
        totals[era] += seksi_km
        for f, gk in zip(fs, geo):
            share = seksi_km * gk / sum(geo) if sum(geo) else 0
            out.append({"type": "Feature", "geometry": f["geometry"], "properties": {
                "nama": nama, "seksi": seksi, "tgl_operasi": f["properties"]["tgl_operasi"],
                "panjang_km": round(share, 3), "sumber": f["properties"].get("sumber")}})

    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": out}, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} features, {len(groups)} sections -> {OUT}")
    print(f"{skipped} features skipped (empty/invalid date, non-line geometry, or CRS not 4326)")
    print("\nKm per era (compare with BPJT):")
    for era, v in totals.items():
        print(f"  {era:<14}{v:>9,.1f} km")
    print(f"  {'TOTAL':<14}{sum(totals.values()):>9,.1f} km")
    return 0


if __name__ == "__main__":
    sys.exit(main())
