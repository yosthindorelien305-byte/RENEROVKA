"""Tests for AI Growth Approval Engine, Diff Engine, re-apply protection, and safety (PR 4.2)."""

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
            "Origin": "http://127.0.0.1:8080",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def test_diff_engine_handles_added_removed_lines_and_inert_payloads(self):
        orig = "Старый заголовок\nВторая строка\nУдаляемая строка"
        prop = "<script>alert(1)</script>; DROP TABLE users; $(rm -rf /)\nВторая строка\nНовая строка"
        diff = diff_engine.compute_text_diff(orig, prop, field_name="title", target_object="/index.html")
        self.assertTrue(diff["hasChanges"])
        self.assertIn("<script>alert(1)</script>; DROP TABLE users; $(rm -rf /)", diff["addedLines"])
        self.assertIn("Старый заголовок", diff["removedLines"])
        self.assertIn("Удаляемая строка", diff["removedLines"])
        self.assertEqual(diff["stats"]["unchangedCount"], 1)
        self.assertIsNotNone(diff["seoFieldGuidance"])
        self.assertIn("current:/index.html", diff["unifiedDiff"])

    def test_proposal_lifecycle_double_approve_guard_and_no_site_or_prod_mutation(self):
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

        # Validation rejects path traversal / server.py / identical text / bad CSRF
        c_trav, _ = invoke_http(
            "POST",
            "/api/admin/growth/proposals",
            {
                "targetObject": "../server.py",
                "fieldName": "content",
                "currentValue": "a",
                "proposedValue": "b",
                "reason": "invalid path",
            },
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_trav, 400)

        c_same, _ = invoke_http(
            "POST",
            "/api/admin/growth/proposals",
            {
                "targetObject": "/index.html",
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
                "targetObject": "/index.html",
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

        # CSRF protection on approve
        c_csrf, _ = invoke_http(
            "POST",
            f"/api/admin/growth/proposals/{pid}/approve",
            {},
            headers={**self.admin_hdrs, "Origin": "https://attacker.example"},
        )
        self.assertEqual(c_csrf, 403)

        # Approve proposal -> status becomes approved, linked task becomes approved
        c_app, b_app = invoke_http(
            "POST",
            f"/api/admin/growth/proposals/{pid}/approve",
            {"note": "Утверждено вручную"},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_app, 200)
        self.assertEqual(b_app["proposal"]["status"], "approved")

        # Double-approve or reject after approve MUST fail with 409 Conflict (re-apply guard)
        c_reapp, _ = invoke_http(
            "POST",
            f"/api/admin/growth/proposals/{pid}/approve",
            {},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_reapp, 409)
        c_rej_after, _ = invoke_http(
            "POST",
            f"/api/admin/growth/proposals/{pid}/reject",
            {},
            headers=self.admin_hdrs,
        )
        self.assertEqual(c_rej_after, 409)

        # Verify reject workflow on a second proposal
        c_cr2, b_cr2 = invoke_http(
            "POST",
            "/api/admin/growth/proposals",
            {
                "targetObject": "/fitify/",
                "fieldName": "meta_description",
                "currentValue": "",
                "proposedValue": "Новое мета-описание Fitify для поисковых систем длиной более 50 символов.",
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
