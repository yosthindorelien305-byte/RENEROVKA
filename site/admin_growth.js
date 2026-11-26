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
    var sm = b.isProxy && b.status === 'ok'
      ? { code: 'pending_approval', label: 'Прокси (last_login_at)' }
      : statusForMetric(b.status, 'Актуально');
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
      { key: 'D1', fallbackWin: '[+1д, +2д) · мин. возраст 2д', data: b.d1 || {} },
      { key: 'D7', fallbackWin: '[+7д, +8д) · мин. возраст 8д', data: b.d7 || {} },
      { key: 'D30', fallbackWin: '[+30д, +31д) · мин. возраст 31д', data: b.d30 || {} }
    ];
    return '<div class="rf-card">' +
      renderMetricBlockHead(ui, title, b) +
      (b.status === 'unavailable'
        ? '<div class="rf-empty">Источник недоступен</div>'
        : '<div class="rf-table-wrap"><table class="growth-table"><thead><tr><th>Окно наблюдения</th><th>Зрелая когорта</th><th>Вернулись</th><th>Retention</th></tr></thead><tbody>' +
          rows.map(function (r) {
            var d = r.data || {};
            var hasRate = d.ratePct !== null && d.ratePct !== undefined && Number(d.cohortSize || 0) > 0;
            var rateTxt = hasRate ? (d.ratePct + '%') : 'Недостаточно данных';
            var winLabel = r.key + ': ' + (d.windowDefinition || r.fallbackWin);
            var excl = Number(d.excludedIncompleteCount || 0);
            var cohortCell = fmtNum(d.cohortSize) + (excl > 0 ? (' (исключено неполн.: ' + excl + ')') : '');
            return '<tr>' +
              '<td>' + esc(winLabel) + '</td>' +
              '<td>' + esc(cohortCell) + '</td>' +
              '<td>' + esc(fmtNum(d.retainedCount)) + '</td>' +
              '<td>' + renderBadge(ui, hasRate ? (b.isProxy ? 'pending_approval' : 'approved') : 'draft', rateTxt) + '</td>' +
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
    var lEng = eng.lastLoginActivity || eng.loginActivity || {};
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
          renderMetricBlockHead(ui, 'Последний вход в аккаунт (прокси: 24ч / 7д / 30д)', lEng) +
          '<div class="growth-kv-grid">' +
            '<div class="growth-kv"><span>За 24ч (прокси)</span><b>' + esc(fmtNum(lEng.last24h != null ? lEng.last24h : lEng.dau)) + '</b></div>' +
            '<div class="growth-kv"><span>За 7д (прокси)</span><b>' + esc(fmtNum(lEng.last7d != null ? lEng.last7d : lEng.wau)) + '</b></div>' +
            '<div class="growth-kv"><span>За 30д (прокси)</span><b>' + esc(fmtNum(lEng.last30d != null ? lEng.last30d : lEng.mau)) + '</b></div>' +
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
        renderRetentionTable('Когортный Retention тренировок', ret.workoutRetention, ui, 'Учитываются только зрелые когорты (возраст >= N+1 дн.) и фактические тренировки из user_state.hist (День 0 не засчитывается).') +
        renderRetentionTable('Возврат по последнему входу (прокси)', ret.lastLoginReturnProxy || ret.loginRetention, ui, 'Rolling-прокси по единственному полю last_login_at среди зрелых когорт; не отражает точный исторический день N.') +
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

  var TASK_STATUS_LABELS = {
    open: 'Открыта',
    in_progress: 'В работе',
    pending_approval: 'На одобрении',
    approved: 'Одобрена',
    rejected: 'Отклонена',
    completed: 'Завершена',
    cancelled: 'Отменена'
  };

  var TASK_STATUS_BADGE = {
    open: 'draft',
    in_progress: 'in_progress',
    pending_approval: 'pending_approval',
    approved: 'approved',
    rejected: 'rejected',
    completed: 'done',
    cancelled: 'rejected'
  };

  var PROP_STATUS_LABELS = {
    pending: 'Ожидает',
    approved: 'Одобрено (без автодеплоя)',
    rejected: 'Отклонено',
    applied: 'Применено',
    cancelled: 'Отменено'
  };

  var PROP_STATUS_BADGE = {
    pending: 'pending_approval',
    approved: 'approved',
    rejected: 'rejected',
    applied: 'published',
    cancelled: 'draft'
  };

  var SEV_LABELS = {
    critical: 'CRITICAL',
    high: 'HIGH',
    medium: 'MEDIUM',
    low: 'LOW',
    info: 'INFO'
  };

  var SEV_BADGE = {
    critical: 'rejected',
    high: 'rejected',
    medium: 'pending_approval',
    low: 'draft',
    info: 'published'
  };

  function renderTasksHtml(tasksData, detailData, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var f = (opts && opts.filters) || {};
    var data = tasksData || {};
    var tasks = Array.isArray(data.tasks) ? data.tasks : [];
    var detail = detailData && detailData.task ? detailData : null;
    var cats = ['SEO', 'Content', 'Technical', 'Performance', 'Analytics', 'Other'];
    var prios = ['critical', 'high', 'medium', 'low'];
    var sts = ['open', 'in_progress', 'pending_approval', 'approved', 'rejected', 'completed', 'cancelled'];

    var listHtml = tasks.length
      ? '<div class="growth-item-list">' + tasks.map(function (t) {
          var isSel = detail && detail.task.id === t.id;
          return '<div class="growth-item-row' + (isSel ? ' is-selected' : '') + '">' +
            '<div class="growth-item-main">' +
              '<div class="growth-item-top">' +
                '<button type="button" class="growth-link-btn" data-task-select="' + esc(t.id) + '">#' + esc(t.id) + ' · ' + esc(t.title) + '</button>' +
                '<div class="growth-item-badges">' +
                  renderBadge(ui, SEV_BADGE[t.priority] || 'draft', t.priority) +
                  renderBadge(ui, TASK_STATUS_BADGE[t.status] || 'draft', TASK_STATUS_LABELS[t.status] || t.status) +
                '</div>' +
              '</div>' +
              '<div class="growth-item-meta">Категория: <b>' + esc(t.category) + '</b>' +
                (t.targetUrl
                  ? (' · URL (' + (t.targetUrlType === 'external' ? 'внешний, без перехода' : 'внутренний') + '): <code>' + esc(t.targetUrl) + '</code>')
                  : '') +
                (t.seoIssueId ? (' · SEO #' + esc(t.seoIssueId)) : '') +
                ' · Обновлено: ' + esc(t.updatedAtIso || '—') +
              '</div>' +
            '</div>' +
          '</div>';
        }).join('') + '</div>'
      : '<div class="rf-empty">Задачи по выбранным фильтрам не найдены. Создайте задачу вручную или из результатов SEO-аудита.</div>';

    var detailHtml = '';
    if (detail) {
      var dt = detail.task;
      var hist = Array.isArray(detail.history) ? detail.history : [];
      var transitions = Array.isArray(dt.allowedTransitions) ? dt.allowedTransitions : [];
      var linkedProps = Array.isArray(detail.proposals) ? detail.proposals : [];
      detailHtml = '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div>' +
            '<h3 class="growth-block-title">Задача #' + esc(dt.id) + ': ' + esc(dt.title) + '</h3>' +
            '<div class="growth-block-def">' + esc(dt.description || 'Описание не заполнено.') + '</div>' +
          '</div>' +
          renderBadge(ui, TASK_STATUS_BADGE[dt.status] || 'draft', TASK_STATUS_LABELS[dt.status] || dt.status) +
        '</div>' +
        '<div class="growth-kv-list" style="margin-bottom:12px">' +
          '<div class="growth-kv-line"><span>Категория / Приоритет</span><b>' + esc(dt.category) + ' / ' + esc(dt.priority) + '</b></div>' +
          (dt.targetUrl
            ? '<div class="growth-kv-line"><span>Целевой URL (' + (dt.targetUrlType === 'external' ? 'внешний · без перехода' : 'внутренний') + ')</span><b><code>' + esc(dt.targetUrl) + '</code></b></div>'
            : '') +
          (detail.seoIssue ? '<div class="growth-kv-line"><span>Связанная SEO-проблема</span><b>#' + esc(detail.seoIssue.id) + ' (' + esc(detail.seoIssue.issueType) + ' · ' + esc(detail.seoIssue.severity) + ')</b></div>' : '') +
          '<div class="growth-kv-line"><span>Создана / Обновлена</span><b>' + esc(dt.createdAtIso) + ' / ' + esc(dt.updatedAtIso) + '</b></div>' +
        '</div>' +
        '<div class="growth-audit-filters">' +
          '<label class="growth-filter-field"><span>Приоритет</span><select id="growth-task-edit-prio">' +
            prios.map(function (p) { return '<option value="' + p + '"' + (dt.priority === p ? ' selected' : '') + '>' + p + '</option>'; }).join('') +
          '</select></label>' +
          '<label class="growth-filter-field" style="flex:1 1 180px"><span>Комментарий к изменению</span><input id="growth-task-edit-note" class="growth-input" type="text" placeholder="Причина изменения"></label>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-task-save-prio="' + esc(dt.id) + '">Сохранить приоритет</button>' +
        '</div>' +
        '<div class="growth-inline-actions" style="margin-bottom:12px">' +
          transitions.map(function (st) {
            return '<button type="button" class="rf-btn rf-btn-alt" data-task-status="' + esc(dt.id) + ':' + esc(st) + '">→ ' + esc(TASK_STATUS_LABELS[st] || st) + '</button>';
          }).join('') +
        '</div>' +
        (linkedProps.length ? '<div class="growth-note" style="margin-bottom:10px"><b>Связанные предложения:</b> ' +
          linkedProps.map(function (lp) {
            return '<button type="button" class="growth-link-btn" data-prop-jump="' + esc(lp.id) + '">Proposal #' + esc(lp.id) + ' (' + esc(lp.status) + ')</button>';
          }).join(' · ') + '</div>' : '') +
        '<h4 style="margin:8px 0 6px;font-size:13px">История изменений задачи</h4>' +
        (hist.length
          ? '<div class="growth-history-list">' + hist.map(function (h) {
              return '<div class="growth-history-row"><b>' + esc(h.field) + '</b>: <code>' + esc(h.oldValue || '—') + '</code> → <code>' + esc(h.newValue || '—') + '</code>' +
                (h.note ? (' · ' + esc(h.note)) : '') + ' <span class="rf-source-meta">' + esc(h.actor) + ' · ' + esc(h.createdAtIso) + '</span></div>';
            }).join('') + '</div>'
          : '<div class="rf-empty">История пуста</div>') +
      '</div>';
    }

    return '<div class="growth-stack">' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Создать задачу развития</h3><div class="growth-block-def">Все изменения задач фиксируются в истории и append-only Audit Log.</div></div>' +
        '</div>' +
        '<div class="growth-form-grid">' +
          '<label class="growth-filter-field growth-col-span2"><span>Заголовок *</span><input id="growth-new-task-title" class="growth-input" type="text" placeholder="Например: Добавить canonical и OG на новую статью"></label>' +
          '<label class="growth-filter-field"><span>Категория</span><select id="growth-new-task-cat">' + cats.map(function (c) { return '<option value="' + c + '">' + c + '</option>'; }).join('') + '</select></label>' +
          '<label class="growth-filter-field"><span>Приоритет</span><select id="growth-new-task-prio">' + prios.map(function (p) { return '<option value="' + p + '"' + (p === 'medium' ? ' selected' : '') + '>' + p + '</option>'; }).join('') + '</select></label>' +
          '<label class="growth-filter-field"><span>Целевой URL</span><input id="growth-new-task-url" class="growth-input" type="text" placeholder="/ или /fitify/"></label>' +
          '<label class="growth-filter-field" style="grid-column:1 / -1"><span>Описание</span><textarea id="growth-new-task-desc" class="growth-textarea" rows="2" placeholder="Подробности задачи и ожидаемый результат"></textarea></label>' +
        '</div>' +
        '<div class="growth-inline-actions" style="margin-top:10px"><button type="button" class="rf-btn rf-btn-primary" id="growth-create-task-btn">+ Создать задачу</button></div>' +
      '</div>' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Список задач (' + esc(data.total || tasks.length) + ')</h3></div>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-growth-refresh="tasks">↻ Обновить</button>' +
        '</div>' +
        '<div class="growth-audit-filters">' +
          '<label class="growth-filter-field"><span>Статус</span><select id="growth-task-flt-st"><option value="">Все</option>' +
            sts.map(function (s) { return '<option value="' + s + '"' + (f.status === s ? ' selected' : '') + '>' + esc(TASK_STATUS_LABELS[s] || s) + '</option>'; }).join('') +
          '</select></label>' +
          '<label class="growth-filter-field"><span>Категория</span><select id="growth-task-flt-cat"><option value="">Все</option>' +
            cats.map(function (c) { return '<option value="' + c + '"' + (f.category === c ? ' selected' : '') + '>' + c + '</option>'; }).join('') +
          '</select></label>' +
          '<label class="growth-filter-field"><span>Приоритет</span><select id="growth-task-flt-prio"><option value="">Все</option>' +
            prios.map(function (p) { return '<option value="' + p + '"' + (f.priority === p ? ' selected' : '') + '>' + p + '</option>'; }).join('') +
          '</select></label>' +
        '</div>' +
        listHtml +
        renderMeta(ui, data.source || 'flexa.db:growth_tasks', data.updatedAt || '—') +
      '</div>' +
      detailHtml +
    '</div>';
  }

  function renderSeoAuditHtml(auditData, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var sevFilter = (opts && opts.severity) || '';
    var d = auditData || {};
    var sum = d.summary || {};
    var pages = Array.isArray(d.pages) ? d.pages : [];
    var issues = Array.isArray(d.issues) ? d.issues : [];
    var unknowns = Array.isArray(d.unknownChecks) ? d.unknownChecks : [];
    var sevs = ['critical', 'high', 'medium', 'low', 'info'];

    var summaryHtml = '<div class="growth-status-bar">' +
      '<div class="growth-status-pill"><span>Страниц:</span> <b>' + esc(d.pagesChecked || 0) + '</b></div>' +
      sevs.map(function (sv) {
        return '<div class="growth-status-pill"><span>' + esc(SEV_LABELS[sv]) + ':</span> <b>' + esc(sum[sv] || 0) + '</b></div>';
      }).join('') +
    '</div>';

    var pagesHtml = pages.length
      ? '<div class="rf-table-wrap"><table class="growth-table"><thead><tr><th>URL</th><th>Роль</th><th>Title</th><th>H1</th><th>Sitemap</th><th>Индекс</th></tr></thead><tbody>' +
        pages.map(function (p) {
          return '<tr>' +
            '<td><code>' + esc(p.pageUrl) + '</code></td>' +
            '<td>' + esc(p.role) + '</td>' +
            '<td>' + esc(p.title ? (p.titleLength + ' симв.') : 'нет') + '</td>' +
            '<td>' + esc(p.h1Count) + '</td>' +
            '<td>' + (p.inSitemap ? 'Да' : 'Нет') + '</td>' +
            '<td>' + (p.indexable ? 'Да' : 'Нет') + '</td>' +
          '</tr>';
        }).join('') + '</tbody></table></div>'
      : '<div class="rf-empty">Запустите SEO-аудит для инспекции HTML-страниц сайта.</div>';

    var issuesHtml = issues.length
      ? '<div class="growth-item-list">' + issues.map(function (it, idx) {
          return '<div class="growth-item-row">' +
            '<div class="growth-item-main">' +
              '<div class="growth-item-top">' +
                '<b><code>' + esc(it.pageUrl) + '</code> · ' + esc(it.issueType) + '</b>' +
                renderBadge(ui, SEV_BADGE[it.severity] || 'info', SEV_LABELS[it.severity] || it.severity) +
              '</div>' +
              '<div class="growth-attention-desc">' + esc(it.description) + '</div>' +
              '<div class="growth-note"><b>Рекомендация:</b> ' + esc(it.recommendation) + '</div>' +
              '<div class="growth-inline-actions" style="margin-top:8px">' +
                '<button type="button" class="rf-btn rf-btn-alt" data-seo-to-task="' + esc(idx) + '">+ Задача из проблемы</button>' +
                '<button type="button" class="rf-btn rf-btn-alt" data-seo-to-prop="' + esc(idx) + '">+ Предложение изменения</button>' +
              '</div>' +
            '</div>' +
          '</div>';
        }).join('') + '</div>'
      : (d.hasRun ? '<div class="rf-empty">Проблемы по выбранному уровню серьёзности отсутствуют.</div>' : '<div class="rf-empty">Аудит ещё не запускался.</div>');

    return '<div class="growth-stack">' +
      '<div class="rf-card growth-toolbar">' +
        '<div>' +
          '<h3 class="growth-block-title">Детерминированный SEO-аудит (без LLM)</h3>' +
          '<div class="growth-block-def">Проверка фактических HTML-страниц, robots.txt и sitemap.xml. Дата последней проверки: <b>' + esc(d.checkedAtIso || 'не проводилась') + '</b></div>' +
        '</div>' +
        '<div class="growth-toolbar-right">' +
          '<button type="button" class="rf-btn rf-btn-primary" id="growth-run-seo-btn">▶ Запустить SEO-аудит</button>' +
        '</div>' +
      '</div>' +
      '<div class="rf-card">' +
        summaryHtml +
        pagesHtml +
        renderMeta(ui, d.source || 'site/*.html + robots.txt + sitemap.xml', d.checkedAtIso || '—') +
      '</div>' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Найденные проблемы (' + esc(issues.length) + ')</h3></div>' +
          '<label class="growth-filter-field"><span>Серьёзность</span><select id="growth-seo-sev-flt"><option value="">Все</option>' +
            sevs.map(function (s) { return '<option value="' + s + '"' + (sevFilter === s ? ' selected' : '') + '>' + SEV_LABELS[s] + '</option>'; }).join('') +
          '</select></label>' +
        '</div>' +
        issuesHtml +
      '</div>' +
      '<div class="rf-card">' +
        '<div class="growth-block-head"><div><h3 class="growth-block-title">Проверки со статусом unknown (не оцениваются без источника)</h3></div>' + renderBadge(ui, 'draft', 'unknown') + '</div>' +
        '<div class="growth-ext-list">' +
          unknowns.map(function (u) {
            return '<div class="growth-ext-row"><div class="growth-ext-main"><div class="growth-ext-title">' + esc(u.check) + '</div><div class="growth-ext-reason">' + esc(u.reason) + '</div></div><div>' + renderBadge(ui, 'draft', u.status || 'unknown') + '</div></div>';
          }).join('') +
        '</div>' +
      '</div>' +
    '</div>';
  }

  function renderDiffViewerBox(diff, ui) {
    if (!diff) return '<div class="rf-empty">Выберите предложение для сравнения изменений.</div>';
    var st = diff.stats || {};
    var lines = Array.isArray(diff.sideBySideLines) ? diff.sideBySideLines : [];
    var rowsHtml = lines.map(function (ln) {
      var cls = ln.type === 'insert' ? 'rf-diff-add' : (ln.type === 'delete' ? 'rf-diff-del' : (ln.type === 'replace' ? 'is-replace' : ''));
      return '<tr class="' + cls + '">' +
        '<td class="growth-diff-ln">' + esc(ln.oldLineNum || '') + '</td>' +
        '<td class="growth-diff-cell rf-diff-del">' + esc(ln.oldText) + '</td>' +
        '<td class="growth-diff-ln">' + esc(ln.newLineNum || '') + '</td>' +
        '<td class="growth-diff-cell rf-diff-add">' + esc(ln.newText) + '</td>' +
      '</tr>';
    }).join('');

    return '<div class="growth-diff-box">' +
      '<div class="growth-status-bar">' +
        '<div class="growth-status-pill"><span>Объект:</span> <b>' + esc(diff.targetObject || '—') + '</b></div>' +
        '<div class="growth-status-pill"><span>Поле:</span> <b>' + esc(diff.fieldName || 'content') + '</b></div>' +
        '<div class="growth-status-pill"><span>+ строк:</span> <b>' + esc(st.addedCount || 0) + '</b></div>' +
        '<div class="growth-status-pill"><span>- строк:</span> <b>' + esc(st.removedCount || 0) + '</b></div>' +
        '<div class="growth-status-pill"><span>Длина:</span> <b>' + esc(st.originalLength || 0) + ' → ' + esc(st.proposedLength || 0) + '</b></div>' +
      '</div>' +
      (diff.seoFieldGuidance ? '<div class="growth-note" style="margin-bottom:8px"><b>Ориентир SEO:</b> ' + esc(diff.seoFieldGuidance.label) + '</div>' : '') +
      '<div class="rf-table-wrap"><table class="growth-table growth-diff-table"><thead><tr><th>#</th><th>Текущее значение</th><th>#</th><th>Предлагаемое значение</th></tr></thead><tbody>' +
      (rowsHtml || '<tr><td colspan="4" class="rf-empty">Строки совпадают</td></tr>') +
      '</tbody></table></div>' +
      (diff.unifiedDiff ? '<pre class="rf-card-inset rf-diff growth-diff-pre">' + esc(diff.unifiedDiff) + '</pre>' : '') +
    '</div>';
  }

  function renderProposalsHtml(propsData, detailData, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var f = (opts && opts.filters) || {};
    var data = propsData || {};
    var props = Array.isArray(data.proposals) ? data.proposals : [];
    var detail = detailData && detailData.proposal ? detailData : null;
    var fields = ['title', 'meta_description', 'h1', 'canonical', 'robots_meta', 'og_title', 'og_description', 'alt', 'sitemap_xml', 'robots_txt', 'content', 'other'];
    var sts = ['pending', 'approved', 'rejected', 'applied', 'cancelled'];

    var listHtml = props.length
      ? '<div class="growth-item-list">' + props.map(function (p) {
          var isSel = detail && detail.proposal.id === p.id;
          return '<div class="growth-item-row' + (isSel ? ' is-selected' : '') + '">' +
            '<div class="growth-item-main">' +
              '<div class="growth-item-top">' +
                '<button type="button" class="growth-link-btn" data-prop-select="' + esc(p.id) + '">#' + esc(p.id) + ' · ' + esc(p.targetObject) + ' [' + esc(p.fieldName) + ']</button>' +
                renderBadge(ui, PROP_STATUS_BADGE[p.status] || 'draft', PROP_STATUS_LABELS[p.status] || p.status) +
              '</div>' +
              '<div class="growth-item-meta">' + esc(p.reason) +
                (p.taskId ? (' · Задача #' + esc(p.taskId)) : '') +
                ' · Создано: ' + esc(p.createdAtIso || '—') +
              '</div>' +
            '</div>' +
          '</div>';
        }).join('') + '</div>'
      : '<div class="rf-empty">Предложений пока нет. Создайте предложение на основе SEO-аудита или вручную.</div>';

    var detailHtml = '';
    if (detail) {
      var pr = detail.proposal;
      var hist = Array.isArray(detail.history) ? detail.history : [];
      detailHtml = '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div>' +
            '<h3 class="growth-block-title">Предложение #' + esc(pr.id) + ': ' + esc(pr.targetObject) + ' (' + esc(pr.fieldName) + ')</h3>' +
            '<div class="growth-block-def">' + esc(pr.reason) + '</div>' +
          '</div>' +
          renderBadge(ui, PROP_STATUS_BADGE[pr.status] || 'draft', PROP_STATUS_LABELS[pr.status] || pr.status) +
        '</div>' +
        '<div class="growth-note" style="margin-bottom:10px"><b>Политика безопасности:</b> одобрение предложения фиксирует решение администратора в БД и журнале аудита, но <u>не</u> изменяет файлы production-сайта автоматически.</div>' +
        renderDiffViewerBox(detail.diff, ui) +
        '<div class="growth-inline-actions" style="margin-top:12px">' +
          '<button type="button" class="rf-btn rf-btn-alt" data-diff-open="' + esc(pr.id) + '">Открыть в Diff Review</button>' +
          (pr.status === 'pending'
            ? '<button type="button" class="rf-btn rf-btn-green" data-prop-approve="' + esc(pr.id) + '">✓ Одобрить</button>' +
              '<button type="button" class="rf-btn rf-btn-danger" data-prop-reject="' + esc(pr.id) + '">✕ Отклонить</button>'
            : '') +
        '</div>' +
        '<h4 style="margin:12px 0 6px;font-size:13px">История согласования</h4>' +
        (hist.length
          ? '<div class="growth-history-list">' + hist.map(function (h) {
              return '<div class="growth-history-row"><b>' + esc(h.action) + '</b>: <code>' + esc(h.oldStatus || '—') + '</code> → <code>' + esc(h.newStatus || '—') + '</code>' +
                (h.note ? (' · ' + esc(h.note)) : '') + ' <span class="rf-source-meta">' + esc(h.actor) + ' · ' + esc(h.createdAtIso) + '</span></div>';
            }).join('') + '</div>'
          : '<div class="rf-empty">История пуста</div>') +
      '</div>';
    }

    return '<div class="growth-stack">' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Создать предложение изменения (Approval Engine)</h3><div class="growth-block-def">Изменения сохраняются как <code>pending</code> и не применяются к файлам сайта автоматически.</div></div>' +
        '</div>' +
        '<div class="growth-form-grid">' +
          '<label class="growth-filter-field"><span>Объект изменения *</span><input id="growth-new-prop-target" class="growth-input" type="text" placeholder="site/index.html или site/fitify/index.html" value="' + esc((opts && opts.draftTarget) || '') + '"></label>' +
          '<label class="growth-filter-field"><span>Поле</span><select id="growth-new-prop-field">' +
            fields.map(function (fn) { return '<option value="' + fn + '"' + ((opts && opts.draftField) === fn ? ' selected' : '') + '>' + fn + '</option>'; }).join('') +
          '</select></label>' +
          '<label class="growth-filter-field"><span>ID задачи (опц.)</span><input id="growth-new-prop-task" class="growth-input" type="number" min="1" placeholder="1"></label>' +
          '<label class="growth-filter-field" style="grid-column:1 / -1"><span>Причина / обоснование *</span><input id="growth-new-prop-reason" class="growth-input" type="text" placeholder="Почему нужно это изменение"></label>' +
          '<label class="growth-filter-field"><span>Текущее значение</span><textarea id="growth-new-prop-curr" class="growth-textarea" rows="3">' + esc((opts && opts.draftCurr) || '') + '</textarea></label>' +
          '<label class="growth-filter-field"><span>Предлагаемое значение *</span><textarea id="growth-new-prop-next" class="growth-textarea" rows="3" placeholder="Новый текст или разметка"></textarea></label>' +
        '</div>' +
        '<div class="growth-inline-actions" style="margin-top:10px"><button type="button" class="rf-btn rf-btn-primary" id="growth-create-prop-btn">+ Отправить на согласование</button></div>' +
      '</div>' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Очередь предложений (' + esc(data.total || props.length) + ')</h3></div>' +
          '<div class="growth-toolbar-right">' +
            '<select id="growth-prop-flt-st" class="growth-input"><option value="">Все статусы</option>' +
              sts.map(function (s) { return '<option value="' + s + '"' + (f.status === s ? ' selected' : '') + '>' + esc(PROP_STATUS_LABELS[s] || s) + '</option>'; }).join('') +
            '</select>' +
            '<button type="button" class="rf-btn rf-btn-alt" data-growth-refresh="proposals">↻ Обновить</button>' +
          '</div>' +
        '</div>' +
        listHtml +
        renderMeta(ui, data.source || 'flexa.db:growth_proposals', data.updatedAt || '—') +
      '</div>' +
      detailHtml +
    '</div>';
  }

  function renderDiffHtml(proposalsData, diffPayload, opts) {
    var ui = (opts && opts.ui) || DefaultUI;
    var props = Array.isArray((proposalsData || {}).proposals) ? proposalsData.proposals : [];
    var selId = diffPayload ? Number(diffPayload.proposalId) : null;
    var diff = diffPayload && diffPayload.diff ? diffPayload.diff : null;
    var st = diffPayload ? diffPayload.status : '';

    return '<div class="growth-stack">' +
      '<div class="rf-card">' +
        '<div class="growth-block-head">' +
          '<div><h3 class="growth-block-title">Diff Review — безопасное сравнение версий</h3><div class="growth-block-def">Изолированный текстовый diff без выполнения кода, SQL или shell-команд.</div></div>' +
          (st ? renderBadge(ui, PROP_STATUS_BADGE[st] || 'draft', PROP_STATUS_LABELS[st] || st) : '') +
        '</div>' +
        '<div class="growth-audit-filters">' +
          '<label class="growth-filter-field" style="flex:1 1 260px"><span>Предложение</span><select id="growth-diff-prop-sel">' +
            (props.length
              ? props.map(function (p) {
                  return '<option value="' + esc(p.id) + '"' + (selId === p.id ? ' selected' : '') + '>#' + esc(p.id) + ' · ' + esc(p.targetObject) + ' [' + esc(p.fieldName) + '] (' + esc(p.status) + ')</option>';
                }).join('')
              : '<option value="">Нет доступных предложений</option>') +
          '</select></label>' +
          '<button type="button" class="rf-btn rf-btn-alt" data-growth-refresh="diff">↻ Обновить Diff</button>' +
        '</div>' +
      '</div>' +
      '<div class="rf-card">' +
        renderDiffViewerBox(diff, ui) +
        (selId && st === 'pending'
          ? '<div class="growth-inline-actions" style="margin-top:12px">' +
              '<button type="button" class="rf-btn rf-btn-green" data-prop-approve="' + esc(selId) + '">✓ Одобрить предложение #' + esc(selId) + '</button>' +
              '<button type="button" class="rf-btn rf-btn-danger" data-prop-reject="' + esc(selId) + '">✕ Отклонить #' + esc(selId) + '</button>' +
            '</div>'
          : '') +
      '</div>' +
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
    var toast = typeof d.toast === 'function' ? d.toast : function () {};
    var ui = d.ui || DefaultUI;
    var state = {
      subTab: d.initialSubTab || 'dashboard',
      days: 30,
      auditLimit: 25,
      auditOffset: 0,
      auditModule: '',
      auditStatus: '',
      taskStatus: '',
      taskCategory: '',
      taskPriority: '',
      selectedTaskId: null,
      taskDetail: null,
      seoSeverity: '',
      seoAudit: null,
      propStatus: '',
      selectedPropId: null,
      propDetail: null,
      diffPropId: null,
      diffPayload: null,
      draftProp: null,
      loading: false,
      error: '',
      overview: null,
      analytics: null,
      tasks: null,
      proposals: null,
      audit: null
    };

    function confirmAction(title, msg, fn, label) {
      if (ui && typeof ui.openConfirmModal === 'function') {
        ui.openConfirmModal({
          title: title,
          bodyHtml: '<p style="margin:0;color:var(--tx-sub);font-size:13.5px;line-height:1.5">' + esc(msg) + '</p>',
          confirmLabel: label || 'Подтвердить',
          cancelLabel: 'Отмена',
          danger: false,
          onConfirm: async function (close) {
            close();
            await fn();
          }
        });
      } else {
        fn();
      }
    }

    function renderFrame(bodyHtml) {
      var navTabs = [
        { id: 'dashboard', label: '📊 Dashboard' },
        { id: 'analytics', label: '📈 Analytics' },
        { id: 'tasks', label: '✅ Задачи' },
        { id: 'seo', label: '🔎 SEO-аудит' },
        { id: 'proposals', label: '📝 Предложения' },
        { id: 'diff', label: '⚖️ Diff Review' },
        { id: 'audit', label: '🛡️ Audit Log' }
      ];
      el.innerHTML =
        '<div class="rf-card growth-shell-header">' +
          '<div class="growth-hub-banner">' +
            '<div>' +
              '<h2 style="margin:0;font-size:18px">RizzaFit AI Growth</h2>' +
              '<p style="margin:4px 0 0;color:var(--mut);font-size:13px">PR 4.2: Task Manager, детерминированный SEO-аудит, Approval Engine и Diff Review (без автоприменения в production).</p>' +
            '</div>' +
            renderBadge(ui, 'done', 'PR 4.2') +
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

      // Tasks handlers
      var createTaskBtn = el.querySelector('#growth-create-task-btn');
      if (createTaskBtn) {
        createTaskBtn.onclick = async function () {
          try {
            var res = await api('admin/growth/tasks', {
              method: 'POST',
              body: JSON.stringify({
                title: (el.querySelector('#growth-new-task-title') || {}).value || '',
                category: (el.querySelector('#growth-new-task-cat') || {}).value || 'SEO',
                priority: (el.querySelector('#growth-new-task-prio') || {}).value || 'medium',
                targetUrl: (el.querySelector('#growth-new-task-url') || {}).value || '',
                description: (el.querySelector('#growth-new-task-desc') || {}).value || ''
              })
            });
            state.selectedTaskId = res.task && res.task.id;
            toast('Задача создана ✓');
            loadCurrent(true);
          } catch (e) { toast(e.message, 1); }
        };
      }
      var fltTSt = el.querySelector('#growth-task-flt-st');
      var fltTCat = el.querySelector('#growth-task-flt-cat');
      var fltTPrio = el.querySelector('#growth-task-flt-prio');
      if (fltTSt) fltTSt.onchange = function () { state.taskStatus = fltTSt.value || ''; loadCurrent(true); };
      if (fltTCat) fltTCat.onchange = function () { state.taskCategory = fltTCat.value || ''; loadCurrent(true); };
      if (fltTPrio) fltTPrio.onchange = function () { state.taskPriority = fltTPrio.value || ''; loadCurrent(true); };

      el.querySelectorAll('[data-task-select]').forEach(function (btn) {
        btn.onclick = function () {
          state.selectedTaskId = Number(btn.getAttribute('data-task-select'));
          loadCurrent(true);
        };
      });
      el.querySelectorAll('[data-task-status]').forEach(function (btn) {
        btn.onclick = async function () {
          var parts = (btn.getAttribute('data-task-status') || '').split(':');
          try {
            var noteEl = el.querySelector('#growth-task-edit-note');
            await api('admin/growth/tasks/' + parts[0], {
              method: 'PATCH',
              body: JSON.stringify({ status: parts[1], note: noteEl ? noteEl.value : '' })
            });
            toast('Статус задачи обновлён ✓');
            loadCurrent(true);
          } catch (e) { toast(e.message, 1); }
        };
      });
      el.querySelectorAll('[data-task-save-prio]').forEach(function (btn) {
        btn.onclick = async function () {
          var tid = btn.getAttribute('data-task-save-prio');
          var pSel = el.querySelector('#growth-task-edit-prio');
          var noteEl = el.querySelector('#growth-task-edit-note');
          try {
            await api('admin/growth/tasks/' + tid, {
              method: 'PATCH',
              body: JSON.stringify({ priority: pSel ? pSel.value : 'medium', note: noteEl ? noteEl.value : '' })
            });
            toast('Приоритет обновлён ✓');
            loadCurrent(true);
          } catch (e) { toast(e.message, 1); }
        };
      });

      // SEO Audit handlers
      var runSeoBtn = el.querySelector('#growth-run-seo-btn');
      if (runSeoBtn) {
        runSeoBtn.onclick = async function () {
          try {
            runSeoBtn.disabled = true;
            state.seoAudit = await api('admin/growth/seo-audit/run', { method: 'POST', body: '{}' });
            toast('SEO-аудит завершён ✓');
            loadCurrent(true);
          } catch (e) { toast(e.message, 1); }
        };
      }
      var seoSevFlt = el.querySelector('#growth-seo-sev-flt');
      if (seoSevFlt) {
        seoSevFlt.onchange = function () { state.seoSeverity = seoSevFlt.value || ''; loadCurrent(true); };
      }
      el.querySelectorAll('[data-seo-to-task]').forEach(function (btn) {
        btn.onclick = async function () {
          var idx = Number(btn.getAttribute('data-seo-to-task'));
          var iss = state.seoAudit && state.seoAudit.issues && state.seoAudit.issues[idx];
          if (!iss) return;
          try {
            var res = await api('admin/growth/tasks', {
              method: 'POST',
              body: JSON.stringify({
                title: ('SEO [' + iss.severity + ']: ' + iss.issueType + ' (' + iss.pageUrl + ')').slice(0, 150),
                description: iss.description + '\nРекомендация: ' + iss.recommendation,
                category: 'SEO',
                priority: iss.severity === 'info' ? 'low' : iss.severity,
                seoAuditRunId: state.seoAudit.runId,
                seoIssueId: iss.id,
                targetUrl: iss.pageUrl
              })
            });
            state.selectedTaskId = res.task && res.task.id;
            state.subTab = 'tasks';
            toast('Задача создана из SEO-аудита ✓');
            loadCurrent(true);
          } catch (e) { toast(e.message, 1); }
        };
      });
      el.querySelectorAll('[data-seo-to-prop]').forEach(function (btn) {
        btn.onclick = function () {
          var idx = Number(btn.getAttribute('data-seo-to-prop'));
          var iss = state.seoAudit && state.seoAudit.issues && state.seoAudit.issues[idx];
          if (!iss) return;
          var rawUrl = String(iss.pageUrl || '/').split(',')[0].trim();
          var targetObj = 'site/index.html';
          if (rawUrl === '/' || rawUrl === '') targetObj = 'site/index.html';
          else if (rawUrl.endsWith('/')) targetObj = 'site/' + rawUrl.replace(/^\/+/, '') + 'index.html';
          else targetObj = 'site/' + rawUrl.replace(/^\/+/, '');
          state.draftProp = {
            draftTarget: targetObj,
            draftField: iss.fieldName || 'content',
            draftCurr: iss.currentValue || ''
          };
          state.subTab = 'proposals';
          loadCurrent(true);
        };
      });

      // Proposals handlers
      var createPropBtn = el.querySelector('#growth-create-prop-btn');
      if (createPropBtn) {
        createPropBtn.onclick = async function () {
          var tidVal = (el.querySelector('#growth-new-prop-task') || {}).value;
          try {
            var res = await api('admin/growth/proposals', {
              method: 'POST',
              body: JSON.stringify({
                targetObject: (el.querySelector('#growth-new-prop-target') || {}).value || '',
                fieldName: (el.querySelector('#growth-new-prop-field') || {}).value || 'content',
                taskId: tidVal ? Number(tidVal) : null,
                reason: (el.querySelector('#growth-new-prop-reason') || {}).value || '',
                currentValue: (el.querySelector('#growth-new-prop-curr') || {}).value || '',
                proposedValue: (el.querySelector('#growth-new-prop-next') || {}).value || ''
              })
            });
            state.draftProp = null;
            state.selectedPropId = res.proposal && res.proposal.id;
            toast('Предложение создано ✓');
            loadCurrent(true);
          } catch (e) { toast(e.message, 1); }
        };
      }
      var propFlt = el.querySelector('#growth-prop-flt-st');
      if (propFlt) propFlt.onchange = function () { state.propStatus = propFlt.value || ''; loadCurrent(true); };
      el.querySelectorAll('[data-prop-select]').forEach(function (btn) {
        btn.onclick = function () { state.selectedPropId = Number(btn.getAttribute('data-prop-select')); loadCurrent(true); };
      });
      el.querySelectorAll('[data-prop-jump]').forEach(function (btn) {
        btn.onclick = function () {
          state.selectedPropId = Number(btn.getAttribute('data-prop-jump'));
          state.subTab = 'proposals';
          loadCurrent(true);
        };
      });
      el.querySelectorAll('[data-diff-open]').forEach(function (btn) {
        btn.onclick = function () {
          state.diffPropId = Number(btn.getAttribute('data-diff-open'));
          state.subTab = 'diff';
          loadCurrent(true);
        };
      });
      el.querySelectorAll('[data-prop-approve]').forEach(function (btn) {
        btn.onclick = function () {
          var pid = btn.getAttribute('data-prop-approve');
          confirmAction(
            'Одобрить предложение #' + pid + '?',
            'Статус изменится на approved, запись попадёт в Audit Log. Production-файлы сайта НЕ будут изменены автоматически.',
            async function () {
              try {
                await api('admin/growth/proposals/' + pid + '/approve', { method: 'POST', body: JSON.stringify({ note: 'Одобрено в админ-панели' }) });
                toast('Предложение одобрено ✓');
                loadCurrent(true);
              } catch (e) { toast(e.message, 1); }
            },
            'Одобрить'
          );
        };
      });
      el.querySelectorAll('[data-prop-reject]').forEach(function (btn) {
        btn.onclick = function () {
          var pid = btn.getAttribute('data-prop-reject');
          confirmAction(
            'Отклонить предложение #' + pid + '?',
            'Предложение будет переведено в статус rejected и зафиксировано в Audit Log.',
            async function () {
              try {
                await api('admin/growth/proposals/' + pid + '/reject', { method: 'POST', body: JSON.stringify({ note: 'Отклонено администратором' }) });
                toast('Предложение отклонено');
                loadCurrent(true);
              } catch (e) { toast(e.message, 1); }
            },
            'Отклонить'
          );
        };
      });

      var diffSel = el.querySelector('#growth-diff-prop-sel');
      if (diffSel) {
        diffSel.onchange = function () {
          state.diffPropId = diffSel.value ? Number(diffSel.value) : null;
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
        } else if (state.subTab === 'tasks') {
          var tq = 'admin/growth/tasks?limit=50&offset=0';
          if (state.taskStatus) tq += '&status=' + encodeURIComponent(state.taskStatus);
          if (state.taskCategory) tq += '&category=' + encodeURIComponent(state.taskCategory);
          if (state.taskPriority) tq += '&priority=' + encodeURIComponent(state.taskPriority);
          state.tasks = await api(tq);
          state.taskDetail = state.selectedTaskId ? await api('admin/growth/tasks/' + state.selectedTaskId).catch(function () { return null; }) : null;
          renderFrame(renderTasksHtml(state.tasks, state.taskDetail, { ui: ui, filters: { status: state.taskStatus, category: state.taskCategory, priority: state.taskPriority } }));
        } else if (state.subTab === 'seo') {
          var sq = 'admin/growth/seo-audit';
          if (state.seoSeverity) sq += '?severity=' + encodeURIComponent(state.seoSeverity);
          state.seoAudit = await api(sq);
          renderFrame(renderSeoAuditHtml(state.seoAudit, { ui: ui, severity: state.seoSeverity }));
        } else if (state.subTab === 'proposals') {
          var pq = 'admin/growth/proposals?limit=50&offset=0';
          if (state.propStatus) pq += '&status=' + encodeURIComponent(state.propStatus);
          state.proposals = await api(pq);
          state.propDetail = state.selectedPropId ? await api('admin/growth/proposals/' + state.selectedPropId).catch(function () { return null; }) : null;
          renderFrame(renderProposalsHtml(state.proposals, state.propDetail, Object.assign({ ui: ui, filters: { status: state.propStatus } }, state.draftProp || {})));
        } else if (state.subTab === 'diff') {
          state.proposals = await api('admin/growth/proposals?limit=50&offset=0');
          var plist = (state.proposals && state.proposals.proposals) || [];
          if (!state.diffPropId && plist.length) state.diffPropId = plist[0].id;
          state.diffPayload = state.diffPropId ? await api('admin/growth/proposals/' + state.diffPropId + '/diff').catch(function () { return null; }) : null;
          renderFrame(renderDiffHtml(state.proposals, state.diffPayload, { ui: ui }));
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
    renderTasksHtml: renderTasksHtml,
    renderSeoAuditHtml: renderSeoAuditHtml,
    renderProposalsHtml: renderProposalsHtml,
    renderDiffHtml: renderDiffHtml,
    renderAuditHtml: renderAuditHtml,
    _renderBarSeries: renderBarSeries
  };
});
