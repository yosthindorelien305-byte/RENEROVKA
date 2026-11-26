"""Tests for Deterministic SEO Audit on real site/ and synthetic fixtures (PR 4.2)."""

import hashlib
import os
import tempfile
import unittest

import server
from growth import seo_audit
from tests.test_growth_tasks import invoke_http
from tests.test_isolation import IsolatedServerTestCase


def _tree_snapshot(root_dir):
    snap = {}
    for root, _dirs, files in os.walk(root_dir):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, root_dir)
            with open(p, "rb") as f:
                snap[rel] = hashlib.sha256(f.read()).hexdigest()
    return snap


class TestGrowthSeoAudit(IsolatedServerTestCase):
    def setUp(self):
        super().setUp()
        self.admin_pw = "SeoAdm_2026!"
        server.set_pw(self.admin_pw)
        code, body = invoke_http("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(code, 200)
        self.admin_hdrs = {
            "Authorization": f"Bearer {body['token']}",
            "Origin": "http://127.0.0.1:8080",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def test_real_site_audit_api_persists_and_does_not_mutate_site_files(self):
        # Ignore site/content changes just snapshot *.html, robots.txt, sitemap.xml
        before_html = {
            fn: hashlib.sha256(open(os.path.join(server.SITE, fn), "rb").read()).hexdigest()
            for fn in ("index.html", "admin.html", "robots.txt", "sitemap.xml")
        }

        c_pre, b_pre = invoke_http("GET", "/api/admin/growth/seo-audit", headers=self.admin_hdrs)
        self.assertEqual(c_pre, 200)
        self.assertFalse(b_pre["hasRun"])

        c_run, b_run = invoke_http("POST", "/api/admin/growth/seo-audit/run", {}, headers=self.admin_hdrs)
        self.assertEqual(c_run, 200)
        self.assertEqual(b_run["pagesChecked"], 5)
        checked_urls = [p["pageUrl"] for p in b_run["pages"]]
        self.assertEqual(
            set(checked_urls),
            {"/", "/admin.html", "/programs.html", "/exercises.html", "/ai-coach.html"},
        )
        self.assertFalse(any("fitify" in u.lower() for u in checked_urls))
        self.assertEqual(b_run["summary"]["critical"], 0)
        self.assertEqual(b_run["summary"]["high"], 0)
        self.assertFalse(any("fitify" in str(i["pageUrl"]).lower() for i in b_run["issues"]))
        self.assertTrue(b_run["robotsCheck"]["exists"])
        self.assertTrue(b_run["sitemapCheck"]["valid"])
        unknown_names = {u["check"] for u in b_run["unknownChecks"]}
        self.assertIn("search_console_indexing", unknown_names)
        self.assertIn("external_links_reachability", unknown_names)
        for u in b_run["unknownChecks"]:
            self.assertEqual(u["status"], "unknown")

        # GET returns persisted run and severity filtering works
        c_get, b_get = invoke_http("GET", "/api/admin/growth/seo-audit", headers=self.admin_hdrs)
        self.assertEqual(c_get, 200)
        self.assertTrue(b_get["hasRun"])
        self.assertEqual(b_get["runId"], b_run["runId"])

        c_crit, b_crit = invoke_http("GET", "/api/admin/growth/seo-audit?severity=critical", headers=self.admin_hdrs)
        self.assertEqual(c_crit, 200)
        for iss in b_crit["issues"]:
            self.assertEqual(iss["severity"], "critical")

        # Site files unchanged
        for fn, hval in before_html.items():
            after = hashlib.sha256(open(os.path.join(server.SITE, fn), "rb").read()).hexdigest()
            self.assertEqual(after, hval)

    def test_synthetic_site_detects_all_required_seo_issues_deterministically(self):
        with tempfile.TemporaryDirectory(prefix="flexa_seo_synth_") as sdir:
            with open(os.path.join(sdir, "robots.txt"), "w", encoding="utf-8") as f:
                f.write("User-agent: *\nAllow: /\n")
            with open(os.path.join(sdir, "sitemap.xml"), "w", encoding="utf-8") as f:
                f.write(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    "<url><loc>https://rizzafit.ru/missing.html</loc></url>"
                    "<url><loc>https://rizzafit.ru/fitify/</loc></url>"
                    "</urlset>"
                )
            with open(os.path.join(sdir, "index.html"), "w", encoding="utf-8") as f:
                f.write(
                    "<html><head>"
                    "<title>Same Title For Two Pages</title>"
                    '<meta name="description" content="Duplicate meta description text repeated across multiple pages to verify deterministic duplicate check">'
                    '<meta name="robots" content="noindex">'
                    "</head><body>"
                    '<img src="img/a.png">'
                    '<img src="img/deco.svg" alt="">'
                    '<a href="/broken-page.html">Broken</a>'
                    '<a href="https://external.example/test">External unknown</a>'
                    "</body></html>"
                )
            with open(os.path.join(sdir, "second.html"), "w", encoding="utf-8") as f:
                f.write(
                    '<html lang="ru"><head>'
                    "<title>Same Title For Two Pages</title>"
                    '<meta name="description" content="Duplicate meta description text repeated across multiple pages to verify deterministic duplicate check">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<link rel="canonical" href="https://rizzafit.ru/wrong-path">'
                    "</head><body><h1>First</h1><h1>Second</h1></body></html>"
                )
            with open(os.path.join(sdir, "admin.html"), "w", encoding="utf-8") as f:
                f.write("<html><head><title>Admin</title></head><body>Admin</body></html>")
            os.makedirs(os.path.join(sdir, "fitify"), exist_ok=True)
            with open(os.path.join(sdir, "fitify", "index.html"), "w", encoding="utf-8") as f:
                f.write("<html><head><title>Fitify</title></head><body>Fitify</body></html>")

            before = _tree_snapshot(sdir)
            report = seo_audit.scan_site_seo(sdir)
            self.assertEqual(_tree_snapshot(sdir), before)
            self.assertFalse(any("fitify" in p["pageUrl"].lower() for p in report["pages"]))

            types = {(i["pageUrl"], i["issueType"]): i["severity"] for i in report["issues"]}
            self.assertEqual(types[("/robots.txt", "robots_missing_fitify_disallow")], "medium")
            self.assertEqual(types[("/robots.txt", "robots_missing_sitemap")], "medium")
            self.assertEqual(types[("/fitify/", "sitemap_excluded_fitify_url")], "high")
            self.assertEqual(types[("/", "public_page_noindex")], "critical")
            self.assertEqual(types[("/", "missing_canonical")], "high")
            self.assertEqual(types[("/", "missing_h1")], "high")
            self.assertEqual(types[("/", "broken_internal_link")], "high")
            self.assertEqual(types[("/", "images_missing_alt")], "medium")
            # Decorative img with alt="" must NOT cause 2 missing-alt issues (only 1 for img/a.png)
            alt_issue = next(i for i in report["issues"] if i["issueType"] == "images_missing_alt")
            self.assertEqual(alt_issue["currentValue"], "1")
            self.assertEqual(types[("/second.html", "canonical_path_mismatch")], "medium")
            self.assertEqual(types[("/second.html", "multiple_h1")], "low")
            self.assertEqual(types[("/admin.html", "admin_missing_noindex")], "high")
            self.assertEqual(types[("/missing.html", "sitemap_broken_url")], "high")

            all_types = [i["issueType"] for i in report["issues"]]
            self.assertIn("duplicate_title", all_types)
            self.assertIn("duplicate_meta_description", all_types)


if __name__ == "__main__":
    unittest.main()
