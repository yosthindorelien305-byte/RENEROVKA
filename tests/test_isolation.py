"""Shared test isolation base class, path-safety guard, and isolation verification tests.

Prevents any unittest suite from reading or mutating production server_data/flexa.db,
production AI/admin/payment/Telegram configs, or site/content/uploads.
"""
import gc
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import server

PROD_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_SECRET_DIR = os.path.realpath(os.path.join(PROD_ROOT, "server_data"))
PROD_DB_FILE = os.path.realpath(os.path.join(PROD_SECRET_DIR, "flexa.db"))
PROD_UPLOADS = os.path.realpath(os.path.join(PROD_ROOT, "site", "content", "uploads"))

ISOLATED_PATH_ATTRS = (
    "SECRET_DIR",
    "DB_FILE",
    "AI_FILE",
    "ADMIN_FILE",
    "YOOKASSA_FILE",
    "TELEGRAM_FILE",
    "PASS_TXT",
    "UPLOADS",
)


def _is_within(path_real, root_real):
    """Return True if path_real equals or resides inside root_real."""
    try:
        return os.path.commonpath([root_real, path_real]) == root_real
    except ValueError:
        return False


def assert_isolated_server_paths(tmp_root):
    """Raise RuntimeError if any server data/DB/upload path points outside tmp_root or into production."""
    real_tmp = os.path.realpath(tmp_root)
    for attr in ISOLATED_PATH_ATTRS:
        val = getattr(server, attr, None)
        if not isinstance(val, str) or not val.strip():
            raise RuntimeError(f"Isolation guard failed: server.{attr} is empty or unset ({val!r})")
        real_val = os.path.realpath(val)
        if _is_within(real_val, PROD_SECRET_DIR) or real_val == PROD_DB_FILE or _is_within(real_val, PROD_UPLOADS):
            raise RuntimeError(
                f"Isolation guard blocked production path access: server.{attr}={real_val!r} "
                f"(expected inside temp directory {real_tmp!r})"
            )
        if not _is_within(real_val, real_tmp):
            raise RuntimeError(
                f"Isolation guard failed: server.{attr}={real_val!r} is outside temp directory {real_tmp!r}"
            )


def _clear_server_memory_state():
    """Reset in-memory rate limits, coach locks, tokens, failure counters, and AI Coach caches."""
    server.coach_hits.clear()
    with server.coach_sessions_lock:
        server.active_coach_sessions.clear()
    with server.lock:
        server.tokens.clear()
    with server.fails_lock:
        server.fails.clear()
    server.reset_gemini_cooldown()
    server.reset_catalog_cache()


class IsolatedServerTestCase(unittest.TestCase):
    """Base TestCase that redirects all server DB/config/upload paths into a per-test temp directory."""

    def setUp(self):
        super().setUp()
        self._iso_tmp = tempfile.TemporaryDirectory(prefix="flexa_test_iso_")
        self.tmp_dir = self._iso_tmp.name
        self.tmp_secret_dir = os.path.join(self.tmp_dir, "server_data")
        self.tmp_uploads_dir = os.path.join(self.tmp_dir, "uploads")
        os.makedirs(self.tmp_secret_dir, exist_ok=True)
        os.makedirs(self.tmp_uploads_dir, exist_ok=True)

        def _cleanup_tmp():
            gc.collect()
            try:
                self._iso_tmp.cleanup()
            except (PermissionError, OSError):
                pass

        # Register temp dir cleanup first so LIFO executes it after path/state restoration.
        self.addCleanup(_cleanup_tmp)

        orig_env = os.environ.get("FLEXA_DATA_DIR")

        def _restore_env():
            if orig_env is None:
                os.environ.pop("FLEXA_DATA_DIR", None)
            else:
                os.environ["FLEXA_DATA_DIR"] = orig_env

        self.addCleanup(_restore_env)
        os.environ["FLEXA_DATA_DIR"] = self.tmp_secret_dir

        for attr in ISOLATED_PATH_ATTRS:
            self.addCleanup(setattr, server, attr, getattr(server, attr))

        server.SECRET_DIR = self.tmp_secret_dir
        server.DB_FILE = os.path.join(self.tmp_secret_dir, "flexa.db")
        server.AI_FILE = os.path.join(self.tmp_secret_dir, "ai.json")
        server.ADMIN_FILE = os.path.join(self.tmp_secret_dir, "admin.json")
        server.YOOKASSA_FILE = os.path.join(self.tmp_secret_dir, "yookassa.json")
        server.TELEGRAM_FILE = os.path.join(self.tmp_secret_dir, "telegram.json")
        server.PASS_TXT = os.path.join(self.tmp_dir, "ADMIN_PASSWORD.txt")
        server.UPLOADS = self.tmp_uploads_dir

        _clear_server_memory_state()
        self.addCleanup(_clear_server_memory_state)

        assert_isolated_server_paths(self.tmp_dir)
        server.init_db()


def _file_snapshot(path):
    """Return (exists, sha256_or_none) for safe before/after file verification."""
    if not os.path.exists(path):
        return (False, None)
    with open(path, "rb") as f:
        return (True, hashlib.sha256(f.read()).hexdigest())


