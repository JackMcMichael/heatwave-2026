# Data sources, licences, and required attribution

Log every source here **at download time** (PLAN.md §8: copy exact licence wording to guard
against drift). Template:

## <Source name>

- **What:** <variables / files>
- **URL:** <dataset landing page>
- **Retrieved:** <YYYY-MM-DD>
- **Licence:** <name + link>
- **Required credit (verbatim):**
  > <exact attribution text copied from the provider>

---

## ERA5 post-processed daily statistics (Copernicus CDS)

- **What:** Daily maximum and minimum 2 m temperature, Europe bbox (35–62°N, 11°W–25°E),
  June 2026 + June 1991–2020 baseline.
- **URL:** https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics
- **Retrieved:** _pending — fill in when 01_download.py runs for real_
- **Licence:** Copernicus Licence (free use with attribution).
- **Required credit (verbatim):**
  > Contains modified Copernicus Climate Change Service information [2026]. Neither the
  > European Commission nor ECMWF is responsible for any use of this information.

## Open-Meteo Historical Weather API

- **What:** Daily Tmax/Tmin series for the city detail panel, June 2026 + climatology window.
- **URL:** https://open-meteo.com/en/docs/historical-weather-api
- **Retrieved:** _pending_
- **Licence:** CC BY 4.0, free for non-commercial use, no API key.
- **Required credit (verbatim):**
  > Weather data by Open-Meteo.com

## NUTS region boundaries (Eurostat/GISCO) — Phase 2

- **What:** NUTS-1/NUTS-2 GeoJSON boundaries for aggregation regions.
- **URL:** https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics
- **Retrieved:** _pending_
- **Licence:** © EuroGeographics for the administrative boundaries; attribution required.
- **Required credit (verbatim):**
  > © EuroGeographics for the administrative boundaries
