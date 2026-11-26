"""AI Growth Approval Engine & Proposals storage (PR 4.2, strictly no auto-apply to production)."""

import contextlib
import datetime
import os
import re
import sqlite3
import time

from .db import init_growth_db, record_audit_event
from .diff_engine import compute_text_diff

PROPOSAL_STATUSES = ('pending', 'approved', 'rejected', 'applied', 'cancelled')
PROPOSAL_FIELDS = (
    'title',
    'meta_description',
    'h1',
    'canonical',
    'robots_meta',
    'og_title',
    'og_description',
    'alt',
    'sitemap_xml',
    'robots_txt',
    'content',
    'other',
)

TARGET_OBJECT_RE = re.compile(r'^[A-Za-z0-9_./:#-]{1,200}$')


class ConflictError(Exception):
    """Raised on duplicate approval/rejection or already-processed proposals (HTTP 409)."""


def _fmt_iso(ts):
    if not ts:
        return ''
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return ''


def _validate_target_object(raw):
    if not isinstance(raw, str):
        raise ValueError('Поле targetObject должно быть строкой')
    s = raw.replace('\x00', '').strip()
    if not s or not TARGET_OBJECT_RE.fullmatch(s):
        raise ValueError('Некорректный формат targetObject (разрешены латиница, цифры, _./:#-)')
    low = s.lower()
    if '..' in s or 'server_data' in low or low.endswith('.py') or low.startswith(('/', '\\')):
        if not s.startswith('/'):
            raise ValueError('Недопустимый путь в targetObject')
    if '..' in s or 'server_data' in low or low.endswith('.py') or '://' in s:
        raise ValueError('Недопустимый targetObject')
    return s


def _clean_value(raw, *, field, min_len=0, max_len=20000):
    if raw is None:
        s = ''
    elif isinstance(raw, str):
        if '\x00' in raw:
            raise ValueError(f'Поле {field} содержит недопустимый нулевой байт')
        s = raw.strip() if min_len > 0 else raw
    else:
        raise ValueError(f'Поле {field} должно быть строкой')
    if len(s.strip()) < min_len:
        raise ValueError(f'Поле {field} должно содержать минимум {min_len} симв.')
    if len(s) > max_len:
        raise ValueError(f'Поле {field} превышает лимит {max_len} симв.')
    return s


def _parse_pos_int(val, field, *, required=False):
    if val is None or val == '':
        if required:
            raise ValueError(f'Укажите {field}')
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


def _row_to_proposal(row):
    c_at = int(row['created_at'] or 0)
    u_at = int(row['updated_at'] or 0)
    r_at = int(row['reviewed_at']) if row['reviewed_at'] else None
    a_at = int(row['applied_at']) if row['applied_at'] else None
    diff_summary = compute_text_diff(
        row['current_value'],
        row['proposed_value'],
        field_name=row['field_name'],
        target_object=row['target_object'],
    )['stats']
    return {
        'id': int(row['id']),
        'taskId': int(row['task_id']) if row['task_id'] is not None else None,
        'targetObject': str(row['target_object']),
        'fieldName': str(row['field_name']),
        'currentValue': str(row['current_value'] or ''),
        'proposedValue': str(row['proposed_value'] or ''),
        'reason': str(row['reason'] or ''),
        'status': str(row['status'] or 'pending'),
        'reviewedBy': str(row['reviewed_by'] or ''),
        'reviewNote': str(row['review_note'] or ''),
        'reviewedAt': r_at,
        'reviewedAtIso': _fmt_iso(r_at) if r_at else '',
        'appliedAt': a_at,
        'appliedAtIso': _fmt_iso(a_at) if a_at else '',
        'createdBy': str(row['created_by'] or 'admin'),
        'createdAt': c_at,
        'createdAtIso': _fmt_iso(c_at),
        'updatedAt': u_at,
        'updatedAtIso': _fmt_iso(u_at),
        'diffStats': diff_summary,
        'autoApplyDisabled': True,
    }


