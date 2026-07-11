# Project Plan: "Anatomy of a Heatwave" — June 2026 UK & Europe

Interactive climate analytics portfolio piece. Animated map + timeline of the June 2026
European heatwave, with pre-aggregated data built by a Python/SQL pipeline and served as a
static site on GitHub Pages.

**Author:** Jackie · Climate Data & Analytics
**Intended workflow:** This document is the brief for a Claude Code session. Work through the
phases in order; each phase has acceptance criteria.

---

## 1. Concept & narrative

Tell the story of the 17–30 June 2026 heatwave across the UK and Western/Central Europe:

- A scrubbing **timeline** (17 June → 30 June, daily steps, optional auto-play) driving a
  **choropleth/heat map** of daily maximum temperature anomaly vs the 1991–2020 June baseline.
- **Event markers** pinned to key dates: record-breaking days (e.g. UK June record 37.7°C at
  Lingwood, Norfolk on 26 June; France's hottest day on record, 44.3°C at Pissos on 23 June;
  national June records in NL 39.4°C, CH 39.0°C, HU 40.7°C, AT 40.0°C), Met Office red warnings
  (24–26 June — first-ever three consecutive red heat warnings), UKHSA red heat-health alerts.
- A **station detail panel**: click a country/region to see its daily max/min series for June
  2026 vs climatology, including "tropical nights" (min ≥ 20°C).
- Short written analysis section: context (England's warmest June on record; second UK heatwave
  of the year after the late-May event), attribution (World Weather Attribution rapid study),
  impacts (excess mortality estimates, rail disruption, wildfire risk, energy demand).

Verify all headline figures against primary sources during Phase 1 — treat the numbers above as
provisional pointers, not final copy.

## 2. Data sources & licences

Record every source in `data/SOURCES.md` with licence text and retrieval date. All of the below
are free and permit non-commercial publication with attribution.

### Primary gridded temperature data (choose ONE for the map)

1. **ERA5 / ERA5-Land reanalysis** — Copernicus Climate Data Store (CDS).
   - Access: `cdsapi` Python package (free registration, API key).
   - Variables: 2m max/min temperature, daily aggregates via "ERA5 post-processed daily statistics" dataset.
   - Licence: Copernicus licence — free use, must credit: *"Contains modified Copernicus Climate
     Change Service information [2026]. Neither the European Commission nor ECMWF is responsible
     for any use of this information."*
   - Pros: authoritative, consistent across all of Europe. Cons: ~0.25° (ERA5) / 0.1° (ERA5-Land)
     resolution; CDS queue can be slow — cache raw downloads.

2. **E-OBS gridded dataset** (ECA&D / Copernicus) — station-based European grid, daily TX/TN/TG
   at 0.1°. Good for anomaly work; requires the standard E-OBS acknowledgement.

### Supporting / UK-specific

3. **HadUK-Grid** (Met Office, via CEDA) — 1km UK daily grids. Open Government Licence (OGL v3).
   Optional UK zoom layer.
4. **Open-Meteo Historical Weather API** — free non-commercial tier, no key needed, CC BY 4.0.
   Excellent for the per-city detail panel time series (fast, JSON, no queue). Attribution:
   "Weather data by Open-Meteo.com".
5. **UKHSA heat-health alerts** and **Met Office warnings** — published under OGL v3; use for the
   event-marker layer (dates/regions of amber/red alerts).
6. **World Weather Attribution rapid study (June 2026)** — cite for the attribution section.

### Boundaries & basemap

7. **NUTS region boundaries** — Eurostat/GISCO GeoJSON (© EuroGeographics; attribution required).
   Use NUTS-1 or NUTS-2 for aggregation regions; simplify geometry aggressively.
8. **Basemap**: either no basemap (pure choropleth on a neutral background — fastest) or
   OpenStreetMap-based vector tiles via OpenFreeMap/Protomaps (check current attribution terms).
   ODbL attribution "© OpenStreetMap contributors" if OSM-derived.

