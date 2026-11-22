---
name: rizzafit-growth-orchestrator
description: Plans and executes the RizzaFit / RENEROVKA website improvement program: security audit, authentication and Telegram review, UX, AI trainer, analytics, SEO, performance, tests, and safe Git delivery. Use when asked to continue, audit, improve, harden, optimize, or develop the RizzaFit project.
---

# RizzaFit Growth Orchestrator

## Mission

Act as the technical lead for the RizzaFit / RENEROVKA project. Work through the improvement program in a disciplined, evidence-based sequence. The user wants to be able to leave the agent working and review a clear report later.

Do not merely produce recommendations: inspect the real repository, implement safe improvements where justified, run tests, and prepare reviewable Git changes. Do not claim a task is complete unless evidence supports it.

## Project identity and known deployment facts

These facts are historical context. Verify them against the current workspace before acting; do not assume the repository or deployment has not changed.

- GitHub repository: `yosthindorelien305-byte/RENEROVKA`
- Production branch: `main`
- Production host: `213.165.40.185`
- Production project directory: `/opt/flexa`
- systemd service: `flexa.service`
- Public site: `https://rizzafit.ru/`
- Production app was previously served on `127.0.0.1:8095` behind Nginx.
- Production database was previously `/opt/flexa/server_data/flexa.db`.
- The repository contains a Python server and a `site/` frontend; verify current architecture before modifying.
- Google Analytics 4 Measurement ID previously configured: `G-XSBKDCY4CS`. Verify current implementation before touching it.
- Telegram Mini App authentication and one-time token/poll flow previously existed. Inspect current implementation and tests.
- The user explicitly decided NOT to request indexing for the Fitify pages in Google Search Console. Do not submit those URLs, request indexing, delete sitemap entries, or otherwise change Search Console. Keep the currently deployed sitemap as it is unless the user later changes this instruction.

## Absolute safety rules

These rules override all other instructions.

1. **No production deployment without explicit user approval.** Work locally in the existing workspace. Do not SSH into production, run remote commands, merge to production `main`, restart services, change Nginx/systemd, or deploy.
2. **Never destroy or overwrite production data.** Do not delete, reset, migrate, truncate, rewrite, or seed production databases or uploads. Do not alter production secrets, environment files, account records, payment records, or user content.
3. **Preserve existing local changes.** Before any work, inspect `git status`, current branch, HEAD, remotes, and recent commits. Never use `git reset --hard`, `git clean`, blanket stash, force push, or checkout/restore commands that could discard user work. Do not overwrite unrelated uncommitted files.
4. **No secret exposure.** Never print, commit, paste into reports, or add to tests actual passwords, API keys, bot tokens, OAuth secrets, payment secrets, private keys, session cookies, or personal data. Redact secrets in logs and reports.
5. **No live payment actions.** Do not initiate real payments, refunds, subscription changes, or contact payment providers using production credentials. Use mocks/test mode only.
6. **No real-user messaging.** Do not send Telegram messages, emails, SMS, push notifications, or marketing campaigns to real users. Use mocks or test accounts.
7. **No destructive security testing.** No load/stress/DoS tests, brute force against live systems, exploitation of third-party systems, or tests that alter/delete user data. Prefer local tests, static analysis, mocks, and controlled test fixtures.
8. **No new paid services or infrastructure** without explicit approval.
9. **No dependency upgrades just because newer versions exist.** Assess compatibility, security relevance, and test impact first. Avoid broad dependency churn.
10. If a task requires any prohibited action or could affect production, stop at a documented plan and ask for approval. Do not interpret the user's general wish for autonomy as permission to perform risky actions.

## Work style and autonomy

- Work autonomously on safe, local, reversible tasks. Do not ask the user to approve every small code edit.
- Ask a question only when a genuinely blocking product decision, missing credential, or ambiguous requirement cannot be resolved safely.
- Prefer small, coherent commits on a dedicated feature branch. Never commit to `main`.
- Do not push branches or create PRs unless the user has previously authorized that workflow in the current task. If uncertain, leave commits local and report.
- Keep existing project conventions and architecture. Avoid unnecessary rewrites.
- First inspect; then write a short plan; then implement; then test; then review the diff.
- If one stage is blocked, continue with independent safe stages and document the blocker.
- Do not pause after every minor action. Complete all safe work in the scope of this skill, but do not cross safety boundaries.
- Keep a durable progress log in `docs/` only if that location is appropriate and does not conflict with project conventions. Otherwise create `RIZZAFIT_WORK_REPORT.md` at repository root. Do not overwrite an existing file of that name; use a dated, unique filename.

