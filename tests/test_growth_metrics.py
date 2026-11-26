"""Tests for deterministic AI Growth metrics, edge cases, and zero-PII enforcement (PR 4.1)."""

import datetime
import gc
import json
import os
import sqlite3
import unittest

import server
from growth import metrics as growth_metrics
from tests.test_isolation import IsolatedServerTestCase


FIXED_NOW = 1764000000  # 2025-11-24T16:00:00Z


def _collect_strings(obj):
    out = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_collect_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_collect_strings(v))
    return out


class TestGrowthMetrics(IsolatedServerTestCase):
    def test_empty_db_returns_insufficient_data_and_unavailable_external(self):
        an = growth_metrics.compute_analytics(
            server.DB_FILE,
            server.db_lock,
            site_dir=server.SITE,
            content_dir=server.CONTENT,
            free_access_mode=True,
            days=30,
            now_ts=FIXED_NOW,
        )
        self.assertTrue(an["ok"])
        self.assertFalse(an["degraded"])
        self.assertEqual(an["registrations"]["totalUsers"], 0)
        self.assertIsNone(an["activation"]["firstWorkoutRatePct"])
        self.assertEqual(an["activation"]["status"], "insufficient_data")
        self.assertIsNone(an["retention"]["workoutRetention"]["d7"]["ratePct"])
        self.assertEqual(an["retention"]["workoutRetention"]["d7"]["status"], "insufficient_data")
        self.assertIsNone(an["aiCoach"]["avgMessagesPerSession"])
        self.assertEqual(an["externalSources"]["status"], "unavailable")
        for ext in an["externalSources"]["items"]:
            self.assertEqual(ext["status"], "unavailable")
            self.assertIsNone(ext["value"])

    def test_deterministic_metrics_separation_and_zero_pii(self):
        day = 86400
        # User 1: created 10d ago, logged in 2h ago, NO workouts -> counts ONLY in login DAU/WAU/MAU & loginRetention
        u1_crt = FIXED_NOW - 10 * day
        u1_login = FIXED_NOW - 7200

        # User 2: created 10d ago, last_login_at 8d ago, logged workout in D1 window AND workout 3h ago ->
        # counts in workout DAU/WAU/MAU & workoutRetention D1, NOT in login DAU/WAU (last_login is 8d ago!)
        u2_crt = FIXED_NOW - 10 * day
        u2_login = FIXED_NOW - 8 * day
        u2_w_d1 = u2_crt + day + 3600
        u2_w_recent = FIXED_NOW - 10800
        d1_iso = datetime.datetime.fromtimestamp(u2_w_d1, tz=datetime.timezone.utc).strftime("%Y-%m-%d")

        # User 3: Telegram user created 2d ago, active lifetime PRO, 2 workouts, blocked=0
        u3_crt = FIXED_NOW - 2 * day
        u3_login = FIXED_NOW - 2 * day
        u3_w1 = FIXED_NOW - 2 * day + 600

        # User 4: Blocked user created 40d ago
        u4_crt = FIXED_NOW - 40 * day
        u4_login = FIXED_NOW - 40 * day

        u1_state = {
            "fitnessProfile": json.dumps({"goal": "strength", "level": "beginner"}),
        }
        u2_state = {
            "fitnessProfile": json.dumps({"goal": "fat_loss", "level": "intermediate"}),
            "athletePrograms": json.dumps({"activeId": "1", "logs": {"1": [d1_iso]}}),
            "customWorkouts": json.dumps([{"id": "c_priv", "name": "TOP_SECRET_CUSTOM_WORKOUT"}]),
            "hist": json.dumps([
                {"id": "1", "t": u2_w_d1, "s": 1200, "ex": 4, "rpe": "good"},
                {"id": "1", "t": u2_w_recent, "s": 1800, "ex": 6, "rpe": "hard"},
            ]),
        }
        u3_state = {
            "hist": json.dumps([
                {"id": "c_priv", "name": "SECRET_CUSTOM_NAME", "t": u3_w1, "s": 600, "ex": 2, "rpe": "easy"},
            ]),
        }

        with server.db_lock, sqlite3.connect(server.DB_FILE) as conn:
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, oauth_provider, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (1, 'pii_user_alpha', 's', 'h', 'Secret Alpha Name', 'alpha.pii@example.com', '', 'free', 0, 0, ?, ?)",
                (u1_login, u1_crt),
            )
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, oauth_provider, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (2, 'pii_user_beta', 's', 'h', 'Secret Beta Name', 'beta.pii@example.com', '', 'free', 0, 0, ?, ?)",
                (u2_login, u2_crt),
            )
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, oauth_provider, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (3, 'pii_tg_gamma', '', '', 'Secret Gamma TG', '', 'telegram', 'pro', 0, 0, ?, ?)",
                (u3_login, u3_crt),
            )
            conn.execute(
                "INSERT INTO users (id, username, pw_salt, pw_hash, display_name, email, oauth_provider, plan, plan_expires_at, is_blocked, last_login_at, created_at) "
                "VALUES (4, 'pii_blocked_delta', 's', 'h', 'Secret Delta', 'delta.pii@example.com', '', 'free', 0, 1, ?, ?)",
                (u4_login, u4_crt),
            )
            for uid_i, st_obj in ((1, u1_state), (2, u2_state), (3, u3_state)):
                conn.execute(
                    "INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?)",
                    (uid_i, json.dumps(st_obj), FIXED_NOW),
                )
            # Malformed user_state row
            conn.execute(
                "INSERT INTO user_state (user_id, data_json, updated_at) VALUES (4, '{bad json', ?)",
                (FIXED_NOW,),
            )

            # AI Coach sessions (2 within 14d, 1 stale > 14d, 1 malformed)
            conn.execute(
                "INSERT INTO coach_sessions (session_id, user_id, messages_json, version, updated_at, created_at) "
                "VALUES ('user_2', 2, ?, 1, ?, ?)",
                (json.dumps([{"role": "user", "text": "PRIVATE_COACH_MSG_1"}, {"role": "model", "text": "SECRET_COACH_REPLY"}]), FIXED_NOW - 1000, FIXED_NOW - 1000),
            )
            conn.execute(
                "INSERT INTO coach_sessions (session_id, user_id, messages_json, version, updated_at, created_at) "
                "VALUES ('guest_abc', NULL, ?, 1, ?, ?)",
                (json.dumps([{"role": "user", "text": "PRIVATE_GUEST_MSG"}]), FIXED_NOW - 3 * day, FIXED_NOW - 3 * day),
            )
            conn.execute(
                "INSERT INTO coach_sessions (session_id, user_id, messages_json, version, updated_at, created_at) "
                "VALUES ('user_1', 1, ?, 1, ?, ?)",
                (json.dumps([{"role": "user", "text": "OLD_MSG"}]), FIXED_NOW - 20 * day, FIXED_NOW - 20 * day),
            )

            # Payments
            conn.execute(
                "INSERT INTO payments (user_id, plan, days, amount, currency, provider, status, note, created_at) "
                "VALUES (3, 'pro', 0, 1990, 'RUB', 'yookassa', 'paid', 'PRIVATE_PAY_NOTE', ?)",
                (FIXED_NOW - day,),
            )
            conn.execute(
                "INSERT INTO payments (user_id, plan, days, amount, currency, provider, status, note, created_at) "
                "VALUES (2, 'pro', 30, 490, 'RUB', 'yookassa', 'pending', 'PENDING_NOTE', ?)",
                (FIXED_NOW - day,),
            )

            # Moderation & community
            conn.execute(
                "INSERT INTO user_reports (reporter_id, target_user_id, message_id, reason, status, reviewed_at, admin_note, created_at) "
                "VALUES (1, 4, 0, 'PRIVATE_REPORT_REASON_TEXT', 'new', 0, 'PRIVATE_ADMIN_NOTE', ?)",
                (FIXED_NOW - 3600,),
            )
            conn.execute(
                "INSERT INTO user_reports (reporter_id, target_user_id, message_id, reason, status, reviewed_at, admin_note, created_at) "
                "VALUES (2, 4, 0, 'SECOND_PRIVATE_REASON', 'reviewed', ?, '', ?)",
                (FIXED_NOW - 7200, FIXED_NOW - 14400),
            )
            conn.execute(
                "INSERT INTO friendships (requester_id, addressee_id, pair_min, pair_max, status, created_at, updated_at) "
                "VALUES (1, 2, 1, 2, 'accepted', ?, ?)",
                (FIXED_NOW - 1000, FIXED_NOW - 1000),
            )
            conn.execute(
                "INSERT INTO user_blocks (blocker_id, blocked_id, created_at) VALUES (1, 4, ?)",
                (FIXED_NOW - 500,),
            )
            conn.commit()

        an_free = growth_metrics.compute_analytics(
            server.DB_FILE,
            server.db_lock,
            site_dir=server.SITE,
            content_dir=server.CONTENT,
            free_access_mode=True,
            days=30,
            now_ts=FIXED_NOW,
        )

        # Registrations
        reg = an_free["registrations"]
        self.assertEqual(reg["totalUsers"], 4)
        self.assertEqual(reg["activeUsers"], 3)
        self.assertEqual(reg["blockedUsers"], 1)
        self.assertEqual(reg["newInPeriod"], 3)
        self.assertEqual(reg["byAuthMethod"], {"telegram": 1, "password": 3})

        # Strict Login vs Workout separation
        l_eng = an_free["engagement"]["loginActivity"]
        w_eng = an_free["engagement"]["workoutActivity"]
        self.assertEqual((l_eng["dau"], l_eng["wau"], l_eng["mau"]), (1, 2, 3))
        self.assertEqual((w_eng["dau"], w_eng["wau"], w_eng["mau"]), (1, 2, 2))

        # Retention D1 (eligible at >=2d old -> users 1, 2, 3, 4; user 2 worked out in D1 window)
        self.assertEqual(an_free["retention"]["workoutRetention"]["d1"]["cohortSize"], 4)
        self.assertEqual(an_free["retention"]["workoutRetention"]["d1"]["retainedCount"], 1)
        self.assertEqual(an_free["retention"]["workoutRetention"]["d1"]["ratePct"], 25.0)
        # D30 cohort has user 4 only
        self.assertEqual(an_free["retention"]["workoutRetention"]["d30"]["cohortSize"], 1)

        # Activation & Workouts
        self.assertEqual(an_free["activation"]["firstWorkoutUsers"], 2)
        self.assertEqual(an_free["activation"]["firstWorkoutRatePct"], 50.0)
        self.assertEqual(an_free["activation"]["profileCompletedUsers"], 2)
        self.assertEqual(an_free["activation"]["programStartedUsers"], 1)
        self.assertEqual(an_free["workouts"]["completedTotal"], 3)
        self.assertEqual(an_free["workouts"]["completedInPeriod"], 3)
        self.assertEqual(an_free["workouts"]["medianDurationSec"], 1200)

        # Popular catalog (only catalog items, never custom workouts)
        self.assertEqual(an_free["popularCatalog"]["topPrograms"][0]["id"], "1")
        self.assertEqual(an_free["popularCatalog"]["topWorkouts"][0]["id"], "1")

        # RPE & Profiles
        self.assertEqual(an_free["rpeDistribution"]["period"]["good"]["count"], 1)
        self.assertEqual(an_free["rpeDistribution"]["period"]["hard"]["count"], 1)
        self.assertEqual(an_free["rpeDistribution"]["period"]["easy"]["count"], 1)
        self.assertEqual(an_free["userProfiles"]["filledProfilesCount"], 2)
        self.assertEqual(an_free["userProfiles"]["goals"]["strength"], 1)
        self.assertEqual(an_free["userProfiles"]["goals"]["fat_loss"], 1)

        # AI Coach 14d
        coach = an_free["aiCoach"]
        self.assertEqual(coach["activeSessions14d"], 2)
        self.assertEqual(coach["userSessions14d"], 1)
        self.assertEqual(coach["guestSessions14d"], 1)
        self.assertEqual(coach["totalMessages14d"], 3)

        # Monetization & Moderation
        self.assertTrue(an_free["monetization"]["freeAccessMode"])
        self.assertEqual(an_free["monetization"]["realProUsersActive"], 1)
        self.assertEqual(an_free["monetization"]["paidRevenueInPeriod"], 1990)
        self.assertEqual(an_free["moderation"]["reportsByStatus"]["new"], 1)
        self.assertEqual(an_free["moderation"]["avgReviewTimeHours"], 2.0)
        self.assertEqual(an_free["moderation"]["acceptedFriendships"], 1)
        self.assertEqual(an_free["moderation"]["activeBlocks"], 1)
        self.assertEqual(an_free["dataQuality"]["malformedStateRows"], 1)

        # Check FREE_ACCESS_MODE=False propagation
        an_paid = growth_metrics.compute_analytics(
            server.DB_FILE,
            server.db_lock,
            site_dir=server.SITE,
            content_dir=server.CONTENT,
            free_access_mode=False,
            days=30,
            now_ts=FIXED_NOW,
        )
        self.assertFalse(an_paid["monetization"]["freeAccessMode"])

        ov = growth_metrics.compute_overview(
            server.DB_FILE,
            server.db_lock,
            site_dir=server.SITE,
            content_dir=server.CONTENT,
            free_access_mode=True,
            days=30,
            now_ts=FIXED_NOW,
        )

        # Zero PII must appear anywhere in analytics or overview
        joined_text = "\n".join(_collect_strings(an_free) + _collect_strings(ov))
        forbidden_tokens = (
            "alpha.pii@example.com",
            "beta.pii@example.com",
            "delta.pii@example.com",
            "pii_user_alpha",
            "pii_user_beta",
            "pii_tg_gamma",
            "pii_blocked_delta",
            "Secret Alpha Name",
            "Secret Beta Name",
            "Secret Gamma TG",
            "Secret Delta",
            "PRIVATE_COACH_MSG_1",
            "SECRET_COACH_REPLY",
            "PRIVATE_GUEST_MSG",
            "PRIVATE_REPORT_REASON_TEXT",
            "PRIVATE_ADMIN_NOTE",
            "PRIVATE_PAY_NOTE",
            "TOP_SECRET_CUSTOM_WORKOUT",
            "SECRET_CUSTOM_NAME",
        )
        for pii in forbidden_tokens:
            self.assertNotIn(pii, joined_text, msg=f"PII leaked into analytics/overview: {pii}")

    def test_corrupted_db_file_degrades_gracefully_without_faking_zeros(self):
        gc.collect()
        for suffix in ("", "-wal", "-shm"):
            p_rem = server.DB_FILE + suffix
            if suffix and os.path.exists(p_rem):
                os.remove(p_rem)
        with open(server.DB_FILE, "wb") as f:
            f.write(b"NOT A VALID SQLITE FILE")

        an = growth_metrics.compute_analytics(
            server.DB_FILE,
            server.db_lock,
            site_dir=server.SITE,
            content_dir=server.CONTENT,
            days=7,
            now_ts=FIXED_NOW,
        )
        self.assertTrue(an["ok"])
        self.assertTrue(an["degraded"])
        self.assertEqual(an["dataQuality"]["dbHealth"], "corrupted")
        self.assertEqual(an["registrations"]["status"], "unavailable")
        self.assertIsNone(an["registrations"]["value"])
        self.assertEqual(an["engagement"]["workoutActivity"]["status"], "unavailable")

        ov = growth_metrics.compute_overview(
            server.DB_FILE,
            server.db_lock,
            site_dir=server.SITE,
            content_dir=server.CONTENT,
            days=7,
            now_ts=FIXED_NOW,
        )
        self.assertTrue(ov["ok"])
        self.assertTrue(ov["degraded"])
        self.assertEqual(ov["systemStatus"]["dbHealth"], "corrupted")
        self.assertEqual(ov["kpis"][0]["value"], "Нет данных")


if __name__ == "__main__":
    unittest.main()
