"""Tests for AI Coach performance & resilience improvements (PR #14):
- Thread-safe mtime caching of catalog() / build_system()
- Overall 42s deadline budget and capped per-attempt timeouts in ask_gemini()
- 90s in-memory cooldown for degraded primary Gemini models on retryable/network failures
- No fallback and no cooldown on HTTP 400/401/403
"""
import io
import json
import os
import urllib.error
from email.message import Message
from unittest.mock import patch

import server

if __package__:
    from .test_isolation import IsolatedServerTestCase
else:
    from test_isolation import IsolatedServerTestCase


def _gemini_ok_response(text):
    """Build a minimal valid Gemini JSON response payload."""
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class _FakeClock:
    """Deterministic monotonic clock & sleep helper for deadline and cooldown tests."""

    def __init__(self, start=1000.0):
        self.now = float(start)
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, sec):
        self.sleeps.append(sec)
        self.now += float(sec)

    def advance(self, sec):
        self.now += float(sec)


class TestAICoachPerfAndResilience(IsolatedServerTestCase):
    """Verify catalog() cache, overall Gemini deadline, and primary model cooldown."""

    def test_catalog_cache_reuses_result_and_invalidates_on_mtime_change(self):
        """Repeated catalog() / build_system() calls reuse cached output; mtime change invalidates."""
        data_path = os.path.join(self.tmp_dir, "data.json")
        payload_v1 = {
            "programs": [{"id": 1, "t": {"ru": "Базовая программа"}}],
            "workouts": [{"id": 10, "t": {"ru": "Грудь и спина"}}],
            "exercises": [{"id": 100, "img": "push.png", "n": {"ru": "Отжимания"}}],
        }
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(payload_v1, f, ensure_ascii=False)

        orig_site = server.SITE
        self.addCleanup(server.reset_catalog_cache)
        self.addCleanup(setattr, server, "SITE", orig_site)
        server.SITE = self.tmp_dir
        server.reset_catalog_cache()

        parse_calls = 0
        real_json_load = json.load

        def counting_json_load(fp, *args, **kwargs):
            nonlocal parse_calls
            if getattr(fp, "name", "") == data_path:
                parse_calls += 1
            return real_json_load(fp, *args, **kwargs)

        with patch.object(server.json, "load", side_effect=counting_json_load):
            c1 = server.catalog()
            c2 = server.catalog()
            sys_prompt = server.build_system("RizzaFit")

        self.assertEqual(parse_calls, 1)
        self.assertEqual(c1, c2)
        self.assertIn("[[program:1|Базовая программа]]", sys_prompt)
        self.assertIn("[[workout:10|Грудь и спина]]", c1)
        self.assertIn("[[exercise:100|Отжимания]]", c1)

        # Update file content and advance mtime_ns by 2 seconds
        st_before = os.stat(data_path)
        payload_v2 = {
            "programs": [{"id": 2, "t": {"ru": "Силовая программа"}}],
            "workouts": [],
            "exercises": [],
        }
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(payload_v2, f, ensure_ascii=False)
        new_ns = st_before.st_mtime_ns + 2_000_000_000
        os.utime(data_path, ns=(new_ns, new_ns))

        with patch.object(server.json, "load", side_effect=counting_json_load):
            c3 = server.catalog()
            c4 = server.catalog()

        self.assertEqual(parse_calls, 2)
        self.assertEqual(c3, c4)
        self.assertIn("[[program:2|Силовая программа]]", c3)
        self.assertNotIn("Базовая программа", c3)

        # Missing data.json must safely return '' without crashing
        os.remove(data_path)
        self.assertEqual(server.catalog(), "")

    def test_ask_gemini_deadline_caps_attempt_timeouts_and_aborts_below_min_budget(self):
        """ask_gemini() must respect 42s budget, cap per-attempt timeouts, and abort if remaining < 2s."""
        cfg = {
            "provider": "gemini", "base_url": "", "key": "AIzaPerfDeadlineTestKey",
            "model": "gemini-3.8-flash", "enabled": True, "prompt": "",
        }
        msgs = [{"role": "user", "text": "Дай короткий план разминки"}]

        # Scenario A: 15s + 0.4s + 15s + 10s = 40.4s elapsed -> remaining 1.6s < 2.0s -> stop before 3rd model
        clock_a = _FakeClock(1000.0)
        attempts_a = []
        stderr_a = io.StringIO()

        def mock_http_a(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            attempts_a.append((model, round(timeout, 3)))
            if len(attempts_a) in (1, 2):
                clock_a.advance(15.0)
            else:
                clock_a.advance(10.0)
            raise server.AIProviderError("503 Busy", status_code=503, reason="Busy", error_kind="http_error")

        with patch.object(server, "ai_cfg", return_value=cfg), \
             patch.object(server.time, "monotonic", side_effect=clock_a.monotonic), \
             patch.object(server.time, "sleep", side_effect=clock_a.sleep), \
             patch.object(server, "http_json", side_effect=mock_http_a), \
             patch.object(server.sys, "stderr", stderr_a):
            ans_a = server.ask_ai(msgs, "RizzaFit", None)

        self.assertIn("встроенным тренером", ans_a)
        self.assertLessEqual(clock_a.now - 1000.0, server.GEMINI_TOTAL_BUDGET_SEC)
        self.assertEqual([m for m, _ in attempts_a], ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"])
        self.assertEqual(attempts_a[0][1], 15.0)
        self.assertEqual(attempts_a[1][1], 15.0)
        self.assertAlmostEqual(attempts_a[2][1], 11.6, places=2)
        self.assertIn("event=deadline_exceeded", stderr_a.getvalue())

        # Scenario B: primary spends 34s (remaining = 8s >= 2s) -> fallback timeout is capped to 8.0s
        server.reset_gemini_cooldown()
        clock_b = _FakeClock(2000.0)
        attempts_b = []

        def mock_http_b(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            attempts_b.append((model, round(timeout, 3)))
            if model == "gemini-3.8-flash":
                clock_b.advance(34.0)
                raise server.AIProviderError("429 Quota", status_code=429, retry_after=10.0, reason="Quota", error_kind="http_error")
            clock_b.advance(1.5)
            return _gemini_ok_response("Ответ резервной модели в пределах бюджета")

        with patch.object(server, "ai_cfg", return_value=cfg), \
             patch.object(server.time, "monotonic", side_effect=clock_b.monotonic), \
             patch.object(server.time, "sleep", side_effect=clock_b.sleep), \
             patch.object(server, "http_json", side_effect=mock_http_b):
            ans_b = server.ask_ai(msgs, "RizzaFit", None)

        self.assertEqual(ans_b, "Ответ резервной модели в пределах бюджета")
        self.assertEqual(attempts_b, [("gemini-3.8-flash", 15.0), ("gemini-3.1-flash-lite", 8.0)])

    def test_primary_cooldown_activates_on_503_skips_next_call_and_recovers_after_expiry(self):
        """503 on primary places it on 90s cooldown, skips primary on next call, and restores after expiry."""
        secret_key = "AIzaCooldownSecretKey98765"
        cfg = {
            "provider": "gemini", "base_url": "", "key": secret_key,
            "model": "gemini-3.8-flash", "enabled": True, "prompt": "",
        }
        msgs = [{"role": "user", "text": "Сколько подходов делать новичку?"}]
        clock = _FakeClock(1000.0)
        called = []
        stderr_buf = io.StringIO()

        def mock_http(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append((clock.now, model))
            if model == "gemini-3.8-flash" and clock.now < 1090.0:
                raise server.AIProviderError("503 Overloaded", status_code=503, reason="Overloaded", error_kind="http_error")
            return _gemini_ok_response(f"Ответ от {model}")

        with patch.object(server, "ai_cfg", return_value=cfg), \
             patch.object(server.time, "monotonic", side_effect=clock.monotonic), \
             patch.object(server.time, "sleep", side_effect=clock.sleep), \
             patch.object(server, "http_json", side_effect=mock_http), \
             patch.object(server.sys, "stderr", stderr_buf):
            # Call 1 at t=1000: primary 503 (+retry 503) -> fallback -> primary put on cooldown until ~1090.4
            ans1 = server.ask_ai(msgs, "RizzaFit", None)
            self.assertEqual(ans1, "Ответ от gemini-3.1-flash-lite")
            self.assertEqual([m for _, m in called], ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"])

            # Call 2 at t=1010 (within 90s): primary skipped immediately
            called.clear()
            clock.advance(10.0)
            ans2 = server.ask_ai(msgs, "RizzaFit", None)
            self.assertEqual(ans2, "Ответ от gemini-3.1-flash-lite")
            self.assertEqual([m for _, m in called], ["gemini-3.1-flash-lite"])

            # Call 3 at t=1095 (after 90s cooldown expired): primary tried first again
            called.clear()
            clock.now = 1095.0
            ans3 = server.ask_ai(msgs, "RizzaFit", None)
            self.assertEqual(ans3, "Ответ от gemini-3.8-flash")
            self.assertEqual([m for _, m in called], ["gemini-3.8-flash"])

        logs = stderr_buf.getvalue()
        self.assertIn("event=model_cooldown_skip", logs)
        self.assertIn("action=skip_to:gemini-3.1-flash-lite", logs)
        self.assertNotIn(secret_key, logs)

    def test_primary_cooldown_activates_on_timeout_and_url_error_and_429(self):
        """TimeoutError, URLError (via urlopen) and HTTP 429 on primary must put primary on cooldown."""
        cfg = {
            "provider": "gemini", "base_url": "", "key": "AIzaNetCooldownTestKey",
            "model": "gemini-3.8-flash", "enabled": True, "prompt": "",
        }
        msgs = [{"role": "user", "text": "План на спину"}]

        scenarios = [
            ("timeout", TimeoutError("timed out")),
            ("url_error", urllib.error.URLError("temporary dns failure")),
        ]
        for label, exc in scenarios:
            with self.subTest(kind=label):
                server.reset_gemini_cooldown()
                calls = []

                def mock_urlopen(req, timeout=40, exc=exc):
                    model = req.full_url.split("/models/")[1].split(":")[0]
                    calls.append(model)
                    if model == "gemini-3.8-flash":
                        raise exc

                    class _Resp:
                        def __enter__(self_r):
                            return self_r
                        def __exit__(self_r, *a):
                            return False
                        def read(self_r):
                            return json.dumps(_gemini_ok_response(f"OK fallback after {label}")).encode("utf-8")

                    return _Resp()

                with patch.object(server, "ai_cfg", return_value=cfg), \
                     patch.object(server.urllib.request, "urlopen", side_effect=mock_urlopen):
                    ans1 = server.ask_ai(msgs, "RizzaFit", None)
                    self.assertEqual(ans1, f"OK fallback after {label}")
                    self.assertEqual(calls, ["gemini-3.8-flash", "gemini-3.1-flash-lite"])
                    self.assertTrue(server._is_gemini_model_in_cooldown("gemini-3.8-flash"))

                    calls.clear()
                    ans2 = server.ask_ai(msgs, "RizzaFit", None)
                    self.assertEqual(ans2, f"OK fallback after {label}")
                    self.assertEqual(calls, ["gemini-3.1-flash-lite"])

        # HTTP 429 also triggers cooldown
        server.reset_gemini_cooldown()
        calls_429 = []

        def mock_429(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            calls_429.append(model)
            if model == "gemini-3.8-flash":
                raise server.AIProviderError("429 Quota", status_code=429, retry_after=10.0, reason="Quota", error_kind="http_error")
            return _gemini_ok_response("OK fallback after 429")

        with patch.object(server, "ai_cfg", return_value=cfg), \
             patch.object(server, "http_json", side_effect=mock_429):
            self.assertEqual(server.ask_ai(msgs, "RizzaFit", None), "OK fallback after 429")
            self.assertEqual(calls_429, ["gemini-3.8-flash", "gemini-3.1-flash-lite"])
            calls_429.clear()
            self.assertEqual(server.ask_ai(msgs, "RizzaFit", None), "OK fallback after 429")
            self.assertEqual(calls_429, ["gemini-3.1-flash-lite"])

    def test_http_400_401_403_no_fallback_and_no_cooldown(self):
        """HTTP 400/401/403 must fail fast without fallback and must NOT place primary on cooldown."""
        secret_key = "AIzaAuthErrorDoNotCooldown123"
        cfg = {
            "provider": "gemini", "base_url": "", "key": secret_key,
            "model": "gemini-3.8-flash", "enabled": True, "prompt": "",
        }

        for code in (400, 401, 403):
            with self.subTest(status_code=code):
                server.reset_gemini_cooldown()
                calls = []
                stderr_buf = io.StringIO()

                def mock_urlopen(req, timeout=40, code=code):
                    model = req.full_url.split("/models/")[1].split(":")[0]
                    calls.append(model)
                    payload = json.dumps({"error": {"message": f"Err {code} key={secret_key}"}}).encode("utf-8")
                    raise server.urllib.error.HTTPError(req.full_url, code, "Error", Message(), io.BytesIO(payload))

                with patch.object(server, "ai_cfg", return_value=cfg), \
                     patch.object(server.urllib.request, "urlopen", side_effect=mock_urlopen), \
                     patch.object(server.sys, "stderr", stderr_buf):
                    with self.assertRaises(RuntimeError) as ctx:
                        server.ask_ai([{"role": "user", "text": "Привет"}], "RizzaFit", None)

                self.assertEqual(calls, ["gemini-3.8-flash"])
                self.assertNotIn(secret_key, str(ctx.exception))
                self.assertNotIn(secret_key, stderr_buf.getvalue())
                self.assertFalse(server._is_gemini_model_in_cooldown("gemini-3.8-flash"))
