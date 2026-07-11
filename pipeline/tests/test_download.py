"""Smoke tests for 01_download.py job definitions (no network required)."""

import importlib.util
import sys
from pathlib import Path

# 01_download.py has a numeric prefix, so import it by path.
_SPEC = importlib.util.spec_from_file_location(
    "download", Path(__file__).parent.parent / "01_download.py")
download = importlib.util.module_from_spec(_SPEC)
sys.modules["download"] = download
_SPEC.loader.exec_module(download)


def all_jobs():
    return download.era5_jobs() + download.city_jobs()


def test_targets_unique_and_under_raw_dir():
    targets = [j.target for j in all_jobs()]
    assert len(targets) == len(set(targets)), "duplicate cache filenames"
    assert all(download.RAW_DIR in t.parents for t in targets)


def test_bbox_is_valid_cds_order():
    north, west, south, east = download.EUROPE_BBOX
    assert north > south and east > west


def test_era5_requests_cover_event_and_baseline():
    jobs = download.era5_jobs()
    # {TX, TN} x {2026 + each baseline year}; one year per request because
    # the dataset's per-request cost cap rejects multi-year pulls.
    assert len(jobs) == 2 * (1 + len(download.BASELINE_YEARS))
    assert all(len(j.request["year"]) == 1 for j in jobs)
    years = {yr for j in jobs for yr in j.request["year"]}
    assert {"2026", "1991", "2020"} <= years
    assert all(j.request["month"] == ["06"] for j in jobs)
    assert all(len(j.request["day"]) == 30 for j in jobs)


def test_every_city_has_event_and_baseline_job():
    jobs = download.city_jobs()
    assert len(jobs) == 2 * len(download.CITIES)


def test_dry_run_exits_cleanly(capsys):
    assert download.main(["--dry-run"]) == 0
    assert "Dry run" in capsys.readouterr().out
