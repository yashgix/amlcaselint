import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

from amlcaselint import DATA_DIR
from amlcaselint.cases import Alert, write_log
from amlcaselint.checks import BASIS, CHECKS, run_checks
from amlcaselint.cli import main as cli_main
from amlcaselint.corpus import grounded, load_orders, regulation_text
from amlcaselint.review import CANNOT_ASSESS, DEFECT, RISK, review
from amlcaselint.synth import DEFAULT, make_suite

D0 = date(2024, 1, 1)
AS_OF = date(2024, 12, 31)


def day(n):
    return D0 + timedelta(days=n)


def only(alert, check):
    return [f for f in review([alert], AS_OF) if f.check == check]


class StatusTests(unittest.TestCase):
    def test_late_filing_is_defect(self):
        alert = Alert("a", D0, detected=D0, disposition="sar", sar_filed=day(31))
        (finding,) = only(alert, "late_sar")
        self.assertEqual((finding.status, finding.order_id), (DEFECT, "19518"))

    def test_decided_but_unfiled_sar_is_defect(self):
        alert = Alert("a", D0, detected=D0, disposition="sar")
        self.assertEqual(only(alert, "late_sar")[0].status, DEFECT)

    def test_undecided_open_alert_past_deadline_is_risk(self):
        alert = Alert("a", D0, detected=D0)
        self.assertEqual(only(alert, "late_sar")[0].status, RISK)

    def test_on_time_filing_has_no_finding(self):
        alert = Alert("a", D0, detected=D0, disposition="sar", sar_filed=day(30))
        self.assertEqual(only(alert, "late_sar"), [])

    def test_missing_detection_date_cannot_be_assessed(self):
        alert = Alert("a", D0, disposition="sar", sar_filed=day(90))
        self.assertEqual(only(alert, "late_sar")[0].status, CANNOT_ASSESS)

    def test_aged_alert_is_defect(self):
        alert = Alert("a", D0, closed=day(31), disposition="no_sar", rationale="r", evidence=("e",))
        self.assertEqual(only(alert, "aged_alert")[0].status, DEFECT)

    def test_blank_rationale_is_defect(self):
        alert = Alert(
            "a", D0, closed=day(2), disposition="no_sar", evidence=("e",), reasons=("false_positive",)
        )
        self.assertEqual(only(alert, "no_rationale")[0].status, DEFECT)

    def test_prior_filing_only_is_risk(self):
        alert = Alert(
            "a",
            D0,
            closed=day(2),
            disposition="no_sar",
            rationale="r",
            evidence=("e",),
            reasons=("prior_sar",),
        )
        self.assertEqual(only(alert, "prior_filing_only")[0].status, RISK)

    def test_closure_without_reason_codes_cannot_be_assessed(self):
        alert = Alert("a", D0, closed=day(2), disposition="no_sar", rationale="r", evidence=("e",))
        self.assertEqual(only(alert, "prior_filing_only")[0].status, CANNOT_ASSESS)

    def test_regulation_quote_follows_suspect_known(self):
        known = Alert("a", D0, detected=D0, disposition="sar", sar_filed=day(40))
        unknown = Alert("b", D0, detected=D0, disposition="sar", sar_filed=day(70), suspect_known=False)
        self.assertEqual(only(known, "late_sar")[0].regulation_quote, BASIS["late_sar"][0][1])
        self.assertEqual(only(unknown, "late_sar")[0].regulation_quote, BASIS["late_sar"][1][1])


class ConsistencyTests(unittest.TestCase):
    def test_defects_and_risks_are_exactly_the_check_flags(self):
        alerts = make_suite()
        flags = run_checks(alerts, DEFAULT.as_of)
        findings = review(alerts, DEFAULT.as_of)
        for check in CHECKS:
            ids = [f.alert_id for f in findings if f.check == check and f.status != CANNOT_ASSESS]
            self.assertEqual(ids, flags[check], check)

    def test_quotes_are_grounded(self):
        texts = {order.id: order.text for order in load_orders(DATA_DIR)}
        regulation = regulation_text(DATA_DIR)
        alerts = [
            Alert("a", D0, detected=D0, disposition="sar", sar_filed=day(40)),
            Alert("b", D0, closed=day(40), disposition="no_sar", reasons=("prior_ctr",)),
        ]
        for finding in review(alerts, AS_OF):
            self.assertTrue(grounded(finding.quote, texts[finding.order_id]), finding)
            if finding.regulation_quote:
                self.assertTrue(grounded(finding.regulation_quote, regulation))


class ReviewCommandTests(unittest.TestCase):
    def test_json_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.jsonl"
            write_log(log, [Alert("a", D0, detected=D0)])
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli_main(["review", str(log), "--as-of", "2024-12-31"]), 0)
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(
            [(r["check"], r["alert_id"], r["status"]) for r in rows],
            [("late_sar", "a", RISK), ("aged_alert", "a", DEFECT)],
        )


if __name__ == "__main__":
    unittest.main()
