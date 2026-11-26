"""Tests for PII-free aggregated feature telemetry (PR 4.3)."""

import contextlib
import sqlite3
import subprocess
import unittest

import server
from growth import db as growth_db, metrics as growth_metrics, telemetry
from tests.test_growth_tasks import invoke_http
from tests.test_isolation import IsolatedServerTestCase


class TestGrowthTelemetry(IsolatedServerTestCase):
    def setUp(self):
        super().setUp()
        telemetry.reset_rate_limiter()
        self.admin_pw = "TelAdm_2026!"
        server.set_pw(self.admin_pw)
        code, body = invoke_http("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(code, 200)
        self.admin_hdrs = {
            "Authorization": f"Bearer {body['token']}",
            "Origin": "http://127.0.0.1:8080",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def test_idempotent_migration_and_schema_contains_zero_pii_columns(self):
        with server.db_lock, contextlib.closing(sqlite3.connect(server.DB_FILE)) as conn:
            growth_db.init_growth_db(conn)
            growth_db.init_growth_db(conn)
            conn.commit()
            cols = [r[1] for r in conn.execute("PRAGMA table_info(growth_feature_daily)").fetchall()]
        self.assertEqual(cols, ["date_utc", "event_key", "event_count", "updated_at"])
        for forbidden in ("email", "ip", "user_id", "username", "token"):
            self.assertNotIn(forbidden, cols)

    def test_telemetry_endpoint_allowlist_pii_rejection_size_and_rate_limit(self):
        # 1. Allowlisted events accepted and aggregated without storing PII
        for ev in ("coach_open", "coach_open", "program_select", "seo_landing_cta"):
            code, res = invoke_http("POST", "/api/telemetry/event", {"event": ev}, client_ip="10.0.0.11")
            self.assertEqual(code, 202, msg=f"Failed for {ev}: {res}")
            self.assertTrue(res.get("recorded"))

        # 2. Arbitrary events and extra PII fields must be rejected with 400
        bad_payloads = [
            {"event": "arbitrary_custom_event"},
            {"event": ""},
            {"event": 123},
            {"event": "coach_open", "email": "user@example.com"},
            {"event": "coach_open", "userId": 42},
            {"event": "coach_open", "ip": "1.2.3.4"},
            {"event": "coach_open", "token": "secret"},
            {},
            ["coach_open"],
        ]
        for bad in bad_payloads:
            c_bad, _ = invoke_http("POST", "/api/telemetry/event", bad, client_ip="10.0.0.12")
            self.assertEqual(c_bad, 400, msg=f"Bad payload accepted: {bad!r}")

        # Malformed / empty JSON -> 400
        self.assertEqual(invoke_http("POST", "/api/telemetry/event", b"{bad json", client_ip="10.0.0.12")[0], 400)
        self.assertEqual(invoke_http("POST", "/api/telemetry/event", b"", client_ip="10.0.0.12")[0], 400)

        # 3. Body size > MAX_TELEMETRY_BODY -> 413
        oversized = b'{"event":"coach_open","pad":"' + (b"x" * 1100) + b'"}'
        self.assertEqual(invoke_http("POST", "/api/telemetry/event", oversized, client_ip="10.0.0.13")[0], 413)

        # 4. Analytics endpoint reflects exact counts and marks piiStored=False
        c_an, b_an = invoke_http("GET", "/api/admin/growth/analytics?days=30", headers=self.admin_hdrs)
        self.assertEqual(c_an, 200)
        fu = b_an["featureUsage"]
        self.assertFalse(fu["piiStored"])
        self.assertEqual(fu["totalInPeriod"], 4)
        self.assertEqual(fu["totalAllTime"], 4)
        counts = {item["key"]: item["countPeriod"] for item in fu["byEvent"]}
        self.assertEqual(counts["coach_open"], 2)
        self.assertEqual(counts["program_select"], 1)
        self.assertEqual(counts["seo_landing_cta"], 1)

        # 5. Rate limiting per IP (>30 requests within 60s -> 429)
        for _ in range(telemetry.TELEMETRY_RATE_LIMIT_MAX):
            c_ok, _ = invoke_http("POST", "/api/telemetry/event", {"event": "workout_start"}, client_ip="10.0.0.99")
            self.assertEqual(c_ok, 202)
        c_rl, b_rl = invoke_http("POST", "/api/telemetry/event", {"event": "workout_start"}, client_ip="10.0.0.99")
        self.assertEqual(c_rl, 429)
        self.assertEqual(b_rl["error"], "rate_limit_exceeded")

    def test_frontend_analytics_js_exposes_feature_tracking_safely(self):
        script = r"""
        const assert = require('assert');
        const calls = [];
        global.window = {
          location: { origin: 'https://rizzafit.ru', pathname: '/', hash: '#/coach', href: 'https://rizzafit.ru/#/coach' },
          gtag: (t, name, params) => calls.push({ t, name, params })
        };
        const sent = [];
        global.fetch = (url, opts) => {
          sent.push({ url, body: JSON.parse(opts.body) });
          return Promise.resolve({ ok: true });
        };
        require('./site/analytics.js');
        const A = global.window.RizzaAnalytics;
        assert.strictEqual(A.trackCoachOpen(), true);
        assert.strictEqual(A.trackCoachMessage(), true);
        assert.strictEqual(A.trackCoachRefClick('program'), true);
        assert.strictEqual(A.trackProgramSelect(3), true);
        assert.strictEqual(A.trackProgramDayComplete(3), true);
        assert.strictEqual(A.trackProfileCompleted(), true);
        assert.strictEqual(A.trackReminderToggle(true), true);
        assert.deepStrictEqual(sent.map(x => x.body.event), [
          'coach_open', 'coach_message_sent', 'coach_ref_click',
          'program_select', 'program_day_complete', 'profile_completed', 'reminder_toggle'
        ]);
        console.log('ANALYTICS_TELEMETRY_JS_OK');
        """
        res = subprocess.run(["node", "-e", script], cwd=server.ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)
        self.assertIn("ANALYTICS_TELEMETRY_JS_OK", res.stdout)


if __name__ == "__main__":
    unittest.main()
