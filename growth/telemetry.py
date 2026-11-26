"""PII-free aggregated feature usage telemetry for RizzaFit AI Growth (PR 4.3)."""

import contextlib
import datetime
import json
import os
import sqlite3
import threading
import time

from .db import init_growth_db

MAX_TELEMETRY_BODY = 1024
TELEMETRY_RATE_LIMIT_MAX = 30
TELEMETRY_RATE_LIMIT_WINDOW = 60
MAX_RL_CAPACITY = 500

ALLOWED_TELEMETRY_EVENTS = {
    'coach_open': 'Открытие AI Coach',
    'coach_message_sent': 'Сообщения в AI Coach',
    'coach_ref_click': 'Переходы по карточкам AI Coach',
    'program_select': 'Выбор программы тренировок',
    'program_day_complete': 'Отметка дня программы',
    'workout_start': 'Запуск тренировки',
    'workout_complete': 'Завершение тренировки',
    'profile_completed': 'Сохранение fitnessProfile',
    'reminder_toggle': 'Настройка напоминаний',
    'seo_landing_cta': 'Переход с SEO-лендинга в приложение',
}

_rl_lock = threading.Lock()
_rl_hits = {}


def reset_rate_limiter():
    """Clear in-memory telemetry rate limiter buckets (used in unit tests)."""
    with _rl_lock:
        _rl_hits.clear()


def _check_rate_limit(client_ip, *, now_ts=None):
    """Volatile per-IP sliding window limit; never stores IPs on disk."""
    key = str(client_ip or 'unknown')[:64]
    now = float(now_ts if now_ts is not None else time.time())
    cutoff = now - TELEMETRY_RATE_LIMIT_WINDOW
    with _rl_lock:
        if len(_rl_hits) > MAX_RL_CAPACITY:
            stale = [k for k, ts_list in _rl_hits.items() if not ts_list or ts_list[-1] < cutoff]
            for k in stale:
                _rl_hits.pop(k, None)
            if len(_rl_hits) > MAX_RL_CAPACITY:
                _rl_hits.clear()
        recent = [t for t in _rl_hits.get(key, ()) if t >= cutoff]
        if len(recent) >= TELEMETRY_RATE_LIMIT_MAX:
            _rl_hits[key] = recent
            return False
        recent.append(now)
        _rl_hits[key] = recent
        return True


def validate_telemetry_payload(payload):
    """Allow strictly {'event': '<allowlisted_key>'} with zero extra fields or PII."""
    if not isinstance(payload, dict):
        raise ValueError('Тело запроса должно быть JSON-объектом')
    keys = set(payload.keys())
    if keys != {'event'}:
        extra = sorted(keys - {'event'})
        if extra:
            raise ValueError('Запрещённые поля телеметрии: ' + ', '.join(extra))
        raise ValueError('Отсутствует обязательное поле event')
    ev = payload.get('event')
    if not isinstance(ev, str):
        raise ValueError('Поле event должно быть строкой')
    if not ev or ev != ev.strip() or ev not in ALLOWED_TELEMETRY_EVENTS:
        raise ValueError('Недопустимый тип события телеметрии')
    return ev


def _fmt_utc_date(ts):
    return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%d')


def _fmt_utc_iso(ts):
    return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def record_feature_event(db_file, db_lock, event_key, *, now_ts=None):
    """Atomically increment daily counter for allowlisted event without storing user identity."""
    if event_key not in ALLOWED_TELEMETRY_EVENTS:
        raise ValueError('Недопустимый тип события телеметрии')
    ts = int(now_ts if now_ts is not None else time.time())
    date_utc = _fmt_utc_date(ts)
    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        init_growth_db(conn)
        conn.execute(
            'INSERT INTO growth_feature_daily (date_utc, event_key, event_count, updated_at) '
            'VALUES (?, ?, 1, ?) '
            'ON CONFLICT(date_utc, event_key) DO UPDATE SET '
            'event_count = event_count + 1, updated_at = excluded.updated_at',
            (date_utc, event_key, ts),
        )
        conn.commit()
    return {'dateUtc': date_utc, 'event': event_key}


def handle_telemetry_post(handler, *, db_file, db_lock, client_ip=''):
    """Handle POST /api/telemetry/event safely with size cap, rate limit, and allowlist."""
    if not _check_rate_limit(client_ip):
        return handler.send_j(429, {'error': 'rate_limit_exceeded'})

    raw = handler.body(MAX_TELEMETRY_BODY)
    if raw is None:
        return handler.send_j(413, {'error': 'request body too large'})
    if not raw or not raw.strip():
        return handler.send_j(400, {'error': 'empty json body'})

    try:
        payload = json.loads(raw.decode('utf-8'))
    except Exception:
        return handler.send_j(400, {'error': 'bad json'})

    try:
        ev = validate_telemetry_payload(payload)
    except ValueError as e:
        return handler.send_j(400, {'error': str(e)})

    record_feature_event(db_file, db_lock, ev)
    return handler.send_j(202, {'ok': True, 'recorded': True})


