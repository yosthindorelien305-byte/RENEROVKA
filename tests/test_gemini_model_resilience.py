"""Tests for Gemini model chain & per-model cooldown/fallback resilience:
1. Primary returns 503 -> calls fallback 1.
2. Primary and fallback 1 return 503 -> calls fallback 2.
3. Any model on cooldown (primary or fallback) is skipped immediately.
4. After cooldown expires, models are tried again.
5. Timeout triggers cooldown and transitions to next model.
6. HTTP 429 triggers cooldown and transitions cleanly without loops.
7. First successful model stops iteration immediately.
8. When all models fail (or all on cooldown), falls back to builtin without changing ai.json.
9. Gemini failure/cooldown does not affect OpenAI or builtin providers.
10. provider_fallback logs the actual last failed model (never leaks secrets or user text).
"""
import io
import json
import os
from unittest.mock import patch

import server

if __package__:
    from .test_isolation import IsolatedServerTestCase
else:
    from test_isolation import IsolatedServerTestCase


class _FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def monotonic(self):
        return self.now

    def sleep(self, sec):
        self.now += max(0.0, float(sec))


def _ok_resp(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class TestGeminiModelResilience(IsolatedServerTestCase):
    def setUp(self):
        super().setUp()
        server.reset_gemini_cooldown()
        self.addCleanup(server.reset_gemini_cooldown)

    def _cfg(self, model=None, key="AIzaResilienceTestKey987654", provider="gemini", base_url=""):
        return {
            "provider": provider,
            "base_url": base_url,
            "key": key,
            "model": model if model is not None else server.GEMINI_DEFAULT_MODEL,
            "enabled": True,
            "prompt": "",
        }

    def test_1_primary_503_calls_first_fallback(self):
        """Scenario 1: Primary (gemini-flash-lite-latest) returns 503 -> falls back to gemini-3.5-flash-lite."""
        called = []

        def mock_http(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append(model)
            if model == "gemini-flash-lite-latest":
                raise server.AIProviderError("503 Busy", status_code=503, reason="High demand", error_kind="http_error")
            return _ok_resp("OK from fallback 1")

        with patch.object(server, "ai_cfg", return_value=self._cfg()), \
             patch.object(server.time, "sleep"), \
             patch.object(server, "http_json", side_effect=mock_http):
            ans = server.ask_ai([{"role": "user", "text": "План на день"}], "RizzaFit", None)

        self.assertEqual(ans, "OK from fallback 1")
        self.assertEqual(called, ["gemini-flash-lite-latest", "gemini-flash-lite-latest", "gemini-3.5-flash-lite"])

    def test_2_primary_and_first_fallback_503_call_second_fallback(self):
        """Scenario 2: Primary and fallback 1 return 503 -> calls fallback 2 (gemini-3.1-flash-lite-preview)."""
        called = []

        def mock_http(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append(model)
            if model in ("gemini-flash-lite-latest", "gemini-3.5-flash-lite"):
                raise server.AIProviderError("503 Busy", status_code=503, reason="High demand", error_kind="http_error")
            return _ok_resp("OK from fallback 2")

        with patch.object(server, "ai_cfg", return_value=self._cfg()), \
             patch.object(server.time, "sleep"), \
             patch.object(server, "http_json", side_effect=mock_http):
            ans = server.ask_ai([{"role": "user", "text": "Подтягивания"}], "RizzaFit", None)

        self.assertEqual(ans, "OK from fallback 2")
        self.assertEqual(
            called,
            [
                "gemini-flash-lite-latest",
                "gemini-flash-lite-latest",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite-preview",
            ],
        )

    def test_3_and_4_per_model_cooldown_skip_and_recovery_after_expiry(self):
        """Scenarios 3 & 4: Degraded primary AND degraded fallback models are skipped until cooldown expires."""
        clock = _FakeClock(5000.0)
        called = []
        stderr_buf = io.StringIO()

        def mock_http(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append((clock.now, model))
            if model in ("gemini-flash-lite-latest", "gemini-3.5-flash-lite") and clock.now < 5090.0:
                raise server.AIProviderError("503", status_code=503, reason="Overloaded", error_kind="http_error")
            if model == "gemini-3.1-flash-lite-preview" and 5015.0 <= clock.now < 5050.0:
                raise server.AIProviderError("503", status_code=503, reason="Preview busy", error_kind="http_error")
            return _ok_resp(f"Served by {model}")

        with patch.object(server, "ai_cfg", return_value=self._cfg()), \
             patch.object(server.time, "monotonic", side_effect=clock.monotonic), \
             patch.object(server.time, "sleep", side_effect=clock.sleep), \
             patch.object(server, "http_json", side_effect=mock_http), \
             patch.object(server.sys, "stderr", stderr_buf):
            # Call 1 at t=5000: primary & fallback 1 fail -> both placed on cooldown; fallback 2 succeeds
            ans1 = server.ask_ai([{"role": "user", "text": "Разминка"}], "RizzaFit", None)
            self.assertEqual(ans1, "Served by gemini-3.1-flash-lite-preview")
            self.assertTrue(server._is_gemini_model_in_cooldown("gemini-flash-lite-latest", now=clock.now))
            self.assertTrue(server._is_gemini_model_in_cooldown("gemini-3.5-flash-lite", now=clock.now))
            self.assertFalse(server._is_gemini_model_in_cooldown("gemini-3.1-flash-lite-preview", now=clock.now))

            # Call 2 at t=5010: primary AND fallback 1 are skipped -> goes straight to fallback 2
            called.clear()
            clock.now = 5010.0
            ans2 = server.ask_ai([{"role": "user", "text": "Спина"}], "RizzaFit", None)
            self.assertEqual(ans2, "Served by gemini-3.1-flash-lite-preview")
            self.assertEqual([m for _, m in called], ["gemini-3.1-flash-lite-preview"])

            # Call 3 at t=5020: fallback 2 also fails -> all 3 models are now on cooldown -> Call 4 calls NO models and returns builtin immediately
            called.clear()
            clock.now = 5020.0
            ans3 = server.ask_ai([{"role": "user", "text": "Как похудеть?"}], "RizzaFit", None)
            self.assertIn("встроенным тренером", ans3)
            self.assertEqual([m for _, m in called], ["gemini-3.1-flash-lite-preview"])

            called.clear()
            clock.now = 5025.0
            ans4 = server.ask_ai([{"role": "user", "text": "Как похудеть?"}], "RizzaFit", None)
            self.assertIn("встроенным тренером", ans4)
            self.assertEqual(called, [])

            # Call 5 at t=5120 (all cooldowns expired): primary tried first and succeeds immediately
            called.clear()
            clock.now = 5120.0
            ans5 = server.ask_ai([{"role": "user", "text": "Отжимания"}], "RizzaFit", None)
            self.assertEqual(ans5, "Served by gemini-flash-lite-latest")
            self.assertEqual([m for _, m in called], ["gemini-flash-lite-latest"])

        logs = stderr_buf.getvalue()
        self.assertIn("event=model_cooldown_skip", logs)
        self.assertIn("action=all_models_in_cooldown", logs)

    def test_5_timeout_puts_model_on_cooldown_and_transitions(self):
        """Scenario 5: TimeoutError puts the timed-out model on cooldown and transitions cleanly."""
        called = []

        def mock_http(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append(model)
            if model == "gemini-flash-lite-latest":
                raise server.AIProviderError(
                    "Таймаут подключения к AI-провайдеру: timed out",
                    status_code=None,
                    reason="timed out",
                    error_kind="timeout",
                )
            return _ok_resp("OK after timeout")

        with patch.object(server, "ai_cfg", return_value=self._cfg()), \
             patch.object(server, "http_json", side_effect=mock_http):
            ans1 = server.ask_ai([{"role": "user", "text": "Пресс"}], "RizzaFit", None)
            self.assertEqual(ans1, "OK after timeout")
            self.assertEqual(called, ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"])
            self.assertTrue(server._is_gemini_model_in_cooldown("gemini-flash-lite-latest"))

            called.clear()
            ans2 = server.ask_ai([{"role": "user", "text": "Ноги"}], "RizzaFit", None)
            self.assertEqual(ans2, "OK after timeout")
            self.assertEqual(called, ["gemini-3.5-flash-lite"])

    def test_6_http_429_triggers_cooldown_and_transitions_without_loops(self):
        """Scenario 6: HTTP 429 on primary and fallback 1 transitions cleanly through the chain with cooldown."""
        called = []

        def mock_http(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append(model)
            if model in ("gemini-flash-lite-latest", "gemini-3.5-flash-lite"):
                raise server.AIProviderError(
                    "429", status_code=429, retry_after=12.0, reason="Quota exceeded", error_kind="http_error"
                )
            return _ok_resp("OK from preview after 429")

        with patch.object(server, "ai_cfg", return_value=self._cfg()), \
             patch.object(server, "http_json", side_effect=mock_http):
            ans = server.ask_ai([{"role": "user", "text": "Кардио"}], "RizzaFit", None)

        self.assertEqual(ans, "OK from preview after 429")
        self.assertEqual(
            called,
            ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite-preview"],
        )
        self.assertTrue(server._is_gemini_model_in_cooldown("gemini-flash-lite-latest"))
        self.assertTrue(server._is_gemini_model_in_cooldown("gemini-3.5-flash-lite"))

    def test_7_successful_model_stops_fallback_chain_immediately(self):
        """Scenario 7: Once primary or an earlier fallback succeeds, remaining models are not called."""
        called = []

        def mock_ok_primary(req, timeout=40):
            called.append(req.full_url.split("/models/")[1].split(":")[0])
            return _ok_resp("Primary immediate OK")

        with patch.object(server, "ai_cfg", return_value=self._cfg()), \
             patch.object(server, "http_json", side_effect=mock_ok_primary):
            ans = server.ask_ai([{"role": "user", "text": "Привет"}], "RizzaFit", None)

        self.assertEqual(ans, "Primary immediate OK")
        self.assertEqual(called, ["gemini-flash-lite-latest"])

    def test_8_and_10_all_unavailable_uses_builtin_and_logs_last_failed_model_securely(self):
        """Scenarios 8 & 10: Exhausted chain uses builtin, preserves ai.json, and logs actual last failed model without leaking secrets."""
        secret_key = "AIzaLastFailedModelSecretKey999"
        secret_user_msg = "Мой секретный вес 99 кг"
        server.save_ai_cfg(self._cfg(model="gemini-3.8-flash", key=secret_key))
        before_cfg = server.ai_cfg()

        called = []
        stderr_buf = io.StringIO()

        def mock_all_fail(req, timeout=40):
            model = req.full_url.split("/models/")[1].split(":")[0]
            called.append(model)
            raise server.AIProviderError(
                f"503 {secret_key}",
                status_code=503,
                retry_after=0.0,
                reason=f"High demand on {model} key={secret_key}",
                error_kind="http_error",
            )

        with patch.object(server.time, "sleep"), \
             patch.object(server, "http_json", side_effect=mock_all_fail), \
             patch.object(server.sys, "stderr", stderr_buf):
            ans = server.ask_ai([{"role": "user", "text": f"Как похудеть? {secret_user_msg}"}], "RizzaFit", None)

        self.assertIn("встроенным тренером", ans)
        # Admin's configured gemini-3.8-flash is respected first, then all 3 new fallback models are tried
        self.assertEqual(
            called,
            [
                "gemini-3.8-flash",
                "gemini-3.8-flash",
                "gemini-flash-lite-latest",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite-preview",
            ],
        )
        # ai.json must remain untouched
        self.assertEqual(server.ai_cfg(), before_cfg)

        logs = stderr_buf.getvalue()
        fb_lines = [ln for ln in logs.splitlines() if "event=provider_fallback" in ln]
        self.assertEqual(len(fb_lines), 1)
        self.assertIn("model=gemini-3.1-flash-lite-preview", fb_lines[0])
        self.assertNotIn("model=gemini-3.8-flash", fb_lines[0])
        self.assertIn("action=fallback_to:builtin", fb_lines[0])
        self.assertNotIn(secret_key, logs)
        self.assertNotIn(secret_user_msg, logs)

    def test_9_gemini_failure_and_cooldown_do_not_break_openai_or_builtin(self):
        """Scenario 9: Gemini failures and active Gemini cooldowns leave OpenAI and builtin providers working cleanly."""
        # Put all Gemini models into cooldown
        for m in ("gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite-preview"):
            server._set_gemini_model_cooldown(m)

        openai_cfg = {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "key": "sk-test-openai-resilience-123",
            "model": "gpt-4o-mini",
            "enabled": True,
            "prompt": "",
        }
        seen_urls = []

        def mock_openai(req, timeout=40):
            seen_urls.append(req.full_url)
            return {"choices": [{"message": {"content": "OpenAI ответ без сбоев"}}]}

        with patch.object(server, "ai_cfg", return_value=openai_cfg), \
             patch.object(server, "http_json", side_effect=mock_openai):
            ans_oai = server.ask_ai([{"role": "user", "text": "Разминка"}], "RizzaFit", None)

        self.assertEqual(ans_oai, "OpenAI ответ без сбоев")
        self.assertEqual(seen_urls, ["https://api.openai.com/v1/chat/completions"])

        builtin_cfg = self._cfg(provider="builtin", key="")
        with patch.object(server, "ai_cfg", return_value=builtin_cfg):
            ans_bi = server.ask_ai([{"role": "user", "text": "Как похудеть?"}], "RizzaFit", None)
        self.assertIn("Дефицит калорий", ans_bi)
        self.assertNotIn("временно недоступен", ans_bi)

    def test_isolated_data_dir_guarantee_and_default_model_constants(self):
        """Verify test runs in temp FLEXA_DATA_DIR and expected model chain constants are configured."""
        self.assertEqual(server.GEMINI_DEFAULT_MODEL, "gemini-flash-lite-latest")
        self.assertEqual(
            server.GEMINI_FALLBACK_MODELS,
            ("gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite-preview"),
        )
        self.assertTrue(os.path.abspath(server.SECRET_DIR).startswith(os.path.abspath(self.tmp_dir)))
