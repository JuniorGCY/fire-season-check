# Fire Season Check: Tocantins

**NASA Space Apps Challenge 2026 · Challenge: "Harmonization of MODIS and VIIRS Hot Spots"**

A one-page answer to the question a fire manager already asks: **is this fire season above or
below normal?** It combines two NASA satellite records (MODIS since 2000, VIIRS since 2012) into one
weekly series with a measured error, and compares the current year with the previous ten.

- Live page: https://juniorgcy.github.io/fire-season-check/ (GitHub Pages, folder `docs/`).
- Region: Tocantins, Brazil. Intended users: firefighters, brigades and municipal civil defence.

## What it says today

Through November 1, 2026, Tocantins had **41% fewer hotspots** than the average of the previous
10 years (2016 to 2025), the lowest of the 11 years for the same weeks. Four other ways of
calculating it (MODIS alone, VIIRS alone, fire power instead of counts, one ratio for the whole year)
give between **-38% and -43%**. Depending on the method, 2026 is the lowest or the second lowest year.
The last weeks are provisional (near-real-time data is replaced by final data after about 5 months).

## How it works

1. **Read** NASA FIRMS CSVs for a bounding box around Tocantins, keep vegetation fires (`type` 0),
   merge archive and near-real-time files without double counting, and aggregate by ISO week.
2. **Common ruler.** MODIS sees fewer, larger pixels than VIIRS (about 1 km² vs 0.14 km²), so raw counts
   are not comparable. In the weeks where both exist (2012 to 2026) we scale VIIRS to the MODIS ruler.
   Before January 2012 only MODIS is used.
3. **Measure the error.** Fit the ratio on some years, score it on the years it never saw, and repeat
   the other way round. Only fire-season weeks (June to November) with at least 20 MODIS hotspots count.
4. **Compare with normal.** Normal = mean of the previous 10 complete years for the same weeks, the same
   yardstick the state fire plan of Tocantins uses. The comparison is cumulative (year to date).

### Validation (real data, weekly relative error, out of sample)

| Fit | Quantity | Median error | 90th percentile | Direction |
|---|---|---|---|---|
| **One ratio per calendar month** | **hotspot count** | **9.7%** | 38.9% | fit 2012-18, test 2019-26 |
| **One ratio per calendar month** | **hotspot count** | **8.7%** | 28.9% | fit 2019-26, test 2012-18 |
| One ratio for the whole year | hotspot count | 15.1% | 40.7% | fit 2012-18, test 2019-26 |
| One ratio for the whole year | hotspot count | 14.1% | 34.6% | fit 2019-26, test 2012-18 |
| One ratio per calendar month | fire radiative power | 11.4% | 54.8% | fit 2012-18, test 2019-26 |
| One ratio per calendar month | fire radiative power | 13.1% | 45.9% | fit 2019-26, test 2012-18 |
| One ratio for the whole year | fire radiative power | 17.9% | 57.3% | fit 2012-18, test 2019-26 |
| One ratio for the whole year | fire radiative power | 11.9% | 57.8% | fit 2019-26, test 2012-18 |

What we learned: the MODIS/VIIRS count ratio **is not constant**. It is about 0.21 in October and 0.33
in June (whole-year ratio: 0.246), so a monthly ratio cuts the error by about a third. Fire radiative
power agrees between the sensors much better on average (ratio about 1.04), as expected, because power
does not depend on pixel size the way counts do. The headline uses the monthly count ratio.

## Explore an area and a period

Below the headline, the page lets a user pick a rectangle on the map (or type latitude and longitude) and a date
range. It then shows the weekly series, a year-by-week calendar, the difference from the 10-year normal, and three
CSV downloads, all computed in the browser from static files:

| Download | What it holds |
|---|---|
| Weekly series | counts per week for the area: MODIS, VIIRS and the harmonized value |
| By 28 km cell | counts per week and per 0.25 degree cell |
| **Individual hotspots** | every detection in the area and dates: date, time (UTC), latitude, longitude, sensor, fire radiative power (MW), `harmonized_weight`, `provisional` |

`harmonized_weight` is 1 for MODIS before VIIRS starts (2012-01-20) and the monthly MODIS/VIIRS ratio for VIIRS after
it, so the sum of the column equals the harmonized count shown on the page (checked on 2026: 124,997 detections,
weights sum to 25,353, the same total as the page summary). A single CSV is limited to 1.5 million rows.

The map shows the state border and 15 municipality names from IBGE open data. Names sit at the centre of each
municipality, which is close to the town but not exact.

## Limits (also shown on the page)

- Cloud and smoke can hide fire. A hotspot is a satellite pixel, not one fire and not a burned area.
- Fire radiative power is an intensity proxy. Small or cool fires can be missed.
- The region is a bounding box (lat -13.5 to -5.1, lon -50.8 to -45.6) that also covers slivers of
  neighbouring states. The border is drawn for reference only: areas are still chosen as rectangles of 28 km cells,
  and picking a municipality is future work.
