"""Print the examcheck summary and render the README results block from metrics.json."""

import argparse
import json
from pathlib import Path

from examcheck import DATA_DIR
from examcheck.checks import BASIS, CHECKS
from examcheck.corpus import REGULATION, load_index
from examcheck.taxonomy import CATEGORIES, LABELS

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


def _baseline_sentence(metrics):
    return (
        f"Baseline on {metrics['gold_orders']} gold orders: "
        f"micro precision {metrics['micro_precision']:.3f}, "
        f"micro recall {metrics['micro_recall']:.3f}, "
        f"micro F1 {metrics['micro_f1']:.3f}; "
        f"macro F1 {metrics['macro_f1']:.3f}."
    )


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


def render_results(metrics, titles):
    """Render the results block, markers included, from the metrics."""
    lines = [
        START,
        "",
        _corpus_sentence(metrics),
        "",
        _baseline_sentence(metrics),
        "",
        "### Gold set by category",
        "",
        *_category_table(metrics),
        "",
        "### Checks on the synthetic alert log",
        "",
        *_check_table(metrics),
        "",
        *_basis_section(titles),
        END,
    ]
    return "\n".join(lines)


def write_readme(readme, out, metrics, titles):
    """Copy the README to out, replacing only the text between the result markers."""
    text = Path(readme).read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise SystemExit(f"{readme} must contain {START} and {END} once each, in that order")
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(before + render_results(metrics, titles) + after, encoding="utf-8")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results", help="directory holding metrics.json")
    parser.add_argument("--readme", help="README to render into")
    parser.add_argument("--out", help="where to write the rendered README")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    metrics = load_metrics(args.results)
    if args.readme is None:
        print(summary(metrics))
        return 0
    if args.out is None:
        raise SystemExit("--out is required with --readme")
    titles = {entry["id"]: entry["title"].removeprefix("In the Matter of ") for entry in load_index(DATA_DIR)}
    write_readme(args.readme, args.out, metrics, titles)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
