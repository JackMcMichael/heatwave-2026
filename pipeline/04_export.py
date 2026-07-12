#!/usr/bin/env python3
"""Run 03_aggregate.sql and export the site's static data (PLAN.md Phase 2).

Outputs, all under site/data/ (committed to the repo, served by Pages):

* regions.geojson      — simplified NUTS-1 polygons, budget ≤ 500 KB
* daily_anomaly.json   — region × date matrix for 17–30 June, budget ≤ 300 KB
* events.json          — hand-curated timeline markers (records, warnings)
* cities/{name}.json   — per-city detail series, lazy-loaded by the frontend

The build FAILS if a size budget is exceeded (PLAN.md §6) — better a red
build than a slow site. Numbers are rounded in SQL (1 decimal) and coords
quantised to 3 decimals (~110 m), which is plenty for a country-scale map.

Usage: python 04_export.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

log = logging.getLogger("04_export")

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_FILE = Path(__file__).parent / "03_aggregate.sql"
NUTS_FILE = (REPO_ROOT / "data" / "raw" / "nuts"
             / "NUTS_RG_20M_2021_4326_LEVL_1.geojson")
SITE_DATA = REPO_ROOT / "site" / "data"

# Rolling timeline: 17 June 2026 through the newest day in the data.
# The end date is discovered from region_daily at export time.
TIMELINE_START = date(2026, 6, 17)

BUDGET = {"regions.geojson": 500_000, "daily_anomaly.json": 300_000}

# Simplification tolerance in degrees (~1 km) on top of GISCO's 1:20M
# generalisation; raise this first if regions.geojson busts its budget.
SIMPLIFY_TOLERANCE_DEG = 0.01

# Timeline markers. Record values are PROVISIONAL (Met Office verification
# ongoing as of July 2026) — re-verify against primary sources in Phase 5
# before publishing; entries with "date": null still need their date sourced.
EVENTS = [
    {"date": "2026-06-23", "country": "FR", "title": "France's hottest day on record",
     "detail": "44.3°C at Pissos, Landes", "provisional": True},
    {"date": "2026-06-24", "country": "UK", "title": "First of three consecutive Met Office red heat warnings",
     "detail": "Red warnings issued 24–26 June — a first since the system began", "provisional": True},
    {"date": "2026-06-26", "country": "UK", "title": "Provisional UK June record",
     "detail": "37.7°C at Lingwood, Norfolk", "provisional": True},
    {"date": None, "country": "NL", "title": "Netherlands June record",
     "detail": "39.4°C", "provisional": True},
    {"date": None, "country": "CH", "title": "Switzerland June record",
     "detail": "39.0°C", "provisional": True},
    {"date": None, "country": "HU", "title": "Hungary June record",
     "detail": "40.7°C", "provisional": True},
    {"date": None, "country": "AT", "title": "Austria June record",
     "detail": "40.0°C", "provisional": True},
]


def run_sql(con: duckdb.DuckDBPyConnection) -> None:
    """Execute 03_aggregate.sql statement by statement.

    Comment lines are stripped before splitting on ';' so a semicolon in
    prose doesn't get mistaken for a statement boundary.
    """
    lines = [ln for ln in SQL_FILE.read_text(encoding="utf-8").splitlines()
             if not ln.lstrip().startswith("--")]
    for statement in "\n".join(lines).split(";"):
        if statement.strip():
            con.execute(statement)


def write_json(path: Path, payload) -> int:
    """Compact JSON (no whitespace); returns bytes written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    size = path.stat().st_size
    log.info("wrote %s (%.0f KB)", path.relative_to(REPO_ROOT), size / 1000)
    return size


