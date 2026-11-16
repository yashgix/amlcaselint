"""Grounded checks for FinCEN enforcement-action findings over AML alert-case logs."""

from pathlib import Path

__all__ = ["DATA_DIR"]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