def query_feature_usage(db_file, db_lock, *, days=30, now_ts=None):
    """Read aggregated daily feature counters (strictly PII-free, read-only)."""
    period_days = days if days in (7, 30, 90) else 30
    now = int(now_ts if now_ts is not None else time.time())
    updated_iso = _fmt_utc_iso(now)

    end_dt = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).date()
    dates = [(end_dt - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(period_days - 1, -1, -1)]
    date_set = set(dates)
    daily_totals = {d: 0 for d in dates}

    if not db_file or not os.path.isfile(db_file):
        return {
            'status': 'unavailable',
            'source': 'flexa.db:growth_feature_daily',
            'updatedAt': updated_iso,
            'definition': 'Агрегированные суточные счётчики использования функций RizzaFit (без PII).',
            'limitations': 'База данных не найдена.',
            'piiStored': False,
            'totalInPeriod': 0,
            'totalAllTime': 0,
            'byEvent': [],
            'dailySeries': [{'date': d, 'count': 0} for d in dates],
        }

    period_by_ev = {k: 0 for k in ALLOWED_TELEMETRY_EVENTS}
    all_by_ev = {k: 0 for k in ALLOWED_TELEMETRY_EVENTS}

    try:
        with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
            tbl = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_feature_daily'"
            ).fetchone()
            if not tbl:
                return {
                    'status': 'insufficient_data',
                    'source': 'flexa.db:growth_feature_daily',
                    'updatedAt': updated_iso,
                    'definition': 'Агрегированные суточные счётчики использования функций RizzaFit (без PII).',
                    'limitations': 'События телеметрии ещё не поступали.',
                    'piiStored': False,
                    'totalInPeriod': 0,
                    'totalAllTime': 0,
                    'byEvent': [
                        {'key': k, 'label': lbl, 'countPeriod': 0, 'countAllTime': 0}
                        for k, lbl in ALLOWED_TELEMETRY_EVENTS.items()
                    ],
                    'dailySeries': [{'date': d, 'count': 0} for d in dates],
                }
            rows = conn.execute(
                'SELECT date_utc, event_key, event_count FROM growth_feature_daily'
            ).fetchall()
    except sqlite3.Error:
        return {
            'status': 'unavailable',
            'source': 'flexa.db:growth_feature_daily',
            'updatedAt': updated_iso,
            'definition': 'Агрегированные суточные счётчики использования функций RizzaFit (без PII).',
            'limitations': 'Ошибка чтения таблицы телеметрии.',
            'piiStored': False,
            'totalInPeriod': 0,
            'totalAllTime': 0,
            'byEvent': [],
            'dailySeries': [{'date': d, 'count': 0} for d in dates],
        }

    for date_utc, ev_key, ev_cnt in rows:
        k = str(ev_key or '')
        if k not in ALLOWED_TELEMETRY_EVENTS:
            continue
        cnt = max(0, int(ev_cnt or 0))
        all_by_ev[k] += cnt
        if str(date_utc or '') in date_set:
            period_by_ev[k] += cnt
            daily_totals[str(date_utc)] += cnt

    total_period = sum(period_by_ev.values())
    total_all = sum(all_by_ev.values())
    by_event = [
        {
            'key': k,
            'label': lbl,
            'countPeriod': period_by_ev[k],
            'countAllTime': all_by_ev[k],
        }
        for k, lbl in ALLOWED_TELEMETRY_EVENTS.items()
    ]
    by_event.sort(key=lambda x: (-x['countPeriod'], -x['countAllTime'], x['key']))

    return {
        'status': 'ok' if total_all > 0 else 'insufficient_data',
        'source': 'flexa.db:growth_feature_daily',
        'updatedAt': updated_iso,
        'definition': 'Агрегированные суточные счётчики использования функций RizzaFit без хранения IP, email, user ID и токенов.',
        'limitations': 'Только события из строгого allowlist (10 ключей); блокировщики и офлайн-режим могут снижать полноту.',
        'piiStored': False,
        'totalInPeriod': total_period,
        'totalAllTime': total_all,
        'byEvent': by_event,
        'dailySeries': [{'date': d, 'count': daily_totals[d]} for d in dates],
    }
