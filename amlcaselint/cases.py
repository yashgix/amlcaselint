"""Alert-case log records: fields, JSON round-trip and JSON-lines file I/O."""

import json
import re
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


MAX_LINES = 200_000
MAX_LINE_CHARS = 100_000
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


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


def _date(row, name):
    value = row.get(name)
    if value is None and name != "opened":
        return None
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise ValueError(f"{name} must be a YYYY-MM-DD date, got {value!r}")
    return date.fromisoformat(value)


def _strings(row, name):
    value = row.get(name, [])
    if not isinstance(value, list | tuple) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of strings")
    return tuple(value)


def _typed(row, name, kind, default):
    value = row.get(name, default)
    if not isinstance(value, kind):
        raise ValueError(f"{name} must be {kind.__name__}, got {value!r}")
    return value


def from_json(row: dict) -> Alert:
    """Rebuild an alert written by to_json, rejecting bad types with ValueError. Unknown keys are ignored."""
    if not isinstance(row, dict):
        raise ValueError("an alert must be a JSON object")
    if "alert_id" not in row or "opened" not in row:
        raise ValueError("an alert needs alert_id and opened")
    disposition = row.get("disposition")
    if disposition is not None and not isinstance(disposition, str):
        raise ValueError("disposition must be a string or null")
    return Alert(
        alert_id=_typed(row, "alert_id", str, ""),
        opened=_date(row, "opened"),
        detected=_date(row, "detected"),
        closed=_date(row, "closed"),
        disposition=disposition,
        sar_filed=_date(row, "sar_filed"),
        suspect_known=_typed(row, "suspect_known", bool, True),
        rationale=_typed(row, "rationale", str, ""),
        evidence=_strings(row, "evidence"),
        reasons=_strings(row, "reasons"),
        kind=_typed(row, "kind", str, ""),
    )


def write_log(path: str | Path, alerts: Iterable[Alert]) -> None:
    """Write one JSON object per line, each line newline-terminated."""
    alerts = list(alerts)
    if len(alerts) > MAX_LINES:
        raise ValueError(f"a log holds at most {MAX_LINES} alerts")
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(to_json(alert)) + "\n" for alert in alerts)


def read_log(path: str | Path) -> list[Alert]:
    """Read the alerts from a JSON-lines log, skipping blank lines."""
    alerts = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            if len(alerts) == MAX_LINES:
                raise ValueError(f"a log holds at most {MAX_LINES} alerts")
            if len(line.rstrip("\n")) > MAX_LINE_CHARS:
                raise ValueError(f"a log line holds at most {MAX_LINE_CHARS} characters")
            alerts.append(from_json(json.loads(line)))
    return alerts
