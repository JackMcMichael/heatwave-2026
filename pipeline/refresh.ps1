# refresh.ps1 — extend the rolling timeline to the newest available ERA5 day.
# Run from the pipeline/ folder with the venv active. The only slow part is
# the CDS queue; everything already cached is skipped automatically.
#
#   .\refresh.ps1
#
# Then commit & push: GitHub Pages redeploys the site with the longer timeline.

$ErrorActionPreference = "Stop"

python 01_download.py     # new days + any missing monthly baselines
python 02_baseline.py     # convert new/refreshed NetCDF, mapping is cached
python 04_export.py       # re-aggregate (03_aggregate.sql) and export JSON
python -m pytest tests -q # acceptance checks

Write-Host "`nDone. Review 'git status', then commit and push to deploy."
