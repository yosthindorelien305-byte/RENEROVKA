"""Tests for AI Growth authorization, append-only SQLite audit log, and isolation (PR 4.1)."""

import contextlib
import gc
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from email.message import Message

import server
from growth import db as growth_db
from growth import metrics as growth_metrics
from tests.test_isolation import IsolatedServerTestCase, PROD_SECRET_DIR


def invoke_http(method, path, body=None, headers=None, client_ip="127.0.0.1"):
    """Invoke server.H handler in-process without opening network sockets."""
    raw = (
        json.dumps(body).encode("utf-8")
        if body is not None and not isinstance(body, (bytes, bytearray))
        else (body or b"")
    )
    hdrs = Message()
    if isinstance(body, dict):
        hdrs["Content-Type"] = "application/json"
    hdrs["Content-Length"] = str(len(raw))
    if headers:
        for k, v in headers.items():
            hdrs[k] = v

    h = server.H.__new__(server.H)
    h.path = path
    h.command = method
    h.headers = hdrs
    h.client_address = (client_ip, 50001)
    h.rfile = io.BytesIO(raw)
    h.wfile = io.BytesIO()
    h.request_version = "HTTP/1.1"
    h._headers_buffer = []

    captured = {"status": None, "body": None}

    def fake_send_j(code, obj, headers=None):
        captured["status"] = code
        captured["body"] = obj

    h.send_j = fake_send_j
    getattr(h, f"do_{method}")()
    return captured["status"], captured["body"]


def _snapshot(path):
    if not os.path.exists(path):
        return (False, None)
    with open(path, "rb") as f:
        return (True, hashlib.sha256(f.read()).hexdigest())


