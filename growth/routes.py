"""HTTP route dispatcher for /api/admin/growth/* (PR 4.1 + PR 4.2)."""

import json
import re
from urllib.parse import urlparse

from .db import query_audit_log
from .metrics import compute_analytics, compute_overview
from .proposals import (
    ConflictError,
    create_proposal,
    get_proposal_detail,
    get_proposal_diff,
    list_proposals,
    review_proposal,
)
from .seo_audit import get_latest_seo_audit, run_seo_audit
from .tasks import create_task, get_task_detail, list_tasks, update_task

MAX_GROWTH_BODY = 64 * 1024
POS_INT_RE = re.compile(r'^[1-9]\d{0,9}$')


def _qs_first(query_params, key, default=''):
    vals = query_params.get(key) if isinstance(query_params, dict) else None
    if not vals:
        return default
    return str(vals[0] or default).strip()


def _parse_pos_id(raw_id):
    s = str(raw_id or '').strip()
    if not POS_INT_RE.fullmatch(s):
        return None
    return int(s)


def _read_json_body(handler, *, allow_empty=False):
    raw = handler.body(MAX_GROWTH_BODY)
    if raw is None:
        return None, (413, {'error': 'request body too large'})
    if not raw or not raw.strip():
        if allow_empty:
            return {}, None
        return None, (400, {'error': 'empty json body'})
    try:
        obj = json.loads(raw.decode('utf-8'))
    except Exception:
        return None, (400, {'error': 'bad json'})
    if not isinstance(obj, dict):
        return None, (400, {'error': 'json object expected'})
    return obj, None


def check_growth_csrf(handler):
    """Verify Origin/Referer host match and non-form request headers on mutating endpoints."""
    hdrs = getattr(handler, 'headers', None)
    if hdrs is None:
        return False, 'missing headers'

    host = str(hdrs.get('Host') or '').strip().lower()
    origin = str(hdrs.get('Origin') or '').strip()
    referer = str(hdrs.get('Referer') or '').strip()

    if origin:
        parsed = urlparse(origin)
        origin_host = (parsed.netloc or '').lower()
        if parsed.scheme not in ('http', 'https') or not origin_host or (host and origin_host != host):
            return False, 'csrf_origin_mismatch'
    elif referer:
        parsed = urlparse(referer)
        ref_host = (parsed.netloc or '').lower()
        if parsed.scheme not in ('http', 'https') or not ref_host or (host and ref_host != host):
            return False, 'csrf_referer_mismatch'

    x_req = str(hdrs.get('X-Requested-With') or '').strip().lower()
    x_adm = str(hdrs.get('X-Rizza-Admin') or '').strip()
    ctype = str(hdrs.get('Content-Type') or '').strip().lower()
    if x_req == 'xmlhttprequest' or x_adm == '1' or ctype.startswith('application/json'):
        return True, ''
    return False, 'csrf_header_or_json_required'


def handle_growth_get(handler, path, query_params, *, db_file, db_lock, site_dir, content_dir, free_access_mode):
    """Handle authenticated GET requests under /api/admin/growth/."""
    if not handler.authed():
        return handler.send_j(401, {'error': 'unauthorized'})

    if path == '/api/admin/growth/overview':
        payload = compute_overview(
            db_file,
            db_lock,
            site_dir=site_dir,
            content_dir=content_dir,
            free_access_mode=free_access_mode,
            days=_qs_first(query_params, 'days', '30'),
        )
        return handler.send_j(200, payload)

    if path == '/api/admin/growth/analytics':
        payload = compute_analytics(
            db_file,
            db_lock,
            site_dir=site_dir,
            content_dir=content_dir,
            free_access_mode=free_access_mode,
            days=_qs_first(query_params, 'days', '30'),
        )
        return handler.send_j(200, payload)

    if path == '/api/admin/growth/audit':
        payload = query_audit_log(
            db_file,
            db_lock,
            limit=_qs_first(query_params, 'limit', '50'),
            offset=_qs_first(query_params, 'offset', '0'),
            module=_qs_first(query_params, 'module', ''),
            status=_qs_first(query_params, 'status', ''),
        )
        return handler.send_j(200, payload)

    try:
        if path == '/api/admin/growth/tasks':
            payload = list_tasks(
                db_file,
                db_lock,
                status=_qs_first(query_params, 'status', ''),
                category=_qs_first(query_params, 'category', ''),
                priority=_qs_first(query_params, 'priority', ''),
                q=_qs_first(query_params, 'q', ''),
                limit=_qs_first(query_params, 'limit', '50'),
                offset=_qs_first(query_params, 'offset', '0'),
            )
            return handler.send_j(200, payload)

        if path.startswith('/api/admin/growth/tasks/'):
            raw_id = path[len('/api/admin/growth/tasks/'):]
            tid = _parse_pos_id(raw_id)
            if tid is None:
                return handler.send_j(400, {'error': 'некорректный ID задачи'})
            detail = get_task_detail(db_file, db_lock, tid)
            if not detail:
                return handler.send_j(404, {'error': 'задача не найдена'})
            return handler.send_j(200, detail)

        if path == '/api/admin/growth/seo-audit':
            raw_run = _qs_first(query_params, 'runId', '')
            run_id = None
            if raw_run:
                run_id = _parse_pos_id(raw_run)
                if run_id is None:
                    return handler.send_j(400, {'error': 'некорректный runId'})
            payload = get_latest_seo_audit(
                db_file,
                db_lock,
                run_id=run_id,
                severity=_qs_first(query_params, 'severity', ''),
            )
            return handler.send_j(200, payload)

        if path == '/api/admin/growth/proposals':
            raw_tid = _qs_first(query_params, 'taskId', '')
            tid = None
            if raw_tid:
                tid = _parse_pos_id(raw_tid)
                if tid is None:
                    return handler.send_j(400, {'error': 'некорректный taskId'})
            payload = list_proposals(
                db_file,
                db_lock,
                status=_qs_first(query_params, 'status', ''),
                task_id=tid,
                limit=_qs_first(query_params, 'limit', '50'),
                offset=_qs_first(query_params, 'offset', '0'),
            )
            return handler.send_j(200, payload)

        if path.startswith('/api/admin/growth/proposals/'):
            rest = path[len('/api/admin/growth/proposals/'):]
            if rest.endswith('/diff'):
                raw_id = rest[:-len('/diff')]
                pid = _parse_pos_id(raw_id)
                if pid is None:
                    return handler.send_j(400, {'error': 'некорректный ID предложения'})
                diff_res = get_proposal_diff(db_file, db_lock, pid)
                if not diff_res:
                    return handler.send_j(404, {'error': 'предложение не найдено'})
                return handler.send_j(200, diff_res)

            pid = _parse_pos_id(rest)
            if pid is None:
                return handler.send_j(400, {'error': 'некорректный ID предложения'})
            detail = get_proposal_detail(db_file, db_lock, pid)
            if not detail:
                return handler.send_j(404, {'error': 'предложение не найдено'})
            return handler.send_j(200, detail)
    except ValueError as e:
        return handler.send_j(400, {'error': str(e)})

    return handler.send_j(404, {'error': 'not found'})


