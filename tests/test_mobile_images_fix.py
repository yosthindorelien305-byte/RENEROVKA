"""Regression tests for mobile program and workout image rendering & Service Worker caching."""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestMobileImagesFix(unittest.TestCase):
    def test_style_css_mobile_card_image_rules(self):
        with open(os.path.join(SITE, "style.css"), encoding="utf-8") as f:
            css = f.read()

        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)
        cover_match = re.search(r"\.card\s+img\.cover\s*\{([^}]*)\}", css)
        self.assertIsNotNone(cover_match, "Missing .card img.cover rule")
        cover_block = cover_match.group(1)
        self.assertIn("flex: 0 0 auto;", cover_block)
        self.assertIn("aspect-ratio: 16 / 9;", cover_block)

        ex_img_match = re.search(r"(?m)^\.ex-img\s*\{([^}]*)\}", css)
        self.assertIsNotNone(ex_img_match, "Missing .ex-img rule")
        ex_img_block = ex_img_match.group(1)
        self.assertIn("width: 100%;", ex_img_block)
        self.assertIn("flex: 0 0 auto;", ex_img_block)

        mob_media = css.split("@media (max-width: 1023px)", 1)[1].split("@media", 1)[0]
        contents_block = mob_media.split("display: contents;", 1)[0]
        self.assertNotIn(".rf-wo-detail,", contents_block)

    def test_app_js_defers_hidden_tab_and_removes_conflicting_inline_aspect_ratio(self):
        with open(os.path.join(SITE, "app.js"), encoding="utf-8") as f:
            app_js = f.read()

        self.assertNotIn('<div class="ex-img" style="aspect-ratio:16/9">', app_js)
        self.assertIn('id="programs-list" class="grid rf-programs-grid"', app_js)
        self.assertIn("const ensurePrograms = () =>", app_js)
        self.assertIn("const ensureWorkouts = () =>", app_js)
        self.assertIn('decoding="async"', app_js)
        self.assertIn("img.dataset.rfRetried = '1'", app_js)

    def test_service_worker_avoids_404_precache_and_isolates_media_cache(self):
        with open(os.path.join(SITE, "sw.js"), encoding="utf-8") as f:
            sw_js = f.read()

        self.assertIn("flexa-shell-v68", sw_js)
        self.assertIn("MEDIA_CACHE_NAME = 'flexa-media-v1'", sw_js)
        self.assertNotIn("./content/texts.json", sw_js)
        self.assertIn("/content/uploads/", sw_js)
        self.assertIn("res.status === 200", sw_js)
        self.assertIn("caches.match(req, { ignoreSearch: true }).then(hit => hit || Response.error())", sw_js)

    def test_server_and_catalog_assets_exist(self):
        with open(os.path.join(ROOT, "server.py"), encoding="utf-8") as f:
            srv = f.read()
        self.assertIn("ThreadingHTTPServer.request_queue_size = 128", srv)

        with open(os.path.join(SITE, "data.json"), encoding="utf-8") as f:
            data = json.load(f)

        for prog in data.get("programs", []):
            if prog.get("img"):
                p_path = os.path.join(SITE, "img", "programs", f"{prog['id']}.jpg")
                self.assertTrue(os.path.isfile(p_path), msg=f"Missing program cover: {p_path}")

        ex_by_id = {e["id"]: e for e in data.get("exercises", [])}
        checked_first = 0
        for wo in data.get("workouts", []):
            steps = wo.get("s") or []
            if not steps or len(steps[0]) < 2:
                continue
            ex = ex_by_id.get(steps[0][1][0])
            if ex and ex.get("img"):
                checked_first += 1
                ex_path = os.path.join(SITE, "img", "ex", f"svg_norm_{ex['id']}.svg")
                self.assertTrue(os.path.isfile(ex_path), msg=f"Missing workout SVG: {ex_path}")
        self.assertGreater(checked_first, 50)
