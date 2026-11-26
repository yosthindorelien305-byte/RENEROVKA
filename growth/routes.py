"""HTTP route dispatcher for /api/admin/growth/* (PR 4.1)."""

from .db import query_audit_log
from .metrics import compute_analytics, compute_overview


def _qs_first(query_params, key, default=''):
    vals = query_params.get(key) if isinstance(query_params, dict) else None
    if not vals:
        return default
    return str(vals[0] or default).strip()


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

    return handler.send_j(404, {'error': 'not found'})


def handle_growth_write_attempt(handler, path):
    """Reject mutating methods on append-only audit log and unsupported Growth endpoints."""
    if not handler.authed():
        return handler.send_j(401, {'error': 'unauthorized'})
    if path == '/api/admin/growth/audit' or path.startswith('/api/admin/growth/audit/'):
        return handler.send_j(405, {'error': 'growth_audit_log is append-only'})
    return handler.send_j(405, {'error': 'method not allowed'})
