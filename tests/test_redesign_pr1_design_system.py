"""Regression tests for Redesign PR 1 (Dark Luxury + Warm Gold v1.0, Zero-Human Policy):
- Verifies Dark Luxury & Warm Gold palette tokens and mixed Dark/Cream scopes
- Verifies no duplicate :root block remains in site/style.css
- Verifies self-hosted Manrope WOFF2 fonts & OFL 1.1 attribution + removal of external Google Fonts
- Verifies ZERO human photos/silhouettes/mannequins/videos are active in UI:
  * hero-luxury.* and 3d_*.jpg removed
  * muscles.js has zero human silhouette paths
  * all 15 site/img/programs/*.jpg covers exist
  * all 197 site/img/ex/svg_norm_*.svg schematics have data-rf-equip="true" and no legacy black silhouette paths
  * athlete_profile.js and index.html have no human face/shoulders avatars or people emoji
  * app.js uses typographic RIZZAFIT Hero, disables human videos, and blocks legacy upload defaults
- Verifies applyAccent() protects Warm Gold #D6B36A from #00d2ff/#f0a830 config overrides
- Verifies seo_audit.scan_site_seo('site') remains clean (5/5 pages, 0 issues)
"""
import json
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
        self.assertIn(".rf-hero-wordmark", style_css)
        self.assertIn(".rf-muscle-matrix", style_css)

    def test_self_hosted_manrope_woff2_and_zero_human_assets(self):
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

        # Legacy human hero and 3D anatomical body JPGs must not exist
        for removed in (
            "img/brand/hero-luxury.webp",
            "img/brand/hero-luxury.jpg",
            "img/3d_arms_ref.jpg",
            "img/3d_back.jpg",
            "img/3d_chest.jpg",
            "img/3d_front.jpg",
        ):
            self.assertFalse(os.path.exists(os.path.join(SITE, removed)), msg=f"Human asset still exists: site/{removed}")

        with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        self.assertNotIn("fonts.googleapis.com", index_html)
        self.assertNotIn("fonts.gstatic.com", index_html)
        self.assertNotIn('<circle cx="12" cy="8.5" r="3.5"', index_html)
        self.assertNotIn("StayFit", index_html)

        with open(os.path.join(SITE, "img", "logo.svg"), encoding="utf-8") as f:
            logo_svg = f.read()
        self.assertIn("rfGold", logo_svg)

        with open(os.path.join(SITE, "sw.js"), encoding="utf-8") as f:
            sw_js = f.read()
        for cached in (
            "flexa-shell-v69",
            "./fonts/manrope-vf-cyrillic.woff2",
            "./fonts/manrope-vf-latin.woff2",
            "/fonts/",
        ):
            self.assertIn(cached, sw_js)
        self.assertNotIn("hero-luxury", sw_js)

    def test_all_program_covers_and_exercise_equipment_schematics_zero_human(self):
        with open(os.path.join(SITE, "data.json"), encoding="utf-8") as f:
            data = json.load(f)

        for p in data.get("programs", []):
            if p.get("img"):
                p_path = os.path.join(SITE, "img", "programs", f"{p['id']}.jpg")
                self.assertTrue(os.path.isfile(p_path), msg=f"Missing program cover: {p_path}")
                with open(p_path, "rb") as pf:
                    self.assertEqual(pf.read(2), b"\xff\xd8", msg=f"Invalid JPEG cover: {p_path}")

        ex_checked = 0
        for e in data.get("exercises", []):
            if e.get("img"):
                ex_path = os.path.join(SITE, "img", "ex", f"svg_norm_{e['id']}.svg")
                self.assertTrue(os.path.isfile(ex_path), msg=f"Missing exercise schematic: {ex_path}")
                with open(ex_path, encoding="utf-8") as sf:
                    svg_src = sf.read()
                self.assertIn('data-rf-equip="true"', svg_src, msg=f"Legacy SVG not replaced: {ex_path}")
                self.assertNotIn("#000000ff", svg_src, msg=f"Legacy human silhouette found: {ex_path}")
                ex_checked += 1
        self.assertEqual(ex_checked, 197)

        with open(os.path.join(SITE, "muscles.js"), encoding="utf-8") as f:
            muscles_js = f.read()
        self.assertNotIn("front_base", muscles_js)
        self.assertNotIn("back_base", muscles_js)
        self.assertNotIn("fitify-mannequin", muscles_js)
        self.assertIn("RIZZAFIT_MUSCLE_ZONES", muscles_js)

    def test_top_navigation_typographic_hero_and_legacy_upload_guards(self):
        with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        with open(os.path.join(SITE, "app.js"), encoding="utf-8") as f:
            app_js = f.read()
        with open(os.path.join(SITE, "athlete_profile.js"), encoding="utf-8") as f:
            ap_js = f.read()

        for marker in ('id="top-nav"', 'id="top-profile-btn"', 'id="top-ath-av"', 'id="top-coach-btn"', 'id="nav"'):
            self.assertIn(marker, index_html)

        for js_marker in (
            "СТАНЬ СИЛЬНЕЕ.",
            "СТАНЬ ЛУЧШЕ.",
            "rf-hero-brandmark",
            "rf-hero-wordmark",
            "rf-muscle-matrix",
            "rf-section-cream",
            "rf-section-dark",
            "const getExVideo = e => null;",
            "content\\/uploads\\/program_7\\.jpg",
            "content\\/uploads\\/logo\\.(jpg|png)",
            "athlete_avatar\\.jpg",
            "00d2ff|f0a830|2dd4bf",
            "'#D6B36A'",
        ):
            self.assertIn(js_marker, app_js, msg=f"Missing PR 1 marker in site/app.js: {js_marker}")

        self.assertNotIn("hero-luxury", app_js)
        self.assertNotIn("fitify-mannequin-wrap", app_js)
        self.assertNotIn("#2DD4BF", app_js)

        self.assertNotIn("👥", ap_js)
        self.assertNotIn("M6 30c1-7", ap_js)
        self.assertIn("athlete_avatar\\.jpg", ap_js)

    def test_seo_audit_zero_issues_after_pr1(self):
        rep = seo_audit.scan_site_seo(SITE)
        self.assertEqual(rep["pagesChecked"], 5)
        self.assertEqual(rep["summary"]["total"], 0)
        self.assertFalse(any("fitify" in p["pageUrl"].lower() for p in rep["pages"]))
