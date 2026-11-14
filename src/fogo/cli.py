"""Build the page data from FIRMS CSVs.

    python -m fogo.cli build --modis a.csv b.csv --viirs c.csv --out docs/data/tocantins.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .calibrate import CalibrationError, Quantity, compare_methods, fit
from .export import build_payload, write_payload
from .indicators import InsufficientHistory, headline
from .load import TOCANTINS, read_firms
from .series import harmonize
from .weekly import weekly_series

PROVISIONAL_DAYS = 150  # FIRMS replaces near-real-time data with final data after ~5 months


def _split_years(years: list[int]) -> tuple[list[int], list[int]]:
    half = len(years) // 2
    return years[:half], years[half:]


def _robustness_checks(modis: pd.DataFrame, viirs: pd.DataFrame, year: int, last_week: int,
                       data_end: pd.Timestamp) -> list[dict]:
    """Recompute the headline in other defensible ways, so the page can show how much the
    answer depends on our choices (no calibration at all, fire power, a single ratio)."""
    final_until = data_end - pd.Timedelta(days=PROVISIONAL_DAYS)
    candidates = {
        "MODIS alone": lambda: modis["count"],
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
) -> dict:
    modis_detections = read_firms(modis_paths, TOCANTINS)
    viirs_detections = read_firms(viirs_paths, TOCANTINS)
    modis, viirs = weekly_series(modis_detections), weekly_series(viirs_detections)
    # The harmonized series uses VIIRS after 2012, so it is only valid up to the date BOTH sensors
    # reach; otherwise the last weeks would count zero VIIRS hotspots.
    data_end = min(modis_detections["day"].max(), viirs_detections["day"].max())

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
    # Keep only complete weeks that both sensors cover: later weeks would show a false drop to zero.
    harmonized = harmonized[harmonized.index + pd.Timedelta(days=6) <= data_end]

    last_complete_week = (data_end - pd.Timedelta(days=6)).isocalendar()
    year, last_week = int(last_complete_week.year), int(last_complete_week.week)
    result = headline(harmonized, year, last_week, final_until=data_end - pd.Timedelta(days=PROVISIONAL_DAYS))

    checks = _robustness_checks(modis, viirs, year, last_week, data_end)

    validation = (f"fit on {first_half[0]}-{first_half[-1]}, tested on {second_half[0]}-{second_half[-1]}, "
                  f"and the reverse; fire-season weeks (June to November) only")
    payload = build_payload(harmonized, result, calibration, error, region, validation, synthetic,
                            checks=checks)
    write_payload(payload, out)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(prog="fogo")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="harmonize MODIS + VIIRS and write the page JSON")
    build.add_argument("--modis", type=Path, nargs="+", required=True)
    build.add_argument("--viirs", type=Path, nargs="+", required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--quantity", choices=["count", "frp"], default="count")
    build.add_argument("--synthetic", action="store_true", help="mark the data as synthetic (dev only)")
    args = parser.parse_args()
    payload = run(args.modis, args.viirs, args.out, quantity=args.quantity, synthetic=args.synthetic)
    print(payload["headline"]["text"])
    print("validation:", payload["method"]["validation"],
          "| median weekly error:", payload["method"]["weekly_error_median"],
          "| p90:", payload["method"]["weekly_error_p90"])


if __name__ == "__main__":
    main()
