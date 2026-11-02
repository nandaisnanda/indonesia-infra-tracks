# Indonesia Infrastructure Lines

A WebGIS of Indonesia's toll roads, railways and national roads by **year of opening**, grouped by presidential era.
#30DayMapChallenge 2026, Day 2: Lines.

No server and no build step. The page is HTML plus GeoJSON and runs on GitHub Pages.

## Structure

```
index.html                 map (MapLibre GL, 10 basemaps, three line layers)
data/tol.geojson           toll roads (built by apply_dates.py)
data/rel.geojson           railways (built by build_lines.py)
data/jalan.geojson         national roads, trunk and primary (built by build_lines.py)
data/osm_motorway.geojson  raw highway=motorway ways from OSM
data/raw_*.geojson         raw Overpass downloads for rail, trunk, primary (not committed)
data/tgl_ruas.json         toll opening dates for roads that sit in a single era
data/seksi.json            toll section dates for roads that span eras
data/junctions.json        junction and toll-booth nodes used to split sections
data/rel_tgl.json          railway opening dates, by OSM line name
data/jalan_tgl.json        optional opening dates for strategic roads, by name or ref
scripts/fetch_osm.py       fetch highway=motorway for Indonesia from Overpass
scripts/fetch_lines.py     fetch rail, trunk and primary ways from Overpass
scripts/apply_dates.py     merge toll geometry and dates, print km per era
scripts/build_lines.py     simplify and date the rail and road layers
scripts/build.py           older QGIS-based validator, no longer needed
```

If `data/tol.geojson` is missing, the page falls back to raw OSM geometry, then to a DEMO mode with illustrative straight lines and a red banner. The railway and road layers load on demand, so the national roads file only downloads when that layer is switched on.

## Data flow

1. `pip install requests`.
2. Toll: `python scripts/fetch_osm.py`, add dates to `data/tgl_ruas.json` or `data/seksi.json`, then `python scripts/apply_dates.py`.
3. Rail and roads: `python scripts/fetch_lines.py rail trunk primary` (about 30 minutes, Overpass is slow), then `python scripts/build_lines.py`.
4. Compare toll totals with Wikipedia or BPJT. If they differ a lot, check for a wrong date or a duplicated section.

Era boundaries: SBY starts 20 Oct 2004, Jokowi 20 Oct 2014, Prabowo 20 Oct 2024.

Lengths follow the layer. Toll km is geometry length divided by 2, because each OSM motorway way is one carriageway. Rail km is track length. Road km is centerline length.

## Dates and gaps

Toll dates come from Indonesian Wikipedia and news reports. Rail dates come from OSM `start_date` and `opening_date` tags plus the short list in `rel_tgl.json`. Most colonial-era lines carry no date in OSM, so they show as "existing, date unknown" in grey and stay visible at every year. National roads are undated unless listed in `jalan_tgl.json`.

## Deploy to GitHub Pages

Push to `main`, then in **Settings → Pages** choose **Deploy from a branch → main / (root)**.
The site is at `https://nandaisnanda.github.io/indonesia-infra-tracks/`.

To test locally, use a server, because `fetch` does not work from `file://`:

```bash
python -m http.server 8000   # open http://localhost:8000
```

## Presentation notes

- Color shows when a line opened, not who built it. Many lines were planned and built across eras.
- The palette is Okabe-Ito, which stays readable for color-blind viewers.
- Web Mercator suits exploration. Do not use it to compare areas.
- Check toll dates against BPJT before publishing.

## Data license

Geometry © OpenStreetMap contributors, ODbL. If you publish the GeoJSON files, credit OSM and the ODbL license.
