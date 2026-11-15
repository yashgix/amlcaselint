"""Find sentences in FinCEN orders that match the fixed failure categories."""

import re
from dataclasses import dataclass

from .corpus import sentences
from .taxonomy import CATEGORIES, COMPILED

COUNT_RE = re.compile(
    r"(?<![\w$§.,])(\d{1,3}(?:,\d{3})+|\d+)\s+"
    r"(?:[A-Za-z-]+\s+){0,2}?"
    r"(alert events|alerts?|SARs?|suspicious activity reports?|CTRs?|"
    r"currency transaction reports?|days|cases)\b",
    re.IGNORECASE,
)

_UNIT_BY_PREFIX = {
    "ale": "alerts",
    "sar": "sars",
    "sus": "sars",
    "ctr": "ctrs",
    "cur": "ctrs",
    "day": "days",
    "cas": "cases",
}


@dataclass(frozen=True)
class Finding:
    """One order sentence flagged for one category."""

    order_id: str
    category: str
    start: int
    quote: str
    counts: tuple


def counts(quote):
    """Return (unit, number) for every count-like phrase in quote."""
    return tuple(
        (_UNIT_BY_PREFIX[match.group(2)[:3].lower()], int(match.group(1).replace(",", "")))
        for match in COUNT_RE.finditer(quote)
    )


def extract(order):
    """Return one Finding per (sentence, category) match, in reading order."""
    findings = []
    for start, sentence in sentences(order.text):
        for category in CATEGORIES:
            if any(pattern.search(sentence) for pattern in COMPILED[category]):
                findings.append(Finding(order.id, category, start, sentence, counts(sentence)))
    return findings


def flagged(findings):
    """Map each order id to the set of categories it was flagged for."""
    result = {}
    for finding in findings:
        result.setdefault(finding.order_id, set()).add(finding.category)
    return result


def max_count(findings, order_id, category, unit):
    """Largest cited number of unit in that order and category, or 0."""
    numbers = (
        number
        for finding in findings
        if finding.order_id == order_id and finding.category == category
        for found_unit, number in finding.counts
        if found_unit == unit
    )
    return max(numbers, default=0)
