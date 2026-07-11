#!/usr/bin/env python3
"""Phase 1 sanity check: ERA5 June 2026 TX vs published record figures.

Compares the downloaded ERA5 daily-maximum grid against headline station
records from PLAN.md §1. ERA5 is a ~31 km reanalysis, so a grid cell is
expected to read LOWER than a station record set at a favourable site —
typically by 0-5°C. A check passes if the ERA5 value sits in that band;
a value far below (data problem) or above (unit/time problem) fails.

Record figures are provisional (Met Office verification ongoing, PLAN.md §8)
— this script tests data plausibility, not the records themselves.

Usage: python sanity_check.py   (exit 0 = all checks pass)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import xarray as xr

RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "era5"

# ERA5 grid-cell value vs station record: allow this much shortfall/overshoot.
LOW_TOLERANCE = 5.0   # °C below the record is acceptable (smoothing, siting)
HIGH_TOLERANCE = 1.5  # °C above the record is suspicious (would exceed record)


@dataclass(frozen=True)
class Check:
    name: str
    record_c: float        # published (provisional) record value, °C
    date: str              # date the record was set, YYYY-MM-DD ("" = any June day)
    box: tuple[float, float, float, float]  # lat_min, lat_max, lon_min, lon_max


CHECKS = [
    # Point records: small box around the station (a few grid cells).
    Check("Lingwood, Norfolk UK (prov. UK June record)", 37.7, "2026-06-26",
          (52.3, 52.9, 1.1, 1.8)),
    Check("Pissos, France (national all-time record)", 44.3, "2026-06-23",
          (44.0, 44.6, -1.1, -0.5)),
    # National June records: max anywhere in the country that month.
    Check("Netherlands June record", 39.4, "", (50.8, 53.5, 3.4, 7.2)),
    Check("Switzerland June record", 39.0, "", (45.8, 47.8, 6.0, 10.5)),
    Check("Hungary June record", 40.7, "", (45.7, 48.6, 16.0, 22.9)),
    Check("Austria June record", 40.0, "", (46.4, 49.0, 9.5, 17.2)),
]


def era5_max(ds: xr.Dataset, check: Check) -> float:
    """Max TX (°C) inside the check's box, on its date or across June."""
    lat_min, lat_max, lon_min, lon_max = check.box
    # ERA5 latitude runs north→south, so slice descending.
    sub = ds["t2m"].sel(latitude=slice(lat_max, lat_min),
                        longitude=slice(lon_min, lon_max))
    if check.date:
        sub = sub.sel(valid_time=check.date)
    kelvin = float(sub.max())
    return kelvin - 273.15


def main() -> int:
    tx_file = RAW / "tx_2026-06.nc"
    if not tx_file.exists():
        print(f"Missing {tx_file} — run 01_download.py first.")
        return 1

    ds = xr.open_dataset(tx_file)
    failures = 0
    print(f"{'check':<48} {'record':>7} {'ERA5':>7} {'diff':>6}  verdict")
    for check in CHECKS:
        era5 = era5_max(ds, check)
        diff = era5 - check.record_c
        ok = -LOW_TOLERANCE <= diff <= HIGH_TOLERANCE
        failures += not ok
        when = check.date or "June max"
        print(f"{check.name:<48} {check.record_c:>6.1f}° {era5:>6.1f}° "
              f"{diff:>+5.1f}°  {'OK' if ok else 'FAIL'}  ({when})")

    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
