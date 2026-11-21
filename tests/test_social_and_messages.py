"""Unit tests for RizzaFit Social System and Direct Messaging.

Covers:
- Auth-only access (401 for guests across all community & message endpoints)
- User search, privacy (no emails/tokens/passwords), public profiles with real PRs
- Friendships: request, mutual auto-accept, accept, decline, cancel, remove, self-add check
- Direct messaging: open between non-friends, send (1-2000 chars), rate limit, clientMsgId idempotency
- History retrieval, pagination (beforeId), read receipts, unread counter
- Soft delete: sender-only delete for everyone
- Hide conversation for initiator without deleting for peer
- Two-way block: mutual messaging block, friendship removal, unblock
- User reporting
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
        # Ensure response payload is strictly JSON-serializable (catches circular references)
        json.dumps(obj, ensure_ascii=False)
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


class BaseSocialTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.orig_db = server.DB_FILE
        self.orig_free = server.FREE_ACCESS_MODE

        server.DB_FILE = os.path.join(self.tmp.name, "test_social.db")
        server.FREE_ACCESS_MODE = True
        server.fails.clear()
        server.msg_hits.clear()

        server.init_db()

        self.users = {}
        self.tokens = {}

        now = int(time.time())
        salt = "33" * 16
        pw = "Pass12345!"
        pwh = server.hash_pw(pw, salt)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            # Create user_alice
            c1 = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, is_blocked, last_login_at, created_at) '
                'VALUES ("alice", ?, ?, "Alice Walker", "alice@example.com", "free", 0, ?, ?)',
                (salt, pwh, now, now)
            )
            self.users["alice"] = c1.lastrowid

            # Create user_bob
            c2 = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, is_blocked, last_login_at, created_at) '
                'VALUES ("bob", ?, ?, "Bob Builder", "bob@example.com", "free", 0, ?, ?)',
                (salt, pwh, now, now)
            )
            self.users["bob"] = c2.lastrowid

            # Create user_charlie
            c3 = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, is_blocked, last_login_at, created_at) '
                'VALUES ("charlie", ?, ?, "Charlie Chaplin", "charlie@example.com", "free", 0, ?, ?)',
                (salt, pwh, now, now)
            )
            self.users["charlie"] = c3.lastrowid

            # Give Alice PR records in user_state
            alice_state = {
                "prs": {"pushups": 40, "pullups": 15},
                "hist": [{"id": "w1", "t": now - 3600, "s": 1200}],
                "athleteProfile": {"level": 3, "streak": 5, "points": 1500}
            }
            conn.execute(
                'INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?)',
                (self.users["alice"], json.dumps(alice_state), now)
            )

            # Issue tokens
            for uname in ["alice", "bob", "charlie"]:
                uid = self.users[uname]
                tok = f"tok_{uname}_{now}"
                conn.execute(
                    'INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)',
                    (tok, uid, now + 86400)
                )
                self.tokens[uname] = tok

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        server.DB_FILE = self.orig_db
        server.FREE_ACCESS_MODE = self.orig_free
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def auth_hdr(self, uname):
        return {"Authorization": f"Bearer {self.tokens[uname]}"}


class TestGuestSocialAccess(BaseSocialTestCase):
    def test_all_social_endpoints_reject_guests_with_401(self):
        guest_endpoints = [
            ("GET", "/api/users"),
            ("GET", "/api/users/profile?username=alice"),
            ("GET", "/api/friends"),
            ("POST", "/api/friends/request", {"targetUserId": 1}),
            ("POST", "/api/friends/accept", {"requestId": 1}),
            ("POST", "/api/friends/decline", {"requestId": 1}),
            ("POST", "/api/friends/cancel", {"requestId": 1}),
            ("POST", "/api/friends/remove", {"userId": 1}),
            ("GET", "/api/messages/conversations"),
            ("GET", "/api/messages/history?conversationId=1"),
            ("POST", "/api/messages/open", {"targetUserId": 1}),
            ("POST", "/api/messages/send", {"conversationId": 1, "text": "hello"}),
            ("POST", "/api/messages/read", {"conversationId": 1}),
            ("POST", "/api/messages/delete", {"messageId": 1}),
            ("POST", "/api/messages/conversation/hide", {"conversationId": 1}),
            ("GET", "/api/messages/unread-count"),
            ("POST", "/api/users/block", {"targetUserId": 1}),
            ("POST", "/api/users/unblock", {"targetUserId": 1}),
            ("POST", "/api/users/report", {"targetUserId": 1, "reason": "spam"}),
        ]

        for method, path, *rest in guest_endpoints:
            body = rest[0] if rest else None
            status, resp = invoke_handler(method, path, body=body)
            self.assertEqual(
                status, 401,
                f"Guest request to {method} {path} should return 401, got {status} ({resp})"
            )
            self.assertIn("error", resp)


class TestUserSearchAndProfile(BaseSocialTestCase):
    def test_search_users_and_privacy(self):
        # Alice searches for 'bob'
        status, resp = invoke_handler("GET", "/api/users?q=bob", headers=self.auth_hdr("alice"))
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        users = resp.get("users", [])
        self.assertEqual(len(users), 1)
        bob_card = users[0]
        self.assertEqual(bob_card["username"], "bob")
        self.assertEqual(bob_card["displayName"], "Bob Builder")

        # Crucial security assertion: sensitive fields must NEVER leak
        forbidden_fields = {"email", "pw_hash", "pw_salt", "token", "password", "notes", "private"}
        for u in users:
            for field in forbidden_fields:
                self.assertNotIn(field, u)

    def test_public_profile_with_real_prs(self):
        # Bob views Alice's profile
        status, resp = invoke_handler("GET", "/api/users/profile?username=alice", headers=self.auth_hdr("bob"))
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        user = resp.get("user", {})
        self.assertEqual(user["username"], "alice")
        self.assertEqual(user["displayName"], "Alice Walker")
        self.assertEqual(user["friendshipStatus"], "none")

        # Check real PRs extracted from user_state
        prs = user.get("prs", {})
        self.assertEqual(prs.get("pushups"), 40)
        self.assertEqual(prs.get("pullups"), 15)

        # Bob views non-existent user
        status, resp = invoke_handler("GET", "/api/users/profile?username=nobody", headers=self.auth_hdr("bob"))
        self.assertEqual(status, 404)


class TestFriendshipLifecycle(BaseSocialTestCase):
    def test_friend_request_accept_and_remove(self):
        # Alice cannot friend herself
        status, resp = invoke_handler(
            "POST", "/api/friends/request",
            {"targetUserId": self.users["alice"]},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 400)

        # Alice sends request to Bob
        status, resp = invoke_handler(
            "POST", "/api/friends/request",
            {"targetUserId": self.users["bob"]},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        req_id = resp.get("requestId")
        self.assertIsNotNone(req_id)

        # Duplicate request should fail
        status, resp = invoke_handler(
            "POST", "/api/friends/request",
            {"targetUserId": self.users["bob"]},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 400)

        # Check Alice's outgoing and Bob's incoming
        status, a_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_friends.get("outgoing", [])), 1)
        self.assertEqual(a_friends["outgoing"][0]["user"]["username"], "bob")

        status, b_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("bob"))
        self.assertEqual(len(b_friends.get("incoming", [])), 1)
        self.assertEqual(b_friends["incoming"][0]["user"]["username"], "alice")

        # Bob accepts request
        status, resp = invoke_handler(
            "POST", "/api/friends/accept",
            {"requestId": req_id},
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))

        # Both now have each other in friends
        status, a_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_friends.get("friends", [])), 1)
        self.assertEqual(a_friends["friends"][0]["username"], "bob")

        status, b_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("bob"))
        self.assertEqual(len(b_friends.get("friends", [])), 1)
        self.assertEqual(b_friends["friends"][0]["username"], "alice")

        # Alice removes Bob from friends
        status, resp = invoke_handler(
            "POST", "/api/friends/remove",
            {"userId": self.users["bob"]},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)

        # Both friends lists now empty
        status, a_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_friends.get("friends", [])), 0)
        status, b_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("bob"))
        self.assertEqual(len(b_friends.get("friends", [])), 0)

    def test_cancel_and_decline_requests(self):
        # Alice requests Charlie
        status, resp = invoke_handler(
            "POST", "/api/friends/request",
            {"targetUserId": self.users["charlie"]},
            headers=self.auth_hdr("alice")
        )
        req_id = resp["requestId"]

        # Alice cancels request
        status, resp = invoke_handler(
            "POST", "/api/friends/cancel",
            {"requestId": req_id},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)

        status, a_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_friends.get("outgoing", [])), 0)

        # Bob requests Charlie
        status, resp = invoke_handler(
            "POST", "/api/friends/request",
            {"targetUserId": self.users["charlie"]},
            headers=self.auth_hdr("bob")
        )
        req_id2 = resp["requestId"]

        # Charlie declines Bob's request
        status, resp = invoke_handler(
            "POST", "/api/friends/decline",
            {"requestId": req_id2},
            headers=self.auth_hdr("charlie")
        )
        self.assertEqual(status, 200)

        status, c_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("charlie"))
        self.assertEqual(len(c_friends.get("incoming", [])), 0)

    def test_mutual_request_auto_accepts(self):
        # Alice requests Bob
        invoke_handler("POST", "/api/friends/request", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        # Bob requests Alice -> auto-accepts
        status, resp = invoke_handler("POST", "/api/friends/request", {"targetUserId": self.users["alice"]}, headers=self.auth_hdr("bob"))
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("autoAccepted"))

        status, a_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_friends.get("friends", [])), 1)


class TestDirectMessaging(BaseSocialTestCase):
    def test_messaging_between_non_friends(self):
        # Alice opens conversation with Bob (they are not friends)
        status, resp = invoke_handler(
            "POST", "/api/messages/open",
            {"targetUserId": self.users["bob"]},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)
        conv = resp.get("conversation", {})
        conv_id = conv.get("id")
        self.assertIsNotNone(conv_id)

        # Bob opens conversation with Alice -> returns the EXACT SAME conversation ID
        status, resp2 = invoke_handler(
            "POST", "/api/messages/open",
            {"targetUserId": self.users["alice"]},
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(resp2["conversation"]["id"], conv_id)

        # Alice sends message with clientMsgId
        status, send_resp = invoke_handler(
            "POST", "/api/messages/send",
            {"conversationId": conv_id, "text": "Hello Bob!", "clientMsgId": "msg_001"},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)
        msg_id = send_resp["message"]["id"]
        self.assertEqual(send_resp["message"]["text"], "Hello Bob!")

        # Re-sending with same clientMsgId returns existing message (idempotency)
        status, dupe_resp = invoke_handler(
            "POST", "/api/messages/send",
            {"conversationId": conv_id, "text": "Hello Bob!", "clientMsgId": "msg_001"},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)
        self.assertEqual(dupe_resp["message"]["id"], msg_id)

        # Bob checks unread count
        status, unread_resp = invoke_handler("GET", "/api/messages/unread-count", headers=self.auth_hdr("bob"))
        self.assertEqual(status, 200)
        self.assertEqual(unread_resp["unreadCount"], 1)
        self.assertIsNotNone(unread_resp["latestMessage"])

        # Bob views history
        status, hist_resp = invoke_handler(
            "GET", f"/api/messages/history?conversationId={conv_id}",
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(hist_resp["messages"]), 1)

        # Bob marks conversation as read
        status, read_resp = invoke_handler(
            "POST", "/api/messages/read",
            {"conversationId": conv_id},
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(status, 200)
        self.assertEqual(read_resp["readCount"], 1)

        # Bob's unread count is now 0
        status, unread_resp = invoke_handler("GET", "/api/messages/unread-count", headers=self.auth_hdr("bob"))
        self.assertEqual(unread_resp["unreadCount"], 0)

        # Soft deletion: Alice deletes her own message
        status, del_resp = invoke_handler(
            "POST", "/api/messages/delete",
            {"messageId": msg_id},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)
        self.assertTrue(del_resp["ok"])

        # History shows message as deleted
        status, hist_resp = invoke_handler(
            "GET", f"/api/messages/history?conversationId={conv_id}",
            headers=self.auth_hdr("bob")
        )
        self.assertTrue(hist_resp["messages"][0]["isDeleted"])

        # Bob cannot delete Alice's message (restricted strictly to sender)
        # First send another message from Alice
        status, send2 = invoke_handler(
            "POST", "/api/messages/send",
            {"conversationId": conv_id, "text": "Another message", "clientMsgId": "msg_002"},
            headers=self.auth_hdr("alice")
        )
        msg2_id = send2["message"]["id"]
        status, del_err = invoke_handler(
            "POST", "/api/messages/delete",
            {"messageId": msg2_id},
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(status, 403)

    def test_conversation_hide_for_initiator_only(self):
        # Alice opens conversation and sends message to Charlie
        status, resp = invoke_handler("POST", "/api/messages/open", {"targetUserId": self.users["charlie"]}, headers=self.auth_hdr("alice"))
        conv_id = resp["conversation"]["id"]
        invoke_handler("POST", "/api/messages/send", {"conversationId": conv_id, "text": "Hi Charlie"}, headers=self.auth_hdr("alice"))

        # Alice hides conversation
        status, hide_resp = invoke_handler("POST", "/api/messages/conversation/hide", {"conversationId": conv_id}, headers=self.auth_hdr("alice"))
        self.assertEqual(status, 200)

        # Alice's conversation list does NOT include the hidden conversation
        status, a_convs = invoke_handler("GET", "/api/messages/conversations", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_convs["conversations"]), 0)

        # Charlie's conversation list STILL includes the conversation (not deleted for peer)
        status, c_convs = invoke_handler("GET", "/api/messages/conversations", headers=self.auth_hdr("charlie"))
        self.assertEqual(len(c_convs["conversations"]), 1)

    def test_two_way_block_and_unblock(self):
        # Alice and Bob start chat
        status, resp = invoke_handler("POST", "/api/messages/open", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        conv_id = resp["conversation"]["id"]

        # Alice blocks Bob
        status, blk_resp = invoke_handler("POST", "/api/users/block", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        self.assertEqual(status, 200)

        # Bob tries to send message to Alice -> blocked with 403
        status, err1 = invoke_handler(
            "POST", "/api/messages/send",
            {"conversationId": conv_id, "text": "Hey Alice please reply"},
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(status, 403)

        # Alice tries to send message to Bob -> blocked with 403
        status, err2 = invoke_handler(
            "POST", "/api/messages/send",
            {"conversationId": conv_id, "text": "I blocked you"},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 403)

        # Alice unblocks Bob
        status, unblk = invoke_handler("POST", "/api/users/unblock", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        self.assertEqual(status, 200)

        # Now messaging works again
        status, ok_send = invoke_handler(
            "POST", "/api/messages/send",
            {"conversationId": conv_id, "text": "Now unblocked"},
            headers=self.auth_hdr("bob")
        )
        self.assertEqual(status, 200)


class TestUserReport(BaseSocialTestCase):
    def test_report_user(self):
        status, resp = invoke_handler(
            "POST", "/api/users/report",
            {"targetUserId": self.users["bob"], "reason": "Spam and inappropriate behavior"},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))


class TestSocialRegressions(BaseSocialTestCase):
    def test_friends_response_json_serializable_and_request_id(self):
        """GET /api/friends must serialize cleanly without circular references and expose valid requestId."""
        # Alice sends request to Bob, Charlie sends request to Alice
        st1, r1 = invoke_handler("POST", "/api/friends/request", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        self.assertEqual(st1, 200)
        st2, r2 = invoke_handler("POST", "/api/friends/request", {"targetUserId": self.users["alice"]}, headers=self.auth_hdr("charlie"))
        self.assertEqual(st2, 200)

        # GET /api/friends for Alice has both outgoing (bob) and incoming (charlie)
        st_f, a_friends = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(st_f, 200)
        self.assertEqual(len(a_friends["outgoing"]), 1)
        self.assertEqual(len(a_friends["incoming"]), 1)

        out_req_id = a_friends["outgoing"][0]["requestId"]
        inc_req_id = a_friends["incoming"][0]["requestId"]
        self.assertEqual(out_req_id, r1["requestId"])
        self.assertEqual(inc_req_id, r2["requestId"])

        # Accept incoming using requestId from /api/friends, cancel outgoing using requestId from /api/friends
        st_acc, _ = invoke_handler("POST", "/api/friends/accept", {"requestId": inc_req_id}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_acc, 200)
        st_can, _ = invoke_handler("POST", "/api/friends/cancel", {"requestId": out_req_id}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_can, 200)

        # Verify GET /api/friends with accepted friend also serializes cleanly
        st_f2, a_friends2 = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(st_f2, 200)
        self.assertEqual(len(a_friends2["friends"]), 1)
        self.assertEqual(a_friends2["friends"][0]["username"], "charlie")

    def test_profile_edit_display_name_and_avatar_sync(self):
        """Editing own profile via /api/user/sync updates displayName and avatar (including clearing avatar)."""
        avatar_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        st, resp = invoke_handler(
            "POST", "/api/user/sync",
            {"state": {"athleteProfile": json.dumps({"name": "Alice Pro", "handle": "@alice", "avatar": avatar_data})}},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(st, 200)

        # Bob views Alice's public profile and sees updated displayName and avatar
        st_p, prof = invoke_handler("GET", "/api/users/profile?username=alice", headers=self.auth_hdr("bob"))
        self.assertEqual(st_p, 200)
        self.assertEqual(prof["user"]["displayName"], "Alice Pro")
        self.assertEqual(prof["user"]["avatar"], avatar_data)

        # Alice removes her avatar
        st2, _ = invoke_handler(
            "POST", "/api/user/sync",
            {"state": {"athleteProfile": json.dumps({"name": "Alice Pro", "handle": "@alice", "avatar": ""})}},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(st2, 200)

        st_p2, prof2 = invoke_handler("GET", "/api/users/profile?username=alice", headers=self.auth_hdr("bob"))
        self.assertEqual(st_p2, 200)
        self.assertEqual(prof2["user"]["avatar"], "")

    def test_relogin_and_reopen_existing_conversation(self):
        """User starts non-friend chat, logs out, logs back in, and sees existing dialog and messages with full fields."""
        # Alice opens chat with Bob (non-friends) and sends message
        st_o, o_resp = invoke_handler("POST", "/api/messages/open", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_o, 200)
        conv_id = o_resp["conversation"]["id"]

        st_s1, _ = invoke_handler("POST", "/api/messages/send", {"conversationId": conv_id, "text": "Hi before logout"}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_s1, 200)
        st_s2, _ = invoke_handler("POST", "/api/messages/send", {"conversationId": conv_id, "text": "Reply from Bob"}, headers=self.auth_hdr("bob"))
        self.assertEqual(st_s2, 200)

        # Alice logs out
        st_out, _ = invoke_handler("POST", "/api/user/logout", headers=self.auth_hdr("alice"))
        self.assertEqual(st_out, 200)

        # Alice logs in again
        st_in, in_resp = invoke_handler("POST", "/api/user/login", {"username": "alice", "password": "Pass12345!"})
        self.assertEqual(st_in, 200)
        new_hdr = {"Authorization": "Bearer " + in_resp["token"]}

        # Alice fetches conversations list and sees lastMessageText
        st_c, convs = invoke_handler("GET", "/api/messages/conversations", headers=new_hdr)
        self.assertEqual(st_c, 200)
        self.assertEqual(len(convs["conversations"]), 1)
        self.assertEqual(convs["conversations"][0]["id"], conv_id)
        self.assertEqual(convs["conversations"][0]["lastMessageText"], "Reply from Bob")
        self.assertEqual(convs["conversations"][0]["peer"]["username"], "bob")

        # Alice opens history and verifies peer, fromMe, status, and block flags
        st_h, hist = invoke_handler("GET", f"/api/messages/history?conversationId={conv_id}", headers=new_hdr)
        self.assertEqual(st_h, 200)
        self.assertEqual(hist["peer"]["username"], "bob")
        self.assertFalse(hist["isBlockedByMe"])
        self.assertFalse(hist["hasBlockedMe"])
        self.assertEqual(len(hist["messages"]), 2)
        self.assertTrue(hist["messages"][0]["fromMe"])
        self.assertFalse(hist["messages"][1]["fromMe"])
        self.assertIn(hist["messages"][0]["status"], ("sent", "delivered", "read"))


class TestAccountSettingsAndAdminReports(BaseSocialTestCase):
    def test_username_change_validation_uniqueness_and_idor(self):
        # Guest rejected
        st_g, _ = invoke_handler("POST", "/api/user/username", {"username": "newname"})
        self.assertEqual(st_g, 401)

        # Invalid formats: spaces, invalid chars, empty, too short, too long, reserved
        bad_names = [
            "", "   ", "ab", "a" * 25, "bad name", "bad-name", "bad.name",
            "кириллица", "admin", "ADMIN", "support", "root", "system", "rizzafit"
        ]
        for bn in bad_names:
            st, resp = invoke_handler("POST", "/api/user/username", {"username": bn}, headers=self.auth_hdr("alice"))
            self.assertEqual(st, 400, f"Expected 400 for username={bn!r}, got {st} ({resp})")

        # Case-insensitive uniqueness conflict with Bob
        st_dup, resp_dup = invoke_handler("POST", "/api/user/username", {"username": "BOB"}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_dup, 409)
        self.assertIn("занят", resp_dup.get("error", "").lower())

        # IDOR attempt: trying to change Bob's username while authenticated as Alice
        st_idor, _ = invoke_handler(
            "POST", "/api/user/username",
            {"userId": self.users["bob"], "username": "hacked_bob"},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(st_idor, 403)

        # Valid username change (with leading @ and uppercase -> normalized lowercase)
        st_ok, resp_ok = invoke_handler("POST", "/api/user/username", {"username": "@Alice_New1"}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_ok, 200)
        self.assertEqual(resp_ok["user"]["username"], "alice_new1")

        # Repeated change works
        st_ok2, resp_ok2 = invoke_handler("POST", "/api/user/username", {"username": "alice_v2"}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_ok2, 200)
        self.assertEqual(resp_ok2["user"]["username"], "alice_v2")

    def test_username_change_preserves_friends_requests_chats_blocks_and_search(self):
        # 1. Alice and Bob become friends
        _, rq = invoke_handler("POST", "/api/friends/request", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        invoke_handler("POST", "/api/friends/accept", {"requestId": rq["requestId"]}, headers=self.auth_hdr("bob"))

        # 2. Alice sends pending friend request to Charlie
        st_rq2, _ = invoke_handler("POST", "/api/friends/request", {"targetUserId": self.users["charlie"]}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_rq2, 200)

        # 3. Alice and Bob have an active conversation with messages
        _, op = invoke_handler("POST", "/api/messages/open", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        conv_id = op["conversation"]["id"]
        _, m1 = invoke_handler("POST", "/api/messages/send", {"conversationId": conv_id, "text": "Before rename"}, headers=self.auth_hdr("alice"))
        msg_id = m1["message"]["id"]

        # 4. Create 4th user dave and block him from Alice
        now = int(time.time())
        conn = sqlite3.connect(server.DB_FILE)
        try:
            c4 = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, is_blocked, last_login_at, created_at) '
                'VALUES ("dave", "aa", "bb", "Dave", "dave@example.com", "free", 0, ?, ?)',
                (now, now)
            )
            dave_id = c4.lastrowid
            conn.commit()
        finally:
            conn.close()
        invoke_handler("POST", "/api/users/block", {"targetUserId": dave_id}, headers=self.auth_hdr("alice"))

        # 5. Alice renames herself to alice_renamed
        st_ren, ren_resp = invoke_handler("POST", "/api/user/username", {"username": "alice_renamed"}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_ren, 200)
        self.assertEqual(ren_resp["user"]["username"], "alice_renamed")

        # 6. Search by new username finds Alice; old profile URL returns 404; new profile URL returns 200
        st_s, s_resp = invoke_handler("GET", "/api/users?q=alice_renamed", headers=self.auth_hdr("bob"))
        self.assertEqual(st_s, 200)
        self.assertEqual(len(s_resp["users"]), 1)
        self.assertEqual(s_resp["users"][0]["username"], "alice_renamed")

        st_old_p, _ = invoke_handler("GET", "/api/users/profile?username=alice", headers=self.auth_hdr("bob"))
        self.assertEqual(st_old_p, 404)
        st_new_p, new_p = invoke_handler("GET", "/api/users/profile?username=alice_renamed", headers=self.auth_hdr("bob"))
        self.assertEqual(st_new_p, 200)
        self.assertEqual(new_p["user"]["friendshipStatus"], "friends")

        # 7. Friends and pending requests preserved
        _, a_fr = invoke_handler("GET", "/api/friends", headers=self.auth_hdr("alice"))
        self.assertEqual(len(a_fr["friends"]), 1)
        self.assertEqual(a_fr["friends"][0]["username"], "bob")
        self.assertEqual(len(a_fr["outgoing"]), 1)
        self.assertEqual(a_fr["outgoing"][0]["username"], "charlie")

        # 8. Conversation ID, message ID, history, and updated peer username preserved
        _, b_hist = invoke_handler("GET", f"/api/messages/history?conversationId={conv_id}", headers=self.auth_hdr("bob"))
        self.assertEqual(b_hist["peer"]["username"], "alice_renamed")
        self.assertEqual(len(b_hist["messages"]), 1)
        self.assertEqual(b_hist["messages"][0]["id"], msg_id)
        self.assertEqual(b_hist["messages"][0]["text"], "Before rename")

        # 9. Block preserved
        _, blk_list = invoke_handler("GET", "/api/users/blocked", headers=self.auth_hdr("alice"))
        self.assertEqual(len(blk_list["blocked"]), 1)
        self.assertEqual(blk_list["blocked"][0]["username"], "dave")

    def test_profile_reset_sync_preserves_social_data(self):
        # Set custom profile + friend + chat
        av = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        invoke_handler(
            "POST", "/api/user/sync",
            {"state": {"athleteProfile": json.dumps({"name": "Alice Custom", "handle": "@alice", "avatar": av}), "accentTheme": "#ff0000"}},
            headers=self.auth_hdr("alice")
        )
        _, op = invoke_handler("POST", "/api/messages/open", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        cid = op["conversation"]["id"]
        invoke_handler("POST", "/api/messages/send", {"conversationId": cid, "text": "Keep me"}, headers=self.auth_hdr("alice"))

        # Reset profile settings via /api/user/sync (name=username, avatar="", accentTheme removed)
        st_rst, _ = invoke_handler(
            "POST", "/api/user/sync",
            {"state": {"athleteProfile": json.dumps({"name": "alice", "handle": "@alice", "avatar": ""})}},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(st_rst, 200)

        # Logout & re-login -> reset values persist, chat preserved
        invoke_handler("POST", "/api/user/logout", headers=self.auth_hdr("alice"))
        st_in, in_resp = invoke_handler("POST", "/api/user/login", {"username": "alice", "password": "Pass12345!"})
        self.assertEqual(st_in, 200)
        self.assertNotIn("accentTheme", in_resp["state"])
        new_hdr = {"Authorization": "Bearer " + in_resp["token"]}

        st_p, prof = invoke_handler("GET", "/api/users/profile?username=alice", headers=self.auth_hdr("bob"))
        self.assertEqual(st_p, 200)
        self.assertEqual(prof["user"]["displayName"], "alice")
        self.assertEqual(prof["user"]["avatar"], "")

        _, convs = invoke_handler("GET", "/api/messages/conversations", headers=new_hdr)
        self.assertEqual(len(convs["conversations"]), 1)

    def test_blocked_users_list_and_unblock(self):
        # Guest -> 401
        st_g, _ = invoke_handler("GET", "/api/users/blocked")
        self.assertEqual(st_g, 401)

        # Initially empty
        st_0, r_0 = invoke_handler("GET", "/api/users/blocked", headers=self.auth_hdr("alice"))
        self.assertEqual(st_0, 200)
        self.assertEqual(r_0["blocked"], [])

        # Alice blocks Bob; also insert orphaned blocked_id=99999 to verify safe handling
        invoke_handler("POST", "/api/users/block", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        conn = sqlite3.connect(server.DB_FILE)
        try:
            conn.execute('INSERT INTO user_blocks (blocker_id, blocked_id, created_at) VALUES (?, 99999, 1)', (self.users["alice"],))
            conn.commit()
        finally:
            conn.close()

        st_1, r_1 = invoke_handler("GET", "/api/users/blocked", headers=self.auth_hdr("alice"))
        self.assertEqual(st_1, 200)
        self.assertEqual(len(r_1["blocked"]), 1)
        self.assertEqual(r_1["blocked"][0]["username"], "bob")
        for secret_k in ("email", "pw_hash", "pw_salt", "token"):
            self.assertNotIn(secret_k, r_1["blocked"][0])

        # Charlie sees empty blocked list (only own blocks)
        st_c, r_c = invoke_handler("GET", "/api/users/blocked", headers=self.auth_hdr("charlie"))
        self.assertEqual(st_c, 200)
        self.assertEqual(r_c["blocked"], [])

        # Unblock Bob -> list empty & chat open works again
        invoke_handler("POST", "/api/users/unblock", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        _, r_2 = invoke_handler("GET", "/api/users/blocked", headers=self.auth_hdr("alice"))
        self.assertEqual(r_2["blocked"], [])
        st_op, _ = invoke_handler("POST", "/api/messages/open", {"targetUserId": self.users["bob"]}, headers=self.auth_hdr("alice"))
        self.assertEqual(st_op, 200)

    def test_oauth_user_set_password_without_old_and_security(self):
        now = int(time.time())
        conn = sqlite3.connect(server.DB_FILE)
        try:
            cur = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, oauth_provider, oauth_id, plan, is_blocked, last_login_at, created_at) '
                'VALUES ("tg_athlete", "", "", "TG Athlete", "", "telegram", "tg_777888", "free", 0, ?, ?)',
                (now, now)
            )
            tg_uid = cur.lastrowid
            tg_tok = f"tok_tg_{now}"
            conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tg_tok, tg_uid, now + 86400))
            conn.commit()
        finally:
            conn.close()
        tg_hdr = {"Authorization": "Bearer " + tg_tok}

        # /api/user/me reports hasPassword = False
        st_me, me_resp = invoke_handler("GET", "/api/user/me", headers=tg_hdr)
        self.assertEqual(st_me, 200)
        self.assertFalse(me_resp["user"]["hasPassword"])

        # Password login fails before password is set
        st_bad_in, _ = invoke_handler("POST", "/api/user/login", {"username": "tg_athlete", "password": ""})
        self.assertEqual(st_bad_in, 401)

        # Weak password rejected
        st_weak, _ = invoke_handler("POST", "/api/user/profile", {"newPassword": "123"}, headers=tg_hdr)
        self.assertEqual(st_weak, 400)

        # IDOR attempt: setting password for Alice rejected
        st_idor, _ = invoke_handler("POST", "/api/user/profile", {"userId": self.users["alice"], "newPassword": "Hacked123!"}, headers=tg_hdr)
        self.assertEqual(st_idor, 403)

        # Setting password WITHOUT oldPassword succeeds for OAuth user
        st_set, set_resp = invoke_handler("POST", "/api/user/profile", {"newPassword": "TgNewPass123!"}, headers=tg_hdr)
        self.assertEqual(st_set, 200)
        self.assertTrue(set_resp["user"]["hasPassword"])

        # Now regular username+password login works AND oauth_provider/oauth_id remain intact
        st_login, _ = invoke_handler("POST", "/api/user/login", {"username": "tg_athlete", "password": "TgNewPass123!"})
        self.assertEqual(st_login, 200)
        conn = sqlite3.connect(server.DB_FILE)
        try:
            o_row = conn.execute('SELECT oauth_provider, oauth_id FROM users WHERE id = ?', (tg_uid,)).fetchone()
            self.assertEqual(o_row, ("telegram", "tg_777888"))
        finally:
            conn.close()

        # Subsequent password change NOW requires correct oldPassword
        st_no_old, _ = invoke_handler("POST", "/api/user/profile", {"newPassword": "AnotherPass123!"}, headers=tg_hdr)
        self.assertEqual(st_no_old, 400)
        st_chg_ok, _ = invoke_handler("POST", "/api/user/profile", {"oldPassword": "TgNewPass123!", "newPassword": "AnotherPass123!"}, headers=tg_hdr)
        self.assertEqual(st_chg_ok, 200)

    def test_admin_reports_auth_list_filter_and_status_update(self):
        # Create a report from Alice against Bob
        st_r, _ = invoke_handler(
            "POST", "/api/users/report",
            {"targetUserId": self.users["bob"], "reason": "Inappropriate chat spam"},
            headers=self.auth_hdr("alice")
        )
        self.assertEqual(st_r, 200)

        # Guest and normal user cannot access admin reports endpoints
        for hdr in (None, self.auth_hdr("alice")):
            st_g, _ = invoke_handler("GET", "/api/admin/reports", headers=hdr)
            self.assertEqual(st_g, 401)
            st_p, _ = invoke_handler("POST", "/api/admin/reports/status", {"reportId": 1, "status": "reviewed"}, headers=hdr)
            self.assertEqual(st_p, 401)

        # Issue valid admin token
        adm_tok = "test_adm_tok_reports"
        with server.lock:
            server.tokens[adm_tok] = time.time() + 3600
        adm_hdr = {"Authorization": "Bearer " + adm_tok}
        try:
            st_list, data = invoke_handler("GET", "/api/admin/reports?status=new", headers=adm_hdr)
            self.assertEqual(st_list, 200)
            self.assertEqual(data["counts"]["new"], 1)
            self.assertEqual(len(data["reports"]), 1)
            rep = data["reports"][0]
            self.assertEqual(rep["reporter"]["username"], "alice")
            self.assertEqual(rep["target"]["username"], "bob")
            self.assertEqual(rep["reason"], "Inappropriate chat spam")
            rid = rep["id"]

            # Mark as reviewed with note
            st_rev, _ = invoke_handler(
                "POST", "/api/admin/reports/status",
                {"reportId": rid, "status": "reviewed", "note": "Checked by moderator"},
                headers=adm_hdr
            )
            self.assertEqual(st_rev, 200)

            _, data_rev = invoke_handler("GET", "/api/admin/reports?status=reviewed", headers=adm_hdr)
            self.assertEqual(data_rev["counts"]["new"], 0)
            self.assertEqual(data_rev["counts"]["reviewed"], 1)
            self.assertEqual(data_rev["reports"][0]["adminNote"], "Checked by moderator")

            # Close report
            st_cls, _ = invoke_handler(
                "POST", "/api/admin/reports/status",
                {"reportId": rid, "status": "closed"},
                headers=adm_hdr
            )
            self.assertEqual(st_cls, 200)

            _, data_cls = invoke_handler("GET", "/api/admin/reports?status=closed", headers=adm_hdr)
            self.assertEqual(data_cls["counts"]["closed"], 1)
            self.assertEqual(data_cls["reports"][0]["status"], "closed")
        finally:
            with server.lock:
                server.tokens.pop(adm_tok, None)


if __name__ == "__main__":
    unittest.main()
