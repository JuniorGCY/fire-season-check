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
- Tests first for pipeline changes (`python -m pytest -q`, currently 44 passing). Reference result that must not change by accident: **-41% vs the 10-year average through 2026-11-01, rank 11 of 11, median weekly error 9.2%, p90 38.9%**.

## Build
```
PYTHONPATH=src python -m fogo.cli build \
  --modis <fire_archive_M-C61_*.csv> <fire_nrt_M-C61_*.csv> \
  --viirs <fire_archive_SV-C2_*.csv> <fire_nrt_SV-C2_*.csv> \
  --out docs/data/tocantins.json --grid-out docs/data/grid.json
```
Real CSVs live on Sam's PC (`Downloads\Dados\new\...`), not in the repo (`*.csv` is git-ignored).

## Layout
- `src/fogo/load.py` read FIRMS CSVs (type 0 only, archive + NRT without double counting), bounding box `TOCANTINS`.
- `weekly.py` weekly series (ISO weeks, Monday start). `calibrate.py` single/monthly ratio + out-of-sample validation.
- `series.py` harmonized series (MODIS before VIIRS start 2012-01-20, VIIRS x ratio after). `indicators.py` normal = mean of previous 10 complete ISO years, headline, rank.
- `export.py` page JSON. `grid.py` 0.25 degree cells x weeks per sensor (sparse JSON). `cli.py` orchestration. Data end = min of both sensors' last day.
- `docs/index.html` headline + chart + trust card. `docs/explorer.js` area/date explorer: map rectangle or lat/lon, date range, year x week calendar, anomalies vs normal, CSVs.

## Known limits (state them, do not hide them)
- Covers only the Tocantins box (lat -13.5..-5.0, lon -50.8..-45.55), not "any region of the planet".
- Calibration was fitted at state scale; small areas have larger error (page warns under 12 cells).
- CSV exports are counts per week and per 28 km cell, not single detections.
- Latest ~150 days are near-real-time data and provisional.

## Still to do (priority order)
1. Individual hotspot points in the CSV for the selected area (statement says "detected hotspots").
2. State outline and place names on the map.
3. Optional second region (Argentina, CONAE) if time allows.
4. English submission texts (short/long description, references, SI declaration), README live link.
5. Demo (<=30 s video or 7 slides) only AFTER the freeze; test with 3 outsiders; FortiGuard check; submit before 23:59 and keep the receipt.

## NIW evidence to keep
Commit history, screenshots of the live page, public link, tester quotes, submission receipt, any usage numbers.
