"""Regression tests verifying mobile sticky header behavior and desktop invariance."""

import os
import unittest

from growth import seo_audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestMobileHeaderSticky(unittest.TestCase):
    def test_mobile_overflow_clip_and_sticky_header_rules_present(self):
        with open(os.path.join(SITE, "style.css"), encoding="utf-8") as f:
            css = f.read()

        # Mobile <= 420px preserves safe-area top padding on .top
        narrow_block = css.split("@media (max-width: 420px)", 1)[1].split(".top-coach-btn", 1)[0]
        self.assertIn("padding-top: max(10px, env(safe-area-inset-top));", narrow_block)

        # Mobile <= 639px uses overflow-x: clip so .top sticky remains viewport-pinned
        mob_block = css.split("@media (max-width: 639px)", 1)[1].split("@media (min-width: 640px)", 1)[0]
        self.assertIn("overflow-x: clip;", mob_block)
        self.assertIn("body.mob-app .top", mob_block)
        self.assertIn("position: sticky;", mob_block)
        self.assertIn("z-index: 40;", mob_block)
        self.assertIn("@supports not (overflow-x: clip)", mob_block)
        self.assertIn("position: fixed;", mob_block)
        self.assertIn("body.mob-app:not(.player-open)", mob_block)

    def test_desktop_rules_unchanged_and_seo_clean(self):
        with open(os.path.join(SITE, "style.css"), encoding="utf-8") as f:
            css = f.read()

        desktop_640 = css.split("@media (min-width: 640px)", 1)[1].split("@media (min-width: 1024px)", 1)[0]
        desktop_1024 = css.split("@media (min-width: 1024px)", 1)[1]
        self.assertNotIn("overflow-x: clip", desktop_640)
        self.assertNotIn("overflow-x: clip", desktop_1024)
        self.assertNotIn("body.mob-app .top {\n    position: fixed", desktop_640)
        self.assertNotIn("body.mob-app .top {\n    position: fixed", desktop_1024)

        rep = seo_audit.scan_site_seo(SITE)
        self.assertEqual(rep["pagesChecked"], 5)
        self.assertEqual(rep["summary"]["total"], 0)
        self.assertFalse(any("fitify" in p["pageUrl"].lower() for p in rep["pages"]))


if __name__ == "__main__":
    unittest.main()
