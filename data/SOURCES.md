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
  June 2026 → rolling latest day + 1991–2020 baselines per covered month.
- **URL:** https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics
- **Retrieved:** 2026-07-10 (June), 2026-07-11/12 (July + baselines); exact
  per-file timestamps in `data/raw/era5/*.meta.json` sidecars. Current month
  re-retrieved on every refresh run.
- **Licence:** Copernicus Licence (free use with attribution).
- **Required credit (verbatim):**
  > Contains modified Copernicus Climate Change Service information [2026]. Neither the
  > European Commission nor ECMWF is responsible for any use of this information.

## Open-Meteo Historical Weather API

- **What:** Daily Tmax/Tmin series for the city detail panel, June 2026 onwards
  + 1991–2020 whole-year climatology pulls (`*_all.json`).
- **URL:** https://open-meteo.com/en/docs/historical-weather-api
- **Retrieved:** 2026-07-10 through 2026-07-12; sidecars per file.
- **Licence:** CC BY 4.0, free for non-commercial use, no API key.
- **Required credit (verbatim):**
  > Weather data by Open-Meteo.com

## NUTS region boundaries (Eurostat/GISCO)

- **What:** NUTS-1 GeoJSON boundaries (2021 edition, 1:20M — last edition
  including the UK), simplified further for the web.
- **URL:** https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics
- **Retrieved:** 2026-07-12 (see `data/raw/nuts/*.meta.json`).
- **Licence:** © EuroGeographics for the administrative boundaries; attribution required.
- **Required credit (verbatim):**
  > © EuroGeographics for the administrative boundaries

## Event markers & analysis sources (verified 2026-07-12)

- **Met Office** — June 2026 heatwave record recap (37.7°C Lingwood 26 Jun,
  provisional; Wales 35.9°C & UK night record 23.5°C Cardiff 25 Jun; 150+
  station records; red warning on a record third consecutive day). © Crown
  copyright, OGL v3.
  https://www.metoffice.gov.uk/blog/2026/june-2026-heatwave-a-recap-of-the-temperature-records
  https://www.metoffice.gov.uk/about-us/news-and-media/media-centre/weather-and-climate-news/2026/met-office-issues-red-warning-for-extreme-heat-for-record-third-consecutive-day
- **UKHSA / GOV.UK** — red heat-health alerts, six English regions, 24–25 Jun
  (extended). OGL v3.
  https://www.gov.uk/government/news/ukhsa-issues-red-heat-health-alerts-across-england
- **Météo-France (via ITV/Bloomberg)** — France's hottest day since 1947:
  44.3°C Pissos, 23 Jun; Paris June record 40.9°C.
  https://www.itv.com/news/2026-06-23/dozens-dead-in-france-as-heat-dome-brings-40c-temperatures-to-europe
- **Euronews / Copernicus** — June 2026 records across Europe; DE/CZ/PL/HU
  hottest days on record within ~24h, 27–28 Jun.
  https://www.euronews.com/my-europe/2026/07/09/june-2026-broke-heat-records-across-europe-and-oceans-eu-climate-data-reveals
- **WMO** — NL June record 39.4°C; CH June record 39.0°C (Basel).
  https://wmo.int/media/news/record-breaking-heat-spreads-through-europe
- **World Weather Attribution** — rapid study: most severe heatwave recorded
  over the region; intensity vs 1976 "virtually impossible" without climate
  change. https://www.worldweatherattribution.org/
- **Excess mortality** — ~2,700 estimated excess deaths, UK May+June
  heatwaves (PA-reported study, early July 2026).
  https://ca.news.yahoo.com/heatwaves-caused-estimated-2-700-065520920.html
- **Al Jazeera / Met Office** — England's warmest June on record; UK
  second-warmest.
  https://www.aljazeera.com/news/2026/7/1/warmest-june-on-record-for-england-second-warmest-for-uk-says-met-office
