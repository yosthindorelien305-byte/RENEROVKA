(async function () {
  const root = document.getElementById('root');
  const T = window.TEXTS || { ru: {}, en: {} };
  let token = sessionStorage.atok || '';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const $ = (s, e = document) => e.querySelector(s);
  const $$ = (s, e = document) => [...e.querySelectorAll(s)];

  function toast(m, err) {
    const d = document.createElement('div');
    d.className = 'msg' + (err ? ' err' : '');
    d.textContent = m;
    document.body.appendChild(d);
    setTimeout(() => d.remove(), 2600);
  }

  function confirmDangerous(title, message, onConfirm, confirmLabel) {
    const ui = window.RizzaUI;
    if (ui && typeof ui.openConfirmModal === 'function') {
      ui.openConfirmModal({
        title: title || 'Подтвердите действие',
        bodyHtml: `<p style="margin:0;color:var(--tx-sub);line-height:1.5;font-size:13.5px">${esc(message)}</p>`,
        confirmLabel: confirmLabel || 'Подтвердить',
        cancelLabel: 'Отмена',
        danger: true,
        onConfirm: async close => {
          close();
          await onConfirm();
        }
      });
      return;
    }
    if (confirm(message)) onConfirm();
  }

  async function api(path, opt = {}) {
    const r = await fetch('/api/' + path, Object.assign({}, opt, {
      headers: Object.assign({}, opt.headers || {}, token ? { Authorization: 'Bearer ' + token } : {})
    }));
    let j = {};
    try { j = await r.json(); } catch (e) { }
    if (r.status == 401 && path != 'login') {
      token = '';
      sessionStorage.removeItem('atok');
      showLogin();
      throw new Error('Сессия истекла, войдите заново');
    }
    if (!r.ok) throw new Error(j.error || ('Ошибка ' + r.status));
    return j;
  }

  const nc = u => fetch(u + '?v=' + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null);
  const post = (p, o) => api(p, { method: 'POST', body: JSON.stringify(o) });

  async function upload(name, file) {
    if (!file) return null;
    const j = await api('upload?name=' + encodeURIComponent(name), {
      method: 'POST',
      headers: { 'X-Filename': file.name },
      body: file
    });
    return j.path;
  }

  let D, CFG, OV;
  const ATH_DEF = () => Object.assign({}, window.AthleteProfile ? window.AthleteProfile.DEFAULTS : {
    name: 'Mr.Bobrovsky',
    handle: '@mr.bobrovsky',
    avatar: '',
    points: 20710,
    winRate: 70,
    level: 8,
    days: 76,
    streakDays: 35,
    friendsOnline: 0,
    friendsLabelRu: 'Друзья',
    friendsLabelEn: 'Friends',
    streakTitleRu: 'Так держать!',
    streakTitleEn: 'Keep it up!',
    streakSubRu: '{n} дней подряд вы здесь!',
    streakSubEn: '{n} days in a row you are here!',
    taskTitleRu: 'Выполняй задания',
    taskTitleEn: 'Complete new tasks',
    taskSubRu: 'Получай бонусные очки за тренировки и личные рекорды',
    taskSubEn: 'Get a bonus on your progress with workouts in your plan',
    useLiveStats: true
  });
  const DEF = {
    brand: 'Flexa',
    accent: '#e2a749',
    logo: '',
    heroProgram: 2,
    goal: 5,
    hidden: [],
    sections: {},
    t: { ru: {}, en: {} },
    heroTitle: {},
    heroText: {},
    heroLink: '',
    heroImage: '',
    athlete: ATH_DEF()
  };

  async function loadAll() {
    D = await fetch('data.json').then(r => r.json());
    const c = await nc('content/config.json'), o = await nc('content/overrides.json');
    CFG = Object.assign(JSON.parse(JSON.stringify(DEF)), c || {});
    CFG.t = Object.assign({ ru: {}, en: {} }, CFG.t);
    CFG.athlete = Object.assign(ATH_DEF(), CFG.athlete || {});
    OV = Object.assign({ w: {}, p: {}, c: [], e: {} }, o || {});
    OV.e = OV.e || {};
  }

  const saveCfg = () => post('save?file=config', CFG);
  const saveOv = () => post('save?file=overrides', OV);

  const exMap = {};
  const exName = e => e.n.ru || e.n.en || '#' + e.id;
  const effP = id => Object.assign({}, D.programs.find(p => p.id == id), OV.p[id] || {});
  const effW = id => OV.c.find(w => w.id == id) || Object.assign({}, D.workouts.find(w => w.id == id), OV.w[id] || {});
  const effE = id => Object.assign({}, D.exercises.find(e => e.id == id), (OV.e || {})[id] || {});
  const pImg = p => p.image || (D.programs.find(x => x.id == p.id) && D.programs.find(x => x.id == p.id).img ? `img/programs/${p.id}.jpg` : '');

  // ---------- login ----------
  function showLogin() {
    root.innerHTML = `<div class="login"><img src="img/logo.svg"><h1>Админка</h1><p style="color:var(--mut)">Введите пароль. При первом запуске он лежит в файле <b>ADMIN_PASSWORD.txt</b> рядом с server.py</p>
    <form id="lf"><input id="pw" type="password" placeholder="Пароль" autofocus><p><button class="btn block" style="animation:none">Войти</button></p></form><a href="/">← на сайт</a></div>`;
    $('#lf').onsubmit = async e => {
      e.preventDefault();
      try {
        const j = await post('login', { password: $('#pw').value });
        token = j.token;
        sessionStorage.atok = token;
        start();
      } catch (er) {
        toast(er.message, 1);
      }
    };
  }

  // ---------- shell ----------
  let tab = 'athlete', sub = null;
  async function start() {
    try { await api('uploads'); } catch (e) { return showLogin(); }
    await loadAll();
    D.exercises.forEach(e => exMap[e.id] = e);
    shell();
  }

  function shell() {
    const siteNav = [
      ['athlete', '👤 Профиль спортсмена'],
      ['ui', '🎨 Интерфейс'],
      ['programs', '📋 Программы'],
      ['workouts', '🏋️ Тренировки'],
      ['exercises', '🤸 Упражнения & Видео'],
      ['users', '👥 Пользователи'],
      ['reports', '🚩 Жалобы'],
      ['telegram', '✈️ Telegram бот'],
      ['payments', '💳 ЮKassa & СБП'],
      ['ai', '🤖 AI-тренер'],
      ['settings', '⚙️ Настройки']
    ];
    root.innerHTML = `<header class="ah">
      <button type="button" class="btn alt adm-menu-btn" id="adm-menu-btn" aria-label="Меню">☰</button>
      <img src="img/logo.svg" width="30" style="border-radius:8px">
      <b>Админка · ${esc(CFG.brand)}</b>
      <div class="ah-actions">
        <a class="btn alt" href="/#/profile" target="_blank">Профиль</a>
        <a class="btn alt" href="/" target="_blank">Открыть сайт</a>
        <button class="btn alt" id="lo">Выйти</button>
      </div>
    </header>
    <div class="adm-shell" id="adm-shell">
      <div class="adm-drawer-backdrop" id="adm-drawer-bg"></div>
      <aside class="adm-sidebar" id="adm-sidebar">
        <div class="adm-nav-group">
          <div class="adm-nav-title">Управление сайтом</div>
          <div class="tabs adm-nav-list">${siteNav.map(([k, n]) => `<button data-t="${k}" class="${tab == k ? 'on' : ''}">${n}</button>`).join('')}</div>
        </div>
        <div class="adm-nav-group adm-nav-growth">
          <div class="adm-nav-title">Развитие платформы</div>
          <div class="tabs adm-nav-list"><button data-t="growth" class="is-growth ${tab == 'growth' ? 'on' : ''}">📈 AI Growth</button></div>
        </div>
      </aside>
      <main class="wrap adm-main"><div id="tabc"></div></main>
    </div>`;

    $('#lo').onclick = () => {
      if (token) fetch('/api/admin/logout', { method: 'POST', headers: { Authorization: 'Bearer ' + token } }).catch(() => {});
      token = ''; sessionStorage.removeItem('atok'); showLogin();
    };
    const admShell = $('#adm-shell');
    const menuBtn = $('#adm-menu-btn');
    const drawerBg = $('#adm-drawer-bg');
    if (menuBtn && admShell) menuBtn.onclick = () => admShell.classList.toggle('drawer-open');
    if (drawerBg && admShell) drawerBg.onclick = () => admShell.classList.remove('drawer-open');

    $$('.tabs button').forEach(b => b.onclick = () => {
      tab = b.dataset.t;
      sub = null;
      if (admShell) admShell.classList.remove('drawer-open');
      shell();
    });

    const tabs = { athlete: tabAthlete, ui: tabUI, programs: tabPrograms, workouts: tabWorkouts, exercises: tabExercises, users: tabUsers, reports: tabReports, telegram: tabTelegram, payments: tabPayments, ai: tabAI, growth: tabGrowth, settings: tabSettings };
    if (tabs[tab]) tabs[tab]($('#tabc'));
  }

  function tabGrowth(el) {
    if (window.RizzaGrowth && typeof window.RizzaGrowth.render === 'function') {
      return window.RizzaGrowth.render(el, {
        api,
        toast,
        esc,
        ui: window.RizzaUI
      });
    }
    const ui = window.RizzaUI;
    el.innerHTML = `<div class="rf-card">
      <h2 style="margin:0;font-size:18px">RizzaFit AI Growth</h2>
      <p style="margin:6px 0 0;color:var(--mut);font-size:13px">Изолированный от AI Coach контур развития. Не удалось загрузить модуль admin_growth.js.</p>
      ${ui && typeof ui.renderAuditLogList === 'function' ? ui.renderAuditLogList([], { title: 'Журнал действий AI Growth' }) : ''}
    </div>`;
  }

  const imgPicker = (id, src, cls) => `<div class="up"><img ${cls ? `class="${cls}"` : ''} id="${id}-prev" src="${esc(src || 'img/logo.svg')}" onerror="this.style.opacity=.2"><div><input type="file" id="${id}" accept="image/*"><br><button class="btn alt" style="padding:8px 14px;margin-top:6px" id="${id}-clr" type="button">Убрать / вернуть оригинал</button></div></div>`;

  // ---------- tab: athlete profile ----------
  function tabAthlete(el) {
    CFG.athlete = Object.assign(ATH_DEF(), CFG.athlete || {});
    let draft = JSON.parse(JSON.stringify(CFG.athlete));
    if (!Array.isArray(draft.friends)) {
      draft.friends = [];
    } else {
      draft.friends = draft.friends.filter(f => {
        if (window.AthleteProfile && window.AthleteProfile.isFakeUser) return !window.AthleteProfile.isFakeUser(f);
        return !['f1', 'f2', 'f3', 'f4', 's1', 's2', 's3'].includes(f.id);
      });
    }

    const renderPreview = () => {
      const slot = $('#ath-preview-slot');
      if (slot && window.AthleteProfile) {
        slot.innerHTML = window.AthleteProfile.renderCard(draft, { lang: 'ru', preview: true, friends: draft.friends });
      }
    };

    const renderFriendsEditor = () => {
      const box = $('#ath-friends-list');
      if (!box) return;
      box.innerHTML = draft.friends.map((f, idx) => `
        <div style="display:grid;grid-template-columns:1.2fr 1fr 70px 70px auto auto;gap:6px;align-items:center;margin-bottom:8px;">
          <input data-fi="${idx}" data-fk="name" value="${esc(f.name)}" placeholder="Имя">
          <input data-fi="${idx}" data-fk="handle" value="${esc(f.handle)}" placeholder="@ник">
          <input data-fi="${idx}" data-fk="level" type="number" min="1" value="${esc(f.level || 1)}" title="Уровень">
          <input data-fi="${idx}" data-fk="streak" type="number" min="0" value="${esc(f.streak || 0)}" title="Серия">
          <label class="chk" style="margin:0;font-size:12px" title="Онлайн"><input type="checkbox" data-fi="${idx}" data-fk="online" ${f.online ? 'checked' : ''}>🟢</label>
          <button type="button" class="x" data-fdel="${idx}" title="Удалить">✕</button>
        </div>
      `).join('');

      $$('[data-fi]', box).forEach(inp => {
        const idx = +inp.dataset.fi, k = inp.dataset.fk;
        const handler = () => {
          if (k === 'online') draft.friends[idx][k] = inp.checked;
          else if (k === 'level' || k === 'streak') draft.friends[idx][k] = Number(inp.value) || 0;
          else draft.friends[idx][k] = inp.value;
          draft.friendsOnline = draft.friends.filter(x => x.online).length;
          if ($('#ath-friends')) $('#ath-friends').value = draft.friendsOnline;
          renderPreview();
        };
        inp.oninput = handler;
        inp.onchange = handler;
      });
      $$('[data-fdel]', box).forEach(btn => {
        btn.onclick = () => {
          draft.friends.splice(+btn.dataset.fdel, 1);
          draft.friendsOnline = draft.friends.filter(x => x.online).length;
          if ($('#ath-friends')) $('#ath-friends').value = draft.friendsOnline;
          renderFriendsEditor();
          renderPreview();
        };
      });
    };

    el.innerHTML = `
      <div class="adm-athlete-grid">
        <div class="adm-preview-sticky">
          <div style="font-size:12px;color:var(--mut);font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;text-align:center;">
            Предпросмотр профиля на сайте
          </div>
          <div id="ath-preview-slot"></div>
        </div>

        <div>
          <div class="box" style="margin-top:0">
            <h2 style="margin-top:0">👤 Профиль спортсмена</h2>
            <p style="color:var(--mut);font-size:13px;margin-top:0">Настройте отображение профиля спортсмена: эти параметры будут использоваться на странице профиля на сайте.</p>
            <div class="g2">
              <label class="f">Имя спортсмена<input id="ath-name" value="${esc(draft.name)}"></label>
              <label class="f">Ник (@username)<input id="ath-handle" value="${esc(draft.handle)}"></label>
            </div>
            <label class="f">Аватар спортсмена (загрузить с устройства)</label>
            <div class="up" style="margin-bottom:12px">
              <img class="round" id="ath-av-prev" src="${esc(draft.avatar || 'img/logo.svg')}" onerror="this.style.opacity=.25">
              <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
                <label class="btn alt" style="padding:8px 14px;font-size:12.5px;cursor:pointer">
                  📁 Загрузить с устройства
                  <input type="file" id="ath-av-file" accept="image/*" style="display:none">
                </label>
                <button type="button" class="btn alt" id="ath-av-clr" style="padding:8px 14px;font-size:12.5px">Сбросить</button>
              </div>
            </div>
          </div>

          <div class="box">
            <h2 style="margin-top:0">📊 Показатели и статистика</h2>
            <div class="g2">
              <label class="f">Баланс / Очки (XP)<input id="ath-pts" type="number" min="0" step="1" value="${esc(draft.points)}"></label>
              <label class="f">Выполнение цели (%)<input id="ath-win" type="number" min="0" max="100" value="${esc(draft.winRate)}"></label>
            </div>
            <div class="g2">
              <label class="f">Уровень<input id="ath-lvl" type="number" min="1" value="${esc(draft.level)}"></label>
              <label class="f">Дней активности<input id="ath-days" type="number" min="0" value="${esc(draft.days)}"></label>
            </div>
            <div class="g2">
              <label class="f">Серия подряд (дней)<input id="ath-streak" type="number" min="0" value="${esc(draft.streakDays)}"></label>
              <label class="f">Друзей онлайн<input id="ath-friends" type="number" min="0" value="${esc(draft.friendsOnline)}"></label>
            </div>
            <label class="chk" style="margin-top:8px">
              <input type="checkbox" id="ath-live" ${draft.useLiveStats !== false ? 'checked' : ''}>
              Плюсовать реальные тренировки и рекорды пользователя из дневника
            </label>
          </div>

          <div class="box">
            <h2 style="margin-top:0">🃏 Карточки мотивации и заданий</h2>
            <div class="g2">
              <label class="f">Заголовок «Друзья»<input id="ath-fr-lbl" value="${esc(draft.friendsLabelRu)}"></label>
              <label class="f">Заголовок серии<input id="ath-st-ttl" value="${esc(draft.streakTitleRu)}"></label>
            </div>
            <label class="f">Подпись серии ({n} = число дней)<input id="ath-st-sub" value="${esc(draft.streakSubRu)}"></label>
            <div class="g2">
              <label class="f">Заголовок блока заданий<input id="ath-tk-ttl" value="${esc(draft.taskTitleRu)}"></label>
              <label class="f">Описание блока заданий<input id="ath-tk-sub" value="${esc(draft.taskSubRu)}"></label>
            </div>
            <div class="g2">
              <label class="f">Награда за победу в дуэли (XP)<input id="ath-duel-rw" type="number" min="0" step="50" value="${esc(draft.duelReward ?? 500)}"></label>
              <label class="f">Награда за совместный квест (XP)<input id="ath-quest-rw" type="number" min="0" step="50" value="${esc(draft.questReward ?? 500)}"></label>
            </div>
          </div>

          <div class="box">
            <h2 style="margin-top:0">👥 Друзья спортсмена (${draft.friends.length})</h2>
            <p style="color:var(--mut);font-size:12.5px;margin-top:0">Список друзей по умолчанию, который отображается в профиле и рейтинге.</p>
            <div id="ath-friends-list"></div>
            <button type="button" class="btn alt" id="ath-add-friend" style="padding:8px 14px;font-size:12.5px;margin-top:6px">+ Добавить друга</button>
          </div>

          <div class="sticky" style="display:flex;gap:10px">
            <button class="btn block" id="ath-save" style="animation:none">💾 Сохранить профиль спортсмена</button>
            <button type="button" class="btn alt" id="ath-reset">↺ Сбросить</button>
          </div>
        </div>
      </div>
    `;

    renderFriendsEditor();
    renderPreview();

    $('#ath-add-friend').onclick = () => {
      draft.friends.push({
        id: 'f_' + Date.now(),
        name: 'Новый атлет',
        handle: '@athlete_' + (draft.friends.length + 1),
        level: 6,
        streak: 10,
        points: 12000,
        online: true,
        color: '#344430',
        shirt: '#72a355'
      });
      draft.friendsOnline = draft.friends.filter(x => x.online).length;
      if ($('#ath-friends')) $('#ath-friends').value = draft.friendsOnline;
      renderFriendsEditor();
      renderPreview();
    };

    const bind = (id, key, num) => {
      const inp = $(id);
      if (!inp) return;
      inp.oninput = () => {
        draft[key] = num ? (Number(inp.value) || 0) : inp.value;
        renderPreview();
      };
    };

    bind('#ath-name', 'name');
    bind('#ath-handle', 'handle');
    bind('#ath-pts', 'points', true);
    bind('#ath-win', 'winRate', true);
    bind('#ath-lvl', 'level', true);
    bind('#ath-days', 'days', true);
    bind('#ath-streak', 'streakDays', true);
    bind('#ath-friends', 'friendsOnline', true);
    bind('#ath-fr-lbl', 'friendsLabelRu');
    bind('#ath-st-ttl', 'streakTitleRu');
    bind('#ath-st-sub', 'streakSubRu');
    bind('#ath-tk-ttl', 'taskTitleRu');
    bind('#ath-tk-sub', 'taskSubRu');
    bind('#ath-duel-rw', 'duelReward', true);
    bind('#ath-quest-rw', 'questReward', true);

    $('#ath-live').onchange = () => {
      draft.useLiveStats = $('#ath-live').checked;
    };

    $('#ath-av-file').onchange = async e => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        toast('Загрузка аватара...');
        const path = await upload('athlete_avatar', f);
        draft.avatar = path;
        $('#ath-av-prev').src = path;
        $('#ath-av-prev').style.opacity = 1;
        renderPreview();
        toast('Аватар загружен ✓');
      } catch (er) {
        toast(er.message, 1);
      }
    };

    $('#ath-av-clr').onclick = () => {
      draft.avatar = '';
      $('#ath-av-prev').src = 'img/logo.svg';
      renderPreview();
    };

    $('#ath-reset').onclick = () => {
      CFG.athlete = ATH_DEF();
      tabAthlete(el);
      toast('Сброшено к шаблону');
    };

    $('#ath-save').onclick = async () => {
      CFG.athlete = Object.assign(ATH_DEF(), draft);
      try {
        await saveCfg();
        toast('Профиль спортсмена сохранён ✓');
      } catch (er) {
        toast(er.message, 1);
      }
    };
  }

  // ---------- tab: interface ----------
  function tabUI(el) {
    const S = CFG.sections || {};
    const NAV = [['home', 'Главная'], ['programs', 'Программы'], ['workouts', 'Тренировки'], ['coach', 'AI-тренер'], ['exercises', 'Упражнения'], ['history', 'Профиль']];
    const swatches = ['#d89e48', '#88bc6c', '#e5b25c', '#b4f82b', '#00d2ff', '#ff7a1a'];
    el.innerHTML = `
    <div class="box"><h2 style="margin-top:0">Бренд</h2>
      <label class="f">Название сайта<input id="c-brand" value="${esc(CFG.brand)}"></label>
      <label class="f">Акцентный цвет</label>
      <div class="up" style="margin-bottom:14px"><input type="color" id="c-accent" value="${esc(CFG.accent)}">${swatches.map(c => `<button type="button" class="x sw" data-c="${c}" style="width:34px;background:${c}"></button>`).join('')}</div>
      <label class="f">Логотип (квадратный png/svg)</label>${imgPicker('c-logo', CFG.logo || 'img/logo.svg', 'sq')}
    </div>
    <div class="box"><h2 style="margin-top:0">Главный баннер</h2>
      <label class="f">Программа в баннере<select id="c-hp">${D.programs.map(p => `<option value="${p.id}" ${p.id == CFG.heroProgram ? 'selected' : ''}>${esc(effP(p.id).t.ru || effP(p.id).t.en)}</option>`).join('')}</select></label>
      <div class="g2"><label class="f">Заголовок RU (пусто = название программы)<input id="c-ht-ru" value="${esc((CFG.heroTitle || {}).ru)}"></label><label class="f">Заголовок EN<input id="c-ht-en" value="${esc((CFG.heroTitle || {}).en)}"></label></div>
      <div class="g2"><label class="f">Текст RU<textarea id="c-hx-ru" rows="2">${esc((CFG.heroText || {}).ru)}</textarea></label><label class="f">Текст EN<textarea id="c-hx-en" rows="2">${esc((CFG.heroText || {}).en)}</textarea></label></div>
      <label class="f">Ссылка кнопки (пусто = страница программы), например #/workouts<input id="c-hl" value="${esc(CFG.heroLink)}"></label>
      <label class="f">Своя картинка баннера</label>${imgPicker('c-hi', CFG.heroImage)}
    </div>
    <div class="box"><h2 style="margin-top:0">Блоки главной страницы</h2>
      ${[['hero', 'Баннер'], ['activity', 'Активность за неделю'], ['quick', 'Быстрые тренировки'], ['featured', 'Рекомендуемые программы']].map(([k, n]) => `<label class="chk"><input type="checkbox" data-sec="${k}" ${S[k] !== false ? 'checked' : ''}> ${n}</label>`).join('')}
      <label class="f" style="margin-top:12px">Цель: тренировок в неделю<input id="c-goal" type="number" min="1" value="${CFG.goal}"></label>
    </div>
    <div class="box"><h2 style="margin-top:0">Пункты нижнего меню</h2>
      ${NAV.map(([k, n]) => `<label class="chk"><input type="checkbox" data-nav="${k}" ${(CFG.hidden || []).includes(k) ? '' : 'checked'}> ${n}</label>`).join('')}
    </div>
    <div class="box"><h2 style="margin-top:0">Тексты интерфейса</h2><p style="color:var(--mut);font-size:13px;margin-top:0">Серым показан текст по умолчанию. Заполните поле, чтобы заменить его.</p>
      <div class="tt"><b>ключ</b><b>RU</b><b>EN</b></div>
      ${Object.keys(T.ru).map(k => `<div class="tt"><span>${k}</span><input data-tk="${k}" data-l="ru" placeholder="${esc(T.ru[k])}" value="${esc((CFG.t.ru || {})[k])}"><input data-tk="${k}" data-l="en" placeholder="${esc(T.en[k] || '')}" value="${esc((CFG.t.en || {})[k])}"></div>`).join('')}
    </div>
    <div class="sticky"><button class="btn block" id="c-save" style="animation:none">💾 Сохранить интерфейс</button></div>`;

    $$('.sw').forEach(b => b.onclick = () => $('#c-accent').value = b.dataset.c);
    const hook = (id, key, name) => {
      $('#' + id).onchange = async e => {
        try {
          const path = await upload(name, e.target.files[0]);
          CFG[key] = path;
          await saveCfg();
          $('#' + id + '-prev').src = path;
          $('#' + id + '-prev').style.opacity = 1;
          toast('Картинка загружена');
        } catch (er) {
          toast(er.message, 1);
        }
      };
      $('#' + id + '-clr').onclick = async () => {
        CFG[key] = '';
        await saveCfg();
        $('#' + id + '-prev').src = key == 'logo' ? 'img/logo.svg' : '';
        toast('Сброшено');
      };
    };
    hook('c-logo', 'logo', 'logo');
    hook('c-hi', 'heroImage', 'hero_image');

    $('#c-save').onclick = async () => {
      CFG.brand = $('#c-brand').value.trim() || 'Flexa';
      CFG.accent = $('#c-accent').value;
      CFG.heroProgram = +$('#c-hp').value;
      CFG.heroTitle = { ru: $('#c-ht-ru').value, en: $('#c-ht-en').value };
      CFG.heroText = { ru: $('#c-hx-ru').value, en: $('#c-hx-en').value };
      CFG.heroLink = $('#c-hl').value.trim();
      CFG.goal = Math.max(1, +$('#c-goal').value || 5);
      CFG.sections = {};
      $$('[data-sec]').forEach(c => CFG.sections[c.dataset.sec] = c.checked);
      CFG.hidden = $$('[data-nav]').filter(c => !c.checked).map(c => c.dataset.nav);
      CFG.t = { ru: {}, en: {} };
      $$('[data-tk]').forEach(i => {
        const v = i.value.trim();
        if (v && v !== (T[i.dataset.l][i.dataset.tk] || '')) CFG.t[i.dataset.l][i.dataset.tk] = v;
      });
      try {
        await saveCfg();
        toast('Сохранено ✓');
      } catch (e) {
        toast(e.message, 1);
      }
    };
  }

  // ---------- tab: programs ----------
  function tabPrograms(el) {
    if (sub) return programEditor(el, sub);
    el.innerHTML = `<div class="pl">${D.programs.map(p => {
      const e = effP(p.id), im = pImg(e);
      return `<div class="card" data-id="${p.id}">${im ? `<img class="cover" src="${esc(im)}">` : ''}<div class="b"><h3>${esc(e.t.ru || e.t.en)}</h3><div class="tags"><span class="tag">${e.days} дн.</span>${OV.p[p.id] ? '<span class="tag pro">изменено</span>' : ''}</div></div></div>`;
    }).join('')}</div>`;
    $$('.card', el).forEach(c => c.onclick = () => { sub = c.dataset.id; tabPrograms(el); window.scrollTo(0, 0); });
  }

  function programEditor(el, id) {
    const p = effP(id);
    el.innerHTML = `<button class="btn alt" id="back">← Все программы</button><h1 style="margin-top:14px">${esc(p.t.ru || p.t.en)}</h1>
    <div class="box"><label class="f">Картинка программы</label>${imgPicker('p-img', pImg(p))}</div>
    <div class="box"><div class="g2"><label class="f">Название RU<input id="p-tr" value="${esc(p.t.ru)}"></label><label class="f">Название EN<input id="p-te" value="${esc(p.t.en)}"></label></div>
    <label class="f">Длительность (дней)<input id="p-days" type="number" min="1" value="${p.days}"></label>
    <label class="f">Описание RU (можно HTML: &lt;b&gt;, &lt;a href='workout-123'&gt;)<textarea id="p-dr" rows="10">${esc(p.d.ru)}</textarea></label>
    <label class="f">Описание EN<textarea id="p-de" rows="10">${esc(p.d.en)}</textarea></label></div>
    <div class="sticky"><button class="btn block" id="p-save" style="animation:none">💾 Сохранить программу</button><p><button class="btn alt" id="p-reset">↺ Сбросить к оригиналу</button></p></div>`;

    $('#back').onclick = () => { sub = null; tabPrograms(el); };
    $('#p-img').onchange = async e => {
      try {
        const path = await upload('program_' + id, e.target.files[0]);
        OV.p[id] = Object.assign(OV.p[id] || {}, { image: path });
        await saveOv();
        $('#p-img-prev').src = path;
        $('#p-img-prev').style.opacity = 1;
        toast('Картинка загружена');
      } catch (er) {
        toast(er.message, 1);
      }
    };
    $('#p-img-clr').onclick = async () => {
      if (OV.p[id]) delete OV.p[id].image;
      await saveOv();
      $('#p-img-prev').src = pImg(effP(id));
      toast('Возвращена оригинальная картинка');
    };
    $('#p-save').onclick = async () => {
      OV.p[id] = Object.assign(OV.p[id] || {}, {
        t: { ru: $('#p-tr').value, en: $('#p-te').value },
        d: { ru: $('#p-dr').value, en: $('#p-de').value },
        days: Math.max(1, +$('#p-days').value || 1)
      });
      try {
        await saveOv();
        toast('Сохранено ✓');
      } catch (e) {
        toast(e.message, 1);
      }
    };
    $('#p-reset').onclick = () => {
      confirmDangerous('Сброс программы', 'Сбросить все правки этой программы к исходному виду?', async () => {
        delete OV.p[id];
        await saveOv();
        programEditor(el, id);
        toast('Сброшено');
      }, 'Сбросить');
    };
  }

  // ---------- tab: workouts ----------
  let wq = '', wShown = 60;
  function tabWorkouts(el) {
    if (sub) return workoutEditor(el, sub);
    const all = [...OV.c.map(w => w.id), ...D.workouts.map(w => w.id)].map(effW);
    const list = all.filter(w => (w.t.ru || w.t.en) && (!wq || (w.t.ru + ' ' + w.t.en).toLowerCase().includes(wq.toLowerCase())));
    el.innerHTML = `<div class="up" style="margin-bottom:14px"><input id="wq" placeholder="Поиск по названию…" value="${esc(wq)}" style="flex:1"><button class="btn" id="wnew" style="animation:none">＋ Новая тренировка</button></div>
    <p style="color:var(--mut);font-size:13px">Показаны тренировки с названиями (${list.length}). Тренировки программ без названия правятся по номеру: <input id="wid" type="number" placeholder="№" style="width:90px;display:inline-block"> <button class="btn alt" id="wgo" style="padding:6px 12px">открыть</button></p>
    <div>${list.slice(0, wShown).map(w => `<div class="item" data-id="${w.id}" style="cursor:pointer"><span class="num">${w.custom ? '★' : ''}</span><span class="nm">${esc(w.t.ru || w.t.en)}<small>${w.s.reduce((n, s) => n + s.length - 1, 0)} упр.${OV.w[w.id] ? ' · изменено' : ''}${w.custom ? ' · своя' : ''}</small></span><span class="go">›</span></div>`).join('')}</div>
    ${list.length > wShown ? '<p style="text-align:center"><button class="btn alt" id="wmore">Показать ещё</button></p>' : ''}`;

    $('#wq').oninput = e => {
      wq = e.target.value;
      wShown = 60;
      const pos = e.target.selectionStart;
      tabWorkouts(el);
      const i = $('#wq');
      if (i) { i.focus(); i.setSelectionRange(pos, pos); }
    };
    $$('.item', el).forEach(i => i.onclick = () => { sub = i.dataset.id; tabWorkouts(el); window.scrollTo(0, 0); });
    const m = $('#wmore');
    if (m) m.onclick = () => { wShown += 60; tabWorkouts(el); };
    $('#wgo').onclick = () => {
      const id = +$('#wid').value;
      if (D.workouts.find(w => w.id == id)) { sub = id; tabWorkouts(el); }
      else toast('Нет такой тренировки', 1);
    };
    $('#wnew').onclick = async () => {
      const nm = prompt('Название новой тренировки');
      if (!nm) return;
      const id = Math.max(900000, ...OV.c.map(x => x.id)) + 1;
      OV.c.push({ id, custom: true, diff: 'normal', eq: '', temp: 'moderate', rating: 0, rb: 30, rr: 60, pro: false, t: { ru: nm, en: nm }, d: {}, s: [[1, [3, 'repeat', 10, 0]]] });
      await saveOv();
      sub = id;
      tabWorkouts(el);
    };
  }

  function workoutEditor(el, id) {
    const w = effW(id);
    const draft = JSON.parse(JSON.stringify({
      t: { ru: w.t.ru || '', en: w.t.en || '' },
      d: { ru: w.d.ru || '', en: w.d.en || '' },
      rb: w.rb,
      rr: w.rr,
      diff: w.diff,
      temp: w.temp,
      s: w.s
    }));
    const byName = {};
    D.exercises.forEach(e => { if (exName(e)) byName[exName(e).toLowerCase()] = e; });
    const dopt = (arr, cur) => arr.map(v => `<option value="${v}" ${v == cur ? 'selected' : ''}>${v}</option>`).join('');

    el.innerHTML = `<button class="btn alt" id="back">← Все тренировки</button><h1 style="margin-top:14px">${esc(draft.t.ru || draft.t.en || '#' + id)} <small style="color:var(--mut);font-size:14px">№${id}</small></h1><div id="ed"></div>
    <div class="sticky"><button class="btn block" id="w-save" style="animation:none">💾 Сохранить тренировку</button><p class="up">${w.custom ? '<button class="btn alt" id="w-del">🗑 Удалить тренировку</button>' : '<button class="btn alt" id="w-reset">↺ Сбросить к оригиналу</button>'}</p></div>`;

    const box = $('#ed');
    function draw() {
      box.innerHTML = `<div class="box"><div class="g2"><label class="f">Название RU<input data-f="tr" value="${esc(draft.t.ru)}"></label><label class="f">Название EN<input data-f="te" value="${esc(draft.t.en)}"></label></div>
      <div class="g2"><label class="f">Сложность<select data-f="diff">${dopt(['easy', 'normal', 'hard', 'monster'], draft.diff)}</select></label><label class="f">Темп<select data-f="temp">${dopt(['light', 'moderate', 'intense', 'extremly_hard'], draft.temp)}</select></label></div>
      <div class="g2"><label class="f">Отдых между упражнениями, сек<input type="number" min="0" data-f="rb" value="${draft.rb}"></label><label class="f">Отдых между подходами, сек<input type="number" min="0" data-f="rr" value="${draft.rr}"></label></div>
      <div class="g2"><label class="f">Описание RU<textarea rows="4" data-f="dr">${esc(draft.d.ru)}</textarea></label><label class="f">Описание EN<textarea rows="4" data-f="de">${esc(draft.d.en)}</textarea></label></div></div>
      ${draft.s.map((s, i) => `<div class="box"><div class="eh"><span>Подход ${i + 1}</span><label style="font-size:12px;color:var(--mut)">кругов</label><input type="number" min="1" data-si="${i}" data-f="rounds" value="${s[0]}"><button class="x" style="width:40px" data-ds="${i}">🗑</button></div>
        <div class="ecap"><span></span><span>значение</span><span>ед.</span><span>отдых</span><span></span></div>
        ${s.slice(1).map((n, j) => {
          const e = exMap[n[0]];
          return `<div class="erow"><span class="nm">${esc(e ? exName(e) : '#' + n[0])}</span><input type="number" min="0" data-si="${i}" data-nj="${j}" data-f="val" value="${n[2]}"><select data-si="${i}" data-nj="${j}" data-f="unit"><option value="repeat" ${n[1] == 'repeat' ? 'selected' : ''}>повт.</option><option value="second" ${n[1] == 'second' ? 'selected' : ''}>сек</option></select><input type="number" min="0" data-si="${i}" data-nj="${j}" data-f="rest" value="${n[3]}"><button class="x" data-dn="${i},${j}">✕</button></div>`;
        }).join('')}
        <input list="exl" placeholder="＋ добавить упражнение (начните вводить название)" data-add="${i}" style="border-style:dashed;margin-top:6px"></div>`).join('')}
      <p><button class="btn alt" id="addset">＋ Подход</button></p>
      <datalist id="exl">${D.exercises.filter(e => exName(e) && e.img).map(e => `<option value="${esc(exName(e))}">`).join('')}</datalist>`;
    }

    box.oninput = ev => {
      const d = ev.target.dataset, f = d.f, v = ev.target.value;
      if (!f) return;
      const map = {
        tr: () => draft.t.ru = v,
        te: () => draft.t.en = v,
        dr: () => draft.d.ru = v,
        de: () => draft.d.en = v,
        diff: () => draft.diff = v,
        temp: () => draft.temp = v,
        rb: () => draft.rb = Math.max(0, +v || 0),
        rr: () => draft.rr = Math.max(0, +v || 0),
        rounds: () => draft.s[d.si][0] = Math.max(1, +v || 1)
      };
      if (map[f]) return map[f]();
      const n = draft.s[d.si][+d.nj + 1];
      if (f == 'val') n[2] = Math.max(0, +v || 0);
      if (f == 'unit') n[1] = v;
      if (f == 'rest') n[3] = Math.max(0, +v || 0);
    };

    box.onchange = ev => {
      const a = ev.target.dataset.add;
      if (a === undefined) return;
      const e = byName[ev.target.value.trim().toLowerCase()];
      if (!e) return;
      draft.s[a].push([e.id, e.unit == 'second' ? 'second' : 'repeat', e.unit == 'second' ? 30 : 10, 0]);
      draw();
    };

    box.onclick = ev => {
      const b = ev.target.closest('button');
      if (!b) return;
      if (b.dataset.ds !== undefined) { draft.s.splice(b.dataset.ds, 1); draw(); }
      else if (b.dataset.dn) { const [i, j] = b.dataset.dn.split(','); draft.s[i].splice(+j + 1, 1); draw(); }
      else if (b.id == 'addset') { draft.s.push([1, [3, 'repeat', 10, 0]]); draw(); }
    };

    $('#back').onclick = () => { sub = null; tabWorkouts(el); };
    $('#w-save').onclick = async () => {
      const s = draft.s.filter(x => x.length > 1);
      if (!s.length) return toast('Добавьте хотя бы одно упражнение', 1);
      const o = { t: draft.t, d: draft.d, rb: draft.rb, rr: draft.rr, diff: draft.diff, temp: draft.temp, s };
      if (w.custom) Object.assign(OV.c.find(x => x.id == id), o);
      else OV.w[id] = o;
      try {
        await saveOv();
        toast('Сохранено ✓');
      } catch (e) {
        toast(e.message, 1);
      }
    };
    const r = $('#w-reset');
    if (r) r.onclick = () => {
      confirmDangerous('Сброс тренировки', 'Сбросить все правки этой тренировки к оригиналу?', async () => {
        delete OV.w[id];
        await saveOv();
        workoutEditor(el, id);
        toast('Сброшено');
      }, 'Сбросить');
    };
    const dl = $('#w-del');
    if (dl) dl.onclick = () => {
      confirmDangerous('Удаление тренировки', 'Удалить эту пользовательскую тренировку без возможности восстановления?', async () => {
        OV.c = OV.c.filter(x => x.id != id);
        await saveOv();
        sub = null;
        tabWorkouts(el);
        toast('Тренировка удалена');
      }, 'Удалить');
    };
    draw();
  }

  // ---------- tab: exercises ----------
  let exSearchQ = '', exFilterVid = 'all', exPage = 40;
  function tabExercises(el) {
    OV.e = OV.e || {};
    if (sub) {
      const e = effE(sub);
      if (!e || !e.id) { sub = null; return tabExercises(el); }
      const currentVideo = e.video || '';

      el.innerHTML = `
        <div class="box">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <button class="btn alt" id="ex-back">← Назад к списку</button>
            <span style="color:var(--mut);font-size:13px;">ID: #${e.id}</span>
          </div>
          <h2 style="margin:0 0 16px 0;">Редактирование: ${esc(exName(e))}</h2>

          <div class="box" style="background:rgba(0,0,0,0.25);border:1px solid rgba(var(--acr),0.3);border-radius:16px;margin-bottom:20px;padding:18px;">
            <h3 style="margin-top:0;display:flex;align-items:center;gap:8px;color:var(--ac);">📹 Видео / Анимация упражнения</h3>
            <p style="color:var(--mut);font-size:13px;line-height:1.5;">
              Вы можете <b>вставить прямую ссылку на видео из интернета</b> (любой MP4, WebM или GIF), либо <b>загрузить видео-файл со своего компьютера</b>.<br>
              Если поле оставить пустым — в приложении будет отображаться стандартная векторная схема.
            </p>

            <div style="margin:16px 0;">
              <label class="f" style="font-weight:700;">Ссылка на видео из интернета (URL):
                <input id="ex-video-url" placeholder="https://...mp4, webm или gif" value="${esc(currentVideo)}" style="font-family:monospace;font-size:13px;">
              </label>
            </div>

            <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px;">
              <label class="btn alt" style="cursor:pointer;display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.08);">
                📁 Загрузить файл с компьютера (MP4 / WebM / GIF)
                <input type="file" id="ex-video-file" accept="video/mp4,video/webm,image/gif" style="display:none">
              </label>
              <button type="button" class="btn alt" id="ex-video-clear" style="color:#ef4444;border-color:rgba(239,68,68,0.3);">❌ Очистить видео</button>
            </div>

            <div style="margin-top:14px;">
              <div style="font-size:12px;color:var(--mut);margin-bottom:8px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">Предпросмотр видео:</div>
              <div id="ex-video-preview-box" style="width:100%;max-width:380px;aspect-ratio:16/9;background:#050d0b;border-radius:14px;overflow:hidden;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,0.12);box-shadow:0 8px 24px rgba(0,0,0,0.4);">
                ${currentVideo ? `<video src="${currentVideo}" controls autoplay loop muted playsinline style="width:100%;height:100%;object-fit:contain;"></video>` : '<span style="color:var(--mut);font-size:12px;">Видео не задано (схема)</span>'}
              </div>
            </div>
          </div>

          <div class="g2">
            <label class="f">Название (RU)<input id="ex-n-ru" value="${esc((e.n && e.n.ru) || '')}"></label>
            <label class="f">Название (EN)<input id="ex-n-en" value="${esc((e.n && e.n.en) || '')}"></label>
          </div>
          <label class="f">Описание техники (RU)<textarea id="ex-d-ru" rows="4">${esc((e.d && (e.d.ru || e.d.en)) || '')}</textarea></label>
        </div>
        <div class="sticky">
          <button class="btn block" id="ex-save" style="animation:none">💾 Сохранить упражнение</button>
        </div>
      `;

      $('#ex-back').onclick = () => { sub = null; tabExercises(el); };

      const updatePreview = url => {
        const pBox = $('#ex-video-preview-box');
        if (url && url.trim()) {
          pBox.innerHTML = `<video src="${url.trim()}" controls autoplay loop muted playsinline style="width:100%;height:100%;object-fit:contain;"></video>`;
        } else {
          pBox.innerHTML = '<span style="color:var(--mut);font-size:12px;">Видео не задано (схема)</span>';
        }
      };

      $('#ex-video-url').oninput = e => {
        updatePreview(e.target.value);
      };

      $('#ex-video-clear').onclick = () => {
        $('#ex-video-url').value = '';
        updatePreview('');
        toast('Видео удалено. Нажмите "Сохранить"');
      };

      $('#ex-video-file').onchange = async ev => {
        const file = ev.target.files[0];
        if (!file) return;
        try {
          toast('Загрузка видеофайла...');
          const path = await upload('ex_video_' + e.id, file);
          $('#ex-video-url').value = path;
          updatePreview(path);
          toast('✓ Видео успешно загружено!');
        } catch(err) {
          alert('Ошибка загрузки: ' + err.message);
        }
      };

      $('#ex-save').onclick = async () => {
        const vUrl = $('#ex-video-url').value.trim();
        const nRu = $('#ex-n-ru').value.trim();
        const nEn = $('#ex-n-en').value.trim();
        const dRu = $('#ex-d-ru').value.trim();

        OV.e[e.id] = OV.e[e.id] || {};
        if (vUrl) {
          OV.e[e.id].video = vUrl;
        } else {
          delete OV.e[e.id].video;
        }

        if (nRu || nEn) {
          OV.e[e.id].n = Object.assign({}, e.n, { ru: nRu, en: nEn });
        }
        if (dRu) {
          OV.e[e.id].d = Object.assign({}, e.d, { ru: dRu });
        }

        if (!Object.keys(OV.e[e.id]).length) {
          delete OV.e[e.id];
        }

        await saveOv();
        toast('✓ Упражнение сохранено!');
        sub = null;
        tabExercises(el);
      };
      return;
    }

    const q = exSearchQ.trim().toLowerCase();
    let list = D.exercises.map(e => effE(e.id));
    if (q) {
      list = list.filter(e => String(e.id).includes(q) || (e.n && ((e.n.ru && e.n.ru.toLowerCase().includes(q)) || (e.n.en && e.n.en.toLowerCase().includes(q)))));
    }
    if (exFilterVid === 'with_video') {
      list = list.filter(e => !!e.video);
    } else if (exFilterVid === 'no_video') {
      list = list.filter(e => !e.video);
    }

    const total = list.length;
    const pageItems = list.slice(0, exPage);

    el.innerHTML = `
      <div class="box">
        <h2 style="margin-top:0">Упражнения и Видео (${D.exercises.length})</h2>
        <p style="color:var(--mut);font-size:13px;line-height:1.5;">
          Здесь вы можете выбрать любое упражнение и прикрепить к нему собственное видео: вставить прямую ссылку на видеоролик/анимацию из интернета или загрузить файл MP4/WebM с диска.
        </p>

        <div class="g2" style="margin-bottom:14px;">
          <input id="ex-search" placeholder="🔍 Поиск по названию или ID (например, отжимания, приседания, 1, 2)..." value="${esc(exSearchQ)}">
          <div style="display:flex;gap:6px;">
            <button class="btn ${exFilterVid === 'all' ? '' : 'alt'}" data-vf="all" style="padding:8px 12px;font-size:12px;">Все (${D.exercises.length})</button>
            <button class="btn ${exFilterVid === 'with_video' ? '' : 'alt'}" data-vf="with_video" style="padding:8px 12px;font-size:12px;">С видео (${D.exercises.filter(e => !!effE(e.id).video).length})</button>
            <button class="btn ${exFilterVid === 'no_video' ? '' : 'alt'}" data-vf="no_video" style="padding:8px 12px;font-size:12px;">Без видео</button>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;">
          ${pageItems.map(e => `
            <div class="ex-admin-item" data-id="${e.id}" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:12px;display:flex;align-items:center;gap:12px;cursor:pointer;transition:0.2s;">
              <div style="width:48px;height:48px;min-width:48px;background:rgba(0,0,0,0.3);border-radius:8px;overflow:hidden;display:flex;align-items:center;justify-content:center;">
                ${e.img ? `<img src="img/ex/svg_norm_${e.id}.svg" style="max-height:36px;max-width:36px;" onerror="this.onerror=null;this.parentElement.innerHTML='💪'">` : '💪'}
              </div>
              <div style="flex-grow:1;min-width:0;">
                <div style="font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(exName(e))}</div>
                <div style="font-size:11px;color:var(--mut);">#${e.id} · ${e.n && e.n.en ? esc(e.n.en) : ''}</div>
                <div style="margin-top:4px;">
                  ${e.video ? '<span style="background:rgba(var(--acr),0.18);color:var(--ac);border:1px solid rgba(var(--acr),0.32);padding:1px 6px;border-radius:6px;font-size:10px;font-weight:800;">📹 Видео подключено</span>' : '<span style="color:var(--mut);font-size:10px;">Без видео (схема)</span>'}
                </div>
              </div>
              <span style="color:var(--mut);font-size:18px;">›</span>
            </div>
          `).join('')}
        </div>

        ${exPage < total ? `
          <div style="text-align:center;margin-top:20px;">
            <button class="btn alt" id="ex-load-more">Показать еще (осталось ${total - exPage})</button>
          </div>` : ''}
      </div>
    `;

    $('#ex-search').oninput = e => {
      exSearchQ = e.target.value;
      exPage = 40;
      tabExercises(el);
    };

    $$('[data-vf]').forEach(b => {
      b.onclick = () => {
        exFilterVid = b.dataset.vf;
        exPage = 40;
        tabExercises(el);
      };
    });

    $$('.ex-admin-item').forEach(card => {
      card.onclick = () => {
        sub = card.dataset.id;
        tabExercises(el);
      };
    });

    const lm = $('#ex-load-more');
    if (lm) {
      lm.onclick = () => {
        exPage += 40;
        tabExercises(el);
      };
    }
  }

  // ---------- tab: ai ----------
  async function tabAI(el) {
    let c = {};
    try { c = await api('ai/settings'); } catch (e) { return toast(e.message, 1); }
    const GEMINI_DEFAULT_MODEL = 'gemini-flash-lite-latest';
    const curModel = (c.model || '').trim() || (c.provider == 'gemini' ? GEMINI_DEFAULT_MODEL : '');
    const PRESETS = [
      ['DeepSeek', 'https://api.deepseek.com', 'deepseek-v4-flash'],
      ['OpenRouter', 'https://openrouter.ai/api/v1', 'meta-llama/llama-3.3-70b-instruct:free'],
      ['OpenAI', 'https://api.openai.com/v1', 'gpt-4o-mini'],
      ['Groq', 'https://api.groq.com/openai/v1', 'llama-3.3-70b-versatile'],
      ['Ollama (локально)', 'http://localhost:11434/v1', 'llama3.2']
    ];
    el.innerHTML = `<div class="box"><h2 style="margin-top:0">AI-тренер</h2>
      <label class="f">Провайдер<select id="ai-prov">
        <option value="builtin" ${c.provider == 'builtin' ? 'selected' : ''}>⚡ Встроенный автономный тренер (всегда бесплатно, без ключей и оплат)</option>
        <option value="openai" ${c.provider == 'openai' ? 'selected' : ''}>OpenAI-совместимый (DeepSeek, OpenRouter, Groq, Ollama…)</option>
        <option value="gemini" ${c.provider == 'gemini' ? 'selected' : ''}>Google Gemini (доступен не во всех регионах)</option>
      </select></label>
      <div id="ai-presets" class="up" style="margin-bottom:12px">${PRESETS.map((p, i) => `<button type="button" class="btn alt" style="padding:6px 12px;font-size:12px" data-p="${i}">${p[0]}</button>`).join('')}</div>
      <label class="f" id="ai-bu-w">Base URL<input id="ai-bu" name="ai_base_url" autocomplete="off" value="${esc(c.baseUrl)}" placeholder="https://api.openai.com/v1"></label>
      <div id="ai-key-w">
        <p>Статус ключа: <b style="color:${c.hasKey ? 'var(--ac)' : 'var(--mut)'}">${c.hasKey ? 'сохранён (' + esc(c.keyHint) + ')' : 'не задан'}</b></p>
        <label class="f">API-ключ (пусто = не менять; для локального Ollama ключ не нужен)<input id="ai-key" name="ai_api_key" type="password" autocomplete="new-password" spellcheck="false" placeholder="${c.hasKey ? 'Оставьте пустым, чтобы не менять' : 'Вставьте API-ключ'}"></label>
      </div>
      <label class="f" id="ai-model-w">Модель<input id="ai-model" name="ai_model" autocomplete="off" value="${esc(curModel)}"></label>
      <label class="chk"><input type="checkbox" id="ai-on" ${c.enabled ? 'checked' : ''}> Показывать AI-тренера на сайте</label>
      <label class="f" style="margin-top:12px">Дополнительные инструкции тренеру (тон, ограничения, акценты)<textarea id="ai-prompt" rows="5">${esc(c.prompt)}</textarea></label>
      <p style="color:var(--mut);font-size:12px">Ключ хранится только на сервере и не отправляется в браузер посетителей.</p>
      <div class="up"><button class="btn" id="ai-save" style="animation:none">💾 Сохранить</button>${c.hasKey ? '<button class="btn alt" id="ai-clr">Удалить ключ</button>' : ''}</div></div>`;

    const sync = () => {
      const p = $('#ai-prov').value;
      $('#ai-bu-w').style.display = p == 'openai' ? '' : 'none';
      $('#ai-presets').style.display = p == 'openai' ? '' : 'none';
      $('#ai-key-w').style.display = p == 'builtin' ? 'none' : '';
      $('#ai-model-w').style.display = p == 'builtin' ? 'none' : '';
    };
    $('#ai-prov').onchange = () => {
      sync();
      if ($('#ai-prov').value == 'gemini' && !/gemini/.test($('#ai-model').value)) {
        $('#ai-model').value = GEMINI_DEFAULT_MODEL;
      }
    };
    $$('[data-p]').forEach(b => b.onclick = () => {
      const p = PRESETS[b.dataset.p];
      $('#ai-bu').value = p[1];
      $('#ai-model').value = p[2];
    });
    sync();

    const save = async extra => {
      try {
        const prov = $('#ai-prov').value;
        const payload = {
          provider: prov,
          key: $('#ai-key').value,
          model: $('#ai-model').value,
          enabled: $('#ai-on').checked,
          prompt: $('#ai-prompt').value
        };
        if (prov === 'openai') {
          payload.baseUrl = $('#ai-bu').value;
        }
        await post('ai/settings', Object.assign(payload, extra || {}));
        toast('Сохранено ✓');
        tabAI(el);
      } catch (e) {
        toast(e.message, 1);
      }
    };
    $('#ai-save').onclick = () => save();
    const cl = $('#ai-clr');
    if (cl) cl.onclick = () => confirmDangerous('Удаление API-ключа AI Coach', 'Удалить сохранённый API-ключ внешнего AI-провайдера? Это сразу повлияет на работу AI Coach.', () => save({ clearKey: true, key: '' }), 'Удалить ключ');
  }

  // ---------- tab: users & subscriptions ----------
  let uQuery = '';
  async function tabUsers(el) {
    el.innerHTML = `<div class="box"><p style="color:var(--mut)">Загрузка пользователей из базы данных...</p></div>`;
    let data;
    try {
      data = await api('admin/users' + (uQuery ? '?q=' + encodeURIComponent(uQuery) : ''));
    } catch (e) {
      el.innerHTML = `<div class="box"><p style="color:#ff8f8f">Ошибка загрузки: ${esc(e.message)}</p></div>`;
      return;
    }
    const st = data.stats || { total: 0, pro: 0, blocked: 0 };
    const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
    el.innerHTML = `
      <div class="box">
        <h2 style="margin-top:0">Пользователи и подписки</h2>
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;">
          <div style="padding:10px 14px;border-radius:12px;background:rgba(255,255,255,.04);border:1px solid var(--line)">Всего: <b>${st.total}</b></div>
          <div style="padding:10px 14px;border-radius:12px;background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.35)">Активных PRO: <b>${st.pro}</b></div>
          <div style="padding:10px 14px;border-radius:12px;background:rgba(244,63,94,.12);border:1px solid rgba(244,63,94,.35)">Заблокировано: <b>${st.blocked}</b></div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:14px;">
          <input id="u-q" value="${esc(uQuery)}" placeholder="Поиск по логину или email..." style="flex:1;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--txt)">
          <button class="btn" id="u-search" style="animation:none">Найти</button>
          <button class="btn alt" id="u-reset-q">Сброс</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px;">
          ${(data.users || []).map(u => {
            const planLabel = u.isPro ? (u.planExpiresAt ? 'PRO до ' + fmtDate(u.planExpiresAt) : 'PRO навсегда') : 'FREE';
            const planColor = u.isPro ? '#10b981' : '#9ca3af';
            return `<div style="padding:12px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.02);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;">
              <div>
                <div style="font-weight:700;font-size:15px;">
                  @${esc(u.username)}
                  <span style="margin-left:8px;font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid ${planColor};color:${planColor}">${esc(planLabel)}</span>
                  ${u.isBlocked ? '<span style="margin-left:6px;font-size:11px;padding:2px 8px;border-radius:99px;background:#ef4444;color:#fff">БЛОК</span>' : ''}
                </div>
                <div style="font-size:12px;color:var(--mut);margin-top:4px;">
                  Email: <b>${esc(u.email || 'не указан')}</b> · Рег: ${fmtDate(u.createdAt)} · Вход: ${fmtDate(u.lastLoginAt)}
                </div>
              </div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <button class="btn alt u-act" data-act="pro30" data-id="${u.id}" style="padding:6px 10px;font-size:12px">+30д PRO</button>
                <button class="btn alt u-act" data-act="pro365" data-id="${u.id}" style="padding:6px 10px;font-size:12px">+365д PRO</button>
                <button class="btn alt u-act" data-act="pro0" data-id="${u.id}" style="padding:6px 10px;font-size:12px">PRO навсегда</button>
                <button class="btn alt u-act" data-act="free" data-id="${u.id}" style="padding:6px 10px;font-size:12px">Free</button>
                <button class="btn alt u-act" data-act="reset" data-id="${u.id}" style="padding:6px 10px;font-size:12px">Код сброса</button>
                <button class="btn alt u-act" data-act="${u.isBlocked ? 'unblock' : 'block'}" data-id="${u.id}" style="padding:6px 10px;font-size:12px;color:${u.isBlocked ? '#10b981' : '#f87171'}">${u.isBlocked ? 'Разблок' : 'Блок'}</button>
              </div>
            </div>`;
          }).join('') || '<p style="color:var(--mut)">Пользователей пока нет.</p>'}
        </div>
      </div>
      <div class="box">
        <h3 style="margin-top:0">История подписок и выдач</h3>
        ${(data.payments || []).length ? `<div style="display:flex;flex-direction:column;gap:6px;font-size:12px;">
          ${data.payments.map(p => `<div style="padding:8px 10px;border-radius:8px;background:rgba(255,255,255,.02);border:1px solid var(--line);">
            <b>@${esc(p.username)}</b> → <b>${esc(p.plan.toUpperCase())}</b> (${p.days > 0 ? p.days + ' дн.' : 'бессрочно'}) · ${p.amount} ${esc(p.currency)} · <i>${esc(p.provider)}</i> · ${fmtDate(p.createdAt)}
          </div>`).join('')}
        </div>` : '<p style="color:var(--mut);font-size:13px">Записей пока нет.</p>'}
      </div>`;
    $('#u-search').onclick = () => { uQuery = $('#u-q').value.trim(); tabUsers(el); };
    $('#u-reset-q').onclick = () => { uQuery = ''; tabUsers(el); };
    $('#u-q').onkeydown = e => { if (e.key === 'Enter') { uQuery = $('#u-q').value.trim(); tabUsers(el); } };
    $$('.u-act', el).forEach(btn => btn.onclick = async () => {
      const uid = +btn.dataset.id;
      const act = btn.dataset.act;
      const targetUser = (data.users || []).find(x => x.id === uid);
      const userLabel = targetUser ? '@' + targetUser.username : '#' + uid;
      const runAct = async () => {
        try {
          if (act === 'pro30') await post('admin/user/plan', { userId: uid, plan: 'pro', days: 30, note: 'Выдано в админке' });
          else if (act === 'pro365') await post('admin/user/plan', { userId: uid, plan: 'pro', days: 365, note: 'Выдано в админке' });
          else if (act === 'pro0') await post('admin/user/plan', { userId: uid, plan: 'pro', days: 0, note: 'Навсегда в админке' });
          else if (act === 'free') await post('admin/user/plan', { userId: uid, plan: 'free', days: 0, note: 'Сброс в админке' });
          else if (act === 'block' || act === 'unblock') await post('admin/user/block', { userId: uid, blocked: act === 'block' });
          else if (act === 'reset') {
            const res = await post('admin/user/reset-code', { userId: uid });
            alert('Одноразовый код сброса пароля (действует 24 часа):\n\n' + res.code);
          }
          toast('Готово ✓');
          tabUsers(el);
        } catch (e) {
          toast(e.message, 1);
        }
      };
      if (act === 'block') {
        confirmDangerous('Блокировка пользователя', `Заблокировать аккаунт ${userLabel}? Пользователь потеряет доступ к входу на сайт.`, runAct, 'Заблокировать');
        return;
      }
      if (act === 'unblock') {
        confirmDangerous('Разблокировка пользователя', `Снять блокировку с аккаунта ${userLabel}?`, runAct, 'Разблокировать');
        return;
      }
      if (act === 'free') {
        confirmDangerous('Перевод на Free', `Сбросить тариф пользователя ${userLabel} на бесплатный Free?`, runAct, 'Перевести на Free');
        return;
      }
      await runAct();
    });
  }

  // ---------- tab: yookassa payments & SBP ----------
  async function tabPayments(el) {
    el.innerHTML = `<div class="box"><p style="color:var(--mut)">Загрузка настроек ЮKassa...</p></div>`;
    let yk, uData;
    try {
      [yk, uData] = await Promise.all([
        api('admin/yookassa'),
        api('admin/users')
      ]);
    } catch (e) {
      el.innerHTML = `<div class="box"><p style="color:#ff8f8f">Ошибка: ${esc(e.message)}</p></div>`;
      return;
    }
    const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
    const payments = uData.payments || [];

    el.innerHTML = `
      <div class="box">
        <h2 style="margin-top:0">Настройки приёма платежей (ЮKassa / СБП)</h2>
        <p style="color:var(--mut);line-height:1.5;">
          Платёжный шлюз ЮKassa позволяет принимать оплату через <b>СБП (Система быстрых платежей)</b> по QR-коду и прямому переходу в банковские приложения (Сбер, Тинькофф, Альфа и др.), а также банковскими картами.
        </p>

        <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;margin:14px 0;cursor:pointer;">
          <input type="checkbox" id="yk-enabled" ${yk.enabled ? 'checked' : ''} style="width:18px;height:18px;accent-color:var(--acc);">
          <span>Включить приём платежей на сайте</span>
        </label>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:12px;margin-bottom:12px;">
          <label class="f">
            Идентификатор магазина (Shop ID)
            <input id="yk-shop" value="${esc(yk.shopId || '')}" placeholder="например: 345678" style="padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--txt);">
          </label>
          <label class="f">
            Секретный ключ (Secret Key)
            <div style="display:flex;gap:6px;">
              <input id="yk-key" type="password" placeholder="${yk.hasKey ? 'Сохранён (' + yk.keyHint + '), введите новый для смены' : 'live_... или test_...'}" style="flex:1;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--txt);">
              ${yk.hasKey ? `<button class="btn alt" id="yk-clr-key" style="padding:8px 12px;font-size:12px;">Стереть</button>` : ''}
            </div>
          </label>
        </div>

        <label style="display:flex;align-items:center;gap:10px;font-size:13px;color:var(--mut);margin-bottom:16px;cursor:pointer;">
          <input type="checkbox" id="yk-sbp-only" ${yk.sbpOnly ? 'checked' : ''} style="width:16px;height:16px;accent-color:var(--acc);">
          <span>Только СБП (QR-код и банковские приложения — мгновенная оплата)</span>
        </label>

        <div style="background:rgba(255,255,255,.02);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:16px;">
          <div style="font-weight:700;font-size:13px;margin-bottom:4px;">URL для Webhook (уведомления об оплате):</div>
          <div style="display:flex;gap:8px;align-items:center;">
            <input id="yk-webhook" readonly value="${esc(yk.webhookUrl)}" style="flex:1;font-family:monospace;font-size:12px;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:rgba(0,0,0,.3);color:var(--txt);">
            <button class="btn alt" id="yk-copy-wh" style="padding:8px 14px;font-size:12px;">Скопировать</button>
          </div>
          <div style="font-size:11.5px;color:var(--mut);margin-top:6px;line-height:1.4;">
            Укажите этот URL в личном кабинете ЮKassa в разделе <b>Интеграция → HTTP-уведомления</b> и отметьте событие <b>payment.succeeded</b>.
          </div>
        </div>

        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <button class="btn" id="yk-save" style="animation:none;">Сохранить настройки</button>
          <button class="btn alt" id="yk-test">⚡ Проверить соединение с ЮKassa</button>
        </div>
      </div>

      <div class="box">
        <h3 style="margin-top:0">Тарифные планы PRO</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;">
          <div style="padding:14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.02);">
            <div style="font-weight:800;font-size:16px;">1 месяц</div>
            <div style="font-size:22px;font-weight:900;color:var(--acc);margin:4px 0;">290 ₽</div>
            <div style="font-size:12px;color:var(--mut);">30 дней полного доступа ко всем программам</div>
          </div>
          <div style="padding:14px;border-radius:14px;border:1px solid var(--acc);background:rgba(var(--acr), .05);position:relative;">
            <span style="position:absolute;top:10px;right:10px;font-size:10px;padding:2px 8px;border-radius:99px;background:var(--acc);color:#000;font-weight:800;">ХИТ 🔥</span>
            <div style="font-weight:800;font-size:16px;">3 месяца</div>
            <div style="font-size:22px;font-weight:900;color:var(--acc);margin:4px 0;">690 ₽</div>
            <div style="font-size:12px;color:var(--mut);">90 дней (~230 ₽/мес, скидка 20%)</div>
          </div>
          <div style="padding:14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.02);position:relative;">
            <span style="position:absolute;top:10px;right:10px;font-size:10px;padding:2px 8px;border-radius:99px;background:rgba(255,255,255,.1);color:var(--txt);font-weight:800;">−57% ⚡</span>
            <div style="font-weight:800;font-size:16px;">1 год</div>
            <div style="font-size:22px;font-weight:900;color:var(--acc);margin:4px 0;">1 490 ₽</div>
            <div style="font-size:12px;color:var(--mut);">365 дней (~124 ₽/мес, максимальная выгода)</div>
          </div>
        </div>
      </div>

      <div class="box">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin:0">История платежей</h3>
          <button class="btn alt" id="yk-refresh" style="padding:6px 12px;font-size:12px;">Обновить</button>
        </div>
        ${payments.length ? `
        <div style="display:flex;flex-direction:column;gap:8px;">
          ${payments.map(p => {
            const isPaid = p.status === 'paid';
            const stColor = isPaid ? '#10b981' : (p.status === 'pending' ? '#f59e0b' : '#9ca3af');
            const stText = isPaid ? 'Оплачен ✓' : (p.status === 'pending' ? 'Ожидание' : p.status);
            return `
            <div style="padding:10px 14px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.02);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;">
              <div>
                <div style="font-weight:700;font-size:14px;">
                  @${esc(p.username)} <span style="font-size:12px;color:var(--mut);">· Тариф: ${esc(p.plan)} (${p.days ? p.days + ' дн.' : 'бессрочно'})</span>
                </div>
                <div style="font-size:12px;color:var(--mut);margin-top:2px;">
                  ${fmtDate(p.createdAt)} · Провайдер: <b>${esc(p.provider)}</b> ${p.note ? '· ' + esc(p.note) : ''}
                </div>
              </div>
              <div style="text-align:right;">
                <div style="font-weight:900;font-size:16px;color:var(--txt);">${p.amount} ${esc(p.currency)}</div>
                <div style="font-size:11px;font-weight:700;color:${stColor};margin-top:2px;">${stText}</div>
              </div>
            </div>`;
          }).join('')}
        </div>` : '<p style="color:var(--mut)">Платежей пока не зарегистрировано.</p>'}
      </div>
    `;

    $('#yk-copy-wh').onclick = () => {
      const input = $('#yk-webhook');
      input.select();
      navigator.clipboard.writeText(input.value).then(() => toast('URL скопирован в буфер ✓')).catch(() => toast('Скопируйте вручную', 1));
    };

    if ($('#yk-clr-key')) {
      $('#yk-clr-key').onclick = () => {
        confirmDangerous('Удаление ключа ЮKassa', 'Удалить сохранённый секретный ключ ЮKassa? Приём платежей перестанет работать до ввода нового ключа.', async () => {
          try {
            await post('admin/yookassa', { clearKey: true });
            toast('Ключ удалён');
            tabPayments(el);
          } catch (e) {
            toast(e.message, 1);
          }
        }, 'Удалить ключ');
      };
    }

    $('#yk-save').onclick = async () => {
      try {
        const body = {
          enabled: $('#yk-enabled').checked,
          shopId: $('#yk-shop').value.trim(),
          sbpOnly: $('#yk-sbp-only').checked
        };
        const k = $('#yk-key').value.trim();
        if (k) body.secretKey = k;
        await post('admin/yookassa', body);
        toast('Настройки ЮKassa сохранены ✓');
        tabPayments(el);
      } catch (e) {
        toast(e.message, 1);
      }
    };

    $('#yk-test').onclick = async () => {
      try {
        const btn = $('#yk-test');
        btn.disabled = true;
        btn.textContent = 'Проверка...';
        const k = $('#yk-key').value.trim();
        const s = $('#yk-shop').value.trim();
        await post('admin/yookassa/test', { shopId: s, secretKey: k });
        btn.disabled = false;
        btn.textContent = '⚡ Проверить соединение с ЮKassa';
        toast('Соединение с ЮKassa успешно проверено! ✓');
      } catch (e) {
        $('#yk-test').disabled = false;
        $('#yk-test').textContent = '⚡ Проверить соединение с ЮKassa';
        toast('Ошибка ЮKassa: ' + e.message, 1);
      }
    };

    $('#yk-refresh').onclick = () => tabPayments(el);
  }

  // ---------- tab: telegram bot ----------
  async function tabTelegram(el) {
    el.innerHTML = `<div class="box"><div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <div style="width:42px;height:42px;border-radius:50%;background:#229ED9;display:flex;align-items:center;justify-content:center;color:#fff;font-size:22px;box-shadow:0 6px 18px rgba(34,158,217,0.35);">✈️</div>
      <div>
        <h2 style="margin:0;font-size:18px;">Вход через Telegram (Бот)</h2>
        <div style="font-size:12.5px;color:var(--mut);">Мгновенная авторизация и регистрация пользователей без паролей</div>
      </div>
    </div>
    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--bdr);border-radius:12px;padding:14px;margin-bottom:16px;font-size:13px;line-height:1.5;color:var(--mut);">
      <b>Как настроить:</b><br>
      1. Откройте в Telegram бота <a href="https://t.me/BotFather" target="_blank" style="color:#38bdf8;text-decoration:none;">@BotFather</a>.<br>
      2. Отправьте команду <code>/newbot</code> и задайте имя и юзернейм (например, <i>MyFitBot</i>).<br>
      3. Скопируйте полученный <b>HTTP API Token</b> и вставьте в поле ниже.<br>
      4. Укажите юзернейм бота (без @) и нажмите <b>Сохранить</b>, затем <b>Проверить подключение</b>.
    </div>
    <div id="tg-form">Загрузка настроек...</div>
    </div>`;

    try {
      const cfg = await api('admin/telegram');
      const f = $('#tg-form');
      f.innerHTML = `
        <label class="f">Имя пользователя бота (Bot Username)
          <input id="tg-usr" placeholder="Например: RizzaFitBot" value="${esc(cfg.botUsername || '')}">
          <span style="font-size:11px;color:var(--mut)">Юзернейм бота в Telegram без символа @</span>
        </label>
        <label class="f">Токен бота (Bot Token из @BotFather)
          <input id="tg-tok" type="password" placeholder="${cfg.hasToken ? '••••••••••••••••••••••••••••••••' : 'Вставьте токен бота'}" value="">
          <span style="font-size:11px;color:var(--mut)">${cfg.hasToken ? 'Токен уже сохранён на сервере. Оставьте пустым, если не хотите менять.' : 'Формат: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ'}</span>
        </label>
        <label style="display:flex;align-items:center;gap:10px;margin:16px 0;cursor:pointer;">
          <input type="checkbox" id="tg-en" ${cfg.enabled !== false ? 'checked' : ''} style="width:18px;height:18px;accent-color:#229ED9;">
          <span style="font-size:14px;font-weight:600;">Включить вход через Telegram на сайте</span>
        </label>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;">
          <button class="btn" id="tg-save" style="animation:none">💾 Сохранить настройки</button>
          <button class="btn alt" id="tg-test" type="button">⚡ Проверить подключение бота</button>
        </div>
        <div id="tg-status" style="margin-top:16px;"></div>
      `;

      $('#tg-save').onclick = async () => {
        const u = $('#tg-usr').value.trim().replace(/^@/, '');
        const t = $('#tg-tok').value.trim();
        const en = $('#tg-en').checked;
        const payload = { botUsername: u, enabled: en };
        if (t) payload.botToken = t;
        try {
          await post('admin/telegram', payload);
          toast('Настройки Telegram сохранены ✓');
          tabTelegram(el);
        } catch (e) {
          toast(e.message, 1);
        }
      };

      $('#tg-test').onclick = async () => {
        const stat = $('#tg-status');
        stat.innerHTML = '<span style="color:var(--mut)">Проверка соединения с Telegram API...</span>';
        try {
          const res = await post('admin/telegram/test', {});
          if (res.ok && res.bot) {
            stat.innerHTML = `
              <div style="padding:12px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);border-radius:10px;color:#4ade80;font-size:13px;">
                ✓ <b>Бот успешно подключен!</b><br>
                Имя: <b>${esc(res.bot.first_name || '')}</b> (@${esc(res.bot.username || '')})<br>
                ID: ${res.bot.id} · Авторизация через Telegram работает.
              </div>
            `;
          } else {
            stat.innerHTML = `<div style="padding:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:10px;color:#f87171;font-size:13px;">✕ Ошибка: ${esc(res.error || 'Не удалось подключиться')}</div>`;
          }
        } catch (e) {
          stat.innerHTML = `<div style="padding:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:10px;color:#f87171;font-size:13px;">✕ Ошибка проверки: ${esc(e.message)}</div>`;
        }
      };

    } catch (e) {
      $('#tg-form').innerHTML = `<div style="color:#f87171">Ошибка загрузки: ${esc(e.message)}</div>`;
    }
  }

  // ---------- tab: reports ----------
  let repStatusFilter = 'all';
  let repSelectedId = null;
  async function tabReports(el) {
    el.innerHTML = `<div class="box"><h2 style="margin-top:0">🚩 Жалобы пользователей</h2>
      <div id="rep-filters" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;"></div>
      <div id="rep-list"><div style="color:var(--mut)">Загрузка жалоб…</div></div>
    </div>`;

    const statusMeta = {
      new: { label: 'Новая', bg: 'rgba(239,68,68,0.18)', color: '#f87171' },
      reviewed: { label: 'Рассмотрена', bg: 'rgba(245,158,11,0.18)', color: '#fbbf24' },
      closed: { label: 'Закрыта', bg: 'rgba(34,197,94,0.18)', color: '#4ade80' }
    };

    const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

    try {
      const data = await api('admin/reports?status=' + encodeURIComponent(repStatusFilter));
      const counts = data.counts || { all: 0, new: 0, reviewed: 0, closed: 0 };
      const reports = data.reports || [];

      const fWrap = $('#rep-filters');
      fWrap.innerHTML = [
        ['all', `Все (${counts.all || 0})`],
        ['new', `Новые (${counts.new || 0})`],
        ['reviewed', `Рассмотренные (${counts.reviewed || 0})`],
        ['closed', `Закрытые (${counts.closed || 0})`]
      ].map(([k, lbl]) => `<button type="button" class="btn ${repStatusFilter === k ? '' : 'alt'}" data-rep-filter="${k}" style="padding:7px 12px;font-size:12.5px;animation:none">${lbl}</button>`).join('');

      $$('[data-rep-filter]', fWrap).forEach(b => {
        b.onclick = () => {
          repStatusFilter = b.dataset.repFilter;
          repSelectedId = null;
          tabReports(el);
        };
      });

      const listEl = $('#rep-list');
      if (!reports.length) {
        listEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--mut);font-size:13px;">Жалоб в этой категории нет</div>`;
        return;
      }

      listEl.innerHTML = reports.map(r => {
        const sm = statusMeta[r.status] || statusMeta.new;
        const isOpen = repSelectedId === r.id;
        return `
          <div class="rep-card" data-rep-id="${r.id}" style="border:1px solid var(--bdr, rgba(255,255,255,0.1));border-radius:12px;padding:12px 14px;margin-bottom:10px;background:rgba(255,255,255,0.02);">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <span style="padding:3px 8px;border-radius:8px;font-size:11.5px;font-weight:700;background:${sm.bg};color:${sm.color};">${sm.label}</span>
                <b style="font-size:13px;">#${r.id}</b>
                <span style="font-size:12px;color:var(--mut);">${fmtDate(r.createdAt)}</span>
              </div>
              <button type="button" class="btn alt" data-rep-toggle="${r.id}" style="padding:5px 10px;font-size:12px;">${isOpen ? 'Скрыть' : 'Подробнее'}</button>
            </div>
            <div style="margin-top:8px;font-size:13px;display:flex;gap:16px;flex-wrap:wrap;">
              <span>Автор: <b>${esc(r.reporter.displayName)}</b> <span style="color:var(--mut)">@${esc(r.reporter.username)}</span></span>
              <span>На кого: <b>${esc(r.target.displayName)}</b> <span style="color:var(--mut)">@${esc(r.target.username)}</span>${r.target.isBlocked ? ' <span style="color:#f87171;font-size:11px;">(заблокирован)</span>' : ''}</span>
            </div>
            <div style="margin-top:6px;font-size:13px;color:var(--tx);word-break:break-word;"><b>Причина:</b> ${esc(r.reason)}</div>
            ${isOpen ? `
              <div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.08);font-size:12.5px;">
                ${r.messageId ? `<div style="margin-bottom:8px;padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);"><b>Сообщение #${r.messageId}:</b> ${esc(r.messageText || '(удалено или недоступно)')}</div>` : ''}
                ${r.reviewedAt ? `<div style="margin-bottom:8px;color:var(--mut);">Обработано: ${fmtDate(r.reviewedAt)}</div>` : ''}
                <label class="f" style="margin-bottom:10px;">Заметка администратора
                  <input type="text" data-rep-note="${r.id}" value="${esc(r.adminNote || '')}" placeholder="Комментарий модератора (необязательно)">
                </label>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                  <button type="button" class="btn" data-rep-set="${r.id}" data-rep-st="reviewed" style="padding:7px 12px;font-size:12px;animation:none">✓ Пометить рассмотренной</button>
                  <button type="button" class="btn alt" data-rep-set="${r.id}" data-rep-st="closed" style="padding:7px 12px;font-size:12px;">✕ Закрыть жалобу</button>
                  ${r.status !== 'new' ? `<button type="button" class="btn alt" data-rep-set="${r.id}" data-rep-st="new" style="padding:7px 12px;font-size:12px;">↺ Вернуть в новые</button>` : ''}
                </div>
              </div>
            ` : ''}
          </div>`;
      }).join('');

      $$('[data-rep-toggle]', listEl).forEach(b => {
        b.onclick = () => {
          const rid = Number(b.dataset.repToggle);
          repSelectedId = (repSelectedId === rid) ? null : rid;
          tabReports(el);
        };
      });

      $$('[data-rep-set]', listEl).forEach(b => {
        b.onclick = async () => {
          const rid = Number(b.dataset.repSet);
          const st = b.dataset.repSt;
          const noteInp = listEl.querySelector(`[data-rep-note="${rid}"]`);
          const note = noteInp ? noteInp.value.trim() : '';
          b.disabled = true;
          try {
            await post('admin/reports/status', { reportId: rid, status: st, note });
            toast('Статус жалобы обновлён ✓');
            tabReports(el);
          } catch (e) {
            toast(e.message, 1);
            b.disabled = false;
          }
        };
      });
    } catch (e) {
      $('#rep-list').innerHTML = `<div style="color:#f87171">Ошибка загрузки: ${esc(e.message)}</div>`;
    }
  }

  // ---------- tab: settings ----------
  function tabSettings(el) {
    el.innerHTML = `<div class="box"><h2 style="margin-top:0">Сменить пароль админки</h2>
      <label class="f">Новый пароль (минимум 6 символов)<input id="np" type="password"></label>
      <button class="btn" id="npb" style="animation:none">Сменить пароль</button></div>
    <div class="box"><h2 style="margin-top:0">Данные</h2><p style="color:var(--mut)">Все правки хранятся в папке <b>site/content</b> (config.json, overrides.json, uploads/). Скопируйте её, чтобы сделать резервную копию.</p>
      <button class="btn alt" id="dl">⬇ Скачать правки (JSON)</button></div>`;
    $('#npb').onclick = () => {
      const pw = $('#np').value;
      if (!pw || pw.length < 6) {
        toast('Пароль должен быть не короче 6 символов', 1);
        return;
      }
      confirmDangerous('Смена пароля админки', 'Изменить пароль администратора? После смены текущие сессии администратора будут завершены.', async () => {
        try {
          await post('password', { password: pw });
          toast('Пароль изменён ✓');
          $('#np').value = '';
        } catch (e) {
          toast(e.message, 1);
        }
      }, 'Сменить пароль');
    };
    $('#dl').onclick = () => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([JSON.stringify({ config: CFG, overrides: OV }, null, 1)], { type: 'application/json' }));
      a.download = 'flexa-content.json';
      a.click();
    };
  }

  if (token) start(); else showLogin();
})();
