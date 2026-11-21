"""Unit and HTTP serving tests for Google Analytics 4 (GA4) integration.
Validates tag installation, Measurement ID G-XSBKDCY4CS, SPA virtual page views,
auth & CTA event hooks, strict PII protection, URL sanitization, and decoupled deduplication.
"""
import io
import json
import os
import re
import subprocess
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


def eval_in_analytics_js(js_code_block):
    """Execute arbitrary JavaScript logic against site/analytics.js via node and return parsed JSON."""
    normalized_file = ANALYTICS_FILE.replace("\\", "/")
    node_runner = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync('{normalized_file}', 'utf8');
const events = [];
const sandbox = {{
  window: {{
    location: {{ origin: 'https://rizzafit.ru', pathname: '/', hash: '', href: 'https://rizzafit.ru/' }},
    gtag: function(type, name, params) {{ events.push({{ type: type, name: name, params: params }}); }}
  }},
  document: {{ title: 'RizzaFit' }},
  Date: Date,
  URL: URL,
  events: events
}};
sandbox.window.window = sandbox.window;
sandbox.window.URL = URL;
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const A = sandbox.window.RizzaAnalytics;

const result = (() => {{
  {js_code_block}
}})();
console.log(JSON.stringify({{ res: result, events: events }}));
"""
    proc = subprocess.run(["node", "-e", node_runner], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip())


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

    def test_pii_key_variations_and_case_normalization(self):
        """All variations of sensitive keys (camelCase, UPPERCASE, snake_case) must be stripped."""
        js_code = """
        return A.sanitizeParams({
            userToken: 'token_val1',
            USERTOKEN: 'token_val2',
            user_token: 'token_val3',
            'User-Token': 'token_val4',
            sessionToken: 'token_val5',
            SESSION_TOKEN: 'token_val6',
            initData: 'init_val1',
            InitData: 'init_val2',
            tgWebAppData: 'tg_val1',
            tg_web_app_data: 'tg_val2',
            password: 'secret_pass',
            PassWord: 'secret_pass2',
            email: 'user@domain.com',
            EMAIL: 'user@domain.com',
            auth_code: 'code123',
            AuthCode: 'code123',
            token: 'tok_abc',
            TOKEN: 'tok_abc',
            safe_category: 'fitness',
            method: 'credentials'
        });
        """
        output = eval_in_analytics_js(js_code)
        cleaned = output["res"]

        # Only safe keys must remain
        self.assertEqual(cleaned.get("safe_category"), "fitness")
        self.assertEqual(cleaned.get("method"), "credentials")

        # All sensitive keys must be purged
        for forbidden in [
            "userToken", "USERTOKEN", "user_token", "User-Token",
            "sessionToken", "SESSION_TOKEN", "initData", "InitData",
            "tgWebAppData", "tg_web_app_data", "password", "PassWord",
            "email", "EMAIL", "auth_code", "AuthCode", "token", "TOKEN"
        ]:
            self.assertNotIn(forbidden, cleaned, f"Key {forbidden} was not stripped by sanitizer!")

    def test_nested_objects_and_arrays_pii_sanitization(self):
        """Nested objects and arrays must be recursively sanitized against sensitive keys and values."""
        js_code = """
        return A.sanitizeParams({
            level1: {
                userToken: 'secret_token_123',
                safe_info: 'workout_log',
                level2: {
                    password: 'mypassword',
                    safe_metric: 100,
                    arr: [
                        { email: 'person@site.ru', name: 'athlete' },
                        { sessionToken: 'sess_999' },
                        'clean_item'
                    ]
                }
            },
            top_arr: [
                { initData: 'raw_tg_data', tag: 'pro' },
                'plain_text'
            ]
        });
        """
        output = eval_in_analytics_js(js_code)
        cleaned = output["res"]

        level1 = cleaned.get("level1", {})
        self.assertNotIn("userToken", level1)
        self.assertEqual(level1.get("safe_info"), "workout_log")

        level2 = level1.get("level2", {})
        self.assertNotIn("password", level2)
        self.assertEqual(level2.get("safe_metric"), 100)

        arr = level2.get("arr", [])
        self.assertEqual(len(arr), 3)
        self.assertNotIn("email", arr[0])
        self.assertEqual(arr[0].get("name"), "athlete")
        self.assertNotIn("sessionToken", arr[1])
        self.assertEqual(arr[2], "clean_item")

        top_arr = cleaned.get("top_arr", [])
        self.assertNotIn("initData", top_arr[0])
        self.assertEqual(top_arr[0].get("tag"), "pro")

    def test_pii_in_string_values_sanitization(self):
        """String values containing emails, tokens, or phones must be scrubbed."""
        js_code = """
        return {
            clean_str: A.sanitizeString('Normal description text'),
            email_str: A.sanitizeString('Contact us at support@rizzafit.ru for help'),
            bearer_str: A.sanitizeString('Header is Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz'),
            hex_str: A.sanitizeString('auth secret 0123456789abcdef0123456789abcdef'),
            phone_str: A.sanitizeString('Call support at +7 (999) 123-4567 today')
        };
        """
        output = eval_in_analytics_js(js_code)["res"]

        self.assertEqual(output["clean_str"], "Normal description text")
        self.assertIn("[REDACTED_EMAIL]", output["email_str"])
        self.assertNotIn("support@rizzafit.ru", output["email_str"])

        self.assertIn("[REDACTED_TOKEN]", output["bearer_str"])
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", output["bearer_str"])

        self.assertIn("[REDACTED_TOKEN]", output["hex_str"])
        self.assertNotIn("0123456789abcdef0123456789abcdef", output["hex_str"])

        self.assertIn("[REDACTED_PHONE]", output["phone_str"])
        self.assertNotIn("123-4567", output["phone_str"])

    def test_url_and_path_sanitization(self):
        """URL and SPA path sanitizers must strip all query parameters and sensitive fragments."""
        js_code = """
        return {
            loc_with_query_and_hash: A.getSafeLocation('https://rizzafit.ru/?token=secret123&code=456#/workouts?paymentId=pay789#tgWebAppData=xyz'),
            loc_fitify_query: A.getSafeLocation('https://rizzafit.ru/fitify/index.html?utm_source=tg&ref=promo'),
            path_with_query: A.getSafePath('/?token=secret123#/profile?user=admin'),
            path_spa_clean: A.getSafePath('/#/workouts/programs'),
            path_fitify: A.getSafePath('/fitify/muscles.html?session=abc')
        };
        """
        output = eval_in_analytics_js(js_code)["res"]

        # Safe locations
        self.assertEqual(output["loc_with_query_and_hash"], "https://rizzafit.ru/#/workouts")
        self.assertEqual(output["loc_fitify_query"], "https://rizzafit.ru/fitify/index.html")

        # Safe paths
        self.assertEqual(output["path_with_query"], "/#/profile")
        self.assertEqual(output["path_spa_clean"], "/#/workouts/programs")
        self.assertEqual(output["path_fitify"], "/fitify/muscles.html")

        # Verify no query strings leaked
        for k, v in output.items():
            self.assertNotIn("?", v, f"Query parameter leaked in {k}: {v}")
            self.assertNotIn("token", v.lower())
            self.assertNotIn("secret", v.lower())

    def test_repeated_screen_transitions_and_decoupled_dedup(self):
        """Consecutive identical screen views are debounced, but screen transitions (A -> B -> A) are tracked."""
        js_code = """
        A.resetTrackingState();
        const r1 = A.trackPageView('/#/workouts', 'Workouts');
        const r2 = A.trackPageView('/#/workouts', 'Workouts'); // same screen re-render: must be ignored
        const r3 = A.trackPageView('/#/exercises', 'Exercises'); // transition to B: tracked
        const r4 = A.trackPageView('/#/workouts', 'Workouts'); // return to A: tracked!

        return { r1: r1, r2: r2, r3: r3, r4: r4 };
        """
        output = eval_in_analytics_js(js_code)
        res = output["res"]
        events = [e for e in output["events"] if e.get("name") == "page_view"]

        self.assertTrue(res["r1"], "First view of workouts must be tracked")
        self.assertFalse(res["r2"], "Consecutive identical view of workouts must be debounced")
        self.assertTrue(res["r3"], "Transition to exercises must be tracked")
        self.assertTrue(res["r4"], "Returning to workouts after leaving must be tracked as a new view")

        self.assertEqual(len(events), 3, "Exactly 3 page_view events should be sent for A -> A -> B -> A")
        self.assertEqual(events[0]["params"]["page_path"], "/#/workouts")
        self.assertEqual(events[1]["params"]["page_path"], "/#/exercises")
        self.assertEqual(events[2]["params"]["page_path"], "/#/workouts")

    def test_repeated_user_actions_not_blocked(self):
        """Legitimate repeated user actions are not blocked, while microsecond double-bounces are caught."""
        js_code = """
        A.resetTrackingState();
        const r1 = A.trackCta('open_auth_modal', 'login');
        const r2 = A.trackCta('open_auth_modal', 'login'); // immediate microsecond double-bounce: caught

        // Simulate 300ms passing
        const RealDateNow = Date.now;
        Date.now = () => RealDateNow() + 300;
        const r3 = A.trackCta('open_auth_modal', 'login'); // deliberate repeated click: tracked!
        Date.now = RealDateNow;

        return { r1: r1, r2: r2, r3: r3 };
        """
        output = eval_in_analytics_js(js_code)
        res = output["res"]
        cta_events = [e for e in output["events"] if e.get("name") == "cta_click"]

        self.assertTrue(res["r1"])
        self.assertFalse(res["r2"])
        self.assertTrue(res["r3"], "Deliberate repeat action after debounce window must not be blocked")
        self.assertEqual(len(cta_events), 2)

    def test_successful_vs_failed_auth_tracking_logic(self):
        """app.js must strictly decouple registration and login and only track after confirmed backend success."""
        with open(APP_FILE, "r", encoding="utf-8") as f:
            app_code = f.read()

        # Check openCloudAuthModal handling
        # Registration must NOT trigger duplicate trackLogin
        reg_block_match = re.search(
            r'function openCloudAuthModal\(.*?const endpoint = isReg \?.*?if\s*\(\s*!r\.ok\s*\)\s*\{\s*errEl\.textContent\s*=\s*j\.error.*?saveUserMeta\(j\.user\);(.*?)if\s*\(j\.state',
            app_code,
            re.DOTALL
        )
        self.assertIsNotNone(reg_block_match, "Auth handling block after successful response must exist in app.js")
        auth_inner = reg_block_match.group(1)

        self.assertIn("trackSignUp('credentials')", auth_inner)
        self.assertIn("trackLogin('credentials')", auth_inner)
        # Ensure 'if (isReg) { trackSignUp } else { trackLogin }' structure is present
        self.assertIn("if (isReg)", auth_inner)
        self.assertIn("else", auth_inner)

        # Ensure no login tracking in local fallback error branch
        local_auth_match = re.search(r'const finishLocalAuth\s*=\s*async\s*\(\)\s*=>\s*\{(.*?)\};', app_code, re.DOTALL)
        self.assertIsNotNone(local_auth_match)
        self.assertNotIn("trackLogin", local_auth_match.group(1), "Local offline fallback must not send server login event")
        self.assertNotIn("trackSignUp", local_auth_match.group(1), "Local offline fallback must not send server sign_up event")

    def test_no_duplicate_lang_onclick_in_app_js(self):
        """app.js must not assign lang onclick redundantly."""
        with open(APP_FILE, "r", encoding="utf-8") as f:
            code = f.read()

        # Check for duplicate document.getElementById('lang').onclick
        direct_onclicks = len(re.findall(r"document\.getElementById\(['\"]lang['\"]\)\.onclick", code))
        self.assertEqual(direct_onclicks, 0, "Redundant direct document.getElementById('lang').onclick was found")

        # Check langBtn.onclick assigned exactly once
        lang_btn_onclicks = len(re.findall(r"langBtn\.onclick\s*=", code))
        self.assertEqual(lang_btn_onclicks, 1, "langBtn.onclick must be assigned exactly once")

    def test_no_duplicate_or_competing_counters(self):
        """Ensure no competing or duplicate measurement IDs are present in site HTML files."""
        html_files = [INDEX_FILE, ADMIN_FILE, FITIFY_INDEX, FITIFY_MUSCLES]
        for fpath in html_files:
            with open(fpath, "r", encoding="utf-8") as f:
                c = f.read()
            self.assertNotIn("UA-", c, f"Found deprecated UA tag in {fpath}")
            self.assertNotIn("GTM-", c, f"Found GTM container in {fpath}")
            self.assertNotIn("mc.yandex", c, f"Found Yandex Metrika in {fpath}")

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