def list_proposals(db_file, db_lock, *, status='', task_id=None, limit=50, offset=0):
    """List approval proposals cleanly (read-only)."""
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
    if st_f and st_f != 'all' and st_f not in PROPOSAL_STATUSES:
        raise ValueError('Некорректный фильтр status')
    tid = _parse_pos_int(task_id, 'taskId', required=False)

    if not db_file or not os.path.isfile(db_file):
        return {
            'ok': True,
            'status': 'unavailable',
            'dbHealth': 'missing',
            'proposals': [],
            'total': 0,
            'countsByStatus': {},
            'updatedAt': _fmt_iso(now),
        }

    where = []
    params = []
    if st_f and st_f != 'all':
        where.append('status = ?')
        params.append(st_f)
    if tid is not None:
        where.append('task_id = ?')
        params.append(tid)
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    try:
        with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            tbl = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_proposals'").fetchone()
            if not tbl:
                return {
                    'ok': True,
                    'status': 'unavailable',
                    'dbHealth': 'missing_table',
                    'proposals': [],
                    'total': 0,
                    'countsByStatus': {},
                    'updatedAt': _fmt_iso(now),
                }
            total = int(conn.execute(f'SELECT COUNT(*) FROM growth_proposals {where_sql}', tuple(params)).fetchone()[0])
            rows = conn.execute(
                f'SELECT * FROM growth_proposals {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?',
                tuple(params + [lim, off]),
            ).fetchall()
            st_rows = conn.execute('SELECT status, COUNT(*) AS cnt FROM growth_proposals GROUP BY status').fetchall()
            counts = {s: 0 for s in PROPOSAL_STATUSES}
            for sr in st_rows:
                k = str(sr['status'] or '')
                if k in counts:
                    counts[k] = int(sr['cnt'] or 0)
    except sqlite3.Error:
        return {
            'ok': True,
            'status': 'unavailable',
            'dbHealth': 'corrupted',
            'proposals': [],
            'total': 0,
            'countsByStatus': {},
            'updatedAt': _fmt_iso(now),
        }

    return {
        'ok': True,
        'status': 'ok',
        'dbHealth': 'ok',
        'proposals': [_row_to_proposal(r) for r in rows],
        'total': total,
        'limit': lim,
        'offset': off,
        'hasMore': (off + len(rows)) < total,
        'countsByStatus': counts,
        'enums': {'statuses': list(PROPOSAL_STATUSES), 'fields': list(PROPOSAL_FIELDS)},
        'source': 'flexa.db:growth_proposals',
        'updatedAt': _fmt_iso(now),
    }


def get_proposal_detail(db_file, db_lock, proposal_id):
    """Fetch proposal details, approval history, diff preview, and linked task summary."""
    pid = _parse_pos_int(proposal_id, 'proposalId', required=True)
    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        tbl = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_proposals'").fetchone()
        if not tbl:
            return None
        row = conn.execute('SELECT * FROM growth_proposals WHERE id = ?', (pid,)).fetchone()
        if not row:
            return None
        prop = _row_to_proposal(row)
        hist_rows = conn.execute(
            'SELECT id, action, old_status, new_status, actor, note, created_at '
            'FROM growth_proposal_history WHERE proposal_id = ? ORDER BY id DESC LIMIT 50',
            (pid,),
        ).fetchall()
        history = [
            {
                'id': int(h['id']),
                'action': str(h['action']),
                'oldStatus': str(h['old_status'] or ''),
                'newStatus': str(h['new_status'] or ''),
                'actor': str(h['actor'] or 'admin'),
                'note': str(h['note'] or ''),
                'createdAt': int(h['created_at'] or 0),
                'createdAtIso': _fmt_iso(h['created_at']),
            }
            for h in hist_rows
        ]
        linked_task = None
        if prop['taskId']:
            tr = conn.execute('SELECT id, title, status, priority, category FROM growth_tasks WHERE id = ?', (prop['taskId'],)).fetchone()
            if tr:
                linked_task = {
                    'id': int(tr['id']),
                    'title': str(tr['title']),
                    'status': str(tr['status']),
                    'priority': str(tr['priority']),
                    'category': str(tr['category']),
                }

    diff = compute_text_diff(
        prop['currentValue'],
        prop['proposedValue'],
        field_name=prop['fieldName'],
        target_object=prop['targetObject'],
    )
    return {
        'ok': True,
        'proposal': prop,
        'history': history,
        'diff': diff,
        'linkedTask': linked_task,
    }


def get_proposal_diff(db_file, db_lock, proposal_id):
    """Compute diff payload for a given proposal ID."""
    pid = _parse_pos_int(proposal_id, 'proposalId', required=True)
    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        tbl = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_proposals'").fetchone()
        if not tbl:
            return None
        row = conn.execute('SELECT * FROM growth_proposals WHERE id = ?', (pid,)).fetchone()
        if not row:
            return None
        prop = _row_to_proposal(row)

    diff = compute_text_diff(
        prop['currentValue'],
        prop['proposedValue'],
        field_name=prop['fieldName'],
        target_object=prop['targetObject'],
    )
    return {'ok': True, 'proposalId': pid, 'status': prop['status'], 'diff': diff}