class TestDatabaseIsolationGuard(IsolatedServerTestCase):
    """Verify that tests cannot access or mutate production DB/configs."""

    def test_all_server_paths_isolated_inside_temp_dir(self):
        """All mutable server DB, config, password, and upload paths must point inside tmp_dir."""
        assert_isolated_server_paths(self.tmp_dir)
        self.assertTrue(os.path.isfile(server.DB_FILE))
        self.assertNotEqual(os.path.realpath(server.DB_FILE), PROD_DB_FILE)
        self.assertNotEqual(os.path.realpath(server.SECRET_DIR), PROD_SECRET_DIR)
        self.assertNotEqual(os.path.realpath(server.UPLOADS), PROD_UPLOADS)

    def test_guard_rejects_production_db_and_ai_paths(self):
        """Isolation guard must raise RuntimeError immediately if DB_FILE or AI_FILE points to server_data."""
        orig_db = server.DB_FILE
        try:
            server.DB_FILE = PROD_DB_FILE
            with self.assertRaises(RuntimeError) as ctx_db:
                assert_isolated_server_paths(self.tmp_dir)
            self.assertIn("server.DB_FILE", str(ctx_db.exception))
        finally:
            server.DB_FILE = orig_db

        orig_ai = server.AI_FILE
        try:
            server.AI_FILE = os.path.join(PROD_SECRET_DIR, "ai.json")
            with self.assertRaises(RuntimeError) as ctx_ai:
                assert_isolated_server_paths(self.tmp_dir)
            self.assertIn("server.AI_FILE", str(ctx_ai.exception))
        finally:
            server.AI_FILE = orig_ai

    def test_db_writes_do_not_create_or_modify_repo_production_db(self):
        """SQLite and AI config mutations in tests must leave repo server_data files untouched."""
        prod_ai = os.path.join(PROD_SECRET_DIR, "ai.json")
        db_before = _file_snapshot(PROD_DB_FILE)
        ai_before = _file_snapshot(prod_ai)

        conn = sqlite3.connect(server.DB_FILE)
        try:
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (999991, 'iso_probe', 's', 'h', 'Iso Probe', 'iso@test.com', 'free', 0, 0, 0, 1)"
            )
            conn.execute(
                "INSERT INTO coach_sessions (session_id, user_id, messages_json, version, updated_at, created_at) "
                "VALUES ('user_999991', 999991, '[]', 1, 1, 1)"
            )
            conn.commit()
            conn.execute("DELETE FROM coach_sessions")
            conn.commit()
        finally:
            conn.close()

        server.save_ai_cfg({"provider": "builtin", "enabled": True, "model": "gemini-3.8-flash"})
        self.assertTrue(os.path.isfile(server.AI_FILE))

        self.assertEqual(_file_snapshot(PROD_DB_FILE), db_before)
        self.assertEqual(_file_snapshot(prod_ai), ai_before)

    def test_flexa_data_dir_env_var_redirects_paths_and_default_preserved(self):
        """FLEXA_DATA_DIR redirects SECRET_DIR and derived files, while default preserves server_data."""
        env_dir = os.path.join(self.tmp_dir, "custom_env_data")
        code = (
            "import json, server; "
            "print(json.dumps({"
            "'SECRET_DIR': server.SECRET_DIR, "
            "'DB_FILE': server.DB_FILE, "
            "'AI_FILE': server.AI_FILE, "
            "'ADMIN_FILE': server.ADMIN_FILE, "
            "'YOOKASSA_FILE': server.YOOKASSA_FILE, "
            "'TELEGRAM_FILE': server.TELEGRAM_FILE"
            "}))"
        )

        env_with = os.environ.copy()
        env_with["FLEXA_DATA_DIR"] = env_dir
        out_with = subprocess.check_output(
            [sys.executable, "-c", code], cwd=PROD_ROOT, env=env_with, text=True
        )
        import json
        paths_with = json.loads(out_with)
        real_env_dir = os.path.realpath(env_dir)
        for key, val in paths_with.items():
            self.assertTrue(
                _is_within(os.path.realpath(val), real_env_dir),
                f"{key}={val!r} should reside inside {real_env_dir!r}",
            )

        env_default = os.environ.copy()
        env_default.pop("FLEXA_DATA_DIR", None)
        out_default = subprocess.check_output(
            [sys.executable, "-c", code], cwd=PROD_ROOT, env=env_default, text=True
        )
        paths_default = json.loads(out_default)
        self.assertEqual(os.path.realpath(paths_default["SECRET_DIR"]), PROD_SECRET_DIR)
        self.assertEqual(os.path.realpath(paths_default["DB_FILE"]), PROD_DB_FILE)

    def test_growth_orchestrator_uses_isolated_base_class(self):
        """TestGrowthOrchestrator must inherit IsolatedServerTestCase and never init_db on global paths."""
        if __package__:
            from .test_growth_orchestrator import TestGrowthOrchestrator
        else:
            from test_growth_orchestrator import TestGrowthOrchestrator

        self.assertTrue(issubclass(TestGrowthOrchestrator, IsolatedServerTestCase))
        self.assertIs(TestGrowthOrchestrator.setUpClass.__func__, unittest.TestCase.setUpClass.__func__)
