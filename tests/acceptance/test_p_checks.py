import contextlib
import dataclasses
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from amlcaselint import DATA_DIR
from amlcaselint.cases import Alert, from_json, read_log, to_json, write_log
from amlcaselint.checks import (
    BASIS,
    CHECKS,
    POLICY_DAYS,
    aged_alert,
    aged_alert_naive,
    late_sar,
    late_sar_naive,
    no_rationale,
    no_rationale_naive,
    prior_filing_naive,
    prior_filing_only,
    run_checks,
    sar_deadline,
)
from amlcaselint.cli import main as cli
from amlcaselint.corpus import REGULATION, grounded, load_orders, regulation_text
from amlcaselint.run import main, metrics
from amlcaselint.synth import DEFAULT, KINDS, SOURCES, VIOLATIONS, Params, days_late, kind_counts, make_suite, truth

D0 = date(2020, 1, 1)
AS_OF = date(2021, 3, 29)
LISTS = {
    10: ("corpus_orders", "corpus_share", "gold_share", "baseline_gold_share", "precision", "recall", "f1"),
    39: ("cited_alerts", "cited_sars"),
    4: (
        "seeded",
        "flagged",
        "detection_rate",
        "false_flag_rate",
        "naive_flagged",
        "naive_detection_rate",
        "naive_false_flag_rate",
    ),
}
SCALARS = (
    "orders_listed",
    "orders",
    "orders_no_text",
    "orders_individual",
    "words",
    "sentences",
    "findings",
    "findings_grounded",
    "gold_orders",
    "gold_positives",
    "gold_quotes",
    "gold_quotes_grounded",
    "micro_precision",
    "micro_recall",
    "micro_f1",
    "macro_f1",
    "evidence_recall",
    "basis_quotes",
    "basis_quotes_grounded",
    "cases",
    "near_misses",
    "late_sar_mean_days_late",
)


def day(n):
    return D0 + timedelta(days=n)


def sar(detect, filed, known=True, disposition="sar"):
    return Alert(
        "A1",
        D0,
        detected=day(detect),
        closed=day(detect),
        disposition=disposition,
        sar_filed=None if filed is None else day(filed),
        suspect_known=known,
    )


def closed(rationale="checked", evidence=("txn:1",), reasons=("activity_reviewed",), after=5):
    return Alert(
        "A2", D0, closed=day(after), disposition="no_sar", rationale=rationale, evidence=evidence, reasons=reasons
    )


