"""HTTP serving tests for SEO endpoints (robots.txt, sitemap.xml, root /).
Tests in-memory execution via server.H handler without requiring external network sockets.
"""
import io
import os
import unittest
from email.message import Message

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


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


class TestSeoHttpServing(unittest.TestCase):
    def test_get_robots_txt_http_200(self):
        """GET /robots.txt must return 200 OK with text/plain content type and valid directives."""
        status, headers, body_bytes = invoke_static_get("/robots.txt")
        self.assertEqual(status, 200, f"Expected 200, got {status}")

        ctype = headers.get("content-type", "")
        self.assertTrue("text/plain" in ctype or "text/" in ctype, f"Unexpected content-type: {ctype}")

        body = body_bytes.decode("utf-8")
        self.assertIn("User-agent: *", body)
        self.assertIn("Sitemap: https://rizzafit.ru/sitemap.xml", body)
        self.assertIn("Disallow: /admin.html", body)

    def test_get_sitemap_xml_http_200(self):
        """GET /sitemap.xml must return 200 OK with XML content type and valid canonical location."""
        status, headers, body_bytes = invoke_static_get("/sitemap.xml")
        self.assertEqual(status, 200, f"Expected 200, got {status}")

        ctype = headers.get("content-type", "")
        self.assertTrue("xml" in ctype or "text/" in ctype, f"Unexpected content-type: {ctype}")

        body = body_bytes.decode("utf-8")
        self.assertIn("<loc>https://rizzafit.ru/</loc>", body)
        self.assertNotIn("#", body, "sitemap.xml must never contain fragment identifiers")

    def test_get_root_page_http_200_and_seo_headers(self):
        """GET / must return 200 OK with text/html and contain canonical link and Schema.org data."""
        status, headers, body_bytes = invoke_static_get("/")
        self.assertEqual(status, 200, f"Expected 200, got {status}")

        ctype = headers.get("content-type", "")
        self.assertTrue("text/html" in ctype, f"Unexpected content-type: {ctype}")

        body = body_bytes.decode("utf-8")
        self.assertIn('<link rel="canonical" href="https://rizzafit.ru/">', body)
        self.assertIn('<meta name="description"', body)
        self.assertIn('application/ld+json', body)

    def test_path_traversal_blocked(self):
        """Attempting path traversal via dots must return 400 bad path."""
        status, _, _ = invoke_static_get("/../etc/passwd")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
