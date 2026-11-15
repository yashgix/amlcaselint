"""Alert-case log records: fields, JSON round-trip and JSON-lines file I/O."""

import json
from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path

REASONS = (
    "activity_reviewed",
    "customer_explained",
    "expected_activity",
    "false_positive",
    "prior_sar",
    "prior_ctr",
)


@dataclass(frozen=True)
class Alert:
    """One alert case as a bank's AML case log would record it."""

    alert_id: str
    opened: date
    detected: date | None = None
    closed: date | None = None
    disposition: str | None = None
    sar_filed: date | None = None
    suspect_known: bool = True
    rationale: str = ""
    evidence: tuple = ()
    reasons: tuple = ()
    kind: str = ""


_DATE_FIELDS = frozenset({"opened", "detected", "closed", "sar_filed"})
_TUPLE_FIELDS = frozenset({"evidence", "reasons"})


def to_json(alert: Alert) -> dict:
    """Return the alert as a JSON-ready dict: ISO dates, lists for tuples."""
    row = {}
    for field in fields(Alert):
        value = getattr(alert, field.name)
        if isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, tuple):
            value = list(value)
        row[field.name] = value
    return row


def from_json(row: dict) -> Alert:
    """Rebuild an alert written by to_json; unknown keys are ignored."""
    kwargs = {}
    for field in fields(Alert):
        if field.name not in row:
            continue
        value = row[field.name]
        if field.name in _DATE_FIELDS:
            value = date.fromisoformat(value) if value is not None else None
        elif field.name in _TUPLE_FIELDS:
            value = tuple(value)
        kwargs[field.name] = value
    return Alert(**kwargs)


def write_log(path: str | Path, alerts: Iterable[Alert]) -> None:
    """Write one JSON object per line, each line newline-terminated."""
    with Path(path).open("w", encoding="utf-8") as handle:
        for alert in alerts:
            handle.write(json.dumps(to_json(alert)) + "\n")


def read_log(path: str | Path) -> list[Alert]:
    """Read the alerts from a JSON-lines log, skipping blank lines."""
    with Path(path).open(encoding="utf-8") as handle:
        return [from_json(json.loads(line)) for line in handle if line.strip()]
