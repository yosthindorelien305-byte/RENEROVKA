"""Tests for AI Growth Task Manager CRUD, filters, transitions, auth, CSRF, and audit (PR 4.2)."""

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
            "Origin": "http://127.0.0.1:8080",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def test_tasks_require_admin_auth_and_csrf_protection(self):
        # 401 without admin token & for regular user
        for method, ep in (
            ("GET", "/api/admin/growth/tasks"),
            ("GET", "/api/admin/growth/tasks/1"),
            ("POST", "/api/admin/growth/tasks"),
            ("PATCH", "/api/admin/growth/tasks/1"),
        ):
            c_anon, _ = invoke_http(method, ep, {"title": "Test"})
            self.assertEqual(c_anon, 401)
            c_usr, _ = invoke_http(method, ep, {"title": "Test"}, headers={"Authorization": "Bearer user_tok_tasks"})
            self.assertEqual(c_usr, 401)

        # 403 CSRF checks: foreign Origin, foreign Referer, or plain-text form POST without JSON/XHR
        c_org, b_org = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {"title": "CSRF Probe"},
            headers={**self.admin_hdrs, "Origin": "https://evil.example"},
        )
        self.assertEqual(c_org, 403)
        self.assertIn("csrf", b_org["error"])

        hdrs_ref = dict(self.admin_hdrs)
        del hdrs_ref["Origin"]
        hdrs_ref["Referer"] = "https://evil.example/attack.html"
        c_ref, _ = invoke_http("POST", "/api/admin/growth/tasks", {"title": "CSRF Probe"}, headers=hdrs_ref)
        self.assertEqual(c_ref, 403)

        c_form, _ = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            b'{"title":"Form"}',
            headers={
                "Authorization": self.admin_hdrs["Authorization"],
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self.assertEqual(c_form, 403)

    def test_task_crud_filters_transitions_seo_link_and_audit(self):
        # Run SEO audit to obtain real seoAuditRunId and seoIssueId
        run = seo_audit.run_seo_audit(server.DB_FILE, server.db_lock, site_dir=server.SITE)
        self.assertGreaterEqual(len(run["issues"]), 1)
        first_issue = run["issues"][0]

        # Validation errors
        c_short, _ = invoke_http("POST", "/api/admin/growth/tasks", {"title": "ab"}, headers=self.admin_hdrs)
        self.assertEqual(c_short, 400)
        c_bad_cat, _ = invoke_http("POST", "/api/admin/growth/tasks", {"title": "Valid Title", "category": "Hack"}, headers=self.admin_hdrs)
        self.assertEqual(c_bad_cat, 400)
        c_bad_id, _ = invoke_http("GET", "/api/admin/growth/tasks/1abc", headers=self.admin_hdrs)
        self.assertEqual(c_bad_id, 400)
        c_zero_id, _ = invoke_http("GET", "/api/admin/growth/tasks/0", headers=self.admin_hdrs)
        self.assertEqual(c_zero_id, 400)
        c_sqli, _ = invoke_http("GET", "/api/admin/growth/tasks/1%20OR%201=1", headers=self.admin_hdrs)
        self.assertEqual(c_sqli, 400)
        c_semi, _ = invoke_http("GET", "/api/admin/growth/tasks/1;DROP", headers=self.admin_hdrs)
        self.assertEqual(c_semi, 404)

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

        # Create second task in Content category
        c_cr2, b_cr2 = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {"title": "Publish strength guide", "category": "Content", "priority": "low"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_cr2, 201)
        tid2 = b_cr2["task"]["id"]

        # Filtering by category & priority & status
        c_flt, b_flt = invoke_http("GET", "/api/admin/growth/tasks?category=SEO&priority=high", headers=self.admin_hdrs)
        self.assertEqual(c_flt, 200)
        self.assertEqual([t["id"] for t in b_flt["tasks"]], [tid])

        # Valid status transition open -> in_progress -> pending_approval -> approved -> completed
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

        # Invalid status transition (completed -> approved must be rejected)
        c_inv, b_inv = invoke_http(
            "PATCH",
            f"/api/admin/growth/tasks/{tid}",
            {"status": "approved"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_inv, 400)
        self.assertIn("запрещён", b_inv["error"])

        # Update priority on task 2
        c_p2, b_p2 = invoke_http(
            "PATCH",
            f"/api/admin/growth/tasks/{tid2}",
            {"priority": "critical"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_p2, 200)
        self.assertEqual(b_p2["task"]["priority"], "critical")

        # Detail view includes full change history & linked SEO issue
        c_det, b_det = invoke_http("GET", f"/api/admin/growth/tasks/{tid}", headers=self.admin_hdrs)
        self.assertEqual(c_det, 200)
        self.assertEqual(b_det["seoIssue"]["id"], first_issue["id"])
        self.assertGreaterEqual(len(b_det["history"]), 5)

        # Audit log recorded task.create and task.update
        c_aud, b_aud = invoke_http("GET", "/api/admin/growth/audit?module=tasks&limit=20", headers=self.admin_hdrs)
        self.assertEqual(c_aud, 200)
        actions = [e["action"] for e in b_aud["entries"]]
        self.assertIn("task.create", actions)
        self.assertIn("task.update", actions)


if __name__ == "__main__":
    unittest.main()
