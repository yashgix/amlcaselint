"""Where the keyword baseline disagrees with the gold labels, with the text involved."""

from .corpus import load_orders
from .extract import extract, flagged
from .score import load_gold
from .taxonomy import CATEGORIES


def failures(data_dir) -> dict:
    """Per category: misses (gold order, gold quotes) and false hits (order, flagged sentences)."""
    gold = load_gold(data_dir)
    findings = [f for order in load_orders(data_dir) if order.id in gold for f in extract(order)]
    predicted = flagged(findings)
    result = {}
    for category in CATEGORIES:
        misses = [
            {"order_id": order_id, "quotes": labels[category]}
            for order_id, labels in gold.items()
            if category in labels and category not in predicted.get(order_id, ())
        ]
        false_hits = [
            {
                "order_id": order_id,
                "quotes": [f.quote for f in findings if f.order_id == order_id and f.category == category],
            }
            for order_id in gold
            if category not in gold[order_id] and category in predicted.get(order_id, ())
        ]
        result[category] = {"misses": misses, "false_hits": false_hits}
    return result