def export_daily_anomaly(con) -> set[str]:
    """Region × date matrix, arrays aligned with the shared date list.

    The timeline end isn't fixed: it's whatever the newest date in
    region_daily is, so re-running the pipeline extends the site's slider.
    """
    # ::DATE matters: the parquet date column is a timestamp, and exporting
    # "2026-06-17T00:00:00" would break the frontend's event-date matching.
    timeline = [d for (d,) in con.execute(
        "SELECT DISTINCT date::DATE FROM region_daily WHERE date >= ? ORDER BY date",
        [TIMELINE_START]).fetchall()]
    rows = con.execute(
        """
        SELECT region_id, any_value(region_name), any_value(country),
               list(anomaly_c   ORDER BY date) AS anomalies,
               list(tx_mean_c   ORDER BY date) AS tx_means,
               list(tx_max_c    ORDER BY date) AS tx_maxes,
               list(tropical_pct ORDER BY date) AS tropical
        FROM region_daily
        WHERE date >= ?
        GROUP BY region_id
        ORDER BY region_id
        """,
        [TIMELINE_START],
    ).fetchall()

    payload = {
        "dates": [d.isoformat() for d in timeline],
        "baseline": "1991-2020 monthly normals (ERA5)",
        "regions": {
            rid: {"name": name, "country": country,
                  "anomaly": anom, "tx": tx, "tx_max": txx, "tropical": trop}
            for rid, name, country, anom, tx, txx, trop in rows
        },
    }
    write_json(SITE_DATA / "daily_anomaly.json", payload)
    return {r[0] for r in rows}


def export_regions_geojson(region_ids: set[str]) -> None:
    """Simplified NUTS-1 polygons for exactly the regions that have data."""
    import geopandas as gpd
    from shapely.ops import transform

    nuts = gpd.read_file(NUTS_FILE)
    nuts = nuts[nuts["NUTS_ID"].isin(region_ids)].copy()
    missing = region_ids - set(nuts["NUTS_ID"])
    if missing:
        sys.exit(f"regions in data but not in NUTS file: {sorted(missing)}")

    nuts["geometry"] = (
        nuts.geometry
        .simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        .apply(lambda g: transform(lambda x, y: (round(x, 3), round(y, 3)), g))
    )

    features = [
        {"type": "Feature",
         "properties": {"id": row.NUTS_ID, "name": row.NAME_LATN,
                        "country": row.CNTR_CODE},
         "geometry": row.geometry.__geo_interface__}
        for row in nuts.itertuples()
    ]
    write_json(SITE_DATA / "regions.geojson",
               {"type": "FeatureCollection", "features": features})


def export_cities(con) -> None:
    """One lazy-loadable file per city: 2026 series + aligned normals.

    Normals are joined per (month, day) so every 2026 date — whichever month
    the rolling timeline has reached — sits next to its own normal, and all
    five arrays share the same length and order.
    """
    cities = [c for (c,) in con.execute(
        "SELECT DISTINCT city FROM city_daily ORDER BY city").fetchall()]

    for city in cities:
        rows = con.execute(
            """
            SELECT d.date, d.tx, d.tn, c.clim_tx, c.clim_tn
            FROM city_daily d
            JOIN city_clim c ON c.city = d.city
                            AND c.month = month(d.date)
                            AND c.day = day(d.date)
            -- Open-Meteo lags real time by a few days: requested-but-not-yet-
            -- published days come back as nulls. Drop them; the next refresh
            -- fills them in.
            WHERE d.city = ? AND d.tx IS NOT NULL AND d.tn IS NOT NULL
            ORDER BY d.date
            """, [city]).fetchall()
        if not rows:  # defensive: never let one city kill the whole export
            log.warning("no complete days for city %r — skipped", city)
            continue
        dates, tx, tn, clim_tx, clim_tn = map(list, zip(*rows))

        write_json(SITE_DATA / "cities" / f"{city}.json", {
            "city": city,
            "dates": [d.isoformat() for d in dates],
            "tx": tx,
            "tn": tn,
            "clim_tx": clim_tx,
            "clim_tn": clim_tn,
            # Tropical night: daily minimum stays at or above 20 °C.
            "tropical_nights_2026": sum(v >= 20.0 for v in tn),
        })


def check_budgets() -> None:
    over = {
        name: size for name, cap in BUDGET.items()
        if (size := (SITE_DATA / name).stat().st_size) > cap
    }
    if over:
        sys.exit(f"SIZE BUDGET EXCEEDED (PLAN.md §6): {over} "
                 f"— raise SIMPLIFY_TOLERANCE_DEG or trim fields.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    con = duckdb.connect()          # in-memory; nothing to clean up
    import os
    os.chdir(REPO_ROOT)             # 03_aggregate.sql uses repo-root paths

    run_sql(con)
    region_ids = export_daily_anomaly(con)
    export_regions_geojson(region_ids)
    export_cities(con)
    write_json(SITE_DATA / "events.json", EVENTS)
    check_budgets()

    log.info("site/data populated for %d regions. Run pytest next.",
             len(region_ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
