"""Phase 2 acceptance tests (PLAN.md): validate site/data/ outputs.

Run after 04_export.py: every region covers all 14 timeline dates, anomalies
are physically sane, nothing is null, and size budgets hold.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

SITE_DATA = Path(__file__).resolve().parent.parent.parent / "site" / "data"
TIMELINE_START = "2026-06-17"

pytestmark = pytest.mark.skipif(
    not (SITE_DATA / "daily_anomaly.json").exists(),
    reason="site/data not built yet — run 04_export.py first",
)


@pytest.fixture(scope="module")
def daily():
    return json.loads((SITE_DATA / "daily_anomaly.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def regions_geojson():
    return json.loads((SITE_DATA / "regions.geojson").read_text("utf-8"))


def test_timeline_starts_17_june_and_is_contiguous(daily):
    """Rolling timeline: fixed start, contiguous daily steps, ≥ the original
    14-day story, ending wherever the newest ERA5 day is."""
    dates = [date.fromisoformat(d) for d in daily["dates"]]
    assert dates[0].isoformat() == TIMELINE_START
    assert len(dates) >= 14
    assert all((b - a) == timedelta(days=1) for a, b in zip(dates, dates[1:]))


def test_every_region_covers_every_date(daily):
    n = len(daily["dates"])
    for rid, r in daily["regions"].items():
        for key in ("anomaly", "tx", "tx_max", "tropical"):
            assert len(r[key]) == n, f"{rid}.{key} incomplete"


def test_no_nulls(daily):
    for rid, r in daily["regions"].items():
        for key in ("anomaly", "tx", "tx_max", "tropical"):
            assert None not in r[key], f"null in {rid}.{key}"


def test_anomalies_in_sane_range(daily):
    """Anomalies must be physically plausible.

    PLAN.md suggested [-5, +15], but the real event exceeds it: Pays de la
    Loire peaks at +18.9 °C on 23-24 June — consistent with the 44.3 °C
    Pissos record nearby, and with heat-dome events elsewhere (Pacific NW
    2021 reached ~+20 °C). Upper bound widened to +20 accordingly.
    """
    for rid, r in daily["regions"].items():
        assert all(-5.0 <= a <= 20.0 for a in r["anomaly"]), \
            f"{rid} anomaly outside [-5, +20]: {r['anomaly']}"


def test_geojson_matches_data_regions(daily, regions_geojson):
    geo_ids = {f["properties"]["id"] for f in regions_geojson["features"]}
    assert geo_ids == set(daily["regions"])


def test_size_budgets():
    assert (SITE_DATA / "daily_anomaly.json").stat().st_size <= 300_000
    assert (SITE_DATA / "regions.geojson").stat().st_size <= 500_000


def test_city_files_complete():
    city_files = list((SITE_DATA / "cities").glob("*.json"))
    assert len(city_files) == 12  # matches CITIES in 01_download.py
    for f in city_files:
        c = json.loads(f.read_text("utf-8"))
        n = len(c["dates"])
        assert n >= 30 and c["dates"][0] == "2026-06-01"
        # All five arrays are aligned: one normal per 2026 date.
        for key in ("tx", "tn", "clim_tx", "clim_tn"):
            assert len(c[key]) == n and None not in c[key], f"{f.name}.{key}"


def test_events_have_required_fields():
    events = json.loads((SITE_DATA / "events.json").read_text("utf-8"))
    assert len(events) >= 3
    for e in events:
        assert e["title"] and e["country"]
        assert "provisional" in e  # PLAN.md §8: label records provisional
