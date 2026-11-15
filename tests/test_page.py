import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import render_page  # noqa: E402


class PageTest(unittest.TestCase):
    def test_page_matches_results(self):
        committed = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(render_page.render(), committed)

    def test_no_placeholder_left(self):
        self.assertNotRegex(render_page.render(), r"@[A-Z0-9]+@")


if __name__ == "__main__":
    unittest.main()
