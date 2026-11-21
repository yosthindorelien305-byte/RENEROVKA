"""Unit tests for SEO Stage 1: robots.txt, sitemap.xml, and HTML meta tags.
Validates file formats, schemas, and standards compliance without mutating repository data.
"""
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
ROBOTS_FILE = os.path.join(SITE, "robots.txt")
SITEMAP_FILE = os.path.join(SITE, "sitemap.xml")
INDEX_FILE = os.path.join(SITE, "index.html")
LOGO_FILE = os.path.join(SITE, "content", "uploads", "logo.jpg")


class TestSeoStage1Files(unittest.TestCase):
    def test_robots_txt_exists_and_valid(self):
        """robots.txt must exist, be non-empty, contain valid directives and no deprecated ones."""
        self.assertTrue(os.path.isfile(ROBOTS_FILE), "site/robots.txt must exist")
        with open(ROBOTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertGreater(len(content.strip()), 50, "robots.txt must not be empty")
        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("Allow: /style.css", content)
        self.assertIn("Allow: /*.js$", content)
        self.assertIn("Allow: /*.css$", content)
        self.assertIn("Allow: /img/", content)
        self.assertIn("Allow: /content/uploads/", content)
        self.assertIn("Disallow: /admin.html", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn("Disallow: /server_data/", content)
        self.assertNotIn("Disallow: /fitify/", content)
        self.assertIn("Sitemap: https://rizzafit.ru/sitemap.xml", content)

        # Ensure no deprecated Google directives are present
        self.assertNotIn("Host:", content, "Host directive is deprecated by Google and must not be used")
        self.assertNotIn("Crawl-delay:", content, "Crawl-delay is ignored by Googlebot and should not be used")

    def test_sitemap_xml_validity_and_schema(self):
        """sitemap.xml must be valid XML according to sitemaps.org schema, containing only real canonical URLs."""
        self.assertTrue(os.path.isfile(SITEMAP_FILE), "site/sitemap.xml must exist")
        try:
            tree = ET.parse(SITEMAP_FILE)
            root_el = tree.getroot()
        except Exception as e:
            self.fail(f"sitemap.xml failed XML parsing: {e}")

        self.assertEqual(root_el.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root_el.findall("ns:url", ns)

        # Only real, existing canonical URL (https://rizzafit.ru/) should be listed
        self.assertEqual(len(urls), 1, "sitemap.xml must contain only the real indexable canonical URL")

        loc_el = urls[0].find("ns:loc", ns)
        self.assertIsNotNone(loc_el, "<loc> element missing in sitemap URL entry")
        loc = loc_el.text.strip()
        self.assertEqual(loc, "https://rizzafit.ru/")

        # Strictly forbid SPA hash fragments and private routes in sitemap
        self.assertNotIn("#", loc, "sitemap.xml must never contain hash '#' fragments")
        self.assertNotIn("/admin.html", loc)
        self.assertNotIn("/api/", loc)

        # Validate changefreq and priority
        cf_el = urls[0].find("ns:changefreq", ns)
        self.assertIsNotNone(cf_el)
        self.assertIn(cf_el.text.strip(), ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"])

        pr_el = urls[0].find("ns:priority", ns)
        self.assertIsNotNone(pr_el)
        self.assertTrue(0.0 <= float(pr_el.text.strip()) <= 1.0)

    def test_index_html_seo_meta_tags(self):
        """index.html must contain meta description, canonical, robots, OpenGraph and Twitter card tags."""
        self.assertTrue(os.path.isfile(INDEX_FILE), "site/index.html must exist")
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('<meta name="description"', html)
        self.assertIn('<link rel="canonical" href="https://rizzafit.ru/">', html)
        self.assertIn('<meta name="robots" content="index, follow">', html)

        # OpenGraph tags
        self.assertIn('<meta property="og:type" content="website">', html)
        self.assertIn('<meta property="og:url" content="https://rizzafit.ru/">', html)
        self.assertIn('<meta property="og:title"', html)
        self.assertIn('<meta property="og:description"', html)
        self.assertIn('<meta property="og:image" content="https://rizzafit.ru/content/uploads/logo.jpg">', html)
        self.assertIn('<meta property="og:site_name" content="RizzaFit">', html)
        self.assertIn('<meta property="og:locale" content="ru_RU">', html)

        # Twitter Card
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn('<meta name="twitter:title"', html)
        self.assertIn('<meta name="twitter:description"', html)
        self.assertIn('<meta name="twitter:image" content="https://rizzafit.ru/content/uploads/logo.jpg">', html)

    def test_schema_org_json_ld_validity(self):
        """index.html must contain valid Schema.org JSON-LD structured data with WebSite and WebApplication."""
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            html = f.read()

        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        self.assertIsNotNone(match, "Schema.org JSON-LD script block must be present in index.html")

        try:
            ld = json.loads(match.group(1))
        except Exception as e:
            self.fail(f"JSON-LD syntax error in index.html: {e}")

        self.assertEqual(ld.get("@context"), "https://schema.org")
        graph = ld.get("@graph", [])
        types = [item.get("@type") for item in graph]
        self.assertIn("WebSite", types, "WebSite entity must exist in Schema.org graph")
        self.assertIn("WebApplication", types, "WebApplication entity must exist in Schema.org graph")

        app_item = next(item for item in graph if item.get("@type") == "WebApplication")
        self.assertEqual(app_item.get("name"), "RizzaFit")
        offers = app_item.get("offers", {})
        self.assertEqual(offers.get("price"), "0", "Current free access model price must be '0'")
        self.assertEqual(offers.get("priceCurrency"), "RUB")

    def test_logo_image_asset_exists(self):
        """The image referenced by OpenGraph and Twitter card must physically exist on disk."""
        self.assertTrue(os.path.isfile(LOGO_FILE), "site/content/uploads/logo.jpg must exist on disk")
        self.assertGreater(os.path.getsize(LOGO_FILE), 1000, "logo.jpg must be a valid non-empty image file")


if __name__ == "__main__":
    unittest.main()
