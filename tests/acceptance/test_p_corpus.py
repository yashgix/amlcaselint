import hashlib
import json
import unittest

import examcheck
from examcheck.corpus import Order, grounded, load_index, load_orders, normalize, regulation_text, sentences
from examcheck.extract import Finding, counts, extract, flagged, max_count
from examcheck.score import category_scores, confusion, evidence_recall, load_gold, prf
from examcheck.taxonomy import CATEGORIES, COMPILED, LABELS, PATTERNS

DATA = examcheck.DATA_DIR
PATTERN_SHA = "b34c316636fada761889bc99cce3035836751d73f9052c2b04fea7528608ee80"
CORPUS_ORDERS = [8, 31, 32, 13, 23, 26, 14, 26, 20, 34]


class Data(unittest.TestCase):
    def test_manifest_checksums(self):
        manifest = json.loads((DATA / "MANIFEST.json").read_text())
        self.assertEqual(len(manifest["files"]), 43)
        for name, entry in manifest["files"].items():
            blob = (DATA / name).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(), entry["sha256"], name)
            self.assertEqual(len(blob), entry["bytes"], name)

    def test_index(self):
        index = load_index()
        self.assertEqual(len(index), 50)
        status = [e["status"] for e in index]
        tally = [status.count(s) for s in ("included", "no_text_layer", "individual")]
        self.assertEqual(tally, [39, 8, 3])
        for e in index:
            self.assertEqual(len(e["pdf_sha256"]), 64)
            self.assertEqual(e["text"] is not None, e["status"] == "included")

    def test_load_orders(self):
        orders = load_orders()
        self.assertEqual(len(orders), 39)
        self.assertEqual([o.id for o in orders[:3]], ["22686", "19701", "19518"])
        shinhan = orders[2]
        self.assertIsInstance(shinhan, Order)
        self.assertEqual(shinhan.title, "In the Matter of Shinhan Bank America")
        self.assertEqual(shinhan.date, "2023-09-29")
        self.assertEqual(shinhan.text, normalize(shinhan.text))
        self.assertNotIn("\n", shinhan.text)
        self.assertEqual(sum(len(o.text.split()) for o in orders), 214908)


class Text(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("  a\n\tb   c \n"), "a b c")
        self.assertEqual(normalize(""), "")

    def test_sentence_rule(self):
        parts = [s for _, s in sentences("A b. C d? e f! G. 31 U.S.C. § 5318.")]
        self.assertEqual(parts, ["A b.", "C d? e f!", "G. 31 U.S.C. § 5318."])
        self.assertEqual(sentences("one"), [(0, "one")])

    def test_sentences_are_substrings_at_their_offsets(self):
        orders = load_orders()
        for order in orders[:5]:
            found = sentences(order.text)
            self.assertEqual(" ".join(s for _, s in found), order.text)
            for start, s in found:
                self.assertEqual(order.text[start : start + len(s)], s)
        self.assertEqual(sum(len(sentences(o.text)) for o in orders), 6144)

    def test_grounded(self):
        text = normalize("The Bank filed several hundred SARs\nan average of approximately 119 days late.")
        self.assertTrue(grounded("several hundred SARs an  average", text))
        self.assertTrue(grounded(" SARs\nan ", text))
        self.assertFalse(grounded("several hundred SAR an average", text))
        self.assertFalse(grounded("   ", text))

    def test_regulation_text(self):
        text = regulation_text()
        self.assertEqual(text, normalize(text))
        self.assertIn("A bank is required to file a SAR no later than 30 calendar days after the date of initial", text)
        self.assertIn("In no case shall reporting be delayed more than 60 calendar days", text)
        self.assertNotIn("<", text)


class Baseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = load_orders()
        cls.findings = [f for o in cls.orders for f in extract(o)]

    def test_taxonomy(self):
        self.assertEqual(
            CATEGORIES,
            (
                "alert_backlog",
                "late_sar",
                "sar_not_filed",
                "unsupported_disposition",
                "monitoring_gap",
                "cdd_edd",
                "ctr",
                "staffing",
                "independent_testing",
                "governance",
            ),
        )
        self.assertEqual(set(LABELS), set(CATEGORIES))
        self.assertEqual(set(COMPILED), set(CATEGORIES))

    def test_patterns_are_the_frozen_ones(self):
        blob = json.dumps([list(PATTERNS[c]) for c in CATEGORIES]).encode()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), PATTERN_SHA)
        self.assertTrue(COMPILED["alert_backlog"][0].search("BACKLOG of alerts"))

    def test_counts(self):
        self.assertEqual(
            counts("a backlog of over 10,000 alert events (within more than 700 pre-cases)"), (("alerts", 10000),)
        )
        self.assertEqual(
            counts("Lone Star had 4,888 outstanding alerts, 627 cases, and 213 internal referrals."),
            (("alerts", 4888), ("cases", 627)),
        )
        self.assertEqual(counts("over 70,000 backlogged detection alerts"), (("alerts", 70000),))
        self.assertEqual(counts("an average of approximately 119 days late"), (("days", 119),))
        self.assertEqual(counts("approximately 2000 Currency Transaction Report (“CTR”) forms"), (("ctrs", 2000),))
        self.assertEqual(
            counts("filed 1 SAR and 2,121 SARs and 15 suspicious activity reports"),
            (("sars", 1), ("sars", 2121), ("sars", 15)),
        )
        self.assertEqual(counts("$5,000 alerts and §5318 SARs filed"), ())
        self.assertEqual(counts("no numbers here"), ())

    def test_findings_point_into_the_text(self):
        texts = {o.id: o.text for o in self.orders}
        self.assertEqual(len(self.findings), 838)
        for f in self.findings:
            self.assertIsInstance(f, Finding)
            self.assertEqual(texts[f.order_id][f.start : f.start + len(f.quote)], f.quote)
            self.assertIn(f.category, CATEGORIES)
            self.assertEqual(f.counts, counts(f.quote))
        keys = [(f.order_id, f.start, f.category) for f in self.findings]
        self.assertEqual(len(set(keys)), len(keys))

    def test_shinhan_findings(self):
        shinhan = [f for f in self.findings if f.order_id == "19518"]
        self.assertEqual(len(shinhan), 33)
        backlog = [f for f in shinhan if f.category == "alert_backlog"]
        self.assertEqual([f.start for f in backlog], [18002, 21908, 24797])
        self.assertEqual(backlog[1].counts, (("alerts", 10000),))
        self.assertNotIn("ctr", flagged(shinhan)["19518"])

    def test_corpus_flags(self):
        hits = flagged(self.findings)
        self.assertEqual([sum(c in hits.get(o.id, set()) for o in self.orders) for c in CATEGORIES], CORPUS_ORDERS)

    def test_max_count(self):
        made = [
            Finding("1", "late_sar", 0, "x", (("sars", 5), ("days", 90))),
            Finding("1", "late_sar", 9, "y", (("sars", 12),)),
            Finding("2", "late_sar", 0, "z", (("sars", 99),)),
        ]
        self.assertEqual(max_count(made, "1", "late_sar", "sars"), 12)
        self.assertEqual(max_count(made, "1", "late_sar", "alerts"), 0)
        self.assertEqual(max_count(self.findings, "19701", "alert_backlog", "alerts"), 70000)


class Gold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold = load_gold()
        cls.texts = {o.id: o.text for o in load_orders()}

    def test_gold_set(self):
        self.assertEqual(len(self.gold), 15)
        self.assertEqual(sum(len(labels) for labels in self.gold.values()), 96)
        raw = json.loads((DATA / "gold.json").read_text())
        self.assertIn("not yet spot-checked", raw["labeller"])
        for order_id, labels in self.gold.items():
            self.assertTrue(set(labels) <= set(CATEGORIES))
            for quotes in labels.values():
                self.assertTrue(quotes)
                for q in quotes:
                    self.assertTrue(grounded(q, self.texts[order_id]), (order_id, q))

    def test_prf(self):
        for got, want in zip(prf(3, 1, 2), (0.75, 0.6, 2 / 3), strict=True):
            self.assertAlmostEqual(got, want)
        self.assertEqual(prf(0, 0, 0), (0.0, 0.0, 0.0))
        self.assertEqual(prf(0, 2, 0), (0.0, 0.0, 0.0))
        self.assertEqual(prf(2, 0, 0), (1.0, 1.0, 1.0))

    def test_confusion_and_scores(self):
        gold = {"a": {"ctr": ["q"], "late_sar": ["q"]}, "b": {"ctr": ["q"]}, "c": {}}
        predicted = {"a": {"ctr"}, "c": {"ctr", "staffing"}}
        self.assertEqual(confusion(gold, predicted, "ctr"), (1, 1, 1))
        self.assertEqual(confusion(gold, predicted, "late_sar"), (0, 0, 1))
        self.assertEqual(confusion(gold, predicted, "staffing"), (0, 1, 0))
        per, micro, macro = category_scores(gold, predicted)
        self.assertEqual(len(per), 10)
        self.assertEqual(per[CATEGORIES.index("ctr")], prf(1, 1, 1))
        self.assertEqual(micro, prf(1, 2, 2))
        self.assertAlmostEqual(macro, prf(1, 1, 1)[2] / 10)

    def test_evidence_recall(self):
        texts = {"a": "one two three four five six"}
        gold = {"a": {"ctr": ["three four"], "staffing": ["six"]}}
        hit = [Finding("a", "ctr", 4, "two three", ()), Finding("a", "staffing", 0, "one", ())]
        self.assertEqual(evidence_recall(gold, hit, texts), 0.5)
        self.assertEqual(evidence_recall(gold, [Finding("a", "ctr", 0, "one two", ())], texts), 0.0)
        self.assertEqual(evidence_recall(gold, [Finding("a", "staffing", 24, "six", ())], texts), 0.5)