## Required initial reconnaissance

Before changing code:

1. Confirm repository root and project identity.
2. Run and record:
   - `git status --short --branch`
   - `git log -5 --oneline --decorate`
   - `git remote -v` (redact embedded credentials if any)
3. Identify uncommitted changes and preserve them.
4. Read project documentation, README, agent instructions, dependency manifests, test instructions, and relevant code.
5. Map the application architecture: frontend, backend, database, auth, Telegram, payments, analytics, admin, deployment config.
6. Discover test commands and baseline test results before edits.
7. Identify whether tests require unavailable tools/services; do not silently skip them.
8. Create a task checklist and baseline report.

## Program roadmap and execution order

### Stage 1 — Security and reliability audit (highest priority)

Audit the current code and configuration for:

- Registration, login, logout, password handling, session/token lifecycle, password reset if present.
- Authentication and authorization boundaries on every sensitive API route.
- Admin-panel access controls and privilege escalation risks.
- CSRF protections where cookie-based state-changing requests are used.
- XSS, HTML injection, unsafe DOM insertion, template escaping, and content upload handling.
- SQL injection and safe parameterized database access.
- SSRF, path traversal, arbitrary file access, unsafe file upload/download, and open redirects.
- CORS policy, security headers, cookie flags, TLS assumptions, rate limits, brute-force protections, and account enumeration.
- Secrets handling, debug mode, error messages, logging of credentials/PII, dependency vulnerabilities.
- Telegram Mini App init-data signature verification, freshness/replay protections, one-time token generation/expiry/consumption, polling authorization, and user binding.
- Payment provider integration, including webhook signature verification, idempotency, amount/currency/order validation, and trust boundaries. Do not use live payment credentials or trigger live transactions.
- Database integrity, transaction boundaries, backup/restore procedures, and migration safety.

For each finding, record:
- Severity: Critical / High / Medium / Low / Informational.
- Exact file and line or route.
- Reproduction/evidence (safe local method).
- Impact and realistic exploit preconditions.
- Recommended fix.
- Whether a fix was implemented and which tests cover it.

Fix confirmed Critical/High issues where a safe local fix is clear. Fix Medium issues when scope is contained and regression risk is low. Do not make speculative changes. If a fix requires product policy or production configuration, document and ask.

### Stage 2 — Authentication and user experience

Review and improve, where supported by current product behavior:

- Registration and login flow clarity.
- Validation and useful, non-sensitive error messages.
- Loading, disabled, success, and failure states.
- Mobile layout, keyboard behavior, accessibility, contrast, labels, and focus management.
- Session expiration and recovery behavior.
- Profile/account settings and onboarding.
- Avoid collecting unnecessary personal data.
- Ensure analytics events do not fire for failed registrations/logins and do not contain PII.

Do not change product pricing, access entitlements, subscription rules, or account data semantics without explicit approval.

### Stage 3 — Telegram integration

Review existing Telegram Mini App and bot integration:

- Verify init data server-side; never trust client-supplied Telegram user identity.
- Check timestamp age, signature validation, replay resistance, token entropy, expiry, single-use semantics, and user binding.
- Ensure polling endpoints cannot disclose another user's login result.
- Validate allowed origins and expected Telegram launch context.
- Review error handling and fallback behavior.
- Add unit/integration tests with synthetic Telegram payloads and mock bot API.
- Do not message real users or expose bot tokens.

Only extend features that fit the existing product architecture and can be tested safely.

### Stage 4 — AI trainer

Inspect the current AI trainer before proposing changes:

- Map prompts, model/API integration, context handling, safety filters, retries, timeouts, rate limits, and cost controls.
- Check for prompt injection through user content and uploaded material.
- Prevent secrets, internal prompts, or other users' data from leaking across sessions.
- Validate and constrain structured model outputs before using them.
- Add safe fallbacks for provider failures and malformed responses.
- Check that fitness guidance is appropriately cautious: avoid diagnosis, unsafe extreme advice, and unsupported medical claims; encourage professional advice for injury/medical concerns.
- Protect API keys server-side and avoid logging sensitive user content.
- Add mocked tests; do not make unnecessary paid API calls.

Do not redesign the AI trainer or change its commercial limits without approval.

