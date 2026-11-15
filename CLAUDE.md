# Fire Season Check

NASA Space Apps Challenge 2026, challenge "Harmonization of MODIS and VIIRS Hot Spots" (Earth Science / Software).
Solo participant: Sam (PALMVY), virtual Londrina Local Event. Users: firefighters, brigade members, civil defense, land managers, scientists.
**Deadline: Sunday 2026-11-15 23:59 (Local Event time zone, America/Sao_Paulo). Only the last saved submission counts: submit early, resubmit if needed.**
Page freeze (our own rule, not NASA's) has passed: from now on only bug fixes and text, no new features.
Live: https://juniorgcy.github.io/fire-season-check/ (regions: Tocantins by default, `?region=chaco`).

## Rules of the house
- All page text, README and submission texts in **English**. Chat with Sam in Portuguese.
- No backend, no secrets, no external libraries: offline Python pipeline -> static JSON in `docs/data/` -> static page in `docs/` (GitHub Pages, branch main, folder /docs).
- **SI (Super Intelligence) wording must be the same everywhere** (page footer + `<meta name="ai-disclosure">`, README, `docs/data/ABOUT.txt`, `src/fogo/__init__.py`, form, demo). Canonical sentence: "Built with the help of Claude (Anthropic), an AI assistant. The author chose the challenge, chose the approach among the options the assistant listed, chose the users, the regions and how results are shown, and downloaded the NASA FIRMS data. The assistant wrote the code, tests and texts and ran the data checks; the author reviewed the results and decides what is published." Facts behind it (Sam, 2026-11-15): Sam asked the AI for a summary of the challenges and for what keeps the satellites from lining up; the AI listed options and their effects; Sam chose one, decided Tocantins first and other regions in the plan, downloaded the data and chose the presentation. Possible tension with the NASA rule below: Sam should confirm with the Local Lead; never soften the facts. Never claim the AI did not help. NASA rules: SI must not be used to come up with the idea of how to solve the challenge, and must be acknowledged in descriptive text and metadata of code and data (judges see those, not only the form).
- No work on the challenge before the hackathon start (2026-11-14 09:00 America/Sao_Paulo). Earlier exploratory studies exist: the README must say exactly what was and was not reused. Check `git log` and keep the statement true.
- Never invent numbers. Every figure on the page comes from the real FIRMS data. Regenerate JSON with the build command, never edit it by hand.
- UI states are mandatory: loading, error (with retry), empty, ready. Accessible colors, keyboard use, text alternatives.
- Tests first for pipeline changes (`python -m pytest -q`, currently 80 passing). Reference result that must not change by accident: **Tocantins -41% vs the 10-year average through 2026-11-01, rank 11 of 11, median weekly error 9.2%, p90 38.9%**. The same numbers must appear everywhere (page, README, form, demo).
- Keep this file free of private notes (immigration, personal plans): the repository is public.

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
Real CSVs live on Sam's PC (`Downloads\Dados\...`), not in the repo (`*.csv` is git-ignored).

## Layout
- `src/fogo/load.py` read FIRMS CSVs (type 0 only, archive + NRT without double counting), box `TOCANTINS`.
- `weekly.py` weekly series (ISO weeks, Monday start). `calibrate.py` single/monthly ratio + out-of-sample validation.
- `series.py` harmonized series (MODIS before VIIRS start 2012-01-20, VIIRS x ratio after). `indicators.py` normal = mean of previous 10 complete ISO years, headline, rank.
- `export.py` page JSON. `grid.py` 0.25 degree cells x weeks per sensor (sparse JSON). `points.py` every detection, one binary file per year. `geo.py` state border + town names (IBGE). `schedule.py` day/night shares and ratios. `cli.py` orchestration (`build`, `geo`). Data end = VIIRS last day.
- `docs/index.html` headline + chart + trust card. `docs/explorer.js` explorer: map rectangle or lat/lon, date range, year x week and year x month calendars, anomalies vs mean and median, CSVs (weekly, monthly, cell, individual hotspots), PNG downloads. `docs/data/regions.json` lists the regions.

## Ratio direction (say it explicitly in text)
The factor (about 0.25 in Tocantins, 0.31 in the Argentine Chaco) is **multiplied by VIIRS counts to put them on the MODIS scale**. VIIRS 375 m detects MORE fires than MODIS; the factor is below 1 for that reason. Always write it as "MODIS-equivalent = VIIRS x factor" or "MODIS/VIIRS", never as a bare "VIIRS/MODIS 0.25".

## Known limits (state them, do not hide them)
- Two validated regions: Tocantins (read box lat -13.5..-5.1, lon -50.8..-45.6; the grid rounds to -5.0 / -45.55) and the Argentine Chaco (box -28.5..-23.5, -64.5..-58.5; ratio 0.308, error 9.3% / p90 33.2%, 2026 -61% mean / -51% median, rank 11/11). Outside the loaded boxes the page refuses input. The pipeline takes any box (`--bbox`), but two regions are evidence, not proof: **never claim "any region of the planet"**. Wording to use: "any area and dates inside two validated regions; the pipeline re-validates any FIRMS box".
- Paraná Delta was built as a stress test and NOT published (error 23.3% / p90 53.3%, 156 weeks). Publishing it would need a median-first headline and a low-confidence warning.
- Data source is NASA FIRMS only. **No CONAE data is used**; do not imply otherwise.
- Data end 2026-11-02 (VIIRS last day); latest ~150 days are near-real-time and provisional. Say "data through <date>, newest weeks provisional", not "up to today".
- Calibration was fitted at region scale: small areas have larger error (page warns under 12 cells). VIIRS S-NPP misses the MODIS 10:30 overpass; ratios can drift; counts are detections, not burned area.
- Calendar cells are ~28 km: the 375 m VIIRS detail shows only in the individual-hotspots CSV (coordinates rounded to ~100 m, max 1.5M rows).
- One ratio per month for day and night together; measured day 0.27 vs night 0.19. A day/night ruler is future work. Only VIIRS S-NPP is used (not NOAA-20/21).
- "Detected hotspots" are satellite detections, not confirmed fires. No real brigade or civil-defense team has validated the product yet: say so, unless a real quote is obtained.
- No published benchmark exists for our regional/monthly/day-night ratios (literature supports the mechanisms, not the numbers). Claim novelty only as "among the tools we reviewed", never "first" or "only".

## Submission rules (from the official guides)
- Judging: five criteria scored 1-5, no published weights: Impact, Creativity, Validity, Relevance, Presentation (pay equal attention to Presentation).
- Demo: video <= 30 seconds OR <= 7 slides including the title. Over the limit = not eligible for Global Judging. Public link, in English (subtitles in English if not spoken).
- Form: every field required, plus both checkboxes. List ALL external resources (code, text, images) in References: FIRMS, IBGE, Python, pandas, NumPy, pytest and any others used.
- Request FortiGuard classification of the live site now (turnaround is outside our control). Confirm the exact deadline with the Local Lead.
- Use for scoring: Validity = out-of-sample error and honest limits; Creativity = "no single MODIS/VIIRS factor" (changes by month, day/night, region); Impact/Relevance = firefighters and civil defense as users.

## Still to do (priority order, deadline 23:59)
1. Commit and push the current work (CLAUDE.md, README, explorer.js, index.html, regions.json, `docs/data/chaco/`), then check the live page for both regions, phone and desktop.
2. Fix the page footer SI sentence to match the README; add an SI note in code/data metadata (file header or meta tag).
3. Check `git log` for commits before 2026-11-14 09:00 and make the README "earlier work" statement exactly true.
4. Write the ratio-direction sentence on the page and README (see above).
5. English submission texts (short/long description, references, SI declaration), consistent with the numbers above.
6. Demo (<= 30 s or <= 7 slides), public link; 3 outside testers if time allows.
7. Submit early (target before 20:00), keep the receipt, resubmit only if needed.
