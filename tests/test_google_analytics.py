"""Unit and HTTP serving tests for Google Analytics 4 (GA4) integration.
Validates tag installation, Measurement ID G-XSBKDCY4CS, SPA virtual page views,
auth & CTA event hooks, and strict PII protection.
"""
import io
import os
import re
import unittest
from email.message import Message

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
INDEX_FILE = os.path.join(SITE, "index.html")
ANALYTICS_FILE = os.path.join(SITE, "analytics.js")
APP_FILE = os.path.join(SITE, "app.js")
ADMIN_FILE = os.path.join(SITE, "admin.html")
FITIFY_INDEX = os.path.join(SITE, "fitify", "index.html")
FITIFY_MUSCLES = os.path.join(SITE, "fitify", "muscles.html")

GA_ID = "G-XSBKDCY4CS"


def invoke_static_get(path):
    """Invoke server.H static GET handler in-process without network sockets."""
    h = server.H.__new__(server.H)
    h.path = path
    h.command = "GET"
    h.headers = Message()
    h.client_address = ("127.0.0.1", 50000)
    h.rfile = io.BytesIO(b"")
    h.wfile = io.BytesIO()
    h.request_version = "HTTP/1.1"
    h._headers_buffer = []
    h.directory = SITE

    captured = {"status": None, "headers": {}}

    def send_response(code, message=None):
        captured["status"] = code

    def send_header(k, v):
        captured["headers"][k.lower()] = v

    h.send_response = send_response
    h.send_header = send_header
    h.end_headers = lambda: None

    h.do_GET()
    out = h.wfile.getvalue()
    return captured["status"], captured["headers"], out


