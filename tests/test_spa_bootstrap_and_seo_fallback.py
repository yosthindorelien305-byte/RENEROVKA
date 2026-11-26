"""Regression tests ensuring SPA never gets stuck on the static SEO fallback card."""

import os
import subprocess
import unittest

from growth import seo_audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestSpaBootstrapAndSeoFallback(unittest.TestCase):
    def test_index_html_hides_seo_fallback_in_js_and_preserves_seo_tags(self):
        with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
            html = f.read()

        # JS-mode hiding must run in <head> before rendering body
        head = html.split("</head>", 1)[0]
        self.assertIn("document.documentElement.classList.add('rf-js')", head)
        self.assertIn(".rf-js .rf-seo-fallback{display:none!important}", head)

        # Crawlers / no-JS fallback + SEO metadata remain intact
        self.assertIn('<section class="rf-seo-fallback"', html)
        self.assertIn("<h1", html)
        self.assertIn('href="/programs.html"', html)
        self.assertIn('href="/exercises.html"', html)
        self.assertIn('href="/ai-coach.html"', html)
        self.assertIn('<link rel="canonical" href="https://rizzafit.ru/">', html)
        self.assertIn('property="og:title"', html)
        self.assertIn('application/ld+json', html)

        # Service worker controllerchange reload must ignore initial first-install claim
        self.assertIn("const hadController = !!navigator.serviceWorker.controller;", html)
        self.assertIn("if (hadController && !refreshing)", html)

    def test_app_js_and_sw_js_hardened_and_valid_syntax(self):
        for rel in ("app.js", "analytics.js", "sw.js", "admin_growth.js", "ui_components.js"):
            res = subprocess.run(["node", "--check", os.path.join(SITE, rel)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)

        with open(os.path.join(SITE, "app.js"), encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("const seoFb = app.querySelector('.rf-seo-fallback');", app_js)
        self.assertIn("const loadCoreData = async () =>", app_js)
        self.assertIn("caches.match('data.json', { ignoreSearch: true })", app_js)
        self.assertIn("const safeJsonParse = (raw, fallback) =>", app_js)
        self.assertIn("const safeIsoDate = ts =>", app_js)
        self.assertIn("console.error('[RizzaFit] Route render error:'", app_js)
        self.assertIn("console.error('[RizzaFit] SPA boot failed:'", app_js)

        with open(os.path.join(SITE, "sw.js"), encoding="utf-8") as f:
            sw_js = f.read()
        self.assertIn("flexa-shell-v66", sw_js)
        self.assertIn("hit || Response.error()", sw_js)

    def test_deterministic_seo_audit_remains_clean_on_site(self):
        rep = seo_audit.scan_site_seo(SITE)
        self.assertEqual(rep["pagesChecked"], 5)
        self.assertEqual(rep["summary"]["critical"], 0)
        self.assertEqual(rep["summary"]["high"], 0)
        self.assertEqual(rep["summary"]["total"], 0)
        self.assertFalse(any("fitify" in p["pageUrl"].lower() for p in rep["pages"]))


if __name__ == "__main__":
    unittest.main()
