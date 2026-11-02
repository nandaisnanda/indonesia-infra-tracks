"""Merge raw OSM geometry with opening dates into data/tol.geojson.

Input : data/osm_motorway.geojson  (output of fetch_osm.py)
        data/tgl_ruas.json         (dates by OSM road NAME, for roads that sit entirely in one era)
        data/seksi.json            (roads spanning eras, split by section using junction points)
        data/junctions.json        (motorway_junction/toll_booth nodes from Overpass, for seksi.json)
Output: data/tol.geojson           (all ways; undated ones show grey on the web page)

Section splitting: junction points form a spine along the road. Each way is attached to the
nearest spine edge via its midpoint, then takes that edge's date.

Dual carriageways are counted once: each motorway way is one carriageway, so km = geometry / 2.

Usage:  python scripts/apply_dates.py
"""
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ERAS = [("Before 2004", "1900-01-01", "2004-10-20"), ("SBY", "2004-10-20", "2014-10-20"),
        ("Jokowi", "2014-10-20", "2024-10-20"), ("Prabowo", "2024-10-20", "2100-01-01")]
MAX_JUNCTION_KM = 5  # same-named junctions farther than this are treated as not belonging to the road


def line_km(c):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        p1, p2 = math.radians(y1), math.radians(y2)
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(x2 - x1) / 2) ** 2
        s += 2 * 6371 * math.asin(math.sqrt(h))
    return s


def xy(p, lat0):
    """lon/lat -> local flat km (good enough for distances of tens of km)."""
    return (p[0] * 111.32 * math.cos(math.radians(lat0)), p[1] * 110.57)


def dist_seg(p, a, b):
    ax, ay, bx, by, px, py = *a, *b, *p
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def resolve_point(spec, vertices, junctions):
    """Manual point [lon,lat], or junction name -> OSM node closest to the road geometry."""
    if isinstance(spec, list):
        return spec
    lat0 = vertices[0][1]
    pts = [xy(v, lat0) for v in vertices[::5]]
    best = None
    for j in junctions:
        if spec.lower() in j["tags"]["name"].lower():
            q = xy((j["lon"], j["lat"]), lat0)
            d = min(math.hypot(q[0] - p[0], q[1] - p[1]) for p in pts)
            if best is None or d < best[0]:
                best = (d, [j["lon"], j["lat"]])
    if best is None or best[0] > MAX_JUNCTION_KM:
        raise SystemExit(f"Junction '{spec}' not found near the road (closest distance: {best and round(best[0], 1)} km)")
    return best[1]


def era_of(tgl):
    return next(e[0] for e in ERAS if e[1] <= tgl < e[2])


def main() -> None:
    ways = json.loads((DATA / "osm_motorway.geojson").read_text(encoding="utf-8"))["features"]
    junctions = [e for e in json.loads((DATA / "junctions.json").read_text(encoding="utf-8"))
                 if e.get("tags", {}).get("name") and e.get("lat")]
    whole = {}
    for r in json.loads((DATA / "tgl_ruas.json").read_text(encoding="utf-8"))["ruas"]:
        for n in r["nama"]:
            whole[n] = r
    split = {r["nama"]: r for r in json.loads((DATA / "seksi.json").read_text(encoding="utf-8"))["ruas"]}

    by_name = defaultdict(list)
    for f in ways:
        by_name[f["properties"].get("name") or "Unnamed"].append(f)

    # name -> (spine, sections) for roads that get split
    spines = {}
    for nama, r in split.items():
        verts = [c for f in by_name[nama] for c in f["geometry"]["coordinates"]]
        pts = [resolve_point(t, verts, junctions) for t in r["titik"]]
        assert len(r["seksi"]) == len(pts) - 1, f"{nama}: number of sections != points-1"
        lat0 = verts[0][1]
        spines[nama] = ([xy(p, lat0) for p in pts], r["seksi"], lat0)

    out, totals, undated = [], defaultdict(float), 0.0
    seksi_km = defaultdict(float)
    for f in ways:
        nama = f["properties"].get("name") or "Unnamed"
        km = round(line_km(f["geometry"]["coordinates"]) / 2, 3)
        props = {"nama": nama, "panjang_km": km}
        info = None
        if nama in spines:
            spine, seksi, lat0 = spines[nama]
            c = f["geometry"]["coordinates"]
            mid = xy(c[len(c) // 2], lat0)
            i = min(range(len(seksi)), key=lambda k: dist_seg(mid, spine[k], spine[k + 1]))
            info = seksi[i]
            props["seksi"] = f"{split[nama]['titik'][i]} – {split[nama]['titik'][i + 1]}".replace("[", "").replace("]", "")
            if isinstance(split[nama]["titik"][i], list):
                props["seksi"] = f"end – {split[nama]['titik'][i + 1]}"
            seksi_km[(nama, props["seksi"], info.get("tgl"))] += km
        elif nama in whole:
            info = whole[nama]
        if info and info.get("tgl"):
            props.update({"tgl_operasi": info["tgl"], "sumber": info["sumber"]})
            if info.get("catatan"):
                props["catatan"] = info["catatan"]
            totals[era_of(info["tgl"])] += km
        else:
            undated += km
            if info and info.get("status"):
                props["status"] = info["status"]
        out.append({"type": "Feature", "geometry": f["geometry"], "properties": props})

    (DATA / "tol.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out},
                                                 separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} way -> data/tol.geojson")
    for era, _, _ in ERAS:
        print(f"  {era:<16}{totals[era]:>9,.1f} km")
    print(f"  {'Undated':<16}{undated:>9,.1f} km")
    print("\nKm per split section (compare with the lengths on Wikipedia):")
    for (nama, s, tgl), k in sorted(seksi_km.items()):
        print(f"  {nama[:34]:<34} {s[:34]:<34} {str(tgl):<11}{k:>7.1f} km")


if __name__ == "__main__":
    main()
