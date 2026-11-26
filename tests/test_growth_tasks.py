"""Tests for AI Growth Task Manager CRUD, filters, transitions, CSRF, targetUrl, and audit (PR 4.2)."""

import contextlib
import io
import json
import sqlite3
import time
import unittest
from email.message import Message

import server
from growth import seo_audit
from tests.test_isolation import IsolatedServerTestCase


def invoke_http(method, path, body=None, headers=None, client_ip="127.0.0.1"):
    """Invoke server.H handler in-process without opening network sockets."""
    raw = (
        json.dumps(body).encode("utf-8")
        if body is not None and not isinstance(body, (bytes, bytearray))
        else (body or b"")
    )
    hdrs = Message()
    hdrs["Host"] = "127.0.0.1:8080"
    if isinstance(body, dict):
        hdrs["Content-Type"] = "application/json"
    hdrs["Content-Length"] = str(len(raw))
    if headers:
        for k, v in headers.items():
            if k in hdrs:
                del hdrs[k]
            hdrs[k] = v

    h = server.H.__new__(server.H)
    h.path = path
    h.command = method
    h.headers = hdrs
    h.client_address = (client_ip, 50002)
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


class TestGrowthTasks(IsolatedServerTestCase):
    def setUp(self):
        super().setUp()
        self.admin_pw = "TasksAdm_2026!"
        server.set_pw(self.admin_pw)
        now = int(time.time())
        with contextlib.closing(sqlite3.connect(server.DB_FILE)) as conn:
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (7, 'task_reg_user', 's', 'h', 'Regular', 'r@x.com', 'free', 0, 0, ?, ?)",
                (now, now),
            )
            conn.execute(
                "INSERT INTO user_sessions (token, user_id, expires_at) VALUES ('user_tok_tasks', 7, ?)",
                (now + 86400,),
            )
            conn.commit()
        code, body = invoke_http("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(code, 200)
        self.admin_hdrs = {
            "Authorization": f"Bearer {body['token']}",
            "Host": "127.0.0.1:8080",
            "Origin": "http://127.0.0.1:8080",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def test_tasks_require_admin_auth_and_strict_csrf_on_all_mutating_routes(self):
        # Existing admin login remains intact even without Origin/XHR
        c_login, b_login = invoke_http("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(c_login, 200)
        self.assertIn("token", b_login)

        # 401 without admin token & for regular user
        for method, ep in (
            ("GET", "/api/admin/growth/tasks"),
            ("GET", "/api/admin/growth/tasks/1"),
            ("POST", "/api/admin/growth/tasks"),
            ("PATCH", "/api/admin/growth/tasks/1"),
            ("POST", "/api/admin/growth/seo-audit/run"),
        ):
            self.assertEqual(invoke_http(method, ep, {"title": "Test"})[0], 401)
            self.assertEqual(
                invoke_http(method, ep, {"title": "Test"}, headers={"Authorization": "Bearer user_tok_tasks"})[0],
                401,
            )

        tok = self.admin_hdrs["Authorization"]
        # Create one task legitimately so PATCH /tasks/1 tests reach CSRF cleanly
        c_ok, _ = invoke_http("POST", "/api/admin/growth/tasks", {"title": "CSRF Seed Task"}, headers=self.admin_hdrs)
        self.assertEqual(c_ok, 201)

        mutating_targets = (
            ("POST", "/api/admin/growth/tasks", {"title": "CSRF Probe"}),
            ("PATCH", "/api/admin/growth/tasks/1", {"priority": "high"}),
            ("POST", "/api/admin/growth/seo-audit/run", {}),
        )
        for method, ep, payload in mutating_targets:
            # 1. Missing both Origin & Referer -> 403
            c_no_org, b_no_org = invoke_http(
                method,
                ep,
                payload,
                headers={"Authorization": tok, "Host": "127.0.0.1:8080", "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"},
            )
            self.assertEqual(c_no_org, 403, msg=f"Expected 403 missing Origin/Referer for {method} {ep}")
            self.assertEqual(b_no_org["error"], "csrf_missing_origin_or_referer")

            # 2. Content-Type: application/json alone without X-Requested-With / X-Rizza-Admin -> 403
            c_json_only, b_json_only = invoke_http(
                method,
                ep,
                payload,
                headers={"Authorization": tok, "Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080", "Content-Type": "application/json"},
            )
            self.assertEqual(c_json_only, 403, msg=f"Content-Type alone must not pass CSRF on {method} {ep}")
            self.assertEqual(b_json_only["error"], "csrf_trusted_header_required")

            # 3. Origin: null -> 403
            self.assertEqual(invoke_http(method, ep, payload, headers={**self.admin_hdrs, "Origin": "null"})[0], 403)

            # 4. Cross-origin Origin -> 403
            self.assertEqual(invoke_http(method, ep, payload, headers={**self.admin_hdrs, "Origin": "https://evil.example"})[0], 403)

            # 5. Same-origin Origin + cross-origin Referer -> 403
            self.assertEqual(invoke_http(method, ep, payload, headers={**self.admin_hdrs, "Referer": "https://evil.example/pwn.html"})[0], 403)

            # 6. Form Content-Type -> 403 even with XHR header
            self.assertEqual(
                invoke_http(method, ep, b"{}", headers={**self.admin_hdrs, "Content-Type": "application/x-www-form-urlencoded"})[0],
                403,
            )

            # 7. Default port normalization (Nginx Host: rizzafit.ru + Origin: https://rizzafit.ru:443 -> OK; :8443 -> 403)
            c_norm, _ = invoke_http(
                method,
                ep,
                payload,
                headers={**self.admin_hdrs, "Host": "rizzafit.ru", "Origin": "https://rizzafit.ru:443"},
            )
            self.assertIn(c_norm, (200, 201), msg=f"Default HTTPS port normalization failed on {method} {ep}")
            c_bad_port, _ = invoke_http(
                method,
                ep,
                payload,
                headers={**self.admin_hdrs, "Host": "rizzafit.ru", "Origin": "https://rizzafit.ru:8443"},
            )
            self.assertEqual(c_bad_port, 403)

    def test_target_url_strict_validation_and_internal_external_separation(self):
        bad_urls = (
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "file:///etc/passwd",
            "//evil.example/phish",
            "/../secret",
            "/%2e%2e/secret",
            "/fitify\\..\\secret",
            "/line\nbreak",
            "/null\x00byte",
            "https://user@evil.example/test",
            "/server_data/ai.json",
            "relative-without-leading-slash",
        )
        for bad in bad_urls:
            c_bad, _ = invoke_http(
                "POST",
                "/api/admin/growth/tasks",
                {"title": "Bad URL test", "category": "SEO", "targetUrl": bad},
                headers=self.admin_hdrs,
            )
            self.assertEqual(c_bad, 400, msg=f"Dangerous targetUrl accepted: {bad!r}")

        # Internal path -> targetUrlType = 'internal'
        c_int, b_int = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {"title": "Internal URL", "category": "SEO", "targetUrl": "/fitify/muscles.html?view=1#map"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_int, 201)
        self.assertEqual(b_int["task"]["targetUrlType"], "internal")
        self.assertFalse(b_int["task"]["externalNavigationDisabled"])

        # External URL -> targetUrlType = 'external', externalNavigationDisabled = True
        c_ext, b_ext = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {"title": "External URL", "category": "SEO", "targetUrl": "https://example.org/seo-checklist"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_ext, 201)
        self.assertEqual(b_ext["task"]["targetUrlType"], "external")
        self.assertTrue(b_ext["task"]["externalNavigationDisabled"])

    def test_task_crud_filters_transitions_seo_link_and_audit(self):
        run = seo_audit.run_seo_audit(server.DB_FILE, server.db_lock, site_dir=server.SITE)
        self.assertGreaterEqual(len(run["issues"]), 1)
        first_issue = run["issues"][0]

        self.assertEqual(invoke_http("POST", "/api/admin/growth/tasks", {"title": "ab"}, headers=self.admin_hdrs)[0], 400)
        self.assertEqual(invoke_http("POST", "/api/admin/growth/tasks", {"title": "Valid Title", "category": "Hack"}, headers=self.admin_hdrs)[0], 400)
        self.assertEqual(invoke_http("GET", "/api/admin/growth/tasks/1abc", headers=self.admin_hdrs)[0], 400)
        self.assertEqual(invoke_http("GET", "/api/admin/growth/tasks/0", headers=self.admin_hdrs)[0], 400)
        self.assertEqual(invoke_http("GET", "/api/admin/growth/tasks/1%20OR%201=1", headers=self.admin_hdrs)[0], 400)
        self.assertEqual(invoke_http("GET", "/api/admin/growth/tasks/1;DROP", headers=self.admin_hdrs)[0], 404)

        # Create task linked to SEO issue
        c_cr, b_cr = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {
                "title": "Fix SEO issue",
                "description": "Add missing tag cleanly",
                "category": "SEO",
                "priority": "high",
                "seoIssueId": first_issue["id"],
            },
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_cr, 201)
        tid = b_cr["task"]["id"]
        self.assertEqual(b_cr["task"]["seoAuditRunId"], run["runId"])
        self.assertEqual(b_cr["task"]["targetUrl"], first_issue["pageUrl"])
        self.assertEqual(b_cr["task"]["targetUrlType"], "internal")

        # Create second task in Content category
        c_cr2, b_cr2 = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {"title": "Publish strength guide", "category": "Content", "priority": "low"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_cr2, 201)
        tid2 = b_cr2["task"]["id"]

        # Filtering by category & priority
        c_flt, b_flt = invoke_http("GET", "/api/admin/growth/tasks?category=SEO&priority=high", headers=self.admin_hdrs)
        self.assertEqual(c_flt, 200)
        self.assertEqual([t["id"] for t in b_flt["tasks"]], [tid])

        # Valid status transitions
        for next_st in ("in_progress", "pending_approval", "approved", "completed"):
            c_up, b_up = invoke_http(
                "PATCH",
                f"/api/admin/growth/tasks/{tid}",
                {"status": next_st, "note": f"move to {next_st}"},
                headers=self.admin_hdrs,
            )
            self.assertEqual(c_up, 200)
            self.assertEqual(b_up["task"]["status"], next_st)
        self.assertIsNotNone(b_up["task"]["completedAt"])

        # Invalid transition rejected
        c_inv, b_inv = invoke_http("PATCH", f"/api/admin/growth/tasks/{tid}", {"status": "approved"}, headers=self.admin_hdrs)
        self.assertEqual(c_inv, 400)
        self.assertIn("запрещён", b_inv["error"])

        # Priority update on task 2
        c_p2, b_p2 = invoke_http("PATCH", f"/api/admin/growth/tasks/{tid2}", {"priority": "critical"}, headers=self.admin_hdrs)
        self.assertEqual(c_p2, 200)
        self.assertEqual(b_p2["task"]["priority"], "critical")

        # Detail & Audit log verification
        c_det, b_det = invoke_http("GET", f"/api/admin/growth/tasks/{tid}", headers=self.admin_hdrs)
        self.assertEqual(c_det, 200)
        self.assertEqual(b_det["seoIssue"]["id"], first_issue["id"])
        self.assertGreaterEqual(len(b_det["history"]), 5)

        c_aud, b_aud = invoke_http("GET", "/api/admin/growth/audit?module=tasks&limit=20", headers=self.admin_hdrs)
        self.assertEqual(c_aud, 200)
        actions = [e["action"] for e in b_aud["entries"]]
        self.assertIn("task.create", actions)
        self.assertIn("task.update", actions)


if __name__ == "__main__":
    unittest.main()
