"""AI Growth Task Manager (PR 4.2, deterministic SQLite CRUD + history + audit)."""

import contextlib
import datetime
import os
import re
import sqlite3
import time
import urllib.parse

from .db import init_growth_db, record_audit_event

TASK_STATUSES = (
    'open',
    'in_progress',
    'pending_approval',
    'approved',
    'rejected',
    'completed',
    'cancelled',
)
TASK_CATEGORIES = ('SEO', 'Content', 'Technical', 'Performance', 'Analytics', 'Other')
TASK_PRIORITIES = ('critical', 'high', 'medium', 'low')

ALLOWED_TASK_TRANSITIONS = {
    'open': {'in_progress', 'pending_approval', 'completed', 'cancelled'},
    'in_progress': {'open', 'pending_approval', 'completed', 'cancelled'},
    'pending_approval': {'approved', 'rejected', 'in_progress', 'cancelled'},
    'approved': {'in_progress', 'completed', 'cancelled'},
    'rejected': {'open', 'in_progress', 'cancelled'},
    'completed': {'open'},
    'cancelled': {'open'},
}

PRIORITY_ORDER_SQL = (
    'CASE priority WHEN "critical" THEN 1 WHEN "high" THEN 2 WHEN "medium" THEN 3 ELSE 4 END'
)


def _fmt_iso(ts):
    if not ts:
        return ''
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return ''


def _clean_text(raw, *, field, min_len=0, max_len=2000):
    if raw is None:
        s = ''
    elif isinstance(raw, str):
        s = raw.replace('\x00', '').strip()
    else:
        raise ValueError(f'Поле {field} должно быть строкой')
    if len(s) < min_len:
        raise ValueError(f'Поле {field} должно содержать минимум {min_len} симв.')
    if len(s) > max_len:
        raise ValueError(f'Поле {field} превышает лимит {max_len} симв.')
    return s


INTERNAL_URL_RE = re.compile(r'^/[A-Za-z0-9_./-]*(\?[A-Za-z0-9_=&.%-]*)?(#[A-Za-z0-9_./=-]*)?$')


def _validate_and_classify_target_url(raw):
    """Validate targetUrl and classify strictly into ('none' | 'internal' | 'external')."""
    if raw is None or raw == '':
        return '', 'none'
    if not isinstance(raw, str):
        raise ValueError('Поле targetUrl должно быть строкой')
    if '\x00' in raw or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ValueError('Поле targetUrl содержит недопустимые управляющие символы')
    s = raw.strip()
    if not s:
        return '', 'none'
    if len(s) > 300 or any(ch.isspace() for ch in s) or '\\' in s:
        raise ValueError('Некорректный формат или длина targetUrl')

    low = s.lower()
    if low.startswith(('javascript:', 'data:', 'vbscript:', 'file:', 'blob:', 'about:')):
        raise ValueError('Запрещённая URI-схема в targetUrl')
    if s.startswith('//'):
        raise ValueError('Protocol-relative URL (//host) запрещён в targetUrl')

    dec1 = urllib.parse.unquote(s)
    dec2 = urllib.parse.unquote(dec1)
    for cand in (s, dec1, dec2):
        cand_low = cand.lower()
        if '..' in cand or '\\' in cand or '\x00' in cand or any(ord(c) < 32 or ord(c) == 127 for c in cand):
            raise ValueError('Недопустимый traversal или спецсимвол в targetUrl')
        if cand_low.startswith(('javascript:', 'data:', 'vbscript:', 'file:', 'blob:', 'about:')):
            raise ValueError('Запрещённая encoded URI-схема в targetUrl')

    if s.startswith('/'):
        low_s = s.lower()
        if not INTERNAL_URL_RE.fullmatch(s) or low_s.startswith('/server_data') or low_s == '/fitify' or low_s.startswith('/fitify/'):
            raise ValueError('Недопустимый внутренний targetUrl')
        return s, 'internal'

    parsed = urllib.parse.urlparse(s)
    scheme = (parsed.scheme or '').lower()
    if scheme in ('http', 'https'):
        if parsed.username is not None or parsed.password is not None or '@' in (parsed.netloc or ''):
            raise ValueError('Userinfo (@) запрещён во внешнем targetUrl')
        try:
            _ = parsed.port
        except ValueError:
            raise ValueError('Некорректный порт во внешнем targetUrl')
        host = (parsed.hostname or '').strip()
        if not host or ('.' not in host and host != 'localhost'):
            raise ValueError('Некорректный домен во внешнем targetUrl')
        return s, 'external'

    raise ValueError('targetUrl должен быть относительным внутренним путём (/...) или http(s):// URL')


