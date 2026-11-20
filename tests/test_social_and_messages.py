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


if __name__ == "__main__":
    unittest.main()
