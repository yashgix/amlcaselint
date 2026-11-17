"""Print the amlcaselint summary and render the README results block from metrics.json."""

import argparse
import json
from pathlib import Path

from amlcaselint import DATA_DIR
from amlcaselint.checks import BASIS, CHECKS
from amlcaselint.corpus import REGULATION, load_index
from amlcaselint.taxonomy import CATEGORIES, LABELS

START = "<!-- results:start -->"
END = "<!-- results:end -->"


def load_metrics(results_dir):
    """Read metrics.json from a results directory."""
    path = Path(results_dir) / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _rate(value):
    """Format a 0..1 rate to three decimal places."""
    return f"{value:.3f}"


def summary(metrics):
    """Return the one-line console summary."""
    return (
        f"{metrics['orders']} orders, {metrics['findings']:,} findings; "
        f"micro F1 {metrics['micro_f1']:.3f}, macro F1 {metrics['macro_f1']:.3f}"
    )


def _corpus_sentence(metrics):
    return (
        f"{metrics['orders']} included orders ({metrics['words']:,} words, "
        f"{metrics['sentences']:,} sentences) gave {metrics['findings']:,} findings, "
        f"{metrics['findings_grounded']:.3f} of them grounded in the order text."
    )


def _baseline_sentence(metrics, v2):
    positives = metrics["gold_positives"]
    covered = round(metrics["evidence_recall"] * positives)
    text = (
        f"Document-level baseline scores on {metrics['gold_orders']} gold orders (an order counts as a hit "
        f"when any flagged sentence has the category): "
        f"micro precision {metrics['micro_precision']:.3f}, "
        f"micro recall {metrics['micro_recall']:.3f}, "
        f"micro F1 {metrics['micro_f1']:.3f}, "
        f"macro F1 {metrics['macro_f1']:.3f}.\n\n"
        f"Evidence recall is stricter: a gold quote is covered only when a flagged sentence overlaps it. "
        f"{covered} of {positives} gold positives are covered ({metrics['evidence_recall']:.3f}). "
        f"Finding a quote in the order text shows the sentence exists, not that it means what the label says."
    )
    if v2:
        text += (
            "\n\nFor the record, scoring against `data/gold-v2.json`, which adds the label the author rejected, "
            f"gives micro precision {v2['micro_precision']:.3f}, micro recall {v2['micro_recall']:.3f}, "
            f"micro F1 {v2['micro_f1']:.3f}, macro F1 {v2['macro_f1']:.3f}. The v1 scores above are the result."
        )
    return text


