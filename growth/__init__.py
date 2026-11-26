"""RizzaFit AI Growth backend package (PR 4.1 + PR 4.2, deterministic only)."""

from .db import init_growth_db, query_audit_log, record_audit_event, sanitize_audit_details
from .diff_engine import compute_text_diff
from .metrics import compute_analytics, compute_overview
from .proposals import (
    ConflictError,
    create_proposal,
    get_proposal_detail,
    get_proposal_diff,
    list_proposals,
    review_proposal,
)
from .routes import handle_growth_get, handle_growth_patch, handle_growth_post, handle_growth_write_attempt
from .seo_audit import get_latest_seo_audit, run_seo_audit, scan_site_seo
from .tasks import create_task, get_task_detail, list_tasks, update_task

__all__ = [
    'init_growth_db',
    'record_audit_event',
    'query_audit_log',
    'sanitize_audit_details',
    'compute_analytics',
    'compute_overview',
    'compute_text_diff',
    'list_tasks',
    'get_task_detail',
    'create_task',
    'update_task',
    'scan_site_seo',
    'run_seo_audit',
    'get_latest_seo_audit',
    'ConflictError',
    'list_proposals',
    'get_proposal_detail',
    'get_proposal_diff',
    'create_proposal',
    'review_proposal',
    'handle_growth_get',
    'handle_growth_post',
    'handle_growth_patch',
    'handle_growth_write_attempt',
]
