import hashlib
import json
import re
import unittest

from examcheck import DATA_DIR
from examcheck.corpus import Order, grounded, load_index, load_orders, normalize, regulation_text, sentences
from examcheck.extract import Finding, counts, extract, flagged, max_count
from examcheck.taxonomy import CATEGORIES, COMPILED, LABELS, PATTERNS


class CorpusTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize('a' + chr(9) + ' b' + chr(10) + ' c  d'), 'a b c d')

    def test_grounded(self):
        text = normalize('The Bank had a backlog of 5,000 alerts.')
        self.assertTrue(grounded('Bank had a backlog', text))
        self.assertTrue(grounded('  Bank   had ', text))
        self.assertFalse(grounded('', text))
        self.assertFalse(grounded('credit union', text))

    def test_sentences_offsets(self):
        text = 'Hello world. Next sentence? Yes.'
        pairs = sentences(text)
        self.assertEqual(
            [text[start:start + len(sentence)] for start, sentence in pairs],
            ['Hello world.', 'Next sentence?', 'Yes.'],
        )

    def test_load_index(self):
        index = load_index()
        self.assertEqual(len(index), 50)
        self.assertEqual(sum(entry['status'] == 'included' for entry in index), 39)
        self.assertEqual(sum(entry['status'] == 'no_text_layer' for entry in index), 8)
        self.assertEqual(sum(entry['status'] == 'individual' for entry in index), 3)
        for entry in index:
            self.assertIsNotNone(entry['id'])
            self.assertIsNotNone(entry['url'])
            if entry['status'] == 'included':
                self.assertIsNotNone(entry['text'])
            else:
                self.assertIsNone(entry['text'])

    def test_load_orders(self):
        orders = load_orders()
        index = load_index()
        included_ids = [entry['id'] for entry in index if entry['status'] == 'included']
        self.assertEqual(len(orders), 39)
        self.assertEqual([order.id for order in orders], included_ids)
        for order in orders:
            self.assertEqual(order.text, normalize(order.text))

    def test_regulation_text(self):
        text = regulation_text()
        self.assertIn('Reports by banks of suspicious transactions', text)
        self.assertIn('no later than 30 calendar days', text)
        self.assertNotIn('<P>', text)
        self.assertEqual(text, normalize(text))


class TaxonomyTests(unittest.TestCase):
    def test_category_order_and_labels(self):
        self.assertEqual(
            CATEGORIES,
            (
                'alert_backlog',
                'late_sar',
                'sar_not_filed',
                'unsupported_disposition',
                'monitoring_gap',
                'cdd_edd',
                'ctr',
                'staffing',
                'independent_testing',
                'governance',
            ),
        )
        self.assertEqual(set(LABELS), set(CATEGORIES))
        self.assertTrue(all(LABELS[category] for category in CATEGORIES))

    def test_pattern_hash(self):
        payload = json.dumps([list(PATTERNS[category]) for category in CATEGORIES]).encode()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            'b34c316636fada761889bc99cce3035836751d73f9052c2b04fea7528608ee80',
        )

    def test_compiled_patterns(self):
        for category in CATEGORIES:
            self.assertTrue(all(isinstance(pattern, re.Pattern) for pattern in COMPILED[category]))


class ExtractTests(unittest.TestCase):
    def test_counts_lone_star_example(self):
        self.assertEqual(
            counts('Lone Star had 4,888 outstanding alerts, 627 cases'),
            (('alerts', 4888), ('cases', 627)),
        )

    def test_counts_unit_mappings(self):
        quote = (
            '1 alert, 2 SARs, 3 suspicious activity reports, '
            '4 CTRs, 5 currency transaction reports, 6 days, 7 cases'
        )
        self.assertEqual(
            counts(quote),
            (
                ('alerts', 1),
                ('sars', 2),
                ('sars', 3),
                ('ctrs', 4),
                ('ctrs', 5),
                ('days', 6),
                ('cases', 7),
            ),
        )

    def test_extract_one_finding(self):
        order = Order(
            '1',
            '2020-01-01',
            'In the Matter of Test',
            'https://example.com/order.pdf',
            'The Bank had a backlog of 5,000 alerts.',
        )
        findings = extract(order)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.order_id, '1')
        self.assertEqual(finding.category, 'alert_backlog')
        self.assertEqual(finding.start, 0)
        self.assertEqual(finding.quote, 'The Bank had a backlog of 5,000 alerts.')
        self.assertEqual(finding.counts, (('alerts', 5000),))

    def test_flagged_and_max_count(self):
        findings = [
            Finding('a', 'late_sar', 0, 'five SARs were late', (('sars', 5),)),
            Finding('a', 'monitoring_gap', 1, 'monitoring was weak', ()),
            Finding('b', 'late_sar', 2, 'seven SARs were late', (('sars', 7),)),
        ]
        self.assertEqual(flagged(findings), {'a': {'late_sar', 'monitoring_gap'}, 'b': {'late_sar'}})
        self.assertEqual(max_count(findings, 'b', 'late_sar', 'sars'), 7)
        self.assertEqual(max_count(findings, 'a', 'late_sar', 'days'), 0)


if __name__ == '__main__':
    unittest.main()
