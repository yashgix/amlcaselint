"""Run the amlcaselint experiment and write its metrics JSON."""

import argparse
from pathlib import Path

from amlcaselint import DATA_DIR
from amlcaselint.run import main as run_experiment


def build_parser():
    """Build the --out/--data parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="path for the metrics JSON")
    parser.add_argument("--data", default=DATA_DIR, type=Path, help="corpus directory")
    return parser


def main(argv=None):
    """Run the experiment and return an exit code."""
    args = build_parser().parse_args(argv)
    return run_experiment(args.data, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
