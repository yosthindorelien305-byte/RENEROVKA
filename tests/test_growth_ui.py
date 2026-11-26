"""UI & Node.js tests for site/admin_growth.js integration (PR 4.1)."""

import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class TestGrowthFrontendUI(unittest.TestCase):
    def test_js_syntax_and_admin_wiring(self):
        for rel in ("admin_growth.js", "admin.js", "ui_components.js"):
            res = subprocess.run(["node", "--check", os.path.join(SITE, rel)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)

        with open(os.path.join(SITE, "admin.html"), encoding="utf-8") as f:
            admin_html = f.read()
        self.assertIn('<script src="admin_growth.js?v=66"></script>', admin_html)

        with open(os.path.join(SITE, "admin.js"), encoding="utf-8") as f:
            admin_js = f.read()
        self.assertIn("window.RizzaGrowth", admin_js)

    def test_admin_growth_renders_dashboard_analytics_and_audit_safely(self):
        script = r"""
        const assert = require('assert');
        const growth = require('./site/admin_growth.js');

        const dashHtml = growth.renderDashboardHtml({
          generatedAt: '2026-11-26T12:00:00Z',
          systemStatus: { dbHealth: 'ok', freeAccessMode: true, aiGrowthLlm: 'disabled_pr41', auditAppendOnly: true, auditTotal: 3 },
          kpis: [
            { id: 'users_total', label: 'Пользователи', value: '42', delta: '+5 за 30д', source: 'flexa.db:users', updatedAt: '2026-11-26T12:00:00Z', status: 'ok' }
          ],
          attentionItems: [
            { id: 'a1', severity: 'high', title: '<script>xss</script>Жалобы', details: 'Check <img onerror=1>', source: 'flexa.db:user_reports' }
          ],
          recentAudit: [
            { id: 1, action: 'admin.login', module: 'auth', actor: 'admin', actorIp: '127.0.0.1', timestamp: '2026-11-26 12:00 UTC', status: 'ok', detailsText: 'IP: 127.0.0.1' }
          ],
          modules: [{ id: 'dashboard', title: 'Dashboard', status: 'done', statusLabel: 'PR 4.1 активен' }]
        });
        assert(dashHtml.includes('Пользователи'));
        assert(dashHtml.includes('flexa.db:users'));
        assert(dashHtml.includes('2026-11-26T12:00:00Z'));
        assert(dashHtml.includes('&lt;script&gt;xss&lt;/script&gt;'));
        assert(!dashHtml.includes('<script>'));
        assert(dashHtml.includes('Серверный append-only журнал'));

        const anHtml = growth.renderAnalyticsHtml({
          periodDays: 30,
          generatedAt: '2026-11-26T12:00:00Z',
          dataQuality: { dbHealth: 'ok' },
          registrations: { status: 'ok', source: 'flexa.db:users', updatedAt: '2026-11-26T12:00:00Z', totalUsers: 4, newInPeriod: 3, byAuthMethod: { telegram: 1, password: 3 }, dailySeries: [{ date: '2026-11-26', count: 3 }] },
          engagement: {
            lastLoginActivity: { status: 'ok', isProxy: true, metricType: 'last_login_proxy', source: 'flexa.db:users.last_login_at', updatedAt: '2026-11-26T12:00:00Z', last24h: 1, last7d: 2, last30d: 3 },
            workoutActivity: { status: 'ok', isProxy: false, metricType: 'workout_history', source: 'flexa.db:user_state.hist', updatedAt: '2026-11-26T12:00:00Z', dau: 1, wau: 2, mau: 2, workoutsInPeriod: 3, workoutsTotal: 3, medianDurationSec: 1200 }
          },
          retention: {
            workoutRetention: { status: 'insufficient_data', isProxy: false, source: 'flexa.db', updatedAt: '2026-11-26T12:00:00Z', d1: { windowDefinition: '[+1д, +2д)', cohortSize: 0, excludedIncompleteCount: 2, retainedCount: 0, ratePct: null, status: 'insufficient_data' }, d7: {}, d30: {} },
            lastLoginReturnProxy: { status: 'ok', isProxy: true, source: 'flexa.db', updatedAt: '2026-11-26T12:00:00Z', d1: { windowDefinition: 'last_login_at >= +1д', cohortSize: 2, excludedIncompleteCount: 1, retainedCount: 1, ratePct: 50.0, status: 'ok' }, d7: {}, d30: {} }
          },
          activation: { status: 'ok', firstWorkoutUsers: 2, firstWorkoutRatePct: 50.0, profileCompletedUsers: 2, profileCompletedRatePct: 50.0, programStartedUsers: 1, programStartedRatePct: 25.0 },
          workouts: { status: 'ok', completedInPeriod: 3, completedTotal: 3, avgExercisesPerWorkout: 4.5, dailySeries: [{ date: '2026-11-26', count: 3 }] },
          popularCatalog: { status: 'ok', topPrograms: [{ id: '1', title: '50 Подтягиваний', usersCount: 1, completedDaysTotal: 1 }], topWorkouts: [] },
          rpeDistribution: { status: 'ok', period: { easy: { count: 1 }, good: { count: 1 }, hard: { count: 1 }, unrated: { count: 0 } } },
          userProfiles: { status: 'ok', goals: { strength: 1 }, levels: { beginner: 1 } },
          aiCoach: { status: 'ok', windowDays: 14, activeSessions14d: 2, userSessions14d: 1, guestSessions14d: 1, totalMessages14d: 3, avgMessagesPerSession: 1.5, adoptionRatePct: 25.0 },
          featureUsage: { status: 'ok', source: 'flexa.db:growth_feature_daily', updatedAt: '2026-11-26T12:00:00Z', piiStored: false, totalInPeriod: 7, totalAllTime: 7, byEvent: [{ key: 'coach_open', label: 'Открытие AI Coach', countPeriod: 7, countAllTime: 7 }], dailySeries: [{ date: '2026-11-26', count: 7 }] },
          monetization: { status: 'ok', freeAccessMode: true, realProUsersActive: 1, paymentsInPeriodByStatus: { paid: 1, pending: 0 }, paidRevenueInPeriod: 1990 },
          moderation: { status: 'ok', reportsByStatus: { new: 1, reviewed: 1, closed: 0 }, avgReviewTimeHours: 2.0, acceptedFriendships: 1, activeBlocks: 1 },
          externalSources: { status: 'unavailable', updatedAt: '2026-11-26T12:00:00Z', items: [{ id: 'ga4', label: 'Google Analytics 4', status: 'unavailable', source: 'GA4', reason: 'Not connected' }] }
        });
        assert(anHtml.includes('Последний вход в аккаунт (прокси: 24ч / 7д / 30д)'));
        assert(!anHtml.includes('Auth DAU/WAU/MAU'));
        assert(anHtml.includes('Фактические тренировки (Workout DAU/WAU/MAU)'));
        assert(anHtml.includes('Возврат по последнему входу (прокси)'));
        assert(anHtml.includes('исключено неполн.: 2'));
        assert(anHtml.includes('Недостаточно данных'));
        assert(anHtml.includes('unavailable'));
        assert(anHtml.includes('Использование функций (агрегировано, без PII)'));
        assert(anHtml.includes('Открытие AI Coach'));

        const auditHtml = growth.renderAuditHtml({
          appendOnlyEnforced: true,
          source: 'flexa.db:growth_audit_log',
          updatedAt: '2026-11-26T12:00:00Z',
          entries: [{ id: 1, action: 'admin.login', module: 'auth', actor: 'admin', actorIp: '127.0.0.1', timestamp: '2026-11-26 12:00 UTC', status: 'ok', detailsText: 'IP: 127.0.0.1' }],
          total: 1,
          limit: 25,
          offset: 0,
          hasMore: false
        });
        assert(auditHtml.includes('data-readonly="true"'));
        assert(auditHtml.includes('Triggers ON'));
        assert(auditHtml.includes('BEFORE UPDATE'));
        assert(auditHtml.includes('BEFORE DELETE'));

        // PR 4.2 Views: Tasks (inert internal/external URL rendering), SEO Audit, Proposals, Diff Review + XSS protection
        const tasksHtml = growth.renderTasksHtml({
          total: 2,
          source: 'flexa.db:growth_tasks',
          updatedAt: '2026-11-26T12:00:00Z',
          tasks: [
            { id: 1, title: '<script>xss</script>Fix H1', category: 'SEO', priority: 'high', status: 'open', targetUrl: '/', targetUrlType: 'internal', updatedAtIso: '2026-11-26T12:00:00Z' },
            { id: 2, title: 'External Ref', category: 'SEO', priority: 'low', status: 'open', targetUrl: 'https://example.org/<xss>', targetUrlType: 'external', updatedAtIso: '2026-11-26T12:00:00Z' }
          ]
        }, {
          task: { id: 2, title: 'External Ref', description: 'Desc', category: 'SEO', priority: 'low', status: 'open', targetUrl: 'https://example.org/<xss>', targetUrlType: 'external', allowedTransitions: ['in_progress'], createdAtIso: '2026-11-26T12:00:00Z', updatedAtIso: '2026-11-26T12:00:00Z' },
          history: [{ field: 'created', oldValue: '', newValue: 'open/low/SEO', actor: 'admin', createdAtIso: '2026-11-26T12:00:00Z' }],
          proposals: []
        });
        assert(tasksHtml.includes('&lt;script&gt;xss&lt;/script&gt;Fix H1'));
        assert(!tasksHtml.includes('<script>'));
        assert(!tasksHtml.includes('<a '));
        assert(tasksHtml.includes('внешний, без перехода'));
        assert(tasksHtml.includes('внутренний'));
        assert(tasksHtml.includes('&lt;xss&gt;'));
        assert(tasksHtml.includes('Список задач (2)'));

        const seoHtml = growth.renderSeoAuditHtml({
          hasRun: true,
          pagesChecked: 1,
          checkedAtIso: '2026-11-26T12:00:00Z',
          summary: { critical: 0, high: 1, medium: 0, low: 0, info: 0 },
          pages: [{ pageUrl: '/', role: 'public', title: 'RizzaFit', titleLength: 8, h1Count: 0, inSitemap: true, indexable: true }],
          issues: [{ pageUrl: '/', issueType: 'missing_h1', severity: 'high', description: 'No H1', recommendation: 'Add H1' }],
          unknownChecks: [{ check: 'search_console_indexing', status: 'unknown', reason: 'Not connected' }]
        });
        assert(seoHtml.includes('missing_h1'));
        assert(seoHtml.includes('search_console_indexing'));
        assert(seoHtml.includes('unknown'));

        const adminGrowthSrc = require('fs').readFileSync('./site/admin_growth.js', 'utf8');
        assert(!adminGrowthSrc.includes('site/fitify/'));

        const propHtml = growth.renderProposalsHtml({
          total: 1,
          proposals: [{ id: 5, targetObject: 'site/index.html', fieldName: 'title', status: 'pending', reason: 'SEO', createdAtIso: '2026-11-26T12:00:00Z' }]
        }, {
          proposal: { id: 5, targetObject: 'site/index.html', fieldName: 'title', status: 'pending', reason: 'SEO' },
          diff: { targetObject: 'site/index.html', fieldName: 'title', stats: { addedCount: 1, removedCount: 1, originalLength: 3, proposedLength: 3 }, sideBySideLines: [{ type: 'replace', oldLineNum: 1, newLineNum: 1, oldText: 'Old', newText: '<b>New</b>' }], unifiedDiff: '-Old\n+<b>New</b>' },
          history: []
        });
        assert(propHtml.includes('Предложение #5'));
        assert(propHtml.includes('&lt;b&gt;New&lt;/b&gt;'));
        assert(propHtml.includes('data-prop-approve="5"'));

        const diffHtml = growth.renderDiffHtml({ proposals: [{ id: 5, targetObject: '/index.html', fieldName: 'title', status: 'pending' }] }, {
          proposalId: 5,
          status: 'pending',
          diff: { targetObject: '/index.html', fieldName: 'title', stats: { addedCount: 1, removedCount: 1, originalLength: 3, proposedLength: 3 }, sideBySideLines: [{ type: 'insert', oldLineNum: null, newLineNum: 1, oldText: '', newText: 'New Line' }], unifiedDiff: '+New Line' }
        });
        assert(diffHtml.includes('Diff Review'));
        assert(diffHtml.includes('New Line'));
        console.log('GROWTH_UI_OK');
        """
        res = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)
        self.assertIn("GROWTH_UI_OK", res.stdout)


if __name__ == "__main__":
    unittest.main()
