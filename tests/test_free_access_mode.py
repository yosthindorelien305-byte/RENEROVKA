"""Isolated tests for FREE_ACCESS_MODE, payment blocking, pending YooKassa verification,
history preservation, admin access protection, and reversibility to paid mode.

Uses a temporary SQLite database and mocked YooKassa API calls.
Does not touch server_data/flexa.db or any external network service.
"""
import gc
import io
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from email.message import Message
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
import server  # noqa: E402


def invoke_handler(method, path, body=None, headers=None, client_ip="127.0.0.1"):
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    hdrs = Message()
    hdrs["Content-Type"] = "application/json"
    hdrs["Content-Length"] = str(len(raw))
    if headers:
        for k, v in headers.items():
            hdrs[k] = v

    h = server.H.__new__(server.H)
    h.path = path
    h.command = method
    h.headers = hdrs
    h.client_address = (client_ip, 51000)
    h.rfile = io.BytesIO(raw)
    h.wfile = io.BytesIO()
    h.request_version = "HTTP/1.1"
    h._headers_buffer = []

    captured = {"status": None, "body": None}

    def fake_send_j(code, obj):
        captured["status"] = code
        captured["body"] = obj

    h.send_j = fake_send_j
    if method == "GET":
        h.do_GET()
    elif method == "POST":
        h.do_POST()
    else:
        raise ValueError(f"Unsupported method: {method}")
    return captured["status"], captured["body"]


class TestFreeAccessMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.orig_db = server.DB_FILE
        self.orig_yk = server.YOOKASSA_FILE
        self.orig_free = server.FREE_ACCESS_MODE

        server.DB_FILE = os.path.join(self.tmp.name, "test_free.db")
        server.YOOKASSA_FILE = os.path.join(self.tmp.name, "test_yk.json")
        server.FREE_ACCESS_MODE = True
        server.fails.clear()

        server.init_db()
        server.save_yookassa_cfg({
            "shop_id": "999999",
            "secret_key": "test_synthetic_yk_secret",
            "enabled": True,
            "sbp_only": True,
        })

        now = int(time.time())
        self.pw = "TestPass123!"
        salt = "22" * 16
        pwh = server.hash_pw(self.pw, salt)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            cur1 = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES ("free_user", ?, ?, "Free User", "free@example.test", "free", 0, 0, ?, ?)',
                (salt, pwh, now, now),
            )
            self.free_uid = cur1.lastrowid

            cur2 = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES ("other_user", ?, ?, "Other User", "other@example.test", "free", 0, 0, ?, ?)',
                (salt, pwh, now, now),
            )
            self.other_uid = cur2.lastrowid

            # Seed one historical paid payment and one pending payment
            conn.execute(
                'INSERT INTO payments (user_id, plan, days, amount, currency, provider, status, note, payment_id, created_at, updated_at) '
                'VALUES (?, "3m", 90, 690, "RUB", "yookassa", "paid", "Historical", "pay_hist_001", ?, ?)',
                (self.free_uid, now - 86400, now - 86400),
            )
            conn.execute(
                'INSERT INTO payments (user_id, plan, days, amount, currency, provider, status, note, payment_id, created_at, updated_at) '
                'VALUES (?, "1m", 30, 290, "RUB", "yookassa", "pending", "Pending Before Free", "pay_pend_001", ?, ?)',
                (self.free_uid, now - 60, now - 60),
            )
            conn.commit()
        finally:
            conn.close()

        # Log in both users to get valid session tokens
        _, b1 = invoke_handler("POST", "/api/user/login", {"username": "free_user", "password": self.pw})
        self.free_tok = b1["token"]
        _, b2 = invoke_handler("POST", "/api/user/login", {"username": "other_user", "password": self.pw})
        self.other_tok = b2["token"]

        # Create a valid admin session token in memory
        self.admin_tok = "test_admin_tok_12345"
        with server.lock:
            server.tokens[self.admin_tok] = time.time() + 3600

    def tearDown(self):
        with server.lock:
            server.tokens.pop(self.admin_tok, None)
        server.DB_FILE = self.orig_db
        server.YOOKASSA_FILE = self.orig_yk
        server.FREE_ACCESS_MODE = self.orig_free
        server.fails.clear()
        gc.collect()
        try:
            self.tmp.cleanup()
        except PermissionError:
            pass

    def test_1_free_user_gets_pro_without_mutating_db(self):
        """Regular free user receives isPro=True across APIs while DB plan stays 'free'."""
        st_me, b_me = invoke_handler("GET", "/api/user/me", headers={"Authorization": "Bearer " + self.free_tok})
        self.assertEqual(st_me, 200)
        self.assertTrue(b_me["user"]["isPro"])
        self.assertEqual(b_me["user"]["plan"], "pro")
        self.assertTrue(b_me["user"]["freeAccessMode"])

        st_sync, b_sync = invoke_handler("GET", "/api/user/sync", headers={"Authorization": "Bearer " + self.free_tok})
        self.assertEqual(st_sync, 200)
        self.assertTrue(b_sync["user"]["isPro"])

        st_comm, b_comm = invoke_handler("GET", "/api/community/users")
        self.assertEqual(st_comm, 200)
        self.assertTrue(all(u["isPro"] for u in b_comm["users"]))

        # Verify raw DB values were NOT mutated
        conn = sqlite3.connect(server.DB_FILE)
        try:
            row = conn.execute("SELECT plan, plan_expires_at FROM users WHERE id = ?", (self.free_uid,)).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("free", 0))

    def test_2_new_payments_blocked_before_yookassa_and_db(self):
        """POST /api/payment/create returns 403, does not call YooKassa, and inserts no payment row."""
        st_pl, b_pl = invoke_handler("GET", "/api/payment/plans")
        self.assertEqual(st_pl, 200)
        self.assertFalse(b_pl["enabled"])
        self.assertTrue(b_pl["freeAccessMode"])
        self.assertGreaterEqual(len(b_pl["plans"]), 3)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            before_cnt = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        finally:
            conn.close()

        with patch.object(server, "yookassa_create_payment") as mock_create:
            st_cr, b_cr = invoke_handler(
                "POST",
                "/api/payment/create",
                {"planId": "3m"},
                headers={"Authorization": "Bearer " + self.free_tok},
            )
            self.assertEqual(st_cr, 403)
            self.assertTrue(b_cr.get("paymentsDisabled"))
            mock_create.assert_not_called()

        conn = sqlite3.connect(server.DB_FILE)
        try:
            after_cnt = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(before_cnt, after_cnt)

    def test_3_webhook_ignored_in_free_mode_and_rejects_unverified_in_paid_mode(self):
        """In FREE_ACCESS_MODE webhook ignores all events; in paid mode it rejects unknown/unverified events."""
        # 3a. In FREE_ACCESS_MODE=True, webhook ignores everything without touching YooKassa or DB
        with patch.object(server, "yookassa_get_payment") as mock_get:
            st0, b0 = invoke_handler("POST", "/api/payment/yookassa/webhook", {
                "event": "payment.succeeded",
                "object": {"id": "pay_pend_001", "status": "succeeded"},
            })
            self.assertEqual(st0, 200)
            self.assertTrue(b0.get("ignored"))
            self.assertTrue(b0.get("freeAccessMode"))
            mock_get.assert_not_called()

        # 3b. In paid mode (FREE_ACCESS_MODE=False): unknown payment_id is ignored & not inserted
        server.FREE_ACCESS_MODE = False
        with patch.object(server, "yookassa_get_payment") as mock_get:
            st, b = invoke_handler("POST", "/api/payment/yookassa/webhook", {
                "event": "payment.succeeded",
                "object": {
                    "id": "pay_forged_999",
                    "status": "succeeded",
                    "amount": {"value": "1490.00"},
                    "metadata": {"user_id": str(self.free_uid), "days": "3650"},
                },
            })
            self.assertEqual(st, 200)
            self.assertTrue(b.get("ignored"))
            mock_get.assert_not_called()

        # 3c. Existing pending payment, but YooKassa API reports status='pending' -> must stay pending
        with patch.object(server, "yookassa_get_payment", return_value={"id": "pay_pend_001", "status": "pending"}):
            st2, b2 = invoke_handler("POST", "/api/payment/yookassa/webhook", {
                "event": "payment.succeeded",
                "object": {"id": "pay_pend_001", "status": "succeeded"},
            })
            self.assertEqual(st2, 200)
            self.assertEqual(b2.get("status"), "pending")

        conn = sqlite3.connect(server.DB_FILE)
        try:
            p_cnt = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
            p_st = conn.execute('SELECT status FROM payments WHERE payment_id = "pay_pend_001"').fetchone()[0]
            u_plan = conn.execute("SELECT plan FROM users WHERE id = ?", (self.free_uid,)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(p_cnt, 2)
        self.assertEqual(p_st, "pending")
        self.assertEqual(u_plan, "free")

    def test_4_webhook_verifies_existing_pending_payment_idempotently_in_paid_mode(self):
        """In paid mode, verified webhook finalizes existing pending payment once without double-adding days."""
        server.FREE_ACCESS_MODE = False
        with patch.object(server, "yookassa_get_payment", return_value={"id": "pay_pend_001", "status": "succeeded"}):
            st1, b1 = invoke_handler("POST", "/api/payment/yookassa/webhook", {
                "event": "payment.succeeded",
                "object": {"id": "pay_pend_001", "status": "succeeded"},
            })
            self.assertEqual(st1, 200)
            self.assertEqual(b1.get("status"), "paid")

            conn = sqlite3.connect(server.DB_FILE)
            try:
                plan1, exp1 = conn.execute("SELECT plan, plan_expires_at FROM users WHERE id = ?", (self.free_uid,)).fetchone()
                pay_st = conn.execute('SELECT status FROM payments WHERE payment_id = "pay_pend_001"').fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(plan1, "pro")
            self.assertGreater(exp1, int(time.time()))
            self.assertEqual(pay_st, "paid")

            # Second identical webhook must NOT add another 30 days
            st2, _ = invoke_handler("POST", "/api/payment/yookassa/webhook", {
                "event": "payment.succeeded",
                "object": {"id": "pay_pend_001", "status": "succeeded"},
            })
            self.assertEqual(st2, 200)
            conn = sqlite3.connect(server.DB_FILE)
            try:
                _, exp2 = conn.execute("SELECT plan, plan_expires_at FROM users WHERE id = ?", (self.free_uid,)).fetchone()
            finally:
                conn.close()
            self.assertEqual(exp1, exp2)

    def test_5_payment_check_works_for_owner_and_blocks_idor(self):
        """GET /api/payment/check requires auth, blocks other users (403), and verifies owner's pending payment."""
        st_unauth, _ = invoke_handler("GET", "/api/payment/check?paymentId=pay_pend_001")
        self.assertEqual(st_unauth, 401)

        st_other, _ = invoke_handler(
            "GET",
            "/api/payment/check?paymentId=pay_pend_001",
            headers={"Authorization": "Bearer " + self.other_tok},
        )
        self.assertEqual(st_other, 403)

        with patch.object(server, "yookassa_get_payment", return_value={"id": "pay_pend_001", "status": "succeeded"}):
            st_ok, b_ok = invoke_handler(
                "GET",
                "/api/payment/check?paymentId=pay_pend_001",
                headers={"Authorization": "Bearer " + self.free_tok},
            )
            self.assertEqual(st_ok, 200)
            self.assertEqual(b_ok["status"], "paid")
            self.assertTrue(b_ok["isPro"])

    def test_6_history_preserved_and_admin_protected(self):
        """Regular user in free mode cannot access admin APIs; admin still sees payment history & real DB plans."""
        user_hdr = {"Authorization": "Bearer " + self.free_tok}
        for method, path in (
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/yookassa"),
            ("GET", "/api/admin/telegram"),
            ("POST", "/api/admin/user/plan"),
            ("POST", "/api/save?file=config"),
            ("POST", "/api/password"),
        ):
            st, _ = invoke_handler(method, path, {} if method == "POST" else None, headers=user_hdr)
            self.assertIn(st, (401, 404), f"Regular user must not access {method} {path}, got {st}")

        admin_hdr = {"Authorization": "Bearer " + self.admin_tok}
        st_adm, b_adm = invoke_handler("GET", "/api/admin/users", headers=admin_hdr)
        self.assertEqual(st_adm, 200)
        self.assertEqual(len(b_adm["payments"]), 2)
        # Admin sees real DB plan ('free'), not overridden by FREE_ACCESS_MODE
        u_map = {u["username"]: u for u in b_adm["users"]}
        self.assertEqual(u_map["free_user"]["plan"], "free")
        self.assertFalse(u_map["free_user"]["isPro"])

    def test_7_reversible_back_to_paid_model(self):
        """Switching FREE_ACCESS_MODE = False immediately restores paid model without DB changes."""
        server.FREE_ACCESS_MODE = False

        st_me, b_me = invoke_handler("GET", "/api/user/me", headers={"Authorization": "Bearer " + self.free_tok})
        self.assertEqual(st_me, 200)
        self.assertFalse(b_me["user"]["isPro"])
        self.assertEqual(b_me["user"]["plan"], "free")
        self.assertFalse(b_me["user"]["freeAccessMode"])

        st_pl, b_pl = invoke_handler("GET", "/api/payment/plans")
        self.assertEqual(st_pl, 200)
        self.assertTrue(b_pl["enabled"])
        self.assertFalse(b_pl["freeAccessMode"])

        # In paid mode, POST /api/payment/create calls YooKassa and creates a pending payment
        fake_yk_resp = {
            "id": "pay_new_paid_mode_001",
            "confirmation": {"confirmation_url": "https://yookassa.test/confirm/001"},
        }
        with patch.object(server, "yookassa_create_payment", return_value=fake_yk_resp) as mock_create:
            st_cr, b_cr = invoke_handler(
                "POST",
                "/api/payment/create",
                {"planId": "3m"},
                headers={"Authorization": "Bearer " + self.free_tok},
            )
            self.assertEqual(st_cr, 200)
            self.assertTrue(b_cr.get("ok"))
            self.assertEqual(b_cr.get("paymentId"), "pay_new_paid_mode_001")
            mock_create.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