class TestGoogleAnalyticsIntegration(unittest.TestCase):
    def test_ga4_tag_in_index_html(self):
        """index.html must load gtag.js with G-XSBKDCY4CS and include analytics.js."""
        self.assertTrue(os.path.isfile(INDEX_FILE), "site/index.html must exist")
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            html = f.read()

        # Google tag script tag
        expected_script = f"https://www.googletagmanager.com/gtag/js?id={GA_ID}"
        self.assertIn(expected_script, html, f"index.html must include gtag.js script with {GA_ID}")

        # DataLayer initialization and config
        self.assertIn("window.dataLayer = window.dataLayer || [];", html)
        self.assertIn("function gtag(){dataLayer.push(arguments);}", html)
        self.assertIn(f"gtag('config', '{GA_ID}'", html)
        self.assertIn("send_page_view: false", html, "SPA index.html must configure send_page_view: false to avoid duplicate initial page_views")

        # analytics.js included before app.js
        self.assertIn('<script src="analytics.js', html, "index.html must include analytics.js")
        pos_analytics = html.find('src="analytics.js')
        pos_app = html.find('src="app.js')
        self.assertTrue(pos_analytics != -1 and pos_app != -1 and pos_analytics < pos_app,
                        "analytics.js must be loaded before app.js")

    def test_ga4_tag_in_fitify_pages(self):
        """Public static pages in site/fitify/ must include GA4 tag with G-XSBKDCY4CS."""
        for path in [FITIFY_INDEX, FITIFY_MUSCLES]:
            self.assertTrue(os.path.isfile(path), f"{path} must exist")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(f"https://www.googletagmanager.com/gtag/js?id={GA_ID}", content,
                          f"{os.path.basename(path)} must include gtag.js")
            self.assertIn(f"gtag('config', '{GA_ID}')", content,
                          f"{os.path.basename(path)} must configure {GA_ID}")

    def test_admin_html_does_not_contain_ga(self):
        """Admin panel is internal and must not include public marketing analytics tags."""
        self.assertTrue(os.path.isfile(ADMIN_FILE), "site/admin.html must exist")
        with open(ADMIN_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("googletagmanager.com", content, "admin.html must not contain Google Tag Manager / Analytics")
        self.assertNotIn(GA_ID, content, "admin.html must not contain GA Measurement ID")

    def test_analytics_js_structure_and_no_pii(self):
        """analytics.js must provide RizzaAnalytics methods and enforce PII sanitization."""
        self.assertTrue(os.path.isfile(ANALYTICS_FILE), "site/analytics.js must exist")
        with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
            js = f.read()

        # Measurement ID
        self.assertIn(GA_ID, js)

        # Core API methods
        self.assertIn("trackPageView", js)
        self.assertIn("trackSignUp", js)
        self.assertIn("trackLogin", js)
        self.assertIn("trackWorkoutStart", js)
        self.assertIn("trackWorkoutComplete", js)
        self.assertIn("trackCta", js)

        # Forbidden PII keys
        for forbidden in ["email", "password", "token", "userToken", "auth_code", "phone"]:
            self.assertIn(f"'{forbidden}'", js, f"analytics.js must explicitly forbid key '{forbidden}'")

    def test_app_js_event_hooks_and_safe_params(self):
        """app.js must trigger analytics for page views, auth and workouts without sending PII."""
        self.assertTrue(os.path.isfile(APP_FILE), "site/app.js must exist")
        with open(APP_FILE, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("window.RizzaAnalytics.trackPageView", code, "app.js must trigger trackPageView in router")
        self.assertIn("window.RizzaAnalytics.trackSignUp", code, "app.js must trigger trackSignUp on confirmed registration")
        self.assertIn("window.RizzaAnalytics.trackLogin", code, "app.js must trigger trackLogin on confirmed auth")
        self.assertIn("window.RizzaAnalytics.trackWorkoutStart", code, "app.js must trigger trackWorkoutStart")
        self.assertIn("window.RizzaAnalytics.trackWorkoutComplete", code, "app.js must trigger trackWorkoutComplete")

        # Verify that trackSignUp and trackLogin calls do NOT pass username, email or password variables
        matches = re.findall(r'track(?:Login|SignUp)\((.*?)\)', code)
        self.assertTrue(len(matches) >= 3, f"Expected at least 3 login/signup calls, found {len(matches)}")
        for m in matches:
            arg = m.strip()
            self.assertNotIn("password", arg.lower())
            self.assertNotIn("email", arg.lower())
            self.assertNotIn("token", arg.lower())
            self.assertNotIn("username", arg.lower())

    def test_no_duplicate_or_competing_counters(self):
        """Ensure no competing or duplicate measurement IDs are present in site HTML files."""
        html_files = [INDEX_FILE, ADMIN_FILE, FITIFY_INDEX, FITIFY_MUSCLES]
        for fpath in html_files:
            with open(fpath, "r", encoding="utf-8") as f:
                c = f.read()
            # No Universal Analytics or GTM containers
            self.assertNotIn("UA-", c, f"Found deprecated UA tag in {fpath}")
            self.assertNotIn("GTM-", c, f"Found GTM container in {fpath}")
            self.assertNotIn("mc.yandex", c, f"Found Yandex Metrika in {fpath}")

            # If GA_ID is in the file, ensure it only occurs once in script tags
            if GA_ID in c:
                occurrences = len(re.findall(re.escape(GA_ID), c))
                self.assertLessEqual(occurrences, 2, f"GA_ID occurs too many times in {fpath} ({occurrences})")

    def test_http_serving_analytics_assets(self):
        """HTTP GET / serves GA tag and GET /analytics.js serves valid JS asset with 200 OK."""
        status_root, _, body_root = invoke_static_get("/")
        self.assertEqual(status_root, 200)
        self.assertIn(GA_ID, body_root.decode("utf-8"))

        status_js, headers_js, body_js = invoke_static_get("/analytics.js")
        self.assertEqual(status_js, 200)
        ctype = headers_js.get("content-type", "")
        self.assertTrue("javascript" in ctype or "text/" in ctype, f"Unexpected content-type for analytics.js: {ctype}")
        self.assertIn(b"RizzaAnalytics", body_js)


if __name__ == "__main__":
    unittest.main()