def _validate_target_url(raw):
    clean, _ = _validate_and_classify_target_url(raw)
    return clean


def _parse_optional_pos_int(val, field):
    if val is None or val == '':
        return None
    if isinstance(val, bool):
        raise ValueError(f'Некорректный {field}')
    try:
        iv = int(val)
    except (TypeError, ValueError):
        raise ValueError(f'Поле {field} должно быть целым числом')
    if iv <= 0:
        raise ValueError(f'Поле {field} должно быть > 0')
    return iv


def _row_to_task(row):
    c_at = int(row['created_at'] or 0)
    u_at = int(row['updated_at'] or 0)
    done_at = int(row['completed_at']) if row['completed_at'] else None
    t_url = str(row['target_url'] or '')
    try:
        clean_url, url_type = _validate_and_classify_target_url(t_url)
    except ValueError:
        clean_url, url_type = '', 'none'
    return {
        'id': int(row['id']),
        'title': str(row['title'] or ''),
        'description': str(row['description'] or ''),
        'category': str(row['category'] or 'Other'),
        'priority': str(row['priority'] or 'medium'),
        'status': str(row['status'] or 'open'),
        'seoAuditRunId': int(row['seo_audit_run_id']) if row['seo_audit_run_id'] is not None else None,
        'seoIssueId': int(row['seo_issue_id']) if row['seo_issue_id'] is not None else None,
        'targetUrl': clean_url,
        'targetUrlType': url_type,
        'externalNavigationDisabled': (url_type == 'external'),
        'createdBy': str(row['created_by'] or 'admin'),
        'createdAt': c_at,
        'createdAtIso': _fmt_iso(c_at),
        'updatedAt': u_at,
        'updatedAtIso': _fmt_iso(u_at),
        'completedAt': done_at,
        'completedAtIso': _fmt_iso(done_at) if done_at else '',
        'allowedTransitions': sorted(ALLOWED_TASK_TRANSITIONS.get(str(row['status'] or 'open'), set())),
    }