class CaseLog(unittest.TestCase):
    def test_round_trip(self):
        alerts = [sar(3, 20, known=False), closed(), Alert("A3", D0, kind="open_backlog")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            write_log(path, alerts)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            row = json.loads(lines[0])
            self.assertEqual(row["sar_filed"], "2020-01-21")
            self.assertEqual(row["closed"], "2020-01-04")
            self.assertEqual(json.loads(lines[2])["closed"], None)
            self.assertEqual(read_log(path), alerts)
        self.assertEqual(to_json(alerts[1])["evidence"], ["txn:1"])

    def test_from_json_defaults(self):
        alert = from_json({"alert_id": "X", "opened": "2020-01-01", "extra": 1})
        self.assertEqual(alert, Alert("X", D0))
        self.assertEqual(alert.kind, "")


class Checks(unittest.TestCase):
    def test_deadline(self):
        self.assertEqual(sar_deadline(sar(2, None)), day(32))
        self.assertEqual(sar_deadline(sar(2, None, known=False)), day(62))

    def test_late_sar_boundaries(self):
        self.assertFalse(late_sar(sar(0, 30), AS_OF))
        self.assertTrue(late_sar(sar(0, 31), AS_OF))
        self.assertFalse(late_sar(sar(0, 60, known=False), AS_OF))
        self.assertTrue(late_sar(sar(0, 61, known=False), AS_OF))
        self.assertFalse(late_sar(sar(20, 45), AS_OF))
        self.assertFalse(late_sar(Alert("A", D0), AS_OF))

    def test_late_sar_not_yet_filed(self):
        self.assertTrue(late_sar(sar(0, None), day(31)))
        self.assertFalse(late_sar(sar(0, None), day(30)))
        self.assertTrue(late_sar(dataclasses.replace(sar(0, None), closed=None, disposition=None), day(31)))
        self.assertFalse(late_sar(sar(0, None, disposition="no_sar"), day(400)))

    def test_aged_alert(self):
        self.assertFalse(aged_alert(closed(after=POLICY_DAYS), AS_OF))
        self.assertTrue(aged_alert(closed(after=POLICY_DAYS + 1), AS_OF))
        self.assertTrue(aged_alert(Alert("A", D0), day(31)))
        self.assertFalse(aged_alert(Alert("A", D0), day(30)))
        self.assertFalse(aged_alert(closed(after=40), AS_OF, policy_days=45))
        self.assertEqual(POLICY_DAYS, 30)

    def test_no_rationale(self):
        self.assertFalse(no_rationale(closed()))
        self.assertTrue(no_rationale(closed(rationale=" \n")))
        self.assertTrue(no_rationale(closed(evidence=())))
        self.assertFalse(no_rationale(Alert("A", D0)))

    def test_prior_filing_only(self):
        self.assertTrue(prior_filing_only(closed(reasons=("prior_sar",))))
        self.assertTrue(prior_filing_only(closed(reasons=("prior_ctr", "prior_sar"))))
        self.assertFalse(prior_filing_only(closed(reasons=("prior_sar", "activity_reviewed"))))
        self.assertFalse(prior_filing_only(closed(reasons=())))
        self.assertFalse(prior_filing_only(dataclasses.replace(closed(reasons=("prior_sar",)), disposition="sar")))

    def test_naive_versions(self):
        self.assertTrue(late_sar_naive(sar(20, 45), AS_OF))
        self.assertTrue(late_sar_naive(sar(0, 45, known=False), AS_OF))
        self.assertFalse(late_sar_naive(sar(0, 30), AS_OF))
        self.assertFalse(late_sar_naive(closed(), AS_OF))
        self.assertFalse(aged_alert_naive(closed(after=90), AS_OF))
        self.assertTrue(aged_alert_naive(Alert("A", D0), day(31)))
        self.assertFalse(no_rationale_naive(closed(evidence=())))
        self.assertTrue(no_rationale_naive(closed(rationale="")))
        self.assertTrue(prior_filing_naive(closed(rationale="A SAR was previously filed; activity reviewed.")))
        self.assertTrue(prior_filing_naive(closed(rationale="see prior CTR")))
        self.assertFalse(prior_filing_naive(closed(reasons=("prior_sar",), rationale="Reviewed.")))

    def test_run_checks_ignores_kind(self):
        alerts = [sar(0, 31), closed(after=31), closed(reasons=("prior_sar",)), closed(evidence=())]
        flags = run_checks(alerts, AS_OF)
        self.assertEqual(list(flags), list(CHECKS))
        relabelled = [dataclasses.replace(a, kind="closed_clean") for a in alerts]
        self.assertEqual(run_checks(relabelled, AS_OF), flags)
        self.assertEqual(flags["late_sar"], ["A1"])
        self.assertEqual(run_checks(alerts, AS_OF, naive=True)["aged_alert"], [])

    def test_basis_is_grounded(self):
        texts = {o.id: o.text for o in load_orders()} | {REGULATION: regulation_text()}
        self.assertEqual(set(BASIS), set(CHECKS))
        self.assertEqual(sum(len(v) for v in BASIS.values()), 13)
        for check, passages in BASIS.items():
            self.assertTrue(passages)
            for source, quote in passages:
                self.assertTrue(grounded(quote, texts[source]), (check, source))
        self.assertIn(REGULATION, {s for s, _ in BASIS["late_sar"]})


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alerts = make_suite()

    def test_params(self):
        self.assertEqual(DEFAULT, Params())
        self.assertEqual(
            (
                DEFAULT.as_of,
                DEFAULT.policy_days,
                DEFAULT.open_backlog,
                DEFAULT.sars,
                DEFAULT.late_sars,
                DEFAULT.mean_days_late,
                DEFAULT.aged_share,
            ),
            (AS_OF, 30, 10_000, 3_600, 300, 119, 0.40),
        )
        texts = {o.id: o.text for o in load_orders()}
        for name, (source, quote) in SOURCES.items():
            self.assertTrue(hasattr(DEFAULT, name))
            self.assertTrue(grounded(quote, texts[source]), name)

    def test_kind_counts(self):
        self.assertEqual(
            kind_counts(DEFAULT),
            {
                "closed_clean": 10000,
                "closed_aged": 8000,
                "closed_no_rationale": 1000,
                "closed_prior_filing": 1000,
                "open_backlog": 10000,
                "sar_on_time": 2700,
                "sar_late": 300,
                "near_detect_later": 200,
                "near_no_suspect": 200,
                "near_day_limit": 200,
                "near_prior_and_review": 200,
            },
        )
        small = Params(open_backlog=5, sars=40, late_sars=4, closed_no_sar=100, near_misses=2)
        self.assertEqual(sum(kind_counts(small).values()), 100 + 5 + 40 + 2)

    def test_days_late(self):
        self.assertEqual(days_late(0, 300, 119), 1)
        self.assertEqual(days_late(299, 300, 119), 237)
        self.assertEqual(days_late(150, 300, 119), 119)
        self.assertEqual(days_late(0, 1, 119), 119)

    def test_suite_layout(self):
        a = self.alerts
        self.assertEqual(len(a), 33800)
        self.assertEqual([x.alert_id for x in a[:2]] + [a[-1].alert_id], ["A000001", "A000002", "A033800"])
        order = [x.kind for x in a]
        self.assertEqual(sorted(set(order), key=order.index), list(KINDS))
        self.assertEqual(make_suite(), a)
        for x in a:
            dates = [d for d in (x.opened, x.detected, x.closed, x.sar_filed) if d is not None]
            self.assertLessEqual(max(dates), AS_OF)
            self.assertEqual(min(dates), x.opened)

    def test_suite_values(self):
        by_id = {x.alert_id: x for x in self.alerts}
        first = by_id["A000001"]
        self.assertEqual((first.opened, first.closed), (date(2020, 2, 23), date(2020, 2, 24)))
        self.assertEqual(first.disposition, "no_sar")
        self.assertEqual(first.reasons, ("activity_reviewed",))
        backlog = by_id["A020001"]
        self.assertEqual((backlog.opened, backlog.closed, backlog.kind), (date(2021, 2, 26), None, "open_backlog"))
        late = by_id["A033000"]
        self.assertEqual((late.detected, late.sar_filed, late.kind), (date(2019, 8, 31), date(2020, 5, 24), "sar_late"))
        near = by_id["A033001"]
        self.assertEqual(
            (near.opened, near.detected, near.sar_filed), (date(2020, 2, 23), date(2020, 3, 14), date(2020, 3, 25))
        )
        last = by_id["A033800"]
        self.assertEqual(last.reasons, ("prior_sar", "activity_reviewed"))
        missing = [x for x in self.alerts if x.kind == "closed_no_rationale"]
        self.assertEqual(sum(not x.rationale for x in missing), 500)
        self.assertEqual(sum(not x.evidence for x in missing), 500)

    def test_checks_find_exactly_the_seeded_cases(self):
        seeded = truth(self.alerts)
        self.assertEqual(set(seeded), set(VIOLATIONS.values()))
        flags = run_checks(self.alerts, AS_OF)
        for check in CHECKS:
            self.assertEqual(set(flags[check]), seeded[check], check)
        naive = run_checks(self.alerts, AS_OF, naive=True)
        self.assertEqual([len(naive[c]) for c in CHECKS], [1070, 10000, 500, 1200])


class Interfaces(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli(list(argv)), 0)
        return out.getvalue()

    def test_cli_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            write_log(path, [sar(0, 31), closed(reasons=("prior_sar",), rationale="A SAR was previously filed.")])
            flags = json.loads(self.run_cli("check", str(path), "--as-of", "2021-03-29"))
            self.assertEqual(
                flags, {"late_sar": ["A1"], "aged_alert": [], "no_rationale": ["A1"], "prior_filing_only": ["A2"]}
            )
            naive = json.loads(self.run_cli("check", str(path), "--as-of", "2021-03-29", "--naive"))
            self.assertEqual(naive["prior_filing_only"], ["A2"])
            self.assertEqual(naive["aged_alert"], [])

    def test_cli_synth_and_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suite.jsonl"
            self.run_cli("synth", "--out", str(path))
            logged = read_log(path)
            self.assertEqual(len(logged), 33800)
            self.assertTrue(logged == make_suite())
        rows = [json.loads(line) for line in self.run_cli("findings", "--order", "19518").splitlines()]
        self.assertEqual(len(rows), 33)
        self.assertEqual(set(rows[0]), {"order_id", "category", "start", "quote", "counts"})
        self.assertEqual({r["order_id"] for r in rows}, {"19518"})


class Experiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "results" / "metrics.json"
        main(DATA_DIR, cls.out)
        cls.m = json.loads(cls.out.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_names_and_shapes(self):
        names = set(SCALARS) | {n for group in LISTS.values() for n in group}
        self.assertEqual(set(self.m), names)
        for size, group in LISTS.items():
            for name in group:
                self.assertEqual(len(self.m[name]), size, name)
        for name in SCALARS:
            self.assertIsInstance(self.m[name], int | float, name)

    def test_byte_identical_and_sorted(self):
        again = Path(self.tmp.name) / "again.json"
        main(DATA_DIR, again)
        text = self.out.read_text()
        self.assertEqual(again.read_text(), text)
        self.assertEqual(text, json.dumps(metrics(DATA_DIR), sort_keys=True, indent=1) + "\n")

    def test_corpus_values(self):
        m = self.m
        self.assertEqual((m["orders_listed"], m["orders"], m["orders_no_text"], m["orders_individual"]), (50, 39, 8, 3))
        self.assertEqual((m["words"], m["sentences"], m["findings"]), (214908, 6144, 838))
        self.assertEqual(m["findings_grounded"], 1.0)
        self.assertEqual(m["corpus_orders"][:3], [8, 31, 32])
        self.assertEqual(m["corpus_share"][0], round(8 / 39, 6))
        self.assertEqual(m["cited_alerts"][:3], [0, 70000, 10000])
        self.assertEqual(max(m["cited_alerts"]), 120000)
        self.assertEqual(m["cited_sars"][8:10], [2121, 173])

    def test_gold_values(self):
        m = self.m
        self.assertEqual((m["gold_orders"], m["gold_positives"], m["gold_quotes"]), (15, 96, 98))
        self.assertEqual(m["gold_quotes_grounded"], 1.0)
        self.assertEqual(m["recall"][:4], [0.2, 0.846154, 0.916667, 0.6])
        self.assertEqual(m["precision"][1], 0.916667)
        self.assertEqual(m["precision"][6:], [0.8, 0.777778, 0.833333, 0.857143])
        self.assertEqual(m["f1"][:4], [0.333333, 0.88, 0.956522, 0.75])
        self.assertEqual((m["micro_precision"], m["micro_recall"], m["micro_f1"]), (0.91358, 0.770833, 0.836158))
        self.assertEqual((m["macro_f1"], m["evidence_recall"]), (0.787554, 0.541667))
        self.assertEqual(m["gold_share"][1], 0.866667)
        self.assertEqual(m["baseline_gold_share"][1], 0.8)

    def test_check_values(self):
        m = self.m
        self.assertEqual((m["basis_quotes"], m["basis_quotes_grounded"]), (13, 1.0))
        self.assertEqual((m["cases"], m["near_misses"]), (33800, 800))
        self.assertEqual(m["seeded"], [300, 18000, 1000, 1000])
        self.assertEqual(m["flagged"], m["seeded"])
        self.assertEqual((m["detection_rate"], m["false_flag_rate"]), ([1.0] * 4, [0.0] * 4))
        self.assertEqual(m["naive_flagged"], [1070, 10000, 500, 1200])
        self.assertEqual(m["naive_detection_rate"], [1.0, 0.555556, 0.5, 1.0])
        self.assertEqual(m["naive_false_flag_rate"], [round(770 / 33500, 6), 0.0, 0.0, round(200 / 32800, 6)])
        self.assertEqual(m["late_sar_mean_days_late"], 118.503333)

    def test_readme_is_generated(self):
        root = Path(DATA_DIR).parent
        rendered = Path(self.tmp.name) / "README.out.md"
        cmd = [
            sys.executable,
            "demo.py",
            "--readme",
            "README.md",
            "--out",
            str(rendered),
            "--results",
            str(self.out.parent),
        ]
        subprocess.run(cmd, cwd=root, check=True, capture_output=True, timeout=120)
        text = rendered.read_text()
        block = text.split("<!-- results:start -->", 1)[1].split("<!-- results:end -->", 1)[0]
        self.assertIn("0.836", block)
        self.assertIn("| `late_sar` |", block)
        self.assertIn("several hundred SARs an average of approximately 119 days late", block)
        self.assertIn("Shinhan Bank America", block)
        self.assertEqual(text.count("<!-- results:start -->"), 1)
        summary = subprocess.run(
            [sys.executable, "demo.py", "--results", str(self.out.parent)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        self.assertIn("39 orders", summary)
