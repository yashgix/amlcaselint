import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from amlcaselint import DATA_DIR
from amlcaselint.cases import read_log
from amlcaselint.checks import CHECKS, run_checks
from amlcaselint.cli import main as cli_main
from amlcaselint.corpus import grounded, load_orders
from amlcaselint.run import metrics
from amlcaselint.synth import (
    DEFAULT,
    KINDS,
    NEAR_MISSES,
    SOURCES,
    days_late,
    kind_counts,
    make_suite,
    stride,
    truth,
)


class SynthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = {order.id: order.text for order in load_orders(DATA_DIR)}

    def test_sources_grounded(self):
        for name, (source, quote) in SOURCES.items():
            self.assertIn(source, self.orders)
            self.assertTrue(grounded(quote, self.orders[source]), name)

    def test_kind_counts_defaults(self):
        counts = kind_counts(DEFAULT)
        self.assertEqual(list(counts), list(KINDS))
        self.assertEqual(counts["closed_aged"], 8000)
        self.assertEqual(counts["closed_no_rationale"], 1000)
        self.assertEqual(counts["closed_prior_filing"], 1000)
        self.assertEqual(counts["closed_clean"], 10000)
        self.assertEqual(counts["open_backlog"], 10000)
        self.assertEqual(counts["sar_late"], 300)
        self.assertEqual(counts["sar_on_time"], 2700)
        for kind in NEAR_MISSES:
            self.assertEqual(counts[kind], 200)
        self.assertEqual(sum(counts.values()), 33800)

    def test_stride_and_days_late(self):
        self.assertEqual(stride(0, 335), 0)
        self.assertEqual(stride(1, 335), 7919 % 335)
        self.assertEqual(stride(2, 335), (2 * 7919) % 335)
        self.assertEqual(days_late(0, 1, 119), 119)
        self.assertEqual([days_late(j, 5, 10) for j in range(5)], [1, 5, 10, 14, 19])

    def test_make_suite_defaults(self):
        alerts = make_suite()
        self.assertEqual(len(alerts), sum(kind_counts(DEFAULT).values()))
        for index, alert in enumerate(alerts, 1):
            self.assertEqual(alert.alert_id, f"A{index:06d}")
        self.assertEqual({alert.kind for alert in alerts}, set(KINDS))

    def test_truth_matches_strict_checks(self):
        alerts = make_suite()
        seeded = truth(alerts)
        strict = run_checks(alerts, DEFAULT.as_of)
        self.assertEqual(seeded, {check: set(strict[check]) for check in CHECKS})
        self.assertEqual(set(seeded), set(CHECKS))


class CliTests(unittest.TestCase):
    def test_findings_writes_json_lines(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli_main(["findings", "--order", "19518", "--data", str(DATA_DIR)]), 0)
        lines = out.getvalue().strip().splitlines()
        self.assertTrue(lines)
        for line in lines:
            row = json.loads(line)
            self.assertEqual(row["order_id"], "19518")
            self.assertIn("category", row)
            self.assertIn("start", row)
            self.assertIn("quote", row)
            self.assertIn("counts", row)

    def test_synth_and_check_subcommands(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "synthetic.jsonl"
            self.assertEqual(cli_main(["synth", "--out", str(log)]), 0)
            alerts = read_log(log)
            self.assertEqual(len(alerts), sum(kind_counts(DEFAULT).values()))

            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli_main(["check", str(log), "--as-of", "2021-03-29"]), 0)
            result = json.loads(out.getvalue())
            self.assertEqual(list(result), list(CHECKS))

            out_flag = io.StringIO()
            with redirect_stdout(out_flag):
                self.assertEqual(cli_main(["check", str(log), "--as-of", "2021-03-29", "--cannot-assess"]), 0)
            flagged = json.loads(out_flag.getvalue())
            self.assertEqual(list(flagged), [*CHECKS, "cannot_assess"])
            self.assertEqual({k: v for k, v in flagged.items() if k != "cannot_assess"}, result)
            self.assertEqual(flagged["cannot_assess"], {check: [] for check in CHECKS})

            out_naive = io.StringIO()
            with redirect_stdout(out_naive):
                self.assertEqual(
                    cli_main(["check", str(log), "--as-of", "2021-03-29", "--naive"]),
                    0,
                )
            naive_result = json.loads(out_naive.getvalue())
            self.assertEqual(list(naive_result), list(CHECKS))


class RunMetricsTests(unittest.TestCase):
    EXPECTED_KEYS = frozenset(
        {
            "baseline_gold_share",
            "basis_quotes",
            "basis_quotes_grounded",
            "cases",
            "cited_alerts",
            "cited_sars",
            "corpus_orders",
            "corpus_share",
            "detection_rate",
            "evidence_recall",
            "f1",
            "false_flag_rate",
            "findings",
            "findings_grounded",
            "flagged",
            "gold_orders",
            "gold_positives",
            "gold_quotes",
            "gold_quotes_grounded",
            "gold_share",
            "late_sar_mean_days_late",
            "macro_f1",
            "micro_f1",
            "micro_precision",
            "micro_recall",
            "naive_detection_rate",
            "naive_false_flag_rate",
            "naive_flagged",
            "near_misses",
            "orders",
            "orders_individual",
            "orders_listed",
            "orders_no_text",
            "precision",
            "recall",
            "seeded",
            "sentences",
            "words",
        }
    )

    def test_metrics_keys(self):
        result = metrics(DATA_DIR)
        self.assertEqual(set(result), self.EXPECTED_KEYS)

    def test_metrics_determinism(self):
        self.assertEqual(metrics(DATA_DIR), metrics(DATA_DIR))


if __name__ == "__main__":
    unittest.main()
