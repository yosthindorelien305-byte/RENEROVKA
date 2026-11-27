"""Tests for Stage 2 Unified Design System & Responsive Shell (Main Site + Admin Panel):
- Verifies shared tokens.css, ui-kit.css, ui_components.js exist and are wired into index.html, admin.html, and sw.js
- Verifies responsive Desktop/Tablet/Mobile breakpoints across style.css and admin.css
- Verifies existing 11 admin tabs remain intact alongside the new AI Growth hub & responsive drawer
- Runs Node.js functional assertions against site/ui_components.js (XSS escaping, status badges, source+timestamp KPI cards)
"""
import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestResponsiveDesignSystem(unittest.TestCase):
    def test_shared_design_system_files_and_wiring(self):
        for rel in ("tokens.css", "ui-kit.css", "ui_components.js"):
            self.assertTrue(os.path.isfile(os.path.join(SITE, rel)), msg=f"Missing shared file site/{rel}")

        with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        with open(os.path.join(SITE, "admin.html"), encoding="utf-8") as f:
            admin_html = f.read()
        with open(os.path.join(SITE, "sw.js"), encoding="utf-8") as f:
            sw_js = f.read()

        for html_src, name in ((index_html, "index.html"), (admin_html, "admin.html")):
            for token in ("tokens.css?v=67", "ui-kit.css?v=67", "style.css?v=67", "ui_components.js?v=67"):
                self.assertIn(token, html_src, msg=f"{token} missing in {name}")

        self.assertIn("admin.css?v=67", admin_html)
        self.assertIn("admin.js?v=67", admin_html)
        self.assertIn("app.js?v=67", index_html)
        self.assertIn("G-XSBKDCY4CS", index_html)
        self.assertIn('id="nav"', index_html)

        self.assertIn("flexa-shell-v67", sw_js)
        for asset in ("./tokens.css", "./ui-kit.css", "./ui_components.js"):
            self.assertIn(asset, sw_js)

    def test_responsive_breakpoints_in_site_and_admin_css(self):
        with open(os.path.join(SITE, "tokens.css"), encoding="utf-8") as f:
            tokens_css = f.read()
        with open(os.path.join(SITE, "ui-kit.css"), encoding="utf-8") as f:
            uikit_css = f.read()
        with open(os.path.join(SITE, "style.css"), encoding="utf-8") as f:
            style_css = f.read()
        with open(os.path.join(SITE, "admin.css"), encoding="utf-8") as f:
            admin_css = f.read()

        for var_name in ("--ac:", "--bg:", "--card:", "--green:", "--rf-sidebar-w:", "--rf-rail-w:", "--rf-adm-sidebar-w:"):
            self.assertIn(var_name, tokens_css)

        for cls in (".rf-card", ".rf-btn-primary", ".rf-pill", ".rf-status-approved", ".rf-source-meta", ".rf-grid-4"):
            self.assertIn(cls, uikit_css)

        # Main site responsive breakpoints (Mobile / Tablet rail / Desktop sidebar)
        self.assertIn("@media (max-width: 639px)", style_css)
        self.assertIn("@media (min-width: 640px)", style_css)
        self.assertIn("@media (min-width: 1024px)", style_css)
        self.assertIn("var(--rf-rail-w, 76px)", style_css)
        self.assertIn("var(--rf-sidebar-w, 236px)", style_css)

        # Admin Obsidian shell + responsive drawer
        self.assertIn(".adm-shell", admin_css)
        self.assertIn(".adm-sidebar", admin_css)
        self.assertIn("@media (max-width: 1023px)", admin_css)
        self.assertIn("@media (max-width: 639px)", admin_css)
        self.assertNotIn("#172016", admin_css)

    def test_admin_preserves_all_existing_tabs_and_embeds_growth_hub(self):
        with open(os.path.join(SITE, "admin.js"), encoding="utf-8") as f:
            admin_js = f.read()

        for tab_id in ("athlete", "ui", "programs", "workouts", "exercises", "users", "reports", "telegram", "payments", "ai", "settings"):
            self.assertIn(f"['{tab_id}'", admin_js)
        self.assertIn("data-t=\"growth\"", admin_js)
        self.assertIn("function tabGrowth(el)", admin_js)
        self.assertIn("function confirmDangerous(", admin_js)
        self.assertIn("renderAuditLogList", admin_js)
        self.assertIn("adm-menu-btn", admin_js)
        self.assertIn("adm-sidebar", admin_js)
        self.assertIn("RizzaFit AI Growth", admin_js)
        self.assertIn("AI Coach", admin_js)
        # Ensure dangerous admin actions use confirmDangerous modal wrapper
        for marker in ("act === 'block'", "act === 'unblock'", "#ai-clr", "#yk-clr-key", "#p-reset", "#w-del", "#npb"):
            self.assertIn(marker, admin_js)
        self.assertGreaterEqual(admin_js.count("confirmDangerous("), 8)

    def test_ui_components_js_in_node(self):
        script = r"""
        const assert = require('assert');
        const ui = require('./site/ui_components.js');

        const safe = ui.esc('<script>alert("xss") & \'q\'</script>');
        assert(!safe.includes('<') && !safe.includes('>'));
        assert(safe.includes('&lt;script&gt;') && safe.includes('&amp;') && safe.includes('&#39;'));

        const badge = ui.renderStatusBadge('pending_approval');
        assert(badge.includes('rf-status-pending'));
        assert(badge.includes('На одобрении'));

        const approved = ui.renderStatusBadge('approved');
        assert(approved.includes('rf-status-approved'));

        const meta = ui.renderSourceMeta('flexa.db (RO)', '25.11.2026 21:45');
        assert(meta.includes('flexa.db (RO)'));
        assert(meta.includes('25.11.2026 21:45'));

        const kpi = ui.renderKpiCard({
          label: 'SEO Оценка',
          value: '78 / 100',
          delta: '+6',
          source: 'SEO Auditor <bad>',
          updatedAt: '25.11.2026 21:45'
        });
        assert(kpi.includes('SEO Оценка'));
        assert(kpi.includes('78 / 100'));
        assert(kpi.includes('&lt;bad&gt;'));
        assert(!kpi.includes('<bad>'));

        const auditHtml = ui.renderAuditLogList([
          {
            action: '<script>alert(1)</script>SEO update',
            actor: 'admin',
            timestamp: '25.11.2026 22:00',
            status: 'approved',
            details: 'Safe log details <b>tag</b>'
          }
        ], { title: 'Журнал аудита' });
        assert(auditHtml.includes('data-readonly="true"'));
        assert(auditHtml.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
        assert(!auditHtml.includes('<script>'));
        assert(!auditHtml.includes('<input'));
        assert(!auditHtml.includes('<textarea'));
        assert(!auditHtml.includes('contenteditable'));

        const emptyAudit = ui.renderAuditLogList([]);
        assert(emptyAudit.includes('data-readonly="true"'));
        assert(emptyAudit.includes('Записей в журнале пока нет'));
        console.log('NODE_UI_OK');
        """
        res = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)
        self.assertIn("NODE_UI_OK", res.stdout)
