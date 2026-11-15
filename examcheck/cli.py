"""Command line interface for examcheck."""

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import DATA_DIR
from .cases import read_log, write_log
from .checks import cannot_assess, run_checks
from .corpus import load_orders
from .extract import extract
from .failures import failures
from .review import review
from .synth import make_suite


def _findings(args):
    orders = load_orders(args.data)
    if args.order:
        orders = [order for order in orders if order.id == args.order]
    for order in orders:
        for finding in extract(order):
            print(json.dumps(asdict(finding), ensure_ascii=False))
    return 0


def _failures(args):
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(failures(args.data), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


def _synth(args):
    alerts = make_suite()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_log(out, alerts)
    print(f"wrote {len(alerts)} synthetic alerts to {out}")
    return 0


def _check(args):
    alerts = read_log(args.log)
    result = run_checks(alerts, args.as_of, naive=args.naive)
    if args.cannot_assess:
        result["cannot_assess"] = cannot_assess(alerts)
    print(json.dumps(result, indent=1))
    return 0


def _review(args):
    for finding in review(read_log(args.log), args.as_of):
        print(json.dumps(asdict(finding), ensure_ascii=False))
    return 0


def build_parser():
    """Build the argument parser with its subcommands."""
    parser = argparse.ArgumentParser(prog="examcheck")
    sub = parser.add_subparsers(dest="command", required=True)

    findings = sub.add_parser("findings", help="print baseline findings as JSON lines")
    findings.add_argument("--order", help="only this order id")
    findings.add_argument("--data", default=DATA_DIR, help="corpus directory")
    findings.set_defaults(func=_findings)

    failed = sub.add_parser(
        "failures", help="write the baseline's misses and false hits against the gold set"
    )
    failed.add_argument("--out", required=True, help="output JSON path")
    failed.add_argument("--data", default=DATA_DIR, help="corpus directory")
    failed.set_defaults(func=_failures)

    synth = sub.add_parser("synth", help="write the synthetic alert log")
    synth.add_argument("--out", required=True, help="output JSON-lines path")
    synth.set_defaults(func=_synth)

    check = sub.add_parser("check", help="run the checks over an alert log")
    check.add_argument("log", help="JSON-lines alert log")
    check.add_argument("--as-of", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    check.add_argument("--naive", action="store_true", help="use the naive check versions")
    check.add_argument(
        "--cannot-assess", action="store_true", help="also list alerts skipped for missing input"
    )
    check.set_defaults(func=_check)

    review_cmd = sub.add_parser(
        "review", help="one finding per flagged alert and check, with status and quote"
    )
    review_cmd.add_argument("log", help="JSON-lines alert log")
    review_cmd.add_argument("--as-of", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    review_cmd.set_defaults(func=_review)

    return parser


def main(argv=None):
    """Run the command line and return an exit code."""
    args = build_parser().parse_args(argv)
    return args.func(args)
