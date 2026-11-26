"""Unit tests for RizzaFit-only SEO public pages (PR 4.3): sitemap.xml, canonical tags, unique metadata, and Fitify exclusion."""
import io
import os
import re
import unittest
import xml.etree.ElementTree as ET
from email.message import Message

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SITEMAP_FILE = os.path.join(SITE, "sitemap.xml")
INDEX_FILE = os.path.join(SITE, "index.html")
PROGRAMS_FILE = os.path.join(SITE, "programs.html")
EXERCISES_FILE = os.path.join(SITE, "exercises.html")
COACH_FILE = os.path.join(SITE, "ai-coach.html")
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
    def test_sitemap_contains_all_four_rizzafit_public_pages_without_fitify(self):
        """sitemap.xml must contain strictly the 4 RizzaFit canonical URLs and zero Fitify URLs."""
        self.assertTrue(os.path.isfile(SITEMAP_FILE), "site/sitemap.xml must exist")
        tree = ET.parse(SITEMAP_FILE)
        root_el = tree.getroot()
        self.assertEqual(root_el.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")

        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root_el.findall("ns:url", ns)
        self.assertEqual(len(urls), 4, "sitemap.xml must contain exactly 4 public RizzaFit pages")

        expected_locs = {
            "https://rizzafit.ru/": {"changefreq": "daily", "priority": "1.0"},
            "https://rizzafit.ru/programs.html": {"changefreq": "weekly", "priority": "0.9"},
            "https://rizzafit.ru/exercises.html": {"changefreq": "weekly", "priority": "0.9"},
            "https://rizzafit.ru/ai-coach.html": {"changefreq": "weekly", "priority": "0.9"},
        }

        found_locs = {}
        for u in urls:
            loc = u.find("ns:loc", ns).text.strip()
            self.assertNotIn("fitify", loc.lower(), "Fitify must never be promoted in sitemap.xml")
            lastmod = u.find("ns:lastmod", ns).text.strip()
            self.assertRegex(lastmod, r"^\d{4}-\d{2}-\d{2}$")
            cf = u.find("ns:changefreq", ns).text.strip()
            pr = u.find("ns:priority", ns).text.strip()
            found_locs[loc] = {"changefreq": cf, "priority": pr}

        self.assertEqual(set(found_locs.keys()), set(expected_locs.keys()))
        for loc, meta in expected_locs.items():
            self.assertEqual(found_locs[loc]["changefreq"], meta["changefreq"])
            self.assertEqual(found_locs[loc]["priority"], meta["priority"])

    def test_sitemap_excludes_admin_private_and_fitify_routes(self):
        """sitemap.xml must not contain admin.html, API endpoints, server_data, hash fragments, or fitify."""
        with open(SITEMAP_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("/admin.html", content)
        self.assertNotIn("/api/", content)
        self.assertNotIn("/server_data/", content)
        self.assertNotIn("#", content)
        self.assertNotIn("fitify", content.lower())

    def test_canonical_robots_unique_titles_descriptions_and_h1_on_rizzafit_pages(self):
        """Each public RizzaFit page must have unique title, unique description, canonical, robots, and H1."""
        pages = [
            (INDEX_FILE, "https://rizzafit.ru/"),
            (PROGRAMS_FILE, "https://rizzafit.ru/programs.html"),
            (EXERCISES_FILE, "https://rizzafit.ru/exercises.html"),
            (COACH_FILE, "https://rizzafit.ru/ai-coach.html"),
        ]
        titles = set()
        descriptions = set()
        for fpath, expected_canon in pages:
            self.assertTrue(os.path.isfile(fpath), f"Missing SEO page: {fpath}")
            with open(fpath, "r", encoding="utf-8") as f:
                html = f.read()
            self.assertIn(f'<link rel="canonical" href="{expected_canon}">', html)
            self.assertIn('<meta name="robots" content="index, follow">', html)
            self.assertNotIn("user-scalable=no", html)
            self.assertNotIn("fitify", html.lower())
            if fpath != INDEX_FILE:
                self.assertIn('aria-current="page"', html)
                self.assertIn(".rf-seo-top .brand{flex:0 0 auto", html)

            t_m = re.search(r"<title>(.*?)</title>", html, re.S)
            d_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.S)
            h1_list = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            self.assertIsNotNone(t_m)
            self.assertIsNotNone(d_m)
            self.assertEqual(len(h1_list), 1, f"{fpath} must have exactly one <h1>")
            titles.add(t_m.group(1).strip())
            descriptions.add(d_m.group(1).strip())

        self.assertEqual(len(titles), 4, "Titles across the 4 public RizzaFit pages must be unique")
        self.assertEqual(len(descriptions), 4, "Meta descriptions across the 4 public RizzaFit pages must be unique")

    def test_rizzafit_seo_pages_and_sitemap_http_serving(self):
        """GET on public RizzaFit SEO pages and /sitemap.xml must return 200 OK with valid headers."""
        s_code, s_hdrs, s_body = invoke_static_get("/sitemap.xml")
        self.assertEqual(s_code, 200)
        self.assertTrue("xml" in s_hdrs.get("content-type", "") or "text/" in s_hdrs.get("content-type", ""))
        tree = ET.fromstring(s_body)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text.strip() for el in tree.findall("ns:url/ns:loc", ns)]
        self.assertEqual(len(locs), 4)
        self.assertFalse(any("fitify" in u.lower() for u in locs))

        for path, canon in [
            ("/", "https://rizzafit.ru/"),
            ("/programs.html", "https://rizzafit.ru/programs.html"),
            ("/exercises.html", "https://rizzafit.ru/exercises.html"),
            ("/ai-coach.html", "https://rizzafit.ru/ai-coach.html"),
        ]:
            code, hdrs, body_bytes = invoke_static_get(path)
            self.assertEqual(code, 200, f"GET {path} returned {code}")
            self.assertIn("text/html", hdrs.get("content-type", ""))
            body = body_bytes.decode("utf-8")
            self.assertIn(f'<link rel="canonical" href="{canon}">', body)
            self.assertIn('<meta name="robots" content="index, follow">', body)

    def test_fitify_files_preserved_on_disk_and_not_deleted(self):
        """Excluding Fitify from SEO must not delete its existing files/directories."""
        self.assertTrue(os.path.isfile(FITIFY_INDEX_FILE))
        self.assertTrue(os.path.isfile(FITIFY_MUSCLES_FILE))


if __name__ == "__main__":
    unittest.main()