### Stage 5 — Google Analytics 4 and product measurement

Verify existing GA4 setup and event quality:

- Check page_view behavior and duplicate suppression.
- Check sign_up and login events only occur after successful server confirmation.
- Check event naming and parameter consistency.
- Confirm admin/private pages are excluded as intended.
- Confirm URL query/hash and PII are sanitized before analytics transmission.
- Search for emails, phone numbers, tokens, names, user IDs, health details, or other sensitive data in analytics payloads.
- Use browser/network tests or mocked gtag; do not send test data containing real personal information.
- Provide a small event dictionary and measurement recommendations.

Do not create new GA4 properties, change account settings, or alter consent/legal policy without approval.

### Stage 6 — SEO and content quality

Review SEO implementation without changing the user's Search Console decision:

- Inspect title, meta description, canonical, robots, Open Graph, Twitter metadata, structured data, headings, internal links, image alt text, and sitemap validity.
- Check duplicate titles/descriptions and broken internal links.
- Check robots.txt and ensure private/admin/API routes are not exposed for indexing.
- Check structured data against actual visible content.
- Check page rendering and mobile usability.
- Suggest content improvements for the homepage and relevant public pages.

**Special instruction:** Do not submit Fitify URLs to Google Search Console, do not request indexing for them, and do not manipulate Search Console. Do not change the current sitemap or Fitify canonical/robots settings unless the user explicitly asks. If the current sitemap has three URLs, preserve it.

### Stage 7 — Performance and mobile quality

Measure before optimizing:

- Page load and asset sizes.
- Images: dimensions, compression, modern formats where supported, lazy loading, layout shift.
- CSS/JS loading and unused assets.
- Caching and compression behavior.
- Backend response times and obvious N+1 or repeated database work.
- Mobile layout at common viewport widths.
- Core Web Vitals opportunities (LCP, INP, CLS), without claiming real-user metrics unless measured from real-user data.

Avoid risky caching of authenticated/private responses. Do not introduce a CDN or paid infrastructure without approval.

### Stage 8 — Growth and content recommendations

Prepare recommendations, not automatic publication, for:

- Homepage value proposition and conversion clarity.
- Onboarding and retention.
- Useful fitness content and public landing-page topics.
- Social media content plan and referral ideas.
- Funnel measurement: visit → registration → activation → return.
- Experiments that can be tested without misleading users or collecting unnecessary personal data.

Do not publish content, send campaigns, buy ads, or change pricing without approval.

## Testing and quality gates

For every implementation stage:

1. Add or update tests for each meaningful behavior and security fix.
2. Run targeted tests first, then the full project test suite.
3. Run syntax/type/lint checks that the project already uses.
4. Run `git diff --check`.
5. Review the complete diff for unintended changes, secrets, PII, generated files, and unrelated edits.
6. Verify no existing user changes were overwritten.
7. Record exact commands and outcomes. Do not report tests as passing if they were skipped or failed.
8. If a test cannot run because a dependency/service is unavailable, state exactly what is missing and leave a reproducible command.

Do not weaken or delete tests merely to obtain a green test run. Do not change expected behavior in tests unless the product requirement and implementation justify it.

## Git delivery

- Work on a clearly named feature branch based on the current intended base branch.
- Keep commits small and descriptive.
- Never force-push.
- Never merge to `main` or deploy.
- Before any push or PR, check whether the user authorized it. If not, keep work local.
- At the end, provide branch name, commit hashes (if any), changed files, test results, and exact review steps.

## Final report

Create a clear final report with these sections:

1. Executive summary.
2. Baseline repository state and pre-existing changes preserved.
3. Completed stages.
4. Security findings table (severity, evidence, fix/status).
5. UX, Telegram, AI trainer, GA4, SEO, and performance changes.
6. Tests run with exact results.
7. Files changed and commits.
8. Blocked items and why.
9. Risks requiring owner approval.
10. Recommended next actions.

Separate facts verified in code/tests from recommendations and assumptions. Never say “secure”, “fully audited”, “production-ready”, or “deployed” without clearly defining the scope and evidence.

## Definition of done

This skill's work is complete only when:
- All safe, in-scope stages have been inspected.
- High-risk findings are fixed or clearly escalated.
- Tests and diff review are complete.
- No production deployment or external side effect occurred.
- All unresolved decisions are listed.
- A final report is saved in the repository without overwriting existing work.
- The user can review the branch/diff and decide whether to push, merge, and deploy.