def list_tasks(
    db_file,
    db_lock,
    *,
    status='',
    category='',
    priority='',
    q='',
    limit=50,
    offset=0,
):
    """List Growth tasks with filters (read-only, safe if DB uninitialized)."""
    now = int(time.time())
    try:
        lim = max(1, min(200, int(limit)))
    except (TypeError, ValueError):
        lim = 50
    try:
        off = max(0, int(offset))
    except (TypeError, ValueError):
        off = 0

    st_f = str(status or '').strip().lower()
    cat_f = str(category or '').strip()
    prio_f = str(priority or '').strip().lower()
    q_f = str(q or '').strip().lower()[:120]

    if st_f and st_f != 'all' and st_f not in TASK_STATUSES:
        raise ValueError('Некорректный фильтр status')
    if cat_f and cat_f.lower() != 'all' and cat_f not in TASK_CATEGORIES:
        raise ValueError('Некорректный фильтр category')
    if prio_f and prio_f != 'all' and prio_f not in TASK_PRIORITIES:
        raise ValueError('Некорректный фильтр priority')

    if not db_file or not os.path.isfile(db_file):
        return {
            'ok': True,
            'status': 'unavailable',
            'dbHealth': 'missing',
            'tasks': [],
            'total': 0,
            'countsByStatus': {},
            'updatedAt': _fmt_iso(now),
        }

    where = []
    params = []
    if st_f and st_f != 'all':
        where.append('status = ?')
        params.append(st_f)
    if cat_f and cat_f.lower() != 'all':
        where.append('category = ?')
        params.append(cat_f)
    if prio_f and prio_f != 'all':
        where.append('priority = ?')
        params.append(prio_f)
    if q_f:
        like = f'%{q_f}%'
        where.append('(lower(title) LIKE ? OR lower(description) LIKE ? OR lower(target_url) LIKE ?)')
        params.extend([like, like, like])
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    try:
        with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            tbl = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_tasks'").fetchone()
            if not tbl:
                return {
                    'ok': True,
                    'status': 'unavailable',
                    'dbHealth': 'missing_table',
                    'tasks': [],
                    'total': 0,
                    'countsByStatus': {},
                    'updatedAt': _fmt_iso(now),
                }
            total = int(conn.execute(f'SELECT COUNT(*) FROM growth_tasks {where_sql}', tuple(params)).fetchone()[0])
            rows = conn.execute(
                f'SELECT * FROM growth_tasks {where_sql} '
                f'ORDER BY {PRIORITY_ORDER_SQL} ASC, updated_at DESC, id DESC LIMIT ? OFFSET ?',
                tuple(params + [lim, off]),
            ).fetchall()
            st_rows = conn.execute('SELECT status, COUNT(*) AS cnt FROM growth_tasks GROUP BY status').fetchall()
            counts = {s: 0 for s in TASK_STATUSES}
            for sr in st_rows:
                k = str(sr['status'] or '')
                if k in counts:
                    counts[k] = int(sr['cnt'] or 0)
    except sqlite3.Error:
        return {
            'ok': True,
            'status': 'unavailable',
            'dbHealth': 'corrupted',
            'tasks': [],
            'total': 0,
            'countsByStatus': {},
            'updatedAt': _fmt_iso(now),
        }

    return {
        'ok': True,
        'status': 'ok',
        'dbHealth': 'ok',
        'tasks': [_row_to_task(r) for r in rows],
        'total': total,
        'limit': lim,
        'offset': off,
        'hasMore': (off + len(rows)) < total,
        'countsByStatus': counts,
        'enums': {
            'statuses': list(TASK_STATUSES),
            'categories': list(TASK_CATEGORIES),
            'priorities': list(TASK_PRIORITIES),
        },
        'source': 'flexa.db:growth_tasks',
        'updatedAt': _fmt_iso(now),
    }


def get_task_detail(db_file, db_lock, task_id):
    """Fetch a single task, its change history, linked SEO issue, and linked proposals."""
    tid = _parse_optional_pos_int(task_id, 'taskId')
    if tid is None:
        raise ValueError('Некорректный ID задачи')

    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        tbl = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_tasks'").fetchone()
        if not tbl:
            return None
        row = conn.execute('SELECT * FROM growth_tasks WHERE id = ?', (tid,)).fetchone()
        if not row:
            return None
        task = _row_to_task(row)
        hist_rows = conn.execute(
            'SELECT id, field_name, old_value, new_value, actor, note, created_at '
            'FROM growth_task_history WHERE task_id = ? ORDER BY id DESC LIMIT 100',
            (tid,),
        ).fetchall()
        history = [
            {
                'id': int(h['id']),
                'field': str(h['field_name']),
                'oldValue': str(h['old_value'] or ''),
                'newValue': str(h['new_value'] or ''),
                'actor': str(h['actor'] or 'admin'),
                'note': str(h['note'] or ''),
                'createdAt': int(h['created_at'] or 0),
                'createdAtIso': _fmt_iso(h['created_at']),
            }
            for h in hist_rows
        ]

        seo_issue = None
        if task['seoIssueId']:
            ir = conn.execute('SELECT * FROM growth_seo_issues WHERE id = ?', (task['seoIssueId'],)).fetchone()
            if ir:
                seo_issue = {
                    'id': int(ir['id']),
                    'runId': int(ir['run_id']),
                    'pageUrl': str(ir['page_url']),
                    'issueType': str(ir['issue_type']),
                    'severity': str(ir['severity']),
                    'description': str(ir['description']),
                    'recommendation': str(ir['recommendation']),
                }

        prop_rows = conn.execute(
            'SELECT id, target_object, field_name, status, reason, created_at '
            'FROM growth_proposals WHERE task_id = ? ORDER BY id DESC',
            (tid,),
        ).fetchall()
        proposals = [
            {
                'id': int(p['id']),
                'targetObject': str(p['target_object']),
                'fieldName': str(p['field_name']),
                'status': str(p['status']),
                'reason': str(p['reason']),
                'createdAtIso': _fmt_iso(p['created_at']),
            }
            for p in prop_rows
        ]

    return {
        'ok': True,
        'task': task,
        'history': history,
        'seoIssue': seo_issue,
        'proposals': proposals,
    }


