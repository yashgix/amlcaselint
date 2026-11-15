'''Score baseline findings against the hand-labelled gold set.'''

import json
from pathlib import Path

from . import DATA_DIR
from .corpus import normalize
from .taxonomy import CATEGORIES


def load_gold(data_dir=DATA_DIR):
    '''Return the orders object of gold.json.'''
    path = Path(data_dir) / 'gold.json'
    return json.loads(path.read_text(encoding='utf-8'))['orders']


def prf(tp, fp, fn):
    '''Precision, recall and F1, with 0.0 for an empty denominator.'''
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def confusion(gold, predicted, category):
    '''True positives, false positives and false negatives over the gold orders.'''
    tp = fp = fn = 0
    for order_id, labels in gold.items():
        positive = category in labels
        hit = category in predicted.get(order_id, ())
        if positive and hit:
            tp += 1
        elif positive:
            fn += 1
        elif hit:
            fp += 1
    return tp, fp, fn


def category_scores(gold, predicted):
    '''Per-category scores, micro scores and the macro F1.'''
    per = []
    tp = fp = fn = 0
    for category in CATEGORIES:
        category_tp, category_fp, category_fn = confusion(gold, predicted, category)
        per.append(prf(category_tp, category_fp, category_fn))
        tp += category_tp
        fp += category_fp
        fn += category_fn
    micro = prf(tp, fp, fn)
    macro = sum(scores[2] for scores in per) / len(per) if per else 0.0
    return per, micro, macro


def _overlaps(start, end, other_start, other_end):
    return start < other_end and other_start < end


def evidence_recall(gold, findings, texts):
    '''Share of gold positives whose quote overlaps a finding of the same category.'''
    by_key = {}
    for finding in findings:
        by_key.setdefault((finding.order_id, finding.category), []).append(finding)

    positives = 0
    covered = 0
    for order_id, labels in gold.items():
        text = texts[order_id]
        for category, quotes in labels.items():
            positives += 1
            spans = []
            for quote in quotes:
                needle = normalize(quote)
                start = text.find(needle)
                if start != -1:
                    spans.append((start, start + len(needle)))
            matched = by_key.get((order_id, category), ())
            if any(
                _overlaps(finding.start, finding.start + len(finding.quote), span_start, span_end)
                for finding in matched
                for span_start, span_end in spans
            ):
                covered += 1
    return covered / positives if positives else 0.0
