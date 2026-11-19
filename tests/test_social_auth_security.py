"""Isolated in-process security tests for social login and Telegram auth.
Uses a temporary SQLite database and synthetic test-only bot token.
Does not touch server_data/flexa.db, open network sockets, or contact external services.
"""
import gc
import hashlib
import hmac
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from email.message import Message
from urllib.parse import urlencode

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
import server  # noqa: E402

SYNTHETIC_BOT_TOKEN = "000000000:TEST_SYNTHETIC_LOCAL_ONLY_TOKEN"


def make_tg_init_data(user_dict, bot_token=SYNTHETIC_BOT_TOKEN, auth_date=None, bad_hash=False):
    params = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user_dict, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(secret, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    if bad_hash:
        sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    params["hash"] = sig
    return urlencode(params)


def invoke_handler(method, path, body=None, headers=None, client_ip="127.0.0.1"):
    """Invoke server.H.do_GET / do_POST directly in-process without opening sockets."""
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
    h.client_address = (client_ip, 50000)
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


class TestSocialAuthSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.orig_db = server.DB_FILE
        cls.orig_tg = server.TELEGRAM_FILE
        cls.orig_admin = server.ADMIN_FILE

        server.DB_FILE = os.path.join(cls.tmp.name, "test_flexa.db")
        server.TELEGRAM_FILE = os.path.join(cls.tmp.name, "test_telegram.json")
        server.ADMIN_FILE = os.path.join(cls.tmp.name, "test_admin.json")

        server.init_db()
        server.save_telegram_cfg({
            "bot_token": SYNTHETIC_BOT_TOKEN,
            "bot_username": "RizzaFitTestBot",
            "enabled": True,
        })

        # Seed existing password user + existing progress state
        cls.victim_salt = "11" * 16
        cls.victim_pw = "StrongTestPass123!"
        cls.victim_hash = server.hash_pw(cls.victim_pw, cls.victim_salt)
        cls.victim_state = json.dumps({"hist": "[{\"id\":1,\"ts\":1700000000}]"})
        now = int(time.time())
        conn = sqlite3.connect(server.DB_FILE)
        try:
            cur = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, '
                'oauth_provider, oauth_id, avatar, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES ("existing_user", ?, ?, "Existing Athlete", "existing@example.test", "", "", "", "pro", 0, 0, ?, ?)',
                (cls.victim_salt, cls.victim_hash, now, now),
            )
            cls.victim_id = cur.lastrowid
            conn.execute(
                'INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?)',
                (cls.victim_id, cls.victim_state, now),
            )
            # Seed a blocked Telegram user
            conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, '
                'oauth_provider, oauth_id, avatar, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES ("blocked_tg", "", "", "Blocked User", "", "telegram", "999000999", "", "free", 0, 1, ?, ?)',
                (now, now),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def tearDownClass(cls):
        server.DB_FILE = cls.orig_db
        server.TELEGRAM_FILE = cls.orig_tg
        server.ADMIN_FILE = cls.orig_admin
        server.fails.clear()
        with server.tg_auth_lock:
            server.tg_pending_auth.clear()
            server.tg_used_init_hashes.clear()
        gc.collect()
        try:
            cls.tmp.cleanup()
        except PermissionError:
            pass

    def setUp(self):
        server.fails.clear()

    def test_1_forged_email_cannot_login_to_existing_account(self):
        """Forged email via google/vk/yandex/telegram must not grant access to existing_user."""
        for prov in ("google", "vk", "yandex"):
            status, body = invoke_handler("POST", "/api/user/social-login", {
                "provider": prov,
                "socialId": f"forged_{prov}_123",
                "email": "existing@example.test",
                "username": "attacker",
            })
            self.assertEqual(status, 501, f"Expected 501 for {prov}, got {status}: {body}")
            self.assertNotIn("token", body)

        # Even with valid Telegram initData, supplying victim's email in body must NOT link to victim
        init_data = make_tg_init_data({"id": 555111, "username": "tg_other", "first_name": "Other"})
        status, body = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": init_data,
            "email": "existing@example.test",
        })
        self.assertEqual(status, 200)
        self.assertNotEqual(body["user"]["id"], self.victim_id)
        self.assertEqual(body["user"]["email"], "")

    def test_2_forged_social_id_rejected(self):
        """Raw socialId without verified initData must be rejected without creating a session."""
        conn = sqlite3.connect(server.DB_FILE)
        try:
            before_sessions = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        finally:
            conn.close()

        status, body = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "socialId": "123456789",
            "username": "spoofed_tg",
            "displayName": "Spoofed",
        })
        self.assertEqual(status, 401)
        self.assertNotIn("token", body)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            after_sessions = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(before_sessions, after_sessions)

    def test_3_invalid_and_expired_telegram_signature_rejected(self):
        """Tampered hash or expired auth_date in Telegram initData must return 401."""
        bad_init = make_tg_init_data({"id": 777001, "username": "bad_sig"}, bad_hash=True)
        status, body = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": bad_init,
        })
        self.assertEqual(status, 401)
        self.assertNotIn("token", body)

        expired_init = make_tg_init_data(
            {"id": 777001, "username": "expired_sig"},
            auth_date=int(time.time()) - 600,
        )
        status2, body2 = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": expired_init,
        })
        self.assertEqual(status2, 401)
        self.assertNotIn("token", body2)

    def test_4_valid_telegram_webapp_signature_accepted(self):
        """Valid signed Telegram WebApp initData creates/authenticates user and returns working session."""
        valid_init = make_tg_init_data({
            "id": 888001,
            "username": "valid_tg_user",
            "first_name": "Ivan",
            "last_name": "Petrov",
        })
        status, body = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": valid_init,
        })
        self.assertEqual(status, 200, f"Unexpected response: {body}")
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("token"))
        self.assertEqual(body["user"]["username"], "valid_tg_user")
        self.assertEqual(body["user"]["displayName"], "Ivan Petrov")

        # Verify session token actually works on /api/user/me
        me_status, me_body = invoke_handler(
            "GET", "/api/user/me", headers={"Authorization": "Bearer " + body["token"]}
        )
        self.assertEqual(me_status, 200)
        self.assertEqual(me_body["user"]["username"], "valid_tg_user")

    def test_5_telegram_bot_deeplink_one_time_token_and_blocked_check(self):
        """Telegram Bot /start -> /poll works without admin auth, token is single-use, blocked user rejected."""
        # 5a. Unauthenticated client can call /api/auth/telegram/start
        st_code, st_body = invoke_handler("POST", "/api/auth/telegram/start", {})
        self.assertEqual(st_code, 200, f"Expected 200 on /start, got {st_code}: {st_body}")
        self.assertTrue(st_body.get("configured"))
        auth_token = st_body["token"]
        self.assertIn(f"start=auth_{auth_token}", st_body["url"])

        # Before confirmation: poll returns confirmed=False
        p0_code, p0_body = invoke_handler("GET", f"/api/auth/telegram/poll?token={auth_token}")
        self.assertEqual(p0_code, 200)
        self.assertFalse(p0_body.get("confirmed"))

        # Simulate bot receiving /start auth_<token> (bot_token=None avoids any network call)
        ok = server.process_telegram_auth_code(
            auth_token,
            {"id": 888002, "username": "bot_tester", "first_name": "Bot", "last_name": "<Tester>"},
            chat_id=888002,
            bot_token=None,
        )
        self.assertTrue(ok)

        # First poll returns confirmed=True and sessionToken
        p1_code, p1_body = invoke_handler("GET", f"/api/auth/telegram/poll?token={auth_token}")
        self.assertEqual(p1_code, 200)
        self.assertTrue(p1_body.get("confirmed"))
        self.assertTrue(p1_body.get("sessionToken"))
        self.assertEqual(p1_body["user"]["username"], "bot_tester")

        # Second poll with the SAME token must NOT return a session again
        p2_code, p2_body = invoke_handler("GET", f"/api/auth/telegram/poll?token={auth_token}")
        self.assertEqual(p2_code, 200)
        self.assertFalse(p2_body.get("confirmed"))
        self.assertNotIn("sessionToken", p2_body)

        # 5b. Blocked Telegram user must be rejected
        st2_code, st2_body = invoke_handler("POST", "/api/auth/telegram/start", {})
        self.assertEqual(st2_code, 200)
        blk_tok = st2_body["token"]
        ok_blk = server.process_telegram_auth_code(
            blk_tok,
            {"id": 999000999, "username": "blocked_tg", "first_name": "Blocked"},
            chat_id=999000999,
            bot_token=None,
        )
        self.assertFalse(ok_blk)
        pb_code, pb_body = invoke_handler("GET", f"/api/auth/telegram/poll?token={blk_tok}")
        self.assertEqual(pb_code, 403)
        self.assertNotIn("sessionToken", pb_body)

    def test_6_existing_user_can_still_login_with_password(self):
        """Existing user logs in normally by username+password and email+password."""
        st1, b1 = invoke_handler("POST", "/api/user/login", {
            "username": "existing_user",
            "password": self.victim_pw,
        })
        self.assertEqual(st1, 200)
        self.assertTrue(b1.get("token"))
        self.assertEqual(b1["user"]["id"], self.victim_id)
        self.assertTrue(b1["user"]["isPro"])

        st2, b2 = invoke_handler("POST", "/api/user/login", {
            "email": "existing@example.test",
            "password": self.victim_pw,
        })
        self.assertEqual(st2, 200)
        self.assertEqual(b2["user"]["id"], self.victim_id)

    def test_7_existing_user_data_unchanged(self):
        """Existing user's password hash, oauth binding, email, plan, and state remain untouched."""
        conn = sqlite3.connect(server.DB_FILE)
        try:
            row = conn.execute(
                "SELECT pw_salt, pw_hash, email, oauth_provider, oauth_id, plan FROM users WHERE id = ?",
                (self.victim_id,),
            ).fetchone()
            st_row = conn.execute(
                "SELECT data_json FROM user_state WHERE user_id = ?",
                (self.victim_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, (self.victim_salt, self.victim_hash, "existing@example.test", "", "", "pro"))
        self.assertEqual(st_row[0], self.victim_state)

    def test_8_unknown_and_expired_auth_code_create_nothing(self):
        """Unknown or expired auth_code must NOT create a user or session in DB."""
        def db_counts():
            conn = sqlite3.connect(server.DB_FILE)
            try:
                u_cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                s_cnt = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
                return u_cnt, s_cnt
            finally:
                conn.close()

        before = db_counts()
        ok_unknown = server.process_telegram_auth_code(
            "nonexistent_code_xyz",
            {"id": 700001, "username": "ghost_user", "first_name": "Ghost"},
            chat_id=700001,
            bot_token=None,
        )
        self.assertFalse(ok_unknown)
        self.assertEqual(db_counts(), before)

        # Expired pending auth_code (> 900s)
        expired_tok = "expired_auth_tok_1"
        with server.tg_auth_lock:
            server.tg_pending_auth[expired_tok] = {
                "created_at": time.time() - (server.TG_AUTH_TTL + 5),
                "status": "pending",
            }
        ok_expired = server.process_telegram_auth_code(
            expired_tok,
            {"id": 700002, "username": "expired_user", "first_name": "Expired"},
            chat_id=700002,
            bot_token=None,
        )
        self.assertFalse(ok_expired)
        self.assertEqual(db_counts(), before)
        with server.tg_auth_lock:
            self.assertNotIn(expired_tok, server.tg_pending_auth)

    def test_9_reused_auth_code_does_not_create_second_session(self):
        """Calling process_telegram_auth_code twice with the same auth_code must not create a 2nd session."""
        st_code, st_body = invoke_handler("POST", "/api/auth/telegram/start", {})
        self.assertEqual(st_code, 200)
        tok = st_body["token"]

        ok1 = server.process_telegram_auth_code(
            tok,
            {"id": 700003, "username": "once_user", "first_name": "Once"},
            chat_id=700003,
            bot_token=None,
        )
        self.assertTrue(ok1)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            sess_after_first = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        finally:
            conn.close()

        ok2 = server.process_telegram_auth_code(
            tok,
            {"id": 700003, "username": "once_user", "first_name": "Once"},
            chat_id=700003,
            bot_token=None,
        )
        self.assertFalse(ok2)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            sess_after_second = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(sess_after_first, sess_after_second)

        # Clean up token via poll
        invoke_handler("GET", f"/api/auth/telegram/poll?token={tok}")

    def test_10_expired_poll_token_removed_and_returns_unconfirmed(self):
        """Expired token in /api/auth/telegram/poll must be deleted and never return sessionToken."""
        exp_tok = "expired_poll_tok_1"
        with server.tg_auth_lock:
            server.tg_pending_auth[exp_tok] = {
                "created_at": time.time() - (server.TG_AUTH_TTL + 10),
                "status": "confirmed",
                "sessionToken": "should_never_be_returned",
                "user": {"id": 999, "username": "stale"},
                "state": {},
                "updatedAt": 0,
            }
        code, body = invoke_handler("GET", f"/api/auth/telegram/poll?token={exp_tok}")
        self.assertEqual(code, 200)
        self.assertFalse(body.get("confirmed"))
        self.assertNotIn("sessionToken", body)
        with server.tg_auth_lock:
            self.assertNotIn(exp_tok, server.tg_pending_auth)

    def test_11_replayed_telegram_init_data_rejected(self):
        """Valid Telegram WebApp initData works on first login and is rejected on replay."""
        fresh_init = make_tg_init_data({
            "id": 700004,
            "username": "replay_check_user",
            "first_name": "Replay",
        })
        st1, b1 = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": fresh_init,
        })
        self.assertEqual(st1, 200, f"First login must succeed, got {st1}: {b1}")
        self.assertTrue(b1.get("token"))

        conn = sqlite3.connect(server.DB_FILE)
        try:
            sess_after_first = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        finally:
            conn.close()

        # Replaying the exact same initData must be rejected with 401 and create no new session
        st2, b2 = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": fresh_init,
        })
        self.assertEqual(st2, 401)
        self.assertNotIn("token", b2)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            sess_after_replay = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(sess_after_first, sess_after_replay)

    def test_12_blocked_webapp_user_and_concurrent_poll_single_winner(self):
        """Blocked Telegram WebApp user gets 403; concurrent /poll requests yield sessionToken to exactly one."""
        # 12a. Blocked user via Telegram WebApp initData
        blocked_init = make_tg_init_data({
            "id": 999000999,
            "username": "blocked_tg",
            "first_name": "Blocked",
        })
        blk_status, blk_body = invoke_handler("POST", "/api/user/social-login", {
            "provider": "telegram",
            "initData": blocked_init,
        })
        self.assertEqual(blk_status, 403)
        self.assertNotIn("token", blk_body)

        # 12b. Concurrent /api/auth/telegram/poll from multiple threads
        st_code, st_body = invoke_handler("POST", "/api/auth/telegram/start", {})
        self.assertEqual(st_code, 200)
        tok = st_body["token"]
        ok = server.process_telegram_auth_code(
            tok,
            {"id": 700005, "username": "race_user", "first_name": "Race"},
            chat_id=700005,
            bot_token=None,
        )
        self.assertTrue(ok)

        n_threads = 4
        barrier = threading.Barrier(n_threads)
        results = []
        res_lock = threading.Lock()

        def worker():
            barrier.wait()
            c, b = invoke_handler("GET", f"/api/auth/telegram/poll?token={tok}")
            with res_lock:
                results.append((c, b))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), n_threads)
        winners = [b for c, b in results if c == 200 and b.get("confirmed") and b.get("sessionToken")]
        losers = [b for c, b in results if c == 200 and not b.get("confirmed") and "sessionToken" not in b]
        self.assertEqual(len(winners), 1, f"Expected exactly 1 winner, got {len(winners)}")
        self.assertEqual(len(losers), n_threads - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
