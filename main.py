"""
Trading Signal Scanner — entry point.

Usage:
    python main.py                          # daily scan, full universe
    python main.py --timeframe hourly       # hourly scan
    python main.py --categories SP500 DJIA  # limit to specific indices
    python main.py --no-backtest            # skip backtest (faster)
    python main.py --workers 4              # control parallelism
    python main.py --top 30                 # show top 30 signals
"""

from __future__ import annotations
import argparse
import logging

from scanner.scan  import run_scan
from output.report import print_report

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(name)s | %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Signal Scanner")
    parser.add_argument(
        "--timeframe", "-t",
        choices=["daily", "hourly", "intraday"],
        default="daily",
        help="Timeframe to scan (default: daily)",
    )
    parser.add_argument(
        "--categories", "-c",
        nargs="+",
        default=None,
        metavar="CAT",
        help="Universe categories to include (e.g. SP500 DJIA FX). Default: all.",
    )
    parser.add_argument(
        "--no-backtest",
        action="store_true",
        default=False,
        help="Skip backtesting (much faster, no win rates)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=8,
        help="Number of parallel worker threads (default: 8)",
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=20,
        help="Number of top signals to display (default: 20)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    results = run_scan(
        timeframe          = args.timeframe,
        max_workers        = args.workers,
        run_backtest_flag  = not args.no_backtest,
        categories         = args.categories,
        top_n              = args.top,
    )

    print_report(results, timeframe=args.timeframe)


if __name__ == "__main__":
    main()
