"""Regression tests for Stage 3 Obsidian Athletic 2.0 inner screens:
- Verifies Home, Programs/Workouts, Exercises, Profile, AI Coach, and Workout Player
  renderers keep all existing IDs, routes, and Stage 3 responsive wrappers
- Verifies style.css contains Stage 3 responsive breakpoints (640px, 1024px, 1366px)
- Verifies AI Coach endpoints and cancellation/retry hooks remain untouched
- Verifies site/app.js passes Node syntax check cleanly
"""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestStage3SiteScreens(unittest.TestCase):
    def test_app_js_preserves_routes_ids_and_stage3_wrappers(self):
        with open(os.path.join(SITE, "app.js"), encoding="utf-8") as f:
            app_js = f.read()

        # Required routes and hooks preserved
        for token in (
            "home()", "coach()", "programs(arg)", "program(id)",
            "workouts(tab)", "workout(id)", "exercises()", "exercise(id)", "profile()",
            "id=\"hsearch\"", "id=\"wo-tab-workouts\"", "id=\"wo-tab-programs\"",
            "id=\"prog-pin\"", "id=\"prog-tick\"", "id=\"wo-unlock-main\"",
            "id=\"go\"", "id=\"warmup\"", "id=\"log-pr-btn\"",
            "id=\"fp-edit-btn\"", "id=\"body-log-btn\"", "id=\"cform\"", "id=\"cin\"", "id=\"cclr\"",
            "/api/coach", "/api/coach/history", "_cancelCoachRequest",
        ):
            self.assertIn(token, app_js, msg=f"Missing preserved contract in site/app.js: {token}")

        # Stage 3 responsive screen wrappers across all 6 screens
        for cls in (
            "rf-home-top", "rf-bento-main", "rf-bento-side", "rf-home-programs",
            "rf-detail-layout", "rf-detail-main", "rf-detail-side", "rf-sticky-box",
            "rf-programs-grid", "rf-filter-bar", "rf-ex-detail", "rf-ex-media", "rf-ex-body",
            "rf-profile-layout", "rf-profile-aside", "rf-profile-main", "rf-auth-gate-wrap",
            "rf-coach-layout", "rf-coach-aside", "rf-player-right",
        ):
            self.assertIn(cls, app_js, msg=f"Missing Stage 3 wrapper class in site/app.js: {cls}")

    def test_style_css_stage3_responsive_screen_rules(self):
        with open(os.path.join(SITE, "style.css"), encoding="utf-8") as f:
            css = f.read()

        for marker in (
            "STAGE 3: RESPONSIVE INNER SCREENS",
            ".rf-home-top",
            ".rf-detail-layout",
            ".rf-ex-detail",
            ".rf-profile-layout",
            ".rf-coach-layout",
            ".rf-player-right",
            "@media (min-width: 640px)",
            "@media (min-width: 1024px)",
            "@media (min-width: 1366px)",
            ".p-body:not(.rest-mode)",
            "bottom: 16px;",
        ):
            self.assertIn(marker, css, msg=f"Missing Stage 3 CSS marker: {marker}")

    def test_app_js_node_syntax(self):
        res = subprocess.run(["node", "--check", os.path.join(SITE, "app.js")], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)
