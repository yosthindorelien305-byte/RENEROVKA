"""Regression tests for Redesign PR 1 (Dark Luxury + Warm Gold v1.0):
- Verifies Dark Luxury & Warm Gold palette tokens and mixed Dark/Cream scopes
- Verifies no duplicate :root block remains in site/style.css
- Verifies self-hosted Manrope WOFF2 fonts & OFL 1.1 attribution + removal of external Google Fonts from index.html
- Verifies bespoke Hero photography assets exist and are precached in sw.js
- Verifies applyAccent() rejects legacy #00d2ff/#f0a830 config overrides in favor of #D6B36A
- Verifies Desktop Top Navigation (#top-nav) + Mobile Bottom Nav (#nav) + Hero CTAs & SEO cleanliness
"""
import os
import unittest

from growth import seo_audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestRedesignPR1DesignSystem(unittest.TestCase):
    def test_dark_luxury_palette_tokens_and_single_root(self):
        with open(os.path.join(SITE, "tokens.css"), encoding="utf-8") as f:
            tokens_css = f.read()
        with open(os.path.join(SITE, "style.css"), encoding="utf-8") as f:
            style_css = f.read()

        for expected in (
            "#171717",
            "#101010",
            "#292929",
            "#D6B36A",
            "#E8CA86",
            "#FAF7F0",
            ".rf-section-dark",
            ".rf-section-cream",
            "font-family: 'Manrope'",
        ):
            self.assertIn(expected, tokens_css, msg=f"Missing token/scope in tokens.css: {expected}")

        self.assertNotIn("#2DD4BF", tokens_css)
        self.assertNotIn(":root {", style_css, msg="Duplicate :root block should not exist in style.css")
        self.assertNotIn("#2DD4BF", style_css)

    def test_self_hosted_manrope_woff2_and_hero_assets(self):
        fonts_dir = os.path.join(SITE, "fonts")
        for fname in ("manrope-vf-cyrillic.woff2", "manrope-vf-latin.woff2"):
            fpath = os.path.join(fonts_dir, fname)
            self.assertTrue(os.path.isfile(fpath), msg=f"Missing font file {fname}")
            with open(fpath, "rb") as f:
                header = f.read(4)
            self.assertEqual(header, b"wOF2", msg=f"{fname} is not a valid WOFF2 binary")

        ofl_path = os.path.join(fonts_dir, "OFL.txt")
        self.assertTrue(os.path.isfile(ofl_path))
        with open(ofl_path, encoding="utf-8") as f:
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", f.read())

        for asset in ("img/brand/hero-luxury.webp", "img/brand/hero-luxury.jpg"):
            self.assertTrue(os.path.isfile(os.path.join(SITE, asset)), msg=f"Missing hero asset site/{asset}")

        with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        self.assertNotIn("fonts.googleapis.com", index_html)
        self.assertNotIn("fonts.gstatic.com", index_html)

        with open(os.path.join(SITE, "sw.js"), encoding="utf-8") as f:
            sw_js = f.read()
        for cached in (
            "./fonts/manrope-vf-cyrillic.woff2",
            "./fonts/manrope-vf-latin.woff2",
            "./img/brand/hero-luxury.webp",
            "/fonts/",
        ):
            self.assertIn(cached, sw_js)

    def test_top_navigation_hero_and_legacy_accent_protection(self):
        with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        with open(os.path.join(SITE, "app.js"), encoding="utf-8") as f:
            app_js = f.read()

        for marker in (
            'id="top-nav"',
            'id="top-profile-btn"',
            'id="top-ath-av"',
            'id="top-coach-btn"',
            'id="nav"',
        ):
            self.assertIn(marker, index_html)

        for js_marker in (
            "СТАНЬ СИЛЬНЕЕ.",
            "СТАНЬ ЛУЧШЕ.",
            "rf-hero",
            "rf-section-cream",
            "rf-section-dark",
            "rf-home-learn-more",
            "img/brand/hero-luxury.webp",
            "00d2ff|f0a830|2dd4bf",
            "'#D6B36A'",
        ):
            self.assertIn(js_marker, app_js, msg=f"Missing PR 1 marker in site/app.js: {js_marker}")

        self.assertNotIn("#2DD4BF", app_js)

    def test_seo_audit_zero_issues_after_pr1(self):
        rep = seo_audit.scan_site_seo(SITE)
        self.assertEqual(rep["pagesChecked"], 5)
        self.assertEqual(rep["summary"]["total"], 0)
        self.assertFalse(any("fitify" in p["pageUrl"].lower() for p in rep["pages"]))