def _category_table(metrics):
    lines = [
        f"| Category | Gold orders citing it | Precision | Recall | F1 | "
        f"Share of the {metrics['orders']} orders flagged |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, category in enumerate(CATEGORIES):
        gold = round(metrics["gold_share"][index] * metrics["gold_orders"])
        lines.append(
            f"| {LABELS[category]} | {gold} | {_rate(metrics['precision'][index])} | "
            f"{_rate(metrics['recall'][index])} | {_rate(metrics['f1'][index])} | "
            f"{_rate(metrics['corpus_share'][index])} |"
        )
    return lines


def _check_table(metrics):
    lines = [
        "| Check | Seeded | Detection | False flags | Naive detection | Naive false flags |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, check in enumerate(CHECKS):
        lines.append(
            f"| `{check}` | {metrics['seeded'][index]} | "
            f"{_rate(metrics['detection_rate'][index])} | "
            f"{_rate(metrics['false_flag_rate'][index])} | "
            f"{_rate(metrics['naive_detection_rate'][index])} | "
            f"{_rate(metrics['naive_false_flag_rate'][index])} |"
        )
    return lines


def _source_name(source, titles):
    if source == REGULATION:
        return REGULATION
    return titles.get(source, source)


def _basis_section(titles):
    lines = ["### Basis", ""]
    for check in CHECKS:
        lines.extend([f"**`{check}`**", ""])
        for source, quote in BASIS[check]:
            lines.append(f'- {_source_name(source, titles)}: "{quote}"')
        lines.append("")
    return lines


def render_results(metrics, v2, titles):
    """Render the results block, markers included, from the metrics."""
    lines = [
        START,
        "",
        _corpus_sentence(metrics),
        "",
        _baseline_sentence(metrics, v2),
        "",
        "### Gold set by category",
        "",
        *_category_table(metrics),
        "",
        "### Checks on the synthetic alert log",
        "",
        *_check_table(metrics),
        "",
        "Detection 1.000 and false flags 0.000 are true by construction: the generator seeds exactly the "
        "cases the rules flag, so they show the code matches its spec, not that it finds real defects. "
        "The naive rules are written to be wrong, so their columns show what each rule detail is for.",
        "",
        *_basis_section(titles),
        END,
    ]
    return "\n".join(lines)


def _clip(text, width=300):
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def _failure_entries(rows, titles):
    return [
        f'- {titles.get(row["order_id"], row["order_id"])}: "{_clip(quote)}"'
        for row in rows
        for quote in row["quotes"][:2]
    ]


def render_failures(failures, titles):
    """Render the baseline failure analysis as markdown from failures.json."""
    lines = [
        "# Keyword baseline failures on the gold set",
        "",
        "Generated by `demo.py --failures`. A miss is a gold quote in an order where the baseline flagged nothing "
        "for that category. A false hit is a flagged sentence in an order the gold set does not label with the "
        "category. Scoring is per order, so a category counted as hit may still flag the wrong sentence "
        "(see evidence recall in the README). Sentences are clipped to 300 characters. "
        "Labels are the frozen v1 gold set. The Lone Star (18845) independent testing false hit stands. A proposal to "
        "label it positive was rejected on 15 Nov 2026, because the sentence summarises the OCC's own earlier action "
        "in a separate section, not FinCEN's Determinations.",
        "",
        "| Category | Misses | False hits |",
        "| --- | ---: | ---: |",
    ]
    for category in CATEGORIES:
        entry = failures[category]
        lines.append(f"| {LABELS[category]} | {len(entry['misses'])} | {len(entry['false_hits'])} |")
    for category in CATEGORIES:
        entry = failures[category]
        if not (entry["misses"] or entry["false_hits"]):
            continue
        lines.extend(["", f"## {LABELS[category]}"])
        if entry["misses"]:
            lines.extend(["", "Missed (gold quote):", "", *_failure_entries(entry["misses"], titles)])
        if entry["false_hits"]:
            lines.extend(
                ["", "False hit (flagged sentence):", "", *_failure_entries(entry["false_hits"], titles)]
            )
    return "\n".join(lines) + "\n"


def write_readme(readme, out, metrics, v2, titles):
    """Copy the README to out, replacing only the text between the result markers."""
    text = Path(readme).read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise SystemExit(f"{readme} must contain {START} and {END} once each, in that order")
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(before + render_results(metrics, v2, titles) + after, encoding="utf-8")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results", help="directory holding metrics.json")
    parser.add_argument("--readme", help="README to render into")
    parser.add_argument("--out", help="where to write the rendered README")
    parser.add_argument("--failures", help="failures.json to render")
    parser.add_argument("--failures-out", help="where to write the rendered failure analysis")
    return parser


def _titles():
    return {entry["id"]: entry["title"].removeprefix("In the Matter of ") for entry in load_index(DATA_DIR)}


def _write_failures(args):
    if args.failures_out is None:
        raise SystemExit("--failures-out is required with --failures")
    failures = json.loads(Path(args.failures).read_text(encoding="utf-8"))
    out = Path(args.failures_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_failures(failures, _titles()), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.failures:
        return _write_failures(args)
    metrics = load_metrics(args.results)
    if args.readme is None:
        print(summary(metrics))
        return 0
    if args.out is None:
        raise SystemExit("--out is required with --readme")
    titles = _titles()
    v2_path = Path(args.results) / "gold-v2.json"
    v2 = json.loads(v2_path.read_text(encoding="utf-8")) if v2_path.exists() else None
    write_readme(args.readme, args.out, metrics, v2, titles)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
