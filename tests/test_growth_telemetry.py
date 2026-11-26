"""Tests for PII-free aggregated feature telemetry (PR 4.3)."""

import contextlib
import sqlite3
import subprocess
import threading
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
            {"event": " coach_open "},
            {"event": "COACH_OPEN"},
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

        # Resilience: telemetry failure (rejected Promise or sync throw) must never break app
        resilient_script = r"""
        const assert = require('assert');
        global.window = {
          location: { origin: 'https://rizzafit.ru', pathname: '/', hash: '#/', href: 'https://rizzafit.ru/#/' }
        };
        global.fetch = () => Promise.reject(new Error('network down'));
        require('./site/analytics.js');
        assert.doesNotThrow(() => global.window.RizzaAnalytics.trackCoachOpen());
        global.fetch = () => { throw new Error('sync fail'); };
        assert.strictEqual(global.window.RizzaAnalytics.trackWorkoutStart(1, 'Test') || 'ok', 'ok');
        console.log('ANALYTICS_RESILIENCE_OK');
        """
        res2 = subprocess.run(["node", "-e", resilient_script], cwd=server.ROOT, capture_output=True, text=True)
        self.assertEqual(res2.returncode, 0, msg=res2.stderr or res2.stdout)
        self.assertIn("ANALYTICS_RESILIENCE_OK", res2.stdout)

    def test_ip_spoofing_blocked_and_trusted_proxy_respected(self):
        # 1. Direct untrusted socket IP rotating forged X-Real-IP and X-Forwarded-For headers cannot bypass 30/60s cap
        for idx in range(telemetry.TELEMETRY_RATE_LIMIT_MAX):
            c_ok, _ = invoke_http(
                "POST",
                "/api/telemetry/event",
                {"event": "coach_open"},
                headers={
                    "X-Real-IP": f"10.1.0.{idx + 1}",
                    "X-Forwarded-For": f"172.16.0.{idx + 1}",
                },
                client_ip="198.51.100.10",
            )
            self.assertEqual(c_ok, 202)
        c_spoof_blk, b_blk = invoke_http(
            "POST",
            "/api/telemetry/event",
            {"event": "coach_open"},
            headers={"X-Real-IP": "10.99.99.99", "X-Forwarded-For": "8.8.8.8"},
            client_ip="198.51.100.10",
        )
        self.assertEqual(c_spoof_blk, 429)
        self.assertEqual(b_blk["error"], "rate_limit_exceeded")

        # 2. Trusted Nginx reverse proxy (127.0.0.1 / ::1) uses validated X-Real-IP and ignores X-Forwarded-For
        for idx in range(telemetry.TELEMETRY_RATE_LIMIT_MAX):
            c_prx, _ = invoke_http(
                "POST",
                "/api/telemetry/event",
                {"event": "program_select"},
                headers={
                    "X-Real-IP": "203.0.113.5",
                    "X-Forwarded-For": f"192.0.2.{idx + 1}",
                },
                client_ip="127.0.0.1",
            )
            self.assertEqual(c_prx, 202)
        # 31st request for 203.0.113.5 even with a new X-Forwarded-For is blocked (429)
        c_prx_blk, _ = invoke_http(
            "POST",
            "/api/telemetry/event",
            {"event": "program_select"},
            headers={"X-Real-IP": "203.0.113.5", "X-Forwarded-For": "1.1.1.1"},
            client_ip="::1",
        )
        self.assertEqual(c_prx_blk, 429)
        # Different real client behind Nginx proxy is NOT blocked
        c_other, _ = invoke_http(
            "POST",
            "/api/telemetry/event",
            {"event": "program_select"},
            headers={"X-Real-IP": "203.0.113.6", "X-Forwarded-For": "1.1.1.1"},
            client_ip="127.0.0.1",
        )
        self.assertEqual(c_other, 202)
        # Invalid X-Real-IP behind trusted proxy safely falls back to proxy socket IP
        c_bad_hdr, _ = invoke_http(
            "POST",
            "/api/telemetry/event",
            {"event": "workout_start"},
            headers={"X-Real-IP": "not-an-ip, 1.2.3.4"},
            client_ip="127.0.0.1",
        )
        self.assertEqual(c_bad_hdr, 202)

    def test_rate_limit_capacity_flood_cannot_reset_existing_clients_and_recovers_after_window(self):
        t0 = 1000.0
        for _ in range(telemetry.TELEMETRY_RATE_LIMIT_MAX):
            self.assertTrue(telemetry._check_rate_limit("203.0.113.10", now_ts=t0))
        self.assertFalse(telemetry._check_rate_limit("203.0.113.10", now_ts=t0 + 1.0))

        for _ in range(25):
            self.assertTrue(telemetry._check_rate_limit("203.0.113.11", now_ts=t0))

        # Attacker floods 600 distinct source IPs within the same 60s window
        flood_allowed = 0
        flood_blocked = 0
        for i in range(600):
            ip = f"198.18.{i // 250}.{(i % 250) + 1}"
            if telemetry._check_rate_limit(ip, now_ts=t0 + 5.0):
                flood_allowed += 1
            else:
                flood_blocked += 1

        self.assertEqual(flood_allowed, telemetry.MAX_RL_CAPACITY - 2)
        self.assertEqual(flood_blocked, 600 - (telemetry.MAX_RL_CAPACITY - 2))
        self.assertEqual(len(telemetry._rl_hits), telemetry.MAX_RL_CAPACITY)

        # Existing clients' counters MUST NOT be cleared or reset by the flood
        self.assertFalse(telemetry._check_rate_limit("203.0.113.10", now_ts=t0 + 6.0))
        for _ in range(5):
            self.assertTrue(telemetry._check_rate_limit("203.0.113.11", now_ts=t0 + 6.0))
        self.assertFalse(telemetry._check_rate_limit("203.0.113.11", now_ts=t0 + 6.0))

        # After 60s window passes, expired entries are evicted and clients recover cleanly
        self.assertTrue(telemetry._check_rate_limit("203.0.113.99", now_ts=t0 + 66.0))
        self.assertTrue(telemetry._check_rate_limit("203.0.113.10", now_ts=t0 + 66.0))

    def test_sliding_window_exact_30_per_60s(self):
        t0 = 2000.0
        for _ in range(telemetry.TELEMETRY_RATE_LIMIT_MAX):
            self.assertTrue(telemetry._check_rate_limit("203.0.113.50", now_ts=t0))
        self.assertFalse(telemetry._check_rate_limit("203.0.113.50", now_ts=t0 + 59.0))
        self.assertTrue(telemetry._check_rate_limit("203.0.113.50", now_ts=t0 + 60.1))

    def test_concurrent_requests_thread_safety(self):
        total_threads = 60
        barrier = threading.Barrier(total_threads)
        results = []
        res_lock = threading.Lock()
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                code, _body = invoke_http(
                    "POST",
                    "/api/telemetry/event",
                    {"event": "workout_complete"},
                    client_ip="198.51.100.77",
                )
                with res_lock:
                    results.append(code)
            except Exception as e:
                with res_lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(total_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=15)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), total_threads)
        self.assertEqual(results.count(202), telemetry.TELEMETRY_RATE_LIMIT_MAX)
        self.assertEqual(results.count(429), total_threads - telemetry.TELEMETRY_RATE_LIMIT_MAX)
        an = growth_metrics.compute_analytics(server.DB_FILE, server.db_lock, days=30)
        counts = {item["key"]: item["countPeriod"] for item in an["featureUsage"]["byEvent"]}
        self.assertEqual(counts["workout_complete"], telemetry.TELEMETRY_RATE_LIMIT_MAX)


if __name__ == "__main__":
    unittest.main()
