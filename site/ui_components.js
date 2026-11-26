/* ===================================================================
   RIZZAFIT UNIFIED UI COMPONENTS (Site, Admin & Growth AI)
   Browser global (window.RizzaUI) + CommonJS export for unit tests
   =================================================================== */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(root);
  } else {
    root.RizzaUI = factory(root);
  }
})(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';

  function esc(val) {
    return String(val == null ? '' : val).replace(/[&<>"']/g, function (c) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[c];
    });
  }

  function formatDateTime(input) {
    if (!input && input !== 0) return '—';
    var d;
    if (input instanceof Date) {
      d = input;
    } else if (typeof input === 'number') {
      d = new Date(input < 1e12 ? input * 1000 : input);
    } else {
      d = new Date(String(input));
    }
    if (isNaN(d.getTime())) return String(input);
    var pad = function (n) { return n < 10 ? '0' + n : String(n); };
    return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear() + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  var STATUS_META = {
    draft: { cls: 'rf-status-draft', label: 'Черновик' },
    pending_approval: { cls: 'rf-status-pending', label: 'На одобрении' },
    pending: { cls: 'rf-status-pending', label: 'На одобрении' },
    in_progress: { cls: 'rf-status-pending', label: 'В работе' },
    approved: { cls: 'rf-status-approved', label: 'Одобрено' },
    done: { cls: 'rf-status-approved', label: 'Готово' },
    published: { cls: 'rf-status-published', label: 'Опубликовано' },
    rejected: { cls: 'rf-status-rejected', label: 'Отклонено' }
  };

  function renderStatusBadge(status, customLabel) {
    var key = String(status || 'draft').toLowerCase().trim();
    var meta = STATUS_META[key] || { cls: 'rf-status-draft', label: status || 'Черновик' };
    var lbl = customLabel || meta.label;
    return '<span class="rf-pill ' + meta.cls + '">' + esc(lbl) + '</span>';
  }

  function renderSourceMeta(source, updatedAt) {
    var srcText = source ? esc(source) : 'не указан';
    var updText = updatedAt ? esc(typeof updatedAt === 'number' ? formatDateTime(updatedAt) : updatedAt) : 'нет данных';
    return '<div class="rf-source-meta">' +
      '<span>Источник: <strong>' + srcText + '</strong></span>' +
      '<span>· Обновлено: ' + updText + '</span>' +
    '</div>';
  }

  function renderKpiCard(opts) {
    var o = opts || {};
    var toneCls = o.tone === 'warn' ? ' warn' : (o.tone === 'danger' ? ' danger' : '');
    var deltaHtml = o.delta ? '<span class="rf-kpi-delta' + toneCls + '">' + esc(o.delta) + '</span>' : '';
    var metaHtml = (o.source || o.updatedAt) ? renderSourceMeta(o.source, o.updatedAt) : '';
    return '<div class="rf-card rf-kpi">' +
      '<div class="rf-kpi-lbl">' + esc(o.label || '') + '</div>' +
      '<div class="rf-kpi-val"><span>' + esc(o.value == null ? '—' : o.value) + '</span>' + deltaHtml + '</div>' +
      metaHtml +
    '</div>';
  }

  function openConfirmModal(opts) {
    var doc = root && root.document;
    if (!doc || !doc.body) return null;
    var o = opts || {};
    var bd = doc.createElement('div');
    bd.className = 'rf-modal-backdrop';
    var confirmCls = o.danger ? 'rf-btn rf-btn-danger' : 'rf-btn rf-btn-primary';
    bd.innerHTML =
      '<div class="rf-modal" role="dialog" aria-modal="true">' +
        '<div class="rf-modal-head">' +
          '<h3>' + esc(o.title || 'Подтверждение') + '</h3>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-rf-close="1" aria-label="Закрыть">✕</button>' +
        '</div>' +
        '<div class="rf-modal-body">' + (o.bodyHtml || '') + '</div>' +
        '<div class="rf-modal-actions">' +
          '<button type="button" class="rf-btn rf-btn-alt" data-rf-close="1">' + esc(o.cancelLabel || 'Отмена') + '</button>' +
          '<button type="button" class="' + confirmCls + '" data-rf-confirm="1">' + esc(o.confirmLabel || 'Подтвердить') + '</button>' +
        '</div>' +
      '</div>';

    function close() {
      if (doc.removeEventListener) doc.removeEventListener('keydown', onKey);
      if (bd.parentNode) bd.parentNode.removeChild(bd);
    }
    function onKey(ev) {
      if (ev.key === 'Escape') close();
    }

    bd.onclick = function (ev) {
      if (ev.target === bd) close();
    };
    bd.querySelectorAll('[data-rf-close]').forEach(function (btn) {
      btn.onclick = close;
    });
    var okBtn = bd.querySelector('[data-rf-confirm]');
    if (okBtn) {
      okBtn.onclick = function () {
        if (typeof o.onConfirm === 'function') o.onConfirm(close);
        else close();
      };
    }
    if (doc.addEventListener) doc.addEventListener('keydown', onKey);
    doc.body.appendChild(bd);
    return { close: close, element: bd };
  }

  function renderAuditLogList(entries, opts) {
    var o = opts || {};
    var title = o.title || 'Журнал действий';
    var items = Array.isArray(entries) ? entries : [];
    var rowsHtml = '';
    if (!items.length) {
      rowsHtml = '<div class="rf-empty">Записей в журнале пока нет</div>';
    } else {
      rowsHtml = '<div class="rf-audit-list">' + items.map(function (entry) {
        var item = entry || {};
        var ts = typeof item.timestamp === 'number'
          ? formatDateTime(item.timestamp)
          : (item.timestamp ? String(item.timestamp) : '—');
        var badge = item.status ? renderStatusBadge(item.status, item.statusLabel) : '';
        var details = item.details
          ? '<div class="rf-audit-details">' + esc(item.details) + '</div>'
          : '';
        return '<div class="rf-audit-row">' +
          '<div class="rf-audit-row-top">' +
            '<span class="rf-audit-action">' + esc(item.action || 'Событие') + '</span>' +
            badge +
          '</div>' +
          '<div class="rf-audit-meta">' +
            '<span>Инициатор: <strong>' + esc(item.actor || 'system') + '</strong></span>' +
            '<span>· ' + esc(ts) + '</span>' +
          '</div>' +
          details +
        '</div>';
      }).join('') + '</div>';
    }
    return '<div class="rf-card rf-audit-log" data-readonly="true">' +
      '<div class="rf-audit-head">' +
        '<h3>' + esc(title) + '</h3>' +
        '<span class="rf-pill rf-audit-lock">' + esc(o.lockLabel || '👁 Только просмотр (UI)') + '</span>' +
      '</div>' +
      rowsHtml +
    '</div>';
  }

  return {
    esc: esc,
    formatDateTime: formatDateTime,
    renderStatusBadge: renderStatusBadge,
    renderSourceMeta: renderSourceMeta,
    renderKpiCard: renderKpiCard,
    openConfirmModal: openConfirmModal,
    renderAuditLogList: renderAuditLogList
  };
});
