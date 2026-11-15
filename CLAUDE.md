# Fire Season Check · Tocantins

NASA Space Apps Challenge 2026, challenge #8 "Harmonization of MODIS and VIIRS Hot Spots".
Solo participant: Sam (PALMVY), Londrina virtual local event. Users: firefighters, brigade members, civil defense.
**Deadline: Sunday 2026-11-15 23:59 (UTC-3). Page freeze: Sunday 12:00.** Live: https://juniorgcy.github.io/fire-season-check/

## Rules of the house
- All page text, README and submission texts in **English**. Chat with Sam in Portuguese.
- No backend, no secrets, no external libraries: offline Python pipeline -> static JSON in `docs/data/` -> static page in `docs/` (GitHub Pages, branch main, folder /docs).
- Keep the Super Intelligence (SI) disclosure honest: Sam chose the challenge, region, users and story; the method was developed with Claude. Never claim the AI did not help.
- Never invent numbers. Every figure on the page comes from the real FIRMS data. Regenerate JSON with the command below, do not edit it by hand.
- UI states are mandatory: loading, error (with retry), empty, ready. Accessible colors, keyboard use, text alternatives.
- Tests first for pipeline changes (`python -m pytest -q`, currently 80 passing). Reference result that must not change by accident: **-41% vs the 10-year average through 2026-11-01, rank 11 of 11, median weekly error 9.2%, p90 38.9%**.

## Build
```
PYTHONPATH=src python -m fogo.cli build \
  --modis <fire_archive_M-C61_*.csv> <fire_nrt_M-C61_*.csv> \
  --viirs <fire_archive_SV-C2_*.csv> <fire_nrt_SV-C2_*.csv> \
  --out docs/data/tocantins.json --grid-out docs/data/grid.json --points-out docs/data/points
```
Other region: add `--region "Name" --bbox SOUTH NORTH WEST EAST` (same box as the FIRMS download). Border and towns: `python -m fogo.cli geo ...` (see README).
Windows: `python` is the Store alias, use `py -3`. Do not use `%-d` in strftime (breaks on Windows).
Regenerating `docs/data/points/` (44 MB) bloats git history: only when the format or the data really change.
Real CSVs live on Sam's PC (`Downloads\Dados\new\...`), not in the repo (`*.csv` is git-ignored).

## Layout
- `src/fogo/load.py` read FIRMS CSVs (type 0 only, archive + NRT without double counting), bounding box `TOCANTINS`.
- `weekly.py` weekly series (ISO weeks, Monday start). `calibrate.py` single/monthly ratio + out-of-sample validation.
- `series.py` harmonized series (MODIS before VIIRS start 2012-01-20, VIIRS x ratio after). `indicators.py` normal = mean of previous 10 complete ISO years, headline, rank.
- `export.py` page JSON. `grid.py` 0.25 degree cells x weeks per sensor (sparse JSON). `points.py` every detection, one binary file per year (`docs/data/points/`). `geo.py` state border + town names from IBGE (`docs/data/geo.json`). `schedule.py` day/night shares and ratios. `cli.py` orchestration (`build`, `geo`). Data end = VIIRS last day (series continues when MODIS stops).
- `docs/index.html` headline + chart + trust card. `docs/explorer.js` area/date explorer: map rectangle or lat/lon, date range, year x week calendar, anomalies vs normal, CSVs.

## Known limits (state them, do not hide them)
- The page covers only the Tocantins box. Read box `TOCANTINS` is lat -13.5..-5.1, lon -50.8..-45.6; the grid rounds up to -5.0 / -45.55 (so the page preset says -5.0). Both are right. The pipeline takes any box (`--bbox`) but only Tocantins is validated: never claim "any region of the planet".
- Calibration was fitted at state scale; small areas have larger error (page warns under 12 cells).
- Weekly and cell CSVs are counts; the individual-hotspots CSV has detections (coordinates rounded to ~100 m, max 1.5M rows).
- Latest ~150 days are near-real-time data and provisional.
- One ratio per month for day and night passes together; measured day ratio 0.27 vs night 0.19 (shown on the page, a day/night ruler is future work).
- Only VIIRS S-NPP is used (not NOAA-20/21); the headline uses the mean (state plan yardstick), the median is shown next to it (-41.4%).

## Still to do (priority order)
Done: individual points CSV, state border + town names, region parameter (`--bbox`), README live link, median (headline, weeks, months, area), monthly calendar + latest month vs median, PNG downloads, monthly CSV, continuity (data end = VIIRS), day/night diagnostic. Checked phone width (375 px) and light theme locally. 80 tests.
1. Commit and push, then check the live page.
2. Optional second region (Argentina, CONAE): needs its CSVs and its own out-of-sample validation before it appears on the page.
3. English submission texts (short/long description, references, SI declaration).
4. Demo (<=30 s video or 7 slides) only AFTER the freeze; test with 3 outsiders; FortiGuard check; submit before 23:59 and keep the receipt.

## NIW evidence to keep
Commit history, screenshots of the live page, public link, tester quotes, submission receipt, any usage numbers.
