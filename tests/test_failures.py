import unittest

from demo import render_failures
from examcheck import DATA_DIR
from examcheck.corpus import grounded, load_orders
from examcheck.failures import failures
from examcheck.run import metrics
from examcheck.taxonomy import CATEGORIES, LABELS


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


if __name__ == "__main__":
    unittest.main()