def handle_growth_post(handler, path, *, db_file, db_lock, site_dir, client_ip=''):
    """Handle authenticated CSRF-protected POST requests under /api/admin/growth/."""
    if not handler.authed():
        return handler.send_j(401, {'error': 'unauthorized'})
    if path == '/api/admin/growth/audit' or path.startswith('/api/admin/growth/audit/'):
        return handler.send_j(405, {'error': 'growth_audit_log is append-only'})

    csrf_ok, csrf_err = check_growth_csrf(handler)
    if not csrf_ok:
        return handler.send_j(403, {'error': csrf_err})

    try:
        if path == '/api/admin/growth/tasks':
            body, err = _read_json_body(handler)
            if err:
                return handler.send_j(err[0], err[1])
            return handler.send_j(201, create_task(db_file, db_lock, body, actor='admin', actor_ip=client_ip))

        if path == '/api/admin/growth/seo-audit/run':
            _body, err = _read_json_body(handler, allow_empty=True)
            if err:
                return handler.send_j(err[0], err[1])
            return handler.send_j(200, run_seo_audit(db_file, db_lock, site_dir=site_dir, actor='admin', actor_ip=client_ip))

        if path == '/api/admin/growth/proposals':
            body, err = _read_json_body(handler)
            if err:
                return handler.send_j(err[0], err[1])
            return handler.send_j(201, create_proposal(db_file, db_lock, body, actor='admin', actor_ip=client_ip))

        if path.startswith('/api/admin/growth/proposals/'):
            rest = path[len('/api/admin/growth/proposals/'):]
            for suffix, decision in (('/approve', 'approve'), ('/reject', 'reject')):
                if rest.endswith(suffix):
                    pid = _parse_pos_id(rest[:-len(suffix)])
                    if pid is None:
                        return handler.send_j(400, {'error': 'некорректный ID предложения'})
                    body, err = _read_json_body(handler, allow_empty=True)
                    if err:
                        return handler.send_j(err[0], err[1])
                    res = review_proposal(
                        db_file,
                        db_lock,
                        pid,
                        decision,
                        note=body.get('note', ''),
                        actor='admin',
                        actor_ip=client_ip,
                    )
                    if not res:
                        return handler.send_j(404, {'error': 'предложение не найдено'})
                    return handler.send_j(200, res)
    except ConflictError as e:
        return handler.send_j(409, {'error': str(e)})
    except ValueError as e:
        return handler.send_j(400, {'error': str(e)})

    return handler.send_j(404, {'error': 'not found'})


def handle_growth_patch(handler, path, *, db_file, db_lock, site_dir='', client_ip=''):
    """Handle authenticated CSRF-protected PATCH requests under /api/admin/growth/."""
    if not handler.authed():
        return handler.send_j(401, {'error': 'unauthorized'})
    if path == '/api/admin/growth/audit' or path.startswith('/api/admin/growth/audit/'):
        return handler.send_j(405, {'error': 'growth_audit_log is append-only'})

    csrf_ok, csrf_err = check_growth_csrf(handler)
    if not csrf_ok:
        return handler.send_j(403, {'error': csrf_err})

    try:
        if path.startswith('/api/admin/growth/tasks/'):
            tid = _parse_pos_id(path[len('/api/admin/growth/tasks/'):])
            if tid is None:
                return handler.send_j(400, {'error': 'некорректный ID задачи'})
            body, err = _read_json_body(handler)
            if err:
                return handler.send_j(err[0], err[1])
            res = update_task(db_file, db_lock, tid, body, actor='admin', actor_ip=client_ip)
            if not res:
                return handler.send_j(404, {'error': 'задача не найдена'})
            return handler.send_j(200, res)
    except ValueError as e:
        return handler.send_j(400, {'error': str(e)})

    return handler.send_j(405, {'error': 'method not allowed'})


def handle_growth_write_attempt(handler, path):
    """Reject unsupported mutating methods (PUT/DELETE) on Growth endpoints."""
    if not handler.authed():
        return handler.send_j(401, {'error': 'unauthorized'})
    if path == '/api/admin/growth/audit' or path.startswith('/api/admin/growth/audit/'):
        return handler.send_j(405, {'error': 'growth_audit_log is append-only'})
    return handler.send_j(405, {'error': 'method not allowed'})
