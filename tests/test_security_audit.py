"""Security audit regression test suite for RENEROVKA (Flexa).
Tests all 13 core security aspects in an isolated temporary SQLite database and environment.
Does not touch server_data/flexa.db, production configuration, or network sockets.
"""
import io
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from email.message import Message

import server


def invoke_handler(method, path, body=None, headers=None, client_ip="127.0.0.1"):
    """Invoke server.H handler in-process without network sockets."""
    raw = json.dumps(body).encode("utf-8") if body is not None and not isinstance(body, (bytes, bytearray)) else (body or b"")
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
    h.client_address = (client_ip, 50000)
    h.rfile = io.BytesIO(raw)
    h.wfile = io.BytesIO()
    h.request_version = "HTTP/1.1"
    h._headers_buffer = []

    captured = {"status": None, "body": None, "headers": {}}

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


class BaseSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="flexa_sec_test_")
        self.orig_db_file = server.DB_FILE
        self.orig_secret_dir = server.SECRET_DIR
        self.orig_admin_file = server.ADMIN_FILE
        self.orig_pass_txt = server.PASS_TXT
        self.orig_uploads = server.UPLOADS
        self.orig_free_mode = server.FREE_ACCESS_MODE

        server.SECRET_DIR = os.path.join(self.tmp_dir, "server_data")
        os.makedirs(server.SECRET_DIR, exist_ok=True)
        server.DB_FILE = os.path.join(server.SECRET_DIR, "flexa.db")
        server.ADMIN_FILE = os.path.join(server.SECRET_DIR, "admin.json")
        server.PASS_TXT = os.path.join(self.tmp_dir, "ADMIN_PASSWORD.txt")
        server.UPLOADS = os.path.join(self.tmp_dir, "uploads")
        os.makedirs(server.UPLOADS, exist_ok=True)

        server.tokens.clear()
        server.fails.clear()

        # Initialize admin password
        self.admin_pw = "SecTestPass_123!"
        server.set_pw(self.admin_pw)
        server.init_db()

        # Create test users
        now = int(time.time())
        salt1 = "11111111111111111111111111111111"
        hash1 = server.hash_pw("Password_1", salt1)
        salt2 = "22222222222222222222222222222222"
        hash2 = server.hash_pw("Password_2", salt2)

        with server.db_lock, sqlite3.connect(server.DB_FILE) as conn:
            conn.execute(
                'INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES (1, "alice", ?, ?, "Alice Walker", "alice@example.com", "free", 0, 0, ?, ?)',
                (salt1, hash1, now, now)
            )
            conn.execute(
                'INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES (2, "bob", ?, ?, "Bob Builder", "bob@example.com", "free", 0, 0, ?, ?)',
                (salt2, hash2, now, now)
            )
            conn.execute(
                'INSERT INTO user_sessions (token, user_id, expires_at) VALUES ("tok_alice_1", 1, ?)',
                (now + 86400,)
            )
            conn.execute(
                'INSERT INTO user_sessions (token, user_id, expires_at) VALUES ("tok_alice_2", 1, ?)',
                (now + 86400,)
            )
            conn.execute(
                'INSERT INTO user_sessions (token, user_id, expires_at) VALUES ("tok_bob", 2, ?)',
                (now + 86400,)
            )
            conn.commit()

    def tearDown(self):
        server.DB_FILE = self.orig_db_file
        server.SECRET_DIR = self.orig_secret_dir
        server.ADMIN_FILE = self.orig_admin_file
        server.PASS_TXT = self.orig_pass_txt
        server.UPLOADS = self.orig_uploads
        server.FREE_ACCESS_MODE = self.orig_free_mode
        server.tokens.clear()
        server.fails.clear()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class TestAdminAuthenticationAndRoutes(BaseSecurityTestCase):
    def test_1_all_admin_routes_reject_unauthenticated_with_401(self):
        """Every admin route must reject guests, bad tokens, and expired tokens with 401."""
        admin_routes = [
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/yookassa"),
            ("GET", "/api/admin/telegram"),
            ("GET", "/api/ai/settings"),
            ("GET", "/api/uploads"),
            ("POST", "/api/admin/user/plan", {"userId": 1, "plan": "pro"}),
            ("POST", "/api/admin/user/block", {"userId": 1, "blocked": True}),
            ("POST", "/api/admin/user/reset-code", {"userId": 1}),
            ("POST", "/api/admin/yookassa", {"shopId": "123"}),
            ("POST", "/api/admin/yookassa/test", {"shopId": "123", "secretKey": "sec"}),
            ("POST", "/api/admin/telegram", {"botUsername": "test"}),
            ("POST", "/api/admin/telegram/test", {}),
            ("POST", "/api/ai/settings", {"enabled": True}),
            ("POST", "/api/save?file=config", {"brand": "Flexa"}),
            ("POST", "/api/password", {"password": "NewAdminPassword123"}),
        ]

        # 1. No token at all -> 401
        for method, path, *rest in admin_routes:
            body = rest[0] if rest else None
            st, b = invoke_handler(method, path, body=body)
            self.assertEqual(st, 401, f"Route {method} {path} without token must return 401, got {st} ({b})")

        # 2. Invalid / forged token -> 401
        bad_hdr = {"Authorization": "Bearer forged_fake_token_12345"}
        for method, path, *rest in admin_routes:
            body = rest[0] if rest else None
            st, b = invoke_handler(method, path, body=body, headers=bad_hdr)
            self.assertEqual(st, 401, f"Route {method} {path} with forged token must return 401, got {st} ({b})")

        # 3. Regular user token -> 401
        user_hdr = {"Authorization": "Bearer tok_alice_1"}
        for method, path, *rest in admin_routes:
            body = rest[0] if rest else None
            st, b = invoke_handler(method, path, body=body, headers=user_hdr)
            self.assertEqual(st, 401, f"Route {method} {path} with regular user token must return 401, got {st} ({b})")

        # 4. Expired admin token -> 401
        with server.lock:
            server.tokens["expired_admin_tok"] = time.time() - 10
        exp_hdr = {"Authorization": "Bearer expired_admin_tok"}
        for method, path, *rest in admin_routes:
            body = rest[0] if rest else None
            st, b = invoke_handler(method, path, body=body, headers=exp_hdr)
            self.assertEqual(st, 401, f"Route {method} {path} with expired admin token must return 401, got {st} ({b})")

    def test_2_admin_login_and_server_side_logout_revocation(self):
        """Admin logs in, accesses admin API, then logs out and token is immediately revoked on server."""
        # Login
        st, b = invoke_handler("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(st, 200)
        adm_token = b["token"]
        self.assertTrue(len(adm_token) >= 32)

        # Access with token -> 200
        adm_hdr = {"Authorization": "Bearer " + adm_token}
        st_get, b_get = invoke_handler("GET", "/api/admin/users", headers=adm_hdr)
        self.assertEqual(st_get, 200)

        # Logout via POST /api/admin/logout
        st_lo, b_lo = invoke_handler("POST", "/api/admin/logout", headers=adm_hdr)
        self.assertEqual(st_lo, 200)
        self.assertTrue(b_lo.get("ok"))

        # Access with revoked token must now fail with 401
        st_rev, _ = invoke_handler("GET", "/api/admin/users", headers=adm_hdr)
        self.assertEqual(st_rev, 401)

    def test_3_admin_password_change_invalidates_all_active_tokens(self):
        """Changing admin password revokes all previously issued admin tokens."""
        # Issue 2 admin tokens
        st1, b1 = invoke_handler("POST", "/api/login", {"password": self.admin_pw})
        st2, b2 = invoke_handler("POST", "/api/login", {"password": self.admin_pw})
        tok1 = b1["token"]
        tok2 = b2["token"]

        # Change admin password
        st_pw, _ = invoke_handler("POST", "/api/password", {"password": "BrandNewAdminPw123!"}, headers={"Authorization": "Bearer " + tok1})
        self.assertEqual(st_pw, 200)

        # Both old tokens must now be rejected
        st_old1, _ = invoke_handler("GET", "/api/admin/users", headers={"Authorization": "Bearer " + tok1})
        self.assertEqual(st_old1, 401)
        st_old2, _ = invoke_handler("GET", "/api/admin/users", headers={"Authorization": "Bearer " + tok2})
        self.assertEqual(st_old2, 401)

        # Login with new password works
        st_new, b_new = invoke_handler("POST", "/api/login", {"password": "BrandNewAdminPw123!"})
        self.assertEqual(st_new, 200)


class TestUserAuthenticationSecurity(BaseSecurityTestCase):
    def test_4_user_password_change_revokes_other_sessions(self):
        """When user changes their password, all other active sessions are revoked while current session stays."""
        # Alice has two sessions: tok_alice_1 and tok_alice_2
        hdr1 = {"Authorization": "Bearer tok_alice_1"}
        hdr2 = {"Authorization": "Bearer tok_alice_2"}

        # Both valid initially
        st1, _ = invoke_handler("GET", "/api/user/me", headers=hdr1)
        st2, _ = invoke_handler("GET", "/api/user/me", headers=hdr2)
        self.assertEqual(st1, 200)
        self.assertEqual(st2, 200)

        # Alice changes password using session 1
        st_ch, _ = invoke_handler(
            "POST", "/api/user/profile",
            {"oldPassword": "Password_1", "newPassword": "NewPassword_1_Sec!"},
            headers=hdr1
        )
        self.assertEqual(st_ch, 200)

        # Current session (session 1) still works
        st1_after, _ = invoke_handler("GET", "/api/user/me", headers=hdr1)
        self.assertEqual(st1_after, 200)

        # Other session (session 2) is revoked
        st2_after, _ = invoke_handler("GET", "/api/user/me", headers=hdr2)
        self.assertEqual(st2_after, 401)

    def test_5_brute_force_rate_limiting_and_anti_flush_defense(self):
        """Repeated failed admin logins return 429; dummy spam keys cannot flush blocked attacker, fails cannot grow unbounded."""
        attacker_ip = "192.168.1.100"

        # 5 failed attempts
        for _ in range(5):
            st, _ = invoke_handler("POST", "/api/login", {"password": "WrongPassword"}, client_ip=attacker_ip)
            self.assertEqual(st, 401)

        # 6th attempt -> 429 Too Many Requests
        st6, b6 = invoke_handler("POST", "/api/login", {"password": "WrongPassword"}, client_ip=attacker_ip)
        self.assertEqual(st6, 429)

        # Attacker tries to flush the rate-limit dictionary by creating > 500 keys (up to 700 keys)
        for i in range(700):
            server.record_fail(f"dummy_spam_{i}", ttl=600)

        # Attacker IP must STILL be blocked (not wiped by cache eviction or limit overflow)
        st_after_spam, _ = invoke_handler("POST", "/api/login", {"password": "WrongPassword"}, client_ip=attacker_ip)
        self.assertEqual(st_after_spam, 429)

    def test_5a_rate_limit_capacity_boundary_and_fail_closed_under_full_active_blocks(self):
        """Test boundary conditions (500, 501, 700 keys), multithreading, and strict fail-closed protection."""
        server.fails.clear()

        # 1. Fill dictionary with exactly 500 active blocked keys (count >= 5)
        for i in range(500):
            with server.fails_lock:
                server.fails[f"blocked_ip_{i}"] = (5, time.time(), time.time() + 300)

        self.assertEqual(len(server.fails), 500)

        # 2. Existing blocked key remains blocked
        allowed, c, _ = server.check_fail_limit("blocked_ip_0", 5, 60)
        self.assertFalse(allowed)
        self.assertEqual(c, 5)

        # 3. Boundary check: attempt to add 501st key when all 500 existing keys are active blocks
        # record_fail must NOT evict any active block and must NOT expand fails beyond 500
        res = server.record_fail("new_attacker_ip_501", ttl=300, max_size=500)
        self.assertEqual(len(server.fails), 500)
        self.assertNotIn("new_attacker_ip_501", server.fails)
        self.assertEqual(res, 5)  # Safe fail-closed value returned

        # 4. Check that new keys in full-load fail-closed state are blocked by check_fail_limit
        allowed_new, _, _ = server.check_fail_limit("new_attacker_ip_501", 5, 60)
        self.assertFalse(allowed_new)

        # 5. Push 200 more keys (total 700 attempts)
        for j in range(200):
            server.record_fail(f"overflow_{j}", ttl=300, max_size=500)

        # Dictionary size strictly capped at 500, never grows uncontrollably
        self.assertEqual(len(server.fails), 500)

        # All original active blocks are preserved
        self.assertIn("blocked_ip_0", server.fails)
        self.assertIn("blocked_ip_499", server.fails)
        allowed_orig, _, _ = server.check_fail_limit("blocked_ip_499", 5, 60)
        self.assertFalse(allowed_orig)

        # 6. Multithreading test under concurrency
        import concurrent.futures
        def worker(idx):
            k = f"thread_key_{idx % 50}"
            server.record_fail(k, ttl=300, max_size=500)
            server.check_fail_limit(k, 5, 60)
            if idx % 10 == 0:
                server.reset_fail(k)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(worker, i) for i in range(100)]
            concurrent.futures.wait(futures)

        # Dictionary must be in a consistent state and size <= 500
        self.assertTrue(len(server.fails) <= 500)

    def test_5b_x_forwarded_for_spoofing_defense(self):
        """Attacker cannot bypass rate limiting or spoof identity by sending forged X-Forwarded-For or X-Real-IP header."""
        real_proxy_ip = "203.0.113.50"
        forged_client_ip = "198.51.100.77"

        # 1. Запрос через доверенный локальный прокси (127.0.0.1) c валидным X-Real-IP
        h_proxy_v4 = server.H.__new__(server.H)
        h_proxy_v4.headers = Message()
        h_proxy_v4.headers["X-Real-IP"] = real_proxy_ip
        h_proxy_v4.headers["X-Forwarded-For"] = forged_client_ip
        h_proxy_v4.client_address = ("127.0.0.1", 54321)
        self.assertEqual(server.get_client_ip(h_proxy_v4), real_proxy_ip)

        # 2. Запрос через доверенный IPv6 прокси (::1) c валидным X-Real-IP
        h_proxy_v6 = server.H.__new__(server.H)
        h_proxy_v6.headers = Message()
        h_proxy_v6.headers["X-Real-IP"] = "2001:db8::1"
        h_proxy_v6.client_address = ("::1", 54321)
        self.assertEqual(server.get_client_ip(h_proxy_v6), "2001:db8::1")

        # 3. Прямой запрос от чужого IP (НЕ из TRUSTED_PROXIES) с поддельным X-Real-IP:
        # X-Real-IP и X-Forwarded-For ПОЛНОСТЬЮ ИГНОРИРУЮТСЯ, используется реальный socket IP
        h_direct = server.H.__new__(server.H)
        h_direct.headers = Message()
        h_direct.headers["X-Real-IP"] = "1.2.3.4"
        h_direct.headers["X-Forwarded-For"] = "5.6.7.8"
        h_direct.client_address = ("198.51.100.5", 43210)
        self.assertEqual(server.get_client_ip(h_direct), "198.51.100.5")

        # 4. Прямой IPv6 запрос от чужого адреса с поддельным X-Real-IP
        h_direct_v6 = server.H.__new__(server.H)
        h_direct_v6.headers = Message()
        h_direct_v6.headers["X-Real-IP"] = "1.2.3.4"
        h_direct_v6.client_address = ("2607:f8b0:4005:805::200e", 43210)
        self.assertEqual(server.get_client_ip(h_direct_v6), "2607:f8b0:4005:805::200e")

        # 5. Запрос через доверенный прокси, но с некорректным X-Real-IP -> откат к IP прокси
        invalid_ips = ["::::", "999.999.999.999", "", "   ", "not_an_ip", "1.2.3.4; rm -rf", "256.0.0.1"]
        for bad_ip in invalid_ips:
            h_bad = server.H.__new__(server.H)
            h_bad.headers = Message()
            h_bad.headers["X-Real-IP"] = bad_ip
            h_bad.client_address = ("127.0.0.1", 54321)
            self.assertEqual(server.get_client_ip(h_bad), "127.0.0.1")

        # 6. Socket IP некорректен или пуст -> безопасный откат к 127.0.0.1
        h_none = server.H.__new__(server.H)
        h_none.headers = Message()
        h_none.client_address = ("invalid_socket_ip", 54321)
        self.assertEqual(server.get_client_ip(h_none), "127.0.0.1")

        # 7. Защита от брутфорса при прямом подключении: смена поддельных X-Real-IP / X-Forwarded-For не помогает
        direct_attacker = "198.51.100.99"
        for _ in range(5):
            hdrs = {"X-Real-IP": "10.0.0.1", "X-Forwarded-For": "10.0.0.2"}
            st, _ = invoke_handler("POST", "/api/login", {"password": "WrongPassword"}, headers=hdrs, client_ip=direct_attacker)
            self.assertEqual(st, 401)

        # 6-я попытка с другим поддельным IP всё равно блокируется 429
        hdrs_blocked = {"X-Real-IP": "172.16.0.1", "X-Forwarded-For": "172.16.0.2"}
        st_blocked, _ = invoke_handler("POST", "/api/login", {"password": "WrongPassword"}, headers=hdrs_blocked, client_ip=direct_attacker)
        self.assertEqual(st_blocked, 429)


