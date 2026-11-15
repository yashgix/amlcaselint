"""Load the pinned FinCEN order corpus and split it into grounded sentences."""

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import DATA_DIR

REGULATION = "31 CFR 1020.320"

_SENTENCE_BREAK = re.compile(r"(?<=[.!?]) (?=[A-Z])")
_XML_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Order:
    """One included FinCEN enforcement action with normalized text."""

    id: str
    date: str
    title: str
    url: str
    text: str


def normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces."""
    return " ".join(text.split())


def grounded(quote: str, text: str) -> bool:
    """Whether a quote appears in normalized text."""
    normalized = normalize(quote)
    return bool(normalized) and normalized in text


def sentences(text: str) -> list[tuple[int, str]]:
    """Split normalized text at sentence boundaries and return (start, sentence)."""
    result: list[tuple[int, str]] = []
    start = 0
    for part in _SENTENCE_BREAK.split(text):
        if part:
            result.append((start, part))
        start += len(part) + 1  # the removed single space
    return result


def load_index(data_dir: Path | str = DATA_DIR) -> list[dict]:
    """Read the pinned list of enforcement actions."""
    return json.loads((Path(data_dir) / "orders.json").read_text(encoding="utf-8"))


def load_orders(data_dir: Path | str = DATA_DIR) -> list[Order]:
    """Load included orders in index order with normalized text."""
    data_dir = Path(data_dir)
    orders = []
    for entry in load_index(data_dir):
        if entry["status"] != "included":
            continue
        text = normalize((data_dir / entry["text"]).read_text(encoding="utf-8"))
        orders.append(Order(entry["id"], entry["date"], entry["title"], entry["url"], text))
    return orders


def regulation_text(data_dir: Path | str = DATA_DIR) -> str:
    """Return 31 CFR 1020.320 as normalized plain text."""
    xml = (Path(data_dir) / "regulation" / "31-cfr-1020.320.xml").read_text(encoding="utf-8")
    return normalize(html.unescape(_XML_TAGS.sub(" ", xml)))
