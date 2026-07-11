# Anatomy of a Heatwave — June 2026

Interactive map + timeline of the 17–30 June 2026 UK/European heatwave. Daily maximum
temperature anomalies vs the 1991–2020 June baseline, aggregated to NUTS regions by an
offline Python/DuckDB pipeline and served as a static site on GitHub Pages.

See [PLAN.md](PLAN.md) for the full project brief and build phases.

## Layout

```
pipeline/   Offline data pipeline (Python + DuckDB SQL). Run once; outputs go to site/data/.
data/       raw/ downloads (gitignored, cached) and SOURCES.md licence log.
site/       Static frontend — the GitHub Pages root. Never touches raw data.
```

## Pipeline quick start

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate   # or `.venv\Scripts\activate` on Windows
pip install -e .

# Preview what would be downloaded — no credentials needed:
python 01_download.py --dry-run

# Real run (ERA5 pulls need ~/.cdsapirc — see below):
python 01_download.py
```

ERA5 downloads require a free [Copernicus CDS](https://cds.climate.copernicus.eu) account.
After registering, put your key in `~/.cdsapirc`:

```
url: https://cds.climate.copernicus.eu/api
key: <your-personal-access-token>
```

Open-Meteo city series need no key. All downloads are cached in `data/raw/`; re-running
skips anything already present (use `--force` to re-download).

## One-time GitHub setup (run these yourself)

From this directory, with the [gh CLI](https://cli.github.com) logged in:

```bash
git init -b main
git add -A
git commit -m "Phase 0: scaffold + Pages deploy workflow"
gh repo create heatwave-2026 --public --source=. --push

# Enable Pages with GitHub Actions as the source:
gh api repos/{owner}/heatwave-2026/pages -X POST -f build_type=workflow
```

The `deploy.yml` workflow then publishes `site/` on every push to `main`. The placeholder
page appears at `https://<your-username>.github.io/heatwave-2026/` within a minute or two
of the first successful run (check the Actions tab). If the `gh api` call complains that
Pages already exists, just set **Settings → Pages → Source → GitHub Actions** in the web UI.

## Attribution

Data source licences and required credit lines are tracked in
[data/SOURCES.md](data/SOURCES.md) and will be rendered at `site/attributions.html`.