class TestUploadAndIDORSecurity(BaseSecurityTestCase):
    def test_6_file_upload_validation(self):
        """File upload validates magic bytes, container signatures, and blocks SVG entirely."""
        # Get admin token
        st_l, b_l = invoke_handler("POST", "/api/login", {"password": self.admin_pw})
        adm_hdr = {"Authorization": "Bearer " + b_l["token"]}

        # 1. Upload SVG -> rejected with 400 (SVG is forbidden)
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        h_svg = dict(adm_hdr, **{"X-Filename": "test.svg"})
        st_s, b_s = invoke_handler("POST", "/api/upload?name=test_svg", body=malicious_svg, headers=h_svg)
        self.assertEqual(st_s, 400)
        self.assertTrue("Разрешены" in b_s.get("error", "") or "SVG" in b_s.get("error", ""))

        # 2. Upload fake PNG (invalid magic bytes) -> rejected with 400
        fake_png = b'NOT_A_REAL_PNG_CONTENT_1234567890'
        h_png = dict(adm_hdr, **{"X-Filename": "test.png"})
        st_p, b_p = invoke_handler("POST", "/api/upload?name=test_png", body=fake_png, headers=h_png)
        self.assertEqual(st_p, 400)
        self.assertIn("PNG", b_p.get("error", ""))

        # 3. Upload valid PNG with real magic bytes -> accepted with 200
        valid_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        st_ok, b_ok = invoke_handler("POST", "/api/upload?name=valid_png", body=valid_png, headers=h_png)
        self.assertEqual(st_ok, 200)
        self.assertIn("content/uploads/valid_png.png", b_ok["path"])

        # 4. Negative tests for MP4/MOV: invalid container signatures
        h_mp4 = dict(adm_hdr, **{"X-Filename": "video.mp4"})

        # 4a. Short file < 16 bytes
        st_m1, b_m1 = invoke_handler("POST", "/api/upload?name=video_short", body=b'\x00\x00\x00\x08ftyp', headers=h_mp4)
        self.assertEqual(st_m1, 400)
        self.assertIn("короткий", b_m1.get("error", ""))

        # 4b. Invalid box type (e.g. b'fake')
        fake_box_mp4 = b'\x00\x00\x00\x20fakeisom\x00\x00\x02\x00isomiso2avc1mp41'
        st_m2, b_m2 = invoke_handler("POST", "/api/upload?name=video_fakebox", body=fake_box_mp4, headers=h_mp4)
        self.assertEqual(st_m2, 400)
        self.assertIn("сигнатура", b_m2.get("error", ""))

        # 4c. ftyp box with invalid/corrupt brand bytes (control characters)
        bad_brand_mp4 = b'\x00\x00\x00\x18ftyp\x01\x02\x03\x04\x00\x00\x00\x00isommp42'
        st_m3, b_m3 = invoke_handler("POST", "/api/upload?name=video_badbrand", body=bad_brand_mp4, headers=h_mp4)
        self.assertEqual(st_m3, 400)
        self.assertIn("бренд", b_m3.get("error", ""))

        # 4d. Corrupted box size: box_size exceeds total file length (bounds overflow)
        overflow_box_mp4 = b'\x00\x00\x00\x40ftypisom\x00\x00\x02\x00isomiso2avc1mp41'  # claims 64 bytes, file has 32 bytes
        st_m_ov, b_m_ov = invoke_handler("POST", "/api/upload?name=video_overflow", body=overflow_box_mp4, headers=h_mp4)
        self.assertEqual(st_m_ov, 400)
        self.assertIn("границы", b_m_ov.get("error", ""))

        # 4e. Corrupted box size: box_size < 8 (invalid header)
        invalid_size_mp4 = b'\x00\x00\x00\x04ftypisom\x00\x00\x02\x00isomiso2avc1mp41'
        st_m_sz, b_m_sz = invoke_handler("POST", "/api/upload?name=video_badsize", body=invalid_size_mp4, headers=h_mp4)
        self.assertEqual(st_m_sz, 400)
        self.assertIn("< 8", b_m_sz.get("error", ""))

        # 5. Positive test for MP4: valid container signature (ftyp isom)
        valid_mp4 = b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41'
        st_m4, b_m4 = invoke_handler("POST", "/api/upload?name=video_ok", body=valid_mp4, headers=h_mp4)
        self.assertEqual(st_m4, 200)
        self.assertIn("content/uploads/video_ok.mp4", b_m4["path"])

        # 4f. Incomplete box header at tail of stream
        truncated_tail_mp4 = valid_mp4 + b'\x00\x00\x00'  # 3 extra bytes without complete header
        st_m_tail, b_m_tail = invoke_handler("POST", "/api/upload?name=video_badtail", body=truncated_tail_mp4, headers=h_mp4)
        self.assertEqual(st_m_tail, 400)
        self.assertIn("неполный заголовок", b_m_tail.get("error", ""))

        # 6. Positive test for MOV / QuickTime container
        h_mov = dict(adm_hdr, **{"X-Filename": "clip.mov"})
        valid_mov = b'\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  '
        st_mov, b_mov = invoke_handler("POST", "/api/upload?name=clip_ok", body=valid_mov, headers=h_mov)
        self.assertEqual(st_mov, 200)
        self.assertIn("content/uploads/clip_ok.mov", b_mov["path"])

        # 7. Extended size (64-bit) ftyp container test:
        # raw_box_size == 1, 8 bytes extended size (24), 4 bytes major_brand (isom)
        ext_size_bytes = (24).to_bytes(8, 'big')
        valid_ext_mp4 = b'\x00\x00\x00\x01ftyp' + ext_size_bytes + b'isom\x00\x00\x02\x00'
        st_ext, b_ext = invoke_handler("POST", "/api/upload?name=video_ext", body=valid_ext_mp4, headers=h_mp4)
        self.assertEqual(st_ext, 200)
        self.assertIn("content/uploads/video_ext.mp4", b_ext["path"])

        # 8. Extended size ftyp too short for major_brand and minor_version:
        # 8a. Extended size ftyp of 20 bytes (missing minor_version, requires min 24 bytes) -> rejected with 400
        ext_20_size_bytes = (20).to_bytes(8, 'big')
        ext_20_mp4 = b'\x00\x00\x00\x01ftyp' + ext_20_size_bytes + b'isom'
        st_bext20, b_bext20 = invoke_handler("POST", "/api/upload?name=video_badext20", body=ext_20_mp4, headers=h_mp4)
        self.assertEqual(st_bext20, 400)
        self.assertIn("слишком короткий", b_bext20.get("error", ""))
        self.assertIn("24", b_bext20.get("error", ""))

        # 8b. Standard ftyp of 12 bytes (missing minor_version, requires min 16 bytes) -> rejected with 400
        std_12_mp4 = b'\x00\x00\x00\x0cftypisom' + b'\x00\x00\x00\x00'  # 16-byte total file with a 12-byte ftyp box
        st_bstd12, b_bstd12 = invoke_handler("POST", "/api/upload?name=video_badstd12", body=std_12_mp4, headers=h_mp4)
        self.assertEqual(st_bstd12, 400)
        self.assertIn("слишком короткий", b_bstd12.get("error", ""))
        self.assertIn("16", b_bstd12.get("error", ""))

    def test_7_idor_prevention_on_payments_and_data_privacy(self):
        """User cannot access payments belonging to another user, and public profile exposes no private credentials."""
        now = int(time.time())
        with server.db_lock, sqlite3.connect(server.DB_FILE) as conn:
            conn.execute(
                'INSERT INTO payments (id, user_id, plan, days, amount, currency, provider, status, payment_id, created_at, updated_at) '
                'VALUES (1, 2, "pro", 30, 490, "RUB", "yookassa", "pending", "pay_bob_secret_123", ?, ?)',
                (now, now)
            )
            conn.commit()

        # Alice tries to inspect Bob's payment IDOR
        hdr_alice = {"Authorization": "Bearer tok_alice_1"}
        st_idor, _ = invoke_handler("GET", "/api/payment/check?paymentId=pay_bob_secret_123", headers=hdr_alice)
        self.assertEqual(st_idor, 403)

        # Alice inspects Bob's public profile
        st_prof, b_prof = invoke_handler("GET", "/api/users/profile?username=bob", headers=hdr_alice)
        self.assertEqual(st_prof, 200)
        card = b_prof["profile"]

        # Sensitive columns must never appear in public profile
        self.assertNotIn("email", card)
        self.assertNotIn("pw_hash", card)
        self.assertNotIn("pw_salt", card)
        self.assertNotIn("token", card)
        self.assertNotIn("oauth_id", card)


if __name__ == "__main__":
    unittest.main()
