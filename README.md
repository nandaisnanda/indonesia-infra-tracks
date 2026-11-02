# Indonesia Toll Lines

A WebGIS of Indonesia's toll road network by **year of opening**, grouped by presidential era.
#30DayMapChallenge 2026, Day 2: Lines.

No server and no build step. The page is HTML plus GeoJSON and runs on GitHub Pages.

## Structure

```
index.html              map (MapLibre GL, 10 basemaps)
data/tol.geojson        final data the page reads (built by apply_dates.py)
data/osm_motorway.geojson  raw highway=motorway ways from OSM
data/tgl_ruas.json      opening dates for roads that sit in a single era
data/seksi.json         section-by-section dates for roads that span eras
data/junctions.json     junction and toll-booth nodes used to split sections
scripts/fetch_osm.py    fetch highway=motorway for Indonesia from Overpass
scripts/apply_dates.py  merge geometry and dates, print km per era
scripts/build.py        older QGIS-based validator, no longer needed
```

If `data/tol.geojson` is missing, the page falls back to raw OSM geometry, then to a DEMO mode with illustrative straight lines and a red banner.

## Data flow

1. `pip install requests`, then `python scripts/fetch_osm.py` writes `data/osm_motorway.geojson`.
2. Add a road's opening date to `data/tgl_ruas.json`. For a road that opened in stages across eras, add its junctions and per-section dates to `data/seksi.json` instead.
3. `python scripts/apply_dates.py` writes `data/tol.geojson` and prints km per era in the terminal.
4. Compare the totals with the lengths on Wikipedia or BPJT. If they differ a lot, check for a wrong date or a duplicated section.

Era boundaries: SBY starts 20 Oct 2004, Jokowi 20 Oct 2014, Prabowo 20 Oct 2024.
Each OSM motorway way is one carriageway, so km is geometry length divided by 2.

## Deploy to GitHub Pages

```bash
git init && git add . && git commit -m "Indonesia Toll Lines"
git branch -M main
git remote add origin https://github.com/nandaisnanda/garis-tol.git
git push -u origin main
```

On GitHub, go to **Settings → Pages → Source: Deploy from a branch → main / (root)**.
The site goes live at `https://nandaisnanda.github.io/garis-tol/` within 1 to 2 minutes.

To test locally, use a server, because `fetch` does not work from `file://`:

```bash
python -m http.server 8000   # open http://localhost:8000
```

## Presentation notes

- Color shows when a section opened, not who built it. Many roads were planned and built across eras, and the side panel says so.
- The palette is Okabe-Ito, which stays readable for color-blind viewers.
- Web Mercator suits exploration. Do not use it to compare areas.
- Dates come from Indonesian Wikipedia and news reports. Check them against BPJT before publishing.

## Data license

Geometry © OpenStreetMap contributors, ODbL. If you publish `tol.geojson`, credit OSM and the ODbL license.