def create_proposal(db_file, db_lock, payload, *, actor='admin', actor_ip=''):
    """Create a pending change proposal (never modifies site files)."""
    if not isinstance(payload, dict):
        raise ValueError('Тело запроса должно быть JSON-объектом')

    allowed_keys = {'taskId', 'targetObject', 'fieldName', 'currentValue', 'proposedValue', 'reason'}
    unknown = set(payload.keys()) - allowed_keys
    if unknown:
        raise ValueError('Неизвестные поля: ' + ', '.join(sorted(unknown)))

    target_obj = _validate_target_object(payload.get('targetObject'))
    field_name = str(payload.get('fieldName') or 'content').strip().lower()
    if field_name not in PROPOSAL_FIELDS:
        raise ValueError('Недопустимое поле изменения (fieldName)')
    curr_val = _clean_value(payload.get('currentValue', ''), field='currentValue', min_len=0, max_len=20000)
    prop_val = _clean_value(payload.get('proposedValue'), field='proposedValue', min_len=1, max_len=20000)
    if curr_val == prop_val:
        raise ValueError('Предлагаемое значение должно отличаться от текущего')
    reason = _clean_value(payload.get('reason'), field='reason', min_len=3, max_len=1000)
    task_id = _parse_pos_int(payload.get('taskId'), 'taskId', required=False)
    now = int(time.time())

    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        init_growth_db(conn)
        if task_id is not None:
            tr = conn.execute('SELECT id FROM growth_tasks WHERE id = ?', (task_id,)).fetchone()
            if not tr:
                raise ValueError('Связанная задача (taskId) не найдена')

        cur = conn.execute(
            'INSERT INTO growth_proposals '
            '(task_id, target_object, field_name, current_value, proposed_value, reason, status, '
            'reviewed_by, review_note, reviewed_at, applied_at, created_by, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, "pending", "", "", NULL, NULL, ?, ?, ?)',
            (task_id, target_obj, field_name, curr_val, prop_val, reason, actor, now, now),
        )
        pid = int(cur.lastrowid)
        conn.execute(
            'INSERT INTO growth_proposal_history (proposal_id, action, old_status, new_status, actor, note, created_at) '
            'VALUES (?, "created", "", "pending", ?, ?, ?)',
            (pid, actor, reason[:240], now),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM growth_proposals WHERE id = ?', (pid,)).fetchone()
        prop_dto = _row_to_proposal(row)

    record_audit_event(
        db_file,
        db_lock,
        action='proposal.create',
        module='proposals',
        target=f'proposal:{pid}',
        status='ok',
        actor=actor,
        actor_ip=actor_ip,
        details={'targetObject': target_obj, 'fieldName': field_name, 'taskId': task_id},
    )
    return {'ok': True, 'proposal': prop_dto}


def review_proposal(db_file, db_lock, proposal_id, decision, *, note='', actor='admin', actor_ip=''):
    """Approve or reject a pending proposal (idempotency protected, NEVER edits production)."""
    pid = _parse_pos_int(proposal_id, 'proposalId', required=True)
    if decision not in ('approve', 'reject'):
        raise ValueError('Решение должно быть approve или reject')
    clean_note = _clean_value(note or '', field='note', min_len=0, max_len=500).strip()
    new_status = 'approved' if decision == 'approve' else 'rejected'
    now = int(time.time())

    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        init_growth_db(conn)
        row = conn.execute('SELECT * FROM growth_proposals WHERE id = ?', (pid,)).fetchone()
        if not row:
            return None

        old_status = str(row['status'] or 'pending')
        if old_status != 'pending':
            raise ConflictError(
                f'Предложение #{pid} уже обработано (статус: {old_status}). Повторное действие заблокировано.'
            )

        conn.execute(
            'UPDATE growth_proposals SET status = ?, reviewed_by = ?, review_note = ?, reviewed_at = ?, updated_at = ? '
            'WHERE id = ? AND status = "pending"',
            (new_status, actor, clean_note, now, now, pid),
        )
        conn.execute(
            'INSERT INTO growth_proposal_history (proposal_id, action, old_status, new_status, actor, note, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (pid, decision, old_status, new_status, actor, clean_note, now),
        )

        # Sync linked task if it is awaiting approval
        linked_tid = row['task_id']
        if linked_tid is not None:
            tr = conn.execute('SELECT id, status FROM growth_tasks WHERE id = ?', (int(linked_tid),)).fetchone()
            if tr and str(tr['status']) == 'pending_approval':
                conn.execute(
                    'UPDATE growth_tasks SET status = ?, updated_at = ? WHERE id = ?',
                    (new_status, now, int(linked_tid)),
                )
                conn.execute(
                    'INSERT INTO growth_task_history (task_id, field_name, old_value, new_value, actor, note, created_at) '
                    'VALUES (?, "status", "pending_approval", ?, ?, ?, ?)',
                    (int(linked_tid), new_status, actor, f'Синхронизация по proposal #{pid}', now),
                )

        conn.commit()
        updated_row = conn.execute('SELECT * FROM growth_proposals WHERE id = ?', (pid,)).fetchone()
        prop_dto = _row_to_proposal(updated_row)

    record_audit_event(
        db_file,
        db_lock,
        action=f'proposal.{decision}',
        module='proposals',
        target=f'proposal:{pid}',
        status='ok',
        actor=actor,
        actor_ip=actor_ip,
        details={
            'targetObject': prop_dto['targetObject'],
            'fieldName': prop_dto['fieldName'],
            'newStatus': new_status,
            'autoApplyDisabled': True,
        },
    )
    return {'ok': True, 'proposal': prop_dto}