class TestGrowthSecurityAndAudit(IsolatedServerTestCase):
    def setUp(self):
        super().setUp()
        self.admin_pw = "GrowthAdmPass_2026!"
        server.set_pw(self.admin_pw)
        now = int(time.time())
        with server.db_lock, sqlite3.connect(server.DB_FILE) as conn:
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (10, 'regular_user', 's1', 'h1', 'Regular User', 'reg@example.com', 'free', 0, 0, ?, ?)",
                (now, now),
            )
            conn.execute(
                "INSERT INTO user_sessions (token, user_id, expires_at) VALUES ('user_sess_tok_123', 10, ?)",
                (now + 86400,),
            )
            conn.commit()

    def _login_admin(self):
        code, body = invoke_http("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(code, 200)
        return body["token"]

    def test_growth_routes_require_admin_auth_and_reject_user_tokens(self):
        routes_get = (
            "/api/admin/growth/overview?days=30",
            "/api/admin/growth/analytics?days=30",
            "/api/admin/growth/audit?limit=10&offset=0",
        )
        for route in routes_get:
            code_anon, body_anon = invoke_http("GET", route)
            self.assertEqual(code_anon, 401, msg=f"Expected 401 for anonymous GET {route}")
            self.assertEqual(body_anon.get("error"), "unauthorized")

            code_user, body_user = invoke_http(
                "GET", route, headers={"Authorization": "Bearer user_sess_tok_123"}
            )
            self.assertEqual(code_user, 401, msg=f"Expected 401 for regular user GET {route}")
            self.assertEqual(body_user.get("error"), "unauthorized")

        for method in ("POST", "PUT", "DELETE", "PATCH"):
            code_anon, _ = invoke_http(method, "/api/admin/growth/audit", {"action": "tamper"})
            self.assertEqual(code_anon, 401)
            code_user, _ = invoke_http(
                method,
                "/api/admin/growth/audit",
                {"action": "tamper"},
                headers={"Authorization": "Bearer user_sess_tok_123"},
            )
            self.assertEqual(code_user, 401)

    def test_audit_log_http_and_sqlite_append_only_enforcement(self):
        tok = self._login_admin()
        hdrs = {"Authorization": f"Bearer {tok}"}

        for method in ("POST", "PUT", "DELETE", "PATCH"):
            code, body = invoke_http(method, "/api/admin/growth/audit", {"id": 1}, headers=hdrs)
            self.assertEqual(code, 405, msg=f"{method} on audit must return 405")
            self.assertIn("append-only", body.get("error", ""))

        # Insert event and verify SQLite BEFORE UPDATE / BEFORE DELETE triggers raise IntegrityError
        eid = growth_db.record_audit_event(
            server.DB_FILE,
            server.db_lock,
            action="test.event",
            module="growth",
            target="unit-test",
            status="ok",
            actor="admin",
            actor_ip="127.0.0.1",
            details={"safe": 1, "secret_token": "MUST_SCRUB", "user_email": "leak@example.com"},
            backup_ref="backups/b1.json",
        )
        self.assertGreater(eid, 0)

        with server.db_lock, sqlite3.connect(server.DB_FILE) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE growth_audit_log SET action = 'tampered' WHERE id = ?", (eid,))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM growth_audit_log WHERE id = ?", (eid,))

        code_get, res = invoke_http("GET", "/api/admin/growth/audit?limit=10&offset=0", headers=hdrs)
        self.assertEqual(code_get, 200)
        self.assertTrue(res["appendOnlyEnforced"])
        self.assertGreaterEqual(res["total"], 2)  # admin.login + test.event
        top = res["entries"][0]
        self.assertEqual(top["action"], "test.event")
        self.assertEqual(top["backupRef"], "backups/b1.json")
        self.assertEqual(top["actorIp"], "127.0.0.1")
        self.assertEqual(top["details"].get("safe"), 1)
        self.assertNotIn("secret_token", top["details"])
        self.assertNotIn("user_email", top["details"])
        self.assertNotIn("MUST_SCRUB", json.dumps(top))
        self.assertNotIn("leak@example.com", json.dumps(top))

    def test_audit_pagination_filters_and_admin_action_logging(self):
        tok = self._login_admin()
        hdrs = {"Authorization": f"Bearer {tok}"}

        invoke_http("POST", "/api/admin/user/plan", {"userId": 10, "plan": "pro", "days": 30}, headers=hdrs)
        invoke_http("POST", "/api/admin/user/block", {"userId": 10, "blocked": True}, headers=hdrs)
        invoke_http("POST", "/api/admin/logout", {}, headers=hdrs)

        # Old token must now be invalid
        code_after_lo, _ = invoke_http("GET", "/api/admin/growth/audit", headers=hdrs)
        self.assertEqual(code_after_lo, 401)

        tok2 = self._login_admin()
        hdrs2 = {"Authorization": f"Bearer {tok2}"}

        code_p1, p1 = invoke_http("GET", "/api/admin/growth/audit?limit=2&offset=0", headers=hdrs2)
        self.assertEqual(code_p1, 200)
        self.assertEqual(len(p1["entries"]), 2)
        self.assertTrue(p1["hasMore"])

        code_p2, p2 = invoke_http("GET", "/api/admin/growth/audit?limit=2&offset=2", headers=hdrs2)
        self.assertEqual(code_p2, 200)
        self.assertGreaterEqual(len(p2["entries"]), 2)
        self.assertNotEqual(p1["entries"][0]["id"], p2["entries"][0]["id"])

        code_mod, users_audit = invoke_http("GET", "/api/admin/growth/audit?module=users&limit=10", headers=hdrs2)
        self.assertEqual(code_mod, 200)
        actions = [e["action"] for e in users_audit["entries"]]
        self.assertIn("user.plan_update", actions)
        self.assertIn("user.block_toggle", actions)

        code_nf, _ = invoke_http("GET", "/api/admin/growth/nonexistent", headers=hdrs2)
        self.assertEqual(code_nf, 404)

    def test_configs_and_ai_coach_remain_isolated_and_intact(self):
        prod_files = [
            os.path.join(PROD_SECRET_DIR, "ai.json"),
            os.path.join(PROD_SECRET_DIR, "telegram.json"),
            os.path.join(PROD_SECRET_DIR, "yookassa.json"),
            os.path.join(PROD_SECRET_DIR, "admin.json"),
        ]
        before = {p: _snapshot(p) for p in prod_files}

        # Configure isolated builtin AI Coach and invoke Growth analytics + AI Coach
        server.save_ai_cfg({"provider": "builtin", "enabled": True, "model": "gemini-flash-lite-latest", "prompt": ""})
        tok = self._login_admin()
        code, overview = invoke_http("GET", "/api/admin/growth/overview", headers={"Authorization": f"Bearer {tok}"})
        self.assertEqual(code, 200)
        self.assertEqual(overview["systemStatus"]["aiGrowthLlm"], "disabled_pr41")

        # Existing builtin AI Coach works normally without changes
        reply = server.ask_ai([{"role": "user", "text": "Составь программу тренировок дома"}], "RizzaFit", None)
        self.assertTrue(isinstance(reply, str) and len(reply) > 10)

        for p in prod_files:
            self.assertEqual(_snapshot(p), before[p], msg=f"Production file mutated: {p}")

    def test_import_and_readonly_queries_do_not_mutate_existing_db(self):
        with tempfile.TemporaryDirectory(prefix="flexa_pre_pr22_", ignore_cleanup_errors=True) as pre_dir:
            pre_db = os.path.join(pre_dir, "flexa.db")
            with contextlib.closing(sqlite3.connect(pre_db)) as conn:
                conn.execute(
                    "CREATE TABLE users ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "username TEXT UNIQUE NOT NULL, "
                    "pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL, "
                    "display_name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', "
                    "plan TEXT NOT NULL DEFAULT 'free', plan_expires_at INTEGER NOT NULL DEFAULT 0, "
                    "is_blocked INTEGER NOT NULL DEFAULT 0, last_login_at INTEGER NOT NULL DEFAULT 0, "
                    "created_at INTEGER NOT NULL, oauth_provider TEXT NOT NULL DEFAULT '', "
                    "oauth_id TEXT NOT NULL DEFAULT '', avatar TEXT NOT NULL DEFAULT '')"
                )
                conn.execute(
                    "INSERT INTO users (id, username, pw_salt, pw_hash, created_at, last_login_at) "
                    "VALUES (1, 'legacy_user', 's', 'h', 1760000000, 1761000000)"
                )
                conn.commit()

            snap_before = _snapshot(pre_db)

            # 1. Importing server & growth modules in a fresh Python process must NOT alter the existing DB
            env = dict(os.environ)
            env["FLEXA_DATA_DIR"] = pre_dir
            res = subprocess.run(
                [sys.executable, "-c", "import server, growth.db, growth.metrics, growth.routes; print('IMPORT_OK')"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)
            self.assertIn("IMPORT_OK", res.stdout)
            self.assertEqual(_snapshot(pre_db), snap_before)

            # 2. Read-only Growth queries against legacy DB without growth_audit_log must NOT create/mutate tables
            audit_pre = growth_db.query_audit_log(pre_db, server.db_lock)
            self.assertEqual(audit_pre["status"], "unavailable")
            self.assertEqual(audit_pre["dbHealth"], "missing_table")
            self.assertFalse(audit_pre["appendOnlyEnforced"])
            an_pre = growth_metrics.compute_analytics(pre_db, server.db_lock, now_ts=1764000000)
            self.assertTrue(an_pre["ok"])
            self.assertEqual(an_pre["registrations"]["totalUsers"], 1)
            self.assertEqual(_snapshot(pre_db), snap_before)

            # 3. Explicit init_db() initializes growth_audit_log + triggers while preserving legacy users
            orig_db, orig_sec = server.DB_FILE, server.SECRET_DIR
            try:
                server.SECRET_DIR = pre_dir
                server.DB_FILE = pre_db
                server.init_db()
            finally:
                server.DB_FILE, server.SECRET_DIR = orig_db, orig_sec
                gc.collect()

            with contextlib.closing(sqlite3.connect(pre_db)) as conn:
                tbl = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_audit_log'"
                ).fetchone()
                self.assertIsNotNone(tbl)
                trigs = {
                    r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='growth_audit_log'"
                    ).fetchall()
                }
                self.assertEqual(trigs, {"trg_growth_audit_no_update", "trg_growth_audit_no_delete"})
                legacy = conn.execute("SELECT username FROM users WHERE id = 1").fetchone()
                self.assertEqual(legacy[0], "legacy_user")


if __name__ == "__main__":
    unittest.main()
