"""Deterministic Python + SQL analytics for RizzaFit AI Growth (PR 4.1)."""

import contextlib
import datetime
import json
import os
import re
import sqlite3
import statistics
import time

from .db import query_audit_log
from .telemetry import query_feature_usage

ALLOWED_PERIOD_DAYS = (7, 30, 90)
COACH_WINDOW_DAYS = 14

GOAL_KEYS = ('fat_loss', 'muscle_gain', 'recomp', 'strength', 'endurance', 'health')
LEVEL_KEYS = ('beginner', 'intermediate', 'advanced')
RPE_KEYS = ('easy', 'good', 'hard')


def _fmt_utc_iso(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return ''


def _fmt_utc_date(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%d')
    except Exception:
        return ''


def _normalize_days(raw_days):
    try:
        d = int(raw_days)
    except (TypeError, ValueError):
        return 30
    return d if d in ALLOWED_PERIOD_DAYS else 30


def _pct(num, den):
    if den is None or den <= 0 or num is None:
        return None
    return round((float(num) / float(den)) * 100.0, 1)


def _parse_epoch_sec(raw_t):
    """Parse epoch seconds/ms or YYYY-MM-DD inside [2000-01-01, 2100-01-01]."""
    if isinstance(raw_t, bool) or raw_t is None:
        return None
    if isinstance(raw_t, str):
        s = raw_t.strip()
        if not s:
            return None
        m = re.match(r'^(\d{4}-\d{2}-\d{2})', s)
        if m:
            try:
                dt = datetime.datetime.strptime(m.group(1), '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
                return dt.timestamp()
            except ValueError:
                return None
    try:
        ts = float(raw_t)
    except (TypeError, ValueError):
        return None
    if ts > 1e11:
        ts /= 1000.0
    if not (946684800 <= ts <= 4102444800):
        return None
    return ts


def _parse_nested(state_dict, key):
    raw = state_dict.get(key)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            raw = json.loads(s)
        except Exception:
            return None
    return raw if isinstance(raw, (dict, list)) else None


def _build_date_buckets(now_ts, days):
    end_dt = datetime.datetime.fromtimestamp(int(now_ts), tz=datetime.timezone.utc).date()
    dates = [(end_dt - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days - 1, -1, -1)]
    return dates, {d: 0 for d in dates}


def _load_catalog_titles(site_dir, content_dir):
    """Read-only lookup of public catalog program & workout titles (never custom user titles)."""
    programs = {}
    workouts = {}

    data_path = os.path.join(site_dir, 'data.json') if site_dir else ''
    if data_path and os.path.isfile(data_path):
        try:
            with open(data_path, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                for p in data.get('programs') or []:
                    if not isinstance(p, dict) or p.get('id') is None:
                        continue
                    t = p.get('t') if isinstance(p.get('t'), dict) else {}
                    title = str(t.get('ru') or t.get('en') or '').strip()
                    if title:
                        programs[str(p['id'])] = title[:120]
                for w in data.get('workouts') or []:
                    if not isinstance(w, dict) or w.get('id') is None:
                        continue
                    t = w.get('t') if isinstance(w.get('t'), dict) else {}
                    title = str(t.get('ru') or t.get('en') or '').strip()
                    if title:
                        workouts[str(w['id'])] = title[:120]
        except Exception:
            pass

    ov_path = os.path.join(content_dir, 'overrides.json') if content_dir else ''
    if ov_path and os.path.isfile(ov_path):
        try:
            with open(ov_path, encoding='utf-8') as f:
                ov = json.load(f)
            if isinstance(ov, dict):
                for kind, target_map in (('p', programs), ('w', workouts)):
                    sub = ov.get(kind)
                    if not isinstance(sub, dict):
                        continue
                    for eid, item in sub.items():
                        if not isinstance(item, dict):
                            continue
                        t = item.get('t') if isinstance(item.get('t'), dict) else {}
                        title = str(t.get('ru') or t.get('en') or '').strip()
                        if title:
                            target_map[str(eid)] = title[:120]
        except Exception:
            pass

    return programs, workouts


def _external_sources_block(updated_iso):
    return {
        'status': 'unavailable',
        'updatedAt': updated_iso,
        'definition': 'Внешние источники веб-аналитики и маркетинга (не хранятся в SQLite)',
        'items': [
            {
                'id': 'ga4',
                'label': 'Google Analytics 4 (посещаемость, отказы, UTM)',
                'status': 'unavailable',
                'value': None,
                'source': 'GA4 Property G-XSBKDCY4CS (только клиентская отправка)',
                'reason': 'GA4 Data API не подключён к серверу. Цифры не подменяются нулями.',
            },
            {
                'id': 'searchConsole',
                'label': 'Search Console / Яндекс.Вебмастер (позиции и CTR)',
                'status': 'unavailable',
                'value': None,
                'source': 'Внешний поисковый API',
                'reason': 'Интеграция с поисковыми консолями не настроена.',
            },
            {
                'id': 'guestFunnel',
                'label': 'Гостевая воронка (до регистрации и входа)',
                'status': 'unavailable',
                'value': None,
                'source': 'Серверная воронка без авторизации',
                'reason': 'Анонимные серверные счётчики просмотров и стартов не включены.',
            },
            {
                'id': 'socialChannels',
                'label': 'Охваты и ER в Telegram-канале / соцсетях',
                'status': 'unavailable',
                'value': None,
                'source': 'Telegram Channel Stats / Social API',
                'reason': 'Модуль Social AI и статистика канала планируются в PR 4.5.',
            },
        ],
    }


def _degraded_analytics(days, now_ts, db_health, err_msg, free_access_mode):
    updated_iso = _fmt_utc_iso(now_ts)
    unavail_block = {
        'status': 'unavailable',
        'value': None,
        'source': 'flexa.db',
        'updatedAt': updated_iso,
        'limitations': err_msg,
    }
    return {
        'ok': True,
        'degraded': True,
        'periodDays': days,
        'generatedAt': updated_iso,
        'generatedAtTs': int(now_ts),
        'freeAccessMode': bool(free_access_mode),
        'dataQuality': {
            'dbHealth': db_health,
            'error': err_msg,
            'malformedStateRows': None,
            'malformedCoachRows': None,
            'generatedAt': updated_iso,
            'periodDays': days,
        },
        'registrations': {**unavail_block, 'definition': 'Регистрации в таблице users'},
        'engagement': {
            'lastLoginActivity': {**unavail_block, 'isProxy': True, 'metricType': 'last_login_proxy', 'definition': 'Прокси недавних входов по единственному полю users.last_login_at (не исторический DAU/WAU/MAU)'},
            'workoutActivity': {**unavail_block, 'isProxy': False, 'metricType': 'workout_history', 'definition': 'Фактическая активность тренировок по user_state.hist'},
        },
        'retention': {
            'workoutRetention': {**unavail_block, 'isProxy': False, 'definition': 'Когортное удержание фактических тренировок D1/D7/D30'},
            'lastLoginReturnProxy': {**unavail_block, 'isProxy': True, 'metricType': 'last_login_return_proxy', 'definition': 'Rolling-прокси возврата по единственному полю users.last_login_at D1/D7/D30'},
        },
        'activation': {**unavail_block, 'definition': 'Активация зарегистрированных пользователей'},
        'workouts': {**unavail_block, 'definition': 'Завершённые тренировки из user_state.hist'},
        'popularCatalog': {**unavail_block, 'definition': 'Популярные программы и тренировки каталога', 'topPrograms': [], 'topWorkouts': []},
        'rpeDistribution': {**unavail_block, 'definition': 'Распределение субъективной нагрузки RPE'},
        'userProfiles': {**unavail_block, 'definition': 'Цели и уровни подготовки из fitnessProfile'},
        'aiCoach': {**unavail_block, 'windowDays': COACH_WINDOW_DAYS, 'definition': 'Сессии AI Coach за 14-дневное окно'},
        'featureUsage': {**unavail_block, 'piiStored': False, 'totalInPeriod': 0, 'totalAllTime': 0, 'byEvent': [], 'dailySeries': [], 'definition': 'Агрегированные суточные счётчики использования функций RizzaFit'},
        'monetization': {**unavail_block, 'freeAccessMode': bool(free_access_mode), 'definition': 'Подписки PRO и платежи'},
        'moderation': {**unavail_block, 'definition': 'Жалобы и социальные связи'},
        'externalSources': _external_sources_block(updated_iso),
    }


def _extract_raw_snapshot(db_file, db_lock):
    """Hold db_lock only long enough to fetch raw SQLite rows."""
    required_tables = {'users', 'user_state', 'payments', 'coach_sessions', 'user_reports', 'friendships', 'user_blocks'}
    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        existing = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        missing_tables = sorted(required_tables - existing)

        users_rows = conn.execute(
            'SELECT id, created_at, last_login_at, oauth_provider, plan, plan_expires_at, is_blocked FROM users'
        ).fetchall() if 'users' in existing else []

        state_rows = conn.execute(
            'SELECT user_id, data_json, updated_at FROM user_state'
        ).fetchall() if 'user_state' in existing else []

        pay_rows = conn.execute(
            'SELECT user_id, plan, days, amount, currency, provider, status, created_at FROM payments'
        ).fetchall() if 'payments' in existing else []

        coach_rows = conn.execute(
            'SELECT session_id, user_id, messages_json, updated_at, created_at FROM coach_sessions'
        ).fetchall() if 'coach_sessions' in existing else []

        report_rows = conn.execute(
            'SELECT status, created_at, reviewed_at FROM user_reports'
        ).fetchall() if 'user_reports' in existing else []

        friend_accepted = int(conn.execute(
            "SELECT COUNT(*) FROM friendships WHERE status = 'accepted'"
        ).fetchone()[0]) if 'friendships' in existing else None

        blocks_count = int(conn.execute(
            'SELECT COUNT(*) FROM user_blocks'
        ).fetchone()[0]) if 'user_blocks' in existing else None

    return {
        'missingTables': missing_tables,
        'users': users_rows,
        'user_state': state_rows,
        'payments': pay_rows,
        'coach_sessions': coach_rows,
        'user_reports': report_rows,
        'friend_accepted': friend_accepted,
        'blocks_count': blocks_count,
    }


def compute_analytics(
    db_file,
    db_lock,
    *,
    site_dir='',
    content_dir='',
    free_access_mode=True,
    days=30,
    now_ts=None,
):
    """Compute all Growth analytics deterministically from SQLite + static site catalog."""
    period_days = _normalize_days(days)
    now = int(now_ts if now_ts is not None else time.time())
    updated_iso = _fmt_utc_iso(now)

    if not db_file or not os.path.isfile(db_file):
        return _degraded_analytics(period_days, now, 'missing', 'Файл базы данных SQLite не найден', free_access_mode)

    try:
        snap = _extract_raw_snapshot(db_file, db_lock)
    except sqlite3.Error:
        return _degraded_analytics(
            period_days, now, 'corrupted', 'Не удалось прочитать SQLite БД (возможно повреждение)', free_access_mode
        )

    if snap['missingTables'] and 'users' in snap['missingTables']:
        return _degraded_analytics(
            period_days,
            now,
            'uninitialized',
            'Отсутствуют базовые таблицы БД: ' + ', '.join(snap['missingTables']),
            free_access_mode,
        )

    prog_titles, wo_titles = _load_catalog_titles(site_dir, content_dir)
    period_start = now - period_days * 86400
    max_ts = now + 300
    d1_cut = now - 86400
    d7_cut = now - 7 * 86400
    d30_cut = now - 30 * 86400
    coach_cut = now - COACH_WINDOW_DAYS * 86400

    # --- 1. Users & Last-Login Recency Proxy (strictly users.last_login_at) ---
    users_rows = snap['users']
    total_users = len(users_rows)
    blocked_users = 0
    active_users = 0
    new_in_period = 0
    auth_tg = 0
    auth_pw = 0
    real_pro_active = 0

    last_login_24h = 0
    last_login_7d = 0
    last_login_30d = 0

    user_created_map = {}
    user_last_login_map = {}

    reg_dates, reg_buckets = _build_date_buckets(now, period_days)

    for uid, created_at, last_login_at, oauth_provider, plan, plan_expires_at, is_blocked in users_rows:
        uid_int = int(uid)
        c_ts = int(created_at or 0)
        l_ts = int(last_login_at or 0)
        blk = bool(is_blocked)
        user_created_map[uid_int] = c_ts
        user_last_login_map[uid_int] = l_ts

        if blk:
            blocked_users += 1
        else:
            active_users += 1

        if (oauth_provider or '').strip().lower() == 'telegram':
            auth_tg += 1
        else:
            auth_pw += 1

        if c_ts >= period_start and c_ts <= max_ts:
            new_in_period += 1
            d_str = _fmt_utc_date(c_ts)
            if d_str in reg_buckets:
                reg_buckets[d_str] += 1

        if not blk and str(plan or '').lower() == 'pro' and (int(plan_expires_at or 0) == 0 or int(plan_expires_at or 0) > now):
            real_pro_active += 1

        if not blk and 0 < l_ts <= max_ts:
            if l_ts >= d1_cut:
                last_login_24h += 1
            if l_ts >= d7_cut:
                last_login_7d += 1
            if l_ts >= d30_cut:
                last_login_30d += 1

    # --- 2. User State: Workouts, Programs, RPE, Fitness Profiles ---
    malformed_state_rows = 0
    user_workout_times = {}  # uid -> [epoch_sec]
    first_workout_users = 0
    profile_completed_users = 0
    program_started_users = 0

    workouts_total = 0
    workouts_in_period = 0
    wo_dates, wo_buckets = _build_date_buckets(now, period_days)
    durations_period = []
    ex_counts_period = []

    rpe_total = {'easy': 0, 'good': 0, 'hard': 0, 'unrated': 0}
    rpe_period = {'easy': 0, 'good': 0, 'hard': 0, 'unrated': 0}

    goal_counts = {k: 0 for k in GOAL_KEYS}
    goal_counts['unspecified'] = 0
    level_counts = {k: 0 for k in LEVEL_KEYS}
    level_counts['unspecified'] = 0
    filled_profiles_count = 0

    prog_usage = {}  # pid -> {'users': set, 'days': int}
    wo_usage = {}    # wid -> {'total': int, 'period': int}

    for uid, data_json_raw, _updated_at in snap['user_state']:
        uid_int = int(uid)
        if not data_json_raw:
            continue
        try:
            state = json.loads(data_json_raw)
        except Exception:
            malformed_state_rows += 1
            continue
        if not isinstance(state, dict):
            malformed_state_rows += 1
            continue

        # Fitness profile
        fp = _parse_nested(state, 'fitnessProfile')
        if isinstance(fp, dict) and fp:
            has_core_fp = any(fp.get(k) for k in ('goal', 'level', 'age', 'heightCm', 'sex'))
            if has_core_fp:
                profile_completed_users += 1
                filled_profiles_count += 1
                g = str(fp.get('goal') or '').strip().lower()
                goal_counts[g if g in GOAL_KEYS else 'unspecified'] += 1
                lv = str(fp.get('level') or '').strip().lower()
                level_counts[lv if lv in LEVEL_KEYS else 'unspecified'] += 1

        # Programs (athletePrograms preferred over legacy progState)
        ps = _parse_nested(state, 'athletePrograms')
        if not isinstance(ps, dict) or not ps.get('activeId'):
            ps_leg = _parse_nested(state, 'progState')
            if isinstance(ps_leg, dict) and ps_leg.get('activeId'):
                ps = ps_leg
        if isinstance(ps, dict):
            active_pid = str(ps.get('activeId') or '').strip()
            logs_map = ps.get('logs') if isinstance(ps.get('logs'), dict) else {}
            if active_pid or any(isinstance(v, list) and len(v) > 0 for v in logs_map.values()):
                program_started_users += 1
            seen_pids = set()
            if active_pid:
                seen_pids.add(active_pid)
            for pid_k, d_list in logs_map.items():
                if isinstance(d_list, list) and d_list:
                    seen_pids.add(str(pid_k))
            for pid in seen_pids:
                if pid not in prog_titles:
                    continue  # catalog programs only
                entry = prog_usage.setdefault(pid, {'users': set(), 'days': 0})
                entry['users'].add(uid_int)
                d_logs = logs_map.get(pid)
                if isinstance(d_list := d_logs, list):
                    valid_days = {str(x).strip() for x in d_list if isinstance(x, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', x.strip())}
                    entry['days'] += len(valid_days)

        # Workout history (strictly user_state.hist)
        hist = _parse_nested(state, 'hist')
        if isinstance(hist, list):
            u_times = []
            for item in hist:
                if not isinstance(item, dict):
                    continue
                workouts_total += 1
                t_sec = _parse_epoch_sec(item.get('t'))
                if t_sec is not None:
                    u_times.append(t_sec)
                in_period = t_sec is not None and (period_start <= t_sec <= now + 86400)
                if in_period:
                    workouts_in_period += 1
                    d_str = _fmt_utc_date(t_sec)
                    if d_str in wo_buckets:
                        wo_buckets[d_str] += 1

                    raw_dur = item.get('s')
                    if not isinstance(raw_dur, bool) and raw_dur is not None:
                        try:
                            dur_f = float(raw_dur)
                            if 1 <= dur_f <= 86400:
                                durations_period.append(dur_f)
                        except (TypeError, ValueError):
                            pass

                    raw_ex = item.get('ex')
                    if not isinstance(raw_ex, bool) and raw_ex is not None:
                        try:
                            ex_i = int(raw_ex)
                            if 1 <= ex_i <= 500:
                                ex_counts_period.append(ex_i)
                        except (TypeError, ValueError):
                            pass

                rpe_raw = str(item.get('rpe') or '').strip().lower()
                rpe_key = rpe_raw if rpe_raw in RPE_KEYS else 'unrated'
                rpe_total[rpe_key] += 1
                if in_period:
                    rpe_period[rpe_key] += 1

                wid = str(item.get('id') or '').strip()
                if wid and wid in wo_titles:
                    w_stat = wo_usage.setdefault(wid, {'total': 0, 'period': 0})
                    w_stat['total'] += 1
                    if in_period:
                        w_stat['period'] += 1

            if u_times or any(isinstance(x, dict) for x in hist):
                first_workout_users += 1
            if u_times:
                user_workout_times[uid_int] = u_times

    workout_dau = sum(1 for ts_list in user_workout_times.values() if any(d1_cut <= t <= max_ts for t in ts_list))
    workout_wau = sum(1 for ts_list in user_workout_times.values() if any(d7_cut <= t <= max_ts for t in ts_list))
    workout_mau = sum(1 for ts_list in user_workout_times.values() if any(d30_cut <= t <= max_ts for t in ts_list))

    # --- 3. Retention (Completed Workout Cohorts vs Last-Login Return Proxy) ---
    workout_retention = {}
    last_login_return_proxy = {}
    for n in (1, 7, 30):
        key = f'd{n}'
        min_age_sec = (n + 1) * 86400
        # Only users registered >= N+1 full days ago have a closed Day N observation window [created+N*d, created+(N+1)*d)
        matured_cohort = [
            uid_i for uid_i, c_ts in user_created_map.items()
            if 0 < c_ts <= max_ts and (now - c_ts) >= min_age_sec
        ]
        incomplete_cnt = sum(
            1 for c_ts in user_created_map.values()
            if 0 < c_ts <= max_ts and 0 <= (now - c_ts) < min_age_sec
        )

        w_retained = 0
        for uid_i in matured_cohort:
            c_ts = user_created_map[uid_i]
            win_start = c_ts + n * 86400
            win_end = c_ts + (n + 1) * 86400
            if any(win_start <= wt < win_end for wt in user_workout_times.get(uid_i, ())):
                w_retained += 1
        workout_retention[key] = {
            'minAgeDays': n + 1,
            'windowDefinition': f'[+{n}д, +{n + 1}д) от регистрации',
            'cohortSize': len(matured_cohort),
            'excludedIncompleteCount': incomplete_cnt,
            'retainedCount': w_retained,
            'ratePct': _pct(w_retained, len(matured_cohort)),
            'status': 'ok' if matured_cohort else 'insufficient_data',
        }

        # Last-login rolling proxy among the same matured cohort (>= N+1 days old) to avoid incomplete-cohort bias
        l_retained = sum(
            1 for uid_i in matured_cohort
            if (user_created_map[uid_i] + n * 86400) <= user_last_login_map.get(uid_i, 0) <= max_ts
        )
        last_login_return_proxy[key] = {
            'minAgeDays': n + 1,
            'windowDefinition': f'last_login_at >= +{n}д (когорта >= {n + 1}д)',
            'cohortSize': len(matured_cohort),
            'excludedIncompleteCount': incomplete_cnt,
            'retainedCount': l_retained,
            'ratePct': _pct(l_retained, len(matured_cohort)),
            'status': 'ok' if matured_cohort else 'insufficient_data',
        }

    # --- 4. Catalog Popularity ---
    top_programs = sorted(
        [
            {
                'id': pid,
                'title': prog_titles[pid],
                'usersCount': len(st['users']),
                'completedDaysTotal': st['days'],
            }
            for pid, st in prog_usage.items()
        ],
        key=lambda x: (-x['usersCount'], -x['completedDaysTotal'], x['id']),
    )[:10]

    top_workouts = sorted(
        [
            {
                'id': wid,
                'title': wo_titles[wid],
                'completionsPeriod': st['period'],
                'completionsTotal': st['total'],
            }
            for wid, st in wo_usage.items()
        ],
        key=lambda x: (-x['completionsPeriod'], -x['completionsTotal'], x['id']),
    )[:10]

    # --- 5. AI Coach (14-day window, zero chat content) ---
    malformed_coach_rows = 0
    coach_active_14d = 0
    coach_user_14d = 0
    coach_guest_14d = 0
    coach_unique_users = set()
    coach_messages_14d = 0

    for sid, uid, msg_raw, upd_at, _crt_at in snap['coach_sessions']:
        u_ts = int(upd_at or 0)
        if u_ts < coach_cut:
            continue
        coach_active_14d += 1
        if uid is not None or str(sid or '').startswith('user_'):
            coach_user_14d += 1
            if uid is not None:
                coach_unique_users.add(int(uid))
        else:
            coach_guest_14d += 1
        if msg_raw:
            try:
                parsed_msgs = json.loads(msg_raw)
                if isinstance(parsed_msgs, list):
                    coach_messages_14d += len(parsed_msgs)
                else:
                    malformed_coach_rows += 1
            except Exception:
                malformed_coach_rows += 1

    # --- 6. Monetization & Payments ---
    pay_period_counts = {'paid': 0, 'pending': 0, 'canceled': 0}
    pay_all_counts = {'paid': 0, 'pending': 0, 'canceled': 0}
    rev_period = 0
    rev_all = 0
    for _uid, _plan, _days, amount, _curr, _prov, status, created_at in snap['payments']:
        st = str(status or 'pending').strip().lower()
        amt = int(amount or 0)
        c_ts = int(created_at or 0)
        if st in pay_all_counts:
            pay_all_counts[st] += 1
        if st == 'paid':
            rev_all += amt
        if c_ts >= period_start:
            if st in pay_period_counts:
                pay_period_counts[st] += 1
            if st == 'paid':
                rev_period += amt

    # --- 7. Moderation (aggregates only, zero text/names) ---
    rep_counts = {'all': 0, 'new': 0, 'reviewed': 0, 'closed': 0}
    rep_in_period = 0
    review_durations_sec = []
    for status, created_at, reviewed_at in snap['user_reports']:
        st = str(status or 'new').strip().lower()
        c_ts = int(created_at or 0)
        r_ts = int(reviewed_at or 0)
        rep_counts['all'] += 1
        if st in rep_counts:
            rep_counts[st] += 1
        if c_ts >= period_start:
            rep_in_period += 1
        if r_ts > 0 and c_ts > 0 and r_ts >= c_ts:
            review_durations_sec.append(r_ts - c_ts)

    avg_review_hours = round((sum(review_durations_sec) / len(review_durations_sec)) / 3600.0, 1) if review_durations_sec else None

    rpe_period_sum = sum(rpe_period.values())
    rpe_total_sum = sum(rpe_total.values())

    feature_usage = query_feature_usage(db_file, db_lock, days=period_days, now_ts=now)

    return {
        'ok': True,
        'degraded': False,
        'periodDays': period_days,
        'generatedAt': updated_iso,
        'generatedAtTs': now,
        'freeAccessMode': bool(free_access_mode),
        'dataQuality': {
            'dbHealth': 'ok',
            'missingTables': snap['missingTables'],
            'malformedStateRows': malformed_state_rows,
            'malformedCoachRows': malformed_coach_rows,
            'generatedAt': updated_iso,
            'periodDays': period_days,
        },
        'registrations': {
            'status': 'ok',
            'source': 'flexa.db:users',
            'updatedAt': updated_iso,
            'definition': 'Количество записей в таблице users по полю created_at',
            'limitations': 'Не учитывает неавторизованных гостей; историческая разбивка зависит от created_at.',
            'totalUsers': total_users,
            'activeUsers': active_users,
            'blockedUsers': blocked_users,
            'newInPeriod': new_in_period,
            'byAuthMethod': {'telegram': auth_tg, 'password': auth_pw},
            'dailySeries': [{'date': d, 'count': reg_buckets[d]} for d in reg_dates],
        },
        'engagement': {
            'lastLoginActivity': {
                'status': 'ok' if total_users > 0 else 'insufficient_data',
                'isProxy': True,
                'metricType': 'last_login_proxy',
                'source': 'flexa.db:users.last_login_at (активные, не заблокированы)',
                'updatedAt': updated_iso,
                'definition': 'Прокси недавности входа: активные аккаунты, у которых единственное поле last_login_at попадает в 24ч / 7д / 30д. Не является точным историческим DAU/WAU/MAU.',
                'limitations': 'БД хранит только время последнего входа (перезаписывается новым входом), без истории отдельных логин-сессий; пользователи без повторного входа после регистрации или с более поздним логином искажают исторические окна.',
                'last24h': last_login_24h,
                'last7d': last_login_7d,
                'last30d': last_login_30d,
            },
            'workoutActivity': {
                'status': 'ok' if total_users > 0 else 'insufficient_data',
                'isProxy': False,
                'metricType': 'workout_history',
                'source': 'flexa.db:user_state.hist',
                'updatedAt': updated_iso,
                'definition': 'Фактическая активность тренировок: уникальные аккаунты с синхронизированными записями в hist за 24ч (DAU) / 7д (WAU) / 30д (MAU)',
                'limitations': 'Учитываются только авторизованные аккаунты, выполнившие синхронизацию user_state.',
                'dau': workout_dau,
                'wau': workout_wau,
                'mau': workout_mau,
                'workoutsInPeriod': workouts_in_period,
                'workoutsTotal': workouts_total,
                'medianDurationSec': round(statistics.median(durations_period)) if durations_period else None,
            },
        },
        'retention': {
            'workoutRetention': {
                'status': 'ok' if any(v['status'] == 'ok' for v in workout_retention.values()) else 'insufficient_data',
                'isProxy': False,
                'metricType': 'workout_cohort_retention',
                'source': 'flexa.db:users.created_at + user_state.hist',
                'updatedAt': updated_iso,
                'definition': 'Доля пользователей зрелой когорты (возраст >= N+1 полных дней), зафиксировавших тренировку в точное окно [N, N+1) дней после регистрации (День 0 не засчитывается).',
                'limitations': 'Аккаунты, не завершившие окно наблюдения (возраст < N+1 дн.), строго исключены из знаменателя; при cohortSize=0 возвращается insufficient_data.',
                **workout_retention,
            },
            'lastLoginReturnProxy': {
                'status': 'ok' if any(v['status'] == 'ok' for v in last_login_return_proxy.values()) else 'insufficient_data',
                'isProxy': True,
                'metricType': 'last_login_return_proxy',
                'source': 'flexa.db:users.created_at + users.last_login_at',
                'updatedAt': updated_iso,
                'definition': 'Rolling-прокси возврата в аккаунт: доля зрелой когорты (>= N+1 дн.), у которой last_login_at >= created_at + N дней (не является точным D-retention).',
                'limitations': 'last_login_at перезаписывается при каждом входе и не фиксирует посещения в конкретный день N; неполные когорты (< N+1 дн.) исключены из знаменателя.',
                **last_login_return_proxy,
            },
        },
        'activation': {
            'status': 'ok' if total_users > 0 else 'insufficient_data',
            'source': 'flexa.db:users + user_state',
            'updatedAt': updated_iso,
            'definition': 'Доля пользователей с >=1 тренировкой, заполненным fitnessProfile или начатой программой',
            'limitations': 'Нет данных о локальном прогрессе гостей без регистрации.',
            'totalUsers': total_users,
            'firstWorkoutUsers': first_workout_users,
            'firstWorkoutRatePct': _pct(first_workout_users, total_users),
            'profileCompletedUsers': profile_completed_users,
            'profileCompletedRatePct': _pct(profile_completed_users, total_users),
            'programStartedUsers': program_started_users,
            'programStartedRatePct': _pct(program_started_users, total_users),
        },
        'workouts': {
            'status': 'ok' if workouts_total > 0 else 'insufficient_data',
            'source': 'flexa.db:user_state.hist',
            'updatedAt': updated_iso,
            'definition': 'Количество завершённых тренировок и длительность сессий в user_state.hist',
            'limitations': 'Записи без корректного поля времени t учитываются в общем итоге, но не попадают в дневной ряд периода.',
            'completedTotal': workouts_total,
            'completedInPeriod': workouts_in_period,
            'medianDurationSec': round(statistics.median(durations_period)) if durations_period else None,
            'avgExercisesPerWorkout': round(sum(ex_counts_period) / len(ex_counts_period), 1) if ex_counts_period else None,
            'dailySeries': [{'date': d, 'count': wo_buckets[d]} for d in wo_dates],
        },
        'popularCatalog': {
            'status': 'ok' if (top_programs or top_workouts) else 'insufficient_data',
            'source': 'flexa.db:user_state + site/data.json + overrides.json',
            'updatedAt': updated_iso,
            'definition': 'Топ-10 публичных программ и тренировок каталога по данным синхронизированных пользователей',
            'limitations': 'Пользовательские кастомные тренировки исключены ради приватности и чистоты каталога.',
            'topPrograms': top_programs,
            'topWorkouts': top_workouts,
        },
        'rpeDistribution': {
            'status': 'ok' if rpe_total_sum > 0 else 'insufficient_data',
            'source': 'flexa.db:user_state.hist[*].rpe',
            'updatedAt': updated_iso,
            'definition': 'Оценка сложности тренировок (easy / good / hard / unrated)',
            'limitations': 'RPE является необязательной отметкой после завершения тренировки.',
            'periodTotal': rpe_period_sum,
            'allTimeTotal': rpe_total_sum,
            'period': {
                k: {'count': rpe_period[k], 'pct': _pct(rpe_period[k], rpe_period_sum)}
                for k in ('easy', 'good', 'hard', 'unrated')
            },
            'allTime': {
                k: {'count': rpe_total[k], 'pct': _pct(rpe_total[k], rpe_total_sum)}
                for k in ('easy', 'good', 'hard', 'unrated')
            },
        },
        'userProfiles': {
            'status': 'ok' if filled_profiles_count > 0 else 'insufficient_data',
            'source': 'flexa.db:user_state.fitnessProfile',
            'updatedAt': updated_iso,
            'definition': 'Распределение целей и уровней подготовки пользователей',
            'limitations': 'Учитываются только аккаунты с заполненным fitnessProfile.',
            'filledProfilesCount': filled_profiles_count,
            'goals': goal_counts,
            'levels': level_counts,
        },
        'aiCoach': {
            'status': 'ok' if coach_active_14d > 0 else 'insufficient_data',
            'source': 'flexa.db:coach_sessions (14d window)',
            'updatedAt': updated_iso,
            'definition': 'Активность сессий AI Coach за доступное 14-дневное окно (только счётчики, без текстов переписки)',
            'limitations': 'server.py очищает coach_sessions старше 14 дней при запуске; долгосрочная история недоступна.',
            'windowDays': COACH_WINDOW_DAYS,
            'activeSessions14d': coach_active_14d,
            'userSessions14d': coach_user_14d,
            'guestSessions14d': coach_guest_14d,
            'uniqueRegisteredUsers14d': len(coach_unique_users),
            'totalMessages14d': coach_messages_14d,
            'avgMessagesPerSession': round(coach_messages_14d / coach_active_14d, 1) if coach_active_14d > 0 else None,
            'adoptionRatePct': _pct(len(coach_unique_users), total_users),
        },
        'featureUsage': feature_usage,
        'monetization': {
            'status': 'ok',
            'source': 'flexa.db:users + payments + FREE_ACCESS_MODE',
            'updatedAt': updated_iso,
            'definition': 'Реальные активные PRO-подписки, платежи по статусам и статус режима бесплатного доступа',
            'limitations': 'При FREE_ACCESS_MODE=True все пользователи получают PRO-функции бесплатно и оплата через YooKassa отключена.',
            'freeAccessMode': bool(free_access_mode),
            'realProUsersActive': real_pro_active,
            'paymentsInPeriodByStatus': pay_period_counts,
            'paymentsAllTimeByStatus': pay_all_counts,
            'paidRevenueInPeriod': rev_period,
            'paidRevenueAllTime': rev_all,
        },
        'moderation': {
            'status': 'ok',
            'source': 'flexa.db:user_reports + friendships + user_blocks',
            'updatedAt': updated_iso,
            'definition': 'Агрегированная статистика жалоб, дружбы и блокировок без персональных текстов',
            'limitations': 'Тексты жалоб и сообщений не передаются в Growth-аналитику.',
            'reportsByStatus': rep_counts,
            'reportsInPeriod': rep_in_period,
            'avgReviewTimeHours': avg_review_hours,
            'acceptedFriendships': snap['friend_accepted'],
            'activeBlocks': snap['blocks_count'],
        },
        'externalSources': _external_sources_block(updated_iso),
    }


def compute_overview(
    db_file,
    db_lock,
    *,
    site_dir='',
    content_dir='',
    free_access_mode=True,
    days=30,
    now_ts=None,
):
    """Build Dashboard overview combining deterministic KPIs, attention alerts, and recent audit."""
    now = int(now_ts if now_ts is not None else time.time())
    analytics = compute_analytics(
        db_file,
        db_lock,
        site_dir=site_dir,
        content_dir=content_dir,
        free_access_mode=free_access_mode,
        days=days,
        now_ts=now,
    )
    audit = query_audit_log(db_file, db_lock, limit=5, offset=0, now_ts=now)
    updated_iso = analytics['generatedAt']

    if analytics.get('degraded'):
        kpis = [
            {
                'id': 'users_total',
                'label': 'Пользователи (всего)',
                'value': 'Нет данных',
                'delta': '',
                'source': 'flexa.db:users',
                'updatedAt': updated_iso,
                'status': 'unavailable',
                'definition': analytics['dataQuality'].get('error', 'БД недоступна'),
            },
            {
                'id': 'last_login_7d_proxy',
                'label': 'Последний вход за 7д (прокси)',
                'value': 'Нет данных',
                'delta': '',
                'source': 'flexa.db:users.last_login_at',
                'updatedAt': updated_iso,
                'status': 'unavailable',
                'isProxy': True,
            },
            {
                'id': 'workout_wau',
                'label': 'Тренировки WAU (7д)',
                'value': 'Нет данных',
                'delta': '',
                'source': 'flexa.db:user_state.hist',
                'updatedAt': updated_iso,
                'status': 'unavailable',
            },
            {
                'id': 'coach_14d',
                'label': 'AI Coach (14д)',
                'value': 'Нет данных',
                'delta': '',
                'source': 'flexa.db:coach_sessions (14d)',
                'updatedAt': updated_iso,
                'status': 'unavailable',
            },
        ]
        attention = [{
            'id': 'db_degraded',
            'severity': 'high',
            'title': 'База данных аналитики недоступна',
            'details': analytics['dataQuality'].get('error', 'Проверьте файл flexa.db.'),
            'source': 'flexa.db',
        }]
    else:
        reg = analytics['registrations']
        l_eng = analytics['engagement']['lastLoginActivity']
        w_eng = analytics['engagement']['workoutActivity']
        act = analytics['activation']
        coach = analytics['aiCoach']
        mod = analytics['moderation']
        mon = analytics['monetization']

        act_pct = act.get('firstWorkoutRatePct')
        kpis = [
            {
                'id': 'users_total',
                'label': 'Пользователи (всего)',
                'value': str(reg['totalUsers']),
                'delta': f"+{reg['newInPeriod']} за {analytics['periodDays']}д",
                'source': reg['source'],
                'updatedAt': updated_iso,
                'status': reg['status'],
                'definition': reg['definition'],
            },
            {
                'id': 'last_login_7d_proxy',
                'label': 'Последний вход за 7д (прокси)',
                'value': str(l_eng['last7d']),
                'delta': f"24ч: {l_eng['last24h']} · 30д: {l_eng['last30d']} (прокси)",
                'source': l_eng['source'],
                'updatedAt': updated_iso,
                'status': l_eng['status'],
                'definition': l_eng['definition'],
                'isProxy': True,
            },
            {
                'id': 'workout_wau',
                'label': 'Тренировались WAU (7д)',
                'value': str(w_eng['wau']),
                'delta': f"{w_eng['workoutsInPeriod']} трен. за {analytics['periodDays']}д",
                'source': w_eng['source'],
                'updatedAt': updated_iso,
                'status': w_eng['status'],
                'definition': w_eng['definition'],
            },
            {
                'id': 'activation_workout',
                'label': 'Активация (≥1 тренировка)',
                'value': f'{act_pct}%' if act_pct is not None else 'Нет данных',
                'delta': f"{act['firstWorkoutUsers']} из {act['totalUsers']}",
                'source': act['source'],
                'updatedAt': updated_iso,
                'status': act['status'],
                'definition': act['definition'],
            },
            {
                'id': 'coach_14d',
                'label': 'Сессии AI Coach (14д)',
                'value': str(coach['activeSessions14d']),
                'delta': f"акк: {coach['userSessions14d']} · гости: {coach['guestSessions14d']}",
                'source': coach['source'],
                'updatedAt': updated_iso,
                'status': coach['status'],
                'definition': coach['definition'],
            },
            {
                'id': 'moderation_open',
                'label': 'Открытые жалобы',
                'value': str(mod['reportsByStatus']['new']),
                'delta': f"всего жалоб: {mod['reportsByStatus']['all']}",
                'source': mod['source'],
                'updatedAt': updated_iso,
                'status': 'ok',
                'definition': mod['definition'],
            },
        ]

        attention = []
        if mod['reportsByStatus']['new'] > 0:
            attention.append({
                'id': 'open_reports',
                'severity': 'high',
                'title': f"Нерассмотренные жалобы: {mod['reportsByStatus']['new']}",
                'details': 'Перейдите в раздел «Жалобы» админ-панели для модерации.',
                'source': 'flexa.db:user_reports',
            })
        if mon['freeAccessMode']:
            attention.append({
                'id': 'free_access_mode',
                'severity': 'info',
                'title': 'Активен режим бесплатного доступа (FREE_ACCESS_MODE)',
                'details': 'Все пользователи получают PRO-функции бесплатно; платежи YooKassa отключены. Реальных PRO в БД: ' + str(mon['realProUsersActive']),
                'source': 'env:FLEXA_FREE_MODE',
            })
        dq = analytics['dataQuality']
        if (dq['malformedStateRows'] or 0) > 0 or (dq['malformedCoachRows'] or 0) > 0:
            attention.append({
                'id': 'malformed_json',
                'severity': 'medium',
                'title': 'Обнаружены повреждённые JSON-строки состояния',
                'details': f"user_state: {dq['malformedStateRows']}, coach_sessions: {dq['malformedCoachRows']} (безопасно пропущены).",
                'source': 'flexa.db',
            })
        if reg['totalUsers'] > 0 and act_pct is not None and act_pct < 30.0:
            attention.append({
                'id': 'low_activation',
                'severity': 'medium',
                'title': f'Низкая активация в первую тренировку ({act_pct}%)',
                'details': f"Только {act['firstWorkoutUsers']} из {reg['totalUsers']} зарегистрированных пользователей синхронизировали тренировку.",
                'source': 'flexa.db:user_state',
            })
        attention.append({
            'id': 'external_analytics_unavailable',
            'severity': 'info',
            'title': 'Внешние источники трафика (GA4 / Search Console) не подключены',
            'details': 'Отказы, поисковые запросы и гостевая воронка помечены статусом unavailable и не подменяются нулями.',
            'source': 'externalSources',
        })

    return {
        'ok': True,
        'degraded': bool(analytics.get('degraded')),
        'periodDays': analytics['periodDays'],
        'generatedAt': updated_iso,
        'generatedAtTs': now,
        'systemStatus': {
            'dbHealth': analytics['dataQuality']['dbHealth'],
            'freeAccessMode': bool(free_access_mode),
            'aiGrowthLlm': 'disabled_pr41',
            'auditAppendOnly': bool(audit.get('appendOnlyEnforced')),
            'auditTotal': int(audit.get('total') or 0),
        },
        'kpis': kpis,
        'attentionItems': attention,
        'recentAudit': audit.get('entries', []),
        'auditStatus': audit.get('status', 'ok'),
        'externalSources': analytics['externalSources'],
        'modules': [
            {'id': 'dashboard', 'title': 'Dashboard', 'status': 'done', 'statusLabel': 'PR 4.1 активен'},
            {'id': 'analytics', 'title': 'Analytics', 'status': 'done', 'statusLabel': 'PR 4.1 активен'},
            {'id': 'audit', 'title': 'Audit Log', 'status': 'done', 'statusLabel': 'PR 4.1 активен'},
            {'id': 'seo', 'title': 'SEO Audit', 'status': 'done', 'statusLabel': 'PR 4.2 активен'},
            {'id': 'tasks', 'title': 'Task Manager', 'status': 'done', 'statusLabel': 'PR 4.2 активен'},
            {'id': 'proposals', 'title': 'Proposals & Diff', 'status': 'done', 'statusLabel': 'PR 4.2 активен'},
            {'id': 'reports', 'title': 'Reports AI', 'status': 'draft', 'statusLabel': 'План PR 4.3'},
            {'id': 'content', 'title': 'Content AI', 'status': 'draft', 'statusLabel': 'План PR 4.4'},
            {'id': 'social', 'title': 'Social AI', 'status': 'draft', 'statusLabel': 'План PR 4.5'},
        ],
    }
