#!/usr/bin/env python3
"""Download raw inputs for the June 2026 heatwave pipeline (PLAN.md Phase 1).

Two sources, both cached under ``data/raw/`` so re-runs are free:

* **ERA5 daily statistics** (Copernicus CDS, needs ``~/.cdsapirc``):
  daily max/min 2 m temperature over the Europe bbox for June 2026, plus
  June 1991-2020 for the climatological baseline. We use the post-processed
  "daily statistics" dataset rather than hourly ERA5 — ~24x less data and no
  local resampling step.

* **Open-Meteo historical archive** (no key, CC BY 4.0): per-city daily
  Tmax/Tmin series for the frontend detail panel.

Usage::

    python 01_download.py --dry-run          # show the plan, touch nothing
    python 01_download.py                    # download whatever isn't cached
    python 01_download.py --only era5        # just the CDS pulls
    python 01_download.py --only cities      # just Open-Meteo
    python 01_download.py --force            # ignore cache, re-download all

CDS requests sit in a queue that can take minutes to hours, so start ERA5
pulls early in a session (PLAN.md §8). A download is only considered cached
once it has been fully written: files are downloaded to ``*.part`` and
renamed into place, so an interrupted run never poisons the cache.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("01_download")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Repo layout: this file lives in pipeline/, raw data goes to ../data/raw/.
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

# Europe bounding box from PLAN.md Phase 1, in CDS order: North, West, South, East.
EUROPE_BBOX = [62, -11, 35, 25]

EVENT_YEAR = 2026
BASELINE_YEARS = list(range(1991, 2021))  # 1991-2020 climate normal period
JUNE = "06"
JUNE_DAYS = [f"{d:02d}" for d in range(1, 31)]

# CDS dataset for pre-computed daily aggregates of ERA5 single-level fields.
# NOTE: parameter names occasionally change between CDS API versions — if a
# request is rejected, compare against the "API request" tab on the dataset
# page: https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics
CDS_DATASET = "derived-era5-single-levels-daily-statistics"

# Cities for the detail panel. Chosen to cover the headline records (Norwich
# is the nearest city to the Lingwood UK record; Bordeaux to Pissos, FR) plus
# a spread of major cities across the affected area.
CITIES: dict[str, tuple[float, float]] = {
    # name: (latitude, longitude)
    "london": (51.51, -0.13),
    "norwich": (52.63, 1.30),
    "paris": (48.86, 2.35),
    "bordeaux": (44.84, -0.58),
    "amsterdam": (52.37, 4.90),
    "brussels": (50.85, 4.35),
    "berlin": (52.52, 13.41),
    "zurich": (47.37, 8.55),
    "vienna": (48.21, 16.37),
    "budapest": (47.50, 19.04),
    "madrid": (40.42, -3.70),
    "milan": (45.46, 9.19),
}

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_PAUSE_S = 1.0  # be polite to the free tier between requests


# --------------------------------------------------------------------------
# Download job definitions
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Job:
    """One cacheable download: a target file plus how to produce it."""

    name: str            # human-readable label for logs / dry-run table
    source: str          # "era5" or "cities" (matches the --only flag)
    target: Path         # final cached file under data/raw/
    request: dict = field(default_factory=dict)  # source-specific parameters
    est_size: str = "?"  # rough size hint shown in --dry-run

    @property
    def cached(self) -> bool:
        # Treat tiny files as failed partial writes, not cache hits. Real
        # payloads here are >100 kB; an HTML error page or empty file is not.
        return self.target.exists() and self.target.stat().st_size > 10_000


def era5_jobs() -> list[Job]:
    """CDS requests: one file per (statistic, year).

    The daily-statistics dataset computes aggregates on the fly, so it has a
    tight per-request cost cap — a single 30-year baseline request comes back
    "403: cost limits exceeded". One year per request stays under the cap
    (it's the same size as the accepted June 2026 request), and the cache
    makes the 62-request run resumable: re-running skips completed years.
    """
    def request(stat: str, years: list[int]) -> dict:
        return {
            "product_type": "reanalysis",
            "variable": ["2m_temperature"],
            "year": [str(y) for y in years],
            "month": [JUNE],
            "day": JUNE_DAYS,
            "daily_statistic": stat,
            "time_zone": "utc+00:00",  # keep UTC so days align with ERA5 grid
            "frequency": "1_hourly",
            "area": EUROPE_BBOX,
        }

    jobs = []
    for stat, label in [("daily_maximum", "tx"), ("daily_minimum", "tn")]:
        for year in [EVENT_YEAR, *BASELINE_YEARS]:
            jobs.append(Job(
                name=f"ERA5 {label.upper()} June {year}",
                source="era5",
                target=RAW_DIR / "era5" / f"{label}_{year}-{JUNE}.nc",
                request=request(stat, [year]),
                est_size="~2 MB",
            ))
    return jobs


def city_jobs() -> list[Job]:
    """Open-Meteo requests: two files per city (event month + baseline).

    The archive API only takes a contiguous date range, so the baseline pull
    covers 1991-06-01..2020-06-30 whole; non-June rows are filtered out later
    in DuckDB (03_aggregate.sql) — disk is cheaper than a request per year.
    """
    jobs = []
    for city, (lat, lon) in CITIES.items():
        common = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "UTC",
        }
        jobs.append(Job(
            name=f"Open-Meteo {city} June {EVENT_YEAR}",
            source="cities",
            target=RAW_DIR / "openmeteo" / f"{city}_{EVENT_YEAR}-{JUNE}.json",
            request={**common, "start_date": f"{EVENT_YEAR}-06-01",
                     "end_date": f"{EVENT_YEAR}-06-30"},
            est_size="~3 kB",
        ))
        jobs.append(Job(
            name=f"Open-Meteo {city} 1991-2020 baseline",
            source="cities",
            target=RAW_DIR / "openmeteo" / f"{city}_baseline_1991-2020.json",
            request={**common, "start_date": "1991-06-01",
                     "end_date": "2020-06-30"},
            est_size="~400 kB",
        ))
    return jobs


# --------------------------------------------------------------------------
# Fetchers
# --------------------------------------------------------------------------

def cds_credentials_present() -> bool:
    """True if cdsapi will find credentials (rc file or environment)."""
    rc = Path(os.environ.get("CDSAPI_RC", Path.home() / ".cdsapirc"))
    return rc.exists() or ("CDSAPI_URL" in os.environ and "CDSAPI_KEY" in os.environ)


def fetch_era5(job: Job) -> None:
    """Submit one CDS request and retrieve the result NetCDF."""
    import cdsapi  # deferred: not needed for --dry-run / cities-only runs

    part = job.target.with_suffix(job.target.suffix + ".part")
    client = cdsapi.Client()  # reads ~/.cdsapirc; raises clearly if malformed
    log.info("CDS request submitted for %s (queue may take a while) ...", job.name)
    client.retrieve(CDS_DATASET, job.request, str(part))
    part.replace(job.target)  # only now does the cache consider it complete


def fetch_city(job: Job, session) -> None:
    """Fetch one Open-Meteo daily series and store the raw JSON response."""
    resp = session.get(OPEN_METEO_URL, params=job.request, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if "daily" not in payload:  # API returns 200 + {"error": ...} on bad params
        raise RuntimeError(f"Open-Meteo response missing 'daily': {payload}")

    part = job.target.with_suffix(job.target.suffix + ".part")
    part.write_text(json.dumps(payload), encoding="utf-8")
    part.replace(job.target)


def write_sidecar(job: Job) -> None:
    """Record request params + retrieval date next to each download.

    PLAN.md §8: log provenance at download time. These sidecars are the
    machine-readable half; copy retrieval dates into data/SOURCES.md.
    """
    sidecar = job.target.with_suffix(job.target.suffix + ".meta.json")
    sidecar.write_text(json.dumps({
        "name": job.name,
        "source": job.source,
        "dataset": CDS_DATASET if job.source == "era5" else OPEN_METEO_URL,
        "request": job.request,
        "retrieved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def print_plan(jobs: list[Job]) -> None:
    """Dry-run output: what would be downloaded, what's already cached."""
    width = max(len(j.name) for j in jobs)
    print(f"\nDry run — nothing will be downloaded. Cache root: {RAW_DIR}\n")
    for job in jobs:
        status = "cached  " if job.cached else "MISSING "
        rel = job.target.relative_to(REPO_ROOT)
        print(f"  [{status}] {job.name:<{width}}  {job.est_size:>8}  {rel}")
    missing = [j for j in jobs if not j.cached]
    print(f"\n{len(jobs) - len(missing)} cached, {len(missing)} to download.")
    if any(j.source == "era5" for j in missing):
        print("ERA5 downloads need CDS credentials: "
              + ("found." if cds_credentials_present()
                 else "NOT found — see README for ~/.cdsapirc setup."))


def run(jobs: list[Job], force: bool) -> int:
    """Execute all jobs, skipping cache hits. Returns count of failures."""
    era5_wanted = [j for j in jobs if j.source == "era5" and (force or not j.cached)]
    if era5_wanted and not cds_credentials_present():
        log.error(
            "ERA5 downloads requested but no CDS credentials found.\n"
            "  Create ~/.cdsapirc (see README) or set CDSAPI_URL/CDSAPI_KEY.\n"
            "  To fetch only the keyless Open-Meteo data: --only cities"
        )
        return 1

    session = None
    failures = 0
    for job in jobs:
        if job.cached and not force:
            log.info("cached: %s", job.name)
            continue
        job.target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if job.source == "era5":
                fetch_era5(job)
            else:
                if session is None:
                    import requests
                    session = requests.Session()
                fetch_city(job, session)
                time.sleep(OPEN_METEO_PAUSE_S)
            write_sidecar(job)
            log.info("done: %s -> %s", job.name, job.target.relative_to(REPO_ROOT))
        except Exception:
            # Keep going: one stuck CDS request shouldn't waste the cities run.
            log.exception("FAILED: %s", job.name)
            failures += 1
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="print the download plan and cache status, then exit")
    parser.add_argument("--only", choices=["era5", "cities"],
                        help="restrict to one source")
    parser.add_argument("--force", action="store_true",
                        help="re-download even if a cached file exists")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    jobs = era5_jobs() + city_jobs()
    if args.only:
        jobs = [j for j in jobs if j.source == args.only]

    if args.dry_run:
        print_plan(jobs)
        return 0

    failures = run(jobs, force=args.force)
    if failures:
        log.error("%d download(s) failed — re-run to retry just those.", failures)
        return 1
    log.info("All downloads present. Next: 02_baseline.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
