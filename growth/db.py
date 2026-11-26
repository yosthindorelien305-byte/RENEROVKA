"""Server-side append-only SQLite storage for RizzaFit AI Growth."""

import contextlib
import datetime
import json
import os
import re
import sqlite3
import time

SENSITIVE_KEY_PARTS = (
    'password', 'passwd', 'pw_', '_pw', 'token', 'secret', 'api_key', 'apikey',
    'email', 'mail', 'phone', 'auth', 'cookie', 'init_data', 'initdata',
    'messages', 'message_text', 'body', 'reason', 'admin_note',
)
EMAIL_SCRUB_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
BEARER_SCRUB_RE = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}')
BOT_TOKEN_SCRUB_RE = re.compile(r'\b\d{6,12}:[A-Za-z0-9_-]{20,}\b')

AUDIT_SOURCE_ID = 'flexa.db:growth_audit_log'


def init_growth_db(conn):
    """Create append-only growth_audit_log table, indexes, and SQLite triggers."""
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_audit_log ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'created_at INTEGER NOT NULL, '
        'actor TEXT NOT NULL DEFAULT "admin", '
        'actor_ip TEXT NOT NULL DEFAULT "", '
        'action TEXT NOT NULL, '
        'module TEXT NOT NULL DEFAULT "growth", '
        'target TEXT NOT NULL DEFAULT "", '
        'status TEXT NOT NULL DEFAULT "ok", '
        'details_json TEXT NOT NULL DEFAULT "{}", '
        'backup_ref TEXT NOT NULL DEFAULT "")'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_audit_created ON growth_audit_log(created_at DESC, id DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_audit_module ON growth_audit_log(module, id DESC)')
    conn.execute(
        'CREATE TRIGGER IF NOT EXISTS trg_growth_audit_no_update '
        'BEFORE UPDATE ON growth_audit_log '
        'BEGIN '
        '  SELECT RAISE(ABORT, "growth_audit_log is append-only: UPDATE forbidden"); '
        'END;'
    )
    conn.execute(
        'CREATE TRIGGER IF NOT EXISTS trg_growth_audit_no_delete '
        'BEFORE DELETE ON growth_audit_log '
        'BEGIN '
        '  SELECT RAISE(ABORT, "growth_audit_log is append-only: DELETE forbidden"); '
        'END;'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_tasks ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'title TEXT NOT NULL, '
        'description TEXT NOT NULL DEFAULT "", '
        'category TEXT NOT NULL DEFAULT "Other", '
        'priority TEXT NOT NULL DEFAULT "medium", '
        'status TEXT NOT NULL DEFAULT "open", '
        'seo_audit_run_id INTEGER, '
        'seo_issue_id INTEGER, '
        'target_url TEXT NOT NULL DEFAULT "", '
        'created_by TEXT NOT NULL DEFAULT "admin", '
        'created_at INTEGER NOT NULL, '
        'updated_at INTEGER NOT NULL, '
        'completed_at INTEGER)'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_tasks_status ON growth_tasks(status, priority, id DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_tasks_cat ON growth_tasks(category, id DESC)')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_task_history ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'task_id INTEGER NOT NULL, '
        'field_name TEXT NOT NULL, '
        'old_value TEXT NOT NULL DEFAULT "", '
        'new_value TEXT NOT NULL DEFAULT "", '
        'actor TEXT NOT NULL DEFAULT "admin", '
        'note TEXT NOT NULL DEFAULT "", '
        'created_at INTEGER NOT NULL)'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_task_history_tid ON growth_task_history(task_id, id DESC)')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_seo_audit_runs ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'created_at INTEGER NOT NULL, '
        'pages_checked INTEGER NOT NULL DEFAULT 0, '
        'issues_total INTEGER NOT NULL DEFAULT 0, '
        'summary_json TEXT NOT NULL DEFAULT "{}", '
        'checks_json TEXT NOT NULL DEFAULT "{}")'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_seo_issues ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'run_id INTEGER NOT NULL, '
        'page_url TEXT NOT NULL, '
        'issue_type TEXT NOT NULL, '
        'severity TEXT NOT NULL, '
        'status TEXT NOT NULL DEFAULT "open", '
        'description TEXT NOT NULL, '
        'recommendation TEXT NOT NULL, '
        'field_name TEXT NOT NULL DEFAULT "", '
        'current_value TEXT NOT NULL DEFAULT "", '
        'checked_at INTEGER NOT NULL)'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_seo_issues_run ON growth_seo_issues(run_id, id ASC)')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_proposals ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'task_id INTEGER, '
        'target_object TEXT NOT NULL, '
        'field_name TEXT NOT NULL DEFAULT "content", '
        'current_value TEXT NOT NULL DEFAULT "", '
        'proposed_value TEXT NOT NULL, '
        'reason TEXT NOT NULL, '
        'status TEXT NOT NULL DEFAULT "pending", '
        'reviewed_by TEXT NOT NULL DEFAULT "", '
        'review_note TEXT NOT NULL DEFAULT "", '
        'reviewed_at INTEGER, '
        'applied_at INTEGER, '
        'created_by TEXT NOT NULL DEFAULT "admin", '
        'created_at INTEGER NOT NULL, '
        'updated_at INTEGER NOT NULL)'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_proposals_status ON growth_proposals(status, id DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_proposals_task ON growth_proposals(task_id, id DESC)')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_proposal_history ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'proposal_id INTEGER NOT NULL, '
        'action TEXT NOT NULL, '
        'old_status TEXT NOT NULL DEFAULT "", '
        'new_status TEXT NOT NULL DEFAULT "", '
        'actor TEXT NOT NULL DEFAULT "admin", '
        'note TEXT NOT NULL DEFAULT "", '
        'created_at INTEGER NOT NULL)'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_prop_hist_pid ON growth_proposal_history(proposal_id, id DESC)')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS growth_feature_daily ('
        'date_utc TEXT NOT NULL, '
        'event_key TEXT NOT NULL, '
        'event_count INTEGER NOT NULL DEFAULT 0, '
        'updated_at INTEGER NOT NULL, '
        'PRIMARY KEY (date_utc, event_key))'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_growth_feature_daily_date ON growth_feature_daily(date_utc DESC)')


def _scrub_text(val, max_len=240):
    """Remove control chars, emails, bearer/bot tokens, and bound string length."""
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]+', ' ', str(val or '')).strip()
    s = EMAIL_SCRUB_RE.sub('[redacted-email]', s)
    s = BEARER_SCRUB_RE.sub(r'\1[redacted-token]', s)
    s = BOT_TOKEN_SCRUB_RE.sub('[redacted-bot-token]', s)
    if len(s) > max_len:
        s = s[:max_len].rstrip() + '…'
    return s


def _is_sensitive_key(key_str):
    lk = str(key_str or '').strip().lower()
    if lk in ('pw', 'key', 'secret', 'token', 'password', 'email', 'phone'):
        return True
    return any(part in lk for part in SENSITIVE_KEY_PARTS)


def _sanitize_value(val, depth=0):
    if depth > 3:
        return _scrub_text(val, max_len=120)
    if val is None or isinstance(val, (bool, int)):
        return val
    if isinstance(val, float):
        return round(val, 4)
    if isinstance(val, str):
        return _scrub_text(val, max_len=240)
    if isinstance(val, list):
        return [_sanitize_value(item, depth + 1) for item in val[:15]]
    if isinstance(val, dict):
        out = {}
        for idx, (k, v) in enumerate(val.items()):
            if idx >= 25:
                break
            ks = _scrub_text(k, max_len=60)
            if not ks or _is_sensitive_key(ks):
                continue
            out[ks] = _sanitize_value(v, depth + 1)
        return out
    return _scrub_text(val, max_len=120)


def sanitize_audit_details(details):
    """Produce compact, PII/secret-free JSON string (<= 2000 bytes) for audit log storage."""
    if details is None:
        cleaned = {}
    elif isinstance(details, str):
        txt = _scrub_text(details, max_len=400)
        cleaned = {'note': txt} if txt else {}
    elif isinstance(details, dict):
        cleaned = _sanitize_value(details, depth=0)
    else:
        cleaned = {'value': _scrub_text(details, max_len=240)}

    raw = json.dumps(cleaned, ensure_ascii=False, separators=(',', ':'))
    if len(raw.encode('utf-8')) > 2000:
        summary = {'truncated': True, 'preview': _scrub_text(raw, max_len=200)}
        raw = json.dumps(summary, ensure_ascii=False, separators=(',', ':'))
    return raw


def _format_utc_iso(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return ''


def _format_display_dt(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return ''


def record_audit_event(
    db_file,
    db_lock,
    *,
    action,
    module='growth',
    target='',
    status='ok',
    actor='admin',
    actor_ip='',
    details=None,
    backup_ref='',
    created_at=None,
):
    """Append one immutable audit event row to growth_audit_log and return its id."""
    ts = int(created_at if created_at is not None else time.time())
    actor_clean = _scrub_text(actor or 'admin', max_len=64) or 'admin'
    ip_clean = _scrub_text(actor_ip or '', max_len=64)
    action_clean = _scrub_text(action or 'event', max_len=120) or 'event'
    module_clean = re.sub(r'[^a-zA-Z0-9_-]', '', str(module or 'growth').lower())[:40] or 'growth'
    target_clean = _scrub_text(target or '', max_len=160)
    status_clean = re.sub(r'[^a-zA-Z0-9_-]', '', str(status or 'ok').lower())[:32] or 'ok'
    backup_clean = _scrub_text(backup_ref or '', max_len=200)
    details_json = sanitize_audit_details(details)

    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        init_growth_db(conn)
        cur = conn.execute(
            'INSERT INTO growth_audit_log '
            '(created_at, actor, actor_ip, action, module, target, status, details_json, backup_ref) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (ts, actor_clean, ip_clean, action_clean, module_clean, target_clean, status_clean, details_json, backup_clean),
        )
        conn.commit()
        return int(cur.lastrowid)


def _format_details_text(details_obj, row):
    parts = []
    if row['target']:
        parts.append(f"Объект: {row['target']}")
    if row['actor_ip']:
        parts.append(f"IP: {row['actor_ip']}")
    if isinstance(details_obj, dict) and details_obj:
        kv = [f'{k}={v}' for k, v in list(details_obj.items())[:8]]
        parts.append(', '.join(kv))
    if row['backup_ref']:
        parts.append(f"Backup: {row['backup_ref']}")
    return ' · '.join(parts)


def query_audit_log(db_file, db_lock, *, limit=50, offset=0, module='', status='', now_ts=None):
    """Read paginated audit log entries in reverse chronological order."""
    now = int(now_ts if now_ts is not None else time.time())
    try:
        lim = max(1, min(200, int(limit)))
    except (TypeError, ValueError):
        lim = 50
    try:
        off = max(0, int(offset))
    except (TypeError, ValueError):
        off = 0

    mod_filter = re.sub(r'[^a-zA-Z0-9_-]', '', str(module or '').strip().lower())
    st_filter = re.sub(r'[^a-zA-Z0-9_-]', '', str(status or '').strip().lower())

    if not db_file or not os.path.isfile(db_file):
        return {
            'ok': True,
            'status': 'unavailable',
            'dbHealth': 'missing',
            'appendOnlyEnforced': False,
            'source': AUDIT_SOURCE_ID,
            'updatedAt': _format_utc_iso(now),
            'updatedAtTs': now,
            'entries': [],
            'total': 0,
            'limit': lim,
            'offset': off,
            'hasMore': False,
            'error': 'База данных не найдена',
        }

    where_clauses = []
    params = []
    if mod_filter and mod_filter != 'all':
        where_clauses.append('module = ?')
        params.append(mod_filter)
    if st_filter and st_filter != 'all':
        where_clauses.append('status = ?')
        params.append(st_filter)
    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    try:
        with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            tbl = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_audit_log'"
            ).fetchone()
            if not tbl:
                return {
                    'ok': True,
                    'status': 'unavailable',
                    'dbHealth': 'missing_table',
                    'appendOnlyEnforced': False,
                    'source': AUDIT_SOURCE_ID,
                    'updatedAt': _format_utc_iso(now),
                    'updatedAtTs': now,
                    'entries': [],
                    'total': 0,
                    'limit': lim,
                    'offset': off,
                    'hasMore': False,
                    'error': 'Таблица growth_audit_log ещё не инициализирована',
                }

            trig_cnt = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='growth_audit_log' "
                "AND name IN ('trg_growth_audit_no_update', 'trg_growth_audit_no_delete')"
            ).fetchone()[0]

            total = int(conn.execute(
                f'SELECT COUNT(*) FROM growth_audit_log {where_sql}', tuple(params)
            ).fetchone()[0])

            rows = conn.execute(
                f'SELECT id, created_at, actor, actor_ip, action, module, target, status, details_json, backup_ref '
                f'FROM growth_audit_log {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?',
                tuple(params + [lim, off]),
            ).fetchall()

            mod_rows = conn.execute(
                'SELECT DISTINCT module FROM growth_audit_log ORDER BY module ASC'
            ).fetchall()
            available_modules = [str(r[0]) for r in mod_rows if r[0]]
    except sqlite3.Error:
        return {
            'ok': True,
            'status': 'unavailable',
            'dbHealth': 'corrupted',
            'appendOnlyEnforced': False,
            'source': AUDIT_SOURCE_ID,
            'updatedAt': _format_utc_iso(now),
            'updatedAtTs': now,
            'entries': [],
            'total': 0,
            'limit': lim,
            'offset': off,
            'hasMore': False,
            'error': 'Ошибка чтения growth_audit_log из SQLite',
        }

    entries = []
    for row in rows:
        try:
            details_obj = json.loads(row['details_json']) if row['details_json'] else {}
            if not isinstance(details_obj, dict):
                details_obj = {'value': details_obj}
        except Exception:
            details_obj = {'malformedDetails': True}
        created_val = int(row['created_at'] or 0)
        entries.append({
            'id': int(row['id']),
            'createdAt': created_val,
            'timestamp': _format_display_dt(created_val),
            'isoTimestamp': _format_utc_iso(created_val),
            'actor': str(row['actor'] or 'admin'),
            'actorIp': str(row['actor_ip'] or ''),
            'action': str(row['action'] or ''),
            'module': str(row['module'] or 'growth'),
            'target': str(row['target'] or ''),
            'status': str(row['status'] or 'ok'),
            'details': details_obj,
            'detailsText': _format_details_text(details_obj, row),
            'backupRef': str(row['backup_ref'] or ''),
        })

    return {
        'ok': True,
        'status': 'ok',
        'dbHealth': 'ok',
        'appendOnlyEnforced': int(trig_cnt or 0) == 2,
        'source': AUDIT_SOURCE_ID,
        'updatedAt': _format_utc_iso(now),
        'updatedAtTs': now,
        'entries': entries,
        'total': total,
        'limit': lim,
        'offset': off,
        'hasMore': (off + len(entries)) < total,
        'availableModules': available_modules,
    }
