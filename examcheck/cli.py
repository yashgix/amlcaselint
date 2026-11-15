"""Command line interface for examcheck."""

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import DATA_DIR
from .cases import read_log, write_log
from .checks import run_checks
from .corpus import load_orders
from .extract import extract
from .synth import make_suite


def _findings(args):
    orders = load_orders(args.data)
    if args.order:
        orders = [order for order in orders if order.id == args.order]
    for order in orders:
        for finding in extract(order):
            print(json.dumps(asdict(finding), ensure_ascii=False))
    return 0


def _synth(args):
    alerts = make_suite()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_log(out, alerts)
    print(f"wrote {len(alerts)} synthetic alerts to {out}")
    return 0


def _check(args):
    result = run_checks(read_log(args.log), args.as_of, naive=args.naive)
    print(json.dumps(result, indent=1))
    return 0


def build_parser():
    """Build the argument parser with the three subcommands."""
    parser = argparse.ArgumentParser(prog="examcheck")
    sub = parser.add_subparsers(dest="command", required=True)

    findings = sub.add_parser("findings", help="print baseline findings as JSON lines")
    findings.add_argument("--order", help="only this order id")
    findings.add_argument("--data", default=DATA_DIR, help="corpus directory")
    findings.set_defaults(func=_findings)

    synth = sub.add_parser("synth", help="write the synthetic alert log")
    synth.add_argument("--out", required=True, help="output JSON-lines path")
    synth.set_defaults(func=_synth)

    check = sub.add_parser("check", help="run the checks over an alert log")
    check.add_argument("log", help="JSON-lines alert log")
    check.add_argument("--as-of", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    check.add_argument("--naive", action="store_true", help="use the naive check versions")
    check.set_defaults(func=_check)

    return parser


def main(argv=None):
    """Run the command line and return an exit code."""
    args = build_parser().parse_args(argv)
    return args.func(args)
