#!/usr/bin/env python3
"""Prepare inputs for the DuckDB aggregation stage (PLAN.md Phase 2).

Three cacheable steps, each skipped when its output already exists:

1. **NetCDF → Parquet**: reshape each cached ERA5 file from a (day, lat, lon)
   grid into a tidy long table so DuckDB can scan it. No aggregation happens
   here — all of that lives in 03_aggregate.sql.
2. **NUTS boundaries**: download Eurostat/GISCO NUTS-1 polygons (2021 edition,
   1:20M — the last edition that still includes the UK, which this story
   needs). © EuroGeographics; logged in data/SOURCES.md.
3. **Cell→region mapping**: point-in-polygon join assigning each ERA5 grid
   cell to a NUTS-1 region. This is geometry, not aggregation, so it's done
   once here with geopandas; the daily GROUP BYs in SQL then join against
   the resulting plain table. Sea cells match no region and drop out.

Usage: python 02_baseline.py [--force]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("02_baseline")

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ERA5 = REPO_ROOT / "data" / "raw" / "era5"
RAW_NUTS = REPO_ROOT / "data" / "raw" / "nuts"
INTERIM = REPO_ROOT / "data" / "interim"

# NUTS 2021, 1:20M generalised, WGS84, level 1 only. The 2024 edition drops
# the UK (post-Brexit), so 2021 it is.
NUTS_URL = ("https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
            "NUTS_RG_20M_2021_4326_LEVL_1.geojson")
NUTS_FILE = RAW_NUTS / "NUTS_RG_20M_2021_4326_LEVL_1.geojson"

# Same Europe bbox as 01_download.py (lat_min, lat_max, lon_min, lon_max).
BBOX = (35.0, 62.0, -11.0, 25.0)


def convert_era5_to_parquet(force: bool) -> None:
    """One tidy Parquet per NetCDF: (date, lat, lon, temp_c) rows in °C."""
    import xarray as xr

    nc_files = sorted(RAW_ERA5.glob("*.nc"))
    if not nc_files:
        sys.exit(f"No NetCDF files in {RAW_ERA5} — run 01_download.py first.")

    for nc in nc_files:
        stat = nc.stem.split("_")[0]  # "tx" or "tn"
        out = INTERIM / "era5" / stat / f"{nc.stem}.parquet"
        # mtime-aware: the current month's NetCDF is re-downloaded on every
        # 01_download.py run, so its parquet must be rebuilt when it's older.
        if out.exists() and not force and out.stat().st_mtime >= nc.stat().st_mtime:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)

        ds = xr.open_dataset(nc)
        df = (
            ds["t2m"].to_dataframe().reset_index()
            .rename(columns={"valid_time": "date", "latitude": "lat",
                             "longitude": "lon", "t2m": "temp_c"})
            [["date", "lat", "lon", "temp_c"]]
        )
        df["temp_c"] = (df["temp_c"] - 273.15).astype("float32")  # K → °C
        # Write-then-rename so an interrupted run never leaves a truncated
        # parquet that a later run would mistake for a cache hit.
        tmp = out.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(out)
        ds.close()
        log.info("converted %s (%d rows)", out.relative_to(REPO_ROOT), len(df))


def download_nuts(force: bool) -> None:
    """Fetch NUTS-1 GeoJSON once; record provenance in a sidecar."""
    import requests

    if NUTS_FILE.exists() and not force:
        log.info("cached: %s", NUTS_FILE.name)
        return
    NUTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    log.info("downloading NUTS boundaries from GISCO ...")
    resp = requests.get(NUTS_URL, timeout=120)
    resp.raise_for_status()
    part = NUTS_FILE.with_suffix(".part")
    part.write_bytes(resp.content)
    part.replace(NUTS_FILE)

    NUTS_FILE.with_suffix(".meta.json").write_text(json.dumps({
        "url": NUTS_URL,
        "licence": "© EuroGeographics for the administrative boundaries",
        "retrieved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    log.info("saved %s (%.1f MB)", NUTS_FILE.name, len(resp.content) / 1e6)


def build_cell_region_map(force: bool) -> None:
    """Assign each ERA5 grid cell to the NUTS-1 region containing it."""
    import geopandas as gpd
    import pandas as pd
    import xarray as xr

    out = INTERIM / "cell_region.parquet"
    if out.exists() and not force:
        log.info("cached: %s", out.name)
        return

    # The grid is identical across all files; take it from any one of them.
    sample = next(RAW_ERA5.glob("*.nc"))
    ds = xr.open_dataset(sample)
    grid = pd.MultiIndex.from_product(
        [ds["latitude"].values, ds["longitude"].values], names=["lat", "lon"]
    ).to_frame(index=False)
    ds.close()

    cells = gpd.GeoDataFrame(
        grid, geometry=gpd.points_from_xy(grid["lon"], grid["lat"]),
        crs="EPSG:4326",
    )

    lat_min, lat_max, lon_min, lon_max = BBOX
    nuts = gpd.read_file(NUTS_FILE).cx[lon_min:lon_max, lat_min:lat_max]
    nuts = nuts.rename(columns={
        "NUTS_ID": "region_id", "NAME_LATN": "region_name",
        "CNTR_CODE": "country",
    })[["region_id", "region_name", "country", "geometry"]]

    joined = gpd.sjoin(cells, nuts, predicate="within", how="inner")
    result = joined[["lat", "lon", "region_id", "region_name", "country"]]
    result.to_parquet(out, index=False)
    log.info("mapped %d of %d cells to %d regions -> %s",
             len(result), len(cells), result["region_id"].nunique(),
             out.relative_to(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true",
                        help="rebuild outputs even if cached")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    convert_era5_to_parquet(args.force)
    download_nuts(args.force)
    build_cell_region_map(args.force)
    log.info("Done. Next: 04_export.py (runs 03_aggregate.sql).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
