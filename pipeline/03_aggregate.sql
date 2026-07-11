-- 03_aggregate.sql — every aggregation in the pipeline lives here (DuckDB).
-- Executed by 04_export.py with the repo root as working directory.
-- Inputs:  data/interim/era5/{tx,tn}/*.parquet   (from 02_baseline.py)
--          data/interim/cell_region.parquet       (from 02_baseline.py)
--          data/raw/openmeteo/*.json              (from 01_download.py)
-- Outputs: in-memory tables region_daily, city_daily, city_clim,
--          which 04_export.py serialises to site/data/.

-- ---------------------------------------------------------------------------
-- Raw ERA5 scans. One row per (day, grid cell), temperature in °C.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW tx_raw AS
SELECT date, lat, lon, temp_c
FROM read_parquet('data/interim/era5/tx/*.parquet');

CREATE OR REPLACE VIEW tn_raw AS
SELECT date, lat, lon, temp_c
FROM read_parquet('data/interim/era5/tn/*.parquet');

-- ---------------------------------------------------------------------------
-- 1991-2020 June climatology per grid cell: the "normal" June daily max
-- that 2026 anomalies are measured against.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE climatology AS
SELECT lat, lon, avg(temp_c) AS clim_tx
FROM tx_raw
WHERE year(date) BETWEEN 1991 AND 2020
GROUP BY lat, lon;

CREATE OR REPLACE TABLE cell_region AS
SELECT * FROM read_parquet('data/interim/cell_region.parquet');

-- ---------------------------------------------------------------------------
-- Daily per-region stats for June 2026: the map's data.
-- Cell→region assignment comes from 02_baseline.py; anomalies are computed
-- per cell first (against that cell's own climatology), then averaged, so
-- mountainous regions aren't skewed by mixing warm and cold cells.
-- tropical_pct = share of the region's cells with a night min ≥ 20 °C.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE region_daily AS
SELECT
    cr.region_id,
    any_value(cr.region_name)                                    AS region_name,
    any_value(cr.country)                                        AS country,
    tx.date,
    round(avg(tx.temp_c - c.clim_tx), 1)                         AS anomaly_c,
    round(avg(tx.temp_c), 1)                                     AS tx_mean_c,
    -- max() preserves float32, whose values (e.g. 42.6) aren't exactly
    -- representable and would serialise as 42.599998…; cast first.
    round(max(tx.temp_c)::DOUBLE, 1)                             AS tx_max_c,
    round(100.0 * count(*) FILTER (WHERE tn.temp_c >= 20.0)
                / count(*), 0)                                   AS tropical_pct
FROM tx_raw tx
JOIN tn_raw       tn USING (date, lat, lon)
JOIN climatology  c  USING (lat, lon)
JOIN cell_region  cr USING (lat, lon)
WHERE year(tx.date) = 2026
GROUP BY cr.region_id, tx.date;

-- ---------------------------------------------------------------------------
-- City detail-panel series. Open-Meteo responses hold parallel arrays under
-- `daily`; multiple unnest() calls in one SELECT zip them positionally.
-- City name is recovered from the cached filename ({city}_2026-06.json).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE city_daily AS
SELECT
    split_part(parse_filename(filename, true), '_', 1)  AS city,
    unnest(daily.time)::DATE                             AS date,
    unnest(daily.temperature_2m_max)::DOUBLE             AS tx,
    unnest(daily.temperature_2m_min)::DOUBLE             AS tn
FROM read_json_auto('data/raw/openmeteo/*_2026-06.json', filename = true);

-- Per-city June climatology by day of month (1991-2020). The baseline files
-- span whole years (the archive API only takes contiguous ranges), so the
-- June filter happens here — disk was cheaper than 30 requests per city.
CREATE OR REPLACE TABLE city_clim AS
WITH baseline AS (
    SELECT
        split_part(parse_filename(filename, true), '_', 1)  AS city,
        unnest(daily.time)::DATE                             AS date,
        unnest(daily.temperature_2m_max)::DOUBLE             AS tx,
        unnest(daily.temperature_2m_min)::DOUBLE             AS tn
    FROM read_json_auto('data/raw/openmeteo/*_baseline_*.json', filename = true)
)
SELECT
    city,
    day(date)          AS day,
    round(avg(tx), 1)  AS clim_tx,
    round(avg(tn), 1)  AS clim_tn
FROM baseline
WHERE month(date) = 6
GROUP BY city, day(date);
