"""Measure the corpus, the gold scores and the synthetic checks into one metrics dict."""

import json
from pathlib import Path

from . import DATA_DIR
from .checks import BASIS, CHECKS, run_checks, sar_deadline
from .corpus import REGULATION, grounded, load_index, load_orders, regulation_text, sentences
from .extract import extract, flagged, max_count
from .score import category_scores, evidence_recall, load_gold
from .synth import DEFAULT, NEAR_MISSES, make_suite, truth
from .taxonomy import CATEGORIES


def _share(part, whole):
    """part / whole rounded to six places, 0.0 when whole is zero."""
    return round(part / whole, 6) if whole else 0.0


def _corpus(data_dir, orders, findings):
    """Corpus sizes and the baseline's per-category coverage."""
    index = load_index(data_dir)
    texts = {order.id: order.text for order in orders}
    categories = flagged(findings)
    cited = [
        sum(1 for order in orders if category in categories.get(order.id, ())) for category in CATEGORIES
    ]
    return {
        "orders_listed": len(index),
        "orders": len(orders),
        "orders_no_text": sum(1 for entry in index if entry["status"] == "no_text_layer"),
        "orders_individual": sum(1 for entry in index if entry["status"] == "individual"),
        "words": sum(len(order.text.split()) for order in orders),
        "sentences": sum(len(sentences(order.text)) for order in orders),
        "findings": len(findings),
        "findings_grounded": _share(
            sum(1 for finding in findings if grounded(finding.quote, texts[finding.order_id])),
            len(findings),
        ),
        "corpus_orders": cited,
        "corpus_share": [_share(count, len(orders)) for count in cited],
        "cited_alerts": [max_count(findings, order.id, "alert_backlog", "alerts") for order in orders],
        "cited_sars": [max_count(findings, order.id, "late_sar", "sars") for order in orders],
    }


def _gold(data_dir, orders, findings, gold_file="gold.json"):
    """Baseline scores and quote grounding against the gold set."""
    gold = load_gold(data_dir, gold_file)
    texts = {order.id: order.text for order in orders}
    gold_findings = [finding for finding in findings if finding.order_id in gold]
    predicted = flagged(gold_findings)
    per, micro, macro = category_scores(gold, predicted)
    quotes = [
        (order_id, quote)
        for order_id, labels in gold.items()
        for category_quotes in labels.values()
        for quote in category_quotes
    ]
    labelled = [sum(1 for labels in gold.values() if category in labels) for category in CATEGORIES]
    baseline = [
        sum(1 for order_id in gold if category in predicted.get(order_id, ())) for category in CATEGORIES
    ]
    return {
        "gold_orders": len(gold),
        "gold_positives": sum(len(labels) for labels in gold.values()),
        "gold_quotes": len(quotes),
        "gold_quotes_grounded": _share(
            sum(1 for order_id, quote in quotes if grounded(quote, texts[order_id])),
            len(quotes),
        ),
        "gold_share": [_share(count, len(gold)) for count in labelled],
        "baseline_gold_share": [_share(count, len(gold)) for count in baseline],
        "precision": [round(scores[0], 6) for scores in per],
        "recall": [round(scores[1], 6) for scores in per],
        "f1": [round(scores[2], 6) for scores in per],
        "micro_precision": round(micro[0], 6),
        "micro_recall": round(micro[1], 6),
        "micro_f1": round(micro[2], 6),
        "macro_f1": round(macro, 6),
        "evidence_recall": round(evidence_recall(gold, gold_findings, texts), 6),
    }


def _basis(orders, data_dir):
    """Share of the quoted passages that appear in their cited source."""
    texts = {order.id: order.text for order in orders}
    regulation = regulation_text(data_dir)
    total = 0
    hits = 0
    for passages in BASIS.values():
        for source, quote in passages:
            total += 1
            text = regulation if source == REGULATION else texts.get(source, "")
            hits += grounded(quote, text)
    return {"basis_quotes": total, "basis_quotes_grounded": _share(hits, total)}


def _checks():
    """Strict and naive check results on the default synthetic log."""
    alerts = make_suite()
    as_of = DEFAULT.as_of
    by_id = {alert.alert_id: alert for alert in alerts}
    seeded = truth(alerts)
    strict = run_checks(alerts, as_of)
    naive = run_checks(alerts, as_of, naive=True)
    cases = len(alerts)

    seeded_n, flagged_n, detection, false_flag = [], [], [], []
    naive_flagged_n, naive_detection, naive_false_flag = [], [], []
    delays = []
    for check in CHECKS:
        seed = seeded.get(check, set())
        hit = set(strict[check])
        naive_hit = set(naive[check])
        seeded_n.append(len(seed))
        flagged_n.append(len(hit))
        detection.append(_share(len(hit & seed), len(seed)))
        false_flag.append(_share(len(hit - seed), cases - len(seed)))
        naive_flagged_n.append(len(naive_hit))
        naive_detection.append(_share(len(naive_hit & seed), len(seed)))
        naive_false_flag.append(_share(len(naive_hit - seed), cases - len(seed)))
        if check == "late_sar":
            delays = [
                (by_id[alert_id].sar_filed - sar_deadline(by_id[alert_id])).days
                for alert_id in strict[check]
                if by_id[alert_id].sar_filed is not None
            ]

    return {
        "cases": cases,
        "near_misses": sum(1 for alert in alerts if alert.kind in NEAR_MISSES),
        "seeded": seeded_n,
        "flagged": flagged_n,
        "detection_rate": detection,
        "false_flag_rate": false_flag,
        "naive_flagged": naive_flagged_n,
        "naive_detection_rate": naive_detection,
        "naive_false_flag_rate": naive_false_flag,
        "late_sar_mean_days_late": round(sum(delays) / len(delays), 6) if delays else 0.0,
    }


def metrics(data_dir=DATA_DIR):
    """Return every metric, with floats rounded to six places."""
    orders = load_orders(data_dir)
    findings = [finding for order in orders for finding in extract(order)]
    result = {}
    result.update(_corpus(data_dir, orders, findings))
    result.update(_gold(data_dir, orders, findings))
    result.update(_basis(orders, data_dir))
    result.update(_checks())
    return result


GOLD_V2_KEYS = (
    "gold_positives",
    "micro_precision",
    "micro_recall",
    "micro_f1",
    "macro_f1",
    "evidence_recall",
)


def gold_v2_metrics(data_dir=DATA_DIR):
    """Baseline scores against data/gold-v2.json, beside the frozen v1 scores."""
    orders = load_orders(data_dir)
    findings = [finding for order in orders for finding in extract(order)]
    scores = _gold(data_dir, orders, findings, "gold-v2.json")
    return {key: scores[key] for key in GOLD_V2_KEYS}


def main(data_dir=DATA_DIR, out="results/metrics.json"):
    """Write the metrics JSON to out and return 0."""
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics(data_dir), sort_keys=True, indent=1) + "\n", encoding="utf-8")
    return 0