## 3. Architecture

Two completely decoupled stages:

```
[Stage A — offline pipeline, Python + SQL]
  cdsapi / requests  →  raw NetCDF / JSON  (data/raw/, gitignored, cached)
        │  xarray: daily TX/TN, clip to Europe bbox, compute anomaly vs 1991–2020 June normals
        ▼
  DuckDB (spatial ext): join grid cells → NUTS regions, GROUP BY region, date
        ▼
  Small static outputs (site/data/):
    - regions.geojson        (simplified NUTS polygons, ~200–400 KB)
    - daily_anomaly.json     (region × date matrix of TX anomaly + absolute TX, ~50–150 KB)
    - events.json            (hand-curated markers: records, warnings, key dates)
    - cities/{name}.json     (per-city daily series for detail panel, lazy-loaded)

[Stage B — static frontend, GitHub Pages]
  index.html + MapLibre GL JS + vanilla JS timeline
  Loads regions.geojson once, restyles fill colours per timeline step (no re-fetch)
```

Key principle: **the browser never touches raw data**. All heavy lifting happens once, offline.
Timeline scrubbing is just a `setPaintProperty`/feature-state update — effectively instant on
mobile.

### Why these choices

- **DuckDB** gives you the SQL you're fluent in for the aggregation layer, runs in-process, has a
  spatial extension, and reads Parquet/GeoJSON natively. Pipeline pattern: xarray → tidy
  DataFrame/Parquet → DuckDB SQL → JSON.
- **MapLibre GL JS** (BSD) over Leaflet: GPU-rendered vector fills animate smoothly when driven
  by a slider; feature-state updates avoid re-parsing GeoJSON per frame. Leaflet is an
  acceptable simpler fallback if MapLibre feels heavy.
- **GitHub Actions** (optional Phase 6): re-run the pipeline on demand; but since this is a
  historical event, a one-off local run committed to the repo is fine and simpler.

## 4. Repo structure

```
heatwave-2026/
├── README.md
├── PLAN.md                  ← this file
├── pipeline/
│   ├── pyproject.toml       (deps: cdsapi, xarray, netcdf4, duckdb, pandas, geopandas, shapely)
│   ├── 01_download.py       (CDS + Open-Meteo pulls, cached to data/raw/)
│   ├── 02_baseline.py       (1991–2020 June climatology per grid cell)
│   ├── 03_aggregate.sql     (DuckDB: cell→NUTS join, daily region stats)
│   ├── 04_export.py         (write site/data/*.json, run size checks)
│   └── tests/               (pytest: schema, value ranges, region coverage)
├── data/
│   ├── raw/                 (gitignored)
│   └── SOURCES.md           (source, licence, URL, retrieval date, citation text)
├── site/                    ← GitHub Pages root
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js  js/timeline.js  js/map.js
│   ├── data/                (pipeline outputs, committed)
│   └── attributions.html
└── .github/workflows/deploy.yml   (Pages deploy from site/)
```

## 5. Build phases (Claude Code milestones)

**Phase 0 — Scaffold (30 min)**
Repo, Pages deployment from `site/` (or `docs/`), placeholder index.html live at
`<user>.github.io/heatwave-2026`. ✅ Done when the placeholder is publicly reachable.

**Phase 1 — Data acquisition (1–2 sessions)**
CDS account + `~/.cdsapirc`; download script with local caching; pull June 2026 daily TX/TN for
Europe bbox (approx 35–62°N, -11–25°E) plus June 1991–2020 for the baseline (ERA5 daily
statistics dataset keeps this manageable — avoid downloading hourly). Verify a known value
(e.g. the 26 June UK peak appears in the right grid cell ballpark). ✅ Done when raw NetCDF is
cached and a sanity-check notebook/script confirms plausible values against 3+ published record
figures.

