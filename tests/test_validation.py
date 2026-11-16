import json
import tempfile
import unittest
from pathlib import Path

from amlcaselint import cases
from amlcaselint.cases import Alert, from_json, read_log, write_log
from amlcaselint.cli import main as cli_main
from amlcaselint.synth import Params, kind_counts, make_suite

GOOD = {"alert_id": "A", "opened": "2024-01-01", "closed": "2024-01-02", "rationale": "r", "evidence": ["e"]}


class IngestionTests(unittest.TestCase):
    def bad(self, **changes):
        row = {**GOOD, **changes}
        with self.assertRaises(ValueError, msg=changes):
            from_json(row)

    def test_valid_row(self):
        self.assertEqual(from_json(GOOD).evidence, ("e",))

    def test_null_and_wrong_types_rejected(self):
        self.bad(rationale=None)
        self.bad(evidence=None)
        self.bad(evidence="txn:1")
        self.bad(evidence=[1])
        self.bad(reasons="prior_sar")
        self.bad(suspect_known="yes")
        self.bad(alert_id=7)
        self.bad(kind=None)
        self.bad(disposition=3)

    def test_bad_dates_rejected(self):
        for value in ("20240101", "2024-1-1", "2024-02-30", 20240101, None):
            self.bad(opened=value)
        self.bad(closed="01/02/2024")
        self.bad(sar_filed=5)

    def test_missing_keys_and_non_objects_rejected(self):
        for row in ({}, [], "x", 3, None, {"opened": "2024-01-01"}, {"alert_id": "A"}):
            with self.assertRaises(ValueError, msg=row):
                from_json(row)

    def test_optional_dates_may_be_null(self):
        alert = from_json({**GOOD, "detected": None, "sar_filed": None})
        self.assertIsNone(alert.detected)


class LogFileTests(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            path.write_text(text, encoding="utf-8")
            return read_log(path)

    def test_bad_lines_reject_the_log(self):
        for line in ("not json", "{}", "[]", json.dumps({**GOOD, "rationale": None})):
            with self.assertRaises(ValueError, msg=line):
                self.read(line + "\n")

    def test_commands_reject_malformed_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            path.write_text(json.dumps({**GOOD, "rationale": None}) + "\n", encoding="utf-8")
            for command in ("check", "review"):
                with self.assertRaises(ValueError):
                    cli_main([command, str(path), "--as-of", "2024-12-31"])

    def test_line_count_and_length_limits(self):
        row = json.dumps(GOOD)
        original = cases.MAX_LINES
        cases.MAX_LINES = 2
        try:
            self.assertEqual(len(self.read(f"{row}\n{row}\n\n")), 2)
            with self.assertRaises(ValueError):
                self.read(f"{row}\n{row}\n{row}\n")
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                write_log(Path(tmp) / "x.jsonl", [Alert("a", None)] * 3)
        finally:
            cases.MAX_LINES = original
        with self.assertRaises(ValueError):
            self.read(json.dumps({**GOOD, "rationale": "x" * cases.MAX_LINE_CHARS}))


class ParamsTests(unittest.TestCase):
    def test_inconsistent_counts_rejected(self):
        for params in (
            Params(sars=100),
            Params(policy_days=0),
            Params(open_backlog=-1),
            Params(aged_share=1.5),
        ):
            with self.assertRaises(ValueError, msg=params):
                make_suite(params)

    def test_oversized_suite_rejected(self):
        with self.assertRaises(ValueError):
            kind_counts(Params(open_backlog=200_000))

    def test_documented_valid_example(self):
        params = Params(open_backlog=5, sars=40, late_sars=4, closed_no_sar=100, near_misses=2)
        self.assertEqual(len(make_suite(params)), sum(kind_counts(params).values()))


if __name__ == "__main__":
    unittest.main()
