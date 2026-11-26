(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./ui_components.js'));
  } else {
    root.RizzaGrowth = factory(root.RizzaUI);
  }
})(typeof self !== 'undefined' ? self : this, function (DefaultUI) {
  function esc(v) {
    if (DefaultUI && typeof DefaultUI.esc === 'function') return DefaultUI.esc(v);
    return String(v == null ? '' : v).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function renderMeta(ui, source, updatedAt) {
    if (ui && typeof ui.renderSourceMeta === 'function') {
      return ui.renderSourceMeta(source || '—', updatedAt || '—');
    }
    return '<div class="rf-source-meta"><span>Источник: ' + esc(source || '—') + '</span> · <span>Обновлено: ' + esc(updatedAt || '—') + '</span></div>';
  }

  function renderBadge(ui, status, label) {
    if (ui && typeof ui.renderStatusBadge === 'function') {
      return ui.renderStatusBadge(status, label);
    }
    return '<span class="rf-status-badge">' + esc(label || status || 'draft') + '</span>';
  }

  function statusForMetric(st, labelOk) {
    if (st === 'unavailable') return { code: 'rejected', label: 'Недоступно (unavailable)' };
    if (st === 'insufficient_data') return { code: 'draft', label: 'Мало данных' };
    return { code: 'done', label: labelOk || 'Достоверно' };
  }

  function fmtNum(v, suffix) {
    if (v === null || v === undefined || v === '') return 'Нет данных';
    return String(v) + (suffix || '');
  }

  function fmtDurSec(sec) {
    if (sec === null || sec === undefined) return 'Нет данных';
    var m = Math.max(1, Math.round(Number(sec) / 60));
    return m + ' мин';
  }

  function fmtHours(h) {
    if (h === null || h === undefined) return 'Нет данных';
    return String(h) + ' ч';
  }

  function renderMetricBlockHead(ui, title, block) {
    var b = block || {};
    var sm = statusForMetric(b.status, 'Актуально');
    return '<div class="growth-block-head">' +
      '<div>' +
        '<h3 class="growth-block-title">' + esc(title) + '</h3>' +
        (b.definition ? '<div class="growth-block-def">' + esc(b.definition) + '</div>' : '') +
      '</div>' +
      renderBadge(ui, sm.code, sm.label) +
    '</div>';
  }

  function renderMetricBlockFoot(ui, block) {
    var b = block || {};
    return '<div class="growth-block-foot">' +
      renderMeta(ui, b.source || 'flexa.db', b.updatedAt || '—') +
      (b.limitations ? '<div class="growth-limitation"><b>Ограничение:</b> ' + esc(b.limitations) + '</div>' : '') +
    '</div>';
  }

  function renderBarSeries(series, accentClass) {
    var items = Array.isArray(series) ? series : [];
    if (!items.length) {
      return '<div class="rf-empty">Нет временного ряда за выбранный период</div>';
    }
    var max = items.reduce(function (m, it) { return Math.max(m, Number(it.count || 0)); }, 0);
    var total = items.reduce(function (s, it) { return s + Number(it.count || 0); }, 0);
    var firstDate = items[0] ? items[0].date : '';
    var lastDate = items[items.length - 1] ? items[items.length - 1].date : '';
    var bars = items.map(function (it) {
      var cnt = Number(it.count || 0);
      var hPct = max > 0 ? Math.max(cnt > 0 ? 8 : 2, Math.round((cnt / max) * 100)) : 2;
      var cls = 'growth-chart-bar' + (cnt === 0 ? ' is-zero' : '') + (accentClass ? ' ' + accentClass : '');
      return '<div class="growth-chart-col" title="' + esc(it.date + ': ' + cnt) + '">' +
        '<div class="' + cls + '" style="height:' + hPct + '%"></div>' +
      '</div>';
    }).join('');
    return '<div class="growth-chart">' +
      '<div class="growth-chart-bars">' + bars + '</div>' +
      '<div class="growth-chart-axis">' +
        '<span>' + esc(firstDate) + '</span>' +
        '<span>Всего за период: <b>' + esc(total) + '</b> · Пик/день: <b>' + esc(max) + '</b></span>' +
        '<span>' + esc(lastDate) + '</span>' +
      '</div>' +
    '</div>';
  }

  function renderShareBars(rows) {
    var items = Array.isArray(rows) ? rows : [];
    var total = items.reduce(function (s, r) { return s + Number(r.count || 0); }, 0);
    if (!items.length || total === 0) {
      return '<div class="rf-empty">Нет заполненных записей</div>';
    }
    return '<div class="growth-share-list">' + items.map(function (r) {
      var cnt = Number(r.count || 0);
      var pct = total > 0 ? Math.round((cnt / total) * 1000) / 10 : 0;
      return '<div class="growth-share-row">' +
        '<div class="growth-share-meta"><span>' + esc(r.label) + '</span><span><b>' + esc(cnt) + '</b> (' + esc(pct) + '%)</span></div>' +
        '<div class="growth-share-track"><div class="growth-share-fill" style="width:' + Math.min(100, pct) + '%"></div></div>' +
      '</div>';
    }).join('') + '</div>';
  }

  function renderRetentionTable(title, block, ui, noteText) {
    var b = block || {};
    var rows = [
      { label: 'D1 (1-е сутки после регистрации)', data: b.d1 || {} },
      { label: 'D7 (7-е сутки после регистрации)', data: b.d7 || {} },
      { label: 'D30 (30-е сутки после регистрации)', data: b.d30 || {} }
    ];
    return '<div class="rf-card">' +
      renderMetricBlockHead(ui, title, b) +
      (b.status === 'unavailable'
        ? '<div class="rf-empty">Источник недоступен</div>'
        : '<div class="rf-table-wrap"><table class="growth-table"><thead><tr><th>Окно</th><th>Когорта</th><th>Вернулись</th><th>Retention</th></tr></thead><tbody>' +
          rows.map(function (r) {
            var d = r.data || {};
            var rateTxt = (d.ratePct !== null && d.ratePct !== undefined) ? (d.ratePct + '%') : 'Недостаточно данных';
            return '<tr>' +
              '<td>' + esc(r.label) + '</td>' +
              '<td>' + esc(fmtNum(d.cohortSize)) + '</td>' +
              '<td>' + esc(fmtNum(d.retainedCount)) + '</td>' +
              '<td>' + renderBadge(ui, d.status === 'ok' ? 'approved' : 'draft', rateTxt) + '</td>' +
            '</tr>';
          }).join('') +
          '</tbody></table></div>') +
      (noteText ? '<div class="growth-note">' + esc(noteText) + '</div>' : '') +
      renderMetricBlockFoot(ui, b) +
    '</div>';
  }

  function renderExternalSourcesCard(ext, ui) {
    var items = (ext && Array.isArray(ext.items)) ? ext.items : [];
    return '<div class="rf-card">' +
      '<div class="growth-block-head">' +
        '<div>' +
          '<h3 class="growth-block-title">Внешние и неподключённые источники</h3>' +
          '<div class="growth-block-def">Показатели без серверного источника не оцениваются приближённо и никогда не подменяются нулями.</div>' +
        '</div>' +
        renderBadge(ui, 'rejected', 'unavailable') +
      '</div>' +
      '<div class="growth-ext-list">' +
      items.map(function (it) {
        return '<div class="growth-ext-row">' +
          '<div class="growth-ext-main">' +
            '<div class="growth-ext-title">' + esc(it.label) + '</div>' +
            '<div class="growth-ext-reason">' + esc(it.reason) + '</div>' +
            '<div class="rf-source-meta">Источник: ' + esc(it.source) + '</div>' +
          '</div>' +
          '<div class="growth-ext-stat">' + renderBadge(ui, 'rejected', it.status || 'unavailable') + '</div>' +
        '</div>';
      }).join('') +
      '</div>' +
      renderMeta(ui, 'externalSources', (ext && ext.updatedAt) || '—') +
    '</div>';
  }

  function mapAuditEntries(entries) {
    return (Array.isArray(entries) ? entries : []).map(function (e) {
      var st = String(e.status || 'ok').toLowerCase();
      var badgeStatus = st === 'error' || st === 'failed' ? 'rejected' : 'done';
      var details = e.detailsText || (e.target ? ('Объект: ' + e.target) : '');
      return {
        action: '[' + (e.module || 'growth') + '] ' + (e.action || 'event'),
        actor: (e.actor || 'admin') + (e.actorIp ? (' · ' + e.actorIp) : ''),
        timestamp: e.timestamp || e.isoTimestamp || '—',
        status: badgeStatus,
        statusLabel: st,
        details: details
      };
    });
  }

  function renderDashboardHtml(overview, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var data = overview || {};
    var sys = data.systemStatus || {};
    var kpis = Array.isArray(data.kpis) ? data.kpis : [];
    var att = Array.isArray(data.attentionItems) ? data.attentionItems : [];
    var mods = Array.isArray(data.modules) ? data.modules : [];
    var auditEntries = mapAuditEntries(data.recentAudit || []);

    var kpiHtml = '<div class="rf-grid-3 growth-kpi-grid">' + kpis.map(function (k) {
      if (ui && typeof ui.renderKpiCard === 'function') {
        return ui.renderKpiCard({
          label: k.label,
          value: k.value,
          delta: k.delta || '',
          source: k.source || 'flexa.db',
          updatedAt: k.updatedAt || data.generatedAt || '—',
          tone: k.status === 'unavailable' ? 'warn' : (k.id === 'moderation_open' && Number(k.value) > 0 ? 'warn' : 'ok')
        });
      }
      return '<div class="rf-card"><b>' + esc(k.label) + '</b><div>' + esc(k.value) + '</div></div>';
    }).join('') + '</div>';

    var attHtml = att.length
      ? att.map(function (a) {
          var badgeCode = a.severity === 'high' ? 'rejected' : (a.severity === 'medium' ? 'pending_approval' : 'draft');
          var badgeLbl = a.severity === 'high' ? 'Важно' : (a.severity === 'medium' ? 'Внимание' : 'Инфо');
          return '<div class="growth-attention-item">' +
            '<div class="growth-attention-top">' +
              '<b>' + esc(a.title) + '</b>' +
              renderBadge(ui, badgeCode, badgeLbl) +
            '</div>' +
            '<div class="growth-attention-desc">' + esc(a.details) + '</div>' +
            '<div class="rf-source-meta">Источник: ' + esc(a.source || 'flexa.db') + '</div>' +
          '</div>';
        }).join('')
      : '<div class="rf-empty">Требующих внимания отклонений нет</div>';

    var auditBlock = (ui && typeof ui.renderAuditLogList === 'function')
      ? ui.renderAuditLogList(auditEntries, {
          title: 'Последние события серверного Audit Log',
          lockLabel: '🛡️ Серверный append-only журнал'
        })
      : '<div class="rf-card">Audit Log</div>';

    return '<div class="growth-stack">' +
      '<div class="rf-card">' +
        '<div class="growth-status-bar">' +
          '<div class="growth-status-pill"><span>БД:</span> <b>' + esc(sys.dbHealth || 'ok') + '</b></div>' +
          '<div class="growth-status-pill"><span>FREE_ACCESS_MODE:</span> <b>' + (sys.freeAccessMode ? 'ВКЛ (бесплатный доступ)' : 'ВЫКЛ (платные PRO)') + '</b></div>' +
          '<div class="growth-status-pill"><span>AI Growth LLM:</span> <b>Отключён (PR 4.1)</b></div>' +
          '<div class="growth-status-pill"><span>Audit Log:</span> <b>' + (sys.auditAppendOnly ? 'SQLite append-only' : 'Проверка') + ' (' + esc(sys.auditTotal || 0) + ')</b></div>' +
        '</div>' +
        renderMeta(ui, 'flexa.db + site catalog', data.generatedAt || '—') +
      '</div>' +
      kpiHtml +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Требует внимания</h3><div class="growth-block-def">Автоматические детерминированные проверки состояния платформы</div></div>' +
        '</div>' +
        '<div class="growth-attention-list">' + attHtml + '</div>' +
      '</div>' +
      auditBlock +
      '<div class="growth-inline-actions"><button type="button" class="rf-btn rf-btn-alt" data-growth-jump="audit">Открыть весь журнал Audit (' + esc(sys.auditTotal || 0) + ')</button>' +
      '<button type="button" class="rf-btn rf-btn-alt" data-growth-jump="analytics">Перейти в Analytics (7 / 30 / 90д)</button></div>' +
      '<div class="rf-card">' +
        '<div class="growth-block-head"><div><h3 class="growth-block-title">Модули AI Growth</h3><div class="growth-block-def">Этап 4 реализуется поэтапно; AI Coach атлетов (ai.json) полностью изолирован.</div></div></div>' +
        '<div class="rf-grid-4">' +
          mods.map(function (m) {
            return '<div class="rf-card-inset growth-mod-card">' +
              '<div class="growth-mod-top"><b>' + esc(m.title) + '</b>' + renderBadge(ui, m.status, m.statusLabel) + '</div>' +
            '</div>';
          }).join('') +
        '</div>' +
      '</div>' +
    '</div>';
  }

  function renderAnalyticsHtml(analytics, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var data = analytics || {};
    var days = Number(data.periodDays || (opts && opts.days) || 30);
    var dq = data.dataQuality || {};
    var degradedBanner = data.degraded
      ? '<div class="rf-card growth-degraded"><b>Аналитика в режиме degraded (' + esc(dq.dbHealth || 'unavailable') + '):</b> ' + esc(dq.error || 'БД недоступна') + '. Отсутствующие метрики помечены как <code>unavailable</code>.</div>'
      : '';

    var reg = data.registrations || {};
    var eng = data.engagement || {};
    var lEng = eng.loginActivity || {};
    var wEng = eng.workoutActivity || {};
    var ret = data.retention || {};
    var act = data.activation || {};
    var wo = data.workouts || {};
    var pop = data.popularCatalog || {};
    var rpe = data.rpeDistribution || {};
    var prof = data.userProfiles || {};
    var coach = data.aiCoach || {};
    var mon = data.monetization || {};
    var mod = data.moderation || {};

    var authBy = reg.byAuthMethod || {};
    var rpePer = rpe.period || {};
    var rpeRows = [
      { label: '😌 Легко (easy)', count: (rpePer.easy && rpePer.easy.count) || 0 },
      { label: '💪 В самый раз (good)', count: (rpePer.good && rpePer.good.count) || 0 },
      { label: '🥵 Тяжело (hard)', count: (rpePer.hard && rpePer.hard.count) || 0 },
      { label: 'Без оценки (unrated)', count: (rpePer.unrated && rpePer.unrated.count) || 0 }
    ];

    var goalsMap = prof.goals || {};
    var goalLabels = {
      fat_loss: 'Похудение',
      muscle_gain: 'Набор массы',
      recomp: 'Рельеф',
      strength: 'Сила',
      endurance: 'Выносливость',
      health: 'Здоровье',
      unspecified: 'Не указано'
    };
    var goalRows = Object.keys(goalLabels).map(function (k) {
      return { label: goalLabels[k], count: Number(goalsMap[k] || 0) };
    });

    var levelsMap = prof.levels || {};
    var levelLabels = {
      beginner: 'Новичок',
      intermediate: 'Средний',
      advanced: 'Продвинутый',
      unspecified: 'Не указано'
    };
    var levelRows = Object.keys(levelLabels).map(function (k) {
      return { label: levelLabels[k], count: Number(levelsMap[k] || 0) };
    });

    var topProgs = Array.isArray(pop.topPrograms) ? pop.topPrograms : [];
    var topWos = Array.isArray(pop.topWorkouts) ? pop.topWorkouts : [];
    var payPer = mon.paymentsInPeriodByStatus || {};
    var repSt = mod.reportsByStatus || {};

    return '<div class="growth-stack">' +
      '<div class="rf-card growth-toolbar">' +
        '<div class="growth-period-group">' +
          '<span class="growth-period-lbl">Период:</span>' +
          [7, 30, 90].map(function (d) {
            return '<button type="button" class="rf-btn ' + (days === d ? 'rf-btn-primary' : 'rf-btn-alt') + '" data-growth-days="' + d + '">' + d + ' дней</button>';
          }).join('') +
        '</div>' +
        '<div class="growth-toolbar-right">' +
          '<span class="rf-source-meta">Сформировано: ' + esc(data.generatedAt || '—') + ' · БД: <b>' + esc(dq.dbHealth || 'ok') + '</b></span>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-growth-refresh="analytics">↻ Обновить</button>' +
        '</div>' +
      '</div>' +
      degradedBanner +
      '<div class="rf-grid-2">' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Входы в аккаунт (Auth DAU/WAU/MAU)', lEng) +
          '<div class="growth-kv-grid">' +
            '<div class="growth-kv"><span>DAU (24ч)</span><b>' + esc(fmtNum(lEng.dau)) + '</b></div>' +
            '<div class="growth-kv"><span>WAU (7д)</span><b>' + esc(fmtNum(lEng.wau)) + '</b></div>' +
            '<div class="growth-kv"><span>MAU (30д)</span><b>' + esc(fmtNum(lEng.mau)) + '</b></div>' +
          '</div>' +
          renderMetricBlockFoot(ui, lEng) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Фактические тренировки (Workout DAU/WAU/MAU)', wEng) +
          '<div class="growth-kv-grid">' +
            '<div class="growth-kv"><span>DAU (24ч)</span><b>' + esc(fmtNum(wEng.dau)) + '</b></div>' +
            '<div class="growth-kv"><span>WAU (7д)</span><b>' + esc(fmtNum(wEng.wau)) + '</b></div>' +
            '<div class="growth-kv"><span>MAU (30д)</span><b>' + esc(fmtNum(wEng.mau)) + '</b></div>' +
          '</div>' +
          '<div class="growth-kv-sub">За период: <b>' + esc(fmtNum(wEng.workoutsInPeriod)) + '</b> · Всего: <b>' + esc(fmtNum(wEng.workoutsTotal)) + '</b> · Медиана: <b>' + esc(fmtDurSec(wEng.medianDurationSec)) + '</b></div>' +
          renderMetricBlockFoot(ui, wEng) +
        '</div>' +
      '</div>' +
      '<div class="rf-grid-2">' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Регистрации (' + days + 'д)', reg) +
          '<div class="growth-kv-grid">' +
            '<div class="growth-kv"><span>Всего</span><b>' + esc(fmtNum(reg.totalUsers)) + '</b></div>' +
            '<div class="growth-kv"><span>Новых (' + days + 'д)</span><b>' + esc(fmtNum(reg.newInPeriod)) + '</b></div>' +
            '<div class="growth-kv"><span>Telegram / Email</span><b>' + esc(fmtNum(authBy.telegram)) + ' / ' + esc(fmtNum(authBy.password)) + '</b></div>' +
          '</div>' +
          renderBarSeries(reg.dailySeries, 'is-reg') +
          renderMetricBlockFoot(ui, reg) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Завершённые тренировки (' + days + 'д)', wo) +
          '<div class="growth-kv-grid">' +
            '<div class="growth-kv"><span>За период</span><b>' + esc(fmtNum(wo.completedInPeriod)) + '</b></div>' +
            '<div class="growth-kv"><span>Всего в БД</span><b>' + esc(fmtNum(wo.completedTotal)) + '</b></div>' +
            '<div class="growth-kv"><span>Ср. упр./трен.</span><b>' + esc(fmtNum(wo.avgExercisesPerWorkout)) + '</b></div>' +
          '</div>' +
          renderBarSeries(wo.dailySeries, 'is-wo') +
          renderMetricBlockFoot(ui, wo) +
        '</div>' +
      '</div>' +
      '<div class="rf-grid-2">' +
        renderRetentionTable('Когортный Retention тренировок', ret.workoutRetention, ui, 'Учитываются только фактические тренировки из user_state.hist.') +
        renderRetentionTable('Возврат в аккаунт (Login Proxy)', ret.loginRetention, ui, 'Рассчитан отдельно по last_login_at (не является тренировочным retention).') +
      '</div>' +
      '<div class="rf-grid-2">' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Активация пользователей', act) +
          '<div class="growth-kv-list">' +
            '<div class="growth-kv-line"><span>Завершили ≥ 1 тренировки</span><b>' + esc(fmtNum(act.firstWorkoutUsers)) + ' (' + esc(fmtNum(act.firstWorkoutRatePct, '%')) + ')</b></div>' +
            '<div class="growth-kv-line"><span>Заполнили fitnessProfile</span><b>' + esc(fmtNum(act.profileCompletedUsers)) + ' (' + esc(fmtNum(act.profileCompletedRatePct, '%')) + ')</b></div>' +
            '<div class="growth-kv-line"><span>Начали программу</span><b>' + esc(fmtNum(act.programStartedUsers)) + ' (' + esc(fmtNum(act.programStartedRatePct, '%')) + ')</b></div>' +
          '</div>' +
          renderMetricBlockFoot(ui, act) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Распределение RPE (' + days + 'д)', rpe) +
          (rpe.status === 'unavailable' ? '<div class="rf-empty">Недоступно</div>' : renderShareBars(rpeRows)) +
          renderMetricBlockFoot(ui, rpe) +
        '</div>' +
      '</div>' +
      '<div class="rf-grid-2">' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Цели пользователей (fitnessProfile)', prof) +
          (prof.status === 'unavailable' ? '<div class="rf-empty">Недоступно</div>' : renderShareBars(goalRows)) +
          renderMetricBlockFoot(ui, prof) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Уровни подготовки (fitnessProfile)', prof) +
          (prof.status === 'unavailable' ? '<div class="rf-empty">Недоступно</div>' : renderShareBars(levelRows)) +
          renderMetricBlockFoot(ui, prof) +
        '</div>' +
      '</div>' +
      '<div class="rf-grid-2">' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Популярные программы каталога', pop) +
          (topProgs.length
            ? '<div class="rf-table-wrap"><table class="growth-table"><thead><tr><th>ID</th><th>Программа</th><th>Польз.</th><th>Дней выполн.</th></tr></thead><tbody>' +
              topProgs.map(function (p) {
                return '<tr><td>#' + esc(p.id) + '</td><td>' + esc(p.title) + '</td><td><b>' + esc(p.usersCount) + '</b></td><td>' + esc(p.completedDaysTotal) + '</td></tr>';
              }).join('') + '</tbody></table></div>'
            : '<div class="rf-empty">Нет синхронизированных программ</div>') +
          renderMetricBlockFoot(ui, pop) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Популярные тренировки каталога', pop) +
          (topWos.length
            ? '<div class="rf-table-wrap"><table class="growth-table"><thead><tr><th>ID</th><th>Тренировка</th><th>За период</th><th>Всего</th></tr></thead><tbody>' +
              topWos.map(function (w) {
                return '<tr><td>#' + esc(w.id) + '</td><td>' + esc(w.title) + '</td><td><b>' + esc(w.completionsPeriod) + '</b></td><td>' + esc(w.completionsTotal) + '</td></tr>';
              }).join('') + '</tbody></table></div>'
            : '<div class="rf-empty">Нет завершённых тренировок каталога</div>') +
          renderMetricBlockFoot(ui, pop) +
        '</div>' +
      '</div>' +
      '<div class="rf-grid-3">' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'AI Coach (окно ' + esc(coach.windowDays || 14) + ' дней)', coach) +
          '<div class="growth-kv-list">' +
            '<div class="growth-kv-line"><span>Активных сессий (14д)</span><b>' + esc(fmtNum(coach.activeSessions14d)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Авторизованные / гости</span><b>' + esc(fmtNum(coach.userSessions14d)) + ' / ' + esc(fmtNum(coach.guestSessions14d)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Сообщений (ср. на сессию)</span><b>' + esc(fmtNum(coach.totalMessages14d)) + ' (' + esc(fmtNum(coach.avgMessagesPerSession)) + ')</b></div>' +
            '<div class="growth-kv-line"><span>Вовлечение аккаунтов</span><b>' + esc(fmtNum(coach.adoptionRatePct, '%')) + '</b></div>' +
          '</div>' +
          renderMetricBlockFoot(ui, coach) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Монетизация и PRO', mon) +
          '<div class="growth-kv-list">' +
            '<div class="growth-kv-line"><span>FREE_ACCESS_MODE</span><b>' + (mon.freeAccessMode ? 'ВКЛ (бесплатно)' : 'ВЫКЛ') + '</b></div>' +
            '<div class="growth-kv-line"><span>Реальных PRO в БД</span><b>' + esc(fmtNum(mon.realProUsersActive)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Платежи (' + days + 'д): paid / pending</span><b>' + esc(fmtNum(payPer.paid)) + ' / ' + esc(fmtNum(payPer.pending)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Выручка paid (' + days + 'д)</span><b>' + esc(fmtNum(mon.paidRevenueInPeriod, ' ₽')) + '</b></div>' +
          '</div>' +
          renderMetricBlockFoot(ui, mon) +
        '</div>' +
        '<div class="rf-card">' +
          renderMetricBlockHead(ui, 'Модерация и комьюнити', mod) +
          '<div class="growth-kv-list">' +
            '<div class="growth-kv-line"><span>Новых жалоб</span><b>' + esc(fmtNum(repSt.new)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Рассмотрено / закрыто</span><b>' + esc(fmtNum(repSt.reviewed)) + ' / ' + esc(fmtNum(repSt.closed)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Ср. время разбора</span><b>' + esc(fmtHours(mod.avgReviewTimeHours)) + '</b></div>' +
            '<div class="growth-kv-line"><span>Дружб / блокировок</span><b>' + esc(fmtNum(mod.acceptedFriendships)) + ' / ' + esc(fmtNum(mod.activeBlocks)) + '</b></div>' +
          '</div>' +
          renderMetricBlockFoot(ui, mod) +
        '</div>' +
      '</div>' +
      renderExternalSourcesCard(data.externalSources, ui) +
    '</div>';
  }

  function renderAuditHtml(audit, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var f = (opts && opts.filters) || {};
    var data = audit || {};
    var entries = mapAuditEntries(data.entries || []);
    var limit = Number(data.limit || 25);
    var offset = Number(data.offset || 0);
    var total = Number(data.total || 0);
    var fromIdx = total > 0 ? (offset + 1) : 0;
    var toIdx = Math.min(total, offset + entries.length);
    var modulesList = Array.isArray(data.availableModules) && data.availableModules.length
      ? data.availableModules
      : ['auth', 'users', 'content', 'growth'];

    var modOpts = ['<option value="">Все модули</option>'].concat(modulesList.map(function (m) {
      return '<option value="' + esc(m) + '"' + (f.module === m ? ' selected' : '') + '>' + esc(m) + '</option>';
    })).join('');

    var stOpts = [
      ['', 'Все статусы'],
      ['ok', 'ok'],
      ['error', 'error']
    ].map(function (pair) {
      return '<option value="' + esc(pair[0]) + '"' + ((f.status || '') === pair[0] ? ' selected' : '') + '>' + esc(pair[1]) + '</option>';
    }).join('');

    var listHtml = (ui && typeof ui.renderAuditLogList === 'function')
      ? ui.renderAuditLogList(entries, {
          title: 'Серверный журнал действий AI Growth',
          lockLabel: '🛡️ Серверный append-only журнал'
        })
      : '<div class="rf-card" data-readonly="true">Audit Log</div>';

    return '<div class="growth-stack">' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div>' +
            '<h3 class="growth-block-title">Защищённый серверный Audit Log</h3>' +
            '<div class="growth-block-def">SQLite-таблица <code>growth_audit_log</code> защищена триггерами <code>BEFORE UPDATE</code> и <code>BEFORE DELETE</code>; маршрутов изменения и удаления не существует.</div>' +
          '</div>' +
          renderBadge(ui, data.appendOnlyEnforced ? 'approved' : 'pending_approval', data.appendOnlyEnforced ? 'Triggers ON' : 'Проверка БД') +
        '</div>' +
        '<div class="growth-audit-filters">' +
          '<label class="growth-filter-field"><span>Модуль</span><select id="growth-audit-mod">' + modOpts + '</select></label>' +
          '<label class="growth-filter-field"><span>Статус</span><select id="growth-audit-st">' + stOpts + '</select></label>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-growth-refresh="audit">↻ Обновить</button>' +
        '</div>' +
        renderMeta(ui, data.source || 'flexa.db:growth_audit_log', data.updatedAt || '—') +
      '</div>' +
      listHtml +
      '<div class="rf-card growth-pager">' +
        '<span class="rf-source-meta">Показано: ' + esc(fromIdx) + '–' + esc(toIdx) + ' из ' + esc(total) + '</span>' +
        '<div class="growth-pager-btns">' +
          '<button type="button" class="rf-btn rf-btn-alt" data-growth-page="prev"' + (offset <= 0 ? ' disabled' : '') + '>← Назад</button>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-growth-page="next"' + (!data.hasMore ? ' disabled' : '') + '>Вперёд →</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }

  function render(el, deps) {
    if (!el) return;
    var d = deps || {};
    var api = d.api;
    var ui = d.ui || DefaultUI;
    var state = {
      subTab: d.initialSubTab || 'dashboard',
      days: 30,
      auditLimit: 25,
      auditOffset: 0,
      auditModule: '',
      auditStatus: '',
      loading: false,
      error: '',
      overview: null,
      analytics: null,
      audit: null
    };

    function renderFrame(bodyHtml) {
      var navTabs = [
        { id: 'dashboard', label: '📊 Dashboard' },
        { id: 'analytics', label: '📈 Analytics' },
        { id: 'audit', label: '🛡️ Audit Log' }
      ];
      el.innerHTML =
        '<div class="rf-card growth-shell-header">' +
          '<div class="growth-hub-banner">' +
            '<div>' +
              '<h2 style="margin:0;font-size:18px">RizzaFit AI Growth</h2>' +
              '<p style="margin:4px 0 0;color:var(--mut);font-size:13px">PR 4.1 Foundation: детерминированная аналитика SQLite и неизменяемый серверный аудит.</p>' +
            '</div>' +
            renderBadge(ui, 'done', 'PR 4.1: Foundation') +
          '</div>' +
          '<div class="growth-subnav" role="tablist">' +
            navTabs.map(function (t) {
              return '<button type="button" role="tab" aria-selected="' + (state.subTab === t.id ? 'true' : 'false') + '" ' +
                'class="growth-subnav-btn' + (state.subTab === t.id ? ' on' : '') + '" data-growth-tab="' + t.id + '">' + esc(t.label) + '</button>';
            }).join('') +
          '</div>' +
        '</div>' +
        '<div id="growth-sub-body">' + bodyHtml + '</div>';

      el.querySelectorAll('[data-growth-tab]').forEach(function (btn) {
        btn.onclick = function () {
          state.subTab = btn.getAttribute('data-growth-tab');
          loadCurrent(true);
        };
      });
      el.querySelectorAll('[data-growth-jump]').forEach(function (btn) {
        btn.onclick = function () {
          state.subTab = btn.getAttribute('data-growth-jump');
          loadCurrent(true);
        };
      });
      el.querySelectorAll('[data-growth-days]').forEach(function (btn) {
        btn.onclick = function () {
          state.days = Number(btn.getAttribute('data-growth-days')) || 30;
          loadCurrent(true);
        };
      });
      el.querySelectorAll('[data-growth-refresh]').forEach(function (btn) {
        btn.onclick = function () { loadCurrent(true); };
      });
      var modSel = el.querySelector('#growth-audit-mod');
      if (modSel) {
        modSel.onchange = function () {
          state.auditModule = modSel.value || '';
          state.auditOffset = 0;
          loadCurrent(true);
        };
      }
      var stSel = el.querySelector('#growth-audit-st');
      if (stSel) {
        stSel.onchange = function () {
          state.auditStatus = stSel.value || '';
          state.auditOffset = 0;
          loadCurrent(true);
        };
      }
      var prevBtn = el.querySelector('[data-growth-page="prev"]');
      if (prevBtn) {
        prevBtn.onclick = function () {
          state.auditOffset = Math.max(0, state.auditOffset - state.auditLimit);
          loadCurrent(true);
        };
      }
      var nextBtn = el.querySelector('[data-growth-page="next"]');
      if (nextBtn) {
        nextBtn.onclick = function () {
          state.auditOffset = state.auditOffset + state.auditLimit;
          loadCurrent(true);
        };
      }
    }

    async function loadCurrent(forceRefresh) {
      if (typeof api !== 'function') {
        renderFrame('<div class="rf-card">API недоступно</div>');
        return;
      }
      if (state.loading && !forceRefresh) return;
      state.loading = true;
      state.error = '';
      renderFrame('<div class="rf-card growth-loading">Загрузка данных ' + esc(state.subTab) + '…</div>');
      try {
        if (state.subTab === 'dashboard') {
          state.overview = await api('admin/growth/overview?days=' + state.days);
          renderFrame(renderDashboardHtml(state.overview, { ui: ui }));
        } else if (state.subTab === 'analytics') {
          state.analytics = await api('admin/growth/analytics?days=' + state.days);
          renderFrame(renderAnalyticsHtml(state.analytics, { ui: ui, days: state.days }));
        } else if (state.subTab === 'audit') {
          var q = 'admin/growth/audit?limit=' + state.auditLimit + '&offset=' + state.auditOffset;
          if (state.auditModule) q += '&module=' + encodeURIComponent(state.auditModule);
          if (state.auditStatus) q += '&status=' + encodeURIComponent(state.auditStatus);
          state.audit = await api(q);
          renderFrame(renderAuditHtml(state.audit, { ui: ui, filters: { module: state.auditModule, status: state.auditStatus } }));
        }
      } catch (e) {
        state.error = e && e.message ? e.message : 'Ошибка загрузки';
        renderFrame('<div class="rf-card growth-degraded"><b>Ошибка:</b> ' + esc(state.error) + ' <button type="button" class="rf-btn rf-btn-alt" data-growth-refresh="retry" style="margin-left:8px">Повторить</button></div>');
      } finally {
        state.loading = false;
      }
    }

    loadCurrent(true);
  }

  return {
    render: render,
    renderDashboardHtml: renderDashboardHtml,
    renderAnalyticsHtml: renderAnalyticsHtml,
    renderAuditHtml: renderAuditHtml,
    _renderBarSeries: renderBarSeries
  };
});
