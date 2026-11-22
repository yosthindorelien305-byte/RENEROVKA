"""Unit tests for SEO Stage 2: expanded sitemap.xml, canonical tags, and robots meta tags.
Validates all public pages:
- https://rizzafit.ru/
- https://rizzafit.ru/fitify/
- https://rizzafit.ru/fitify/muscles.html
"""
import io
import os
import unittest
import xml.etree.ElementTree as ET
from email.message import Message

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SITEMAP_FILE = os.path.join(SITE, "sitemap.xml")
INDEX_FILE = os.path.join(SITE, "index.html")
FITIFY_INDEX_FILE = os.path.join(SITE, "fitify", "index.html")
FITIFY_MUSCLES_FILE = os.path.join(SITE, "fitify", "muscles.html")


def invoke_static_get(path):
    """Invoke server.H static GET handler in-process and capture status, headers, and body."""
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


class TestSeoStage2(unittest.TestCase):
    def test_sitemap_contains_all_three_public_pages(self):
        """sitemap.xml must contain exactly the 3 public canonical pages with correct metadata."""
        self.assertTrue(os.path.isfile(SITEMAP_FILE), "site/sitemap.xml must exist")
        tree = ET.parse(SITEMAP_FILE)
        root_el = tree.getroot()
        self.assertEqual(root_el.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")

        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root_el.findall("ns:url", ns)
        self.assertEqual(len(urls), 3, "sitemap.xml must contain exactly 3 public pages")

        expected_locs = {
            "https://rizzafit.ru/": {"lastmod": "2026-11-21", "changefreq": "daily", "priority": "1.0"},
            "https://rizzafit.ru/fitify/": {"lastmod": "2026-11-22", "changefreq": "weekly", "priority": "0.8"},
            "https://rizzafit.ru/fitify/muscles.html": {"lastmod": "2026-11-22", "changefreq": "weekly", "priority": "0.8"},
        }

        found_locs = {}
        for u in urls:
            loc_el = u.find("ns:loc", ns)
            self.assertIsNotNone(loc_el, "<loc> is missing in a sitemap entry")
            loc = loc_el.text.strip()

            lastmod_el = u.find("ns:lastmod", ns)
            self.assertIsNotNone(lastmod_el, f"<lastmod> is missing for {loc}")
            lastmod = lastmod_el.text.strip()

            cf_el = u.find("ns:changefreq", ns)
            self.assertIsNotNone(cf_el, f"<changefreq> is missing for {loc}")
            cf = cf_el.text.strip()

            pr_el = u.find("ns:priority", ns)
            self.assertIsNotNone(pr_el, f"<priority> is missing for {loc}")
            pr = pr_el.text.strip()

            found_locs[loc] = {"lastmod": lastmod, "changefreq": cf, "priority": pr}

        self.assertEqual(set(found_locs.keys()), set(expected_locs.keys()))
        for loc, meta in expected_locs.items():
            self.assertEqual(found_locs[loc]["lastmod"], meta["lastmod"], f"lastmod mismatch for {loc}")
            self.assertEqual(found_locs[loc]["changefreq"], meta["changefreq"], f"changefreq mismatch for {loc}")
            self.assertEqual(found_locs[loc]["priority"], meta["priority"], f"priority mismatch for {loc}")

    def test_sitemap_excludes_admin_and_private_routes(self):
        """sitemap.xml must not contain admin.html, API endpoints, server_data, or hash fragments."""
        with open(SITEMAP_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("/admin.html", content, "/admin.html must never be in sitemap")
        self.assertNotIn("/api/", content, "/api/ must never be in sitemap")
        self.assertNotIn("/server_data/", content, "/server_data/ must never be in sitemap")
        self.assertNotIn("#", content, "hash '#' SPA fragments must never be in sitemap")

    def test_canonical_tags_on_all_public_pages(self):
        """Each public HTML page must contain its canonical link pointing to rizzafit.ru."""
        # 1. Root page
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index_html = f.read()
        self.assertIn('<link rel="canonical" href="https://rizzafit.ru/">', index_html)

        # 2. Fitify index
        with open(FITIFY_INDEX_FILE, "r", encoding="utf-8") as f:
            fitify_index_html = f.read()
        self.assertIn('<link rel="canonical" href="https://rizzafit.ru/fitify/">', fitify_index_html)

        # 3. Fitify muscles
        with open(FITIFY_MUSCLES_FILE, "r", encoding="utf-8") as f:
            fitify_muscles_html = f.read()
        self.assertIn('<link rel="canonical" href="https://rizzafit.ru/fitify/muscles.html">', fitify_muscles_html)

    def test_robots_meta_tags_on_all_public_pages(self):
        """Each public HTML page must contain meta name='robots' content='index, follow'."""
        for file_path, name in [
            (INDEX_FILE, "site/index.html"),
            (FITIFY_INDEX_FILE, "site/fitify/index.html"),
            (FITIFY_MUSCLES_FILE, "site/fitify/muscles.html"),
        ]:
            with open(file_path, "r", encoding="utf-8") as f:
                html = f.read()
            self.assertIn(
                '<meta name="robots" content="index, follow">',
                html,
                f"{name} must contain '<meta name=\"robots\" content=\"index, follow\">'",
            )

    def test_sitemap_http_serving_valid_xml(self):
        """GET /sitemap.xml must return 200 OK with XML content-type and parseable XML."""
        status, headers, body_bytes = invoke_static_get("/sitemap.xml")
        self.assertEqual(status, 200, f"Expected 200, got {status}")
        ctype = headers.get("content-type", "")
        self.assertTrue("xml" in ctype or "text/" in ctype, f"Unexpected content-type: {ctype}")

        try:
            tree = ET.fromstring(body_bytes)
        except Exception as e:
            self.fail(f"HTTP response body is not valid XML: {e}")

        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text.strip() for el in tree.findall("ns:url/ns:loc", ns)]
        self.assertIn("https://rizzafit.ru/", locs)
        self.assertIn("https://rizzafit.ru/fitify/", locs)
        self.assertIn("https://rizzafit.ru/fitify/muscles.html", locs)
        self.assertNotIn("/admin.html", "\n".join(locs))

    def test_fitify_pages_http_serving(self):
        """GET /fitify/ and GET /fitify/muscles.html must return 200 OK and have canonical & robots."""
        for path, expected_canonical in [
            ("/fitify/", "https://rizzafit.ru/fitify/"),
            ("/fitify/muscles.html", "https://rizzafit.ru/fitify/muscles.html"),
        ]:
            status, headers, body_bytes = invoke_static_get(path)
            self.assertEqual(status, 200, f"GET {path} returned status {status}")
            ctype = headers.get("content-type", "")
            self.assertTrue("text/html" in ctype, f"Unexpected content-type: {ctype}")
            body = body_bytes.decode("utf-8")
            self.assertIn(f'<link rel="canonical" href="{expected_canonical}">', body)
            self.assertIn('<meta name="robots" content="index, follow">', body)


if __name__ == "__main__":
    unittest.main()
