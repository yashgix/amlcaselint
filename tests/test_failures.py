import unittest

from amlcaselint import DATA_DIR
from amlcaselint.corpus import grounded, load_orders
from amlcaselint.failures import failures
from amlcaselint.run import gold_v2_metrics, metrics
from amlcaselint.score import load_gold
from amlcaselint.taxonomy import CATEGORIES, LABELS
from demo import render_failures


class FailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = failures(DATA_DIR)

    def test_every_category_present_in_order(self):
        self.assertEqual(list(self.result), list(CATEGORIES))

    def test_misses_agree_with_recall(self):
        gold = metrics(DATA_DIR)
        for index, category in enumerate(CATEGORIES):
            labelled = round(gold["gold_share"][index] * gold["gold_orders"])
            hits = labelled - len(self.result[category]["misses"])
            self.assertAlmostEqual(gold["recall"][index], hits / labelled, places=5, msg=category)

    def test_quotes_come_from_the_orders(self):
        texts = {order.id: order.text for order in load_orders(DATA_DIR)}
        for category in CATEGORIES:
            for kind in ("misses", "false_hits"):
                for row in self.result[category][kind]:
                    self.assertTrue(row["quotes"], (category, row["order_id"]))
                    for quote in row["quotes"]:
                        self.assertTrue(grounded(quote, texts[row["order_id"]]), (category, quote))

    def test_render_lists_each_category_row(self):
        text = render_failures(self.result, {})
        for category in CATEGORIES:
            self.assertIn(f"| {LABELS[category]} |", text)


class GoldV2Tests(unittest.TestCase):
    def test_v2_adds_exactly_the_listed_label(self):
        v1 = load_gold(DATA_DIR)
        v2 = load_gold(DATA_DIR, "gold-v2.json")
        added = [(o, c) for o in v2 for c in v2[o] if c not in v1.get(o, {})]
        self.assertEqual(added, [("18845", "independent_testing")])
        self.assertTrue(all(v1[o][c] == v2[o][c] for o in v1 for c in v1[o]))
        texts = {order.id: order.text for order in load_orders(DATA_DIR)}
        self.assertTrue(grounded(v2["18845"]["independent_testing"][0], texts["18845"]))

    def test_v2_scores_differ_from_v1_only_by_that_label(self):
        v2 = gold_v2_metrics(DATA_DIR)
        self.assertEqual(v2["gold_positives"], metrics(DATA_DIR)["gold_positives"] + 1)
        self.assertGreater(v2["micro_f1"], metrics(DATA_DIR)["micro_f1"])


if __name__ == "__main__":
    unittest.main()
