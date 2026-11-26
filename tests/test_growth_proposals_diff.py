"""Tests for AI Growth Approval Engine, Diff Engine, targetObject hardening, and CSRF (PR 4.2)."""

import hashlib
import os
import unittest

import server
from growth import diff_engine
from tests.test_growth_tasks import invoke_http
from tests.test_isolation import PROD_DB_FILE, IsolatedServerTestCase


class TestGrowthProposalsAndDiff(IsolatedServerTestCase):
    def setUp(self):
        super().setUp()
        self.admin_pw = "PropAdm_2026!"
        server.set_pw(self.admin_pw)
        code, body = invoke_http("POST", "/api/login", {"password": self.admin_pw})
        self.assertEqual(code, 200)
        self.admin_hdrs = {
            "Authorization": f"Bearer {body['token']}",
            "Host": "127.0.0.1:8080",
            "Origin": "http://127.0.0.1:8080",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def test_diff_engine_handles_added_removed_lines_and_inert_payloads(self):
        orig = "Старый заголовок\nВторая строка\nУдаляемая строка"
        prop = "<script>alert(1)</script>; DROP TABLE users; $(rm -rf /)\nВторая строка\nНовая строка"
        diff = diff_engine.compute_text_diff(orig, prop, field_name="title", target_object="site/index.html")
        self.assertTrue(diff["hasChanges"])
        self.assertIn("<script>alert(1)</script>; DROP TABLE users; $(rm -rf /)", diff["addedLines"])
        self.assertIn("Старый заголовок", diff["removedLines"])
        self.assertIn("Удаляемая строка", diff["removedLines"])
        self.assertEqual(diff["stats"]["unchangedCount"], 1)
        self.assertIsNotNone(diff["seoFieldGuidance"])
        self.assertIn("current:site/index.html", diff["unifiedDiff"])

    def test_target_object_rejects_absolute_traversal_urls_and_secrets(self):
        forbidden_targets = (
            "/etc/passwd",
            "/index.html",
            "//etc/passwd",
            "C:/Windows",
            "C:\\Windows\\System32",
            "../secret",
            "site/../../secret",
            "site/%2e%2e/secret",
            "site/%2e%2e%2fsecret",
            "site/%252e%252e/secret",
            "https://evil.com/index.html",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "server_data/ai.json",
            "site/server_data/admin.json",
            "site/fitify/index.html",
            "fitify/muscles.html",
            "server.py",
            "growth/db.py",
            "site/index.html\x00",
            "~root/.ssh/id_rsa",
            "site/index.html#bad?x=1",
        )
        for bad_target in forbidden_targets:
            code, body = invoke_http(
                "POST",
                "/api/admin/growth/proposals",
                {
                    "targetObject": bad_target,
                    "fieldName": "content",
                    "currentValue": "old",
                    "proposedValue": "new",
                    "reason": "security check",
                },
                headers=self.admin_hdrs,
            )
            self.assertEqual(code, 400, msg=f"targetObject must be rejected with 400: {bad_target!r} -> {body}")

        for good_target in ("site/index.html", "site/index.html#title", "site/programs.html", "site/robots.txt"):
            code_ok, res_ok = invoke_http(
                "POST",
                "/api/admin/growth/proposals",
                {
                    "targetObject": good_target,
                    "fieldName": "title",
                    "currentValue": "Old",
                    "proposedValue": "New",
                    "reason": "valid relative identifier",
                },
                headers=self.admin_hdrs,
            )
            self.assertEqual(code_ok, 201, msg=f"Valid relative targetObject rejected: {good_target!r} -> {res_ok}")

    def test_proposal_lifecycle_csrf_double_approve_guard_and_no_site_or_prod_mutation(self):
        index_path = os.path.join(server.SITE, "index.html")
        index_hash_before = hashlib.sha256(open(index_path, "rb").read()).hexdigest()
        prod_db_before = (
            hashlib.sha256(open(PROD_DB_FILE, "rb").read()).hexdigest()
            if os.path.exists(PROD_DB_FILE)
            else None
        )

        # Create linked task in pending_approval
        c_t, b_t = invoke_http(
            "POST",
            "/api/admin/growth/tasks",
            {"title": "Update landing title", "category": "SEO", "status": "pending_approval"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_t, 201)
        tid = b_t["task"]["id"]

        # Reject identical current/proposed values
        c_same, _ = invoke_http(
            "POST",
            "/api/admin/growth/proposals",
            {
                "targetObject": "site/index.html",
                "fieldName": "title",
                "currentValue": "Same",
                "proposedValue": "Same",
                "reason": "no diff",
            },
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_same, 400)

        # Create valid proposal
        c_cr, b_cr = invoke_http(
            "POST",
            "/api/admin/growth/proposals",
            {
                "taskId": tid,
                "targetObject": "site/index.html#title",
                "fieldName": "title",
                "currentValue": "RizzaFit — тренировки",
                "proposedValue": "RizzaFit — программы тренировок и прогресс",
                "reason": "Уточнить ключевые слова в title",
            },
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_cr, 201)
        pid = b_cr["proposal"]["id"]
        self.assertEqual(b_cr["proposal"]["status"], "pending")
        self.assertTrue(b_cr["proposal"]["autoApplyDisabled"])

        # Diff endpoint & detail endpoint
        c_diff, b_diff = invoke_http("GET", f"/api/admin/growth/proposals/{pid}/diff", headers=self.admin_hdrs)
        self.assertEqual(c_diff, 200)
        self.assertTrue(b_diff["diff"]["hasChanges"])
        self.assertEqual(b_diff["diff"]["addedLines"], ["RizzaFit — программы тренировок и прогресс"])

        # CSRF checks across approve & reject
        for ep in (f"/api/admin/growth/proposals/{pid}/approve", f"/api/admin/growth/proposals/{pid}/reject"):
            # Missing both Origin & Referer -> 403
            h_no_org = {"Authorization": self.admin_hdrs["Authorization"], "Host": "127.0.0.1:8080", "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"}
            self.assertEqual(invoke_http("POST", ep, {}, headers=h_no_org)[0], 403)
            # Content-Type: application/json alone without X-Requested-With -> 403
            h_json_only = {"Authorization": self.admin_hdrs["Authorization"], "Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080", "Content-Type": "application/json"}
            self.assertEqual(invoke_http("POST", ep, {}, headers=h_json_only)[0], 403)
            # Cross-origin -> 403
            self.assertEqual(invoke_http("POST", ep, {}, headers={**self.admin_hdrs, "Origin": "https://attacker.example"})[0], 403)
            # Port mismatch -> 403
            self.assertEqual(invoke_http("POST", ep, {}, headers={**self.admin_hdrs, "Origin": "http://127.0.0.1:9999"})[0], 403)

        # Approve proposal -> status becomes approved, linked task becomes approved
        c_app, b_app = invoke_http(
            "POST",
            f"/api/admin/growth/proposals/{pid}/approve",
            {"note": "Утверждено вручную"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_app, 200)
        self.assertEqual(b_app["proposal"]["status"], "approved")

        # Double-approve or reject after approve MUST fail with 409 Conflict
        self.assertEqual(invoke_http("POST", f"/api/admin/growth/proposals/{pid}/approve", {}, headers=self.admin_hdrs)[0], 409)
        self.assertEqual(invoke_http("POST", f"/api/admin/growth/proposals/{pid}/reject", {}, headers=self.admin_hdrs)[0], 409)

        # Verify reject workflow on a second proposal
        c_cr2, b_cr2 = invoke_http(
            "POST",
            "/api/admin/growth/proposals",
            {
                "targetObject": "site/ai-coach.html",
                "fieldName": "meta_description",
                "currentValue": "",
                "proposedValue": "Новое мета-описание страницы AI-тренера RizzaFit длиной более 50 символов.",
                "reason": "Добавить description",
            },
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_cr2, 201)
        pid2 = b_cr2["proposal"]["id"]
        c_rej, b_rej = invoke_http(
            "POST",
            f"/api/admin/growth/proposals/{pid2}/reject",
            {"note": "Нужно переформулировать"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_rej, 200)
        self.assertEqual(b_rej["proposal"]["status"], "rejected")

        # Audit log contains proposal.create, proposal.approve, proposal.reject
        c_aud, b_aud = invoke_http("GET", "/api/admin/growth/audit?module=proposals&limit=20", headers=self.admin_hdrs)
        self.assertEqual(c_aud, 200)
        actions = [e["action"] for e in b_aud["entries"]]
        self.assertIn("proposal.create", actions)
        self.assertIn("proposal.approve", actions)
        self.assertIn("proposal.reject", actions)

        # Approval NEVER modifies site/index.html or production flexa.db
        self.assertEqual(hashlib.sha256(open(index_path, "rb").read()).hexdigest(), index_hash_before)
        if prod_db_before is not None:
            self.assertEqual(hashlib.sha256(open(PROD_DB_FILE, "rb").read()).hexdigest(), prod_db_before)


if __name__ == "__main__":
    unittest.main()
