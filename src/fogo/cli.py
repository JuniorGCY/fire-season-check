"""Build the page data from FIRMS CSVs.

    python -m fogo.cli build --modis a.csv b.csv --viirs c.csv --out docs/data/tocantins.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .calibrate import CalibrationError, Quantity, compare_methods, fit
from .export import build_payload, write_payload
from .grid import build_grid
from .indicators import InsufficientHistory, headline
from .geo import DEFAULT_PLACES, build_geo
from .load import TOCANTINS, BBox, read_firms
from .points import build_points
from .schedule import observation_summary
from .series import VIIRS_SNPP_START, harmonize
from .weekly import weekly_series

PROVISIONAL_DAYS = 150  # FIRMS replaces near-real-time data with final data after ~5 months


def _split_years(years: list[int]) -> tuple[list[int], list[int]]:
    half = len(years) // 2
    return years[:half], years[half:]


def _robustness_checks(modis: pd.DataFrame, viirs: pd.DataFrame, year: int, last_week: int,
                       data_end: pd.Timestamp, modis_covers: bool = True) -> list[dict]:
    """Recompute the headline in other defensible ways, so the page can show how much the
    answer depends on our choices (no calibration at all, fire power, a single ratio).
    "MODIS alone" is skipped once MODIS no longer covers the period (it would read as zero fire)."""
    final_until = data_end - pd.Timedelta(days=PROVISIONAL_DAYS)
    candidates = {
        **({"MODIS alone": lambda: modis["count"]} if modis_covers else {}),
        "VIIRS alone": lambda: viirs["count"],
        "fire power instead of counts": lambda: harmonize(
            modis, viirs, fit(modis, viirs, "frp", "monthly"))["value"],
        "one ratio for the whole year": lambda: harmonize(
            modis, viirs, fit(modis, viirs, "count", "single"))["value"],
    }
    checks = []
    for label, build in candidates.items():
        try:
            other = headline(build(), year, last_week, final_until=final_until)
        except (InsufficientHistory, CalibrationError):
            continue
        checks.append({"label": label, "pct_vs_normal": round(other.pct_vs_normal, 1),
                       "rank": other.rank, "compared_years": other.compared_years})
    return checks


def run(
    modis_paths: list[Path],
    viirs_paths: list[Path],
    out: Path,
    region: str = "Tocantins",
    quantity: Quantity = "count",
    synthetic: bool = False,
    grid_out: Path | None = None,
    points_out: Path | None = None,
    box: BBox = TOCANTINS,
) -> dict:
    modis_detections = read_firms(modis_paths, box)
    viirs_detections = read_firms(viirs_paths, box)
    for sensor, detections in (("MODIS", modis_detections), ("VIIRS", viirs_detections)):
        if detections.empty:
            raise SystemExit(f"no hotspots from {sensor} inside the box "
                             f"lat {box.min_lat}..{box.max_lat}, lon {box.min_lon}..{box.max_lon}: "
                             "check the box and the CSV files")
    modis, viirs = weekly_series(modis_detections), weekly_series(viirs_detections)
    # After 2012 the harmonized series is VIIRS on the MODIS ruler, so it ends where VIIRS ends:
    # later weeks would count zero VIIRS hotspots. It does NOT need MODIS to keep flying, so the
    # series continues when MODIS (Terra/Aqua, near the end of their lives) stops.
    modis_last, viirs_last = modis_detections["day"].max(), viirs_detections["day"].max()
    data_end = viirs_last

    overlap_years = sorted(set((modis.index + pd.Timedelta(days=3)).year)
                           & set((viirs.index + pd.Timedelta(days=3)).year))
    first_half, second_half = _split_years(overlap_years)
    if len(first_half) < 2 or len(second_half) < 2:
        raise SystemExit("need at least 4 overlapping years to validate the calibration")

    # Out-of-sample error in both directions; keep the fit kind with the lower median error.
    forward = compare_methods(modis, viirs, first_half, second_half)
    backward = compare_methods(modis, viirs, second_half, first_half)
    both = pd.concat([forward, backward])
    summary = both[both.quantity == quantity].groupby("kind").agg(
        median_error=("median_error", "mean"), p90_error=("p90_error", "max"), weeks=("weeks", "sum"))
    kind = summary["median_error"].idxmin()
    error = summary.loc[kind].to_dict()

    calibration = fit(modis, viirs, quantity, kind)  # final fit on every overlapping year
    harmonized = harmonize(modis, viirs, calibration)["value"]
    # Keep only complete weeks up to the data end: later weeks would show a false drop to zero.
    harmonized = harmonized[harmonized.index + pd.Timedelta(days=6) <= data_end]

    last_complete_week = (data_end - pd.Timedelta(days=6)).isocalendar()
    year, last_week = int(last_complete_week.year), int(last_complete_week.week)
    result = headline(harmonized, year, last_week, final_until=data_end - pd.Timedelta(days=PROVISIONAL_DAYS))

    checks = _robustness_checks(modis, viirs, year, last_week, data_end,
                                modis_covers=modis_last >= data_end)
    observation = observation_summary(modis_detections, viirs_detections, VIIRS_SNPP_START,
                                      min(modis_last, viirs_last))

    validation = (f"fit on {first_half[0]}-{first_half[-1]}, tested on {second_half[0]}-{second_half[-1]}, "
                  f"and the reverse; fire-season weeks (June to November) only")
    payload = build_payload(harmonized, result, calibration, error, region, validation, synthetic,
                            checks=checks, observation=observation,
                            sensors_last_day={"modis_last_day": modis_last.strftime("%Y-%m-%d"),
                                              "viirs_last_day": viirs_last.strftime("%Y-%m-%d")})
    write_payload(payload, out)
    if grid_out is not None:
        grid = build_grid(modis_detections, viirs_detections, box, harmonized.index.max(), calibration)
        grid_out.parent.mkdir(parents=True, exist_ok=True)
        grid_out.write_text(json.dumps(grid, separators=(",", ":")))
    if points_out is not None:
        # Same cutoff as the grid: the end of the last complete common week.
        build_points(modis_detections, viirs_detections, box, points_out,
                     through=harmonized.index.max() + pd.Timedelta(days=6))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(prog="fogo")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="harmonize MODIS + VIIRS and write the page JSON")
    build.add_argument("--modis", type=Path, nargs="+", required=True)
    build.add_argument("--viirs", type=Path, nargs="+", required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--region", default=None, help="region name shown on the page (required with --bbox)")
    build.add_argument("--bbox", type=float, nargs=4, default=None,
                       metavar=("SOUTH", "NORTH", "WEST", "EAST"),
                       help="decimal degrees; default is the Tocantins box. Use the same box as the FIRMS download.")
    build.add_argument("--quantity", choices=["count", "frp"], default="count")
    build.add_argument("--grid-out", type=Path, default=None, help="also write the 0.25 degree grid JSON")
    build.add_argument("--points-out", type=Path, default=None,
                       help="also write individual hotspots as one binary file per year (folder)")
    build.add_argument("--synthetic", action="store_true", help="mark the data as synthetic (dev only)")
    geo_cmd = commands.add_parser("geo", help="write the state outline and place names for the map")
    geo_cmd.add_argument("--state", type=Path, required=True, help="IBGE state mesh (GeoJSON)")
    geo_cmd.add_argument("--towns", type=Path, required=True, help="IBGE municipal mesh (GeoJSON)")
    geo_cmd.add_argument("--names", type=Path, required=True, help="IBGE municipality list (JSON)")
    geo_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "geo":
        load = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
        geo = build_geo(load(args.state), load(args.towns), load(args.names), DEFAULT_PLACES)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"outline: {sum(len(r) for r in geo['outline'])} points, places: {len(geo['places'])}")
        return
    try:
        box = BBox(*args.bbox) if args.bbox else TOCANTINS
    except ValueError as error:
        raise SystemExit(f"--bbox: {error}") from error
    if args.bbox and not args.region:
        parser.error("--bbox needs --region, so the page names the right place")
    payload = run(args.modis, args.viirs, args.out, region=args.region or "Tocantins", quantity=args.quantity,
                  synthetic=args.synthetic, grid_out=args.grid_out, points_out=args.points_out, box=box)
    print(payload["headline"]["text"])
    print("validation:", payload["method"]["validation"],
          "| median weekly error:", payload["method"]["weekly_error_median"],
          "| p90:", payload["method"]["weekly_error_p90"])


if __name__ == "__main__":
    main()
