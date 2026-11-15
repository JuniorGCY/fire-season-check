# Submission texts (copy into the Space Apps form)

All numbers below come from the real NASA FIRMS data and match the page and the README.
Data through 2026-11-01; the newest weeks are near-real-time and provisional.

## Project name

Fire Season Check

## Links

- Live page: https://juniorgcy.github.io/fire-season-check/ (Argentine Chaco: https://juniorgcy.github.io/fire-season-check/?region=chaco)
- Demo (7 slides): https://juniorgcy.github.io/fire-season-check/slides.html
- Code and data: https://github.com/JuniorGCY/fire-season-check

## High-level summary (short)

Fire Season Check turns 25 years of NASA FIRMS hotspots from two sensors, MODIS (since 2000) and VIIRS (since
2012), into one consistent weekly record and answers the question a fire manager already asks: is this season
above or below normal? MODIS-equivalent counts are computed as VIIRS × a factor fitted per month on each region's
own data and tested on years it never saw (typical weekly error 9.2% in Tocantins, Brazil). Through November 1,
2026, Tocantins had 41% fewer hotspots than the average of the previous 10 years, the lowest of 11 years. Users
pick any area and dates inside two validated regions (Tocantins and the Argentine Chaco) and get year-by-week and
year-by-month burning calendars, anomalies against the 10-year average and median, CSVs of individual hotspots
and images. Our main finding: there is no single MODIS/VIIRS factor; it changes by month, time of day and region.

## Detailed description

**What it does.** A static web page for firefighters, brigade members, civil defence, land managers and
scientists. It opens with one sentence and one number: how the current season compares with the previous 10
years, with its rank. Below it, an explorer lets the user draw a rectangle on a map (or type latitude and
longitude) and pick dates. It shows a year-by-week and a year-by-month burning calendar from November 2000, each
week and month against the 10-year average and median, the latest month against the median of the same month
(October 2026 in Tocantins: −51%), the busiest month and the busiest year in the area. Users can download CSVs
(weekly, monthly, per 28 km cell, and every individual hotspot with a harmonized weight) and PNG images of the
calendars and the map.

**How it works.** An offline Python pipeline reads FIRMS archive and near-real-time CSVs (vegetation fires,
type 0), merges them without double counting and builds weekly series per sensor. Before 2012 the record is
MODIS; after VIIRS starts it is VIIRS on the MODIS scale: MODIS-equivalent = VIIRS × factor, with one factor per
calendar month. The factor is fitted on the years both satellites fly and scored on years it has not seen
(fit 2012–2018, test 2019–2026, and the reverse): median weekly error 9.2% in Tocantins (90th percentile
38.9%) and 9.3% in the Argentine Chaco (33.2%). The answer is recomputed four other ways (MODIS alone, VIIRS
alone, fire radiative power, one yearly factor); in Tocantins all give between −38% and −43%. Because the
series uses VIIRS after 2012, it keeps going when the ageing MODIS satellites stop. The page is static (no
server, no keys, no external libraries), works on a phone, and has loading, error, empty and ready states,
accessible colour ramps, keyboard use and text alternatives.

**What we found.** There is no single conversion factor. MODIS sees 0.33 hotspots per VIIRS hotspot in June
but 0.21 in October in Tocantins; 0.27 on daytime passes but 0.19 at night; 0.246 over the year in Tocantins
but 0.308 in the Argentine Chaco, so a factor copied from one region is about 25% off in the other. The night
factor is the same (0.19) in both regions, so the difference comes from daytime passes. A stress test on the
Paraná Delta, where fires are small, gave a 23% weekly error, so we left it off the page; there, 2026 looks
−60% against the mean but only −8% against the median, because the extreme fires of 2020 and 2022 inflate the
mean. This is why the page shows the median next to the mean.

**Benefits and intended impact.** A brigade or civil defence office gets a consistent 25-year picture of its
own area in seconds, can see which weeks and months are critical, and can compare the current season or month
with history, using the same yardstick as the Tocantins state fire plan (the 10-year average). Every number
carries its measured error, so users know how much to trust it.

**Limits (stated on the page).** Two validated regions; the pipeline re-validates any FIRMS box, but two
regions are evidence, not proof. One factor for day and night together; VIIRS S-NPP only (not NOAA-20/21).
Small areas have larger errors (the page warns). Hotspots are satellite detections, not confirmed fires, and no
brigade has field-tested the tool yet.

**Next steps.** Separate day and night factors, NOAA-20/21 VIIRS, more regions with a median-first headline
where the mean misleads, and a field test with Tocantins brigades.

**Tools.** Python, pandas, NumPy, pytest (80 automated tests); HTML, CSS and plain JavaScript; GitHub Pages.

## Use of NASA data

NASA FIRMS active fire data: MODIS Collection 6.1 (Terra and Aqua, from 2000-11-01) and VIIRS S-NPP 375 m
(VNP14IMG, from 2012-01-20), archive and near-real-time CSVs, for the Tocantins box (latitude −13.5 to −5.1,
longitude −50.8 to −45.6), the Argentine Chaco box (−28.5 to −23.5, −64.5 to −58.5) and the Paraná Delta box
(−34.5 to −32.0, −61.0 to −58.0, stress test only). FIRMS is the only fire data source. No CONAE data is used.

## References

- NASA FIRMS, MODIS Collection 6.1 active fire product (Terra and Aqua). https://firms.modaps.eosdis.nasa.gov/
- NASA FIRMS, VIIRS S-NPP 375 m active fire product (VNP14IMG). https://firms.modaps.eosdis.nasa.gov/
- IBGE, territorial meshes (state and municipal) and municipality list, IBGE data API, for the Tocantins border
  and town names. https://servicodados.ibge.gov.br/
- IPAM report on forest fires in Tocantins (context for the problem).
- Tocantins state fire plan (PPCDIF-TO), goal of reducing hotspots against the 10-year average (yardstick).
- Python, pandas, NumPy, pytest (open-source software).
- Claude (Anthropic), AI assistant (see SI declaration).
- No NASA logos or branding, no third-party images, no external JavaScript libraries.

## Use of Super Intelligence (SI)

Built with the help of Claude (Anthropic), an AI assistant. The author chose the challenge, chose the approach
among the options the assistant listed, chose the users, the regions and how results are shown, and downloaded
the NASA FIRMS data. The assistant wrote the code, tests and texts and ran the data checks; the author reviewed
the results and decides what is published.

What happened, in order: the author asked Claude for a summary of the challenges and chose this one; asked what
keeps the MODIS and VIIRS records from lining up; Claude listed the options and what each affects; the author
chose the approach (a measured MODIS/VIIRS factor validated on unseen years), decided the users, to start with
Tocantins and to plan other regions, downloaded the FIRMS data and chose the presentation. There is no
generated imagery, audio or video. The same statement is in the page footer and metadata, the README,
`docs/data/ABOUT.txt` and the code.
