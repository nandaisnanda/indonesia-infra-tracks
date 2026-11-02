"""Build the rail and road layers the page reads.

Input : data/raw_rail.geojson, raw_trunk.geojson, raw_primary.geojson   (fetch_lines.py)
        data/rel_tgl.json      opening dates for railway lines, by OSM line NAME
        data/jalan_tgl.json    opening dates for strategic roads, by OSM road NAME or REF
Output: data/rel.geojson       railway lines (dated where known, otherwise "existing")
        data/jalan.geojson     national roads (trunk/primary) plus dated strategic roads

Geometry is simplified (Douglas-Peucker) and rounded so the files stay small enough for
GitHub Pages. Ways with the same name/ref/class and dates are merged into one MultiLineString.

Usage:  python scripts/build_lines.py
"""
import json
import math
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RAIL_DROP_SERVICE = {"yard", "siding", "crossover", "spur", "depot", "wye"}
RAIL_DROP_USAGE = {"industrial", "test"}
TOL_DEG = {"rail": 0.0002, "trunk": 0.0005, "primary": 0.0008}   # ~20 m / 55 m / 90 m


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def line_km(c):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        p1, p2 = math.radians(y1), math.radians(y2)
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(x2 - x1) / 2) ** 2
        s += 2 * 6371 * math.asin(math.sqrt(h))
    return s


def simplify(pts, tol):
    """Iterative Douglas-Peucker on lon/lat degrees (fine at this tolerance)."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        far, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if den == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / den))
                d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d > far:
                far, idx = d, i
        if far > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def date_of(props):
    """OSM opening_date/start_date when it is a plain ISO date or year."""
    for k in ("opening_date", "start_date"):
        v = (props.get(k) or "").strip()
        if len(v) >= 4 and v[:4].isdigit():
            y = int(v[:4])
            if 1850 <= y <= 2100:
                return v[:10] if len(v) >= 10 and v[4] == "-" else f"{v[:4]}-01-01"
    return None


def emit(groups, tol, path):
    feats, total = [], 0.0
    for (key, props), lines in groups.items():
        lines = [simplify(l, tol) for l in lines]
        lines = [l for l in lines if len(l) >= 2]
        if not lines:
            continue
        km = round(sum(line_km(l) for l in lines), 2)
        total += km
        p = dict(props)
        p["panjang_km"] = km
        geom = ({"type": "LineString", "coordinates": lines[0]} if len(lines) == 1
                else {"type": "MultiLineString", "coordinates": lines})
        feats.append({"type": "Feature", "properties": p, "geometry": geom})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                               separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"  {path.name}: {len(feats)} features, {total:,.0f} km, {path.stat().st_size / 1e6:.2f} MB")


def build_rail():
    raw = load("raw_rail.geojson")
    if not raw:
        return print("raw_rail.geojson missing; run fetch_lines.py rail")
    table = {}
    for r in (load("rel_tgl.json") or {"ruas": []})["ruas"]:
        for n in r["nama"]:
            table[n] = r
    groups = defaultdict(list)
    for f in raw["features"]:
        p = f["properties"]
        rw = p.get("railway")
        if rw == "narrow_gauge" or p.get("service") in RAIL_DROP_SERVICE or p.get("usage") in RAIL_DROP_USAGE:
            continue
        if p.get("construction") or "Pabrik" in (p.get("operator") or ""):
            continue
        name = p.get("name") or "Unnamed rail"
        info = table.get(name, {})
        tgl = info.get("tgl") or date_of(p)
        jenis = {"subway": "MRT", "light_rail": "LRT"}.get(rw, "Rail")
        props = {"nama": name, "jenis": jenis, "operator": p.get("operator") or ""}
        if tgl:
            props["tgl_operasi"] = tgl
            props["sumber"] = info.get("sumber", "OpenStreetMap opening_date/start_date")
        if info.get("catatan"):
            props["catatan"] = info["catatan"]
        groups[(name, tuple(sorted(props.items())))].append(f["geometry"]["coordinates"])
    emit(groups, TOL_DEG["rail"], DATA / "rel.geojson")


def build_roads():
    """Trunk and primary roads, merged by name/ref. Dated only where jalan_tgl.json says so."""
    table = {}
    for r in (load("jalan_tgl.json") or {"ruas": []})["ruas"]:
        for n in r["nama"]:
            table[n] = r
    groups = defaultdict(list)
    for layer in ("trunk", "primary"):
        raw = load(f"raw_{layer}.geojson")
        if not raw:
            print(f"  raw_{layer}.geojson missing; run fetch_lines.py {layer}")
            continue
        for f in raw["features"]:
            p = f["properties"]
            if p.get("construction"):
                continue
            ref = p.get("ref") or ""
            name = p.get("name") or (f"Road {ref}" if ref else f"Unnamed {layer} road")
            info = table.get(name) or table.get(ref) or {}
            props = {"nama": name, "jenis": "Trunk road" if layer == "trunk" else "Primary road", "ref": ref}
            if info.get("tgl"):
                props["tgl_operasi"] = info["tgl"]
                props["sumber"] = info.get("sumber", "")
                if info.get("catatan"):
                    props["catatan"] = info["catatan"]
            groups[(name, tuple(sorted(props.items())))].append(f["geometry"]["coordinates"])
    # primary roads are simplified harder than trunk roads, so emit each class separately
    trunk = {k: v for k, v in groups.items() if dict(k[1])["jenis"] == "Trunk road"}
    prim = {k: v for k, v in groups.items() if k not in trunk}
    merged = {}
    for g, tol in ((trunk, TOL_DEG["trunk"]), (prim, TOL_DEG["primary"])):
        for k, lines in g.items():
            merged[k] = [simplify(l, tol) for l in lines]
    emit(merged, 0, DATA / "jalan.geojson")


def main():
    print("Rail")
    build_rail()
    print("Roads")
    build_roads()


if __name__ == "__main__":
    main()
