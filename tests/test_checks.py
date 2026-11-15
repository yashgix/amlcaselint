import unittest
from datetime import date

from examcheck import DATA_DIR
from examcheck.cases import Alert
from examcheck.checks import (
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
from examcheck.corpus import REGULATION, grounded, load_orders, regulation_text


class CheckTests(unittest.TestCase):
    def test_check_names_and_policy_days(self):
        self.assertEqual(CHECKS, ("late_sar", "aged_alert", "no_rationale", "prior_filing_only"))
        self.assertEqual(POLICY_DAYS, 30)

    def test_sar_deadline_known_and_unknown_suspect(self):
        known = Alert("a", date(2024, 1, 1), detected=date(2024, 1, 1))
        unknown = Alert("a", date(2024, 1, 1), detected=date(2024, 1, 1), suspect_known=False)
        self.assertEqual(sar_deadline(known), date(2024, 1, 31))
        self.assertEqual(sar_deadline(unknown), date(2024, 3, 1))

    def test_late_sar_boundaries(self):
        as_of = date(2024, 2, 1)
        detected = date(2024, 1, 1)

        self.assertFalse(late_sar(Alert("a", date(2024, 1, 1)), as_of))
        self.assertFalse(
            late_sar(
                Alert("a", date(2024, 1, 1), detected=detected, sar_filed=date(2024, 1, 31)),
                as_of,
            )
        )
        self.assertTrue(
            late_sar(
                Alert("a", date(2024, 1, 1), detected=detected, sar_filed=date(2024, 2, 1)),
                as_of,
            )
        )
        self.assertFalse(
            late_sar(
                Alert("a", date(2024, 1, 1), detected=detected, disposition="no_sar"),
                as_of,
            )
        )
        self.assertFalse(
            late_sar(
                Alert("a", date(2024, 1, 1), detected=detected, disposition="sar"),
                date(2024, 1, 31),
            )
        )
        self.assertTrue(
            late_sar(
                Alert("a", date(2024, 1, 1), detected=detected, disposition="sar"),
                as_of,
            )
        )
        self.assertFalse(
            late_sar(
                Alert(
                    "a",
                    date(2024, 1, 1),
                    detected=detected,
                    suspect_known=False,
                    sar_filed=date(2024, 3, 1),
                ),
                as_of,
            )
        )
        self.assertTrue(
            late_sar(
                Alert(
                    "a",
                    date(2024, 1, 1),
                    detected=detected,
                    suspect_known=False,
                    sar_filed=date(2024, 3, 2),
                ),
                as_of,
            )
        )

    def test_aged_alert_boundaries(self):
        as_of = date(2024, 2, 1)
        self.assertFalse(aged_alert(Alert("a", date(2024, 1, 1), closed=date(2024, 1, 31)), as_of))
        self.assertTrue(aged_alert(Alert("a", date(2024, 1, 1), closed=date(2024, 2, 1)), as_of))
        self.assertFalse(aged_alert(Alert("a", date(2024, 1, 1)), date(2024, 1, 31)))
        self.assertTrue(aged_alert(Alert("a", date(2024, 1, 1)), as_of))

    def test_no_rationale(self):
        self.assertFalse(no_rationale(Alert("a", date(2024, 1, 1))))
        self.assertTrue(no_rationale(Alert("a", date(2024, 1, 1), closed=date(2024, 1, 2), rationale=" ")))
        self.assertTrue(
            no_rationale(Alert("a", date(2024, 1, 1), closed=date(2024, 1, 2), rationale="ok", evidence=()))
        )
        self.assertFalse(
            no_rationale(
                Alert(
                    "a",
                    date(2024, 1, 1),
                    closed=date(2024, 1, 2),
                    rationale="ok",
                    evidence=("e",),
                )
            )
        )

    def test_prior_filing_only(self):
        def make(reasons, disposition="no_sar"):
            return Alert(
                "a",
                date(2024, 1, 1),
                closed=date(2024, 1, 2),
                disposition=disposition,
                rationale="x",
                evidence=("e",),
                reasons=reasons,
            )

        self.assertFalse(prior_filing_only(make(())))
        self.assertTrue(prior_filing_only(make(("prior_sar",))))
        self.assertTrue(prior_filing_only(make(("prior_ctr",))))
        self.assertTrue(prior_filing_only(make(("prior_sar", "prior_ctr"))))
        self.assertFalse(prior_filing_only(make(("prior_sar", "activity_reviewed"))))
        self.assertFalse(prior_filing_only(make(("prior_sar",), disposition="sar")))

    def test_naive_versions_differ(self):
        late = Alert(
            "a",
            date(2024, 1, 1),
            detected=date(2024, 2, 1),
            disposition="sar",
            sar_filed=date(2024, 2, 2),
        )
        self.assertFalse(late_sar(late, date(2024, 3, 1)))
        self.assertTrue(late_sar_naive(late, date(2024, 3, 1)))

        closed_old = Alert("b", date(2024, 1, 1), closed=date(2024, 2, 2))
        self.assertTrue(aged_alert(closed_old, date(2024, 2, 2)))
        self.assertFalse(aged_alert_naive(closed_old, date(2024, 2, 2)))
        self.assertTrue(aged_alert_naive(Alert("c", date(2024, 1, 1)), date(2024, 2, 2)))

        self.assertTrue(
            no_rationale_naive(Alert("d", date(2024, 1, 1), closed=date(2024, 1, 2), rationale=" "))
        )
        self.assertFalse(
            no_rationale_naive(
                Alert(
                    "e",
                    date(2024, 1, 1),
                    closed=date(2024, 1, 2),
                    rationale="ok",
                    evidence=(),
                )
            )
        )

        self.assertTrue(
            prior_filing_naive(
                Alert(
                    "f",
                    date(2024, 1, 1),
                    closed=date(2024, 1, 2),
                    disposition="no_sar",
                    rationale="previously filed",
                )
            )
        )
        self.assertTrue(
            prior_filing_naive(
                Alert(
                    "g",
                    date(2024, 1, 1),
                    closed=date(2024, 1, 2),
                    disposition="no_sar",
                    rationale="prior SAR",
                )
            )
        )
        self.assertFalse(
            prior_filing_naive(
                Alert(
                    "h",
                    date(2024, 1, 1),
                    closed=date(2024, 1, 2),
                    disposition="no_sar",
                    rationale="reviewed",
                )
            )
        )

    def test_run_checks_order_and_results(self):
        as_of = date(2024, 1, 31)
        alerts = [
            Alert(
                "late",
                date(2024, 1, 1),
                detected=date(2024, 1, 1),
                sar_filed=date(2024, 2, 1),
                disposition="sar",
                rationale="x",
                evidence=("e",),
            ),
            Alert(
                "aged",
                date(2024, 1, 1),
                closed=date(2024, 2, 2),
                disposition="no_sar",
                rationale="x",
                evidence=("e",),
                reasons=("activity_reviewed",),
            ),
            Alert(
                "no",
                date(2024, 1, 1),
                closed=date(2024, 1, 10),
                disposition="no_sar",
                rationale=" ",
                evidence=("e",),
            ),
            Alert(
                "prior",
                date(2024, 1, 1),
                closed=date(2024, 1, 10),
                disposition="no_sar",
                rationale="x",
                evidence=("e",),
                reasons=("prior_ctr",),
            ),
            Alert(
                "clean",
                date(2024, 1, 1),
                closed=date(2024, 1, 10),
                disposition="no_sar",
                rationale="x",
                evidence=("e",),
                reasons=("activity_reviewed",),
            ),
        ]
        strict = run_checks(alerts, as_of)
        self.assertEqual(list(strict), list(CHECKS))
        self.assertEqual(strict["late_sar"], ["late"])
        self.assertEqual(strict["aged_alert"], ["aged"])
        self.assertEqual(strict["no_rationale"], ["no"])
        self.assertEqual(strict["prior_filing_only"], ["prior"])

        naive = run_checks(alerts, as_of, naive=True)
        self.assertEqual(list(naive), list(CHECKS))
        self.assertEqual(naive["aged_alert"], [])


class BasisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = {order.id: order.text for order in load_orders(DATA_DIR)}
        cls.regulation = regulation_text(DATA_DIR)

    def test_basis_quotes_grounded(self):
        for check, passages in BASIS.items():
            self.assertIn(check, CHECKS)
            for source, quote in passages:
                text = self.regulation if source == REGULATION else self.orders.get(source, "")
                self.assertTrue(grounded(quote, text), (check, source, quote))


if __name__ == "__main__":
    unittest.main()
