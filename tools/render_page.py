"""Render docs/index.html from tools/page_template.html, results/*.json and a review of the synthetic log."""

import html
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from examcheck.review import review  # noqa: E402
from examcheck.synth import make_suite  # noqa: E402

AS_OF = date(2021, 3, 29)
CATEGORIES = [
    "Alert backlog",
    "Late SAR",
    "SAR not filed",
    "Unsupported disposition",
    "Monitoring gap",
    "CDD / EDD",
    "CTR filing",
    "Staffing",
    "Independent testing",
    "Governance",
]
CHECKS = ["late_sar", "aged_alert", "no_rationale", "prior_filing_only"]
FIELDS = ("check", "alert_id", "status", "reason", "order_id")


def _load(name):
    return json.loads((ROOT / "results" / name).read_text(encoding="utf-8"))


def _f(x):
    return f"{x:.3f}"


def _tiles(m):
    items = [
        (m["orders"], f"included orders of {m['orders_listed']} listed ({m['orders_no_text']} scanned with no text, {m['orders_individual']} against individuals)"),
        (m["findings"], f"baseline findings, {_f(m['findings_grounded'])} of them found verbatim in the order text"),
        (_f(m["micro_f1"]), f"micro F1 against {m['gold_orders']} labelled orders (v1)"),
        (f"{m['evidence_recall'] * 100:.1f}%", "evidence recall: gold quotes overlapped by a flagged sentence"),
    ]  # fmt: skip
    return "".join(
        f'<div class="tile"><span class="big num">{a}</span><span class="small muted">{html.escape(b)}</span></div>'
        for a, b in items
    )


def _bars(m):
    return "".join(
        f'<div class="b"><span class="name">{c}</span><span class="track"><span class="fill" '
        f'style="width:{m["f1"][i] * 100:.1f}%"></span></span><span class="v"><b class="num">{_f(m["f1"][i])}</b></span></div>'
        for i, c in enumerate(CATEGORIES)
    )


def _category_rows(m, fail):
    rows = []
    for i, (c, key) in enumerate(zip(CATEGORIES, fail, strict=True)):
        cells = [round(m["gold_share"][i] * m["gold_orders"]), _f(m["precision"][i]), _f(m["recall"][i]),
                 _f(m["f1"][i]), len(fail[key]["misses"]), len(fail[key]["false_hits"])]  # fmt: skip
        rows.append(f"<tr><td>{c}</td>" + "".join(f'<td class="r">{x}</td>' for x in cells) + "</tr>")
    return "".join(rows)


def _check_rows(m):
    rows = []
    for i, c in enumerate(CHECKS):
        cells = [f"{m['seeded'][i]:,}", *(_f(m[k][i]) for k in ("detection_rate", "false_flag_rate", "naive_detection_rate", "naive_false_flag_rate"))]  # fmt: skip
        rows.append(
            f"<tr><td><code>{c}</code></td>" + "".join(f'<td class="r">{x}</td>' for x in cells) + "</tr>"
        )
    return "".join(rows)


def _example(finding):
    shown = {k: asdict(finding)[k] for k in FIELDS}
    return html.escape(json.dumps(shown, indent=1)), html.escape(finding.quote)


def values():
    m, v2, fail = _load("metrics.json"), _load("gold-v2.json"), _load("failures.json")
    findings = review(make_suite(), AS_OF)
    count = Counter(f.status for f in findings)
    defect = findings[0]
    risk = next(f for f in findings if f.status == "risk")
    defect_json, defect_quote = _example(defect)
    risk_json, risk_quote = _example(risk)
    return {
        "TILES": _tiles(m), "BARS": _bars(m), "ROWS": _category_rows(m, fail), "CROWS": _check_rows(m),
        "V1P": _f(m["micro_precision"]), "V1R": _f(m["micro_recall"]), "V1F": _f(m["micro_f1"]), "V1M": _f(m["macro_f1"]),
        "V2P": _f(v2["micro_precision"]), "V2R": _f(v2["micro_recall"]), "V2F": _f(v2["micro_f1"]), "V2M": _f(v2["macro_f1"]),
        "WORDS": f"{m['words']:,}", "SENT": f"{m['sentences']:,}", "ER": _f(m["evidence_recall"]),
        "GP": m["gold_positives"], "COV": round(m["evidence_recall"] * m["gold_positives"]),
        "DEF": f"{count['defect']:,}", "RISK": f"{count['risk']:,}", "CA": f"{count['cannot_assess']:,}",
        "DEFECT": defect_json, "DEFQ": defect_quote, "RISKJ": risk_json, "RISKQ": risk_quote,
    }  # fmt: skip


def render():
    page = (ROOT / "tools" / "page_template.html").read_text(encoding="utf-8")
    for key, value in values().items():
        page = page.replace(f"@{key}@", str(value))
    return page


if __name__ == "__main__":
    (ROOT / "docs" / "index.html").write_text(render(), encoding="utf-8")
