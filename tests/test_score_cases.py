import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from examcheck import DATA_DIR
from examcheck.cases import REASONS, Alert, from_json, read_log, to_json, write_log
from examcheck.extract import Finding
from examcheck.score import category_scores, confusion, evidence_recall, load_gold, prf


class GoldScoreTests(unittest.TestCase):
    def test_load_gold(self):
        gold = load_gold()
        raw = json.loads((DATA_DIR / "gold.json").read_text(encoding="utf-8"))
        self.assertEqual(len(gold), 15)
        self.assertIn("labeller", raw)
        self.assertIn("method", raw)

    def test_prf_zero_denominators(self):
        self.assertEqual(prf(0, 0, 0), (0.0, 0.0, 0.0))
        self.assertEqual(prf(1, 1, 1), (0.5, 0.5, 0.5))
        self.assertEqual(prf(0, 1, 0), (0.0, 0.0, 0.0))

    def test_confusion_over_gold_orders_only(self):
        gold = {"a": {"late_sar": ["quote"]}, "b": {}}
        self.assertEqual(confusion(gold, {"a": {"late_sar"}}, "late_sar"), (1, 0, 0))
        self.assertEqual(confusion(gold, {"b": {"late_sar"}}, "late_sar"), (0, 1, 1))
        self.assertEqual(confusion(gold, {}, "late_sar"), (0, 0, 1))

    def test_category_scores_shapes_and_micro_macro(self):
        gold = {"a": {"alert_backlog": ["x"]}}
        predicted = {"a": {"alert_backlog"}}
        per, micro, macro = category_scores(gold, predicted)
        self.assertEqual(len(per), 10)
        self.assertEqual(per[0], (1.0, 1.0, 1.0))
        self.assertEqual(micro, (1.0, 1.0, 1.0))
        self.assertAlmostEqual(macro, 0.1)

    def test_evidence_recall(self):
        text = "The Bank had a backlog of 5,000 alerts."
        gold = {"1": {"alert_backlog": ["a backlog of 5,000 alerts"]}}
        findings = [Finding("1", "alert_backlog", 0, text, ())]
        self.assertEqual(evidence_recall(gold, findings, {"1": text}), 1.0)

    def test_evidence_recall_miss_and_empty(self):
        text = "The Bank had a backlog of 5,000 alerts."
        gold = {"1": {"alert_backlog": ["missing quote"]}}
        findings = [Finding("1", "alert_backlog", 0, "another sentence", ())]
        self.assertEqual(evidence_recall(gold, findings, {"1": text}), 0.0)
        self.assertEqual(evidence_recall({}, [], {}), 0.0)


class CasesTests(unittest.TestCase):
    def test_reasons_tuple(self):
        self.assertEqual(
            REASONS,
            (
                "activity_reviewed",
                "customer_explained",
                "expected_activity",
                "false_positive",
                "prior_sar",
                "prior_ctr",
            ),
        )

    def test_alert_defaults(self):
        alert = Alert("A1", date(2024, 1, 1))
        self.assertEqual(alert.alert_id, "A1")
        self.assertEqual(alert.opened, date(2024, 1, 1))
        self.assertIsNone(alert.detected)
        self.assertIsNone(alert.closed)
        self.assertIsNone(alert.disposition)
        self.assertIsNone(alert.sar_filed)
        self.assertTrue(alert.suspect_known)
        self.assertEqual(alert.rationale, "")
        self.assertEqual(alert.evidence, ())
        self.assertEqual(alert.reasons, ())
        self.assertEqual(alert.kind, "")

    def test_to_json_from_json_inverse(self):
        alert = Alert(
            "A1",
            date(2024, 1, 1),
            date(2024, 1, 2),
            date(2024, 1, 3),
            "sar",
            date(2024, 1, 4),
            False,
            "reason",
            ("txn:1", "profile:1"),
            ("prior_sar", "activity_reviewed"),
            "sar_late",
        )
        row = to_json(alert)
        self.assertEqual(row["detected"], "2024-01-02")
        self.assertEqual(row["evidence"], ["txn:1", "profile:1"])
        self.assertEqual(row["reasons"], ["prior_sar", "activity_reviewed"])
        self.assertEqual(from_json(row), alert)

    def test_from_json_ignores_unknown_keys_and_uses_defaults(self):
        row = {"alert_id": "A1", "opened": "2024-01-01", "extra": 123}
        alert = from_json(row)
        self.assertEqual(alert.alert_id, "A1")
        self.assertEqual(alert.opened, date(2024, 1, 1))
        self.assertIsNone(alert.detected)
        self.assertEqual(alert.rationale, "")
        self.assertEqual(alert.evidence, ())

    def test_write_and_read_log(self):
        first = Alert("A1", date(2024, 1, 1))
        second = Alert(
            "A2",
            date(2024, 1, 2),
            closed=date(2024, 1, 3),
            disposition="no_sar",
            rationale="ok",
            evidence=("txn:2",),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alerts.jsonl"
            write_log(path, [first, second])
            self.assertEqual(read_log(path), [first, second])
            path.write_text(
                json.dumps(to_json(first)) + chr(10) + chr(10) + json.dumps(to_json(second)) + chr(10),
                encoding="utf-8",
            )
            self.assertEqual(read_log(path), [first, second])


if __name__ == "__main__":
    unittest.main()