**Phase 2 — Aggregation pipeline (1–2 sessions)**
Climatology → anomaly grids → DuckDB spatial join to simplified NUTS regions → daily region
table → JSON exports with size assertions (fail build if `daily_anomaly.json` > 300 KB or
`regions.geojson` > 500 KB). Write pytest checks: every region has all 14 dates; anomalies in a
sane range (-5 to +15°C); no nulls. ✅ Done when `site/data/` is populated and tests pass.

**Phase 3 — Map + timeline frontend (2–3 sessions)**
MapLibre choropleth coloured by anomaly; date slider + play/pause (requestAnimationFrame, ~2
steps/sec); colour scale with legend (diverging, anomaly-centred, colour-blind-safe — e.g. a
Viridis/inferno-family ramp); event markers appearing on their dates; region click → detail
panel fetching `cities/{x}.json` lazily. ✅ Done when scrubbing is smooth on a mid-range phone
(test via Chrome DevTools mobile throttling).

**Phase 4 — Mobile & performance polish (1 session)**
Responsive layout (map full-bleed, timeline as bottom sheet on mobile); touch-friendly slider;
`prefers-reduced-motion` respected; Lighthouse mobile score ≥ 90; total transfer on first load
≤ ~1.5 MB including map library. Preload data JSON; defer everything non-critical.

**Phase 5 — Content, attribution, domain (1 session)**
- Written analysis section (300–500 words) with citations.
- `attributions.html` + footer credits: Copernicus/ECMWF statement, E-OBS/ECA&D
  acknowledgement (if used), Met Office data © Crown copyright OGL v3, Open-Meteo CC BY 4.0,
  © EuroGeographics for NUTS boundaries, © OpenStreetMap contributors (if OSM basemap),
  MapLibre licence note. Copy exact required wording from each provider into `SOURCES.md` first.
- Custom domain: in Squarespace DNS add a CNAME (`heatwave` or `www` subdomain →
  `<user>.github.io`) or A/AAAA records for an apex domain; set the custom domain in repo
  Settings → Pages; enforce HTTPS. A subdomain (e.g. `heatwave.yourdomain.com`) is the least
  painful option and leaves the apex free for a future portfolio hub.

**Phase 6 (optional stretch)**
- GitHub Actions workflow that re-runs Phases 1–2 (useful if a July 2026 heatwave chapter is
  added later — one may already be underway).
- "Tropical nights" toggle layer (TN ≥ 20°C count per region).
- WBGT/humidity layer referencing the WWA analysis.
- Compare-mode: June 2026 vs June 1976 analogue.

## 6. Performance budget

| Asset | Budget |
|---|---|
| regions.geojson (simplified, quantised coords) | ≤ 500 KB |
| daily_anomaly.json | ≤ 300 KB |
| JS (app code, excl. MapLibre) | ≤ 50 KB |
| First-load total transfer | ≤ 1.5 MB |
| Timeline scrub frame budget | < 16 ms/step |

Techniques: mapshaper `-simplify 5–10% keep-shapes` on NUTS; 1-decimal precision on anomaly
values; feature-state styling instead of data swaps; gzip/brotli comes free from Pages.

## 7. Suggested opening prompt for Claude Code

> "Read PLAN.md. We're on Phase 0/1. Set up the repo scaffold and GitHub Pages deployment as
> specified, then write pipeline/01_download.py with caching and a dry-run mode. Ask me before
> anything that needs my CDS credentials. Keep Python idiomatic and well-commented; use DuckDB
> SQL for all aggregation logic."

## 8. Risks & mitigations

- **CDS queue delays** → cache aggressively; do downloads early in a session; E-OBS or
  Open-Meteo as fallback for a first working version.
- **Record figures still provisional** (Met Office verification ongoing as of July 2026) → label
  records "provisional" in event markers; re-check before publishing.
- **GeoJSON too heavy on mobile** → drop to NUTS-1, simplify harder, or switch to PMTiles.
- **Licence wording drift** → copy exact attribution text into SOURCES.md at download time.