def create_task(db_file, db_lock, payload, *, actor='admin', actor_ip=''):
    """Create a validated Growth task and append to task history and audit log."""
    if not isinstance(payload, dict):
        raise ValueError('Тело запроса должно быть JSON-объектом')

    allowed_keys = {
        'title', 'description', 'category', 'priority', 'status',
        'seoAuditRunId', 'seoIssueId', 'targetUrl', 'note',
    }
    unknown = set(payload.keys()) - allowed_keys
    if unknown:
        raise ValueError('Неизвестные поля: ' + ', '.join(sorted(unknown)))

    title = _clean_text(payload.get('title'), field='title', min_len=3, max_len=160)
    desc = _clean_text(payload.get('description', ''), field='description', min_len=0, max_len=2000)
    category = str(payload.get('category') or 'SEO').strip()
    if category not in TASK_CATEGORIES:
        raise ValueError('Недопустимая категория задачи')
    priority = str(payload.get('priority') or 'medium').strip().lower()
    if priority not in TASK_PRIORITIES:
        raise ValueError('Недопустимый приоритет задачи')
    status = str(payload.get('status') or 'open').strip().lower()
    if status not in ('open', 'in_progress', 'pending_approval'):
        raise ValueError('Новая задача может иметь статус только open, in_progress или pending_approval')
    target_url = _validate_target_url(payload.get('targetUrl', ''))
    note = _clean_text(payload.get('note', ''), field='note', min_len=0, max_len=300)

    run_id = _parse_optional_pos_int(payload.get('seoAuditRunId'), 'seoAuditRunId')
    issue_id = _parse_optional_pos_int(payload.get('seoIssueId'), 'seoIssueId')
    now = int(time.time())

    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        init_growth_db(conn)
        if issue_id is not None:
            ir = conn.execute('SELECT id, run_id, page_url FROM growth_seo_issues WHERE id = ?', (issue_id,)).fetchone()
            if not ir:
                raise ValueError('Указанная SEO-проблема (seoIssueId) не найдена')
            if run_id is None:
                run_id = int(ir['run_id'])
            if not target_url:
                first_page = str(ir['page_url'] or '').split(',')[0].strip()
                if first_page:
                    try:
                        target_url, _ = _validate_and_classify_target_url(first_page)
                    except ValueError:
                        target_url = ''
        elif run_id is not None:
            rr = conn.execute('SELECT id FROM growth_seo_audit_runs WHERE id = ?', (run_id,)).fetchone()
            if not rr:
                raise ValueError('Указанный запуск SEO-аудита (seoAuditRunId) не найден')

        cur = conn.execute(
            'INSERT INTO growth_tasks '
            '(title, description, category, priority, status, seo_audit_run_id, seo_issue_id, '
            'target_url, created_by, created_at, updated_at, completed_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)',
            (title, desc, category, priority, status, run_id, issue_id, target_url, actor, now, now),
        )
        tid = int(cur.lastrowid)
        conn.execute(
            'INSERT INTO growth_task_history (task_id, field_name, old_value, new_value, actor, note, created_at) '
            'VALUES (?, "created", "", ?, ?, ?, ?)',
            (tid, f'{status}/{priority}/{category}', actor, note, now),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM growth_tasks WHERE id = ?', (tid,)).fetchone()
        task_dto = _row_to_task(row)

    record_audit_event(
        db_file,
        db_lock,
        action='task.create',
        module='tasks',
        target=f'task:{tid}',
        status='ok',
        actor=actor,
        actor_ip=actor_ip,
        details={'category': category, 'priority': priority, 'status': status, 'seoIssueId': issue_id},
    )
    return {'ok': True, 'task': task_dto}


def update_task(db_file, db_lock, task_id, payload, *, actor='admin', actor_ip=''):
    """Update task fields/status with transition enforcement, change history, and audit log."""
    tid = _parse_optional_pos_int(task_id, 'taskId')
    if tid is None:
        raise ValueError('Некорректный ID задачи')
    if not isinstance(payload, dict) or not payload:
        raise ValueError('Тело запроса должно содержать изменяемые поля')

    allowed_keys = {'title', 'description', 'category', 'priority', 'status', 'targetUrl', 'note'}
    unknown = set(payload.keys()) - allowed_keys
    if unknown:
        raise ValueError('Неизвестные поля: ' + ', '.join(sorted(unknown)))

    note = _clean_text(payload.get('note', ''), field='note', min_len=0, max_len=300)
    now = int(time.time())

    changes = []
    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        init_growth_db(conn)
        row = conn.execute('SELECT * FROM growth_tasks WHERE id = ?', (tid,)).fetchone()
        if not row:
            return None

        updates = {}
        if 'title' in payload:
            nv = _clean_text(payload['title'], field='title', min_len=3, max_len=160)
            if nv != row['title']:
                updates['title'] = nv
                changes.append(('title', row['title'], nv))
        if 'description' in payload:
            nv = _clean_text(payload['description'], field='description', min_len=0, max_len=2000)
            if nv != row['description']:
                updates['description'] = nv
                changes.append(('description', row['description'], nv))
        if 'category' in payload:
            nv = str(payload['category'] or '').strip()
            if nv not in TASK_CATEGORIES:
                raise ValueError('Недопустимая категория задачи')
            if nv != row['category']:
                updates['category'] = nv
                changes.append(('category', row['category'], nv))
        if 'priority' in payload:
            nv = str(payload['priority'] or '').strip().lower()
            if nv not in TASK_PRIORITIES:
                raise ValueError('Недопустимый приоритет задачи')
            if nv != row['priority']:
                updates['priority'] = nv
                changes.append(('priority', row['priority'], nv))
        if 'targetUrl' in payload:
            nv = _validate_target_url(payload['targetUrl'])
            if nv != row['target_url']:
                updates['target_url'] = nv
                changes.append(('target_url', row['target_url'], nv))
        if 'status' in payload:
            nv = str(payload['status'] or '').strip().lower()
            if nv not in TASK_STATUSES:
                raise ValueError('Недопустимый статус задачи')
            old_st = str(row['status'])
            if nv != old_st:
                allowed_next = ALLOWED_TASK_TRANSITIONS.get(old_st, set())
                if nv not in allowed_next:
                    raise ValueError(f'Переход статуса "{old_st}" -> "{nv}" запрещён')
                updates['status'] = nv
                updates['completed_at'] = now if nv == 'completed' else None
                changes.append(('status', old_st, nv))

        if not changes:
            return {'ok': True, 'task': _row_to_task(row), 'changes': []}

        updates['updated_at'] = now
        set_clause = ', '.join(f'{col} = ?' for col in updates.keys())
        conn.execute(
            f'UPDATE growth_tasks SET {set_clause} WHERE id = ?',
            tuple(list(updates.values()) + [tid]),
        )
        for col, ov, nv in changes:
            conn.execute(
                'INSERT INTO growth_task_history (task_id, field_name, old_value, new_value, actor, note, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (tid, col, str(ov or '')[:240], str(nv or '')[:240], actor, note, now),
            )
        conn.commit()
        new_row = conn.execute('SELECT * FROM growth_tasks WHERE id = ?', (tid,)).fetchone()
        task_dto = _row_to_task(new_row)

    record_audit_event(
        db_file,
        db_lock,
        action='task.update',
        module='tasks',
        target=f'task:{tid}',
        status='ok',
        actor=actor,
        actor_ip=actor_ip,
        details={'changedFields': [c[0] for c in changes], 'status': task_dto['status'], 'priority': task_dto['priority']},
    )
    return {'ok': True, 'task': task_dto, 'changes': [c[0] for c in changes]}