- Calibration was fitted for the whole state, so small areas (under 12 cells) have a larger error; the page warns.
- Individual coordinates are rounded to about 100 m. The weekly and cell CSVs are counts, the individual CSV is
  detections.
- The page covers only the Tocantins box. The pipeline accepts any FIRMS box (`--bbox`, see "Another region"), but no
  region other than Tocantins has been validated, so we do not claim "any region of the planet".
- Near-real-time data has no `type` column, so static sources are not filtered in the last months.
- Only weekly values were validated (table above), so single days are not shown.
- Not an official warning system.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q                      # 72 tests
PYTHONPATH=src python -m fogo.cli build \
  --modis path/to/fire_archive_M-C61_*.csv path/to/fire_nrt_M-C61_*.csv \
  --viirs path/to/fire_archive_SV-C2_*.csv path/to/fire_nrt_SV-C2_*.csv \
  --out docs/data/tocantins.json --grid-out docs/data/grid.json --points-out docs/data/points
cd docs && python -m http.server 8765    # open http://localhost:8765
```

### Another region

The pipeline is not tied to Tocantins. Download MODIS and VIIRS CSVs from FIRMS for any box, then give the same box:

```bash
PYTHONPATH=src python -m fogo.cli build --region "Your region" --bbox SOUTH NORTH WEST EAST \
  --modis ... --viirs ... --out out/region.json --grid-out out/grid.json --points-out out/points
```

The box must be the one used in the FIRMS download and must not cross the antimeridian. The command stops with a clear
message if a box is impossible or holds no hotspots. The calibration (monthly MODIS/VIIRS ratio) is refitted and
validated on that region's own data, so the error reported is for that region. This repository ships and has validated
only Tocantins; the page reads one region from `docs/data/`, and the state border and town names (`geo.json`) are specific to Tocantins.

State border and place names (IBGE open data, saved once as JSON; the page works without this file):

```bash
# state mesh, municipal mesh and municipality list from servicodados.ibge.gov.br (state code 17)
PYTHONPATH=src python -m fogo.cli geo --state estado.json --towns municipios.json --names nomes.json \
  --out docs/data/geo.json
```

On Windows without the `python` command, use `py -3`. The `%-d` date format is avoided on purpose because Windows
does not support it.

Data: NASA FIRMS Archive Download (https://firms.modaps.eosdis.nasa.gov/download/), CSV, MODIS C6.1 from
2000-11-01 and VIIRS S-NPP 375 m from 2012-01-20, bounding box above. The raw CSVs (over 300 MB) are not
in this repository.

## Layout

```
src/fogo/load.py        read and merge FIRMS CSVs, filter by region and fire type
src/fogo/weekly.py      weekly series per sensor
src/fogo/calibrate.py   MODIS<->VIIRS ratio, out-of-sample error, method comparison
src/fogo/series.py      one weekly series on the MODIS ruler
src/fogo/indicators.py  normal, year-to-date headline, weekly curve
src/fogo/export.py      the small JSON the page reads
src/fogo/grid.py        0.25 degree cells x weeks per sensor (sparse JSON for the area explorer)
src/fogo/points.py      every detection, one binary file per year (docs/data/points/, about 44 MB)
src/fogo/geo.py         state border and place names for the map (docs/data/geo.json, from IBGE)
src/fogo/cli.py         end to end build, plus robustness checks
docs/                   static page (no backend, no keys): index.html + data/tocantins.json
tests/                  72 tests (reading, weeks, calibration, indicators, export, grid, points, geo, region, end to end)
```

## NASA data and references

- NASA FIRMS, MODIS Collection 6.1 active fire (Terra and Aqua), 2000 to present.
- NASA FIRMS, VIIRS S-NPP 375 m active fire (VNP14IMG), 2012 to present.
- IBGE, malhas territoriais (state and municipal meshes) and municipality list, via the IBGE data API, for the border and place names.
- Software: Python, pandas, NumPy, pytest. The page uses plain HTML, CSS and JavaScript, no external libraries.
- Context on Tocantins fire season used to frame the problem: IPAM report on forest fires in Tocantins;
  the state fire plan (PPCDIF-TO) goal of reducing hotspots against the 10-year average.
- No NASA logos or branding are used.

## Use of Super Intelligence (SI)

Claude (Anthropic) was used as a coding and analysis assistant during the hackathon: it wrote the code,
the tests and the page, and ran the data checks that are reported above. The author chose the challenge,
the region and the intended users, asked for a story-first product instead of a data dashboard, ran the
FIRMS requests, reviewed the results and decides what is published. The specific method (monthly
calibration ratio, comparison with a 10-year normal, robustness checks) was developed in conversation
with Claude. Code, data processing and the text of this repository and page are SI-assisted; there is no
generated imagery, audio or video in the page.

## Disclosure about earlier work

Before the event the author studied the FIRMS data format and downloaded two small sample files
(August to September 2023) and built an early exploratory prototype. None of that code is used here: every
file in this repository was written on November 14, 2026, during the hackathon, from scratch.

## License

MIT, see `LICENSE`.
