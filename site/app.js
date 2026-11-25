(async function () {
  const app = document.getElementById('app');
  const nc = u => fetch(u + '?v=' + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null);
  const [D, CFG0, OV0] = await Promise.all([fetch('data.json').then(r => r.json()), nc('content/config.json'), nc('content/overrides.json')]);
  const CFG = Object.assign({ brand: 'RizzaFit', accent: '#F0A830', logo: '', heroProgram: 2, goal: 5, hidden: [], sections: {}, t: {}, ptitle: {}, athlete: {} }, CFG0 || {});
  let L = localStorage.lang || 'ru';
  const [COACH, PAY_CFG] = await Promise.all([
    fetch('/api/coach/status').then(r => r.ok ? r.json() : { enabled: false }).catch(() => ({ enabled: false })),
    fetch('api/payment/plans').then(r => r.ok ? r.json() : { enabled: false, freeAccessMode: false }).catch(() => ({ enabled: false, freeAccessMode: false }))
  ]);
  const T = window.TEXTS;
    const t = k => ((CFG.t[L] || {})[k] || T[L][k] || k);
  const ui = k => D.ui[L][k] || D.ui.en[k] || k;
  // ---- content overrides (managed in the admin panel) ----
  const OV = Object.assign({ w: {}, p: {}, c: [], e: {} }, OV0 || {});
  OV.e = OV.e || {};
  OV.c.forEach(w => D.workouts.unshift(w));
  Object.entries(OV.w).forEach(([id, o]) => { const w = D.workouts.find(x => x.id == id); if (w) Object.assign(w, o); });
  Object.entries(OV.p).forEach(([id, o]) => { const p = D.programs.find(x => x.id == id); if (p) { Object.assign(p, o); if (o.image) p.img = true; } });
  Object.entries(OV.e).forEach(([id, o]) => { const e = D.exercises.find(x => x.id == id); if (e) Object.assign(e, o); });
  const pImg = p => p.image || `img/programs/${p.id}.jpg`;
  const ACCENT_THEMES = [
    { id: 'amber', hex: '#F0A830', ru: 'Янтарь', en: 'Amber' },
    { id: 'teal', hex: '#2DD4BF', ru: 'Неон', en: 'Teal' },
    { id: 'blue', hex: '#38BDF8', ru: 'Небо', en: 'Blue' },
    { id: 'violet', hex: '#A78BFA', ru: 'Аметист', en: 'Violet' },
    { id: 'mono', hex: '#E2E8F0', ru: 'Моно', en: 'Mono' }
  ];
  function applyAccent(customHex) {
    const raw = customHex || localStorage.accentTheme || CFG.accent || '#F0A830';
    const hex = /^#[0-9a-f]{6}$/i.test(raw) ? raw : '#F0A830';
    const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const mix = k => [r, g, b].map(v => Math.round(v + (k > 0 ? (255 - v) : v) * Math.abs(k))).join(',');
    const st = document.documentElement.style;
    st.setProperty('--ac', hex); st.setProperty('--acr', `${r},${g},${b}`);
    st.setProperty('--ac-l', `rgb(${mix(.35)})`); st.setProperty('--ac-d', `rgb(${mix(-.25)})`);
    return hex;
  }
  // ---- brand / theme ----
  (function theme() {
    applyAccent();
    const st = document.documentElement.style;
    const logo = CFG.logo || 'img/logo.svg';
    st.setProperty('--logo', `url(${logo})`);
    document.title = CFG.brand + ' — ' + (L == 'ru' ? 'тренировки и программы' : 'workouts & programs');
    document.querySelector('link[rel=icon]').href = logo;
    const bImg = document.querySelector('.brand img');
    if (bImg) bImg.src = logo;
    const nm = CFG.brand || 'RizzaFit';
    const bName = document.querySelector('.brand-name') || document.querySelector('.brand span');
    if (bName) bName.innerHTML = nm.length > 1 ? esc0(nm.slice(0, -1)) + '<em>' + esc0(nm.slice(-1)) + '</em>' : esc0(nm);
    if (!COACH.enabled) (CFG.hidden = (CFG.hidden || []).concat('coach'));
    const topCoachBtn = document.getElementById('top-coach-btn');
    if (topCoachBtn) topCoachBtn.style.display = (COACH.enabled && !(CFG.hidden || []).includes('coach')) ? '' : 'none';
    (CFG.hidden || []).forEach(k => { const a = document.querySelector(`#nav a[data-k=${k}]`); if (a) a.style.display = 'none'; });
    const ft = document.querySelector('footer');
    if (ft) ft.textContent = '© ' + nm + ' · ' + ((CFG.t[L] || {}).footer || T[L].footer);
    function esc0(s) { return s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  })();
  function isLoggedIn() {
    return !!(localStorage.userToken && localStorage.userName);
  }

  function syncNavAthlete() {
    const avBox = document.getElementById('nav-ath-av');
    const usersBtn = document.getElementById('nav-users-btn');
    const msgBtn = document.getElementById('nav-messages-btn');
    const msgBadge = document.getElementById('nav-msg-badge');
    const logged = isLoggedIn();

    if (usersBtn) usersBtn.classList.toggle('hidden', !logged);
    if (msgBtn) msgBtn.classList.toggle('hidden', !logged);
    if (!logged && msgBadge) msgBadge.classList.add('hidden');

    if (!avBox) return;
    if (!logged) {
      avBox.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8.5" r="3.5"/><path d="M5.5 19.5c1.4-3.1 3.8-4.5 6.5-4.5s5.1 1.4 6.5 4.5"/></svg>`;
      return;
    }
    let loc = {};
    try { loc = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
    const avUrl = loc.avatar || localStorage.userAvatar || '';
    const uName = localStorage.userName || loc.name || 'A';
    if (avUrl) {
      avBox.innerHTML = `<img src="${esc(avUrl)}" alt="">`;
    } else {
      avBox.innerHTML = `<span class="nav-init">${esc(uName.charAt(0).toUpperCase())}</span>`;
    }
  }
  const exMap = {}; D.exercises.forEach(e => exMap[e.id] = e);
  const woMap = {}; D.workouts.forEach(w => woMap[w.id] = w);
  function getCustomWorkouts() {
    try {
      const arr = JSON.parse(localStorage.customWorkouts || '[]');
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function saveCustomWorkouts(arr) {
    localStorage.customWorkouts = JSON.stringify(arr || []);
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
  }
  function registerCustomWorkouts() {
    getCustomWorkouts().slice().reverse().forEach(cw => {
      cw._custom = true;
      woMap[cw.id] = cw;
      if (!D.workouts.some(x => x.id === cw.id)) D.workouts.unshift(cw);
    });
  }
  registerCustomWorkouts();
  function upsertCustomWorkout(cw) {
    cw._custom = true;
    delete cw._woTxt;
    const list = getCustomWorkouts().filter(x => x.id !== cw.id);
    list.unshift(cw);
    saveCustomWorkouts(list);
    const idx = D.workouts.findIndex(x => x.id === cw.id);
    if (idx >= 0) D.workouts[idx] = cw;
    else D.workouts.unshift(cw);
    woMap[cw.id] = cw;
  }
  function removeCustomWorkout(id) {
    saveCustomWorkouts(getCustomWorkouts().filter(x => x.id !== id));
    const idx = D.workouts.findIndex(x => x.id === id);
    if (idx >= 0) D.workouts.splice(idx, 1);
    delete woMap[id];
  }

  const PROG_WORKOUT_IDS = new Set();
  (D.programs || []).forEach(p => {
    ['ru', 'en'].forEach(lang => {
      const text = (p.d && p.d[lang]) || '';
      const m = text.match(/workout-(\d+)/g);
      if (m) m.forEach(x => PROG_WORKOUT_IDS.add(x.replace('workout-', '')));
    });
  });

  function isUserPro() {
    if (PAY_CFG && PAY_CFG.freeAccessMode) return true;
    if (localStorage.userIsPro !== '1') return false;
    const exp = +(localStorage.userPlanExp || 0);
    if (exp > 0 && Math.floor(Date.now() / 1000) > exp) {
      localStorage.userIsPro = '0';
      return false;
    }
    return true;
  }

  function isProWorkout(w) {
    if (!w) return false;
    if (w._custom) return false;
    if (w.pro) return true;
    if (PROG_WORKOUT_IDS.has(String(w.id))) return true;
    return false;
  }

  function splitProgramDesc(rawText) {
    const parts = (rawText || '').split(/\n\s*\n/);
    if (parts.length >= 2) {
      return { teaser: parts.slice(0, 2).join('\n\n'), rest: parts.slice(2).join('\n\n') };
    }
    const idx = (rawText || '').indexOf('\n', 300);
    if (idx > 0 && idx < 600) {
      return { teaser: rawText.slice(0, idx), rest: rawText.slice(idx) };
    }
    return { teaser: (rawText || '').slice(0, 300) + '...', rest: rawText || '' };
  }

  const exName = e => e.n[L] || e.n.en || e.n.ru || ('#' + e.id);
  const woName = w => w.t[L] || w.t.en || w.t.ru || (t('untitled') + ' #' + w.id);
  const pName = p => p.t[L] || p.t.en;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function uiSvg(name, sz = 14) {
    const p = {
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      chart: '<path d="M4 19h16"/><path d="M7 15v-4"/><path d="M12 15V7"/><path d="M17 15v-6"/>',
      bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/>',
      flame: '<path d="M12 2c1.5 3.2 5 5.2 5 9.2a5 5 0 1 1-10 0c0-2.1 1-4 2.5-5.5.2 1.6 1 2.5 2 2.8-.2-2 .2-4.3.5-6.5z"/>',
      trophy: '<path d="M8 21h8M12 17v4"/><path d="M7 4h10v6a5 5 0 0 1-10 0V4z"/><path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/>',
      edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>',
      trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
      heart: '<path d="M20.4 4.6a5.4 5.4 0 0 0-7.6 0L12 5.4l-.8-.8a5.4 5.4 0 0 0-7.6 7.6l.8.8L12 20.5l7.6-7.5.8-.8a5.4 5.4 0 0 0 0-7.6z"/>',
      heartFill: '<path fill="currentColor" d="M20.4 4.6a5.4 5.4 0 0 0-7.6 0L12 5.4l-.8-.8a5.4 5.4 0 0 0-7.6 7.6l.8.8L12 20.5l7.6-7.5.8-.8a5.4 5.4 0 0 0 0-7.6z"/>',
      play: '<polygon fill="currentColor" points="6 4 20 12 6 20 6 4"/>',
      pin: '<path d="M12 17v5"/><path d="M9 4h6l-1 6 3 3v2H7v-2l3-3-1-6z"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      trend: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
      dumbbell: '<path d="M6.5 6.5v11M17.5 6.5v11M3 9v6M21 9v6M6.5 12h11"/>',
      sparkles: '<path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"/>',
      download: '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M4 19h16"/>',
      upload: '<path d="M12 15V3"/><path d="M7 8l5-5 5 5"/><path d="M4 19h16"/>',
      scale: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 10a4 4 0 0 1 8 0"/><path d="M12 10l2-2"/>',
      check: '<path d="M5 13l4 4L19 7"/>',
      swords: '<path d="M14.5 17.5L3 6V3h3l11.5 11.5M13 19l2 2 4-4-2-2M9.5 6.5L6.5 9.5M9.5 17.5L21 6V3h-3L6.5 14.5M11 19l-2 2-4-4 2-2M14.5 6.5L17.5 9.5"/>',
      handshake: '<path d="M11 15h2l3 3H8l3-3z"/><path d="M18 11l-4-4-4 4-2-2 4-4 4 4 4 4z"/><path d="M2 11l4-4 3 3"/><path d="M22 11l-4-4-3 3"/>',
      repeat: '<path d="M17 1l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
      settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
      snowflake: '<path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M19.07 4.93L4.93 19.07"/>',
      bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
      users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
      user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
      video: '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>',
      image: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>'
    };
    return `<svg class="ui-ic" width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p[name] || ''}</svg>`;
  }
  const hist = () => {
    try {
      const arr = JSON.parse(localStorage.hist || '[]');
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  };
  const calc1RM = (w, r) => (w > 0 ? (r <= 1 ? w : Math.round(w * (1 + r / 30))) : 0);
  function loadExLogs() {
    try { return JSON.parse(localStorage.exLogs || '{}') || {}; } catch (e) { return {}; }
  }
  function getExLog(exId) {
    return loadExLogs()[String(exId)] || null;
  }
  function saveExLog(exId, w, r) {
    const logs = loadExLogs();
    const key = String(exId);
    const prev = logs[key] || null;
    const est = calc1RM(w, r);
    const prevBestW = prev ? (prev.bestW || 0) : 0;
    const prevBest1RM = prev ? (prev.best1RM || 0) : 0;
    const isWeightPr = Boolean(prev && w > 0 && (w > prevBestW || est > prevBest1RM));
    logs[key] = {
      w,
      r,
      bestW: Math.max(prevBestW, w),
      best1RM: Math.max(prevBest1RM, est),
      t: Date.now()
    };
    localStorage.exLogs = JSON.stringify(logs);
    return { isWeightPr, bestW: logs[key].bestW, best1RM: logs[key].best1RM };
  }
  const vib = p => { try { if (navigator.vibrate) navigator.vibrate(p); } catch (e) {} };
  function loadAudioCfg() {
    let raw = {};
    try { raw = JSON.parse(localStorage.audioCfg || '{}'); } catch (e) {}
    const muted = raw.muted !== undefined ? !!raw.muted : (localStorage.audioMuted === 'true');
    return {
      muted,
      sfx: raw.sfx !== false,
      voice: raw.voice !== false,
      vol: typeof raw.vol === 'number' ? Math.max(0.1, Math.min(1, raw.vol)) : 0.85
    };
  }
  let AUD = loadAudioCfg();
  const audioIcon = () => {
    if (AUD.muted || (!AUD.sfx && !AUD.voice)) {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M21 9l-5 6M16 9l5 6"/></svg>';
    }
    if (AUD.sfx && !AUD.voice) {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8.5-3 8.5h18s-3-1.5-3-8.5"/><path d="M10.3 20a2 2 0 0 0 3.4 0"/></svg>';
    }
    if (!AUD.sfx && AUD.voice) {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.8 5.8a9 9 0 0 1 0 12.4"/></svg>';
  };
  function syncSndBtn() {
    const ic = audioIcon();
    const isMuted = !!(AUD.muted || (!AUD.sfx && !AUD.voice));
    const lbl = isMuted ? (L == 'ru' ? 'Звук выкл.' : 'Sound muted') : (L == 'ru' ? 'Настройки звука' : 'Audio settings');
    const b1 = document.getElementById('snd-btn');
    if (b1) {
      b1.innerHTML = ic;
      b1.classList.toggle('is-muted', isMuted);
      b1.title = lbl;
      b1.setAttribute('aria-label', lbl);
    }
    const b2 = document.getElementById('p-snd');
    if (b2) {
      b2.innerHTML = ic;
      b2.classList.toggle('is-muted', isMuted);
      b2.title = lbl;
    }
  }
  function saveAudioCfg(next) {
    AUD = Object.assign({}, AUD, next || {});
    localStorage.audioCfg = JSON.stringify(AUD);
    localStorage.audioMuted = String(!!AUD.muted || (!AUD.sfx && !AUD.voice));
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
    if (AUD.muted || !AUD.voice) stopSpeech();
    syncSndBtn();
  }

  let audioCtx = null;
  const audioCache = {};
  function getAudioCtx() {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    }
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
    return audioCtx;
  }
  function unlockAudio() {
    getAudioCtx();
    ['mp3_box_bell.mp3', 'mp3_workout_completed.mp3'].forEach(n => {
      if (!audioCache[n]) {
        const a = new Audio('audio/' + n);
        a.preload = 'auto';
        audioCache[n] = a;
      }
    });
  }
  document.addEventListener('pointerdown', unlockAudio, { once: true, passive: true });

  function playTone(freq = 660, duration = 0.14, type = 'sine', delay = 0, volScale = 1) {
    if (AUD.muted || !AUD.sfx) return;
    try {
      const ctx = getAudioCtx();
      if (!ctx) return;
      const t0 = ctx.currentTime + delay;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, t0);
      const peak = Math.max(0.01, Math.min(0.45, 0.22 * AUD.vol * volScale));
      gain.gain.setValueAtTime(0.001, t0);
      gain.gain.linearRampToValueAtTime(peak, t0 + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0008, t0 + duration);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(t0); osc.stop(t0 + duration + 0.02);
    } catch (e) {}
  }

  function beep(freq = 660, duration = 0.15) {
    playTone(freq, duration, 'sine', 0, 1);
  }

  const snd = n => {
    if (AUD.muted || !AUD.sfx) return;
    try {
      const a = audioCache[n] || new Audio('audio/' + n);
      audioCache[n] = a;
      a.pause();
      a.currentTime = 0;
      a.volume = AUD.vol;
      a.play().catch(() => playTone(n.includes('completed') ? 784 : 660, 0.22));
    } catch (e) {
      playTone(660, 0.2);
    }
  };

  function sfx(kind) {
    if (AUD.muted || !AUD.sfx) return;
    if (kind === 'tick') return playTone(880, 0.075, 'sine', 0, 0.85);
    if (kind === 'step') return playTone(520, 0.045, 'triangle', 0, 0.45);
    if (kind === 'done') {
      playTone(523.25, 0.11, 'triangle', 0, 0.85);
      playTone(659.25, 0.16, 'triangle', 0.08, 0.9);
      return;
    }
    if (kind === 'half') {
      playTone(659.25, 0.1, 'sine', 0, 0.75);
      playTone(880, 0.14, 'sine', 0.1, 0.75);
      return;
    }
    if (kind === 'pr') {
      [523.25, 659.25, 783.99, 1046.5].forEach((f, idx) => playTone(f, 0.18, 'triangle', idx * 0.07, 1));
      return;
    }
    if (kind === 'bell') return snd('mp3_box_bell.mp3');
    if (kind === 'finish') return snd('mp3_workout_completed.mp3');
  }

  function stopSpeech() {
    try {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    } catch (e) {}
  }

  function speak(phrase, opts) {
    if (AUD.muted || !AUD.voice || !phrase) return;
    const o = opts || {};
    try {
      if ('speechSynthesis' in window) {
        if (!o.queue) window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(phrase);
        const want = L == 'ru' ? 'ru' : 'en';
        const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
        const match = voices.find(v => (v.lang || '').toLowerCase().startsWith(want));
        if (match) u.voice = match;
        u.lang = L == 'ru' ? 'ru-RU' : 'en-US';
        u.rate = o.rate || 1.04;
        u.volume = AUD.vol;
        window.speechSynthesis.speak(u);
      }
    } catch (e) {}
  }

  function openAudioModal(onClose) {
    unlockAudio();
    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';
    bd.style.zIndex = '100005';
    const closeM = () => { bd.remove(); if (typeof onClose === 'function') onClose(); };
    const renderM = () => {
      const isOff = AUD.muted || (!AUD.sfx && !AUD.voice);
      const pct = Math.round(AUD.vol * 100);
      bd.innerHTML = `<div class="ap-modal aud-modal">
        <div class="ap-notif-head">
          <h3 style="display:flex;align-items:center;gap:8px;">${uiSvg('bolt', 16)} ${L == 'ru' ? 'Настройки звука' : 'Sound Settings'}</h3>
          <button type="button" class="fr-btn-del" id="aud-x">✕</button>
        </div>
        <button type="button" class="aud-master ${isOff ? 'off' : 'on'}" id="aud-master">
          <span style="display:flex;align-items:center;justify-content:center;">${uiSvg(isOff ? 'bell' : 'bolt', 20)}</span>
          <b>${isOff ? (L == 'ru' ? 'Звук выключен — нажмите чтобы включить' : 'Sound muted — tap to enable') : (L == 'ru' ? 'Звук включён' : 'Sound enabled')}</b>
        </button>
        <div class="aud-grid">
          <button type="button" class="aud-tile ${!AUD.muted && AUD.sfx ? 'on' : ''}" id="aud-sfx">
            <span style="display:flex;align-items:center;justify-content:center;">${uiSvg('bell', 20)}</span>
            <b>${L == 'ru' ? 'Сигналы и гонг' : 'Timers & Bells'}</b>
            <small>${!AUD.muted && AUD.sfx ? (L == 'ru' ? 'Вкл' : 'On') : (L == 'ru' ? 'Выкл' : 'Off')}</small>
          </button>
          <button type="button" class="aud-tile ${!AUD.muted && AUD.voice ? 'on' : ''}" id="aud-voice">
            <span style="display:flex;align-items:center;justify-content:center;">${uiSvg('settings', 20)}</span>
            <b>${L == 'ru' ? 'Голосовой тренер' : 'Voice Coach'}</b>
            <small>${!AUD.muted && AUD.voice ? (L == 'ru' ? 'Вкл' : 'On') : (L == 'ru' ? 'Выкл' : 'Off')}</small>
          </button>
        </div>
        <div class="aud-vol-box">
          <div class="aud-vol-head">
            <span>${L == 'ru' ? 'Громкость' : 'Volume'}</span>
            <b id="aud-vol-lbl">${pct}%</b>
          </div>
          <input type="range" id="aud-vol" min="10" max="100" step="5" value="${pct}">
        </div>
        <div style="display:flex;gap:8px;margin-top:14px;">
          <button type="button" class="btn alt" style="flex:1;padding:10px;font-size:13px;" id="aud-test">▶ ${L == 'ru' ? 'Проверить' : 'Test'}</button>
          <button type="button" class="btn" style="flex:1;padding:10px;font-size:13px;" id="aud-ok">${L == 'ru' ? 'Готово' : 'Done'}</button>
        </div>
      </div>`;

      bd.onclick = ev => { if (ev.target === bd) closeM(); };
      bd.querySelector('#aud-x').onclick = () => { vib(20); closeM(); };
      bd.querySelector('#aud-ok').onclick = () => { vib(20); closeM(); };
      bd.querySelector('#aud-master').onclick = () => {
        vib(25);
        if (isOff) {
          saveAudioCfg({ muted: false, sfx: (!AUD.sfx && !AUD.voice) ? true : AUD.sfx, voice: (!AUD.sfx && !AUD.voice) ? true : AUD.voice });
        } else {
          saveAudioCfg({ muted: true });
        }
        renderM();
      };
      bd.querySelector('#aud-sfx').onclick = () => {
        vib(20);
        const nextSfx = AUD.muted ? true : !AUD.sfx;
        saveAudioCfg({ muted: false, sfx: nextSfx });
        if (nextSfx) sfx('done');
        renderM();
      };
      bd.querySelector('#aud-voice').onclick = () => {
        vib(20);
        const nextVoice = AUD.muted ? true : !AUD.voice;
        saveAudioCfg({ muted: false, voice: nextVoice });
        renderM();
      };
      const volEl = bd.querySelector('#aud-vol');
      volEl.oninput = () => {
        const val = Number(volEl.value) / 100;
        bd.querySelector('#aud-vol-lbl').textContent = Math.round(val * 100) + '%';
        saveAudioCfg({ vol: val, muted: false });
      };
      bd.querySelector('#aud-test').onclick = () => {
        vib(25);
        unlockAudio();
        if (AUD.muted) saveAudioCfg({ muted: false });
        if (!AUD.sfx && !AUD.voice) saveAudioCfg({ sfx: true, voice: true });
        if (AUD.sfx) sfx('done');
        if (AUD.voice) speak(L == 'ru' ? 'Звук настроен! Отличной тренировки!' : 'Sound is ready! Have a great workout!');
        renderM();
      };
    };
    document.body.appendChild(bd);
    renderM();
  }

  const sndBtn = document.getElementById('snd-btn');
  if (sndBtn) {
    syncSndBtn();
    sndBtn.onclick = () => { vib(25); openAudioModal(); };
  }
  let wakeLock = null;
  async function requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
        wakeLock.addEventListener('release', () => { wakeLock = null; });
      }
    } catch (e) {}
  }
  function releaseWakeLock() {
    if (wakeLock) {
      try { wakeLock.release(); } catch (e) {}
      wakeLock = null;
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.body.classList.contains('player-open') && document.visibilityState === 'visible') {
      requestWakeLock();
    }
  });
  const WARMUP_WORKOUT = {
    id: 'warmup',
    t: { ru: 'Разминка перед тренировкой', en: 'Dynamic Warm-Up' },
    d: {
      ru: '3-минутный динамический комплекс для разогрева суставов, связок и подготовки сердечно-сосудистой системы к основной нагрузке.',
      en: '3-minute dynamic warm-up to prepare joints, muscles and cardiovascular system for your workout.'
    },
    diff: 'easy',
    temp: 'moderate',
    rb: 10,
    rr: 15,
    s: [
      [1,
        [81, 'second', 30, 10], // Jumping jacks 30s
        [82, 'second', 30, 10], // High Knee Jog 30s
        [85, 'second', 30, 10], // Squats 30s
        [90, 'second', 30, 10], // Lunges 30s
        [53, 'second', 30, 0]   // Plank 30s
      ]
    ]
  };
  const getFavs = () => new Set(JSON.parse(localStorage.favs || '[]'));
  const toggleFav = id => {
    const f = getFavs();
    if (f.has(id)) f.delete(id); else f.add(id);
    localStorage.favs = JSON.stringify([...f]);
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
    vib(35);
    return f.has(id);
  };
  function calcStreak(list) {
    if (window.AthleteProfile && window.AthleteProfile.calcStreakSimple) {
      return window.AthleteProfile.calcStreakSimple(list);
    }
    if (!list || !list.length) return 0;
    const dates = new Set(list.map(x => new Date(x.t).toISOString().slice(0, 10)));
    let s = 0, d = new Date();
    if (!dates.has(d.toISOString().slice(0, 10))) d.setDate(d.getDate() - 1);
    while (dates.has(d.toISOString().slice(0, 10))) {
      s++;
      d.setDate(d.getDate() - 1);
    }
    return s;
  }

  function getProgState() {
    let raw = {};
    try { raw = JSON.parse(localStorage.athletePrograms || localStorage.progState || '{}'); } catch (e) {}
    return {
      activeId: raw.activeId || null,
      logs: raw.logs && typeof raw.logs === 'object' ? raw.logs : {}
    };
  }
  function saveProgState(st) {
    localStorage.athletePrograms = JSON.stringify({ activeId: st.activeId || null, logs: st.logs || {} });
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
  }
  const eqLbl = v => ui('wft_eq_' + v) === 'wft_eq_' + v ? v : ui('wft_eq_' + v);
  const lvlLbl = v => t(v) === v ? v : t(v);
  const diffLbl = v => ui('wt_difficulty_' + v);
  const tempLbl = v => ui('wt_temp_' + v);
  const exImg = (e, c) => e.img ? `<img src="img/ex/svg_norm_${e.id}.svg" alt="">` : '';

  const getExVideo = e => {
    if (!e) return null;
    return e.video || null;
  };

  const renderExVisual = (e, options = {}) => {
    if (!e) return uiSvg('dumbbell', 28);
    const vid = getExVideo(e);
    const preferVideo = localStorage.getItem('flexa_view_mode') !== 'schema';
    const hasVideo = !!vid;

    if (hasVideo && (options.forceVideo || preferVideo)) {
      return `
        <div class="ex-visual-wrap video-active" data-id="${e.id}">
          <video class="ex-video-elem" src="${vid}" autoplay loop muted playsinline poster="${e.img ? `img/ex/svg_norm_${e.id}.svg` : ''}"></video>
          ${options.allowToggle ? `
            <div class="ex-visual-switcher">
              <button class="visual-toggle-btn active" data-mode="video" title="${L == 'ru' ? '3D Видео' : '3D Video'}">${uiSvg('video', 13)} 3D</button>
              <button class="visual-toggle-btn" data-mode="schema" title="${L == 'ru' ? 'Схема' : 'Schema'}">${uiSvg('image', 13)}</button>
            </div>` : ''}
        </div>`;
    }

    return `
      <div class="ex-visual-wrap schema-active" data-id="${e.id}">
        ${e.img ? `<img class="ex-img-elem" src="img/ex/svg_norm_${e.id}.svg" alt="">` : uiSvg('dumbbell', 28)}
        ${hasVideo && options.allowToggle ? `
          <div class="ex-visual-switcher">
            <button class="visual-toggle-btn" data-mode="video" title="${L == 'ru' ? '3D Видео' : '3D Video'}">${uiSvg('video', 13)} 3D</button>
            <button class="visual-toggle-btn active" data-mode="schema" title="${L == 'ru' ? 'Схема' : 'Schema'}">${uiSvg('image', 13)}</button>
          </div>` : ''}
      </div>`;
  };

  function richDesc(s, options = {}) {
    s = s || '';
    if (options && options.lockWorkouts) {
      s = s.replace(/<a\s+href=['"]workout-(\d+)['"][^>]*>(.*?)<\/a>/gi, (m, id, text) => `<a href="#/workouts/programs" class="prog-locked-link" data-woid="${id}">${uiSvg('bolt', 12)} ${text}</a>`);
    }
    // links like exercise-34 / workout-1456 / program-3
    s = s.replace(/<a\s+href=['"](exercise|workout|program)-(\d+)['"][^>]*>/g, (m, k, id) => `<a href="#/${k}/${id}">`);
    // plain text (workout descs) may contain no tags: keep newlines via CSS
    return s;
  }

  const MUSCLE_RULES = {
    chest: /груд|отжим|жим лежа|chest|push.?up|dips|брусь|fly|сведен/i,
    back: /спин|подтягив|тяг|гиперэкстенз|back|pull.?up|chin.?up|row|lat|pulldown|deadlift/i,
    abs: /пресс|живот|кор|планк|скручив|скруч|abs|core|plank|crunch|sit.?up|mountain/i,
    arms: /рук|бицеп|трицеп|молот|француз|arm|bicep|tricep|curl|extension/i,
    shoulders: /плеч|дельт|армейск|махи|shoulder|pike|handstand|delt|overhead/i,
    legs: /ног|присед|выпад|ягодиц|бедр|икр|мост|leg|squat|lunge|glute|calf|hip/i
  };
  const CARDIO_RX = /берпи|прыж|джамп|бег|скакал|кардио|burpee|jump|jack|sprint|skip|high knee/i;

  function detectMuscles(text) {
    const m = {};
    Object.keys(MUSCLE_RULES).forEach(k => { m[k] = MUSCLE_RULES[k].test(text); });
    return m;
  }

  function exCleanName(e) {
    if (!e || !e.n) return '';
    return ((e.n.ru || '') + ' ' + (e.n.en || '')).replace(/\([^)]*\)/g, '');
  }

  function exText(e) {
    if (!e) return '';
    return exCleanName(e) + ' ' + ((e.d && (e.d.ru + ' ' + e.d.en)) || '');
  }

  function muscleLabelsMap() {
    return {
      chest: L == 'ru' ? 'Грудь' : 'Chest',
      back: L == 'ru' ? 'Спина' : 'Back',
      abs: L == 'ru' ? 'Пресс / Кор' : 'Core / Abs',
      arms: L == 'ru' ? 'Руки' : 'Arms',
      shoulders: L == 'ru' ? 'Плечи' : 'Shoulders',
      legs: L == 'ru' ? 'Ноги' : 'Legs'
    };
  }

  function findExerciseAlternatives(exId, opts = {}) {
    const cur = exMap[exId];
    if (!cur) return { groups: [], items: [] };
    const curClean = exCleanName(cur);
    const curM = detectMuscles(curClean);
    const hasNameGrp = Object.values(curM).some(Boolean);
    const finalM = hasNameGrp ? curM : detectMuscles(exText(cur));
    const curGroups = Object.keys(finalM).filter(k => finalM[k]);
    const isCardio = CARDIO_RX.test(curClean || exText(cur));
    const q = (opts.q || '').trim().toLowerCase();
    const bwOnly = !!opts.bwOnly;
    const list = [];

    D.exercises.forEach(alt => {
      if (!alt || alt.id == exId) return;
      if (!(alt.n && (alt.n.ru || alt.n.en))) return;
      const altEq = (!alt.eq || alt.eq === 'none') ? 'no_equipment' : alt.eq;
      if (bwOnly && altEq !== 'no_equipment') return;
      const altName = (alt.n[L] || alt.n.en || alt.n.ru || '').toLowerCase();
      if (q && !altName.includes(q)) return;

      const altClean = exCleanName(alt);
      const nameM = detectMuscles(altClean);
      const fullM = detectMuscles(exText(alt));
      let score = 0, shared = 0;

      curGroups.forEach(g => {
        if (nameM[g]) { score += 90; shared++; }
        else if (fullM[g]) { score += 20; shared++; }
      });
      if (isCardio) {
        if (CARDIO_RX.test(altClean)) { score += 90; shared++; }
        else if (CARDIO_RX.test(exText(alt))) { score += 20; shared++; }
      }
      if (!curGroups.length && !isCardio && alt.mech && alt.mech === cur.mech) score += 30;
      const curEq = (!cur.eq || cur.eq === 'none') ? 'no_equipment' : cur.eq;
      if (altEq === curEq) score += 30;
      else if (altEq === 'no_equipment') score += 12;
      if (alt.mech && alt.mech === cur.mech) score += 15;
      if (alt.lvl && alt.lvl === cur.lvl) score += 12;
      if (getExVideo(alt)) score += 25;
      if (alt.img) score += 20;
      score += Number(alt.rating) || 4.0;

      if (shared > 0 || q || (!curGroups.length && !isCardio)) {
        list.push({ ex: alt, score });
      }
    });
    list.sort((a, b) => b.score - a.score);
    return { groups: curGroups, items: list.slice(0, 24).map(x => x.ex) };
  }

  const RPE_OPTS = [
    { id: 'easy', icon: '😌', ru: 'Легко', en: 'Easy', hintRu: 'Отличный запас сил! В следующий раз берите нагрузку на уровень выше.', hintEn: 'Plenty left in the tank! Try a harder variation next session.' },
    { id: 'good', icon: '💪', ru: 'В самый раз', en: 'Just right', hintRu: 'Идеальная нагрузка для стабильного роста и прогресса.', hintEn: 'Optimal effort — the sweet spot for steady gains.' },
    { id: 'hard', icon: '🥵', ru: 'Тяжело', en: 'Hard', hintRu: 'Мощная работа! Запланируйте лёгкое восстановление на завтра.', hintEn: 'Heavy session! Prioritize sleep and recovery before pushing again.' }
  ];

  function renderMuscleCard(w) {
    const text = ((w.t && (w.t.ru || w.t.en)) || '') + ' ' + ((w.d && (w.d.ru || w.d.en)) || '') + ' ' +
      (w.s || []).map(s => s.slice(1).map(n => {
        const e = exMap[n[0]];
        return e ? (e.n.ru + ' ' + e.n.en) : '';
      }).join(' ')).join(' ');
    const m = detectMuscles(text);
    const hasAny = Object.values(m).some(Boolean);
    if (!hasAny) m.arms = m.chest = true;
    const labels = muscleLabelsMap();

    const frontSvg = window.FITIFY_FRONT_SVG || '';
    const backSvg = window.FITIFY_BACK_SVG || '';

    return `
    <div class="fitify-mannequin-card" id="m3d-box" data-muscles='${JSON.stringify(m)}'>
      <div class="m3d-header">
        <div class="m3d-title">${uiSvg('dumbbell', 15)} ${L == 'ru' ? 'Целевые группы мышц' : 'Target Muscle Groups'}</div>
      </div>

      <div class="fitify-stage">
        <div class="fitify-mannequin-wrap">
          <div class="m-lbl">${L == 'ru' ? 'Спереди' : 'Front'}</div>
          <div id="m-front-slot">${frontSvg}</div>
        </div>
        <div class="fitify-mannequin-wrap">
          <div class="m-lbl">${L == 'ru' ? 'Сзади' : 'Back'}</div>
          <div id="m-back-slot">${backSvg}</div>
        </div>
      </div>

      <div class="m3d-pills">
        ${Object.entries(labels).map(([k, name]) => `
          <button class="m3d-pill ${m[k] ? 'active' : ''}" data-muscle="${k}">
            <span class="m3d-dot"></span>${name}
          </button>`).join('')}
      </div>
    </div>`;
  }

  function woSeconds(w) {
    if (!w || !w.s) return 0;
    let secs = 0;
    w.s.forEach(s => {
      const r = s[0] || 1;
      s.slice(1).forEach(n => {
        const dur = n[1] == 'second' ? n[2] : n[2] * 3;
        secs += r * (dur + (n[3] || w.rb || 0));
      });
    });
    return secs;
  }

  let deferredInstallPrompt = null;
  window.addEventListener('beforeinstallprompt', ev => {
    ev.preventDefault();
    deferredInstallPrompt = ev;
  });
  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
  });

  function getBodyMetrics() {
    try {
      const m = JSON.parse(localStorage.bodyMetrics || '{}');
      return {
        target: typeof m.target === 'number' ? m.target : null,
        logs: Array.isArray(m.logs) ? m.logs : []
      };
    } catch (e) {
      return { target: null, logs: [] };
    }
  }
  function saveBodyMetrics(m) {
    localStorage.bodyMetrics = JSON.stringify(m || { target: null, logs: [] });
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
  }

  const FITNESS_GOALS = [
    { id: 'fat_loss', ru: 'Похудение', en: 'Fat loss' },
    { id: 'muscle_gain', ru: 'Набор мышечной массы', en: 'Muscle gain' },
    { id: 'recomp', ru: 'Рельеф', en: 'Tone & recomp' },
    { id: 'strength', ru: 'Сила', en: 'Strength' },
    { id: 'endurance', ru: 'Выносливость', en: 'Endurance' },
    { id: 'health', ru: 'Здоровье', en: 'General health' }
  ];
  const FITNESS_LEVELS = [
    { id: 'beginner', ru: 'Новичок', en: 'Beginner' },
    { id: 'intermediate', ru: 'Средний', en: 'Intermediate' },
    { id: 'advanced', ru: 'Продвинутый', en: 'Advanced' }
  ];
  const FITNESS_SEX_OPTS = [
    { id: 'unspecified', ru: 'Не указывать', en: 'Prefer not to say' },
    { id: 'male', ru: 'Мужской', en: 'Male' },
    { id: 'female', ru: 'Женский', en: 'Female' }
  ];
  function getFitnessProfile() {
    let raw = {};
    try { raw = JSON.parse(localStorage.fitnessProfile || '{}') || {}; } catch (e) {}
    const out = {};
    const h = +raw.heightCm;
    if (!isNaN(h) && h >= 100 && h <= 250) out.heightCm = Math.round(h * 10) / 10;
    const a = +raw.age;
    if (Number.isInteger(a) && a >= 12 && a <= 100) out.age = a;
    if (typeof raw.sex === 'string' && FITNESS_SEX_OPTS.some(x => x.id === raw.sex)) out.sex = raw.sex;
    if (typeof raw.goal === 'string' && FITNESS_GOALS.some(x => x.id === raw.goal)) out.goal = raw.goal;
    if (typeof raw.level === 'string' && FITNESS_LEVELS.some(x => x.id === raw.level)) out.level = raw.level;
    if (typeof raw.injuries === 'string' && raw.injuries.trim()) {
      out.injuries = raw.injuries.replace(/[<>]/g, '').replace(/\s+/g, ' ').trim().slice(0, 160);
    }
    return out;
  }
  function saveFitnessProfile(fp) {
    const src = fp && typeof fp === 'object' ? fp : {};
    const clean = {};
    const h = +src.heightCm;
    if (!isNaN(h) && h >= 100 && h <= 250) clean.heightCm = Math.round(h * 10) / 10;
    const a = +src.age;
    if (Number.isInteger(a) && a >= 12 && a <= 100) clean.age = a;
    if (typeof src.sex === 'string' && FITNESS_SEX_OPTS.some(x => x.id === src.sex)) clean.sex = src.sex;
    if (typeof src.goal === 'string' && FITNESS_GOALS.some(x => x.id === src.goal)) clean.goal = src.goal;
    if (typeof src.level === 'string' && FITNESS_LEVELS.some(x => x.id === src.level)) clean.level = src.level;
    if (typeof src.injuries === 'string' && src.injuries.trim()) {
      clean.injuries = src.injuries.replace(/[<>]/g, '').replace(/\s+/g, ' ').trim().slice(0, 160);
    }
    localStorage.fitnessProfile = JSON.stringify(clean);
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
    return clean;
  }

  function renderActivityChartHtml(allH, days = 7) {
    const dayMap = {};
    allH.forEach(x => {
      const iso = new Date(x.t).toISOString().slice(0, 10);
      dayMap[iso] = (dayMap[iso] || 0) + Math.max(1, Math.round((x.s || 0) / 60));
    });
    const slots = [];
    const now = new Date();
    for (let k = days - 1; k >= 0; k--) {
      const d = new Date(now);
      d.setDate(now.getDate() - k);
      const iso = d.toISOString().slice(0, 10);
      slots.push({
        iso,
        mins: dayMap[iso] || 0,
        lbl: days <= 7
          ? d.toLocaleDateString(L, { weekday: 'short' }).slice(0, 2)
          : (k % 5 === 0 || k === 0 ? String(d.getDate()) : '')
      });
    }
    const maxM = Math.max(10, ...slots.map(s => s.mins));
    const totalM = slots.reduce((a, b) => a + b.mins, 0);
    const activeD = slots.filter(s => s.mins > 0).length;
    const W = 320, H = 88, padB = 18, padT = 8;
    const chartH = H - padB - padT;
    const step = W / slots.length;
    const barW = Math.max(4, Math.min(20, step * 0.56));
    const bars = slots.map((sl, idx) => {
      const bh = sl.mins ? Math.max(4, Math.round((sl.mins / maxM) * chartH)) : 3;
      const x = +(idx * step + (step - barW) / 2).toFixed(1);
      const y = +(padT + chartH - bh).toFixed(1);
      const isToday = idx === slots.length - 1;
      const fill = sl.mins ? (isToday ? '#2DD4BF' : '#F0A830') : 'rgba(255,255,255,0.08)';
      return `<rect x="${x}" y="${y}" width="${barW.toFixed(1)}" height="${bh}" rx="3" fill="${fill}"><title>${sl.iso}: ${sl.mins} ${L == 'ru' ? 'мин' : 'min'}</title></rect>`
        + (sl.lbl ? `<text x="${(x + barW / 2).toFixed(1)}" y="${H - 3}" text-anchor="middle" fill="#8E97A4" font-size="9" font-weight="700">${esc(sl.lbl)}</text>` : '');
    }).join('');
    return `
      <div class="act-summary">
        <span><b>${totalM}</b> ${L == 'ru' ? 'мин' : 'min'}</span>
        <span><b>${activeD}</b> / ${days} ${L == 'ru' ? 'дн.' : 'd'}</span>
      </div>
      <svg class="act-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${bars}</svg>`;
  }

  function renderMuscleBalanceHtml(allH) {
    if (!allH.length) return '';
    const counts = { chest: 0, back: 0, legs: 0, shoulders: 0, arms: 0, abs: 0 };
    allH.forEach(x => {
      const w = woMap[x.id];
      if (!w) return;
      const m = detectMuscles(woFullText(w));
      Object.keys(counts).forEach(k => {
        if (m[k]) counts[k]++;
      });
    });
    const labels = muscleLabelsMap();
    const entries = Object.entries(counts).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    if (!entries.length) return '';
    const maxV = Math.max(1, entries[0][1]);
    return `
      <div class="mb-wrap">
        <div class="mb-title">${L == 'ru' ? 'Баланс нагрузки по мышцам' : 'Muscle Load Balance'}</div>
        <div class="mb-list">
          ${entries.map(([k, v]) => {
            const pct = Math.round((v / maxV) * 100);
            return `<div class="mb-row">
              <span class="mb-lbl">${esc(labels[k] || k)}</span>
              <span class="mb-track"><i style="width:${pct}%"></i></span>
              <span class="mb-val">${v}</span>
            </div>`;
          }).join('')}
        </div>
      </div>`;
  }

  function renderHeatmapHtml(allH) {
    const byDate = {};
    let vol12w = 0;
    const cutoff = Date.now() - 84 * 864e5;
    allH.forEach(x => {
      const iso = new Date(x.t).toISOString().slice(0, 10);
      byDate[iso] = (byDate[iso] || 0) + Math.max(1, Math.round((x.s || 0) / 60));
      if (x.t >= cutoff && x.vol > 0) vol12w += x.vol;
    });
    const today = new Date();
    const dowToday = (today.getDay() + 6) % 7;
    const start = new Date(today);
    start.setDate(today.getDate() - (11 * 7 + dowToday));
    let cols = '', activeDays = 0;
    for (let w = 0; w < 12; w++) {
      let cells = '';
      for (let d = 0; d < 7; d++) {
        const dt = new Date(start);
        dt.setDate(start.getDate() + w * 7 + d);
        const iso = dt.toISOString().slice(0, 10);
        const mins = byDate[iso] || 0;
        if (mins > 0) activeDays++;
        const lvl = mins === 0 ? 0 : mins < 20 ? 1 : mins < 40 ? 2 : 3;
        const future = dt > today ? ' hm-fut' : '';
        cells += `<span class="hm-cell l${lvl}${future}" title="${iso}: ${mins} ${L == 'ru' ? 'мин' : 'min'}"></span>`;
      }
      cols += `<div class="hm-col">${cells}</div>`;
    }
    return `
      <div class="hm-wrap">
        <div class="hm-head">
          <span class="mb-title" style="margin:0;">${L == 'ru' ? 'Календарь 12 недель' : '12-Week Heatmap'}</span>
          <small>${activeDays} ${L == 'ru' ? 'акт. дн.' : 'active d.'}${vol12w > 0 ? ` · ${vol12w.toLocaleString()} ${L == 'ru' ? 'кг' : 'kg'}` : ''}</small>
        </div>
        <div class="hm-grid">${cols}</div>
      </div>`;
  }

  function renderBodyMetricsCard() {
    const bm = getBodyMetrics();
    const logs = bm.logs;
    const latest = logs.length ? logs[logs.length - 1] : null;
    const prev = logs.length > 1 ? logs[logs.length - 2] : null;
    const delta = latest && prev ? +(latest.w - prev.w).toFixed(1) : null;
    let spark = '';
    if (logs.length >= 2) {
      const pts = logs.slice(-12);
      const ws = pts.map(p => p.w);
      const minW = Math.min(...ws), maxW = Math.max(...ws);
      const span = Math.max(0.5, maxW - minW);
      const poly = pts.map((p, idx) => {
        const x = +(idx * (120 / (pts.length - 1))).toFixed(1);
        const y = +(28 - ((p.w - minW) / span) * 22 - 3).toFixed(1);
        return `${x},${y}`;
      }).join(' ');
      spark = `<svg class="body-spark" viewBox="0 0 120 32" fill="none"><polyline points="${poly}" stroke="#2DD4BF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    }
    return `
      <div class="ss-card prof-body">
        <div class="ss-card-title">
          <b>${uiSvg('scale', 15)} ${L == 'ru' ? 'Вес и замеры тела' : 'Body Weight & Metrics'}</b>
          <button type="button" class="duel-rules-btn" id="body-log-btn">+ ${L == 'ru' ? 'Записать' : 'Log'}</button>
        </div>
        <div class="body-kpi-row">
          <div>
            <div class="body-val">${latest ? latest.w + ' <small>' + (L == 'ru' ? 'кг' : 'kg') + '</small>' : '—'}</div>
            <div class="body-sub">
              ${delta !== null ? `<span style="color:${delta <= 0 ? 'var(--green)' : 'var(--ac-l)'};font-weight:700;">${delta > 0 ? '+' : ''}${delta} ${L == 'ru' ? 'кг' : 'kg'}</span>` : (L == 'ru' ? 'Нет записей' : 'No logs yet')}
              ${bm.target ? ` · ${L == 'ru' ? 'Цель' : 'Goal'}: ${bm.target}` : ''}
              ${latest && latest.waist ? ` · ${L == 'ru' ? 'Талия' : 'Waist'}: ${latest.waist}` : ''}
            </div>
          </div>
          ${spark}
        </div>
      </div>`;
  }

  function renderFitnessProfileCard() {
    const fp = getFitnessProfile();
    const bm = getBodyMetrics();
    const ps = getProgState();
    const latest = bm.logs.length ? bm.logs[bm.logs.length - 1] : null;
    const goalMeta = FITNESS_GOALS.find(g => g.id === fp.goal);
    const levelMeta = FITNESS_LEVELS.find(l => l.id === fp.level);
    const sexMeta = FITNESS_SEX_OPTS.find(s => s.id === fp.sex);
    const filledChecks = [
      Boolean(fp.heightCm),
      Boolean(fp.age),
      Boolean(latest && latest.w > 0),
      Boolean(bm.target && bm.target > 0),
      Boolean(goalMeta),
      Boolean(levelMeta),
      Boolean(ps.activeId)
    ];
    const filledCnt = filledChecks.filter(Boolean).length;
    const totChecks = filledChecks.length;
    const pct = Math.round((filledCnt / totChecks) * 100);
    const bmi = (fp.heightCm && latest && latest.w > 0)
      ? (latest.w / Math.pow(fp.heightCm / 100, 2)).toFixed(1)
      : '';
    const emptyLbl = '—';
    const items = [
      { lbl: L == 'ru' ? 'Рост' : 'Height', val: fp.heightCm ? `${fp.heightCm} ${L == 'ru' ? 'см' : 'cm'}` : emptyLbl, empty: !fp.heightCm },
      { lbl: L == 'ru' ? 'Возраст' : 'Age', val: fp.age ? `${fp.age}` : emptyLbl, empty: !fp.age },
      { lbl: L == 'ru' ? 'Текущий вес' : 'Current weight', val: latest ? `${latest.w} ${L == 'ru' ? 'кг' : 'kg'}${bmi ? ` (ИМТ ${bmi})` : ''}` : emptyLbl, empty: !latest },
      { lbl: L == 'ru' ? 'Целевой вес' : 'Target weight', val: bm.target ? `${bm.target} ${L == 'ru' ? 'кг' : 'kg'}` : emptyLbl, empty: !bm.target },
      { lbl: L == 'ru' ? 'Цель' : 'Goal', val: goalMeta ? (L == 'ru' ? goalMeta.ru : goalMeta.en) : emptyLbl, empty: !goalMeta },
      { lbl: L == 'ru' ? 'Уровень' : 'Level', val: levelMeta ? (L == 'ru' ? levelMeta.ru : levelMeta.en) : emptyLbl, empty: !levelMeta }
    ];
    if (sexMeta && sexMeta.id !== 'unspecified') {
      items.push({ lbl: L == 'ru' ? 'Пол' : 'Sex', val: L == 'ru' ? sexMeta.ru : sexMeta.en, empty: false, wide: true });
    }
    return `
      <div class="ss-card prof-fitness">
        <div class="fp-head">
          <div class="ss-card-title" style="margin:0">
            <b>${uiSvg('user', 15)} ${L == 'ru' ? 'Мои параметры и цели' : 'My Parameters & Goals'}</b>
          </div>
          <div class="fp-head-r">
            <span class="fp-pill ${filledCnt === totChecks ? 'done' : ''}">${L == 'ru' ? 'Заполнено' : 'Filled'} ${filledCnt}/${totChecks}</span>
            <button type="button" class="duel-rules-btn" id="fp-edit-btn">${L == 'ru' ? 'Редактировать' : 'Edit'}</button>
          </div>
        </div>
        <div class="fp-bar"><i style="width:${pct}%"></i></div>
        <div class="fp-grid">
          ${items.map(it => `
            <div class="fp-item ${it.wide ? 'wide' : ''}">
              <div class="fp-lbl">${esc(it.lbl)}</div>
              <div class="fp-val ${it.empty ? 'muted' : ''}">${esc(it.val)}</div>
            </div>`).join('')}
        </div>
        ${fp.injuries ? `<div class="fp-inj"><b>${L == 'ru' ? 'Ограничения:' : 'Limitations:'}</b> ${esc(fp.injuries)}</div>` : ''}
        ${filledCnt < totChecks ? `<div class="fp-empty-hint">${L == 'ru' ? 'Заполненные данные автоматически учитываются AI Coach при подборе нагрузки и советов.' : 'Filled details are used by AI Coach to tailor workouts and nutrition advice.'}</div>` : ''}
      </div>`;
  }

  function renderActiveProgramCard() {
    const ps = getProgState();
    const activeP = ps.activeId ? D.programs.find(p => String(p.id) === String(ps.activeId)) : null;
    if (!activeP) {
      return `
        <div class="ss-card prof-program">
          <div class="fp-head">
            <div class="ss-card-title" style="margin:0">
              <b>${uiSvg('pin', 15)} ${L == 'ru' ? 'Моя программа' : 'My Program'}</b>
            </div>
            <button type="button" class="duel-rules-btn" id="fp-prog-change">${L == 'ru' ? 'Выбрать' : 'Choose'}</button>
          </div>
          <div class="fp-empty-hint" style="margin-top:0">${L == 'ru' ? 'Программа ещё не выбрана' : 'No active program selected yet'}</div>
        </div>`;
    }
    const doneDays = Array.isArray(ps.logs[activeP.id]) ? ps.logs[activeP.id].length : 0;
    const totalDays = Math.max(1, +activeP.days || 30);
    const pct = Math.min(100, Math.round((doneDays / totalDays) * 100));
    return `
      <div class="ss-card prof-program">
        <div class="fp-head">
          <div class="ss-card-title" style="margin:0">
            <b>${uiSvg('pin', 15)} ${L == 'ru' ? 'Моя программа' : 'My Program'}</b>
          </div>
          <span class="fp-pill ${pct >= 100 ? 'done' : ''}">${pct}%</span>
        </div>
        <div class="fp-prog-title">${esc(pName(activeP))}</div>
        <div class="fp-prog-meta">
          <span>${L == 'ru' ? 'Выполнено дней' : 'Completed days'}: <b>${doneDays} / ${totalDays}</b></span>
          <span>${tempLbl(activeP.temp)}</span>
        </div>
        <div class="prog-bar-track"><div class="prog-bar-fill" style="width:${pct}%"></div></div>
        <div class="fp-prog-actions">
          <a href="#/program/${activeP.id}" class="btn">${L == 'ru' ? 'Открыть' : 'Open'}</a>
          <button type="button" class="btn alt" id="fp-prog-change">${L == 'ru' ? 'Сменить' : 'Change'}</button>
          <button type="button" class="btn alt" id="fp-prog-clear">${L == 'ru' ? 'Снять' : 'Unpin'}</button>
        </div>
      </div>`;
  }

  function renderThemeSwatchesHtml() {
    const curHex = (localStorage.accentTheme || CFG.accent || '#F0A830').toLowerCase();
    return ACCENT_THEMES.map(th => {
      const on = th.hex.toLowerCase() === curHex;
      return `<button type="button" class="theme-dot ${on ? 'on' : ''}" data-theme-hex="${th.hex}" title="${L == 'ru' ? th.ru : th.en}" style="--dot:${th.hex}"></button>`;
    }).join('');
  }

  function renderBackupAndPwaCard() {
    const isStandalone = window.matchMedia && window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    const canPrompt = !!deferredInstallPrompt && !isStandalone;
    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent || '');
    const cTok = localStorage.userToken || '';
    const cUser = localStorage.userName || '';
    const cTs = +(localStorage.cloudSyncTs || 0);
    const cTime = cTs ? new Date(cTs * 1000).toLocaleTimeString(L, { hour: '2-digit', minute: '2-digit' }) : '';
    const uEmail = localStorage.userEmail || '';
    const isPro = isUserPro();
    const uPlanExp = +(localStorage.userPlanExp || 0);
    const planText = (PAY_CFG && PAY_CFG.freeAccessMode)
      ? (L == 'ru' ? 'Бесплатно' : 'Free')
      : (isPro
        ? (uPlanExp ? `PRO до ${new Date(uPlanExp * 1000).toLocaleDateString(L)}` : 'PRO ∞')
        : 'FREE');
    return `
      <div class="ss-card prof-tools">
        <div class="ss-card-title">
          <b>${uiSvg('users', 15)} ${L == 'ru' ? 'Аккаунт и синхронизация' : 'Account & Cloud Sync'}</b>
          ${cTok ? `<span style="display:flex;gap:6px;align-items:center;"><span class="tag ${isPro ? 'pro' : ''}" style="${isPro ? 'background:var(--acc);color:#000;' : ''}">${planText}</span><span class="tag pro">@${esc(cUser)}</span></span>` : ''}
        </div>
        ${cTok ? `
          <div style="font-size:12px;color:var(--mut);margin-bottom:8px;">
            ${uEmail ? esc(uEmail) + ' · ' : ''}${cTime ? (L == 'ru' ? `Синхронизировано в ${cTime}` : `Synced at ${cTime}`) : (L == 'ru' ? 'Аккаунт подключён' : 'Account connected')}
          </div>
          <div class="prof-tools-row" style="margin-bottom:8px;">
            <button type="button" class="btn" id="cloud-sync-btn">${uiSvg('repeat', 14)} ${L == 'ru' ? 'Синхронизировать' : 'Sync now'}</button>
            <button type="button" class="btn alt" id="cloud-acct-btn">${L == 'ru' ? 'Пароль / Email' : 'Password / Email'}</button>
          </div>
          <div class="prof-tools-row" style="margin-bottom:12px;">
            ${!isPro ? `<button type="button" class="btn alt" id="cloud-pro-btn" style="border-color:var(--acc);color:var(--acc);">${uiSvg('bolt', 14)} ${L == 'ru' ? 'Получить PRO' : 'Upgrade to PRO'}</button>` : ''}
            <button type="button" class="btn alt" id="cloud-logout-btn">${L == 'ru' ? 'Выйти' : 'Sign out'}</button>
          </div>` : `
          <div style="font-size:12px;color:var(--mut);margin-bottom:8px;">
            ${L == 'ru' ? 'Войдите или создайте аккаунт, чтобы прогресс, веса и подписка сохранялись в базе сервера.' : 'Sign in or register to save progress and subscription in the database.'}
          </div>
          <button type="button" class="btn block" id="cloud-auth-btn" style="margin-bottom:12px;">${uiSvg('users', 14)} ${L == 'ru' ? 'Войти / Создать аккаунт' : 'Sign in / Register'}</button>`}
        <div class="ss-card-title" style="padding-top:8px;border-top:1px solid var(--line);">
          <b>${uiSvg('download', 15)} ${L == 'ru' ? 'Резервная копия и PWA' : 'Backup & PWA'}</b>
        </div>
        <div class="prof-tools-row">
          <button type="button" class="btn alt" id="bk-export">${uiSvg('download', 14)} ${L == 'ru' ? 'Экспорт JSON' : 'Export JSON'}</button>
          <button type="button" class="btn alt" id="bk-import-btn">${uiSvg('upload', 14)} ${L == 'ru' ? 'Импорт' : 'Import'}</button>
          <input type="file" id="bk-import-file" accept=".json,application/json" style="display:none">
        </div>
        <button type="button" class="btn alt block" id="pwa-offline-btn" style="margin-top:8px;font-size:12px;">${uiSvg('bolt', 13)} ${L == 'ru' ? 'Подготовить для зала (офлайн-кеш)' : 'Cache for Offline Gym Use'}</button>
        ${!isStandalone ? (canPrompt
          ? `<button type="button" class="btn block" id="pwa-install-btn" style="margin-top:8px;">${uiSvg('plus', 14)} ${L == 'ru' ? 'Установить приложение на экран' : 'Install App to Home Screen'}</button>`
          : `<div class="prof-pwa-hint">${isIos
              ? (L == 'ru' ? 'Установка на iPhone: «Поделиться» → «На экран „Домой“»' : 'Install on iPhone: Share → Add to Home Screen')
              : (L == 'ru' ? 'Установка на Android: меню браузера (⋮) → «Добавить на гл. экран»' : 'Install on Android: Browser menu (⋮) → Add to Home screen')}</div>`)
          : ''}
      </div>`;
  }

  const BACKUP_KEYS = ['hist', 'prs', 'exLogs', 'weekPlan', 'accentTheme', 'customWorkouts', 'athletePrograms', 'progState', 'athleteProfile', 'fitnessProfile', 'favs', 'freezeState', 'bodyMetrics', 'audioCfg', 'restPreset', 'duels', 'coopQuest', 'notifPrefs'];
  function collectLocalState() {
    const data = {};
    BACKUP_KEYS.forEach(k => {
      if (localStorage[k] !== undefined) data[k] = localStorage[k];
    });
    return data;
  }
  function applyServerState(stateObj, updatedAt) {
    if (!stateObj || typeof stateObj !== 'object') return;
    Object.entries(stateObj).forEach(([k, v]) => {
      if (BACKUP_KEYS.includes(k) && typeof v === 'string') localStorage.setItem(k, v);
    });
    if (updatedAt) localStorage.cloudSyncTs = String(updatedAt);
    applyAccent();
    registerCustomWorkouts();
  }
  const LOCAL_ACCOUNTS_KEY = 'localAccounts';
  function readLocalAccounts() {
    try { return JSON.parse(localStorage[LOCAL_ACCOUNTS_KEY] || '{}'); } catch { return {}; }
  }
  function writeLocalAccounts(obj) {
    localStorage[LOCAL_ACCOUNTS_KEY] = JSON.stringify(obj);
  }
  function isLocalToken(tok) {
    return typeof tok === 'string' && tok.startsWith('local:');
  }
  async function hashLocalPass(user, pass) {
    const raw = user.toLowerCase() + ':' + pass;
    if (window.crypto && crypto.subtle) {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
      return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
    }
    let h = 0;
    for (let i = 0; i < raw.length; i++) h = ((h << 5) - h + raw.charCodeAt(i)) | 0;
    return 'h' + (h >>> 0).toString(16);
  }
  function saveUserMeta(u) {
    if (!u || typeof u !== 'object') return;
    if (u.username) {
      localStorage.userName = u.username;
      let loc = {};
      try { loc = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
      if (!loc.name || loc.name === 'Mr.Bobrovsky' || loc.name === 'Атлет') loc.name = u.displayName || u.username;
      if (!loc.handle || loc.handle === '@mr.bobrovsky' || loc.handle === '@athlete') loc.handle = '@' + u.username.toLowerCase();
      localStorage.athleteProfile = JSON.stringify(loc);
    }
    if (u.avatar) {
      localStorage.userAvatar = u.avatar;
      let loc = {};
      try { loc = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
      loc.avatar = u.avatar;
      localStorage.athleteProfile = JSON.stringify(loc);
    }
    localStorage.userEmail = u.email || '';
    localStorage.userPlan = u.plan || 'free';
    localStorage.userPlanExp = String(u.planExpiresAt || 0);
    localStorage.userIsPro = u.isPro ? '1' : '0';
    if (typeof u.hasPassword === 'boolean') {
      localStorage.userHasPassword = u.hasPassword ? '1' : '0';
    }
  }
  function clearUserMeta() {
    ['userToken', 'userName', 'userEmail', 'userAvatar', 'userPlan', 'userPlanExp', 'userIsPro', 'userHasPassword', 'cloudSyncTs', 'athleteProfile', 'athleteFriends', 'last_notified_msg_id'].forEach(k => localStorage.removeItem(k));
  }
  let cloudSyncTimer = null;
  async function pushCloudSync() {
    if (cloudSyncTimer) {
      clearTimeout(cloudSyncTimer);
      cloudSyncTimer = null;
    }
    const tok = localStorage.userToken;
    if (!tok) return false;
    if (isLocalToken(tok)) {
      const uname = tok.slice(6).toLowerCase();
      const accs = readLocalAccounts();
      if (!accs[uname]) return false;
      const ts = Date.now();
      accs[uname].state = collectLocalState();
      accs[uname].updatedAt = ts;
      writeLocalAccounts(accs);
      localStorage.cloudSyncTs = String(ts);
      return true;
    }
    try {
      const r = await fetch('api/user/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok },
        body: JSON.stringify({ state: collectLocalState() })
      });
      if (r.status === 401) {
        localStorage.removeItem('userToken');
        return false;
      }
      if (!r.ok) return false;
      const j = await r.json();
      if (j.updatedAt) localStorage.cloudSyncTs = String(j.updatedAt);
      return true;
    } catch (e) { return false; }
  }
  async function pullCloudSync(force) {
    const tok = localStorage.userToken;
    if (!tok) return false;
    if (isLocalToken(tok)) {
      const uname = tok.slice(6).toLowerCase();
      const accs = readLocalAccounts();
      const acc = accs[uname];
      if (!acc) {
        localStorage.removeItem('userToken');
        return false;
      }
      localStorage.userName = acc.username || uname;
      const srvTs = +(acc.updatedAt || 0);
      const locTs = +(localStorage.cloudSyncTs || 0);
      if (srvTs > 0 && (force || srvTs > locTs) && acc.state && Object.keys(acc.state).length) {
        applyServerState(acc.state, srvTs);
        render();
        return true;
      }
      return true;
    }
    try {
      const r = await fetch('api/user/sync', { headers: { 'Authorization': 'Bearer ' + tok } });
      if (r.status === 401) {
        localStorage.removeItem('userToken');
        return false;
      }
      if (!r.ok) return false;
      const j = await r.json();
      if (j.user) saveUserMeta(j.user);
      const srvTs = +(j.updatedAt || 0);
      const locTs = +(localStorage.cloudSyncTs || 0);
      const hasMissingProfileSync = srvTs > 0 && j.state && (
        (!j.state.athletePrograms && (localStorage.athletePrograms !== undefined || localStorage.progState !== undefined))
        || (!j.state.bodyMetrics && localStorage.bodyMetrics !== undefined)
        || (!j.state.fitnessProfile && localStorage.fitnessProfile !== undefined)
      );
      if (srvTs > 0 && (force || srvTs > locTs) && j.state && Object.keys(j.state).length) {
        applyServerState(j.state, srvTs);
        if (hasMissingProfileSync) scheduleCloudSync();
        render();
        return true;
      }
      if (hasMissingProfileSync) {
        scheduleCloudSync();
      }
      if (srvTs === 0 && Object.keys(collectLocalState()).length) {
        await pushCloudSync();
      }
      return true;
    } catch (e) { return false; }
  }
  function scheduleCloudSync() {
    if (!localStorage.userToken) return;
    clearTimeout(cloudSyncTimer);
    cloudSyncTimer = setTimeout(pushCloudSync, 1200);
  }
  async function syncCommunityUsers() {
    try {
      const r = await fetch('api/community/users');
      if (r.ok) {
        const j = await r.json();
        if (j && Array.isArray(j.users) && window.AthleteProfile) {
          window.AthleteProfile.setCommunityUsers(j.users);
          return j.users;
        }
      }
    } catch (e) {}
    return [];
  }
  function exportBackupJson() {
    const payload = { app: 'FLEXA', exportedAt: new Date().toISOString(), data: {} };
    BACKUP_KEYS.forEach(k => {
      if (localStorage[k] !== undefined) payload.data[k] = localStorage[k];
    });
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `flexa-backup-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 100);
  }

  function importBackupJsonFile(file, cb) {
    if (!file) return;
    const r = new FileReader();
    r.onload = () => {
      try {
        const parsed = JSON.parse(r.result);
        if (!parsed || typeof parsed.data !== 'object' || Array.isArray(parsed.data)) throw new Error('bad');
        Object.entries(parsed.data).forEach(([k, v]) => {
          if (BACKUP_KEYS.includes(k) && typeof v === 'string') localStorage.setItem(k, v);
        });
        applyAccent();
        registerCustomWorkouts();
        vib(40);
        render();
        showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Прогресс восстановлен' : 'Progress restored');
        if (typeof cb === 'function') cb();
      } catch (err) {
        alert(L == 'ru' ? 'Неверный формат файла резервной копии' : 'Invalid backup file');
      }
    };
    r.readAsText(file);
  }

  async function performOfflineCache(btnEl) {
    vib(20);
    if (btnEl) {
      btnEl.textContent = L == 'ru' ? 'Кеширование…' : 'Caching…';
    }
    try {
      if ('caches' in window) {
        const c = await caches.open('flexa-offline-assets');
        const urls = ['./', './index.html', './style.css', './app.js', './texts.js', './muscles.js', './athlete_profile.js', './data.json'];
        await Promise.all(urls.map(u => fetch(u).then(r => r.ok ? c.put(u, r) : null).catch(() => null)));
      }
      if (btnEl) {
        btnEl.textContent = '✓ ' + (L == 'ru' ? 'Готово к залу' : 'Ready for gym');
      }
      vib(35);
      showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Приложение кешировано для зала' : 'App cached for offline use');
    } catch (e) {
      if (btnEl) {
        btnEl.textContent = L == 'ru' ? 'Повторить кеш' : 'Retry offline cache';
      }
    }
  }

  async function performCloudLogout() {
    vib(20);
    if (window._chatPollTimer) {
      clearInterval(window._chatPollTimer);
      window._chatPollTimer = null;
    }
    if (typeof window._cancelCoachRequest === 'function') {
      try { window._cancelCoachRequest(); } catch (_) {}
    }
    const tok = localStorage.userToken;
    if (tok && isLocalToken(tok)) await pushCloudSync();
    else if (tok) fetch('api/user/logout', { method: 'POST', headers: { 'Authorization': 'Bearer ' + tok } }).catch(() => {});
    clearUserMeta();
    render();
    showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Вы вышли из аккаунта' : 'Signed out');
  }

  function showPayCelebrationModal() {
    vib(40);
    sfx('win');
    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';
    bd.innerHTML = `
      <div class="ap-modal" style="text-align:center;padding:28px 22px;">
        <div style="font-size:44px;line-height:1;margin-bottom:12px;">🎉</div>
        <h3 style="font-size:20px;font-weight:900;margin:0 0 8px;color:var(--acc);">
          ${L == 'ru' ? 'Подписка PRO активирована!' : 'PRO Subscription Activated!'}
        </h3>
        <p style="font-size:13.5px;color:var(--mut);line-height:1.55;margin:0 0 20px;">
          ${L == 'ru'
            ? 'Поздравляем! Вам открыт полный доступ ко всем программам тренировок, трекеру прогресса, AI-тренеру и облачной синхронизации.'
            : 'Congratulations! You now have full access to all workout programs, day tracker, AI coach and cloud sync.'}
        </p>
        <button type="button" class="btn block" id="pw-celeb-btn" style="padding:12px;font-size:14px;font-weight:800;">
          ${L == 'ru' ? 'К программам тренировок 🚀' : 'Start Training 🚀'}
        </button>
      </div>
    `;
    document.body.appendChild(bd);
    bd.querySelector('#pw-celeb-btn').onclick = () => {
      bd.remove();
      window.location.hash = '#/workouts/programs';
      render();
    };
    bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
  }

  async function checkPendingPayment() {
    const hash = window.location.hash || '';
    const pid = sessionStorage.pendingPaymentId || (hash.match(/paymentId=([a-zA-Z0-9_-]+)/) || [])[1];
    if (hash.includes('pay_success') || pid) {
      if (hash.includes('pay_success')) {
        history.replaceState(null, '', window.location.pathname + '#/workouts/programs');
      }
      if (!pid) {
        if (localStorage.userToken && !isLocalToken(localStorage.userToken)) {
          await pullCloudSync(false);
          if (isUserPro()) {
            showPayCelebrationModal();
            render();
          }
        }
        return;
      }
      try {
        const tok = localStorage.userToken;
        const res = await fetch('/api/payment/check?paymentId=' + encodeURIComponent(pid), {
          headers: tok ? { Authorization: 'Bearer ' + tok } : {}
        });
        const data = await res.json();
        if (data && data.isPro) {
          localStorage.userIsPro = '1';
          sessionStorage.removeItem('pendingPaymentId');
          showPayCelebrationModal();
          render();
        }
      } catch (e) {
        console.warn('Payment check error:', e);
      }
    }
  }

  function openPaywallModal(suggestedPlanId = '3m') {
    if (PAY_CFG && PAY_CFG.freeAccessMode) {
      showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Все функции доступны бесплатно' : 'All features are available for free');
      return;
    }
    vib(20);
    let selPlan = suggestedPlanId;
    const PLANS_DATA = [
      { id: '1m', name: L == 'ru' ? '1 месяц' : '1 Month', days: 30, price: 290, badge: '', note: L == 'ru' ? '9.6 ₽ в день' : '9.6 ₽/day' },
      { id: '3m', name: L == 'ru' ? '3 месяца' : '3 Months', days: 90, price: 690, badge: 'ХИТ 🔥', sub: '−20%', note: L == 'ru' ? '7.6 ₽ в день (~230 ₽/мес)' : '7.6 ₽/day' },
      { id: '1y', name: L == 'ru' ? '1 год' : '1 Year', days: 365, price: 1490, badge: 'ВЫГОДА 57% ⚡', sub: '−57%', note: L == 'ru' ? '4.0 ₽ в день (~124 ₽/мес)' : '4.0 ₽/day' }
    ];

    const tok = localStorage.userToken;
    const isGuest = !tok || isLocalToken(tok);
    const uname = localStorage.userName || '';

    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';

    function renderModalContent() {
      const curPlanObj = PLANS_DATA.find(p => p.id === selPlan) || PLANS_DATA[1];
      bd.innerHTML = `
        <div class="ap-modal ap-paywall-modal">
          <div class="ap-pw-header">
            <div class="ap-pw-crown">${uiSvg('bolt', 24)}</div>
            <button type="button" class="ap-pw-close" id="pw-close">✕</button>
            <div class="ap-pw-title">${esc(CFG.brand || 'RizzaFit')} <span>PRO</span></div>
            <div class="ap-pw-subtitle">
              ${L == 'ru' ? 'Разблокируйте все программы тренировок и умные функции' : 'Unlock all workout programs & smart features'}
            </div>
          </div>

          <div class="ap-pw-features">
            <div class="ap-pw-feat-item">
              <span class="ap-pw-feat-ic">${uiSvg('dumbbell', 14)}</span>
              <span>${L == 'ru' ? '<b>Все программы тренировок:</b> 100 отжиманий, 50 подтягиваний, Frank Medrano, Спарта и др.' : '<b>All programs:</b> 100 pushups, 50 pullups, calisthenics routines.'}</span>
            </div>
            <div class="ap-pw-feat-item">
              <span class="ap-pw-feat-ic">${uiSvg('trend', 14)}</span>
              <span>${L == 'ru' ? '<b>Трекер прогресса по дням:</b> пошаговая прогрессия и история каждого дня' : '<b>Daily tracker:</b> step-by-step day logs and history'}</span>
            </div>
            <div class="ap-pw-feat-item">
              <span class="ap-pw-feat-ic">${uiSvg('sparkles', 14)}</span>
              <span>${L == 'ru' ? '<b>Персональный AI-тренер:</b> ответы по технике, советам и планам' : '<b>AI Coach:</b> technique advice, form tips and recovery'}</span>
            </div>
            <div class="ap-pw-feat-item">
              <span class="ap-pw-feat-ic">${uiSvg('check', 14)}</span>
              <span>${L == 'ru' ? '<b>Облачная синхронизация:</b> тренировки и рекорды на ПК и телефоне' : '<b>Cloud sync:</b> auto-backup across all your devices'}</span>
            </div>
          </div>

          <div class="ap-pw-plans-grid">
            ${PLANS_DATA.map(p => {
              const active = p.id === selPlan;
              return `
              <div class="ap-pw-plan-card ${active ? 'active' : ''}" data-pid="${p.id}">
                ${p.badge ? `<div class="ap-pw-plan-badge">${p.badge}</div>` : ''}
                <div class="ap-pw-plan-radio"></div>
                <div class="ap-pw-plan-info">
                  <div class="ap-pw-plan-name">${p.name}</div>
                  <div class="ap-pw-plan-note">${p.note}</div>
                </div>
                <div class="ap-pw-plan-price">${p.price} ₽</div>
              </div>`;
            }).join('')}
          </div>

          <div class="ap-pw-sbp-box">
            <div class="ap-pw-sbp-badge">
              <span class="ap-pw-sbp-logo">⚡ СБП</span>
              <span>${L == 'ru' ? 'Система быстрых платежей' : 'Fast Payment System'}</span>
            </div>
            <div class="ap-pw-sbp-hint">
              ${L == 'ru'
                ? 'Без ввода данных карты. Оплата в приложении любого банка РФ (Сбер, Тинькофф, Альфа, ВТБ).'
                : 'Instant payment in Russian banking apps via QR or direct redirect.'}
            </div>
          </div>

          ${isGuest ? `
          <div class="ap-pw-guest-box">
            <div style="font-size:11.5px;color:var(--mut);line-height:1.4;">
              ${L == 'ru' ? '💡 Совет: войдите в аккаунт, чтобы подписка навсегда привязалась к вашему профилю.' : 'Sign in to link subscription to your account.'}
            </div>
            <button type="button" class="btn alt" id="pw-auth-btn" style="padding:6px 12px;font-size:12px;margin-top:6px;">
              ${L == 'ru' ? 'Войти / Создать аккаунт' : 'Sign In / Register'}
            </button>
          </div>` : `
          <div class="ap-pw-account-box">
            <span>${L == 'ru' ? 'Подписка для:' : 'Account:'} <b>@${esc(uname)}</b> ✓</span>
          </div>`}

          <div id="pw-err" class="ap-pw-err"></div>

          <button type="button" class="btn block ap-pw-submit-btn" id="pw-submit">
            ${uiSvg('bolt', 16)} ${L == 'ru' ? `Оплатить ${curPlanObj.price} ₽ через СБП` : `Pay ${curPlanObj.price} ₽ via SBP`}
          </button>

          <div class="ap-pw-guarantee">
            ${L == 'ru' ? '🔒 Безопасные платежи через ЮKassa · Без скрытых списаний' : 'Secure payments powered by YooKassa'}
          </div>
        </div>
      `;

      bd.querySelector('#pw-close').onclick = () => bd.remove();

      bd.querySelectorAll('.ap-pw-plan-card').forEach(card => {
        card.onclick = () => {
          vib(15);
          selPlan = card.dataset.pid;
          renderModalContent();
        };
      });

      const authBtn = bd.querySelector('#pw-auth-btn');
      if (authBtn) {
        authBtn.onclick = () => {
          bd.remove();
          openCloudAuthModal(() => openPaywallModal(selPlan));
        };
      }

      const submitBtn = bd.querySelector('#pw-submit');
      const errBox = bd.querySelector('#pw-err');
      submitBtn.onclick = async () => {
        vib(25);
        if (isGuest) {
          errBox.textContent = L == 'ru'
            ? 'Пожалуйста, войдите в аккаунт или зарегистрируйтесь (займет 10 сек), чтобы активировать подписку.'
            : 'Please sign in or register to link your subscription.';
          openCloudAuthModal(() => openPaywallModal(selPlan));
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = L == 'ru' ? 'Подключение к ЮKassa...' : 'Connecting to YooKassa...';
        errBox.textContent = '';
        try {
          const resp = await fetch('/api/payment/create', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + localStorage.userToken
            },
            body: JSON.stringify({ planId: selPlan })
          });
          const data = await resp.json();
          if (!resp.ok || !data.ok) {
            submitBtn.disabled = false;
            submitBtn.textContent = L == 'ru' ? `Оплатить ${curPlanObj.price} ₽ через СБП` : `Pay ${curPlanObj.price} ₽ via SBP`;
            if (data && data.notConfigured) {
              errBox.innerHTML = L == 'ru'
                ? 'Платёжный шлюз ЮKassa пока не активирован в панели управления.<br>Администратор может включить его в разделе <b>💳 ЮKassa & СБП</b>.'
                : 'YooKassa is not configured yet in the admin panel.';
            } else {
              errBox.textContent = data.error || (L == 'ru' ? 'Не удалось создать платёж' : 'Failed to create payment');
            }
            return;
          }
          if (data.paymentId) {
            sessionStorage.pendingPaymentId = data.paymentId;
          }
          if (data.paymentUrl) {
            window.location.href = data.paymentUrl;
          } else {
            errBox.textContent = L == 'ru' ? 'ЮKassa не вернула ссылку на оплату' : 'No payment URL returned';
            submitBtn.disabled = false;
          }
        } catch (e) {
          submitBtn.disabled = false;
          submitBtn.textContent = L == 'ru' ? `Оплатить ${curPlanObj.price} ₽ через СБП` : `Pay ${curPlanObj.price} ₽ via SBP`;
          errBox.textContent = e.message || 'Ошибка сети';
        }
      };
    }

    renderModalContent();
    document.body.appendChild(bd);
    bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
  }

  function openCloudProModal() {
    openPaywallModal();
  }

  function openCloudAcctModal(cb) {
    vib(20);
    const hasPw = localStorage.userHasPassword !== '0';
    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';
    bd.innerHTML = `<div class="ap-modal">
      <h3>${uiSvg('users', 17)} ${L == 'ru' ? 'Настройки аккаунта' : 'Account Settings'}</h3>
      ${!hasPw ? `<div style="font-size:12px;color:var(--mut);margin-bottom:10px;line-height:1.4;background:rgba(255,255,255,0.04);padding:8px 10px;border-radius:8px;">
        ${L == 'ru' ? 'У вашего аккаунта (Telegram/OAuth) ещё не задан пароль. Задайте пароль, чтобы также входить по логину/email и паролю.' : 'Your Telegram/OAuth account has no password yet. Set one to also sign in with username/email and password.'}
      </div>` : ''}
      <label>Email<input id="ac-email" type="email" value="${esc(localStorage.userEmail || '')}" placeholder="alex@mail.ru"></label>
      ${hasPw ? `<label>${L == 'ru' ? 'Текущий пароль (если меняете)' : 'Current password (if changing)'}<input id="ac-old" type="password" autocomplete="current-password"></label>` : ''}
      <label>${hasPw ? (L == 'ru' ? 'Новый пароль (мин. 6 символов)' : 'New password (min 6 chars)') : (L == 'ru' ? 'Установить пароль (мин. 6 символов)' : 'Set password (min 6 chars)')}<input id="ac-new" type="password" autocomplete="new-password"></label>
      <div id="ac-err" style="font-size:12px;color:#f87171;min-height:16px;margin-top:4px;"></div>
      <div class="ap-modal-actions">
        <button type="button" class="btn alt" id="ac-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
        <button type="button" class="btn" id="ac-save">${L == 'ru' ? 'Сохранить' : 'Save'}</button>
      </div>
    </div>`;
    document.body.appendChild(bd);
    bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
    bd.querySelector('#ac-cancel').onclick = () => bd.remove();
    bd.querySelector('#ac-save').onclick = async () => {
      const errEl = bd.querySelector('#ac-err');
      errEl.textContent = '';
      const tok = localStorage.userToken;
      if (isLocalToken(tok)) {
        errEl.textContent = L == 'ru' ? 'Доступно на серверной версии сайта' : 'Available on server deployment';
        return;
      }
      const emailVal = bd.querySelector('#ac-email').value.trim().toLowerCase();
      const npw = bd.querySelector('#ac-new').value;
      const payload = {};
      if (emailVal || !npw) payload.email = emailVal;
      if (npw) {
        if (hasPw) {
          const oldEl = bd.querySelector('#ac-old');
          payload.oldPassword = oldEl ? oldEl.value : '';
        }
        payload.newPassword = npw;
      }
      try {
        const r = await fetch('api/user/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok },
          body: JSON.stringify(payload)
        });
        const j = await r.json();
        if (!r.ok) { errEl.textContent = j.error || 'Error'; return; }
        saveUserMeta(j.user);
        bd.remove();
        render();
        showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Данные аккаунта обновлены' : 'Account updated');
        if (typeof cb === 'function') cb(j.user);
      } catch (e) {
        errEl.textContent = L == 'ru' ? 'Нет связи с сервером' : 'Server unreachable';
      }
    };
  }

  function socialSvg(type) {
    if (type === 'telegram') {
      return `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .39z"/></svg>`;
    }
    if (type === 'vk') {
      return `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12.78 17.5c-5.26 0-8.26-3.6-8.38-9.59h2.64c.08 4.4 2.02 6.26 3.56 6.64V7.91h2.49v3.79c1.52-.16 3.1-1.89 3.64-3.79h2.49c-.42 2.35-2.14 4.08-3.36 4.79 1.22.57 3.18 2.07 3.91 4.8h-2.74c-.58-1.8-2.02-3.18-3.92-3.37v3.37h-.33z"/></svg>`;
    }
    if (type === 'google') {
      return `<svg viewBox="0 0 24 24" width="18" height="18"><path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"/><path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"/><path fill="#FBBC05" d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3 0-.8.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.3 0 15.2s.7 5.5 1.9 7.9l3.7-2.9z"/><path fill="#34A853" d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16.5C3.7 20.2 7.5 23.5 12 23.5z"/></svg>`;
    }
    if (type === 'yandex') {
      return `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M13.5 2h2.5L11.5 13.5l4.5 8.5h-2.7L9.5 14l-2 2.5V22H5V2h4.5c3.2 0 5 1.8 5 4.5 0 2.2-1.2 3.8-3 4.4L13.5 2zm-4 7.5h1.2c1.7 0 2.8-.9 2.8-2.4s-1.1-2.4-2.8-2.4H9.5v4.8z"/></svg>`;
    }
    return '';
  }

  async function submitSocialLogin(payload) {
    try {
      if (!payload.state) payload.state = collectLocalState();
      const r = await fetch('api/user/social-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const j = await r.json();
      if (!r.ok || !j.ok) {
        alert(j.error || (L == 'ru' ? 'Ошибка входа через соцсеть' : 'Social sign-in error'));
        return false;
      }
      localStorage.userToken = j.token;
      saveUserMeta(j.user);
      if (window.RizzaAnalytics) {
        window.RizzaAnalytics.trackLogin(payload.provider || 'social');
      }
      if (j.state && Object.keys(j.state).length) applyServerState(j.state, j.updatedAt);
      else if (Object.keys(collectLocalState()).length) await pushCloudSync();
      vib(35);
      showAppToast(CFG.brand || 'RizzaFit', (L == 'ru' ? 'Вход выполнен: ' : 'Signed in as: ') + (j.user.displayName || j.user.username));
      render();
      return true;
    } catch (e) {
      alert(L == 'ru' ? 'Не удалось связаться с сервером' : 'Failed to reach server');
      return false;
    }
  }

  async function openTelegramAuthModal() {
    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';
    bd.innerHTML = `
      <div class="ap-modal" style="max-width:390px;text-align:center;">
        <div style="width:58px;height:58px;border-radius:50%;background:#229ED9;color:#fff;display:inline-flex;align-items:center;justify-content:center;margin-bottom:12px;box-shadow:0 8px 24px rgba(34,158,217,0.35);">
          ${socialSvg('telegram')}
        </div>
        <h3 style="margin:0 0 6px;font-size:18px;font-weight:700;">${L == 'ru' ? 'Вход через Telegram' : 'Sign in with Telegram'}</h3>
        <p id="tg-modal-desc" style="font-size:13px;color:var(--mut);line-height:1.45;margin:0 0 16px;">
          ${L == 'ru' ? 'Связываемся с Telegram-ботом...' : 'Connecting to Telegram bot...'}
        </p>
        <div id="tg-modal-body">
          <div style="padding:18px;display:flex;align-items:center;justify-content:center;">
            <div class="loading-spin" style="width:28px;height:28px;border:3px solid rgba(255,255,255,0.1);border-top-color:#229ED9;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
          </div>
        </div>
        <div class="ap-modal-actions" style="margin-top:16px;">
          <button type="button" class="btn alt" id="tg-modal-cancel" style="width:100%;">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
        </div>
      </div>
    `;
    document.body.appendChild(bd);
    let pollTimer = null;
    let closed = false;
    const cleanup = () => {
      closed = true;
      if (pollTimer) clearInterval(pollTimer);
      if (bd && bd.parentNode) bd.remove();
    };
    bd.onclick = (e) => { if (e.target === bd) cleanup(); };
    bd.querySelector('#tg-modal-cancel').onclick = cleanup;

    try {
      const res = await fetch('api/auth/telegram/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Failed to start auth');
      if (closed) return;

      if (!data.configured || !data.url) {
        bd.querySelector('#tg-modal-desc').textContent = L == 'ru'
          ? 'Telegram-бот еще не подключен в панели администратора.'
          : 'Telegram bot is not configured in admin panel.';
        bd.querySelector('#tg-modal-body').innerHTML = `
          <div style="background:rgba(255,255,255,0.04);border:1px dashed var(--bdr);border-radius:12px;padding:14px;font-size:12.5px;color:var(--mut);line-height:1.45;margin-bottom:12px;text-align:left;">
            ${L == 'ru'
              ? '💡 Администратор может подключить бота в <b>Панели управления (/admin.html -> ✈️ Telegram бот)</b>. Также вы можете зарегистрироваться или войти по логину и паролю.'
              : '💡 Administrator can configure the bot in <b>Admin panel (/admin.html -> ✈️ Telegram bot)</b>. You can also sign in with username and password.'}
          </div>
          <button type="button" class="btn" id="tg-alt-login" style="width:100%;margin-bottom:6px;">
            ${L == 'ru' ? 'Войти / Создать аккаунт' : 'Sign in / Create Account'}
          </button>
        `;
        bd.querySelector('#tg-alt-login').onclick = () => {
          cleanup();
          openCloudAuthModal('login');
        };
        return;
      }

      // Bot is configured!
      bd.querySelector('#tg-modal-desc').innerHTML = L == 'ru'
        ? 'Открываем Telegram... Нажмите кнопку <b>СТАРТ</b> (Start) в боте для завершения входа.'
        : 'Opening Telegram... Tap <b>START</b> in the bot to confirm login.';

      bd.querySelector('#tg-modal-body').innerHTML = `
        <div style="margin-bottom:14px;">
          <a href="${data.url}" target="_blank" rel="noopener noreferrer" class="btn" id="tg-open-link" style="display:inline-flex;align-items:center;justify-content:center;gap:8px;background:#229ED9;color:#fff;width:100%;padding:13px;font-weight:700;border-radius:12px;text-decoration:none;box-shadow:0 4px 16px rgba(34,158,217,0.35);">
            ${socialSvg('telegram')} ${L == 'ru' ? 'Перейти в Telegram (@' + (data.botUsername || 'bot') + ')' : 'Open Telegram (@' + (data.botUsername || 'bot') + ')'}
          </a>
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:8px;font-size:12px;color:var(--mut);">
          <div class="loading-spin" style="width:14px;height:14px;border:2px solid rgba(255,255,255,0.15);border-top-color:#229ED9;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
          <span>${L == 'ru' ? 'Ожидание подтверждения в боте...' : 'Waiting for confirmation in bot...'}</span>
        </div>
      `;

      // Try opening Telegram in new window/tab
      try {
        window.open(data.url, '_blank');
      } catch (err) {}
      const tgOpenLink = bd.querySelector('#tg-open-link');
      if (tgOpenLink) {
        tgOpenLink.addEventListener('click', () => {
          if (window.RizzaAnalytics) window.RizzaAnalytics.trackCta('open_telegram_bot', 'auth');
        });
      }

      // Start polling
      let attempts = 0;
      pollTimer = setInterval(async () => {
        if (closed) return;
        attempts++;
        if (attempts > 120) { // ~3 minutes timeout
          cleanup();
          alert(L == 'ru' ? 'Время ожидания входа через Telegram истекло.' : 'Telegram login timed out.');
          return;
        }
        try {
          const pollRes = await fetch('api/auth/telegram/poll?token=' + encodeURIComponent(data.token));
          const pollData = await pollRes.json();
          if (pollRes.status === 403 || (pollData && pollData.ok === false && pollData.error)) {
            cleanup();
            alert(pollData.error || (L == 'ru' ? 'Вход запрещён' : 'Access denied'));
            return;
          }
          if (pollData.ok && pollData.confirmed && pollData.sessionToken) {
            cleanup();
            localStorage.userToken = pollData.sessionToken;
            saveUserMeta(pollData.user);
            if (window.RizzaAnalytics) {
              window.RizzaAnalytics.trackLogin('telegram');
            }
            if (pollData.state && Object.keys(pollData.state).length) applyServerState(pollData.state, pollData.updatedAt);
            else if (Object.keys(collectLocalState()).length) await pushCloudSync();
            vib(35);
            showAppToast(CFG.brand || 'RizzaFit', (L == 'ru' ? 'Вход выполнен: ' : 'Signed in as: ') + (pollData.user.displayName || pollData.user.username));
            render();
          }
        } catch (e) {
          // ignore transient poll errors
        }
      }, 1500);

    } catch (e) {
      if (closed) return;
      bd.querySelector('#tg-modal-desc').textContent = L == 'ru' ? 'Ошибка связи с сервером' : 'Connection error';
      bd.querySelector('#tg-modal-body').innerHTML = `<div style="color:#f87171;font-size:13px;">${esc(e.message || String(e))}</div>`;
    }
  }

  function handleSocialAuth(provider) {
    if (provider === 'telegram') {
      const tgInitData = window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.initData === 'string'
        ? window.Telegram.WebApp.initData.trim()
        : '';
      if (tgInitData) {
        submitSocialLogin({
          provider: 'telegram',
          initData: tgInitData
        });
        return;
      }
      openTelegramAuthModal();
      return;
    }
    showAppToast(
      CFG.brand || 'RizzaFit',
      L == 'ru'
        ? 'Вход через эту соцсеть временно недоступен. Используйте Telegram или логин и пароль.'
        : 'Sign-in with this provider is temporarily unavailable. Use Telegram or username/password.'
    );
  }

  async function socialApi(endpoint, opts = {}) {
    const tok = localStorage.userToken;
    if (!tok) throw new Error('Not logged in');
    const headers = Object.assign({
      'Authorization': 'Bearer ' + tok
    }, opts.headers || {});
    let body = opts.body;
    if (body && typeof body === 'object' && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    const res = await fetch(endpoint, Object.assign({}, opts, { headers, body }));
    if (res.status === 401) {
      localStorage.removeItem('userToken');
      syncNavAthlete();
      render();
      throw new Error('Unauthorized');
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || 'Server error');
    }
    return data;
  }

  function renderAuthGateStub(title, desc) {
    return `
      <div class="wrap" style="padding:32px 14px;text-align:center;">
        <div class="auth-gate-card" style="max-width:440px;margin:0 auto;">
          <div class="auth-gate-av">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>
          </div>
          <h2 style="margin:0 0 8px;font-size:20px;font-weight:800;color:var(--tx);">${esc(title || t('authRequired'))}</h2>
          <p style="margin:0 0 20px;font-size:13.5px;color:var(--mut);line-height:1.45;">
            ${esc(desc || t('authRequiredDesc'))}
          </p>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <button type="button" class="btn" id="social-gate-login" style="padding:12px;font-size:14px;justify-content:center;">
              ${uiSvg('users', 16)} ${L == 'ru' ? 'Войти в аккаунт' : 'Sign In'}
            </button>
            <button type="button" class="btn alt" id="social-gate-reg" style="padding:12px;font-size:14px;justify-content:center;">
              ${uiSvg('sparkles', 16)} ${L == 'ru' ? 'Создать аккаунт' : 'Create Account'}
            </button>
          </div>
          <div class="auth-sep" style="margin:16px 0 14px;">
            <span>${L == 'ru' ? 'или быстрый вход через соцсети' : 'or quick sign-in with'}</span>
          </div>
          <div class="social-auth-grid">
            <button type="button" class="soc-btn tg" data-soc-provider="telegram" style="grid-column:1 / -1;">
              ${socialSvg('telegram')} Telegram
            </button>
          </div>
        </div>
      </div>`;
  }

  function renderGuestAuthGate() {
    return `
      <div class="auth-gate-card">
        <div class="auth-gate-av">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>
        </div>
        <h2 style="margin:0 0 8px;font-size:20px;font-weight:800;color:var(--tx);">${L == 'ru' ? 'Личный профиль' : 'Personal Profile'}</h2>
        <p style="margin:0 0 20px;font-size:13.5px;color:var(--mut);line-height:1.45;">
          ${L == 'ru' ? 'Войдите или зарегистрируйтесь, чтобы сохранять тренировки, историю, отслеживать прогресс и соревноваться в рейтинге.' : 'Sign in or create an account to save workouts, track progress, and join the leaderboard.'}
        </p>

        <div style="display:flex;flex-direction:column;gap:10px;">
          <button type="button" class="btn" id="guest-btn-login" style="padding:12px;font-size:14px;">
            ${uiSvg('users', 16)} ${L == 'ru' ? 'Войти в аккаунт' : 'Sign In'}
          </button>
          <button type="button" class="btn alt" id="guest-btn-reg" style="padding:12px;font-size:14px;">
            ${uiSvg('sparkles', 16)} ${L == 'ru' ? 'Создать аккаунт' : 'Create Account'}
          </button>
        </div>

        <div class="auth-sep">
          <span>${L == 'ru' ? 'или быстрый вход через соцсети' : 'or quick sign-in with'}</span>
        </div>

        <div class="social-auth-grid">
          <button type="button" class="soc-btn tg" data-soc-provider="telegram" style="grid-column:1 / -1;">
            ${socialSvg('telegram')} Telegram
          </button>
          <button type="button" class="soc-btn vk" data-soc-provider="vk" disabled title="${L == 'ru' ? 'Скоро' : 'Coming soon'}" style="opacity:0.45;cursor:not-allowed;">
            ${socialSvg('vk')} ${L == 'ru' ? 'VK (скоро)' : 'VK (soon)'}
          </button>
          <button type="button" class="soc-btn gg" data-soc-provider="google" disabled title="${L == 'ru' ? 'Скоро' : 'Coming soon'}" style="opacity:0.45;cursor:not-allowed;">
            ${socialSvg('google')} ${L == 'ru' ? 'Google (скоро)' : 'Google (soon)'}
          </button>
          <button type="button" class="soc-btn ya" data-soc-provider="yandex" disabled title="${L == 'ru' ? 'Скоро' : 'Coming soon'}" style="opacity:0.45;cursor:not-allowed;grid-column:1 / -1;">
            ${socialSvg('yandex')} ${L == 'ru' ? 'Яндекс (скоро)' : 'Yandex (soon)'}
          </button>
        </div>

        <div style="margin-top:24px;border-top:1px solid rgba(255,255,255,0.08);padding-top:16px;">
          <div style="font-size:11.5px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;text-align:left;">
            ${L == 'ru' ? 'Что даёт аккаунт:' : 'Account benefits:'}
          </div>
          <ul class="auth-benefits-list">
            <li class="auth-benefit-item">
              <span style="font-size:16px;">☁️</span>
              <div><b>${L == 'ru' ? 'Сохранение в базе данных' : 'Cloud database save'}</b> — ${L == 'ru' ? 'история и рекорды сохраняются на сервере' : 'history and records saved on server'}</div>
            </li>
            <li class="auth-benefit-item">
              <span style="font-size:16px;">🏆</span>
              <div><b>${L == 'ru' ? 'Рейтинг реальных атлетов' : 'Athletes leaderboard'}</b> — ${L == 'ru' ? 'участвуйте в турнирной таблице клуба' : 'compete on the club leaderboard'}</div>
            </li>
            <li class="auth-benefit-item">
              <span style="font-size:16px;">⚔️</span>
              <div><b>${L == 'ru' ? 'Дуэли и квесты' : 'Duels & Co-op quests'}</b> — ${L == 'ru' ? 'соревнуйтесь с другими участниками' : 'challenge other athletes'}</div>
            </li>
            <li class="auth-benefit-item">
              <span style="font-size:16px;">📱</span>
              <div><b>${L == 'ru' ? 'Синхронизация между устройствами' : 'Cross-device sync'}</b> — ${L == 'ru' ? 'прогресс всегда под рукой' : 'progress syncs everywhere'}</div>
            </li>
          </ul>
        </div>
      </div>
    `;
  }

  function openCloudAuthModal(initialMode, cb) {
    if (typeof initialMode === 'function') {
      cb = initialMode;
      initialMode = 'login';
    }
    vib(20);
    let mode = (typeof initialMode === 'string' && ['login', 'register', 'reset'].includes(initialMode)) ? initialMode : 'login';
    if (window.RizzaAnalytics) {
      window.RizzaAnalytics.trackCta('open_auth_modal', mode);
    }
    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';
    const drawAuth = () => {
      const isReg = mode === 'register';
      const isReset = mode === 'reset';
      const title = isReg
        ? (L == 'ru' ? 'Создать аккаунт' : 'Create Account')
        : isReset
          ? (L == 'ru' ? 'Сброс пароля' : 'Reset Password')
          : (L == 'ru' ? 'Вход в аккаунт' : 'Sign In');
      bd.innerHTML = `<div class="ap-modal">
        <h3>${uiSvg('users', 17)} ${title}</h3>
        <div class="act-seg" style="margin-bottom:12px;">
          <button type="button" class="act-seg-btn ${mode === 'login' ? 'on' : ''}" id="ca-tab-login">${L == 'ru' ? 'Вход' : 'Sign In'}</button>
          <button type="button" class="act-seg-btn ${isReg ? 'on' : ''}" id="ca-tab-reg">${L == 'ru' ? 'Регистрация' : 'Register'}</button>
        </div>
        ${isReset ? `
          <div style="font-size:12px;color:var(--mut);margin-bottom:10px;">
            ${L == 'ru' ? 'Введите одноразовый код сброса (выдаётся администратором) и новый пароль.' : 'Enter the one-time reset code and your new password.'}
          </div>
          <label>${L == 'ru' ? 'Код сброса' : 'Reset code'}<input id="ca-code" placeholder="A1B2C3D4" style="text-transform:uppercase"></label>
          <label>${L == 'ru' ? 'Новый пароль (мин. 6 символов)' : 'New password (min 6 chars)'}<input id="ca-pass" type="password" autocomplete="new-password"></label>
        ` : `
          <label>${isReg ? (L == 'ru' ? 'Логин (латиница, цифры, _)' : 'Username (a-z, 0-9, _)') : (L == 'ru' ? 'Логин или Email' : 'Username or Email')}<input id="ca-user" autocomplete="username" placeholder="${isReg ? 'alex_fit' : 'alex_fit / mail@site.ru'}"></label>
          ${isReg ? `<label>Email<input id="ca-email" type="email" autocomplete="email" placeholder="alex@mail.ru"></label>` : ''}
          <label>${L == 'ru' ? 'Пароль (мин. 6 символов)' : 'Password (min 6 chars)'}<input id="ca-pass" type="password" autocomplete="${isReg ? 'new-password' : 'current-password'}"></label>
          ${!isReg ? `<button type="button" id="ca-forgot" style="background:none;border:0;padding:4px 0;color:var(--acc);font-size:12px;cursor:pointer;text-align:left;">${L == 'ru' ? 'Забыли пароль? Ввести код сброса' : 'Forgot password? Use reset code'}</button>` : ''}
        `}
        <div id="ca-err" style="font-size:12px;color:#f87171;min-height:16px;margin-top:4px;"></div>
        <div class="ap-modal-actions">
          <button type="button" class="btn alt" id="ca-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
          <button type="button" class="btn" id="ca-go">${isReg ? (L == 'ru' ? 'Создать' : 'Register') : isReset ? (L == 'ru' ? 'Сохранить' : 'Reset') : (L == 'ru' ? 'Войти' : 'Sign In')}</button>
        </div>
        <div class="auth-sep" style="margin:14px 0 10px;">
          <span>${L == 'ru' ? 'или через соцсети' : 'or with social'}</span>
        </div>
        <div class="social-auth-grid" style="margin-bottom:6px;">
          <button type="button" class="soc-btn tg" data-modal-soc="telegram" style="grid-column:1 / -1;">${socialSvg('telegram')} Telegram</button>
          <button type="button" class="soc-btn vk" data-modal-soc="vk" disabled title="${L == 'ru' ? 'Скоро' : 'Coming soon'}" style="opacity:0.45;cursor:not-allowed;">${socialSvg('vk')} ${L == 'ru' ? 'VK (скоро)' : 'VK (soon)'}</button>
          <button type="button" class="soc-btn gg" data-modal-soc="google" disabled title="${L == 'ru' ? 'Скоро' : 'Coming soon'}" style="opacity:0.45;cursor:not-allowed;">${socialSvg('google')} ${L == 'ru' ? 'Google (скоро)' : 'Google (soon)'}</button>
          <button type="button" class="soc-btn ya" data-modal-soc="yandex" disabled title="${L == 'ru' ? 'Скоро' : 'Coming soon'}" style="opacity:0.45;cursor:not-allowed;grid-column:1 / -1;">${socialSvg('yandex')} ${L == 'ru' ? 'Яндекс (скоро)' : 'Yandex (soon)'}</button>
        </div>
      </div>`;
      bd.querySelectorAll('[data-modal-soc]').forEach(b => {
        b.onclick = () => {
          bd.remove();
          handleSocialAuth(b.dataset.modalSoc);
        };
      });
      bd.querySelector('#ca-tab-login').onclick = () => { mode = 'login'; drawAuth(); };
      bd.querySelector('#ca-tab-reg').onclick = () => { mode = 'register'; drawAuth(); };
      const forgotBtn = bd.querySelector('#ca-forgot');
      if (forgotBtn) forgotBtn.onclick = () => { mode = 'reset'; drawAuth(); };
      bd.querySelector('#ca-cancel').onclick = () => bd.remove();
      bd.querySelector('#ca-go').onclick = async () => {
        const errEl = bd.querySelector('#ca-err');
        errEl.textContent = '';
        if (isReset) {
          const code = bd.querySelector('#ca-code').value.trim().toUpperCase();
          const newPassword = bd.querySelector('#ca-pass').value;
          if (!code) { errEl.textContent = L == 'ru' ? 'Введите код сброса' : 'Enter reset code'; return; }
          if (newPassword.length < 6) { errEl.textContent = L == 'ru' ? 'Пароль должен быть не короче 6 символов' : 'Password must be at least 6 chars'; return; }
          try {
            const r = await fetch('api/user/reset/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code, newPassword }) });
            const j = await r.json();
            if (!r.ok) { errEl.textContent = j.error || 'Error'; return; }
            mode = 'login';
            drawAuth();
            showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Пароль обновлён, войдите' : 'Password updated, please sign in');
          } catch (e) {
            errEl.textContent = L == 'ru' ? 'Нет связи с сервером' : 'Server unreachable';
          }
          return;
        }
        const username = bd.querySelector('#ca-user').value.trim();
        const email = isReg ? bd.querySelector('#ca-email').value.trim().toLowerCase() : '';
        const password = bd.querySelector('#ca-pass').value;
        if (isReg && !/^[a-zA-Z0-9_]{3,24}$/.test(username)) {
          errEl.textContent = L == 'ru' ? 'Логин: 3–24 символа (латиница, цифры, _)' : 'Username: 3-24 chars (a-z, 0-9, _)';
          return;
        }
        if (!isReg && username.length < 3) {
          errEl.textContent = L == 'ru' ? 'Введите логин или Email' : 'Enter username or email';
          return;
        }
        if (isReg && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
          errEl.textContent = L == 'ru' ? 'Укажите корректный Email' : 'Enter a valid Email';
          return;
        }
        if (password.length < 6) {
          errEl.textContent = L == 'ru' ? 'Пароль должен быть не короче 6 символов' : 'Password must be at least 6 characters';
          return;
        }
        const finishLocalAuth = async () => {
          const key = username.toLowerCase();
          const accs = readLocalAccounts();
          const passHash = await hashLocalPass(key, password);
          if (isReg) {
            if (accs[key]) {
              errEl.textContent = L == 'ru' ? 'Такой логин уже есть на этом устройстве' : 'Username already exists on this device';
              return;
            }
            const ts = Date.now();
            accs[key] = { username, email, passHash, state: collectLocalState(), updatedAt: ts };
            writeLocalAccounts(accs);
            localStorage.cloudSyncTs = String(ts);
          } else {
            const acc = accs[key] || Object.values(accs).find(a => (a.email || '').toLowerCase() === key);
            const accKey = acc ? acc.username.toLowerCase() : key;
            if (!acc) {
              errEl.textContent = L == 'ru' ? 'Профиль не найден. Переключитесь на «Регистрация».' : 'Profile not found. Switch to Register.';
              return;
            }
            const chkHash = await hashLocalPass(accKey, password);
            if (acc.passHash !== chkHash) {
              errEl.textContent = L == 'ru' ? 'Неверный пароль' : 'Wrong password';
              return;
            }
            if (acc.state && Object.keys(acc.state).length) applyServerState(acc.state, acc.updatedAt);
          }
          const active = accs[key] || Object.values(accs).find(a => (a.email || '').toLowerCase() === key);
          localStorage.userToken = 'local:' + active.username.toLowerCase();
          saveUserMeta({ username: active.username, email: active.email || '', plan: 'free', planExpiresAt: 0, isPro: false });
          vib(35);
          bd.remove();
          render();
          showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Локальный профиль подключён' : 'Local profile connected');
          if (typeof cb === 'function') cb(active);
        };
        try {
          const endpoint = isReg ? 'api/user/register' : 'api/user/login';
          const body = isReg ? { username, email, password, state: collectLocalState() } : { username, password };
          const r = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
          const ct = r.headers.get('content-type') || '';
          if (!ct.includes('application/json')) {
            await finishLocalAuth();
            return;
          }
          const j = await r.json();
          if (!r.ok) { errEl.textContent = j.error || 'Error'; return; }
          localStorage.userToken = j.token;
          saveUserMeta(j.user);
          if (window.RizzaAnalytics) {
            if (isReg) {
              window.RizzaAnalytics.trackSignUp('credentials');
            } else {
              window.RizzaAnalytics.trackLogin('credentials');
            }
          }
          if (j.state && Object.keys(j.state).length) applyServerState(j.state, j.updatedAt);
          else if (Object.keys(collectLocalState()).length) await pushCloudSync();
          vib(35);
          bd.remove();
          render();
          lastUnreadCheck = 0;
          checkUnreadMessages();
          showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Синхронизация подключена' : 'Cloud sync connected');
          if (typeof cb === 'function') cb(j.user);
        } catch (e) {
          await finishLocalAuth();
        }
      };
    };
    document.body.appendChild(bd);
    bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
    drawAuth();
  }

  function openSettingsSheet() {
    vib(20);
    let cur = {};
    try { cur = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
    const base = Object.assign({}, window.AthleteProfile ? window.AthleteProfile.DEFAULTS : {}, CFG.athlete || {}, cur);
    let pendingAv = base.avatar || '';

    const isStandalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
    const canPrompt = !!deferredInstallPrompt && !isStandalone;

    const cTok = localStorage.userToken || '';
    const cUser = localStorage.userName || '';
    const uEmail = localStorage.userEmail || '';
    const isPro = isUserPro();
    const uPlanExp = +(localStorage.userPlanExp || 0);
    const planText = (PAY_CFG && PAY_CFG.freeAccessMode)
      ? (L == 'ru' ? 'Бесплатно' : 'Free')
      : (isPro
        ? (uPlanExp ? `PRO до ${new Date(uPlanExp * 1000).toLocaleDateString(L)}` : 'PRO ∞')
        : 'FREE');
    const planSubtitle = (PAY_CFG && PAY_CFG.freeAccessMode)
      ? (L == 'ru' ? 'Все функции доступны бесплатно' : 'All features are available for free')
      : (isPro
        ? (L == 'ru' ? 'Премиум подписка активна' : 'Premium subscription active')
        : (L == 'ru' ? 'Синхронизация и AI-тренер' : 'Sync & AI Coach'));

    const cTs = +(localStorage.cloudSyncTs || 0);
    const cTime = cTs ? new Date(cTs * 1000).toLocaleTimeString(L, { hour: '2-digit', minute: '2-digit' }) : '';

    const bd = document.createElement('div');
    bd.className = 'ap-modal-backdrop';
    bd.innerHTML = `
      <div class="ap-modal ap-settings-sheet">
        <div class="ap-settings-header">
          <div style="display:flex;align-items:center;gap:8px;">
            ${uiSvg('settings', 18)}
            <h3 style="margin:0;font-size:17px;font-weight:800;">${L == 'ru' ? 'Настройки' : 'Settings'}</h3>
          </div>
          <button type="button" class="ap-settings-close" id="ap-set-close">✕</button>
        </div>

        <div class="ap-settings-scroll">
          <!-- Секция 1: Профиль и оформление -->
          <div class="ap-set-group-title">${L == 'ru' ? 'Профиль и оформление' : 'Profile & Look'}</div>
          <div class="ap-set-card">
            <div style="display:flex;align-items:center;gap:14px;padding:12px;">
              <div style="width:58px;height:58px;border-radius:50%;border:2px dashed var(--ac);padding:2px;flex:none;overflow:hidden;background:#141a13;">
                <img id="ap-m-av-prev" src="${esc(pendingAv || 'img/logo.svg')}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;" onerror="this.src='img/logo.svg'">
              </div>
              <div style="display:flex;flex-direction:column;gap:6px;flex:1;">
                <label class="btn alt" style="padding:7px 10px;font-size:12px;cursor:pointer;margin:0;text-align:center;display:flex;align-items:center;justify-content:center;gap:6px;">
                  ${uiSvg('upload', 12)} ${L == 'ru' ? 'Загрузить фото' : 'Upload photo'}
                  <input type="file" id="ap-m-av-file" accept="image/*" style="display:none">
                </label>
                <button type="button" class="btn alt" id="ap-m-av-del" style="padding:5px 10px;font-size:11.5px;color:var(--mut);">${L == 'ru' ? 'Убрать фото' : 'Remove'}</button>
              </div>
            </div>
            <div style="padding:0 12px 12px;">
              <label class="ap-set-field-label">${L == 'ru' ? 'Имя спортсмена' : 'Name'}
                <input id="ap-m-name" value="${esc(base.name || '')}" class="ap-set-input">
              </label>
              <label class="ap-set-field-label" style="margin-top:8px;">@username
                <input id="ap-m-handle" value="${esc(cUser ? '@' + cUser : (base.handle || ''))}" class="ap-set-input" autocomplete="off">
              </label>
              <div id="ap-set-err" style="font-size:12px;color:#f87171;min-height:16px;margin-top:6px;"></div>
              <div class="theme-row" style="margin-top:8px;">
                <span style="font-size:12px;color:var(--mut);font-weight:700;">${L == 'ru' ? 'Цвет акцента' : 'Accent theme'}</span>
                <div class="theme-swatches">${renderThemeSwatchesHtml()}</div>
              </div>
            </div>
          </div>

          <!-- Секция 2: Подписка -->
          <div class="ap-set-group-title">${L == 'ru' ? 'Подписка' : 'Subscription'}</div>
          <div class="ap-set-card">
            <div class="ap-set-row" style="${!isPro ? '' : 'border:none;'}">
              <div style="display:flex;align-items:center;gap:10px;">
                <span class="ap-set-icon-box" style="background:rgba(var(--green-r, 34), 197, 94, 0.15);color:var(--ac);">${uiSvg('bolt', 16)}</span>
                <div>
                  <div style="font-weight:800;font-size:13.5px;">${esc(CFG.brand || 'RizzaFit')} PRO</div>
                  <div style="font-size:11.5px;color:var(--mut);">${planSubtitle}</div>
                </div>
              </div>
              <span class="tag ${isPro ? 'pro' : ''}" style="${isPro ? 'background:var(--acc);color:#000;' : ''}">${planText}</span>
            </div>
            ${!isPro ? `
            <div style="padding:0 12px 12px;">
              <button type="button" class="btn block" id="set-cloud-pro-btn" style="font-size:12.5px;padding:9px 12px;">
                ${uiSvg('bolt', 14)} ${L == 'ru' ? 'Узнать о возможностях PRO' : 'Upgrade to PRO'}
              </button>
            </div>` : ''}
          </div>

          <!-- Секция 3: Аккаунт и облако -->
          <div class="ap-set-group-title">${L == 'ru' ? 'Аккаунт и синхронизация' : 'Account & Sync'}</div>
          <div class="ap-set-card">
            ${cTok ? `
              <div class="ap-set-row">
                <div style="display:flex;align-items:center;gap:10px;min-width:0;">
                  <span class="ap-set-icon-box">${uiSvg('users', 16)}</span>
                  <div style="min-width:0;">
                    <div style="font-weight:800;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${uEmail ? esc(uEmail) : '@' + esc(cUser)}</div>
                    <div style="font-size:11px;color:var(--mut);" id="set-sync-time-lbl">${cTime ? (L == 'ru' ? `Синхронизировано в ${cTime}` : `Synced at ${cTime}`) : (L == 'ru' ? 'Подключён к серверу' : 'Connected')}</div>
                  </div>
                </div>
                <button type="button" class="btn alt" id="set-cloud-sync-btn" style="padding:6px 10px;font-size:11.5px;white-space:nowrap;">
                  ${uiSvg('repeat', 13)} ${L == 'ru' ? 'Обновить' : 'Sync'}
                </button>
              </div>
              <div class="ap-set-item-btn" id="set-cloud-acct-btn">
                <span style="display:flex;align-items:center;gap:10px;">
                  <span class="ap-set-icon-box">${uiSvg('lock', 15)}</span>
                  <span>${localStorage.userHasPassword === '0' ? (L == 'ru' ? 'Задать пароль или Email' : 'Set Password / Email') : (L == 'ru' ? 'Сменить пароль или Email' : 'Change Password / Email')}</span>
                </span>
                <span class="ap-set-arrow">›</span>
              </div>
            ` : `
              <div style="padding:12px;">
                <div style="font-size:12px;color:var(--mut);margin-bottom:10px;line-height:1.4;">
                  ${L == 'ru' ? 'Войдите или зарегистрируйтесь, чтобы сохранять тренировки и рекорды в облаке сервера.' : 'Sign in or register to sync your workouts to the cloud.'}
                </div>
                <button type="button" class="btn block" id="set-cloud-auth-btn" style="font-size:12.5px;padding:9px 12px;">
                  ${uiSvg('users', 14)} ${L == 'ru' ? 'Войти / Создать аккаунт' : 'Sign in / Register'}
                </button>
              </div>
            `}
          </div>

          <!-- Секция 3.5: Заблокированные пользователи -->
          ${cTok && !isLocalToken(cTok) ? `
          <div class="ap-set-group-title">${L == 'ru' ? 'Заблокированные пользователи' : 'Blocked Users'}</div>
          <div class="ap-set-card" id="set-blocked-wrap">
            <div style="padding:12px;font-size:12px;color:var(--mut);">${L == 'ru' ? 'Загрузка списка…' : 'Loading…'}</div>
          </div>` : ''}

          <!-- Секция 4: Данные и память -->
          <div class="ap-set-group-title">${L == 'ru' ? 'Данные и память' : 'Data & Storage'}</div>
          <div class="ap-set-card">
            <div class="ap-set-item-btn" id="set-offline-btn">
              <span style="display:flex;align-items:center;gap:10px;">
                <span class="ap-set-icon-box">${uiSvg('bolt', 15)}</span>
                <span id="set-offline-label">${L == 'ru' ? 'Подготовить для зала (офлайн-кеш)' : 'Cache for Offline Gym'}</span>
              </span>
              <span class="ap-set-arrow">⚡</span>
            </div>
            <div class="ap-set-item-btn" id="set-bk-export">
              <span style="display:flex;align-items:center;gap:10px;">
                <span class="ap-set-icon-box">${uiSvg('download', 15)}</span>
                <span>${L == 'ru' ? 'Экспорт данных (резервная копия)' : 'Export Backup (JSON)'}</span>
              </span>
              <span class="ap-set-arrow">›</span>
            </div>
            <div class="ap-set-item-btn" id="set-bk-import-btn" style="border:none;">
              <span style="display:flex;align-items:center;gap:10px;">
                <span class="ap-set-icon-box">${uiSvg('upload', 15)}</span>
                <span>${L == 'ru' ? 'Импорт резервной копии' : 'Import Backup'}</span>
              </span>
              <span class="ap-set-arrow">›</span>
            </div>
            <input type="file" id="set-bk-import-file" accept=".json,application/json" style="display:none">

            ${!isStandalone && canPrompt ? `
              <div class="ap-set-item-btn" id="set-pwa-btn" style="border-top:1px solid var(--line);">
                <span style="display:flex;align-items:center;gap:10px;">
                  <span class="ap-set-icon-box">${uiSvg('plus', 15)}</span>
                  <span>${L == 'ru' ? 'Установить на домашний экран' : 'Install to Home Screen'}</span>
                </span>
                <span class="ap-set-arrow">›</span>
              </div>
            ` : ''}
          </div>

          <!-- Секция 5: Сессия -->
          ${cTok ? `
          <div style="margin-top:14px;">
            <button type="button" class="ap-set-logout-btn" id="set-cloud-logout-btn">
              ${uiSvg('exit', 14)} ${L == 'ru' ? 'Выйти из аккаунта' : 'Sign out'}
            </button>
          </div>` : ''}

          <div style="margin-top:16px;display:flex;gap:8px;">
            <button type="button" class="btn" style="flex:1;padding:11px;" id="ap-m-save">${L == 'ru' ? 'Сохранить изменения' : 'Save Changes'}</button>
            <button type="button" class="btn alt" style="padding:11px 16px;" id="ap-m-reset">${L == 'ru' ? 'Сброс' : 'Reset'}</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(bd);
    bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
    bd.querySelector('#ap-set-close').onclick = () => bd.remove();

    bd.querySelector('#ap-m-av-file').onchange = ev => {
      const file = ev.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const max = 256;
          const scale = Math.min(1, max / Math.max(img.width, img.height));
          const w = Math.max(1, Math.round(img.width * scale));
          const h = Math.max(1, Math.round(img.height * scale));
          const cv = document.createElement('canvas');
          cv.width = w; cv.height = h;
          cv.getContext('2d').drawImage(img, 0, 0, w, h);
          pendingAv = cv.toDataURL('image/jpeg', 0.85);
          bd.querySelector('#ap-m-av-prev').src = pendingAv;
        };
        img.onerror = () => {
          pendingAv = reader.result;
          bd.querySelector('#ap-m-av-prev').src = pendingAv;
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    };

    bd.querySelector('#ap-m-av-del').onclick = () => {
      pendingAv = '';
      bd.querySelector('#ap-m-av-prev').src = 'img/logo.svg';
    };

    bd.querySelectorAll('[data-theme-hex]').forEach(btn => {
      btn.onclick = () => {
        vib(20);
        const hex = btn.dataset.themeHex;
        localStorage.accentTheme = hex;
        applyAccent(hex);
        bd.querySelectorAll('[data-theme-hex]').forEach(b => b.classList.toggle('on', b.dataset.themeHex === hex));
      };
    });

    bd.querySelector('#ap-m-save').onclick = async () => {
      const saveBtn = bd.querySelector('#ap-m-save');
      const errEl = bd.querySelector('#ap-set-err');
      if (errEl) errEl.textContent = '';
      const rawName = bd.querySelector('#ap-m-name').value.trim();
      const rawHandle = bd.querySelector('#ap-m-handle').value;
      const isServerUser = !!(localStorage.userToken && !isLocalToken(localStorage.userToken));

      let finalHandle = rawHandle.trim() || base.handle;
      let usernameChanged = false;

      if (isServerUser) {
        const curU = (localStorage.userName || '').toLowerCase();
        const candRaw = rawHandle.startsWith('@') ? rawHandle.slice(1) : rawHandle;
        if (candRaw.toLowerCase() !== curU || /\s/.test(rawHandle)) {
          if (saveBtn) saveBtn.disabled = true;
          try {
            const uRes = await socialApi('/api/user/username', {
              method: 'POST',
              body: { username: rawHandle }
            });
            if (uRes && uRes.user && uRes.user.username) {
              saveUserMeta(uRes.user);
              finalHandle = '@' + uRes.user.username;
              usernameChanged = !uRes.unchanged;
            }
          } catch (e) {
            if (errEl) errEl.textContent = e.message || (L == 'ru' ? 'Не удалось изменить @username' : 'Failed to change @username');
            if (saveBtn) saveBtn.disabled = false;
            return;
          }
          if (saveBtn) saveBtn.disabled = false;
        } else {
          finalHandle = '@' + curU;
        }
      }

      const next = {
        name: rawName || (localStorage.userName || base.name),
        handle: finalHandle,
        avatar: pendingAv
      };
      localStorage.athleteProfile = JSON.stringify(next);
      localStorage.userAvatar = pendingAv || '';
      if (isServerUser) {
        const ok = await pushCloudSync();
        if (!ok) {
          if (errEl) errEl.textContent = L == 'ru' ? 'Не удалось синхронизировать изменения с сервером' : 'Failed to sync changes to server';
          return;
        }
      } else {
        scheduleCloudSync();
      }
      bd.remove();
      render();
      showAppToast(
        CFG.brand || 'RizzaFit',
        usernameChanged
          ? (L == 'ru' ? 'Профиль и @username обновлены' : 'Profile and @username updated')
          : (L == 'ru' ? 'Настройки сохранены' : 'Settings saved')
      );
    };

    bd.querySelector('#ap-m-reset').onclick = async () => {
      const msg = L == 'ru'
        ? 'Сбросить имя, фото профиля и цвет акцента к значениям по умолчанию? Аккаунт, @username, друзья, чаты и тренировки сохранятся.'
        : 'Reset display name, avatar, and accent color to defaults? Your account, @username, friends, chats, and workouts will be preserved.';
      if (!confirm(msg)) return;
      const errEl = bd.querySelector('#ap-set-err');
      if (errEl) errEl.textContent = '';
      const resetBtn = bd.querySelector('#ap-m-reset');
      if (resetBtn) resetBtn.disabled = true;

      const prevProf = localStorage.getItem('athleteProfile');
      const prevAccent = localStorage.getItem('accentTheme');
      const prevAvatar = localStorage.getItem('userAvatar');

      const curU = localStorage.userName || '';
      const resetProf = {
        name: curU,
        handle: curU ? '@' + curU : '',
        avatar: ''
      };
      localStorage.athleteProfile = JSON.stringify(resetProf);
      localStorage.userAvatar = '';
      localStorage.removeItem('accentTheme');
      applyAccent();

      if (localStorage.userToken && !isLocalToken(localStorage.userToken)) {
        const ok = await pushCloudSync();
        if (!ok) {
          // Restore previous local values on sync failure
          if (prevProf !== null) localStorage.setItem('athleteProfile', prevProf);
          else localStorage.removeItem('athleteProfile');
          if (prevAccent !== null) localStorage.setItem('accentTheme', prevAccent);
          if (prevAvatar !== null) localStorage.setItem('userAvatar', prevAvatar);
          applyAccent();
          if (errEl) errEl.textContent = L == 'ru' ? 'Ошибка синхронизации сброса с сервером. Попробуйте позже.' : 'Failed to sync reset with server. Please try again.';
          if (resetBtn) resetBtn.disabled = false;
          return;
        }
      }
      bd.remove();
      render();
      showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Настройки профиля сброшены' : 'Profile settings reset');
    };

    const blockedWrap = bd.querySelector('#set-blocked-wrap');
    if (blockedWrap) {
      async function loadBlockedList() {
        try {
          const res = await socialApi('/api/users/blocked');
          const list = res.blocked || [];
          if (!list.length) {
            blockedWrap.innerHTML = `<div style="padding:12px;font-size:12px;color:var(--mut);">${L == 'ru' ? 'Нет заблокированных пользователей' : 'No blocked users'}</div>`;
            return;
          }
          blockedWrap.innerHTML = list.map(bu => `
            <div class="ap-set-row" style="gap:10px;">
              <div style="display:flex;align-items:center;gap:10px;min-width:0;cursor:pointer;" data-go-blocked="${esc(bu.username)}">
                <div class="user-avatar-wrap" style="width:34px;height:34px;font-size:13px;">
                  ${bu.avatar ? `<img src="${esc(bu.avatar)}" alt="">` : esc((bu.displayName || bu.username).charAt(0).toUpperCase())}
                </div>
                <div style="min-width:0;">
                  <div style="font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(bu.displayName || bu.username)}</div>
                  <div style="font-size:11px;color:var(--mut);">@${esc(bu.username)}</div>
                </div>
              </div>
              <button type="button" class="btn alt" data-unblock-uid="${esc(String(bu.userId || bu.id))}" style="padding:5px 10px;font-size:11.5px;white-space:nowrap;">${t('unblockUser')}</button>
            </div>
          `).join('');
          blockedWrap.querySelectorAll('[data-go-blocked]').forEach(el => {
            el.onclick = () => { bd.remove(); location.hash = '#/user/' + encodeURIComponent(el.dataset.goBlocked); };
          });
          blockedWrap.querySelectorAll('[data-unblock-uid]').forEach(btn => {
            btn.onclick = async () => {
              btn.disabled = true;
              try {
                await socialApi('/api/users/unblock', { method: 'POST', body: { targetUserId: btn.dataset.unblockUid } });
                showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Пользователь разблокирован' : 'User unblocked');
                loadBlockedList();
                render();
              } catch (e) {
                alert(e.message);
                btn.disabled = false;
              }
            };
          });
        } catch (e) {
          blockedWrap.innerHTML = `<div style="padding:12px;font-size:12px;color:#f87171;">${esc(e.message || 'Error')}</div>`;
        }
      }
      loadBlockedList();
    }

    const proBtn = bd.querySelector('#set-cloud-pro-btn');
    if (proBtn) proBtn.onclick = () => { openCloudProModal(); };

    const authBtn = bd.querySelector('#set-cloud-auth-btn');
    if (authBtn) authBtn.onclick = () => {
      bd.remove();
      openCloudAuthModal(() => openSettingsSheet());
    };

    const acctBtn = bd.querySelector('#set-cloud-acct-btn');
    if (acctBtn) acctBtn.onclick = () => {
      bd.remove();
      openCloudAcctModal(() => openSettingsSheet());
    };

    const syncBtn = bd.querySelector('#set-cloud-sync-btn');
    if (syncBtn) syncBtn.onclick = async () => {
      vib(20);
      syncBtn.disabled = true;
      syncBtn.textContent = '…';
      const ok = await pushCloudSync();
      if (ok) {
        showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Данные синхронизированы' : 'Synced');
        const newTs = +(localStorage.cloudSyncTs || 0);
        const newTime = newTs ? new Date(newTs * 1000).toLocaleTimeString(L, { hour: '2-digit', minute: '2-digit' }) : '';
        const syncLbl = bd.querySelector('#set-sync-time-lbl');
        if (syncLbl && newTime) syncLbl.textContent = L == 'ru' ? `Синхронизировано в ${newTime}` : `Synced at ${newTime}`;
      }
      syncBtn.disabled = false;
      syncBtn.innerHTML = `${uiSvg('check', 13)} ${L == 'ru' ? 'Готово' : 'Done'}`;
    };

    const offBtn = bd.querySelector('#set-offline-btn');
    if (offBtn) offBtn.onclick = () => {
      performOfflineCache(bd.querySelector('#set-offline-label'));
    };

    const expBtn = bd.querySelector('#set-bk-export');
    if (expBtn) expBtn.onclick = () => {
      vib(25);
      exportBackupJson();
      showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Резервная копия сохранена' : 'Backup saved');
    };

    const impBtn = bd.querySelector('#set-bk-import-btn');
    const impFile = bd.querySelector('#set-bk-import-file');
    if (impBtn && impFile) {
      impBtn.onclick = () => impFile.click();
      impFile.onchange = ev => {
        const f = ev.target.files && ev.target.files[0];
        if (f) importBackupJsonFile(f, () => bd.remove());
      };
    }

    const pwaBtn = bd.querySelector('#set-pwa-btn');
    if (pwaBtn) pwaBtn.onclick = async () => {
      if (!deferredInstallPrompt) return;
      vib(25);
      deferredInstallPrompt.prompt();
      try { await deferredInstallPrompt.userChoice; } catch (e) {}
      deferredInstallPrompt = null;
      bd.remove();
      render();
    };

    const logoutBtn = bd.querySelector('#set-cloud-logout-btn');
    if (logoutBtn) logoutBtn.onclick = () => {
      bd.remove();
      performCloudLogout();
    };
  }

  function generateWorkoutShareCard(opts) {
    return new Promise(resolve => {
      try {
        const c = document.createElement('canvas');
        c.width = 1080;
        c.height = 1350;
        const g = c.getContext('2d');
        if (!g) return resolve(null);

        const rr = (x, y, w, h, r) => {
          g.beginPath();
          g.moveTo(x + r, y);
          g.arcTo(x + w, y, x + w, y + h, r);
          g.arcTo(x + w, y + h, x, y + h, r);
          g.arcTo(x, y + h, x, y, r);
          g.arcTo(x, y, x + w, y, r);
          g.closePath();
        };

        const bg = g.createLinearGradient(0, 0, 1080, 1350);
        bg.addColorStop(0, '#0B0E14');
        bg.addColorStop(1, '#141B29');
        g.fillStyle = bg;
        g.fillRect(0, 0, 1080, 1350);

        const glow1 = g.createRadialGradient(220, 220, 20, 220, 220, 480);
        glow1.addColorStop(0, 'rgba(45, 212, 191, 0.22)');
        glow1.addColorStop(1, 'rgba(45, 212, 191, 0)');
        g.fillStyle = glow1;
        g.fillRect(0, 0, 1080, 1350);

        const glow2 = g.createRadialGradient(880, 1100, 20, 880, 1100, 460);
        glow2.addColorStop(0, 'rgba(240, 168, 48, 0.18)');
        glow2.addColorStop(1, 'rgba(240, 168, 48, 0)');
        g.fillStyle = glow2;
        g.fillRect(0, 0, 1080, 1350);

        rr(48, 48, 984, 1254, 44);
        g.fillStyle = 'rgba(255, 255, 255, 0.03)';
        g.fill();
        g.lineWidth = 2;
        g.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        g.stroke();

        g.fillStyle = '#F8FAFC';
        g.font = '800 42px sans-serif';
        g.fillText((CFG.brand || 'FLEXA').toUpperCase(), 96, 132);

        g.fillStyle = '#8E97A4';
        g.font = '600 28px sans-serif';
        g.textAlign = 'right';
        g.fillText(new Date().toLocaleDateString(L, { day: 'numeric', month: 'short', year: 'numeric' }), 984, 130);
        g.textAlign = 'left';

        g.fillStyle = '#2DD4BF';
        g.font = '800 26px sans-serif';
        g.fillText(L == 'ru' ? 'ТРЕНИРОВКА ЗАВЕРШЕНА' : 'WORKOUT COMPLETE', 96, 255);

        g.fillStyle = '#FFFFFF';
        g.font = '800 58px sans-serif';
        const words = String(opts.title || 'Workout').split(/\s+/);
        let line = '', lines = [];
        for (const wd of words) {
          const test = line ? line + ' ' + wd : wd;
          if (g.measureText(test).width > 880 && line) {
            lines.push(line);
            line = wd;
          } else line = test;
        }
        if (line) lines.push(line);
        lines.slice(0, 2).forEach((ln, idx) => g.fillText(ln, 96, 330 + idx * 72));

        const stats = [
          { v: `${opts.mins} ${L == 'ru' ? 'мин' : 'min'}`, l: L == 'ru' ? 'ДЛИТЕЛЬНОСТЬ' : 'DURATION', c: '#F8FAFC' },
          { v: opts.vol > 0 ? `${opts.vol.toLocaleString()} ${L == 'ru' ? 'кг' : 'kg'}` : `~${opts.kcal} ${L == 'ru' ? 'ккал' : 'kcal'}`, l: opts.vol > 0 ? (L == 'ru' ? 'ТОННАЖ' : 'VOLUME') : (L == 'ru' ? 'РАСХОД' : 'BURNED'), c: '#2DD4BF' },
          { v: String(opts.reps || opts.ex), l: opts.reps ? (L == 'ru' ? 'ПОВТОРЕНИЙ' : 'REPS') : (L == 'ru' ? 'УПРАЖНЕНИЙ' : 'EXERCISES'), c: '#F8FAFC' },
          { v: `+${opts.xp} XP`, l: L == 'ru' ? 'ОПЫТ' : 'EARNED', c: '#F0A830' }
        ];
        const cardW = 428, cardH = 220, gap = 32, sx = 96, sy = 470;
        stats.forEach((st, idx) => {
          const cx = sx + (idx % 2) * (cardW + gap);
          const cy = sy + Math.floor(idx / 2) * (cardH + gap);
          rr(cx, cy, cardW, cardH, 30);
          g.fillStyle = 'rgba(255, 255, 255, 0.05)';
          g.fill();
          g.lineWidth = 2;
          g.strokeStyle = 'rgba(255, 255, 255, 0.08)';
          g.stroke();

          g.fillStyle = st.c;
          g.font = '800 56px sans-serif';
          g.fillText(st.v, cx + 36, cy + 112);

          g.fillStyle = '#8E97A4';
          g.font = '700 22px sans-serif';
          g.fillText(st.l, cx + 36, cy + 165);
        });

        let badgeY = 995;
        if (opts.streak > 0) {
          rr(96, badgeY, 888, 74, 24);
          g.fillStyle = 'rgba(240, 168, 48, 0.14)';
          g.fill();
          g.fillStyle = '#F0A830';
          g.font = '800 28px sans-serif';
          g.fillText(L == 'ru' ? `Серия: ${opts.streak} дн. подряд` : `Streak: ${opts.streak} days in a row`, 128, badgeY + 47);
          badgeY += 96;
        }
        if (opts.prsCount > 0) {
          rr(96, badgeY, 888, 74, 24);
          g.fillStyle = 'rgba(45, 212, 191, 0.14)';
          g.fill();
          g.fillStyle = '#2DD4BF';
          g.font = '800 28px sans-serif';
          g.fillText(L == 'ru' ? `Новых рекордов: ${opts.prsCount}` : `New personal records: ${opts.prsCount}`, 128, badgeY + 47);
        }

        g.fillStyle = '#8E97A4';
        g.font = '700 26px sans-serif';
        g.fillText(opts.athlete || 'Athlete', 96, 1235);
        g.textAlign = 'right';
        g.fillText('FLEXA FITNESS', 984, 1235);
        g.textAlign = 'left';

        c.toBlob(blob => resolve(blob), 'image/png');
      } catch (e) {
        resolve(null);
      }
    });
  }

  function getWeekPlan() {
    try {
      const p = JSON.parse(localStorage.weekPlan || '{}');
      return p && typeof p === 'object' ? p : {};
    } catch (e) { return {}; }
  }
  function saveWeekPlan(p) {
    localStorage.weekPlan = JSON.stringify(p || {});
    if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
  }
  function renderWeekPlanCard() {
    const plan = getWeekPlan();
    const todayDow = (new Date().getDay() + 6) % 7;
    const days = L == 'ru' ? ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const todayWid = plan[todayDow];
    const todayW = todayWid ? woMap[todayWid] : null;
    const strip = days.map((lbl, idx) => {
      const hasW = !!(plan[idx] && woMap[plan[idx]]);
      return `<button type="button" class="wp-day ${idx === todayDow ? 'today' : ''} ${hasW ? 'has' : ''}" data-wp-day="${idx}">${lbl}<i></i></button>`;
    }).join('');
    return `
      <div class="ss-card wp-card">
        <div class="ss-card-title">
          <b>${L == 'ru' ? 'План на неделю' : 'Weekly Plan'}</b>
          <button type="button" class="duel-rules-btn" id="wp-edit-btn">${L == 'ru' ? 'Настроить' : 'Edit'}</button>
        </div>
        <div class="wp-strip">${strip}</div>
        <div class="wp-today-row">
          <div class="wp-today-info">
            <small>${L == 'ru' ? 'Сегодня' : 'Today'} (${days[todayDow]})</small>
            <b>${todayW ? esc(woName(todayW)) : (L == 'ru' ? 'День отдыха / свободный выбор' : 'Rest day / free pick')}</b>
          </div>
          ${todayW
            ? `<a href="#/workout/${esc(todayW.id)}" class="btn" style="padding:7px 12px;font-size:11.5px;white-space:nowrap;">▶ ${t('startShort')}</a>`
            : `<a href="#/workouts" class="btn alt" style="padding:7px 12px;font-size:11.5px;white-space:nowrap;">${L == 'ru' ? 'Выбрать' : 'Browse'}</a>`}
        </div>
      </div>`;
  }

    const routes = {
    home() {
      const S = CFG.sections || {};
      const on = k => S[k] !== false;
      const star = D.programs.filter(p => p.img).slice(0, 6);
      const top = D.workouts.filter(w => w.t.ru || w.t.en).sort((a, b) => b.rating - a.rating).slice(0, 10);
      const allH = hist();
      const streak = calcStreak(allH);
      const wk = Date.now() - 7 * 864e5, h = allH.filter(x => x.t > wk);
      const goal = Math.max(1, +CFG.goal || 5), pct = Math.min(100, Math.round(h.length / goal * 100));
      const mins = Math.round(h.reduce((s, x) => s + x.s, 0) / 60);
      const hp = D.programs.find(p => p.id == CFG.heroProgram) || D.programs.find(p => p.img) || star[0];
      const heroT = (CFG.heroTitle && CFG.heroTitle[L]) || pName(hp);
      const heroLink = CFG.heroLink || ('#/program/' + hp.id);
      const calEstimate = allH.length ? Math.max(40, mins * 7 + h.length * 90) : 0;
      const lastH = allH.length ? allH[allH.length - 1] : null;
      const lastW = lastH ? woMap[lastH.id] : null;
      let locAth = {};
      try { locAth = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
      const ath = window.AthleteProfile ? window.AthleteProfile.merge(Object.assign({}, CFG.athlete || {}, locAth), {
        workoutsCount: allH.length,
        streak,
        prsCount: Object.keys(JSON.parse(localStorage.prs || '{}')).length,
        uniqueDays: new Set(allH.map(x => new Date(x.t).toISOString().slice(0, 10))).size,
        weekPct: allH.length ? pct : null
      }) : { winRate: 0, level: 1, days: 0, streakDays: 0, points: 0 };

      const now = new Date(), currentDay = (now.getDay() + 6) % 7;
      const dayNames = L == 'ru' ? ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      const minsByDate = {};
      allH.forEach(x => {
        const iso = new Date(x.t).toISOString().slice(0, 10);
        minsByDate[iso] = (minsByDate[iso] || 0) + Math.max(1, Math.round((x.s || 0) / 60));
      });
      const weekDates = [];
      for (let d = 0; d < 7; d++) {
        const target = new Date(now); target.setDate(now.getDate() - currentDay + d);
        weekDates.push(target.toISOString().slice(0, 10));
      }
      const maxWeekMin = Math.max(20, ...weekDates.map(iso => minsByDate[iso] || 0));
      const weekBars = dayNames.map((lbl, d) => {
        const iso = weekDates[d];
        const dayMin = minsByDate[iso] || 0;
        const isDone = dayMin > 0, isToday = d === currentDay;
        const pctH = isDone ? Math.max(32, Math.min(96, Math.round((dayMin / maxWeekMin) * 94))) : (isToday ? 22 : 14);
        return { lbl, isDone, isToday, pctH, gold: isDone && isToday };
      });

      const recent5 = allH.slice(-5);
      const maxPaceMin = Math.max(15, ...recent5.map(x => Math.max(1, Math.round((x.s || 0) / 60))));
      const paceBars = [0, 1, 2, 3, 4].map(idx => {
        const item = recent5[idx];
        if (!item) return { pct: 12, empty: true };
        const m = Math.max(1, Math.round((item.s || 0) / 60));
        return { pct: Math.max(24, Math.min(100, Math.round((m / maxPaceMin) * 100))), empty: false };
      });
      const avgPace = allH.length ? Math.max(1, Math.round(mins / allH.length)) : 0;

      // Build honest 7-day curve points from real history
      const curveDates = [];
      for (let d = 6; d >= 0; d--) {
        const dt = new Date(now); dt.setDate(now.getDate() - d);
        curveDates.push(dt.toISOString().slice(0, 10));
      }
      const curveVals = curveDates.map(iso => minsByDate[iso] || 0);
      const maxCurve = Math.max(30, ...curveVals);
      const ptsGold = curveVals.map((v, idx) => [Math.round((idx / 6) * 800), Math.round(108 - (v / maxCurve) * 88)]);
      let cum = 0;
      const maxCum = Math.max(30, curveVals.reduce((a, b) => a + b, 0));
      const ptsGreen = curveVals.map((v, idx) => {
        cum += v;
        return [Math.round((idx / 6) * 800), Math.round(110 - (cum / maxCum) * 86)];
      });
      const toPath = pts => pts.map((p, idx) => (idx === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
      const goldLine = toPath(ptsGold);
      const goldArea = `${goldLine} L800,120 L0,120 Z`;
      const greenLine = toPath(ptsGreen);

      const isPro = isUserPro();
      const quickRows = top.slice(0, 4).map(w => {
        const isProW = isProWorkout(w);
        const lock = isProW && !isPro;
        return `
        <a class="ss-table-row" href="#/workout/${w.id}">
          <span class="ss-row-ic" style="color:var(--ac);">${uiSvg('dumbbell', 16)}</span>
          <span class="ss-row-name">${esc(woName(w))}</span>
          <span class="ss-row-meta">${lock ? '<span class="tag pro" style="font-size:10px;padding:2px 6px;margin-right:4px;">🔒 PRO</span>' : ''}★ ${w.rating || '4.9'}</span>
          <span class="ss-row-play">${lock ? '🔒' : '▶'}</span>
        </a>`;
      }).join('');

      return `
      <div class="frosted-search">
        <i>${uiSvg('bolt', 15)}</i>
        <input id="hsearch" placeholder="${L == 'ru' ? 'Поиск тренировок, упражнений и программ…' : 'Search workouts, exercises, programs…'}">
      </div>
      ${lastW ? `
      <div class="last-workout-chip">
        <div class="lw-info">
          <small>${uiSvg('bolt', 11)} ${L == 'ru' ? 'ПРОДОЛЖИТЬ ПОСЛЕДНЮЮ ТРЕНИРОВКУ' : 'RESUME RECENT WORKOUT'}</small>
          <b>${esc(woName(lastW))}</b>
        </div>
        <a class="lw-btn" href="#/workout/${lastW.id}">▶ ${t('startShort')}</a>
      </div>` : ''}

      ${COACH.enabled && !(CFG.hidden || []).includes('coach') ? `
      <a class="coachcard" href="#/coach" id="home-coach-card">
        <div class="orb sm"><span>AI</span></div>
        <div class="coachcard-copy">
          <div class="coachcard-top">
            <b>${esc(t('coachBanner'))}</b>
            <span class="coachcard-badge">AI</span>
          </div>
          <small>${esc(t('coachSub'))}</small>
        </div>
        <span class="go" aria-hidden="true">›</span>
      </a>` : ''}

      <div class="ss-bento">
        <div class="ss-card ss-viability">
          <div class="ss-card-title"><b>${L == 'ru' ? 'Готовность атлета' : 'Athlete Readiness'}</b><span>Lv.${ath.level}</span></div>
          <div class="ss-viability-body">
            ${(() => {
              const rPct = allH.length ? pct : (ath.winRate || 0);
              const rOff = (251.33 * (1 - Math.min(100, Math.max(0, rPct)) / 100)).toFixed(1);
              return `
              <div class="ss-medallion">
                <svg class="ss-ring-svg" viewBox="0 0 100 100" aria-hidden="true">
                  <defs>
                    <linearGradient id="ssRingGrad" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stop-color="#F8C96C"/>
                      <stop offset="55%" stop-color="#F0A830"/>
                      <stop offset="100%" stop-color="#2DD4BF"/>
                    </linearGradient>
                  </defs>
                  <circle class="ss-ring-bg" cx="50" cy="50" r="40"/>
                  <circle class="ss-ring-fg" cx="50" cy="50" r="40" stroke="url(#ssRingGrad)" style="stroke-dasharray:251.33;stroke-dashoffset:${rOff};"/>
                </svg>
                <div class="ss-medallion-core">
                  <b>${rPct}%</b>
                  <small>${L == 'ru' ? 'Цель' : 'Goal'}</small>
                </div>
              </div>`;
            })()}
            <div>
              <div class="ss-sub-metrics">
                <div class="ss-sub-m"><small>${L == 'ru' ? 'Неделя' : 'Weekly'}</small><b>${h.length}/${goal}</b></div>
                <div class="ss-sub-m"><small>${L == 'ru' ? 'Калории' : 'Burned'}</small><b>${calEstimate}</b></div>
              </div>
              <div class="ss-spec-list">
                <div class="ss-spec-row"><span>${L == 'ru' ? 'Вынос.' : 'Endurance'}</span><b class="g">${allH.length ? Math.min(99, 60 + ath.level * 3) : 0}%</b></div>
                <div class="ss-spec-row"><span>${L == 'ru' ? 'Серия' : 'Streak'}</span><b class="y">${streak} ${t('days')}</b></div>
                <div class="ss-spec-row"><span>${L == 'ru' ? 'Баланс' : 'XP'}</span><b>${Math.round(ath.points).toLocaleString()}</b></div>
              </div>
            </div>
          </div>
        </div>

        <div class="ss-kpi-pair">
          <div class="ss-card">
            <div class="ss-card-title"><b>${L == 'ru' ? 'Тренировки' : 'Workouts'}</b><span style="color:var(--ac);">${uiSvg('bolt', 13)}</span></div>
            <div class="ss-kpi-big">
              <div class="num">${allH.length}<span>/${goal}</span></div>
              <span class="tag ${h.length ? 'pro' : ''}">${h.length ? (L == 'ru' ? 'Актив' : 'Active') : (L == 'ru' ? 'Старт' : 'Start')}</span>
            </div>
            <div class="ss-kpi-foot"><span>${L == 'ru' ? '7 дн' : '7d'}: ${h.length}</span><span>+${h.length * 150} XP</span></div>
          </div>
          <div class="ss-card">
            <div class="ss-card-title"><b>${L == 'ru' ? 'Время' : 'Time'}</b><span style="color:var(--mut);">${uiSvg('clock', 13)}</span></div>
            <div class="ss-kpi-big">
              <div class="num">${mins}<span>m</span></div>
              <span class="tag">${L == 'ru' ? 'Всего' : 'Total'}</span>
            </div>
            <div class="ss-kpi-foot"><span>${L == 'ru' ? 'Дней' : 'Days'}: ${Object.keys(minsByDate).length}</span><span style="display:inline-flex;align-items:center;gap:3px;">${uiSvg('flame', 12)} ${streak}</span></div>
          </div>
        </div>

        <div class="ss-mid-charts">
          <div class="ss-card">
            <div class="ss-card-title"><b>${L == 'ru' ? 'Темп' : 'Pace'}</b></div>
            <div style="font-size:22px;font-weight:900;color:var(--tx);line-height:1;">${avgPace} <small style="font-size:11px;color:var(--mut);font-weight:700;">${L == 'ru' ? 'мин' : 'min'}</small></div>
            <div class="ss-mini-bars">
              ${paceBars.map(b => `<i class="${b.empty ? 'empty' : ''}" style="height:${b.pct}%"></i>`).join('')}
            </div>
          </div>
          ${on('activity') ? `
          <div class="ss-card">
            <div class="ss-card-title"><b>${L == 'ru' ? 'Нагрузка' : 'Load'}</b><span>${h.length}/${goal}</span></div>
            <div class="ss-pill-bars">
              ${weekBars.map(b => `
                <div class="ss-pbar-col ${b.isToday ? 'today' : ''}">
                  <div class="ss-pbar ${b.gold ? 'gold' : ''} ${b.isDone ? '' : 'empty'}" style="height:${b.pctH}%"></div>
                  <small>${b.lbl}</small>
                </div>
              `).join('')}
            </div>
          </div>` : ''}
        </div>

        ${on('hero') ? (() => {
          const ps = getProgState();
          const activeP = ps.activeId ? D.programs.find(p => p.id == ps.activeId) : null;
          const useP = activeP || hp;
          const pDone = (ps.logs[useP.id] || []).length;
          const pTot = Math.max(1, +useP.days || 30);
          const hTitle = activeP ? pName(activeP) : heroT;
          const hLink = activeP ? ('#/program/' + activeP.id) : heroLink;
          const hTop = activeP ? (L == 'ru' ? 'Моя программа' : 'My Program') : t('potd');
          return `
          <div class="ss-card ss-droplet-card ss-droplet-wide">
            <div class="ss-droplet-info">
              <div class="ss-card-title" style="margin-bottom:6px"><b>${esc(hTop)}</b><span>${activeP ? uiSvg('pin', 12) : '★'}</span></div>
              <div style="font-size:17px;font-weight:800;color:var(--tx);line-height:1.25;margin-bottom:8px;">${esc(hTitle)}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;">
                <span class="tag">${useP.days ? (pDone ? `${pDone}/${useP.days} ${t('days')}` : `${useP.days} ${t('days')}`) : '30 min'}</span>
                <span class="tag">${tempLbl(useP.temp) || '30 min'}</span>
              </div>
              <a href="${esc(hLink)}" class="btn" style="padding:9px 16px;font-size:13px;">▶ ${activeP ? (L == 'ru' ? 'Продолжить' : 'Continue') : t('startShort')}</a>
            </div>
            ${(() => {
              const pArc = useP.days ? Math.max(0.18, Math.min(1, pDone / pTot)) : 0.72;
              const pOff = (226.2 * (1 - pArc)).toFixed(1);
              return `
              <a href="${esc(hLink)}" class="ss-droplet-ring">
                <svg class="ss-prog-ring" viewBox="0 0 88 88" aria-hidden="true">
                  <circle class="ss-ring-bg" cx="44" cy="44" r="36"/>
                  <circle class="ss-ring-fg" cx="44" cy="44" r="36" stroke="${activeP ? '#2DD4BF' : '#F0A830'}" style="stroke-dasharray:226.2;stroke-dashoffset:${pOff};"/>
                </svg>
                <span class="ss-droplet-core">
                  <b>${useP.days ? (pDone ? `${pDone}/${useP.days}` : useP.days + 'd') : '30m'}</b>
                  <small>▶ ${t('open')}</small>
                </span>
              </a>`;
            })()}
          </div>`;
        })() : ''}

        ${renderWeekPlanCard()}

        ${on('quick') ? `
        <div class="ss-card">
          <div class="ss-card-title"><b>${esc(t('quick'))}</b><a href="#/workouts" style="color:var(--ac)">${t('seeAll')} ›</a></div>
          <div class="ss-table-list">${quickRows}</div>
        </div>` : ''}

        <div class="ss-card ss-curve-card">
          <div class="ss-card-title">
            <b>${L == 'ru' ? 'Кривая прогресса (7 дней)' : 'Progress Curve (7d)'}</b>
            ${COACH.enabled ? `<a href="#/coach" style="color:var(--green);font-weight:800;display:inline-flex;align-items:center;gap:4px;">${uiSvg('sparkles', 13)} ${esc(t('coachBanner'))} ›</a>` : `<span>${allH.length ? `${mins} ${L == 'ru' ? 'мин' : 'min'}` : (L == 'ru' ? 'Нет данных' : 'No data')}</span>`}
          </div>
          ${allH.length ? `
            <svg class="ss-curve-svg" viewBox="0 0 800 120" preserveAspectRatio="none">
              <defs>
                <linearGradient id="gcGold" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#F0A830" stop-opacity="0.28"/>
                  <stop offset="100%" stop-color="#F0A830" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <g stroke="rgba(255,255,255,0.06)" stroke-width="1">
                <line x1="0" y1="30" x2="800" y2="30"/><line x1="0" y1="60" x2="800" y2="60"/><line x1="0" y1="90" x2="800" y2="90"/>
                <line x1="160" y1="0" x2="160" y2="120"/><line x1="320" y1="0" x2="320" y2="120"/><line x1="480" y1="0" x2="480" y2="120"/><line x1="640" y1="0" x2="640" y2="120"/>
              </g>
              <path d="${goldArea}" fill="url(#gcGold)"/>
              <path d="${goldLine}" fill="none" stroke="#F0A830" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="${greenLine}" fill="none" stroke="#2DD4BF" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>` : `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px;background:var(--card-inset);border:1px solid var(--line);border-radius:12px;">
              <span style="font-size:12px;color:var(--mut);">${L == 'ru' ? 'Завершите первую тренировку, чтобы увидеть реальный график роста.' : 'Complete your first workout to track real progress.'}</span>
              <a href="#/workouts" class="btn" style="padding:7px 12px;font-size:11.5px;white-space:nowrap;">▶ ${t('startShort')}</a>
            </div>`}
        </div>
      </div>

      ${on('featured') ? `<h2>${t('prev')}<a href="#/workouts/programs">${esc(t('seeAll'))}</a></h2><div class="grid">${star.map(programCard).join('')}</div>` : ''}`;
    },
    coach() {
      if (!COACH.enabled) return `<h1 style="display:flex;align-items:center;gap:8px;">${uiSvg('sparkles', 22)} ${esc(t('coachTitle'))}</h1><div class="empty">${esc(t('coachOff'))}</div>`;
      return `<div class="chat"><div class="chat-head"><div class="orb"><span>AI</span></div><h1>${esc(t('coachTitle'))}</h1><p>${esc(t('coachSub'))}</p></div>
      <div class="chips" id="chips">${['c1', 'c2', 'c3', 'c4'].map(k => `<button type="button" class="chip2" data-q="${esc(t(k))}">${esc(t(k))}</button>`).join('')}</div>
      <div class="msgs" id="msgs"></div>
      <form class="composer" id="cform"><input id="cin" placeholder="${esc(t('coachPh'))}" autocomplete="off" maxlength="1000"><button type="submit" class="send" aria-label="send">➤</button></form>
      <div class="chat-foot"><button type="button" class="btn alt" id="cclr" style="padding:6px 14px;font-size:12px">${esc(t('coachClear'))}</button></div></div>`;
    },
    programs(arg) {
      return routes.workouts('programs');
    },
    program(id) {
      const p = D.programs.find(x => x.id == id); if (!p) return '';
      const ps = getProgState();
      const logs = Array.isArray(ps.logs[p.id]) ? ps.logs[p.id] : [];
      const totalDays = Math.max(1, +p.days || 30);
      const pct = Math.min(100, Math.round((logs.length / totalDays) * 100));
      const isAct = String(ps.activeId) === String(p.id);
      const todayIso = new Date().toISOString().slice(0, 10);
      const doneToday = logs.includes(todayIso);
      const isPro = isUserPro();
      const rawDesc = p.d[L] || p.d.en || '';

      if (isPro) {
        const d = richDesc(rawDesc);
        return `<a href="#/workouts/programs">← ${t('programs')}</a><h1>${esc(pName(p))}</h1>
        <div class="tags"><span class="tag">${p.days} ${t('days')}</span><span class="tag">${t('pace')}: ${tempLbl(p.temp)}</span><span class="tag pro" style="background:linear-gradient(135deg,var(--acc),#f59e0b);color:#000;font-weight:900;">PRO</span></div>
        ${p.img ? `<p><img src="${pImg(p)}" style="width:100%;max-height:360px;object-fit:cover;border-radius:16px"></p>` : ''}
        <div class="ss-card prog-tracker">
          <div class="ss-card-title">
            <b>${uiSvg('trend', 15)} ${L == 'ru' ? 'Прогресс программы' : 'Program Progress'}</b>
            <span style="color:var(--ac-l);font-weight:800;">${logs.length} / ${totalDays} ${t('days')} (${pct}%)</span>
          </div>
          <div class="prog-bar-track"><div class="prog-bar-fill" style="width:${pct}%"></div></div>
          <div class="prog-actions">
            <button type="button" class="btn ${isAct ? 'alt' : ''}" id="prog-pin" data-pid="${p.id}">${isAct ? uiSvg('check', 14) + ' ' + (L == 'ru' ? 'Активная программа' : 'Active program') : uiSvg('pin', 14) + ' ' + (L == 'ru' ? 'Сделать моей' : 'Set as active')}</button>
            <button type="button" class="btn" id="prog-tick" data-pid="${p.id}">${uiSvg('check', 14)} ${doneToday ? (L == 'ru' ? `Ещё день (#${logs.length + 1})` : `Log day #${logs.length + 1}`) : (L == 'ru' ? `День #${logs.length + 1} выполнен` : `Complete day #${logs.length + 1}`)}</button>
          </div>
          ${logs.length ? `
          <div class="prog-sub-foot">
            <span>${L == 'ru' ? 'Последняя отметка:' : 'Last logged:'} ${logs[logs.length - 1]}</span>
            <div style="display:flex;gap:10px;">
              <button type="button" class="prog-link-btn" id="prog-undo" data-pid="${p.id}">−1</button>
              <button type="button" class="prog-link-btn" id="prog-reset" data-pid="${p.id}">${L == 'ru' ? 'Сброс' : 'Reset'}</button>
            </div>
          </div>` : ''}
        </div>
        <div class="box desc">${d}</div>`;
      }

      // Non-PRO user view:
      const splitted = splitProgramDesc(rawDesc);
      const teaserHtml = richDesc(splitted.teaser, { lockWorkouts: true });
      const lockedHtml = richDesc(splitted.rest, { lockWorkouts: true });

      return `<a href="#/workouts/programs">← ${t('programs')}</a><h1>${esc(pName(p))}</h1>
      <div class="tags"><span class="tag">${p.days} ${t('days')}</span><span class="tag">${t('pace')}: ${tempLbl(p.temp)}</span><span class="tag pro" style="background:rgba(245,158,11,0.18);color:var(--acc);border:1px solid rgba(245,158,11,0.35);font-weight:900;">🔒 PRO ПРОГРАММА</span></div>
      ${p.img ? `<p><img src="${pImg(p)}" style="width:100%;max-height:360px;object-fit:cover;border-radius:16px"></p>` : ''}
      <div class="ss-card prog-lock-box">
        <div class="prog-lock-badge">${uiSvg('bolt', 12)} PRO PROGRAM</div>
        <div class="prog-lock-head">
          <div class="prog-lock-icon">${uiSvg('bolt', 24)}</div>
          <div>
            <div class="prog-lock-title">${L == 'ru' ? 'Программа доступна в RizzaFit PRO' : 'Available with RizzaFit PRO'}</div>
            <div class="prog-lock-sub">${L == 'ru' ? 'Отслеживание дней, готовое расписание тренировок и пошаговый прогресс' : 'Daily tracking, workout logs and progression'}</div>
          </div>
        </div>
        <div class="prog-lock-feats">
          <div class="prog-lock-feat">${uiSvg('check', 13)} ${L == 'ru' ? 'Полный доступ к курсу на ' + p.days + ' дней' : 'Full access to ' + p.days + ' days'}</div>
          <div class="prog-lock-feat">${uiSvg('check', 13)} ${L == 'ru' ? 'Умная отметка выполненных дней и аналитика' : 'Day progression tracking'}</div>
          <div class="prog-lock-feat">${uiSvg('check', 13)} ${L == 'ru' ? 'Оплата через СБП в 1 клик (от 290 ₽)' : 'Instant SBP payment (from 290 ₽)'}</div>
        </div>
        <button type="button" class="btn block prog-unlock-btn" id="prog-unlock-btn">
          ${uiSvg('bolt', 15)} ${L == 'ru' ? 'Разблокировать программу через СБП' : 'Unlock program with PRO'}
        </button>
      </div>
      <div class="box desc" style="margin-bottom:12px;">${teaserHtml}</div>
      <div class="prog-desc-wrap-locked">
        <div class="prog-desc-locked-content">${lockedHtml}</div>
        <div class="prog-plan-lock-overlay" id="prog-desc-lock-overlay">
          <div class="prog-lock-icon" style="margin-bottom:8px;">${uiSvg('bolt', 26)}</div>
          <div style="font-weight:900;font-size:16px;color:var(--tx);margin-bottom:6px;">
            ${L == 'ru' ? 'План тренировок на ' + p.days + ' дней заблокирован' : p.days + '-Day Workout Schedule Locked'}
          </div>
          <div style="font-size:12.5px;color:var(--mut);line-height:1.45;margin-bottom:14px;max-width:320px;">
            ${L == 'ru'
              ? 'Оформите подписку RizzaFit PRO, чтобы открыть расписание всех дней, входящие тренировки и отслеживание прогресса.'
              : 'Upgrade to PRO to unlock the entire day schedule, workouts and tracking.'}
          </div>
          <button type="button" class="btn prog-unlock-btn" id="prog-unlock-desc-btn" style="padding:10px 20px;font-size:13.5px;">
            ${uiSvg('bolt', 14)} ${L == 'ru' ? 'Разблокировать от 290 ₽' : 'Unlock from 290 ₽'}
          </button>
        </div>
      </div>`;
    },
    workouts(tab) {
      const isProg = tab === 'programs';
      return `
      <div class="wo-head-row">
        <div class="act-seg wo-main-seg">
          <button type="button" class="act-seg-btn ${isProg ? '' : 'on'}" id="wo-tab-workouts">
            ${uiSvg('dumbbell', 13)} <span>${t('workouts')}</span>
          </button>
          <button type="button" class="act-seg-btn ${isProg ? 'on' : ''}" id="wo-tab-programs">
            ${uiSvg('flame', 13)} <span>${t('programs')}</span>
          </button>
        </div>
        <a href="#/builder" class="btn wo-build-btn" id="wo-builder-btn" style="${isProg ? 'display:none;' : ''}">＋ ${L == 'ru' ? 'Собрать свою' : 'Build custom'}</a>
      </div>
      <div id="wo-sec-workouts" style="${isProg ? 'display:none;' : ''}">
        <div class="muscle-pills" id="m-pills">
          <button class="mpill on" data-m="">${t('all')}</button>
          <button class="mpill" data-m="mine">${uiSvg('sparkles', 13)} ${L == 'ru' ? 'Мои' : 'Mine'}</button>
          <button class="mpill" data-m="fav">${uiSvg('heartFill', 13)} ${L == 'ru' ? 'Избранное' : 'Favorites'}</button>
          <button class="mpill" data-m="chest">${L == 'ru' ? 'Грудь' : 'Chest'}</button>
          <button class="mpill" data-m="back">${L == 'ru' ? 'Спина' : 'Back'}</button>
          <button class="mpill" data-m="abs">${L == 'ru' ? 'Пресс' : 'Abs'}</button>
          <button class="mpill" data-m="arms">${L == 'ru' ? 'Руки' : 'Arms'}</button>
          <button class="mpill" data-m="legs">${L == 'ru' ? 'Ноги' : 'Legs'}</button>
          <button class="mpill" data-m="full">${uiSvg('bolt', 13)} ${L == 'ru' ? 'Все тело' : 'Full body'}</button>
        </div>
        <div class="filters"><input id="q" placeholder="${L == 'ru' ? 'Поиск по названию или упражнению…' : 'Search workout or exercise…'}">
        <select id="f-eq"><option value="">${t('eq')}: ${t('all')}</option>${[...new Set(D.workouts.map(w => w.eq))].filter(Boolean).map(v => `<option value="${v}">${eqLbl(v)}</option>`).join('')}</select>
        <select id="f-d"><option value="">${t('diff')}: ${t('all')}</option>${[...new Set(D.workouts.map(w => w.diff))].filter(Boolean).map(v => `<option value="${v}">${diffLbl(v)}</option>`).join('')}</select>
        <label style="align-self:center;color:var(--mut)"><input type="checkbox" id="f-t" checked> ${L == 'ru' ? 'только именованные' : 'named only'}</label></div>
        <div id="list" class="grid"></div><div class="more" id="more"></div>
      </div>
      <div id="wo-sec-programs" style="${isProg ? '' : 'display:none;'}">
        <div style="font-size:12.5px;color:var(--mut);margin:4px 2px 14px;line-height:1.4;">
          ${L == 'ru' ? 'Готовые долгосрочные программы тренировок с прогрессией по дням:' : 'Structured training programs with day-by-day progression:'}
        </div>
        <div class="grid">${D.programs.map(programCard).join('')}</div>
      </div>`;
    },
    builder(editId) {
      const isDup = editId && String(editId).startsWith('dup-');
      const srcId = isDup ? String(editId).slice(4) : editId;
      const cur = !isDup && editId && woMap[editId] && woMap[editId]._custom ? woMap[editId] : null;
      const src = cur || (isDup && woMap[srcId] ? woMap[srcId] : null);
      const rounds = src && src.s && src.s[0] ? (src.s[0][0] || 3) : 3;
      const rb = src ? (src.rb ?? 20) : 20;
      const eq = src ? (src.eq || 'no_equipment') : 'no_equipment';
      const title = cur ? woName(cur) : (src ? `${woName(src)} (${L == 'ru' ? 'копия' : 'copy'})` : '');
      return `
        <a href="#/workouts">← ${t('workouts')}</a>
        <h1 style="margin-top:8px;">${uiSvg('settings', 18)} ${cur ? (L == 'ru' ? 'Редактировать тренировку' : 'Edit Custom Workout') : (L == 'ru' ? 'Конструктор тренировки' : 'Workout Builder')}</h1>
        <div class="ss-card cb-card">
          <label class="cb-lbl">${L == 'ru' ? 'Название тренировки' : 'Workout title'}
            <input id="cb-title" value="${esc(title)}" placeholder="${L == 'ru' ? 'Например: Утренний пресс и отжимания' : 'e.g. Morning Push & Core'}">
          </label>
          <div class="cb-opts-grid">
            <label class="cb-lbl">${t('eq')}
              <select id="cb-eq">
                <option value="no_equipment" ${eq === 'no_equipment' ? 'selected' : ''}>${eqLbl('no_equipment')}</option>
                <option value="home_gym" ${eq === 'home_gym' ? 'selected' : ''}>${eqLbl('home_gym')}</option>
                <option value="full_gym" ${eq === 'full_gym' ? 'selected' : ''}>${eqLbl('full_gym')}</option>
              </select>
            </label>
            <label class="cb-lbl">${L == 'ru' ? 'Кругов' : 'Rounds'}
              <select id="cb-rounds">
                ${[1, 2, 3, 4, 5].map(n => `<option value="${n}" ${rounds === n ? 'selected' : ''}>× ${n}</option>`).join('')}
              </select>
            </label>
            <label class="cb-lbl">${L == 'ru' ? 'Отдых' : 'Rest'}
              <select id="cb-rest">
                ${[10, 15, 20, 30, 45, 60].map(sec => `<option value="${sec}" ${rb === sec ? 'selected' : ''}>${sec} ${t('sec')}</option>`).join('')}
              </select>
            </label>
          </div>
          <div class="cb-summary" id="cb-summary"></div>
        </div>

        <h2 style="margin-top:16px;">${uiSvg('trend', 16)} ${L == 'ru' ? 'Выбранные упражнения' : 'Selected Exercises'}</h2>
        <div id="cb-picked" class="cb-picked-list"></div>

        <div class="cb-save-bar">
          <button type="button" class="btn alt" id="cb-save">${uiSvg('download', 14)} ${L == 'ru' ? 'Сохранить' : 'Save'}</button>
          <button type="button" class="btn" id="cb-save-play">${uiSvg('play', 14)} ${L == 'ru' ? 'Сохранить и начать' : 'Save & Start'}</button>
        </div>

        <h2 style="margin-top:20px;">${uiSvg('plus', 16)} ${L == 'ru' ? 'Добавить из базы упражнений' : 'Add from Exercise Library'}</h2>
        <div class="cb-lib-box ss-card">
          <input id="cb-q" class="cb-search" placeholder="${L == 'ru' ? 'Поиск упражнения…' : 'Search exercise…'}">
          <div class="muscle-pills" id="cb-pills" style="margin:8px 0 6px;padding-bottom:4px;">
            <button type="button" class="mpill on" data-cm="">${t('all')}</button>
            <button type="button" class="mpill" data-cm="chest">${L == 'ru' ? 'Грудь' : 'Chest'}</button>
            <button type="button" class="mpill" data-cm="back">${L == 'ru' ? 'Спина' : 'Back'}</button>
            <button type="button" class="mpill" data-cm="abs">${L == 'ru' ? 'Пресс' : 'Abs'}</button>
            <button type="button" class="mpill" data-cm="arms">${L == 'ru' ? 'Руки' : 'Arms'}</button>
            <button type="button" class="mpill" data-cm="shoulders">${L == 'ru' ? 'Плечи' : 'Shoulders'}</button>
            <button type="button" class="mpill" data-cm="legs">${L == 'ru' ? 'Ноги' : 'Legs'}</button>
          </div>
          <div id="cb-lib" class="cb-lib-list"></div>
        </div>
      `;
    },
    workout(id) {
      const w = woMap[id]; if (!w) return '';
      let num = 0;
      const secs = woSeconds(w);
      const isPro = isUserPro();
      const needsPro = isProWorkout(w);
      const isLocked = needsPro && !isPro;

      let sets;
      if (isLocked) {
        let count = 0;
        const previewSets = [];
        const lockedSets = [];
        w.s.forEach((s, i) => {
          const prevItems = [];
          const lockItems = [];
          s.slice(1).forEach(n => {
            count++;
            const e = exMap[n[0]];
            if (count <= 2) {
              prevItems.push(`<div class="item"><span class="num">${count}</span><span class="th">${e && e.img ? exImg(e) : '💪'}</span><span class="nm">${esc(e ? exName(e) : '#' + n[0])}<small>${n[2]} ${n[1] == 'second' ? t('sec') : n[1] == 'repeat' ? t('rep') : n[1]}</small></span><span class="go">🔒</span></div>`);
            } else {
              lockItems.push(`<div class="item"><span class="num">${count}</span><span class="th">${e && e.img ? exImg(e) : '💪'}</span><span class="nm">${esc(e ? exName(e) : '#' + n[0])}<small>${n[2]} ${n[1] == 'second' ? t('sec') : n[1] == 'repeat' ? t('rep') : n[1]}</small></span><span class="go">🔒</span></div>`);
            }
          });
          if (prevItems.length) {
            previewSets.push(`<h4>${t('set')} ${i + 1}<small>${s[0] > 1 ? '× ' + s[0] : ''}</small></h4>${prevItems.join('')}`);
          }
          if (lockItems.length) {
            lockedSets.push(`<h4>${t('set')} ${i + 1}<small>${s[0] > 1 ? '× ' + s[0] : ''}</small></h4>${lockItems.join('')}`);
          }
        });

        sets = `
          <div class="wo-plan-preview">${previewSets.join('')}</div>
          <div class="wo-plan-locked-wrap" id="wo-plan-locked-wrap">
            <div class="wo-plan-locked-preview">${lockedSets.join('')}</div>
            <div class="wo-lock-overlay" id="wo-lock-overlay">
              <div class="prog-lock-icon" style="margin-bottom:8px;">${uiSvg('bolt', 24)}</div>
              <div style="font-weight:800;font-size:15px;color:var(--tx);margin-bottom:4px;">
                ${L == 'ru' ? 'Полный комплекс доступен в PRO' : 'Full workout available with PRO'}
              </div>
              <div style="font-size:12px;color:var(--mut);margin-bottom:12px;max-width:300px;line-height:1.4;">
                ${L == 'ru' ? `Разблокируйте все ${count} упражнений, авто-таймер и ведение дневника` : `Unlock all ${count} exercises, auto-timers and progress tracking`}
              </div>
              <button type="button" class="btn prog-unlock-btn" id="wo-unlock-plan" style="padding:10px 18px;font-size:13px;">
                ${uiSvg('bolt', 14)} ${L == 'ru' ? 'Разблокировать через СБП' : 'Unlock via SBP'}
              </button>
            </div>
          </div>
        `;
      } else {
        sets = w.s.map((s, i) => `<h4>${t('set')} ${i + 1}<small>${s[0] > 1 ? '× ' + s[0] : ''}</small></h4>${s.slice(1).map(n => {
          const e = exMap[n[0]]; num++;
          return `<a class="item" href="#/exercise/${n[0]}"><span class="num">${num}</span><span class="th">${e && e.img ? exImg(e) : '💪'}</span><span class="nm">${esc(e ? exName(e) : '#' + n[0])}<small>${n[2]} ${n[1] == 'second' ? t('sec') : n[1] == 'repeat' ? t('rep') : n[1]}</small></span><span class="go">›</span></a>`;
        }).join('')}`).join('');
      }

      return `<a href="#/workouts">← ${t('workouts')}</a>
      <div class="wcover" style="margin-top:12px">
        <div class="tags" style="margin:0 0 6px;align-items:center">
          ${w._custom ? `<span class="tag pro">${uiSvg('sparkles', 12)} ${L == 'ru' ? 'Моя' : 'Custom'}</span>` : ''}
          ${w.eq ? `<span class="tag pro">${eqLbl(w.eq)}</span>` : ''}
          ${needsPro ? (isPro ? '<span class="tag pro">PRO</span>' : '<span class="tag pro" style="background:rgba(245,158,11,0.18);color:var(--acc);border:1px solid rgba(245,158,11,0.35);font-weight:900;">🔒 PRO ТРЕНИРОВКА</span>') : ''}
          <span style="flex:1"></span>
          ${w._custom ? `<a href="#/builder/${esc(w.id)}" class="fav-btn" title="${L == 'ru' ? 'Редактировать' : 'Edit'}">${uiSvg('edit', 15)}</a><button type="button" class="fav-btn" id="wo-del" title="${L == 'ru' ? 'Удалить' : 'Delete'}">${uiSvg('trash', 15)}</button>` : ''}
          <a href="#/builder/dup-${esc(w.id)}" class="fav-btn" title="${L == 'ru' ? 'Копировать в конструктор' : 'Duplicate to builder'}">${uiSvg('repeat', 15)}</a>
          <button class="fav-btn ${getFavs().has(w.id) ? 'on' : ''}" id="fav-toggle" aria-label="favorite">${uiSvg(getFavs().has(w.id) ? 'heartFill' : 'heart', 16)}</button>
        </div>
        <h1>${esc(woName(w))}</h1>
      </div>
      <div class="wstats"><span>${uiSvg('clock', 14)} <b>${Math.max(1, Math.round(secs / 60))} min</b></span><span>${uiSvg('chart', 14)} <b>${diffLbl(w.diff)}</b></span><span>${uiSvg('bolt', 14)} <b>${tempLbl(w.temp)}</b></span>${w.rating ? `<span>★ <b>${w.rating}</b></span>` : ''}</div>
      ${isLocked ? `
        <button class="btn block prog-unlock-btn" id="wo-unlock-main" style="margin-top:14px;padding:14px 18px;font-size:15px;display:flex;align-items:center;justify-content:center;gap:8px;">
          ${uiSvg('bolt', 17)} ${L == 'ru' ? 'Разблокировать тренировку через СБП' : 'Unlock workout via SBP'}
        </button>
      ` : `
        <button class="btn block" id="go">${uiSvg('play', 14)} ${t('start')}</button>
        <button class="btn block btn-warmup" id="warmup">${uiSvg('flame', 15)} ${L == 'ru' ? 'Разминка перед тренировкой (3 мин)' : 'Pre-Workout Warm-Up (3 min)'}</button>
      `}
      ${renderMuscleCard(w)}
      ${w.d[L] || w.d.en ? `<div class="box desc">${esc(w.d[L] || w.d.en)}</div>` : ''}
      <div class="plan"><h2>${L == 'ru' ? 'План тренировки' : 'Workout plan'}</h2>${sets}</div>`;
    },
    exercises() {
      return `<h1>${t('exercises')}</h1><div class="filters"><input id="q" placeholder="${t('search')}">
      <select id="f-eq"><option value="">${t('eq')}: ${t('all')}</option>${[...new Set(D.exercises.map(w => w.eq))].filter(Boolean).map(v => `<option value="${v}">${eqLbl(v)}</option>`).join('')}</select>
      <select id="f-l"><option value="">${t('lvl')}: ${t('all')}</option>${['beginner', 'intermediate', 'expert'].map(v => `<option value="${v}">${lvlLbl(v)}</option>`).join('')}</select>
      <label style="align-self:center;color:var(--mut)"><input type="checkbox" id="f-i"> ${L == 'ru' ? 'только с картинкой' : 'with image only'}</label></div>
      <div id="list" class="grid"></div><div class="more" id="more"></div>`;
    },
    exercise(id) {
      const e = exMap[id]; if (!e) return '';
      const d = richDesc(e.d[L] || e.d.en || '');
      const prs = JSON.parse(localStorage.prs || '{}');
      const pr = prs[id];
      const relatedW = D.workouts.filter(w => w.s && w.s.some(st => st.slice(1).some(n => n[0] == id))).slice(0, 6);
      return `<a href="javascript:history.back()">← ${t('exercises')}</a><h1>${esc(exName(e))}</h1><div class="detail">
      <div class="ex-img ${e.img ? '' : 'none'}" style="border-radius:20px;overflow:hidden;position:relative;">${renderExVisual(e, { allowToggle: true })}</div>
      <div><div class="tags"><span class="tag">${eqLbl(e.eq)}</span>${e.lvl && e.lvl != 'none' ? `<span class="tag">${lvlLbl(e.lvl)}</span>` : ''}${e.mech ? `<span class="tag">${e.mech}</span>` : ''}${e.rating ? `<span class="tag star">★ ${e.rating}</span>` : ''}</div>
      <div class="ex-pr-banner">
        <div class="ex-pr-info">
          <span class="ex-pr-label">${uiSvg('trophy', 13)} ${L == 'ru' ? 'Личный рекорд' : 'Personal Record'}</span>
          <b class="ex-pr-val">${pr ? `${pr} ${t('rep')}` : (L == 'ru' ? 'Не записан' : 'None yet')}</b>
        </div>
        <button class="ex-pr-btn" id="log-pr-btn">${pr ? (L == 'ru' ? 'Изменить' : 'Update') : '+ ' + (L == 'ru' ? 'Записать' : 'Log')}</button>
      </div>
      ${renderMuscleCard({ t: e.n, d: e.d, s: [] })}
      ${d ? `<div class="box desc" style="margin-top:16px">${d}</div>` : ''}</div></div>
      ${relatedW.length ? `
        <div style="margin-top:28px">
          <h2 style="font-size:18px;margin-bottom:12px">${uiSvg('dumbbell', 16)} ${L == 'ru' ? 'Входит в тренировки' : 'Featured in workouts'}</h2>
          <div class="grid">${relatedW.map(workoutCard).join('')}</div>
        </div>` : ''}`;
    },
    profile() {
      if (!isLoggedIn()) {
        return renderGuestAuthGate();
      }
      const allH = hist();
      const h = [...allH].reverse();
      const totalSec = allH.reduce((sum, x) => sum + (x.s || 0), 0);
      const totalMins = Math.round(totalSec / 60);
      const streak = calcStreak(allH);
      const prs = JSON.parse(localStorage.prs || '{}');
      const exLogs = loadExLogs();
      const prIds = Array.from(new Set([...Object.keys(prs), ...Object.keys(exLogs)]));
      const prEntries = prIds
        .filter(id => exMap[id] && ((prs[id] || 0) > 0 || (exLogs[id] && exLogs[id].bestW > 0)))
        .map(id => [id, prs[id] || 0, exLogs[id] || null]);
      const doneDates = new Set(allH.map(x => new Date(x.t).toISOString().slice(0, 10)));
      const wk = Date.now() - 7 * 864e5;
      const weekDone = allH.filter(x => x.t > wk).length;
      const goal = Math.max(1, +CFG.goal || 5);
      const weekPct = allH.length ? Math.min(100, Math.round(weekDone / goal * 100)) : null;
      let localProfile = {};
      try { localProfile = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
      const athleteCfg = Object.assign({}, CFG.athlete || {}, localProfile);
      const profileCard = window.AthleteProfile ? window.AthleteProfile.renderCard(athleteCfg, {
        lang: L,
        hist: allH,
        doneDates: allH.length ? doneDates : null,
        live: {
          workoutsCount: allH.length,
          streak,
          prsCount: prEntries.length,
          uniqueDays: doneDates.size,
          weekPct
        }
      }) : '';

      const AP = window.AthleteProfile;
      const activeDuels = AP ? AP.getDuels().filter(d => !d.claimed) : [];
      const duelStats = AP ? AP.getDuelStats() : { wins: 0, bonusXp: 0 };
      let duelBanner = '';
      if (activeDuels.length && AP) {
        const d = activeDuels[0];
        const my = AP.calcMyDuelScore(d, allH), rv = AP.calcRivalDuelScore(d);
        const lead = my >= rv;
        duelBanner = `
          <a href="#/friends" class="ss-card duel-mini-banner">
            <div style="display:flex;align-items:center;gap:10px;min-width:0;">
              <span style="display:flex;align-items:center;color:var(--ac);">${uiSvg('swords', 20)}</span>
              <div style="min-width:0;">
                <div style="font-size:13px;font-weight:800;color:var(--tx);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${L == 'ru' ? 'Дуэль' : 'Duel'} vs ${esc(d.friendName)}</div>
                <div style="font-size:11.5px;color:${lead ? 'var(--green)' : 'var(--ac-l)'};font-weight:700;">${my} : ${rv} XP · ⏱ ${AP.formatDuelLeft(d.endsAt, L)}</div>
              </div>
            </div>
            <span class="tag pro">${activeDuels.length > 1 ? '+' + activeDuels.length : '▶'}</span>
          </a>`;
      }

      const activeQ = AP ? AP.getQuest() : null;
      if (activeQ && !activeQ.claimed && AP) {
        const qp = AP.calcQuestProgress(activeQ, allH);
        const qTitle = L == 'ru' ? activeQ.titleRu : activeQ.titleEn;
        duelBanner += `
          <a href="#/friends" class="ss-card duel-mini-banner" style="border-color:rgba(var(--green-r),0.4);">
            <div style="display:flex;align-items:center;gap:10px;min-width:0;">
              <span style="display:flex;align-items:center;color:var(--green);">${uiSvg('handshake', 20)}</span>
              <div style="min-width:0;">
                <div style="font-size:13px;font-weight:800;color:var(--tx);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(qTitle)}</div>
                <div style="font-size:11.5px;color:var(--green);font-weight:700;">${qp.total} / ${qp.target} (${qp.pct}%) · с ${esc(activeQ.friendName.split(' ')[0])}</div>
              </div>
            </div>
            <span class="tag pro">${qp.done ? uiSvg('check', 12) : qp.pct + '%'}</span>
          </a>`;
      }

      const kpis = `
        <div class="hist-kpi-grid">
          <div class="hist-kpi-card">
            <div class="val">${uiSvg('dumbbell', 18)} ${allH.length}</div>
            <div class="lbl">${L == 'ru' ? 'Тренировок' : 'Workouts'}</div>
          </div>
          <div class="hist-kpi-card">
            <div class="val">${uiSvg('clock', 18)} ${totalMins}</div>
            <div class="lbl">${L == 'ru' ? 'Минут всего' : 'Active Mins'}</div>
          </div>
          <div class="hist-kpi-card">
            <div class="val">${uiSvg('flame', 18)} ${streak}</div>
            <div class="lbl">${L == 'ru' ? 'Дней стрик' : 'Day Streak'}</div>
          </div>
          <div class="hist-kpi-card">
            <div class="val">${uiSvg('trophy', 18)} ${duelStats.wins}</div>
            <div class="lbl">${L == 'ru' ? 'Побед в дуэлях' : 'Duel Wins'}</div>
          </div>
        </div>`;

      const analyticsCard = `
        <div class="ss-card prof-analytics">
          <div class="act-head">
            <b>${uiSvg('trend', 15)} ${L == 'ru' ? 'Динамика активности' : 'Activity Trend'}</b>
            <div class="act-seg">
              <button type="button" class="act-seg-btn on" data-act-days="7">7${L == 'ru' ? 'д' : 'd'}</button>
              <button type="button" class="act-seg-btn" data-act-days="30">30${L == 'ru' ? 'д' : 'd'}</button>
            </div>
          </div>
          <div id="act-chart-slot">${renderActivityChartHtml(allH, 7)}</div>
          ${renderHeatmapHtml(allH)}
          ${renderMuscleBalanceHtml(allH)}
        </div>`;
      const fitnessCard = renderFitnessProfileCard();
      const activeProgCard = renderActiveProgramCard();
      const bodyCard = renderBodyMetricsCard();

      let prsHtml = '';
      if (prEntries.length) {
        prsHtml = `
          <div class="pr-section">
            <h2>${uiSvg('trophy', 17)} ${L == 'ru' ? 'Личные рекорды' : 'Personal Records'}</h2>
            <div class="pr-grid">
              ${prEntries.map(([id, val, log]) => {
                const e = exMap[id];
                const hasW = log && log.bestW > 0;
                const valHtml = hasW
                  ? `${log.bestW} <small style="font-size:11px;color:var(--mut);font-weight:600">${L == 'ru' ? 'кг' : 'kg'}</small><div style="font-size:10.5px;color:var(--mut);font-weight:600;margin-top:1px;">1RM ~${log.best1RM}${val > 0 ? ` · ${val} ${t('rep')}` : ''}</div>`
                  : `${val} <small style="font-size:11px;color:var(--mut);font-weight:600">${t('rep')}</small>`;
                return `<a class="pr-card" href="#/exercise/${id}">
                  <div class="pr-thumb">${e && e.img ? `<img src="img/ex/svg_norm_${e.id}.svg" alt="">` : uiSvg('dumbbell', 18)}</div>
                  <div class="pr-info">
                    <div class="pr-title">${esc(e ? exName(e) : '#' + id)}</div>
                    <div class="pr-val">${valHtml}</div>
                  </div>
                </a>`;
              }).join('')}
            </div>
          </div>`;
      }

      let histHtml = '';
      if (h.length) {
        histHtml = `
          <div class="hist-section">
            <h2>${uiSvg('clock', 17)} ${L == 'ru' ? 'История занятий' : 'Workout History'}</h2>
            <div>
              ${h.map(x => {
                const rpeMeta = x.rpe ? RPE_OPTS.find(r => r.id === x.rpe) : null;
                return `
                <a class="hist-item" href="#/workout/${x.id}">
                  <div class="hist-item-info">
                    <div class="hist-item-title">${esc(woMap[x.id] ? woName(woMap[x.id]) : '#' + x.id)}</div>
                    <div class="hist-item-date">${new Date(x.t).toLocaleString(L, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</div>
                  </div>
                  <div class="hist-item-meta">
                    ${rpeMeta ? `<span class="hist-rpe">${rpeMeta.icon} ${L == 'ru' ? rpeMeta.ru : rpeMeta.en}</span>` : ''}
                    <div class="hist-item-dur">${uiSvg('clock', 12)} ${Math.max(1, Math.round((x.s || 0) / 60))} ${L == 'ru' ? 'мин' : 'min'}${x.vol > 0 ? ` · ${x.vol.toLocaleString()} ${L == 'ru' ? 'кг' : 'kg'}` : ''}</div>
                  </div>
                </a>`;
              }).join('')}
            </div>
            <p style="margin-top:20px;text-align:center"><button class="btn alt" id="clr">${t('clear')}</button></p>
          </div>`;
      } else {
        histHtml = `<div class="empty">${t('nohist')}</div>`;
      }

      return `${profileCard}${duelBanner}${fitnessCard}${activeProgCard}${bodyCard}${kpis}${analyticsCard}${prsHtml}${histHtml}`;
    },
    friends() {
      if (!isLoggedIn()) return renderAuthGateStub(t('authRequired'), t('authRequiredDesc'));
      const AP = window.AthleteProfile;
      if (AP && AP.purgeLegacyFakes) AP.purgeLegacyFakes();
      const list = (AP ? AP.getFriends(CFG.athlete) : []).filter(f => !(AP && AP.isFakeUser ? AP.isFakeUser(f) : false));
      const online = list.filter(f => f.online).length;
      let loc = {};
      try { loc = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
      const allH = hist();
      const me = AP ? AP.merge(Object.assign({}, CFG.athlete || {}, loc), {
        workoutsCount: allH.length,
        streak: calcStreak(allH),
        prsCount: Object.keys(JSON.parse(localStorage.prs || '{}')).length
      }) : { name: 'Атлет', handle: '@athlete', points: 0, level: 1, streakDays: 0, duelReward: 500 };

      const duels = AP ? AP.getDuels().filter(d => !d.claimed && !(AP.isFakeUser && AP.isFakeUser({ id: d.friendId, name: d.friendName, handle: d.friendHandle }))) : [];
      const duelByFriend = {};
      duels.forEach(d => { duelByFriend[String(d.friendId)] = d; });
      const rewardXp = Number(me.duelReward) || 500;

      const board = [
        { isMe: true, name: me.name, handle: me.handle, points: Number(me.points) || 0, level: me.level, streak: me.streakDays, avatar: me.avatar },
        ...list
      ].sort((a, b) => (Number(b.points) || 0) - (Number(a.points) || 0));
      const myRank = board.findIndex(x => x.isMe) + 1;

      const existingHandles = new Set(list.map(f => (f.handle || '').toLowerCase()));
      const suggestions = (AP && AP.SUGGESTED_FRIENDS ? AP.SUGGESTED_FRIENDS : [])
        .filter(s => !(AP && AP.isFakeUser ? AP.isFakeUser(s) : false) && !existingHandles.has((s.handle || '').toLowerCase()));

      const duelsHtml = duels.length ? `
        <div class="duels-section">
          <div class="ss-card-title" style="margin:6px 2px 10px;">
            <b style="font-size:15px;display:inline-flex;align-items:center;gap:6px;">${uiSvg('swords', 16)} ${L == 'ru' ? 'Дуэли 1 на 1 (7 дней)' : '7-Day 1v1 Duels'}</b>
            <button type="button" class="duel-rules-btn" id="duel-rules">${L == 'ru' ? '? Правила' : '? Rules'}</button>
          </div>
          ${duels.map(d => {
            const my = AP.calcMyDuelScore(d, allH);
            const rv = AP.calcRivalDuelScore(d);
            const tot = Math.max(1, my + rv);
            const myPct = Math.min(88, Math.max(12, Math.round((my / tot) * 100)));
            const finished = Date.now() >= d.endsAt;
            const won = my >= rv;
            const diff = Math.abs(my - rv);
            return `
            <div class="ss-card duel-card">
              <div class="duel-head">
                <span class="duel-badge">${finished ? (won ? uiSvg('trophy', 11) + ' ' + (L == 'ru' ? 'Победа!' : 'Victory!') : (L == 'ru' ? 'Завершена' : 'Ended')) : '7D DUEL'}</span>
                <span class="duel-timer">⏱ ${AP.formatDuelLeft(d.endsAt, L)}</span>
              </div>
              <div class="duel-vs-row">
                <div class="duel-side">
                  <div class="duel-av me">${me.avatar ? `<img src="${esc(me.avatar)}" alt="">` : uiSvg('dumbbell', 18)}</div>
                  <b class="duel-nm">${L == 'ru' ? 'Ты' : 'You'}</b>
                  <span class="duel-sc gold">${my}</span>
                </div>
                <div class="duel-vs-mid">VS</div>
                <div class="duel-side">
                  <div class="duel-av rv">${AP.miniAvatar(d.friendColor, d.friendShirt, d.friendAvatar)}</div>
                  <b class="duel-nm">${esc(d.friendName.split(' ')[0])}</b>
                  <span class="duel-sc green">${rv}</span>
                </div>
              </div>
              <div class="duel-bar-wrap">
                <div class="duel-bar-me" style="width:${myPct}%"></div>
                <div class="duel-bar-rv" style="width:${100 - myPct}%"></div>
              </div>
              <div class="duel-foot">
                <span class="duel-lead">${finished
                  ? (won ? (L == 'ru' ? `Заберите награду +${rewardXp} XP!` : `Claim +${rewardXp} XP!`) : (L == 'ru' ? `Соперник впереди на ${diff} XP` : `Rival won by ${diff} XP`))
                  : (won ? (L == 'ru' ? `${uiSvg('flame', 13)} Вы ведёте +${diff} XP` : `${uiSvg('flame', 13)} Leading by +${diff} XP`) : (L == 'ru' ? `${uiSvg('bolt', 13)} Отстаёте на ${diff} XP` : `${uiSvg('bolt', 13)} Behind by ${diff} XP`))}
                </span>
                <div style="display:flex;gap:6px;align-items:center;">
                  ${finished
                    ? `<button type="button" class="btn" data-duel-claim="${esc(d.id)}" style="padding:6px 12px;font-size:11.5px;">${won ? uiSvg('trophy', 12) + ' +' + rewardXp + ' XP' : (L == 'ru' ? 'Реванш' : 'Rematch')}</button>`
                    : `<a href="#/workouts" class="btn" style="padding:6px 12px;font-size:11.5px;">▶ ${L == 'ru' ? 'Тренировка' : 'Train'}</a>`}
                  <button type="button" class="fr-btn-del" data-duel-del="${esc(d.id)}" title="${L == 'ru' ? 'Закрыть дуэль' : 'Close duel'}">✕</button>
                </div>
              </div>
            </div>`;
          }).join('')}
        </div>` : `
        <div class="ss-card duel-empty-tip" style="margin-bottom:14px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
            <div>
              <div style="font-size:13.5px;font-weight:800;color:var(--tx);display:inline-flex;align-items:center;gap:6px;">${uiSvg('swords', 15)} ${L == 'ru' ? 'Дуэли 1 на 1 (7 дней)' : '7-Day 1v1 Duels'}</div>
              <div style="font-size:11.5px;color:var(--mut);">${L == 'ru' ? `Нажмите «Дуэль» у любого друга и выиграйте +${rewardXp} XP` : `Tap "Duel" on any friend to compete for +${rewardXp} XP`}</div>
            </div>
            <button type="button" class="duel-rules-btn" id="duel-rules">?</button>
          </div>
        </div>`;

      const activeQ = AP ? AP.getQuest() : null;
      const qProg = (activeQ && !activeQ.claimed && AP) ? AP.calcQuestProgress(activeQ, allH) : null;
      const qReward = Number((CFG.athlete || {}).questReward) || (activeQ && activeQ.reward) || 500;
      const questHtml = (activeQ && !activeQ.claimed && qProg) ? `
        <div class="ss-card quest-card" style="margin-bottom:14px;">
          <div class="duel-head">
            <span class="duel-badge" style="background:var(--green);">${uiSvg('handshake', 12)} ${L == 'ru' ? 'СОВМЕСТНЫЙ КВЕСТ' : 'CO-OP QUEST'}</span>
            <span class="duel-timer">⏱ ${AP.formatDuelLeft(activeQ.endsAt, L)}</span>
          </div>
          <div class="quest-partners">
            <div class="quest-pair-avs">
              <div class="duel-av me" style="width:40px;height:40px;font-size:18px;">${me.avatar ? `<img src="${esc(me.avatar)}" alt="">` : uiSvg('dumbbell', 18)}</div>
              <span class="quest-link-ic" style="display:inline-flex;align-items:center;color:var(--green);">${uiSvg('handshake', 16)}</span>
              <div class="duel-av rv" style="width:40px;height:40px;">${AP.miniAvatar(activeQ.friendColor, activeQ.friendShirt, activeQ.friendAvatar)}</div>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:14px;font-weight:800;color:var(--tx);line-height:1.25;">${esc(L == 'ru' ? activeQ.titleRu : activeQ.titleEn)}</div>
              <div style="font-size:11.5px;color:var(--mut);margin-top:2px;">${L == 'ru' ? 'Напарник:' : 'Partner:'} <b style="color:var(--tx)">${esc(activeQ.friendName)}</b> · +${activeQ.reward} XP</div>
            </div>
          </div>
          <div class="quest-bar-track">
            <div class="quest-bar-fill" style="width:${qProg.pct}%"></div>
          </div>
          <div class="quest-split-meta">
            <span>${L == 'ru' ? 'Твой вклад' : 'Yours'}: <b style="color:var(--ac-l)">${qProg.my}</b></span>
            <span><b>${qProg.total} / ${qProg.target}</b> (${qProg.pct}%)</span>
            <span>${esc(activeQ.friendName.split(' ')[0])}: <b style="color:var(--green)">${qProg.friend}</b></span>
          </div>
          <div class="duel-foot" style="margin-top:10px;">
            <span class="duel-lead">${qProg.done ? (L == 'ru' ? 'Квест выполнен! Заберите награду!' : 'Quest complete! Claim your reward!') : (L == 'ru' ? 'Тренируйтесь, чтобы закрыть цель вместе' : 'Train to finish the goal together')}</span>
            <div style="display:flex;gap:6px;align-items:center;">
              ${qProg.done
                ? `<button type="button" class="btn" id="quest-claim" style="padding:6px 12px;font-size:11.5px;">+${activeQ.reward} XP</button>`
                : `<a href="#/workouts" class="btn" style="padding:6px 12px;font-size:11.5px;">▶ ${L == 'ru' ? 'Вперёд' : 'Go'}</a>`}
              <button type="button" class="fr-btn-del" id="quest-del" title="${L == 'ru' ? 'Отменить квест' : 'Cancel quest'}">✕</button>
            </div>
          </div>
        </div>` : `
        <div class="ss-card quest-card" style="margin-bottom:14px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
            <div>
              <div style="font-size:13.5px;font-weight:800;color:var(--tx);display:flex;align-items:center;gap:6px;">${uiSvg('handshake', 15)} ${L == 'ru' ? 'Совместный квест с другом' : 'Co-op Friend Quest'}</div>
              <div style="font-size:11.5px;color:var(--mut);">${L == 'ru' ? `Выполните общую цель за 7 дней и получите +${qReward} XP` : `Complete a shared 7-day goal for +${qReward} XP`}</div>
            </div>
            <button type="button" class="btn" id="quest-new-btn" style="padding:7px 12px;font-size:11.5px;white-space:nowrap;">+ ${L == 'ru' ? 'Начать' : 'Start'}</button>
          </div>
        </div>`;

      const duelStats = AP ? AP.getDuelStats() : { wins: 0 };
      const questStats = AP ? AP.getQuestStats() : { done: 0 };
      const claimedDuels = AP ? AP.getDuels().filter(d => d.claimed).slice(0, 4) : [];

      return `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;">
          <a href="#/profile" class="btn alt" style="padding:7px 14px;font-size:12.5px;">← ${L == 'ru' ? 'Профиль' : 'Profile'}</a>
          <a href="#/users" class="btn" style="padding:8px 14px;font-size:12.5px;">🔍 ${L == 'ru' ? 'Найти атлетов' : 'Find athletes'}</a>
        </div>

        <div class="social-tabs" id="fr-tabs-bar" style="margin-bottom:14px;">
          <button type="button" class="social-tab-btn active" data-fr-main-tab="friends">👥 ${t('friends')}</button>
          <button type="button" class="social-tab-btn" data-fr-main-tab="incoming">📥 ${t('incomingRequests')} <span class="social-tab-badge" id="fr-badge-inc" style="display:none;">0</span></button>
          <button type="button" class="social-tab-btn" data-fr-main-tab="outgoing">📤 ${t('outgoingRequests')} <span class="social-tab-badge" id="fr-badge-out" style="display:none;">0</span></button>
        </div>
        <div id="fr-requests-panel" style="display:none;margin-bottom:16px;"></div>

        <div id="fr-friends-content">
          ${questHtml}

          ${duelsHtml}

        <div class="ss-card" style="margin-bottom:14px;">
          <div class="ss-card-title">
            <b style="display:inline-flex;align-items:center;gap:6px;">${uiSvg('users', 16)} ${L == 'ru' ? 'Друзья и рейтинг' : 'Friends & Leaderboard'}</b>
            <span class="tag pro">${online} ${L == 'ru' ? 'онлайн' : 'online'}</span>
          </div>
          <div class="fr-rank-banner">
            <div>
              <small>${L == 'ru' ? 'ТВОЁ МЕСТО В РЕЙТИНГЕ' : 'YOUR CLUB RANK'}</small>
              <b>#${myRank} ${L == 'ru' ? 'из' : 'of'} ${board.length} · ${Math.round(me.points).toLocaleString()} XP</b>
              <div style="font-size:11px;color:var(--mut);margin-top:3px;">${L == 'ru' ? 'Побед' : 'Wins'}: <b style="color:var(--ac-l)">${duelStats.wins}</b> · ${L == 'ru' ? 'Квестов' : 'Quests'}: <b style="color:var(--green)">${questStats.done}</b></div>
            </div>
            <button type="button" class="btn alt" id="fr-copy-inv" style="padding:7px 12px;font-size:11.5px;">${L == 'ru' ? 'Пригласить' : 'Invite'}</button>
          </div>
        </div>

        <div class="frosted-search">
          <i>${uiSvg('bolt', 15)}</i>
          <input id="fr-q" placeholder="${L == 'ru' ? 'Поиск друзей по имени или @нику…' : 'Search friends by name or @handle…'}">
        </div>

        <div class="muscle-pills" id="fr-tabs" style="margin-bottom:14px;">
          <button class="mpill on" data-ft="all">${L == 'ru' ? 'Все' : 'All'} (${list.length})</button>
          <button class="mpill" data-ft="online">${L == 'ru' ? 'Онлайн' : 'Online'} (${online})</button>
          <button class="mpill" data-ft="top">${L == 'ru' ? 'Топ по XP' : 'Leaderboard'}</button>
        </div>

        <div id="fr-list" class="fr-list">
          ${list.length ? list.map(f => {
            const activeD = duelByFriend[String(f.id)];
            const rank = board.findIndex(b => !b.isMe && b.id === f.id) + 1;
            const mySc = activeD ? AP.calcMyDuelScore(activeD, allH) : 0;
            const rvSc = activeD ? AP.calcRivalDuelScore(activeD) : 0;
            return `
            <div class="ss-card fr-card fr-clickable" data-fid="${esc(f.id)}" data-name="${esc((f.name + ' ' + f.handle).toLowerCase())}" data-online="${f.online ? '1' : '0'}" data-xp="${Number(f.points) || 0}">
              <div class="fr-av-wrap">
                ${AP ? AP.miniAvatar(f.color, f.shirt, f.avatar) : ''}
                <i class="fr-status-dot ${f.online ? 'on' : ''}"></i>
              </div>
              <div class="fr-info">
                <div class="fr-name-row">
                  <b>${esc(f.name)}</b>
                  ${f.isPro ? '<span class="tag pro" style="font-size:9.5px;padding:1px 5px;margin-left:4px;">PRO</span>' : ''}
                  <span class="fr-rank-badge">#${rank}</span>
                </div>
                <div class="fr-sub">${esc(f.handle)} · Lv.${f.level || 1} · ${f.streak || 0} ${t('days')}</div>
                <div class="fr-xp">${Number(f.points || 0).toLocaleString()} XP · <span style="color:${f.online ? 'var(--green)' : 'var(--mut)'}">${f.online ? (L == 'ru' ? 'онлайн' : 'online') : (L == 'ru' ? 'не в сети' : 'offline')}</span></div>
              </div>
              <div class="fr-actions">
                <button type="button" class="fr-btn-chal" data-quest-friend="${esc(f.id)}" title="${L == 'ru' ? 'Совместный квест' : 'Co-op Quest'}">${uiSvg('handshake', 14)}</button>
                ${activeD
                  ? `<span class="fr-btn-chal sent">${mySc}:${rvSc}</span>`
                  : `<button type="button" class="fr-btn-chal" data-duel-start="${esc(f.id)}">${uiSvg('swords', 13)} ${L == 'ru' ? 'Дуэль' : 'Duel'}</button>`}
                <button type="button" class="fr-btn-del" data-del="${esc(f.id)}" title="${L == 'ru' ? 'Удалить' : 'Remove'}">✕</button>
              </div>
            </div>`;
          }).join('') : `<div class="empty">${L == 'ru' ? 'Пока нет других зарегистрированных атлетов. Пригласите друзей или зарегистрируйте второй аккаунт!' : 'No other registered athletes yet. Invite friends or register another account!'}</div>`}
        </div>

        ${suggestions.length ? `
          <h2 style="margin-top:22px;display:flex;align-items:center;gap:6px;">${uiSvg('sparkles', 16)} ${L == 'ru' ? 'Атлеты рядом' : 'Suggested Athletes'}</h2>
          <div class="fr-list">
            ${suggestions.map(s => `
              <div class="ss-card fr-card">
                <div class="fr-av-wrap">
                  ${AP ? AP.miniAvatar(s.color, s.shirt, s.avatar) : ''}
                  <i class="fr-status-dot ${s.online ? 'on' : ''}"></i>
                </div>
                <div class="fr-info">
                  <div class="fr-name-row"><b>${esc(s.name)}</b></div>
                  <div class="fr-sub">${esc(s.handle)} · Lv.${s.level} · ${s.streak} ${t('days')}</div>
                  <div class="fr-xp">${Number(s.points).toLocaleString()} XP</div>
                </div>
                <button type="button" class="btn" data-add-sug="${esc(s.id)}" style="padding:7px 12px;font-size:12px;">+ ${L == 'ru' ? 'Добавить' : 'Add'}</button>
              </div>
            `).join('')}
          </div>` : ''}

        ${claimedDuels.length ? `
          <h2 style="margin-top:22px;display:flex;align-items:center;gap:6px;">${uiSvg('trend', 16)} ${L == 'ru' ? 'История дуэлей' : 'Duel History'}</h2>
          <div class="fr-list">
            ${claimedDuels.map(d => {
              const won = (d.finalMy || 0) >= (d.finalRival || 0);
              return `<div class="ss-card" style="padding:10px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px;">
                <div>
                  <div style="font-size:13px;font-weight:800;color:var(--tx);display:flex;align-items:center;gap:6px;">${won ? uiSvg('trophy', 14) : uiSvg('repeat', 14)} vs ${esc(d.friendName)}</div>
                  <div style="font-size:11px;color:var(--mut);">${new Date(d.endsAt).toLocaleDateString(L)} · ${d.finalMy || 0} : ${d.finalRival || 0} XP</div>
                </div>
                <span class="tag ${won ? 'pro' : ''}">${won ? (L == 'ru' ? 'Победа' : 'Won') : (L == 'ru' ? 'Поражение' : 'Lost')}</span>
              </div>`;
            }).join('')}
          </div>` : ''}
        </div>
      `;
    },
    history() {
      return this.profile();
    },
    users() {
      if (!isLoggedIn()) return renderAuthGateStub(t('authRequired'), t('authRequiredDesc'));
      return `
        <div class="social-wrap">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <h1 style="font-size:22px;font-weight:800;color:var(--tx);margin:0;">${t('users')}</h1>
            <a href="#/friends" class="btn alt" style="padding:7px 12px;font-size:12.5px;">👥 ${t('friends')}</a>
          </div>
          <div class="social-search-bar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="users-search-input" placeholder="${esc(t('userSearchPlaceholder'))}" autocomplete="off">
          </div>
          <div id="users-grid" class="user-grid">
            <div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--tx-sub);">${L == 'ru' ? 'Загрузка атлетов…' : 'Loading athletes…'}</div>
          </div>
          <div id="users-more-wrap" style="text-align:center;margin-top:16px;"></div>
        </div>`;
    },
    user(username) {
      if (!isLoggedIn()) return renderAuthGateStub(t('authRequired'), t('authRequiredDesc'));
      return `
        <div class="pub-profile" id="pub-profile-wrap">
          <div style="text-align:center;padding:40px;color:var(--tx-sub);">${L == 'ru' ? 'Загрузка профиля…' : 'Loading profile…'}</div>
        </div>`;
    },
    messages(convId) {
      if (!isLoggedIn()) return renderAuthGateStub(t('authRequired'), t('authRequiredDesc'));
      return `
        <div class="wrap messages-wrap" style="padding:10px 10px 80px;">
          <div class="messages-layout ${convId ? 'chat-open' : ''}" id="messages-layout">
            <div class="conv-sidebar">
              <div class="conv-sidebar-header">
                <span>💬 ${t('messages')}</span>
                <a href="#/users" class="btn alt" style="padding:4px 8px;font-size:11px;" title="${t('users')}">+ ${t('users')}</a>
              </div>
              <div class="conv-list" id="conv-list">
                <div style="text-align:center;padding:24px;color:var(--tx-sub);font-size:12px;">${L == 'ru' ? 'Загрузка диалогов…' : 'Loading chats…'}</div>
              </div>
            </div>
            <div class="chat-pane" id="chat-pane">
              ${convId ? `
                <div class="chat-header" id="chat-header">
                  <div style="display:flex;align-items:center;gap:10px;">
                    <a href="#/messages" class="btn alt chat-back-btn" id="chat-back-btn" style="padding:5px 8px;font-size:12px;line-height:1;">‹</a>
                    <span style="font-size:13px;color:var(--tx-sub);">${L == 'ru' ? 'Загрузка…' : 'Loading…'}</span>
                  </div>
                </div>
                <div class="chat-messages" id="chat-messages">
                  <div style="text-align:center;padding:30px;color:var(--tx-sub);font-size:12.5px;">${L == 'ru' ? 'Загрузка истории…' : 'Loading messages…'}</div>
                </div>
                <div class="chat-input-bar" id="chat-input-bar">
                  <textarea class="chat-textarea" id="chat-textarea" placeholder="${esc(t('typeMessage'))}" rows="1"></textarea>
                  <button type="button" class="chat-send-btn" id="chat-send-btn" aria-label="Send">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                  </button>
                </div>
              ` : `
                <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--tx-sub);padding:30px;text-align:center;">
                  <div style="font-size:40px;margin-bottom:12px;opacity:0.6;">💬</div>
                  <div style="font-size:15px;font-weight:700;color:var(--tx);margin-bottom:6px;">${t('noConversations')}</div>
                  <div style="font-size:12.5px;max-width:280px;line-height:1.4;">${L == 'ru' ? 'Выберите диалог из списка слева или найдите атлета в разделе «Пользователи»' : 'Choose a conversation from the left or find an athlete in Users'}</div>
                  <a href="#/users" class="btn" style="margin-top:16px;font-size:13px;">🔍 ${t('users')}</a>
                </div>
              `}
            </div>
          </div>
        </div>`;
    }
  };

  function programCard(p) {
    const ps = getProgState();
    const logs = Array.isArray(ps.logs[p.id]) ? ps.logs[p.id] : [];
    const isAct = String(ps.activeId) === String(p.id);
    const isPro = isUserPro();
    return `<a class="card" href="#/program/${p.id}">${p.img ? `<img class="cover" src="${pImg(p)}">` : ''}<div class="b"><h3>${esc(pName(p))}</h3><div class="tags"><span class="tag">${logs.length ? `${logs.length}/${p.days}` : p.days} ${t('days')}</span><span class="tag">${tempLbl(p.temp)}</span>${isAct ? `<span class="tag pro">${uiSvg('pin', 11)} ${L == 'ru' ? 'Активна' : 'Active'}</span>` : (isPro ? '<span class="tag pro">PRO</span>' : '<span class="tag pro" style="background:rgba(245,158,11,0.18);color:var(--acc);border:1px solid rgba(245,158,11,0.35);">🔒 PRO</span>')}</div></div></a>`;
  }
  function workoutCard(w) {
    const first = w.s[0] && w.s[0][1] && exMap[w.s[0][1][0]];
    const isFav = getFavs().has(w.id);
    const isProW = isProWorkout(w);
    const isPro = isUserPro();
    let proTag = '';
    if (w._custom) {
      proTag = `<span class="tag pro">${uiSvg('sparkles', 11)} ${L == 'ru' ? 'Моя' : 'Custom'}</span>`;
    } else if (isProW) {
      proTag = isPro
        ? '<span class="tag pro">PRO</span>'
        : '<span class="tag pro" style="background:rgba(245,158,11,0.18);color:var(--acc);border:1px solid rgba(245,158,11,0.35);font-weight:800;">🔒 PRO</span>';
    }
    return `<a class="card" href="#/workout/${w.id}">${first && first.img ? `<div class="ex-img" style="aspect-ratio:16/9">${exImg(first)}</div>` : ''}<div class="b"><h3>${esc(woName(w))}</h3><div class="tags">${proTag}<span class="tag">${diffLbl(w.diff)}</span>${w.eq ? `<span class="tag">${eqLbl(w.eq)}</span>` : ''}${w.rating ? `<span class="tag star">★ ${w.rating}</span>` : ''}${isFav ? `<span class="tag pro">${uiSvg('heartFill', 11)}</span>` : ''}</div></div></a>`;
  }
  function exerciseCard(e) {
    const hasVid = !!getExVideo(e);
    return `<a class="card" href="#/exercise/${e.id}"><div class="ex-img ${e.img ? '' : 'none'}">${e.img ? exImg(e) : uiSvg('dumbbell', 24)}</div><div class="b"><h3>${esc(exName(e))}</h3><div class="tags"><span class="tag">${eqLbl(e.eq)}</span>${hasVid ? `<span class="tag" style="background:rgba(var(--acr),0.15);color:var(--ac);border:1px solid rgba(var(--acr),0.32);font-size:10px;font-weight:800;">3D</span>` : ''}${e.rating ? `<span class="tag star">★ ${e.rating}</span>` : ''}</div></div></a>`;
  }

  function pagedList(getItems, card) {
    const list = document.getElementById('list'), more = document.getElementById('more');
    let items = [], shown = 0; const PAGE = 48;
    function draw(reset) {
      if (reset) { list.innerHTML = ''; shown = 0; items = getItems(); if (!items.length) list.innerHTML = `<div class="empty">${t('nothing')}</div>`; }
      items.slice(shown, shown + PAGE).forEach(i => list.insertAdjacentHTML('beforeend', card(i)));
      shown = Math.min(items.length, shown + PAGE);
      more.innerHTML = shown < items.length ? `<button class="btn alt">${t('more')} (${items.length - shown})</button>` : '';
      if (more.firstChild) more.firstChild.onclick = () => draw(false);
    }
    document.querySelectorAll('.filters input,.filters select').forEach(el => el.oninput = () => draw(true));
    draw(true);
    return draw;
  }

  const norm = s => (s || '').toLowerCase();
  function woFullText(w) {
    if (w._woTxt !== undefined) return w._woTxt;
    const base = (w.t.ru || '') + ' ' + (w.t.en || '') + ' ' + (w.d.ru || '') + ' ' + (w.d.en || '');
    const exPart = (w.s || []).map(st => st.slice(1).map(n => {
      const e = exMap[n[0]];
      return e ? ((e.n.ru || '') + ' ' + (e.n.en || '')) : '';
    }).join(' ')).join(' ');
    w._woTxt = base + ' ' + exPart;
    return w._woTxt;
  }
  function after(name) {
    if (name == 'home') {
      const hs = document.getElementById('hsearch');
      if (hs) {
        hs.onkeydown = e => {
          if (e.key == 'Enter' && hs.value.trim()) {
            const val = hs.value.trim();
            location.hash = '#/workouts';
            setTimeout(() => {
              const q = document.getElementById('q');
              if (q) { q.value = val; q.dispatchEvent(new Event('input')); }
            }, 100);
          }
        };
      }
      const openWeekPlanModal = () => {
        vib(20);
        const plan = getWeekPlan();
        const days = L == 'ru' ? ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'] : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        const favs = getFavs();
        const customW = D.workouts.filter(w => w._custom);
        const favW = D.workouts.filter(w => !w._custom && favs.has(w.id));
        const topW = D.workouts.filter(w => !w._custom && !favs.has(w.id) && (w.t.ru || w.t.en)).slice(0, 30);
        const pool = [...customW, ...favW, ...topW];
        const bd = document.createElement('div');
        bd.className = 'ap-modal-backdrop';
        bd.innerHTML = `<div class="ap-modal" style="max-height:86vh;overflow-y:auto;">
          <h3>${L == 'ru' ? 'План тренировок на неделю' : 'Weekly Workout Plan'}</h3>
          ${days.map((dName, idx) => `
            <label>${dName}
              <select class="wp-sel" data-wp-idx="${idx}" style="width:100%;margin-top:4px;background:var(--card-inset);border:1px solid var(--line);border-radius:12px;padding:9px 10px;color:var(--tx);font:inherit;">
                <option value="">${L == 'ru' ? '— День отдыха —' : '— Rest day —'}</option>
                ${pool.map(w => `<option value="${esc(w.id)}" ${String(plan[idx] || '') === String(w.id) ? 'selected' : ''}>${w._custom ? '★ ' : ''}${esc(woName(w))}</option>`).join('')}
              </select>
            </label>`).join('')}
          <div class="ap-modal-actions">
            <button type="button" class="btn alt" id="wp-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
            <button type="button" class="btn" id="wp-save">${L == 'ru' ? 'Сохранить' : 'Save'}</button>
          </div>
        </div>`;
        document.body.appendChild(bd);
        bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
        bd.querySelector('#wp-cancel').onclick = () => bd.remove();
        bd.querySelector('#wp-save').onclick = () => {
          const next = {};
          bd.querySelectorAll('.wp-sel').forEach(sel => {
            if (sel.value) next[sel.dataset.wpIdx] = sel.value;
          });
          saveWeekPlan(next);
          vib(30);
          bd.remove();
          render();
        };
      };
      const wpBtn = document.getElementById('wp-edit-btn');
      if (wpBtn) wpBtn.onclick = openWeekPlanModal;
      app.querySelectorAll('[data-wp-day]').forEach(btn => {
        btn.onclick = openWeekPlanModal;
      });
    }
    if (name == 'workouts' || name == 'programs') {
      const tabWorkouts = document.getElementById('wo-tab-workouts');
      const tabPrograms = document.getElementById('wo-tab-programs');
      const secWorkouts = document.getElementById('wo-sec-workouts');
      const secPrograms = document.getElementById('wo-sec-programs');
      const buildBtn = document.getElementById('wo-builder-btn');

      if (tabWorkouts && tabPrograms) {
        tabWorkouts.onclick = () => {
          vib(20);
          tabWorkouts.classList.add('on');
          tabPrograms.classList.remove('on');
          if (secWorkouts) secWorkouts.style.display = '';
          if (secPrograms) secPrograms.style.display = 'none';
          if (buildBtn) buildBtn.style.display = '';
          history.replaceState(null, '', '#/workouts');
        };
        tabPrograms.onclick = () => {
          vib(20);
          tabPrograms.classList.add('on');
          tabWorkouts.classList.remove('on');
          if (secWorkouts) secWorkouts.style.display = 'none';
          if (secPrograms) secPrograms.style.display = '';
          if (buildBtn) buildBtn.style.display = 'none';
          history.replaceState(null, '', '#/workouts/programs');
        };
      }

      let curMuscle = '';
      const fullRx = /все тел|full body|кругов|hannibal|medrano|комплекс/i;
      const qEl = document.getElementById('q');
      if (qEl) {
        const redraw = pagedList(() => {
          const q = norm(document.getElementById('q').value), eq = document.getElementById('f-eq').value, d = document.getElementById('f-d').value, named = document.getElementById('f-t').checked;
          return D.workouts.filter(w => {
            if (named && !w._custom && !w.t.ru && !w.t.en) return false;
            if (eq && w.eq != eq) return false;
            if (d && w.diff != d) return false;
            if (q && !norm(woFullText(w)).includes(q)) return false;
            if (curMuscle == 'mine') {
              if (!w._custom) return false;
            } else if (curMuscle == 'fav') {
              if (!getFavs().has(w.id)) return false;
            } else if (curMuscle == 'full') {
              const txt = woFullText(w);
              const mf = detectMuscles(txt);
              const cnt = Object.values(mf).filter(Boolean).length;
              if (cnt < 3 && !fullRx.test(txt)) return false;
            } else if (curMuscle && MUSCLE_RULES[curMuscle]) {
              const txt = woFullText(w);
              if (!MUSCLE_RULES[curMuscle].test(txt)) return false;
            }
            return true;
          });
        }, workoutCard);
        const pills = document.querySelectorAll('#m-pills .mpill');
        pills.forEach(b => {
          b.onclick = () => {
            vib(25);
            curMuscle = b.dataset.m;
            pills.forEach(x => x.classList.toggle('on', x == b));
            redraw(true);
          };
        });
      }
    }
    if (name == 'builder') {
      const isDup = arg && String(arg).startsWith('dup-');
      const srcId = isDup ? String(arg).slice(4) : arg;
      const editW = !isDup && arg && woMap[arg] && woMap[arg]._custom ? woMap[arg] : null;
      const dupW = isDup && woMap[srcId] ? woMap[srcId] : null;
      const srcW = editW || dupW;
      let items = srcW && srcW.s && srcW.s.length
        ? srcW.s.flatMap(st => st.slice(1).map(n => ({ id: n[0], unit: n[1] || 'repeat', amt: n[2] || 10 })))
        : [
            { id: 85, unit: 'repeat', amt: 15 },
            { id: 53, unit: 'second', amt: 30 }
          ].filter(x => exMap[x.id]);
      let libMuscle = '', libQuery = '';

      const renderSummary = () => {
        const box = document.getElementById('cb-summary');
        if (!box) return;
        const rounds = +document.getElementById('cb-rounds').value || 3;
        const rb = +document.getElementById('cb-rest').value || 20;
        const pseudo = { rb, rr: rb, s: [[rounds, ...items.map(x => [x.id, x.unit, x.amt, rb])]] };
        const mins = items.length ? Math.max(1, Math.round(woSeconds(pseudo) / 60)) : 0;
        const txt = items.map(x => exCleanName(exMap[x.id])).join(' ');
        const mLabels = muscleLabelsMap();
        const mf = detectMuscles(txt);
        const mTags = Object.keys(mf).filter(k => mf[k]).map(k => `<span class="tag">${esc(mLabels[k])}</span>`).join('');
        box.innerHTML = `<span class="tag pro">⏱ ~${mins} ${L == 'ru' ? 'мин' : 'min'}</span><span class="tag">${items.length} ${L == 'ru' ? 'упр.' : 'ex'} × ${rounds}</span>${mTags}`;
      };

      const renderPicked = () => {
        const box = document.getElementById('cb-picked');
        if (!box) return;
        if (!items.length) {
          box.innerHTML = `<div class="empty" style="padding:18px 12px">${L == 'ru' ? 'Добавьте хотя бы 1 упражнение из списка ниже' : 'Add at least 1 exercise below'}</div>`;
          renderSummary();
          return;
        }
        box.innerHTML = items.map((it, idx) => {
          const e = exMap[it.id];
          return `<div class="cb-item" data-idx="${idx}">
            <span class="cb-th">${e && e.img ? `<img src="img/ex/svg_norm_${e.id}.svg" alt="">` : uiSvg('dumbbell', 16)}</span>
            <div class="cb-info">
              <b>${esc(e ? exName(e) : '#' + it.id)}</b>
              <div class="cb-ctrls">
                <button type="button" class="cb-unit" data-act="unit">${it.unit === 'second' ? t('sec') : t('rep')}</button>
                <div class="cb-step">
                  <button type="button" data-act="sub">−</button>
                  <span>${it.amt}</span>
                  <button type="button" data-act="add">+</button>
                </div>
              </div>
            </div>
            <div class="cb-ord">
              <button type="button" data-act="up" ${idx === 0 ? 'disabled' : ''}>↑</button>
              <button type="button" data-act="dn" ${idx === items.length - 1 ? 'disabled' : ''}>↓</button>
              <button type="button" data-act="del" class="del">✕</button>
            </div>
          </div>`;
        }).join('');
        renderSummary();
      };

      const renderLib = () => {
        const box = document.getElementById('cb-lib');
        if (!box) return;
        const pickedSet = new Set(items.map(x => x.id));
        const q = norm(libQuery);
        const matched = D.exercises.filter(e => {
          if (!(e.n && (e.n.ru || e.n.en))) return false;
          if (q && !norm(e.n.ru + ' ' + e.n.en).includes(q)) return false;
          if (libMuscle && MUSCLE_RULES[libMuscle] && !MUSCLE_RULES[libMuscle].test(exCleanName(e) + ' ' + exText(e))) return false;
          return true;
        }).sort((a, b) => (b.img ? 1 : 0) - (a.img ? 1 : 0) || (b.rating || 0) - (a.rating || 0)).slice(0, 30);
        if (!matched.length) {
          box.innerHTML = `<div class="empty" style="padding:18px 12px">${t('nothing')}</div>`;
          return;
        }
        box.innerHTML = matched.map(e => `
          <div class="cb-lib-row">
            <span class="cb-th">${e.img ? `<img src="img/ex/svg_norm_${e.id}.svg" alt="">` : uiSvg('dumbbell', 16)}</span>
            <div class="cb-info">
              <b>${esc(exName(e))}</b>
              <small>${esc(eqLbl(e.eq))}${getExVideo(e) ? ' · 3D' : ''}</small>
            </div>
            <button type="button" class="btn ${pickedSet.has(e.id) ? 'alt' : ''}" data-add-ex="${e.id}" style="padding:6px 12px;font-size:12px;">
              ${pickedSet.has(e.id) ? '✓ +' : '+ ' + (L == 'ru' ? 'Добавить' : 'Add')}
            </button>
          </div>`).join('');
      };

      document.getElementById('cb-picked').onclick = ev => {
        const btn = ev.target.closest('[data-act]');
        if (!btn) return;
        const row = btn.closest('[data-idx]');
        if (!row) return;
        const idx = +row.dataset.idx, act = btn.dataset.act, it = items[idx];
        if (!it) return;
        vib(20);
        if (act === 'unit') {
          it.unit = it.unit === 'second' ? 'repeat' : 'second';
          it.amt = it.unit === 'second' ? 30 : 12;
        } else if (act === 'sub') {
          it.amt = Math.max(1, it.amt - (it.unit === 'second' ? 5 : 1));
        } else if (act === 'add') {
          it.amt = it.amt + (it.unit === 'second' ? 5 : 1);
        } else if (act === 'up' && idx > 0) {
          [items[idx - 1], items[idx]] = [items[idx], items[idx - 1]];
        } else if (act === 'dn' && idx < items.length - 1) {
          [items[idx + 1], items[idx]] = [items[idx], items[idx + 1]];
        } else if (act === 'del') {
          items.splice(idx, 1);
        }
        renderPicked();
        renderLib();
      };

      document.getElementById('cb-lib').onclick = ev => {
        const btn = ev.target.closest('[data-add-ex]');
        if (!btn) return;
        const e = exMap[+btn.dataset.addEx];
        if (!e) return;
        vib(25); sfx('step');
        const unit = e.unit === 'second' ? 'second' : 'repeat';
        items.push({ id: e.id, unit, amt: unit === 'second' ? 30 : 12 });
        renderPicked();
        renderLib();
      };

      document.getElementById('cb-q').oninput = ev => { libQuery = ev.target.value; renderLib(); };
      document.querySelectorAll('#cb-pills [data-cm]').forEach(b => {
        b.onclick = () => {
          vib(20);
          libMuscle = b.dataset.cm;
          document.querySelectorAll('#cb-pills [data-cm]').forEach(x => x.classList.toggle('on', x === b));
          renderLib();
        };
      });
      ['cb-rounds', 'cb-rest'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.onchange = renderSummary;
      });

      const buildAndSave = () => {
        if (!items.length) {
          alert(L == 'ru' ? 'Добавьте хотя бы одно упражнение!' : 'Add at least one exercise!');
          return null;
        }
        const rawName = document.getElementById('cb-title').value.trim();
        const title = rawName || (L == 'ru' ? 'Моя тренировка' : 'Custom Workout');
        const rounds = +document.getElementById('cb-rounds').value || 3;
        const rb = +document.getElementById('cb-rest').value || 20;
        const eq = document.getElementById('cb-eq').value || 'no_equipment';
        const cw = {
          id: editW ? editW.id : ('cw_' + Date.now()),
          _custom: true,
          t: { ru: title, en: title },
          d: { ru: L == 'ru' ? 'Собственная тренировка из конструктора' : 'Custom workout built by user', en: 'Custom workout built by user' },
          eq,
          diff: rounds >= 4 ? 'hard' : (rounds === 1 ? 'easy' : 'normal'),
          temp: rb <= 15 ? 'intense' : 'moderate',
          rb,
          rr: rb,
          rating: 5.0,
          s: [[rounds, ...items.map(x => [x.id, x.unit, x.amt, rb])]]
        };
        upsertCustomWorkout(cw);
        return cw;
      };

      document.getElementById('cb-save').onclick = () => {
        const cw = buildAndSave();
        if (!cw) return;
        vib(30); sfx('done');
        location.hash = '#/workout/' + cw.id;
      };
      document.getElementById('cb-save-play').onclick = () => {
        const cw = buildAndSave();
        if (!cw) return;
        vib(35);
        play(cw);
      };

      renderPicked();
      renderLib();
    }
    if (name == 'exercises') pagedList(() => {
      const q = norm(document.getElementById('q').value), eq = document.getElementById('f-eq').value, l = document.getElementById('f-l').value, im = document.getElementById('f-i').checked;
      return D.exercises.filter(e => (!im || e.img) && (!eq || e.eq == eq) && (!l || e.lvl == l) && (!q || norm(exName(e)).includes(q)));
    }, exerciseCard);
    if (name == 'coach' && COACH.enabled) {
      const box = document.getElementById('msgs'), inp = document.getElementById('cin');
      const form = document.getElementById('cform');
      const sendBtn = (form && typeof form.querySelector === 'function') ? form.querySelector('.send') : null;
      const clrBtn = document.getElementById('cclr');
      const getCoachStorageKey = () => {
        const uTok = (typeof localStorage !== 'undefined' && (localStorage.userToken || (localStorage.getItem && localStorage.getItem('userToken')))) || '';
        const uName = (typeof localStorage !== 'undefined' && (localStorage.userName || (localStorage.getItem && localStorage.getItem('userName')))) || '';
        const cleanName = String(uName).trim().toLowerCase();
        if (uTok && typeof isLocalToken === 'function' && isLocalToken(uTok)) {
          return 'coach_local_' + (cleanName || 'user');
        }
        if (uTok && cleanName) {
          return 'coach_u_' + cleanName;
        }
        return 'coach_guest';
      };

      const loadCoachHist = () => {
        const k = getCoachStorageKey();
        let h = [];
        try {
          const raw = (typeof localStorage !== 'undefined' && (localStorage[k] || (localStorage.getItem && localStorage.getItem(k)))) || '';
          if (raw) {
            h = JSON.parse(raw);
          } else if (k === 'coach_guest') {
            const leg = (typeof localStorage !== 'undefined' && (localStorage.coach || (localStorage.getItem && localStorage.getItem('coach')))) || '';
            if (leg) h = JSON.parse(leg);
          }
          if (!Array.isArray(h)) h = [];
        } catch (_) { h = []; }
        return h.filter(m => m && (m.role === 'user' || m.role === 'model') && typeof m.text === 'string' && m.text.trim());
      };

      const saveCoachHist = h => {
        try {
          const k = getCoachStorageKey();
          const str = JSON.stringify(h.slice(-30));
          if (typeof localStorage !== 'undefined') {
            localStorage[k] = str;
            if (typeof localStorage.setItem === 'function') localStorage.setItem(k, str);
          }
        } catch (_) {}
      };

      let hist2 = loadCoachHist();
      let busy = false;
      let coachReqSeq = 0;
      let coachAbort = null;
      let historyAbort = null;
      let activeClearPromise = null;
      let lastError = null;

      const setBusy = flag => {
        busy = !!flag;
        if (form && form.classList && typeof form.classList.toggle === 'function') form.classList.toggle('is-busy', busy);
        if (inp) inp.disabled = busy;
        if (sendBtn) sendBtn.disabled = busy;
        if (typeof document.querySelectorAll === 'function') {
          document.querySelectorAll('.chip2').forEach(b => { b.disabled = busy; });
        }
      };

      window._cancelCoachRequest = () => {
        coachReqSeq++;
        setBusy(false);
        if (coachAbort) { try { coachAbort.abort(); } catch (_) {} coachAbort = null; }
        if (historyAbort) { try { historyAbort.abort(); } catch (_) {} historyAbort = null; }
      };

      const md = x => esc(x)
        .replace(/\[\[(program|workout|exercise):(\d+)\|([^\]]+)\]\]/g, (m, k, id, nm) => `<a class="ref" href="#/${k}/${id}">${nm}</a>`)
        .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
        .replace(/^\s*[*-] /gm, '• ')
        .replace(/\n/g, '<br>');
      const bubble = (role, text) => `<div class="m ${role}"><div class="mb">${role == 'model' ? md(text) : esc(text).replace(/\n/g, '<br>')}</div></div>`;
      const draw = (scrollToEnd = false) => {
        if (!box) return;
        let html = bubble('model', t('coachHi')) + hist2.map(m => bubble(m.role, m.text)).join('');
        if (lastError) {
          html += `<div class="m model error"><div class="mb"><div>${esc(lastError.text)}</div>${lastError.retryable ? `<button type="button" class="coach-retry-btn" id="coach-retry-btn">↻ ${esc(L == 'ru' ? 'Повторить' : 'Retry')}</button>` : ''}</div></div>`;
        }
        box.innerHTML = html;
        if (lastError && lastError.retryable) {
          const retryBtn = document.getElementById('coach-retry-btn');
          if (retryBtn) {
            const retryPayload = { q: lastError.q, reqId: lastError.reqId };
            retryBtn.onclick = () => send(retryPayload.q, retryPayload.reqId);
          }
        }
        if (scrollToEnd) window.scrollTo(0, document.body.scrollHeight);
      };

      const syncServerHistory = async () => {
        const uTok = localStorage.userToken || '';
        if (uTok && typeof isLocalToken === 'function' && isLocalToken(uTok)) return;
        const mySeq = coachReqSeq;
        const myStorageKey = getCoachStorageKey();
        if (historyAbort) { try { historyAbort.abort(); } catch (_) {} }
        historyAbort = typeof AbortController !== 'undefined' ? new AbortController() : null;
        try {
          const headers = {};
          if (uTok) headers['Authorization'] = 'Bearer ' + uTok;
          const opts = { method: 'GET', headers, credentials: 'same-origin' };
          if (historyAbort) opts.signal = historyAbort.signal;
          const r = await fetch('/api/coach/history', opts);
          if (mySeq !== coachReqSeq || myStorageKey !== getCoachStorageKey() || busy || activeClearPromise) return;
          if (r.status === 401) {
            showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Сессия истекла, пожалуйста, войдите снова' : 'Session expired, please sign in again');
            return;
          }
          if (!r.ok) return;
          const j = await r.json().catch(() => null);
          if (mySeq !== coachReqSeq || myStorageKey !== getCoachStorageKey() || busy || activeClearPromise) return;
          if (j && Array.isArray(j.messages)) {
            const cleanMsgs = j.messages
              .filter(m => m && (m.role === 'user' || m.role === 'model') && typeof m.text === 'string' && m.text.trim())
              .map(m => ({ role: m.role, text: m.text.trim() }))
              .slice(-30);
            hist2 = cleanMsgs;
            saveCoachHist(hist2);
            draw(hist2.length > 0);
          }
        } catch (_) {}
      };

      const send = async (q, retryReqId = null) => {
        q = (q || '').trim(); if (!q || busy) return;
        setBusy(true);
        if (historyAbort) { try { historyAbort.abort(); } catch (_) {} historyAbort = null; }
        if (!retryReqId && inp) inp.value = '';
        if (activeClearPromise) {
          try { await activeClearPromise; } catch (_) {}
        }
        const mySeq = ++coachReqSeq;
        const myStorageKey = getCoachStorageKey();
        if (coachAbort) { try { coachAbort.abort(); } catch (_) {} }
        coachAbort = typeof AbortController !== 'undefined' ? new AbortController() : null;

        const clientReqId = retryReqId || ('cr_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8));
        if (!retryReqId && lastError && hist2.length && hist2[hist2.length - 1].role === 'user' && hist2[hist2.length - 1].text === lastError.q) {
          hist2.pop();
        }
        lastError = null;
        const lastSaved = hist2.length ? hist2[hist2.length - 1] : null;
        if (!(retryReqId && lastSaved && lastSaved.role === 'user' && lastSaved.text === q)) {
          hist2.push({ role: 'user', text: q });
        }
        draw(true);
        if (box) {
          box.insertAdjacentHTML('beforeend', `<div class="m model" id="typ"><div class="mb typing" aria-label="${esc(t('coachTyping'))}"><i></i><i></i><i></i></div></div>`);
          window.scrollTo(0, document.body.scrollHeight);
        }
        try {
          const uTok = localStorage.userToken || '';
          if (uTok && typeof isLocalToken === 'function' && !isLocalToken(uTok) && cloudSyncTimer && typeof pushCloudSync === 'function') {
            await pushCloudSync().catch(() => false);
            if (mySeq !== coachReqSeq || myStorageKey !== getCoachStorageKey()) return;
          }
          const headers = { 'Content-Type': 'application/json' };
          if (uTok && typeof isLocalToken === 'function' && !isLocalToken(uTok)) {
            headers['Authorization'] = 'Bearer ' + uTok;
          }
          const fetchOpts = {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify({ message: q, reqId: clientReqId, messages: hist2.slice(-12) })
          };
          if (coachAbort) fetchOpts.signal = coachAbort.signal;
          const r = await fetch('/api/coach', fetchOpts);
          const j = await r.json().catch(() => ({}));
          if (mySeq !== coachReqSeq || myStorageKey !== getCoachStorageKey()) return;
          if (r.ok && j && j.reply) {
            hist2.push({ role: 'model', text: String(j.reply) });
            hist2 = hist2.slice(-30);
            saveCoachHist(hist2);
          } else {
            const errMsg = (j && j.error) ? String(j.error) : (L == 'ru' ? `Ошибка сервера (${r.status})` : `Server error (${r.status})`);
            lastError = {
              text: '⚠️ ' + errMsg,
              q,
              reqId: clientReqId,
              retryable: (r.status >= 500 || r.status === 429 || r.status === 408)
            };
          }
        } catch (e) {
          if (mySeq !== coachReqSeq || myStorageKey !== getCoachStorageKey() || (e && e.name === 'AbortError')) return;
          lastError = {
            text: '⚠️ ' + (L == 'ru' ? 'Нет связи с сервером' : 'Connection error'),
            q,
            reqId: clientReqId,
            retryable: true
          };
        } finally {
          if (mySeq === coachReqSeq && myStorageKey === getCoachStorageKey()) {
            setBusy(false);
            draw(true);
          }
        }
      };
      if (form) form.onsubmit = e => { e.preventDefault(); send(inp ? inp.value : ''); };
      document.querySelectorAll('.chip2').forEach(b => b.onclick = () => send(b.dataset.q));
      if (clrBtn) clrBtn.onclick = async () => {
        coachReqSeq++;
        setBusy(false);
        if (coachAbort) { try { coachAbort.abort(); } catch (_) {} coachAbort = null; }
        if (historyAbort) { try { historyAbort.abort(); } catch (_) {} historyAbort = null; }
        lastError = null;
        const prevHist = hist2;
        hist2 = [];
        const currentKey = getCoachStorageKey();
        try { localStorage[currentKey] = '[]'; } catch (_) {}
        draw(false);
        const uTok = localStorage.userToken || '';
        const headers = {};
        if (uTok && typeof isLocalToken === 'function' && !isLocalToken(uTok)) {
          headers['Authorization'] = 'Bearer ' + uTok;
        }
        activeClearPromise = fetch('/api/coach/clear', { method: 'POST', headers, credentials: 'same-origin' })
          .then(async r => {
            if (!r.ok) {
              const errJson = await r.json().catch(() => ({}));
              throw new Error(errJson.error || 'Ошибка очистки на сервере');
            }
            return r;
          })
          .catch(err => {
            // Если запрос очистки завершился ошибкой и пользователь не успел отправить новый вопрос
            if (hist2.length === 0) {
              hist2 = prevHist;
              saveCoachHist(hist2);
              draw(false);
              showAppToast(CFG.brand || 'RizzaFit', '⚠️ ' + (err.message || (L == 'ru' ? 'Не удалось очистить историю' : 'Failed to clear history')));
            }
          })
          .finally(() => {
            activeClearPromise = null;
          });
      };
      draw(false);
      syncServerHistory();
      window.scrollTo(0, 0);
    }
    if (name == 'program') {
      const unlockBtn = document.getElementById('prog-unlock-btn');
      if (unlockBtn) unlockBtn.onclick = () => openPaywallModal();
      const unlockDescBtn = document.getElementById('prog-unlock-desc-btn');
      if (unlockDescBtn) unlockDescBtn.onclick = () => openPaywallModal();
      const lockOverlay = document.getElementById('prog-desc-lock-overlay');
      if (lockOverlay) lockOverlay.onclick = () => openPaywallModal();
      document.querySelectorAll('.prog-locked-link').forEach(a => {
        a.onclick = e => {
          e.preventDefault();
          vib(20);
          openPaywallModal();
        };
      });
      const pinBtn = document.getElementById('prog-pin');
      if (pinBtn) pinBtn.onclick = () => {
        if (!isUserPro()) {
          openPaywallModal();
          return;
        }
        vib(25);
        const ps = getProgState();
        const pid = pinBtn.dataset.pid;
        ps.activeId = String(ps.activeId) === String(pid) ? null : pid;
        saveProgState(ps);
        render();
      };
      const tickBtn = document.getElementById('prog-tick');
      if (tickBtn) tickBtn.onclick = () => {
        if (!isUserPro()) {
          openPaywallModal();
          return;
        }
        vib(35); sfx('done');
        const ps = getProgState();
        const pid = tickBtn.dataset.pid;
        if (!Array.isArray(ps.logs[pid])) ps.logs[pid] = [];
        ps.logs[pid].push(new Date().toISOString().slice(0, 10));
        if (!ps.activeId) ps.activeId = pid;
        saveProgState(ps);
        render();
      };
      const undoBtn = document.getElementById('prog-undo');
      if (undoBtn) undoBtn.onclick = () => {
        vib(20);
        const ps = getProgState();
        const pid = undoBtn.dataset.pid;
        if (Array.isArray(ps.logs[pid]) && ps.logs[pid].length) {
          ps.logs[pid].pop();
          saveProgState(ps);
          render();
        }
      };
      const resetBtn = document.getElementById('prog-reset');
      if (resetBtn) resetBtn.onclick = () => {
        if (!confirm(L == 'ru' ? 'Сбросить отметки этой программы?' : 'Reset progress for this program?')) return;
        vib(25);
        const ps = getProgState();
        delete ps.logs[resetBtn.dataset.pid];
        saveProgState(ps);
        render();
      };
    }
    if (name == 'workout') {
      const w = woMap[arg];
      if (w) {
        const unlockMain = document.getElementById('wo-unlock-main');
        if (unlockMain) unlockMain.onclick = () => openPaywallModal();
        const unlockPlan = document.getElementById('wo-unlock-plan');
        if (unlockPlan) unlockPlan.onclick = () => openPaywallModal();
        const lockOverlay = document.getElementById('wo-lock-overlay');
        if (lockOverlay) lockOverlay.onclick = () => openPaywallModal();
        const goBtn = document.getElementById('go');
        if (goBtn) {
          goBtn.onclick = () => {
            if (isProWorkout(w) && !isUserPro()) {
              openPaywallModal();
              return;
            }
            play(w);
          };
        }
        const wb = document.getElementById('warmup');
        if (wb) {
          wb.onclick = () => {
            if (isProWorkout(w) && !isUserPro()) {
              openPaywallModal();
              return;
            }
            play(WARMUP_WORKOUT);
          };
        }
        const fb = document.getElementById('fav-toggle');
        if (fb) fb.onclick = () => {
          const on = toggleFav(w.id);
          fb.innerHTML = uiSvg(on ? 'heartFill' : 'heart', 16);
          fb.classList.toggle('on', on);
        };
        const delBtn = document.getElementById('wo-del');
        if (delBtn) delBtn.onclick = () => {
          if (confirm(L == 'ru' ? 'Удалить эту тренировку?' : 'Delete this custom workout?')) {
            removeCustomWorkout(w.id);
            vib(25);
            location.hash = '#/workouts';
          }
        };
      }
    }
    if (name == 'exercise') {
      const b = document.getElementById('log-pr-btn');
      if (b) {
        b.onclick = () => {
          const prs = JSON.parse(localStorage.prs || '{}');
          const cur = prs[arg] || '';
          const val = prompt(L == 'ru' ? 'Введите ваш лучший результат (повторений):' : 'Enter your best reps:', cur);
          if (val && !isNaN(val) && +val > 0) {
            prs[arg] = +val;
            localStorage.prs = JSON.stringify(prs);
            if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
            if (window.AthleteProfile) window.AthleteProfile.addDuelBonus(60);
            vib(35);
            render();
          }
        };
      }
    }
    if (name == 'workout' || name == 'exercise') {
      const box = document.getElementById('m3d-box');
      if (box) {
        let m = {};
        try { m = JSON.parse(box.dataset.muscles || '{}'); } catch(e){}

        const applyHighlights = () => {
          // Front mappings
          box.querySelectorAll('#front_chest').forEach(el => el.classList.toggle('active', !!m.chest));
          box.querySelectorAll('#front_abs, #front_obliques').forEach(el => el.classList.toggle('active', !!m.abs));
          box.querySelectorAll('#front_biceps').forEach(el => el.classList.toggle('active', !!m.arms));
          box.querySelectorAll('#front_quads').forEach(el => el.classList.toggle('active', !!m.legs));
          box.querySelectorAll('#front_shoulders_front, #front_shoulders_side').forEach(el => el.classList.toggle('active', !!m.shoulders));
          
          // Back mappings
          box.querySelectorAll('#back_lats, #back_lower_back').forEach(el => el.classList.toggle('active', !!m.back));
          box.querySelectorAll('#back_traps').forEach(el => el.classList.toggle('active', !!m.back || !!m.shoulders));
          box.querySelectorAll('#back_triceps').forEach(el => el.classList.toggle('active', !!m.arms));
          box.querySelectorAll('#back_shoulders_back').forEach(el => el.classList.toggle('active', !!m.shoulders));
          box.querySelectorAll('#back_glutes, #back_hams, #back_calves').forEach(el => el.classList.toggle('active', !!m.legs));
        };

        applyHighlights();

        const pills = box.querySelectorAll('.m3d-pill');
        pills.forEach(p => {
          p.onclick = () => {
            vib(25);
            const k = p.dataset.muscle;
            m[k] = !m[k];
            p.classList.toggle('active', m[k]);
            applyHighlights();
          };
        });

        const svgMap = {
          'front_chest': 'chest',
          'front_abs': 'abs',
          'front_obliques': 'abs',
          'front_biceps': 'arms',
          'front_quads': 'legs',
          'front_shoulders_front': 'shoulders',
          'front_shoulders_side': 'shoulders',
          'back_lats': 'back',
          'back_lower_back': 'back',
          'back_traps': 'back',
          'back_triceps': 'arms',
          'back_shoulders_back': 'shoulders',
          'back_glutes': 'legs',
          'back_hams': 'legs',
          'back_calves': 'legs'
        };
        box.querySelectorAll('.muscle-layer').forEach(layer => {
          const group = svgMap[layer.id];
          if (group) {
            layer.onclick = () => {
              vib(25);
              m[group] = !m[group];
              const pill = box.querySelector(`.m3d-pill[data-muscle="${group}"]`);
              if (pill) pill.classList.toggle('active', m[group]);
              applyHighlights();
            };
          }
        });
      }
    }
    if (name == 'history' || name == 'profile') {
      if (!isLoggedIn()) {
        const loginBtn = document.getElementById('guest-btn-login');
        if (loginBtn) loginBtn.onclick = () => openCloudAuthModal('login');
        const regBtn = document.getElementById('guest-btn-reg');
        if (regBtn) regBtn.onclick = () => openCloudAuthModal('register');
        app.querySelectorAll('[data-soc-provider]').forEach(btn => {
          btn.onclick = () => handleSocialAuth(btn.dataset.socProvider);
        });
        return;
      }
      const clr = document.getElementById('clr');
      if (clr) clr.onclick = () => {
        if (confirm(L == 'ru' ? 'Очистить историю и личные рекорды?' : 'Clear history and records?')) {
          localStorage.hist = '[]';
          localStorage.prs = '{}';
          localStorage.exLogs = '{}';
          if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
          vib(30);
          render();
        }
      };
      app.querySelectorAll('[data-ap-action]').forEach(el => {
        el.onclick = () => {
          vib(20);
          const act = el.dataset.apAction;
          if (act === 'tasks' || act === 'points') {
            location.hash = '#/workouts';
            return;
          }
          if (act === 'streak') {
            const AP = window.AthleteProfile;
            if (!AP) return;
            const now = new Date();
            let viewY = now.getFullYear(), viewM = now.getMonth();
            let selectedIso = now.toISOString().slice(0, 10);
            const bd = document.createElement('div');
            bd.className = 'ap-modal-backdrop';
            const closeCal = () => { bd.remove(); render(); };

            const renderCalModal = () => {
              const allH = hist();
              const fz = AP.getFreezeState();
              const frozenSet = new Set(fz.usedDates);
              const byDate = {};
              allH.forEach(x => {
                const iso = new Date(x.t).toISOString().slice(0, 10);
                if (!byDate[iso]) byDate[iso] = [];
                byDate[iso].push(x);
              });
              const streakNow = calcStreak(allH);
              const monthNames = L == 'ru'
                ? ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
                : ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
              const wd = L == 'ru' ? ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] : ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
              const firstDow = (new Date(viewY, viewM, 1).getDay() + 6) % 7;
              const daysInM = new Date(viewY, viewM + 1, 0).getDate();
              const todayIso = new Date().toISOString().slice(0, 10);
              const yestDt = new Date(); yestDt.setDate(yestDt.getDate() - 1);
              const yestIso = yestDt.toISOString().slice(0, 10);
              const canFreezeYest = fz.tokens > 0 && !byDate[yestIso] && !frozenSet.has(yestIso);

              let locP = {};
              try { locP = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
              const meMerged = AP.merge(Object.assign({}, CFG.athlete || {}, locP), {
                workoutsCount: allH.length,
                streak: streakNow,
                prsCount: Object.keys(JSON.parse(localStorage.prs || '{}')).length
              });

              const monthPrefix = `${viewY}-${String(viewM + 1).padStart(2, '0')}`;
              const monthItems = allH.filter(x => new Date(x.t).toISOString().slice(0, 7) === monthPrefix);
              const monthMins = Math.round(monthItems.reduce((s, x) => s + (x.s || 0), 0) / 60);

              const cells = [];
              for (let k = 0; k < firstDow; k++) cells.push('<span class="cal-cell empty"></span>');
              for (let d = 1; d <= daysInM; d++) {
                const iso = `${viewY}-${String(viewM + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                const hasW = !!(byDate[iso] && byDate[iso].length);
                const isFrz = frozenSet.has(iso);
                const isTod = iso === todayIso;
                const isSel = iso === selectedIso;
                cells.push(`<button type="button" class="cal-cell ${hasW ? 'done' : ''} ${isFrz ? 'frozen' : ''} ${isTod ? 'today' : ''} ${isSel ? 'sel' : ''}" data-cal-iso="${iso}">
                  <span>${d}</span>
                  ${hasW ? '<i></i>' : (isFrz ? `<em>${uiSvg('snowflake', 10)}</em>` : '')}
                </button>`);
              }

              const selList = byDate[selectedIso] || [];
              const selFrozen = frozenSet.has(selectedIso);
              const selDetail = selList.length
                ? selList.map(x => {
                    const rm = x.rpe ? RPE_OPTS.find(r => r.id === x.rpe) : null;
                    return `<div class="cal-day-row"><b>${esc(woMap[x.id] ? woName(woMap[x.id]) : '#' + x.id)}</b><span>${rm ? rm.icon + ' ' : ''}${uiSvg('clock', 12)} ${Math.max(1, Math.round((x.s || 0) / 60))} ${L == 'ru' ? 'мин' : 'min'}</span></div>`;
                  }).join('')
                : (selFrozen
                  ? `<div class="cal-day-empty" style="display:flex;align-items:center;justify-content:center;gap:6px;">${uiSvg('snowflake', 14)} ${L == 'ru' ? 'Серия сохранена заморозкой' : 'Streak protected by freeze'}</div>`
                  : `<div class="cal-day-empty">${L == 'ru' ? 'Нет тренировок за этот день' : 'No workouts logged on this day'}</div>`);

              bd.innerHTML = `<div class="ap-modal cal-modal">
                <div class="ap-notif-head">
                  <h3 style="display:flex;align-items:center;gap:8px;">${uiSvg('clock', 16)} ${L == 'ru' ? 'Календарь и серия' : 'Activity Calendar'}</h3>
                  <button type="button" class="fr-btn-del" id="cal-close">✕</button>
                </div>

                <div class="cal-kpis">
                  <div><b style="display:inline-flex;align-items:center;gap:4px;">${uiSvg('flame', 14)} ${streakNow}</b><small>${L == 'ru' ? 'Серия' : 'Streak'}</small></div>
                  <div><b>${monthItems.length}</b><small>${L == 'ru' ? 'За месяц' : 'This month'}</small></div>
                  <div><b>${monthMins}m</b><small>${L == 'ru' ? 'Минут' : 'Minutes'}</small></div>
                </div>

                <div class="cal-nav">
                  <button type="button" class="cal-arrow" id="cal-prev">‹</button>
                  <b>${monthNames[viewM]} ${viewY}</b>
                  <button type="button" class="cal-arrow" id="cal-next">›</button>
                </div>
                <div class="cal-wds">${wd.map(x => `<span>${x}</span>`).join('')}</div>
                <div class="cal-grid">${cells.join('')}</div>

                <div class="cal-sel-box">
                  <div class="cal-sel-lbl">${selectedIso}</div>
                  ${selDetail}
                </div>

                <div class="fz-box">
                  <div class="fz-head">
                    <div>
                      <b style="display:flex;align-items:center;gap:6px;">${uiSvg('snowflake', 14)} ${L == 'ru' ? 'Заморозка серии' : 'Streak Freeze'}</b>
                      <small>${L == 'ru' ? `В запасе: ${fz.tokens} из 3` : `Available: ${fz.tokens} of 3`}</small>
                    </div>
                    <span class="tag">${Math.round(meMerged.points).toLocaleString()} XP</span>
                  </div>
                  <div class="fz-actions">
                    ${canFreezeYest ? `<button type="button" class="btn fz-use" id="fz-use">${uiSvg('snowflake', 13)} ${L == 'ru' ? 'Заморозить вчера' : 'Freeze yesterday'}</button>` : ''}
                    ${fz.tokens < 3 ? `<button type="button" class="btn alt fz-buy" id="fz-buy">+ ${uiSvg('snowflake', 12)} ${L == 'ru' ? 'Купить (300 XP)' : 'Buy (300 XP)'}</button>` : ''}
                  </div>
                </div>
              </div>`;

              bd.onclick = ev => { if (ev.target === bd) closeCal(); };
              bd.querySelector('#cal-close').onclick = () => { vib(20); closeCal(); };
              bd.querySelector('#cal-prev').onclick = () => {
                vib(15);
                viewM--; if (viewM < 0) { viewM = 11; viewY--; }
                renderCalModal();
              };
              bd.querySelector('#cal-next').onclick = () => {
                vib(15);
                viewM++; if (viewM > 11) { viewM = 0; viewY++; }
                renderCalModal();
              };
              bd.querySelectorAll('[data-cal-iso]').forEach(c => {
                c.onclick = () => { vib(15); selectedIso = c.dataset.calIso; renderCalModal(); };
              });
              const uBtn = bd.querySelector('#fz-use');
              if (uBtn) uBtn.onclick = () => {
                if (AP.useFreezeOnDate(yestIso)) {
                  vib([35, 30, 50]); sfx('done');
                  selectedIso = yestIso;
                  renderCalModal();
                }
              };
              const bBtn = bd.querySelector('#fz-buy');
              if (bBtn) bBtn.onclick = () => {
                const res = AP.buyFreezeToken(meMerged.points, 300);
                if (!res.ok) {
                  alert(L == 'ru' ? 'Недостаточно XP (нужно 300 XP)' : 'Not enough XP (need 300 XP)');
                  return;
                }
                vib(30); sfx('done');
                renderCalModal();
              };
            };

            document.body.appendChild(bd);
            renderCalModal();
            return;
          }
          if (act === 'settings') {
            openSettingsSheet();
            return;
          }
          if (act === 'notify') {
            const AP = window.AthleteProfile;
            if (!AP) return;
            const bd = document.createElement('div');
            bd.className = 'ap-modal-backdrop';
            const closeNotifyModal = () => { bd.remove(); render(); };

            const renderNotifyModal = () => {
              const prefs = AP.getNotifPrefs();
              const allH = hist();
              const list = AP.buildNotifications({ lang: L, hist: allH, cfgAthlete: CFG.athlete });
              const unreadCount = list.filter(n => !n.read).length;
              const pushSup = typeof Notification !== 'undefined';
              const pushPerm = pushSup ? Notification.permission : 'unsupported';
              const pushStatus = !pushSup
                ? (L == 'ru' ? 'Пуш-уведомления не поддерживаются — покажем внутри сайта' : 'Browser push unsupported — shown in-app')
                : pushPerm === 'granted'
                  ? (L == 'ru' ? '✓ Уведомления браузера разрешены' : '✓ Browser notifications allowed')
                  : pushPerm === 'denied'
                    ? (L == 'ru' ? '⚠️ В браузере запрещены — покажем баннер на сайте' : '⚠️ Browser blocked — in-app banner active')
                    : (L == 'ru' ? 'При включении запросим разрешение браузера' : 'Browser permission will be requested when enabled');

              bd.innerHTML = `<div class="ap-modal ap-notif-modal">
                <div class="ap-notif-head">
                  <h3 style="display:flex;align-items:center;gap:8px;">${uiSvg('bell', 16)} ${L == 'ru' ? 'Уведомления' : 'Notifications'}${unreadCount ? ` <span class="ap-notif-pill">${unreadCount}</span>` : ''}</h3>
                  <div style="display:flex;align-items:center;gap:6px;">
                    ${unreadCount ? `<button type="button" class="ap-n-readall" id="ap-n-readall">✓ ${L == 'ru' ? 'Прочитать' : 'Mark read'}</button>` : ''}
                    <button type="button" class="fr-btn-del" id="ap-n-close">✕</button>
                  </div>
                </div>

                <div class="ap-notif-list">
                  ${list.length ? list.map(n => `
                    <button type="button" class="ap-notif-item ${n.read ? 'read' : 'unread'} tone-${n.tone || 'gold'}" data-nid="${esc(n.id)}" data-nhref="${esc(n.href || '')}">
                      <span class="ap-notif-ic">${n.icon}</span>
                      <span class="ap-notif-copy">
                        <b>${esc(n.title)}</b>
                        <small>${esc(n.body)}</small>
                      </span>
                      ${!n.read ? '<i class="ap-n-unread-dot"></i>' : (n.href ? '<span class="ap-n-go">›</span>' : '')}
                    </button>`).join('') : `
                    <div class="ap-notif-empty">✓ ${L == 'ru' ? 'Всё чисто — новых уведомлений нет' : 'All caught up — no new notifications'}</div>`}
                </div>

                <div class="ap-notif-pref-box">
                  <div class="ap-n-sec-lbl">${uiSvg('clock', 12)} ${L == 'ru' ? 'Напоминания о тренировке' : 'Workout Reminders'}</div>
                  <div class="ap-n-row">
                    <label class="ap-n-check">
                      <input type="checkbox" id="ap-n-en" ${prefs.enabled ? 'checked' : ''}>
                      <span>${L == 'ru' ? 'Напоминать ежедневно в' : 'Remind daily at'}</span>
                    </label>
                    <input type="time" id="ap-n-time" class="ap-n-time" value="${esc(prefs.time)}">
                  </div>
                  <div class="ap-n-status">${pushStatus}</div>
                  <div class="ap-n-toggles">
                    <button type="button" class="ap-n-chip ${prefs.duels ? 'on' : ''}" id="ap-n-duels">${uiSvg('swords', 13)} ${L == 'ru' ? 'Дуэли и квесты' : 'Duels & Quests'}</button>
                    <button type="button" class="ap-n-chip ${prefs.streak ? 'on' : ''}" id="ap-n-streak">${uiSvg('flame', 13)} ${L == 'ru' ? 'Серия и советы' : 'Streak & Tips'}</button>
                  </div>
                  <div style="display:flex;gap:8px;margin-top:12px;">
                    <button type="button" class="btn alt" style="flex:1;padding:9px 10px;font-size:12.5px;" id="ap-n-test">${uiSvg('bell', 13)} ${L == 'ru' ? 'Тест' : 'Test'}</button>
                    <button type="button" class="btn" style="flex:1;padding:9px 10px;font-size:12.5px;" id="ap-n-done">${L == 'ru' ? 'Готово' : 'Done'}</button>
                  </div>
                </div>
              </div>`;

              bd.onclick = ev => { if (ev.target === bd) closeNotifyModal(); };
              bd.querySelector('#ap-n-close').onclick = () => { vib(20); closeNotifyModal(); };
              bd.querySelector('#ap-n-done').onclick = () => { vib(20); closeNotifyModal(); };

              const readAllBtn = bd.querySelector('#ap-n-readall');
              if (readAllBtn) readAllBtn.onclick = () => {
                vib(25);
                AP.markNotifsRead(list.map(x => x.id));
                renderNotifyModal();
              };

              bd.querySelectorAll('.ap-notif-item').forEach(btn => {
                btn.onclick = () => {
                  vib(20);
                  AP.markNotifsRead([btn.dataset.nid]);
                  const href = btn.dataset.nhref;
                  if (href) {
                    bd.remove();
                    location.hash = href;
                  } else {
                    renderNotifyModal();
                  }
                };
              });

              const enEl = bd.querySelector('#ap-n-en');
              enEl.onchange = () => {
                vib(20);
                const enabled = enEl.checked;
                AP.saveNotifPrefs({ enabled, lastFiredDate: '' });
                if (enabled && typeof Notification !== 'undefined' && Notification.permission === 'default') {
                  Notification.requestPermission().then(() => renderNotifyModal()).catch(() => {});
                } else {
                  renderNotifyModal();
                }
              };

              bd.querySelector('#ap-n-time').onchange = ev => {
                AP.saveNotifPrefs({ time: ev.target.value || '19:00', lastFiredDate: '' });
              };
              bd.querySelector('#ap-n-duels').onclick = () => {
                vib(20);
                AP.saveNotifPrefs({ duels: !prefs.duels });
                renderNotifyModal();
              };
              bd.querySelector('#ap-n-streak').onclick = () => {
                vib(20);
                AP.saveNotifPrefs({ streak: !prefs.streak });
                renderNotifyModal();
              };
              bd.querySelector('#ap-n-test').onclick = () => {
                vib(30);
                const msg = L == 'ru' ? 'Пора размяться! Откройте тренировку и укрепите серию' : 'Time to move! Start a workout and grow your streak';
                showAppToast(CFG.brand || 'Flexa', msg, '#/workouts');
                if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
                  try { new Notification(CFG.brand || 'Flexa', { body: msg, icon: CFG.logo || 'img/logo.svg' }); } catch (e) {}
                }
              };
            };

            document.body.appendChild(bd);
            renderNotifyModal();
            return;
          }
          if (act === 'friends') {
            location.hash = '#/friends';
          }
        };
      });
      app.querySelectorAll('[data-act-days]').forEach(btn => {
        btn.onclick = () => {
          vib(15);
          const days = +btn.dataset.actDays || 7;
          app.querySelectorAll('[data-act-days]').forEach(b => b.classList.toggle('on', +b.dataset.actDays === days));
          const slot = document.getElementById('act-chart-slot');
          if (slot) slot.innerHTML = renderActivityChartHtml(hist(), days);
        };
      });
      const bodyLogBtn = document.getElementById('body-log-btn');
      if (bodyLogBtn) bodyLogBtn.onclick = () => {
        vib(20);
        const bm = getBodyMetrics();
        const latest = bm.logs.length ? bm.logs[bm.logs.length - 1] : null;
        const bd = document.createElement('div');
        bd.className = 'ap-modal-backdrop';
        bd.innerHTML = `
          <div class="ap-modal">
            <h3>${L == 'ru' ? 'Запись веса и замеров' : 'Log Body Weight'}</h3>
            <label>${L == 'ru' ? 'Текущий вес (кг)' : 'Current weight (kg)'}<input id="bm-w" type="number" step="0.1" min="25" max="300" value="${latest ? latest.w : ''}"></label>
            <label>${L == 'ru' ? 'Целевой вес (кг, необязательно)' : 'Target weight (kg, optional)'}<input id="bm-t" type="number" step="0.1" min="25" max="300" value="${bm.target || ''}"></label>
            <label>${L == 'ru' ? 'Талия (см, необязательно)' : 'Waist (cm, optional)'}<input id="bm-waist" type="number" step="0.5" min="40" max="200" value="${latest && latest.waist ? latest.waist : ''}"></label>
            <div class="ap-modal-actions">
              <button type="button" class="btn alt" id="bm-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
              <button type="button" class="btn" id="bm-save">${L == 'ru' ? 'Сохранить' : 'Save'}</button>
            </div>
          </div>`;
        document.body.appendChild(bd);
        bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
        bd.querySelector('#bm-cancel').onclick = () => bd.remove();
        bd.querySelector('#bm-save').onclick = () => {
          const wVal = parseFloat(bd.querySelector('#bm-w').value);
          const tVal = parseFloat(bd.querySelector('#bm-t').value);
          const waistVal = parseFloat(bd.querySelector('#bm-waist').value);
          if (!isNaN(wVal) && wVal > 0) {
            const iso = new Date().toISOString().slice(0, 10);
            const entry = { d: iso, w: +wVal.toFixed(1) };
            if (!isNaN(waistVal) && waistVal > 0) entry.waist = +waistVal.toFixed(1);
            const idx = bm.logs.findIndex(x => x.d === iso);
            if (idx >= 0) bm.logs[idx] = entry;
            else bm.logs.push(entry);
            if (bm.logs.length > 60) bm.logs = bm.logs.slice(-60);
          }
          bm.target = !isNaN(tVal) && tVal > 0 ? +tVal.toFixed(1) : null;
          saveBodyMetrics(bm);
          vib(30);
          bd.remove();
          render();
        };
      };

      const fpEditBtn = document.getElementById('fp-edit-btn');
      if (fpEditBtn) fpEditBtn.onclick = () => {
        vib(20);
        const fp = getFitnessProfile();
        const bm = getBodyMetrics();
        const latest = bm.logs.length ? bm.logs[bm.logs.length - 1] : null;
        let selSex = fp.sex || 'unspecified';
        let selGoal = fp.goal || '';
        let selLevel = fp.level || '';
        const bd = document.createElement('div');
        bd.className = 'ap-modal-backdrop';
        bd.innerHTML = `
          <div class="ap-modal">
            <h3>${L == 'ru' ? 'Мои параметры и цели' : 'My Parameters & Goals'}</h3>
            <div class="fp-modal-grid">
              <label>${L == 'ru' ? 'Рост (см)' : 'Height (cm)'}<input id="fp-h" type="number" step="0.5" min="100" max="250" value="${fp.heightCm || ''}" placeholder="178"></label>
              <label>${L == 'ru' ? 'Возраст (лет)' : 'Age'}<input id="fp-age" type="number" step="1" min="12" max="100" value="${fp.age || ''}" placeholder="28"></label>
              <label>${L == 'ru' ? 'Текущий вес (кг)' : 'Current weight (kg)'}<input id="fp-w" type="number" step="0.1" min="20" max="400" value="${latest ? latest.w : ''}" placeholder="80"></label>
              <label>${L == 'ru' ? 'Целевой вес (кг)' : 'Target weight (kg)'}<input id="fp-tw" type="number" step="0.1" min="20" max="400" value="${bm.target || ''}" placeholder="75"></label>
            </div>
            <div style="margin-top:10px">
              <div class="fp-lbl">${L == 'ru' ? 'Пол' : 'Sex'}</div>
              <div class="fp-chips" id="fp-sex-chips">
                ${FITNESS_SEX_OPTS.map(s => `<button type="button" class="fp-chip ${selSex === s.id ? 'on' : ''}" data-fp-sex="${s.id}">${esc(L == 'ru' ? s.ru : s.en)}</button>`).join('')}
              </div>
            </div>
            <label style="margin-top:10px;display:block">${L == 'ru' ? 'Цель тренировок' : 'Training goal'}
              <select id="fp-goal">
                <option value="">${L == 'ru' ? 'Не выбрана' : 'Not selected'}</option>
                ${FITNESS_GOALS.map(g => `<option value="${g.id}" ${selGoal === g.id ? 'selected' : ''}>${esc(L == 'ru' ? g.ru : g.en)}</option>`).join('')}
              </select>
            </label>
            <div style="margin-top:10px">
              <div class="fp-lbl">${L == 'ru' ? 'Уровень подготовки' : 'Fitness level'}</div>
              <div class="fp-chips" id="fp-lvl-chips">
                ${FITNESS_LEVELS.map(lv => `<button type="button" class="fp-chip ${selLevel === lv.id ? 'on' : ''}" data-fp-lvl="${lv.id}">${esc(L == 'ru' ? lv.ru : lv.en)}</button>`).join('')}
              </div>
            </div>
            <label style="margin-top:10px;display:block">${L == 'ru' ? 'Ограничения и травмы (необязательно)' : 'Injuries & limitations (optional)'}
              <textarea id="fp-inj" maxlength="160" placeholder="${L == 'ru' ? 'Например: беречь колени, боли в пояснице' : 'e.g. knee discomfort, avoid heavy axial load'}">${esc(fp.injuries || '')}</textarea>
            </label>
            <div class="ap-modal-actions">
              <button type="button" class="btn alt" id="fp-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
              <button type="button" class="btn" id="fp-save">${L == 'ru' ? 'Сохранить' : 'Save'}</button>
            </div>
          </div>`;
        document.body.appendChild(bd);
        bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
        bd.querySelector('#fp-cancel').onclick = () => bd.remove();
        bd.querySelectorAll('[data-fp-sex]').forEach(btn => {
          btn.onclick = () => {
            selSex = btn.dataset.fpSex;
            bd.querySelectorAll('[data-fp-sex]').forEach(b => b.classList.toggle('on', b.dataset.fpSex === selSex));
          };
        });
        bd.querySelectorAll('[data-fp-lvl]').forEach(btn => {
          btn.onclick = () => {
            selLevel = selLevel === btn.dataset.fpLvl ? '' : btn.dataset.fpLvl;
            bd.querySelectorAll('[data-fp-lvl]').forEach(b => b.classList.toggle('on', b.dataset.fpLvl === selLevel));
          };
        });
        bd.querySelector('#fp-save').onclick = () => {
          const hVal = parseFloat(bd.querySelector('#fp-h').value);
          const aVal = parseInt(bd.querySelector('#fp-age').value, 10);
          const wVal = parseFloat(bd.querySelector('#fp-w').value);
          const twVal = parseFloat(bd.querySelector('#fp-tw').value);
          const goalVal = bd.querySelector('#fp-goal').value;
          const injVal = bd.querySelector('#fp-inj').value;

          const nextFp = {};
          if (!isNaN(hVal) && hVal >= 100 && hVal <= 250) nextFp.heightCm = Math.round(hVal * 10) / 10;
          if (!isNaN(aVal) && aVal >= 12 && aVal <= 100) nextFp.age = aVal;
          if (selSex && selSex !== 'unspecified') nextFp.sex = selSex;
          else nextFp.sex = 'unspecified';
          if (goalVal) nextFp.goal = goalVal;
          if (selLevel) nextFp.level = selLevel;
          if (injVal && injVal.trim()) nextFp.injuries = injVal.trim();
          saveFitnessProfile(nextFp);

          let bmChanged = false;
          if (!isNaN(wVal) && wVal >= 20 && wVal <= 400) {
            const iso = new Date().toISOString().slice(0, 10);
            const prevWaist = latest && latest.d === iso && latest.waist ? latest.waist : null;
            const entry = { d: iso, w: +wVal.toFixed(1) };
            if (prevWaist) entry.waist = prevWaist;
            const idx = bm.logs.findIndex(x => x.d === iso);
            if (idx >= 0) bm.logs[idx] = entry;
            else bm.logs.push(entry);
            if (bm.logs.length > 60) bm.logs = bm.logs.slice(-60);
            bmChanged = true;
          }
          const nextTarget = (!isNaN(twVal) && twVal >= 20 && twVal <= 400) ? +twVal.toFixed(1) : null;
          if (nextTarget !== bm.target) {
            bm.target = nextTarget;
            bmChanged = true;
          }
          if (bmChanged) saveBodyMetrics(bm);
          if (localStorage.userToken && !isLocalToken(localStorage.userToken)) {
            pushCloudSync().catch(() => false);
          }
          vib(30);
          bd.remove();
          render();
          showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Параметры профиля сохранены' : 'Profile parameters saved');
        };
      };

      const fpProgChange = document.getElementById('fp-prog-change');
      if (fpProgChange) fpProgChange.onclick = () => {
        vib(20);
        const ps = getProgState();
        const bd = document.createElement('div');
        bd.className = 'ap-modal-backdrop';
        bd.innerHTML = `
          <div class="ap-modal">
            <h3>${L == 'ru' ? 'Выбор активной программы' : 'Choose Active Program'}</h3>
            <div class="fp-picker-list">
              ${D.programs.map(p => {
                const isAct = String(ps.activeId) === String(p.id);
                const done = Array.isArray(ps.logs[p.id]) ? ps.logs[p.id].length : 0;
                return `
                  <button type="button" class="fp-picker-item ${isAct ? 'on' : ''}" data-pick-pid="${p.id}">
                    <span>
                      <strong>${esc(pName(p))}</strong>
                      <small>${p.days} ${t('days')} · ${tempLbl(p.temp)}${done ? ` · ${L == 'ru' ? 'пройдено' : 'done'} ${done}` : ''}</small>
                    </span>
                    <span class="tag ${isAct ? 'pro' : ''}">${isAct ? '✓' : '→'}</span>
                  </button>`;
              }).join('')}
            </div>
            <div class="ap-modal-actions">
              <button type="button" class="btn alt" id="fp-pick-close">${L == 'ru' ? 'Закрыть' : 'Close'}</button>
            </div>
          </div>`;
        document.body.appendChild(bd);
        bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
        bd.querySelector('#fp-pick-close').onclick = () => bd.remove();
        bd.querySelectorAll('[data-pick-pid]').forEach(btn => {
          btn.onclick = () => {
            const nextPs = getProgState();
            nextPs.activeId = btn.dataset.pickPid;
            saveProgState(nextPs);
            if (localStorage.userToken && !isLocalToken(localStorage.userToken)) {
              pushCloudSync().catch(() => false);
            }
            vib(25);
            bd.remove();
            render();
          };
        });
      };

      const fpProgClear = document.getElementById('fp-prog-clear');
      if (fpProgClear) fpProgClear.onclick = () => {
        vib(20);
        const ps = getProgState();
        ps.activeId = null;
        saveProgState(ps);
        if (localStorage.userToken && !isLocalToken(localStorage.userToken)) {
          pushCloudSync().catch(() => false);
        }
        render();
      };
      const bkExport = document.getElementById('bk-export');
      if (bkExport) bkExport.onclick = () => {
        vib(25);
        exportBackupJson();
        showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Резервная копия сохранена' : 'Backup file downloaded');
      };
      const bkImportBtn = document.getElementById('bk-import-btn');
      const bkImportFile = document.getElementById('bk-import-file');
      if (bkImportBtn && bkImportFile) {
        bkImportBtn.onclick = () => bkImportFile.click();
        bkImportFile.onchange = ev => {
          const f = ev.target.files && ev.target.files[0];
          if (f) importBackupJsonFile(f);
        };
      }
      const offlineBtn = document.getElementById('pwa-offline-btn');
      if (offlineBtn) offlineBtn.onclick = () => performOfflineCache(offlineBtn);
      const cloudAuthBtn = document.getElementById('cloud-auth-btn');
      if (cloudAuthBtn) cloudAuthBtn.onclick = () => openCloudAuthModal();
      const cloudAcctBtn = document.getElementById('cloud-acct-btn');
      if (cloudAcctBtn) cloudAcctBtn.onclick = () => openCloudAcctModal();
      const cloudProBtn = document.getElementById('cloud-pro-btn');
      if (cloudProBtn) cloudProBtn.onclick = () => openCloudProModal();
      const cloudSyncBtn = document.getElementById('cloud-sync-btn');
      if (cloudSyncBtn) cloudSyncBtn.onclick = async () => {
        vib(20);
        cloudSyncBtn.disabled = true;
        const tok = localStorage.userToken;
        const okPush = await pushCloudSync();
        if (okPush) showAppToast(CFG.brand || 'RizzaFit', isLocalToken(tok)
          ? (L == 'ru' ? 'Профиль сохранён на устройстве' : 'Profile saved on device')
          : (L == 'ru' ? 'Данные сохранены в базе сервера' : 'Synced to server DB'));
        render();
      };
      const cloudLogoutBtn = document.getElementById('cloud-logout-btn');
      if (cloudLogoutBtn) cloudLogoutBtn.onclick = () => performCloudLogout();
      const pwaBtn = document.getElementById('pwa-install-btn');
      if (pwaBtn) pwaBtn.onclick = async () => {
        if (!deferredInstallPrompt) return;
        vib(25);
        deferredInstallPrompt.prompt();
        try { await deferredInstallPrompt.userChoice; } catch (e) {}
        deferredInstallPrompt = null;
        render();
      };
    }
    if (name == 'friends') {
      const frGuestBtn = document.getElementById('fr-guest-login');
      if (frGuestBtn) frGuestBtn.onclick = () => openCloudAuthModal('login');
      const AP = window.AthleteProfile;
      syncCommunityUsers().then(users => {
        if (users && users.length) {
          const prev = sessionStorage.getItem('lastCommCount');
          if (prev !== String(users.length)) {
            sessionStorage.setItem('lastCommCount', String(users.length));
            render();
          }
        }
      });
      let fTab = 'all';
      const applyFilter = () => {
        const q = (document.getElementById('fr-q')?.value || '').trim().toLowerCase();
        const box = document.getElementById('fr-list');
        if (!box) return;
        const cards = [...box.querySelectorAll('.fr-card')];
        if (fTab === 'top') {
          cards.sort((a, b) => (+b.dataset.xp || 0) - (+a.dataset.xp || 0)).forEach(c => box.appendChild(c));
        }
        cards.forEach(c => {
          const matchQ = !q || (c.dataset.name || '').includes(q);
          const matchTab = fTab !== 'online' || c.dataset.online === '1';
          c.style.display = (matchQ && matchTab) ? '' : 'none';
        });
      };
      const qInp = document.getElementById('fr-q');
      if (qInp) qInp.oninput = applyFilter;
      app.querySelectorAll('#fr-tabs .mpill').forEach(b => {
        b.onclick = () => {
          vib(20);
          app.querySelectorAll('#fr-tabs .mpill').forEach(x => x.classList.remove('on'));
          b.classList.add('on');
          fTab = b.dataset.ft;
          applyFilter();
        };
      });
      const openQuestModal = preFriendId => {
        if (!AP) return;
        const friends = AP.getFriends(CFG.athlete);
        if (!friends.length) return alert(L == 'ru' ? 'Сначала добавьте друга!' : 'Add a friend first!');
        const bd = document.createElement('div');
        bd.className = 'ap-modal-backdrop';
        bd.innerHTML = `<div class="ap-modal">
          <h3 style="display:flex;align-items:center;gap:7px;">${uiSvg('handshake', 18)} ${L == 'ru' ? 'Совместный квест (7 дней)' : '7-Day Co-op Quest'}</h3>
          <label>${L == 'ru' ? 'Напарник' : 'Partner'}
            <select id="nq-friend" style="width:100%;margin-top:4px;background:var(--card-inset);border:1px solid var(--line);border-radius:12px;padding:10px 12px;color:var(--tx);font:inherit;">
              ${friends.map(f => `<option value="${esc(f.id)}" ${String(f.id) === String(preFriendId) ? 'selected' : ''}>${esc(f.name)} (${esc(f.handle)})</option>`).join('')}
            </select>
          </label>
          <label>${L == 'ru' ? 'Общая цель' : 'Shared Goal'}
            <select id="nq-type" style="width:100%;margin-top:4px;background:var(--card-inset);border:1px solid var(--line);border-radius:12px;padding:10px 12px;color:var(--tx);font:inherit;">
              ${AP.QUEST_TEMPLATES.map(tpl => `<option value="${tpl.type}">${esc(L == 'ru' ? tpl.titleRu : tpl.titleEn)}</option>`).join('')}
            </select>
          </label>
          <div style="display:flex;gap:8px;margin-top:14px;">
            <button type="button" class="btn" style="flex:1" id="nq-go">${uiSvg('handshake', 14)} ${L == 'ru' ? 'Запустить квест' : 'Start quest'}</button>
            <button type="button" class="btn alt" id="nq-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
          </div>
        </div>`;
        document.body.appendChild(bd);
        bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
        bd.querySelector('#nq-cancel').onclick = () => bd.remove();
        bd.querySelector('#nq-go').onclick = () => {
          const fid = bd.querySelector('#nq-friend').value;
          const ttype = bd.querySelector('#nq-type').value;
          const fr = friends.find(x => String(x.id) === String(fid)) || friends[0];
          const rw = Number((CFG.athlete || {}).questReward) || 0;
          AP.startQuest(fr, ttype, rw);
          bd.remove();
          vib([35, 30, 50]);
          render();
        };
      };
      const qNewBtn = document.getElementById('quest-new-btn');
      if (qNewBtn) qNewBtn.onclick = () => openQuestModal();
      app.querySelectorAll('[data-quest-friend]').forEach(btn => {
        btn.onclick = () => openQuestModal(btn.dataset.questFriend);
      });
      const qClaimBtn = document.getElementById('quest-claim');
      if (qClaimBtn) qClaimBtn.onclick = () => {
        if (!AP) return;
        const res = AP.claimQuest(hist());
        if (res) {
          vib([60, 40, 90]);
          alert(L == 'ru' ? `🎉 Совместный квест выполнен! Награда +${res.reward} XP зачислена!` : `🎉 Co-op quest complete! +${res.reward} XP claimed!`);
          render();
        }
      };
      const qDelBtn = document.getElementById('quest-del');
      if (qDelBtn) qDelBtn.onclick = () => {
        if (!AP) return;
        AP.saveQuest(null);
        vib(20);
        render();
      };
      app.querySelectorAll('.fr-card[data-fid]').forEach(card => {
        card.onclick = ev => {
          if (ev.target.closest('button, a')) return;
          if (!AP) return;
          const f = AP.getFriends(CFG.athlete).find(x => String(x.id) === String(card.dataset.fid));
          if (!f) return;
          vib(20);
          const seed = String(f.id || f.name).split('').reduce((s, c) => s + c.charCodeAt(0), 0);
          const namedW = D.workouts.filter(w => w.t && (w.t.ru || w.t.en) && w.s && w.s.length);
          const favW = namedW.length ? namedW[(seed * 7) % namedW.length] : null;
          const imgEx = D.exercises.filter(e => e.img && (e.n.ru || e.n.en));
          const prs = [0, 1, 2].map(k => {
            const ex = imgEx.length ? imgEx[(seed * 13 + k * 29) % imgEx.length] : null;
            const reps = 18 + ((seed + k * 11 + (Number(f.level) || 5) * 3) % 42);
            return ex ? { id: ex.id, name: exName(ex), reps } : null;
          }).filter(Boolean);
          const activeD = AP.getDuels().find(d => !d.claimed && String(d.friendId) === String(f.id));
          const bd = document.createElement('div');
          bd.className = 'ap-modal-backdrop';
          bd.innerHTML = `<div class="ap-modal fm-modal">
            <div style="display:flex;justify-content:flex-end;">
              <button type="button" class="fr-btn-del" id="fm-close">✕</button>
            </div>
            <div class="ap-hero" style="margin-top:-12px;">
              <div class="ap-avatar-ring" style="width:74px;height:74px;border-color:${f.online ? 'var(--green)' : 'var(--ac)'};">
                <div class="ap-avatar-inner">${AP.miniAvatar(f.color, f.shirt, f.avatar)}</div>
              </div>
              <h2 class="ap-name" style="font-size:19px;">${esc(f.name)}</h2>
              <div class="ap-handle">${esc(f.handle)} · <span style="color:${f.online ? 'var(--green)' : 'var(--mut)'}">${f.online ? (L == 'ru' ? 'онлайн' : 'online') : (L == 'ru' ? 'не в сети' : 'offline')}</span></div>
            </div>
            <div class="ap-stats-bar" style="margin-bottom:14px;">
              <div class="ap-stat-col"><div class="ap-stat-top"><b>Lv.${f.level || 1}</b></div><small>${L == 'ru' ? 'Уровень' : 'Level'}</small></div>
              <div class="ap-stat-col"><div class="ap-stat-top"><b>${uiSvg('flame', 14)} ${f.streak || 0}</b></div><small>${L == 'ru' ? 'Серия' : 'Streak'}</small></div>
              <div class="ap-stat-col"><div class="ap-stat-top"><b>${Number(f.points || 0).toLocaleString()}</b></div><small>XP</small></div>
            </div>
            ${prs.length ? `
              <div class="fm-sec-lbl">${uiSvg('trophy', 13)} ${L == 'ru' ? 'Рекорды друга' : "Friend's PRs"}</div>
              <div class="fm-pr-list">
                ${prs.map(p => `<a href="#/exercise/${p.id}" class="fm-pr-row"><span>${esc(p.name)}</span><b>${p.reps} ${t('rep')}</b></a>`).join('')}
              </div>` : ''}
            ${favW ? `
              <div class="fm-sec-lbl">${uiSvg('dumbbell', 13)} ${L == 'ru' ? 'Любимая тренировка' : 'Favorite Workout'}</div>
              <div class="fm-wo-box">
                <div style="min-width:0;">
                  <div style="font-size:13.5px;font-weight:800;color:var(--tx);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(woName(favW))}</div>
                  <div style="font-size:11px;color:var(--mut);">${diffLbl(favW.diff)} · ${favW.eq ? eqLbl(favW.eq) : ''}</div>
                </div>
                <a href="#/workout/${favW.id}" class="btn" id="fm-repeat" style="padding:7px 12px;font-size:12px;white-space:nowrap;">▶ ${L == 'ru' ? 'Повторить' : 'Repeat'}</a>
              </div>` : ''}
            <div style="display:flex;gap:8px;margin-top:14px;">
              <button type="button" class="btn" style="flex:1;padding:10px 12px;font-size:13px;" id="fm-duel">${uiSvg('swords', 14)} ${activeD ? (L == 'ru' ? 'Дуэль уже идёт' : 'Duel active') : (L == 'ru' ? 'Дуэль 7д' : '7d Duel')}</button>
              <button type="button" class="btn alt" style="flex:1;padding:10px 12px;font-size:13px;" id="fm-quest">${uiSvg('handshake', 14)} ${L == 'ru' ? 'Квест' : 'Quest'}</button>
            </div>
          </div>`;
          document.body.appendChild(bd);
          bd.onclick = e => { if (e.target === bd) bd.remove(); };
          bd.querySelector('#fm-close').onclick = () => bd.remove();
          const rep = bd.querySelector('#fm-repeat');
          if (rep) rep.onclick = () => bd.remove();
          bd.querySelector('#fm-duel').onclick = () => {
            if (!activeD) AP.startDuel(f);
            bd.remove();
            vib([35, 30, 50]);
            render();
          };
          bd.querySelector('#fm-quest').onclick = () => {
            bd.remove();
            openQuestModal(f.id);
          };
        };
      });
      app.querySelectorAll('[data-duel-start]').forEach(btn => {
        btn.onclick = () => {
          if (!AP) return;
          const f = AP.getFriends(CFG.athlete).find(x => String(x.id) === String(btn.dataset.duelStart));
          if (!f) return;
          AP.startDuel(f);
          vib([35, 30, 50]);
          render();
        };
      });
      app.querySelectorAll('[data-duel-claim]').forEach(btn => {
        btn.onclick = () => {
          if (!AP) return;
          const id = btn.dataset.duelClaim;
          const d = AP.getDuels().find(x => x.id === id);
          const rewardXp = Number((CFG.athlete || {}).duelReward) || 500;
          const res = AP.claimDuel(id, hist(), rewardXp);
          if (res && !res.won && d) {
            AP.startDuel({
              id: d.friendId,
              name: d.friendName,
              handle: d.friendHandle,
              level: d.friendLevel,
              streak: d.friendStreak,
              color: d.friendColor,
              shirt: d.friendShirt,
              avatar: d.friendAvatar
            });
          } else if (res && res.won) {
            alert(L == 'ru' ? `🏆 Победа в дуэли! Вы получили +${res.reward} XP!` : `🏆 Duel victory! You earned +${res.reward} XP!`);
          }
          vib([60, 40, 80]);
          render();
        };
      });
      app.querySelectorAll('[data-duel-del]').forEach(btn => {
        btn.onclick = () => {
          if (!AP) return;
          const id = btn.dataset.duelDel;
          AP.saveDuels(AP.getDuels().filter(d => d.id !== id));
          vib(20);
          render();
        };
      });
      const rulesBtn = document.getElementById('duel-rules');
      if (rulesBtn) rulesBtn.onclick = () => {
        const rw = Number((CFG.athlete || {}).duelReward) || 500;
        alert(L == 'ru'
          ? `⚔️ Правила дуэли на 7 дней:\n\n• +100 XP за каждую завершённую тренировку\n• +15 XP за каждую минуту активности\n• +60 XP за новый личный рекорд (PR)\n• Победитель через 7 дней получает +${rw} XP в профиль!`
          : `⚔️ 7-Day Duel Rules:\n\n• +100 XP per completed workout\n• +15 XP per active minute\n• +60 XP per new Personal Record (PR)\n• Winner after 7 days earns +${rw} XP!`);
      };
      // Server sync for friends and incoming/outgoing requests
      if (isLoggedIn()) {
        socialApi('/api/friends').then(res => {
          if (res && res.friends && AP && AP.syncServerFriends) {
            const prevFriendsJson = localStorage.getItem('athleteFriends');
            AP.syncServerFriends(res.friends);
            const nextFriendsJson = localStorage.getItem('athleteFriends');
            if (prevFriendsJson !== nextFriendsJson) {
              render();
              return;
            }
          }
          const incBadge = document.getElementById('fr-badge-inc');
          const outBadge = document.getElementById('fr-badge-out');
          if (incBadge && res.incoming && res.incoming.length) {
            incBadge.textContent = String(res.incoming.length);
            incBadge.style.display = 'inline-block';
          }
          if (outBadge && res.outgoing && res.outgoing.length) {
            outBadge.textContent = String(res.outgoing.length);
            outBadge.style.display = 'inline-block';
          }

          const tabsBar = document.getElementById('fr-tabs-bar');
          const reqPanel = document.getElementById('fr-requests-panel');
          const friendsContent = document.getElementById('fr-friends-content');
          if (tabsBar && reqPanel && friendsContent) {
            tabsBar.querySelectorAll('[data-fr-main-tab]').forEach(btn => {
              btn.onclick = () => {
                tabsBar.querySelectorAll('[data-fr-main-tab]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const mode = btn.dataset.frMainTab;
                if (mode === 'friends') {
                  reqPanel.style.display = 'none';
                  friendsContent.style.display = '';
                } else if (mode === 'incoming') {
                  friendsContent.style.display = 'none';
                  reqPanel.style.display = 'block';
                  const inc = res.incoming || [];
                  if (!inc.length) {
                    reqPanel.innerHTML = `<div class="empty">${L == 'ru' ? 'Нет входящих заявок' : 'No incoming requests'}</div>`;
                  } else {
                    reqPanel.innerHTML = `
                      <div class="user-grid">
                        ${inc.map(r => {
                          const ru = r.user || r;
                          const reqId = r.requestId || r.id;
                          return `
                          <div class="user-card">
                            <div class="user-card-head" data-go-user="${esc(ru.username)}">
                              <div class="user-avatar-wrap">
                                ${ru.avatar ? `<img src="${esc(ru.avatar)}" alt="">` : (ru.displayName || ru.username).charAt(0).toUpperCase()}
                              </div>
                              <div class="user-card-meta">
                                <div class="user-card-name">${esc(ru.displayName || ru.username)}</div>
                                <div class="user-card-handle">@${esc(ru.username)}</div>
                              </div>
                            </div>
                            <div class="user-card-actions">
                              <button type="button" class="btn" data-req-acc="${esc(String(reqId))}">${t('acceptRequest')}</button>
                              <button type="button" class="btn alt" data-req-dec="${esc(String(reqId))}">${t('declineRequest')}</button>
                            </div>
                          </div>`;
                        }).join('')}
                      </div>`;
                    reqPanel.querySelectorAll('[data-go-user]').forEach(el => {
                      el.onclick = () => { location.hash = '#/user/' + encodeURIComponent(el.dataset.goUser); };
                    });
                    reqPanel.querySelectorAll('[data-req-acc]').forEach(b => {
                      b.onclick = async () => {
                        b.disabled = true;
                        try {
                          await socialApi('/api/friends/accept', { method: 'POST', body: { requestId: Number(b.dataset.reqAcc) } });
                          render();
                        } catch (e) { alert(e.message); b.disabled = false; }
                      };
                    });
                    reqPanel.querySelectorAll('[data-req-dec]').forEach(b => {
                      b.onclick = async () => {
                        b.disabled = true;
                        try {
                          await socialApi('/api/friends/decline', { method: 'POST', body: { requestId: Number(b.dataset.reqDec) } });
                          render();
                        } catch (e) { alert(e.message); b.disabled = false; }
                      };
                    });
                  }
                } else if (mode === 'outgoing') {
                  friendsContent.style.display = 'none';
                  reqPanel.style.display = 'block';
                  const outg = res.outgoing || [];
                  if (!outg.length) {
                    reqPanel.innerHTML = `<div class="empty">${L == 'ru' ? 'Нет исходящих заявок' : 'No outgoing requests'}</div>`;
                  } else {
                    reqPanel.innerHTML = `
                      <div class="user-grid">
                        ${outg.map(r => {
                          const ru = r.user || r;
                          const reqId = r.requestId || r.id;
                          return `
                          <div class="user-card">
                            <div class="user-card-head" data-go-user="${esc(ru.username)}">
                              <div class="user-avatar-wrap">
                                ${ru.avatar ? `<img src="${esc(ru.avatar)}" alt="">` : (ru.displayName || ru.username).charAt(0).toUpperCase()}
                              </div>
                              <div class="user-card-meta">
                                <div class="user-card-name">${esc(ru.displayName || ru.username)}</div>
                                <div class="user-card-handle">@${esc(ru.username)}</div>
                              </div>
                            </div>
                            <div class="user-card-actions">
                              <button type="button" class="btn alt" data-req-cancel="${esc(String(reqId))}">${t('cancelRequest')}</button>
                            </div>
                          </div>`;
                        }).join('')}
                      </div>`;
                    reqPanel.querySelectorAll('[data-go-user]').forEach(el => {
                      el.onclick = () => { location.hash = '#/user/' + encodeURIComponent(el.dataset.goUser); };
                    });
                    reqPanel.querySelectorAll('[data-req-cancel]').forEach(b => {
                      b.onclick = async () => {
                        b.disabled = true;
                        try {
                          await socialApi('/api/friends/cancel', { method: 'POST', body: { requestId: Number(b.dataset.reqCancel) } });
                          render();
                        } catch (e) { alert(e.message); b.disabled = false; }
                      };
                    });
                  }
                }
              };
            });
          }
        }).catch(() => {});
      }

      app.querySelectorAll('[data-del]').forEach(btn => {
        btn.onclick = async () => {
          if (!confirm(L == 'ru' ? 'Удалить из друзей?' : 'Remove friend?')) return;
          const id = btn.dataset.del;
          try {
            await socialApi('/api/friends/remove', { method: 'POST', body: { userId: id } });
          } catch (e) {}
          if (AP) {
            const next = AP.getFriends(CFG.athlete).filter(f => String(f.id) !== String(id));
            AP.saveFriends(next);
          }
          vib(25);
          render();
        };
      });
      app.querySelectorAll('[data-add-sug]').forEach(btn => {
        btn.onclick = () => {
          if (!AP) return;
          const s = (AP.SUGGESTED_FRIENDS || []).find(x => x.id === btn.dataset.addSug);
          if (!s || (AP.isFakeUser && AP.isFakeUser(s))) return;
          const cur = AP.getFriends(CFG.athlete);
          if (!cur.some(f => (f.handle || '').toLowerCase() === (s.handle || '').toLowerCase())) {
            cur.unshift(Object.assign({}, s));
            AP.saveFriends(cur);
          }
          vib(35);
          render();
        };
      });
      const invBtn = document.getElementById('fr-copy-inv');
      if (invBtn) invBtn.onclick = () => {
        const url = location.origin + '/#/friends';
        if (navigator.clipboard) navigator.clipboard.writeText(url).catch(() => {});
        invBtn.textContent = '✓ ' + (L == 'ru' ? 'Скопировано' : 'Copied');
        setTimeout(() => { invBtn.textContent = (L == 'ru' ? 'Пригласить' : 'Invite'); }, 1800);
      };
      const addOpen = document.getElementById('fr-add-open');
      if (addOpen) addOpen.onclick = () => {
        const bd = document.createElement('div');
        bd.className = 'ap-modal-backdrop';
        bd.innerHTML = `<div class="ap-modal">
          <h3 style="display:flex;align-items:center;gap:7px;">${uiSvg('users', 18)} ${L == 'ru' ? 'Добавить друга' : 'Add friend'}</h3>
          <label>${L == 'ru' ? 'Имя' : 'Name'}<input id="nf-name" placeholder="${L == 'ru' ? 'Например: Олег Смирнов' : 'e.g. Alex Smith'}"></label>
          <label>@username<input id="nf-handle" placeholder="@oleg_fit"></label>
          <div class="g2" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <label>${L == 'ru' ? 'Уровень' : 'Level'}<input id="nf-lvl" type="number" min="1" value="5"></label>
            <label>${L == 'ru' ? 'Серия (дней)' : 'Streak'}<input id="nf-str" type="number" min="0" value="12"></label>
          </div>
          <div style="display:flex;gap:8px;margin-top:12px;">
            <button type="button" class="btn" style="flex:1" id="nf-save">${L == 'ru' ? 'Добавить' : 'Add'}</button>
            <button type="button" class="btn alt" id="nf-cancel">${L == 'ru' ? 'Отмена' : 'Cancel'}</button>
          </div>
        </div>`;
        document.body.appendChild(bd);
        bd.onclick = ev => { if (ev.target === bd) bd.remove(); };
        bd.querySelector('#nf-cancel').onclick = () => bd.remove();
        bd.querySelector('#nf-save').onclick = () => {
          if (!AP) return;
          const nm = bd.querySelector('#nf-name').value.trim();
          let hnd = bd.querySelector('#nf-handle').value.trim();
          if (!nm) return;
          if (!hnd) hnd = '@' + nm.toLowerCase().replace(/[^a-zа-я0-9]+/gi, '_').replace(/^_|_$/g, '');
          if (!hnd.startsWith('@')) hnd = '@' + hnd;
          const lvl = Math.max(1, +bd.querySelector('#nf-lvl').value || 5);
          const str = Math.max(0, +bd.querySelector('#nf-str').value || 12);
          const cur = AP.getFriends(CFG.athlete);
          cur.unshift({
            id: 'u_' + Date.now(),
            name: nm,
            handle: hnd,
            level: lvl,
            streak: str,
            points: lvl * 2200 + str * 120,
            online: true,
            color: '#32422e',
            shirt: '#7aa85b'
          });
          AP.saveFriends(cur);
          bd.remove();
          vib(35);
          render();
        };
      };
    }

    if (name === 'users' && isLoggedIn()) {
      const searchInput = document.getElementById('users-search-input');
      const grid = document.getElementById('users-grid');
      const moreWrap = document.getElementById('users-more-wrap');
      let offset = 0;
      const limit = 24;
      let currentQuery = '';
      let searchDebounce = null;

      async function fetchUsers(append = false) {
        if (!grid) return;
        if (!append) {
          offset = 0;
          grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--tx-sub);">${L == 'ru' ? 'Поиск…' : 'Searching…'}</div>`;
        }
        try {
          const res = await socialApi(`/api/users?q=${encodeURIComponent(currentQuery)}&limit=${limit}&offset=${offset}`);
          const users = res.users || [];
          if (!append) grid.innerHTML = '';
          if (!users.length && !append) {
            grid.innerHTML = `<div class="empty" style="grid-column:1/-1;">${t('noUsersFound')}</div>`;
            if (moreWrap) moreWrap.innerHTML = '';
            return;
          }
          users.forEach(u => {
            const card = document.createElement('div');
            card.className = 'user-card';
            let actionBtn = '';
            if (u.friendshipStatus === 'friends') {
              actionBtn = `<span class="user-status-pill friend">${t('inFriends')}</span>`;
            } else if (u.friendshipStatus === 'outgoing') {
              actionBtn = `<button type="button" class="btn alt" data-u-cancel="${u.id}">${t('cancelRequest')}</button>`;
            } else if (u.friendshipStatus === 'incoming') {
              actionBtn = `<button type="button" class="btn" data-u-acc="${u.id}">${t('acceptRequest')}</button>`;
            } else {
              actionBtn = `<button type="button" class="btn alt" data-u-req="${u.id}">+ ${t('sendRequest')}</button>`;
            }
            card.innerHTML = `
              <div class="user-card-head" data-go-user="${esc(u.username)}">
                <div class="user-avatar-wrap">
                  ${u.avatar ? `<img src="${esc(u.avatar)}" alt="">` : (u.displayName || u.username).charAt(0).toUpperCase()}
                </div>
                <div class="user-card-meta">
                  <div class="user-card-name">${esc(u.displayName || u.username)}</div>
                  <div class="user-card-handle">@${esc(u.username)}</div>
                </div>
              </div>
              <div class="user-card-stats">
                <span>Lv.<b>${u.level || 1}</b></span>
                <span><b>${(u.points || 0).toLocaleString()}</b> XP</span>
                <span>🔥 <b>${u.streak || 0}</b> ${t('days')}</span>
              </div>
              <div class="user-card-actions">
                ${actionBtn}
                <button type="button" class="btn" data-u-msg="${u.id}" title="${t('sendMessage')}">💬</button>
              </div>`;
            grid.appendChild(card);
          });

          grid.querySelectorAll('[data-go-user]').forEach(el => {
            el.onclick = () => { location.hash = '#/user/' + el.dataset.goUser; };
          });
          grid.querySelectorAll('[data-u-req]').forEach(b => {
            b.onclick = async () => {
              b.disabled = true;
              try {
                await socialApi('/api/friends/request', { method: 'POST', body: { targetUserId: b.dataset.uReq } });
                b.outerHTML = `<span class="user-status-pill">${t('requestSent')}</span>`;
              } catch (e) { alert(e.message); b.disabled = false; }
            };
          });
          grid.querySelectorAll('[data-u-cancel]').forEach(b => {
            b.onclick = async () => {
              b.disabled = true;
              try {
                await socialApi('/api/friends/cancel', { method: 'POST', body: { targetUserId: b.dataset.uCancel } });
                b.outerHTML = `<span class="user-status-pill">${L == 'ru' ? 'Отменена' : 'Cancelled'}</span>`;
              } catch (e) { alert(e.message); b.disabled = false; }
            };
          });
          grid.querySelectorAll('[data-u-acc]').forEach(b => {
            b.onclick = async () => {
              b.disabled = true;
              try {
                await socialApi('/api/friends/accept', { method: 'POST', body: { targetUserId: b.dataset.uAcc } });
                b.outerHTML = `<span class="user-status-pill friend">${t('inFriends')}</span>`;
              } catch (e) { alert(e.message); b.disabled = false; }
            };
          });
          grid.querySelectorAll('[data-u-msg]').forEach(b => {
            b.onclick = async () => {
              b.disabled = true;
              try {
                const openRes = await socialApi('/api/messages/open', { method: 'POST', body: { targetUserId: b.dataset.uMsg } });
                if (openRes && openRes.conversation) {
                  location.hash = '#/messages/' + openRes.conversation.id;
                }
              } catch (e) { alert(e.message); b.disabled = false; }
            };
          });

          if (moreWrap) {
            if (res.hasMore) {
              moreWrap.innerHTML = `<button type="button" class="btn alt" id="users-load-more">${t('loadMore')}</button>`;
              const lmBtn = document.getElementById('users-load-more');
              if (lmBtn) {
                lmBtn.onclick = () => {
                  offset += limit;
                  fetchUsers(true);
                };
              }
            } else {
              moreWrap.innerHTML = '';
            }
          }
        } catch (e) {
          if (!append) grid.innerHTML = `<div class="empty" style="grid-column:1/-1;">${esc(e.message)}</div>`;
        }
      }

      if (searchInput) {
        searchInput.oninput = () => {
          clearTimeout(searchDebounce);
          searchDebounce = setTimeout(() => {
            currentQuery = searchInput.value.trim();
            fetchUsers(false);
          }, 300);
        };
      }
      fetchUsers(false);
    }

    if (name === 'user' && isLoggedIn()) {
      const wrap = document.getElementById('pub-profile-wrap');
      if (!wrap || !arg) return;
      socialApi('/api/users/profile?username=' + encodeURIComponent(arg)).then(res => {
        const u = res.user;
        const myName = (localStorage.userName || '').toLowerCase();
        const isMe = (u.username || '').toLowerCase() === myName;
        let frBtn = '';
        if (isMe) {
          frBtn = `<a href="#/profile" class="btn">${t('history')}</a>`;
        } else if (u.friendshipStatus === 'friends') {
          frBtn = `<button type="button" class="btn alt" id="pub-fr-remove" style="color:#ef4444;">${t('removeFriend')}</button>`;
        } else if (u.friendshipStatus === 'outgoing') {
          frBtn = `<button type="button" class="btn alt" id="pub-fr-cancel">${t('cancelRequest')}</button>`;
        } else if (u.friendshipStatus === 'incoming') {
          frBtn = `<button type="button" class="btn" id="pub-fr-accept">${t('acceptRequest')}</button> <button type="button" class="btn alt" id="pub-fr-decline">${t('declineRequest')}</button>`;
        } else {
          frBtn = `<button type="button" class="btn" id="pub-fr-add">+ ${t('sendRequest')}</button>`;
        }

        const prEntries = Object.entries(u.prs || {});
        let prsHtml = '';
        if (prEntries.length) {
          prsHtml = `
            <div class="pub-prs-card">
              <div style="font-size:14px;font-weight:700;color:var(--tx);margin-bottom:8px;">🏆 ${t('personalRecords')}</div>
              <div class="pub-prs-grid">
                ${prEntries.map(([exId, val]) => {
                  const ex = exMap[exId];
                  const exN = ex ? exName(ex) : '#' + exId;
                  return `<div class="pub-pr-item"><div class="pub-pr-val">${val} ${t('rep')}</div><div class="pub-pr-title">${esc(exN)}</div></div>`;
                }).join('')}
              </div>
            </div>`;
        } else {
          prsHtml = `
            <div class="pub-prs-card" style="text-align:center;padding:20px;color:var(--tx-sub);font-size:12.5px;">
              🏆 ${t('noPrsYet')}
            </div>`;
        }

        wrap.innerHTML = `
          <div style="margin-bottom:12px;">
            <a href="#/users" class="btn alt" style="padding:6px 12px;font-size:12px;">← ${t('users')}</a>
          </div>
          <div class="pub-profile-header">
            <div class="pub-profile-av">
              ${u.avatar ? `<img src="${esc(u.avatar)}" alt="">` : (u.displayName || u.username).charAt(0).toUpperCase()}
            </div>
            <div class="pub-profile-name">${esc(u.displayName || u.username)}</div>
            <div class="pub-profile-handle">@${esc(u.username)}</div>
            <div class="pub-profile-stats">
              <div>
                <div class="pub-stat-val">${u.level || 1}</div>
                <div class="pub-stat-lbl">${t('lvl')}</div>
              </div>
              <div>
                <div class="pub-stat-val">${(u.points || 0).toLocaleString()}</div>
                <div class="pub-stat-lbl">XP</div>
              </div>
              <div>
                <div class="pub-stat-val">🔥 ${u.streak || 0}</div>
                <div class="pub-stat-lbl">${t('days')}</div>
              </div>
            </div>
            <div class="pub-actions">
              ${frBtn}
              ${!isMe ? `<button type="button" class="btn" id="pub-msg-btn">💬 ${t('sendMessage')}</button>` : ''}
              ${!isMe ? `<button type="button" class="btn alt" id="pub-block-btn" style="font-size:11px;">${res.isBlockedByMe ? t('unblockUser') : t('blockUser')}</button>` : ''}
              ${!isMe ? `<button type="button" class="btn alt" id="pub-report-btn" style="font-size:11px;">⚠️ ${t('reportUser')}</button>` : ''}
            </div>
          </div>
          ${prsHtml}
        `;

        const addB = document.getElementById('pub-fr-add');
        if (addB) addB.onclick = async () => {
          try { await socialApi('/api/friends/request', { method: 'POST', body: { targetUserId: u.id } }); render(); } catch (e) { alert(e.message); }
        };
        const cancelB = document.getElementById('pub-fr-cancel');
        if (cancelB) cancelB.onclick = async () => {
          try { await socialApi('/api/friends/cancel', { method: 'POST', body: { targetUserId: u.id } }); render(); } catch (e) { alert(e.message); }
        };
        const accB = document.getElementById('pub-fr-accept');
        if (accB) accB.onclick = async () => {
          try { await socialApi('/api/friends/accept', { method: 'POST', body: { targetUserId: u.id } }); render(); } catch (e) { alert(e.message); }
        };
        const decB = document.getElementById('pub-fr-decline');
        if (decB) decB.onclick = async () => {
          try { await socialApi('/api/friends/decline', { method: 'POST', body: { targetUserId: u.id } }); render(); } catch (e) { alert(e.message); }
        };
        const remB = document.getElementById('pub-fr-remove');
        if (remB) remB.onclick = async () => {
          if (!confirm(L == 'ru' ? 'Удалить из друзей?' : 'Remove friend?')) return;
          try { await socialApi('/api/friends/remove', { method: 'POST', body: { targetUserId: u.id } }); render(); } catch (e) { alert(e.message); }
        };
        const msgB = document.getElementById('pub-msg-btn');
        if (msgB) msgB.onclick = async () => {
          try {
            const convRes = await socialApi('/api/messages/open', { method: 'POST', body: { targetUserId: u.id } });
            if (convRes && convRes.conversation) {
              location.hash = '#/messages/' + convRes.conversation.id;
            }
          } catch (e) { alert(e.message); }
        };
        const blkB = document.getElementById('pub-block-btn');
        if (blkB) blkB.onclick = async () => {
          try {
            if (res.isBlockedByMe) {
              await socialApi('/api/users/unblock', { method: 'POST', body: { targetUserId: u.id } });
              showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Пользователь разблокирован' : 'User unblocked');
            } else {
              if (!confirm(L == 'ru' ? 'Заблокировать этого пользователя? Он не сможет писать вам и будет удалён из друзей.' : 'Block user?')) return;
              await socialApi('/api/users/block', { method: 'POST', body: { targetUserId: u.id } });
              showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Пользователь заблокирован' : 'User blocked');
            }
            render();
          } catch (e) { alert(e.message); }
        };
        const repB = document.getElementById('pub-report-btn');
        if (repB) repB.onclick = async () => {
          const reason = prompt(t('reportReasonPrompt'));
          if (reason && reason.trim()) {
            try {
              await socialApi('/api/users/report', { method: 'POST', body: { targetUserId: u.id, reason: reason.trim() } });
              showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Жалоба отправлена модераторам' : 'Report sent');
            } catch (e) { alert(e.message); }
          }
        };
      }).catch(err => {
        wrap.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
      });
    }

    if (name === 'messages' && isLoggedIn()) {
      if (window._chatPollTimer) {
        clearInterval(window._chatPollTimer);
        window._chatPollTimer = null;
      }
      const convListEl = document.getElementById('conv-list');
      const chatHeaderEl = document.getElementById('chat-header');
      const chatMessagesEl = document.getElementById('chat-messages');
      const chatInputBarEl = document.getElementById('chat-input-bar');
      const textarea = document.getElementById('chat-textarea');
      const sendBtn = document.getElementById('chat-send-btn');
      const activeConvId = arg ? Number(arg) : null;

      async function loadConversations() {
        if (!convListEl) return;
        try {
          const res = await socialApi('/api/messages/conversations');
          const convs = res.conversations || [];
          if (!convs.length) {
            convListEl.innerHTML = `<div style="text-align:center;padding:24px;color:var(--tx-sub);font-size:12px;">${t('noConversations')}</div>`;
            return;
          }
          convListEl.innerHTML = convs.map(c => {
            const p = c.peer || {};
            const pName = p.displayName || p.username || 'User';
            const isActive = activeConvId && activeConvId === c.id;
            let timeStr = '';
            if (c.lastMessageAt) {
              const d = new Date(c.lastMessageAt * 1000);
              const now = new Date();
              timeStr = (d.toDateString() === now.toDateString())
                ? d.toLocaleTimeString(L, { hour: '2-digit', minute: '2-digit' })
                : d.toLocaleDateString(L, { day: 'numeric', month: 'short' });
            }
            const previewText = c.lastMessageText || c.lastMessagePreview || '';
            return `
              <div class="conv-item ${isActive ? 'active' : ''}" data-conv-go="${c.id}">
                <div class="conv-av">
                  ${p.avatar ? `<img src="${esc(p.avatar)}" alt="">` : pName.charAt(0).toUpperCase()}
                </div>
                <div class="conv-body">
                  <div class="conv-top-line">
                    <span class="conv-name">${esc(pName)}</span>
                    <span class="conv-time">${esc(timeStr)}</span>
                  </div>
                  <div class="conv-bot-line">
                    <span class="conv-preview">${esc(previewText)}</span>
                    ${c.unreadCount > 0 ? `<span class="conv-badge">${c.unreadCount}</span>` : ''}
                  </div>
                </div>
              </div>`;
          }).join('');

          convListEl.querySelectorAll('[data-conv-go]').forEach(item => {
            item.onclick = () => { location.hash = '#/messages/' + item.dataset.convGo; };
          });
        } catch (e) {}
      }

      async function loadActiveChat(silent = false) {
        if (!activeConvId || !chatMessagesEl) return;
        try {
          const res = await socialApi('/api/messages/history?conversationId=' + encodeURIComponent(activeConvId));
          const conv = res.conversation || res;
          const peer = res.peer || conv.peer || {};
          const peerName = peer.displayName || peer.username || 'User';
          const isBlockedByMe = !!(res.isBlockedByMe || conv.isBlockedByMe);
          const hasBlockedMe = !!(res.hasBlockedMe || conv.hasBlockedMe || conv.isBlockedByPeer);
          const isBlocked = isBlockedByMe || hasBlockedMe;

          if (chatHeaderEl && !silent) {
            chatHeaderEl.innerHTML = `
              <div style="display:flex;align-items:center;gap:10px;min-width:0;">
                <a href="#/messages" class="btn alt chat-back-btn" id="chat-back-btn" style="padding:6px 9px;font-size:12px;line-height:1;">‹</a>
                <div class="chat-header-user" id="chat-header-user-link" style="cursor:pointer;">
                  <div class="conv-av" style="width:34px;height:34px;font-size:14px;">
                    ${peer.avatar ? `<img src="${esc(peer.avatar)}" alt="">` : peerName.charAt(0).toUpperCase()}
                  </div>
                  <div style="min-width:0;">
                    <div class="chat-header-name">${esc(peerName)}</div>
                    <div class="chat-header-handle">@${esc(peer.username || '')}</div>
                  </div>
                </div>
              </div>
              <div class="chat-header-actions">
                <button type="button" class="btn alt" id="chat-hide-btn" style="padding:5px 8px;font-size:11px;" title="${t('hideDialogConfirm')}">✕</button>
              </div>`;

            const userLink = document.getElementById('chat-header-user-link');
            if (userLink && peer.username) {
              userLink.onclick = () => { location.hash = '#/user/' + encodeURIComponent(peer.username); };
            }

            const hideB = document.getElementById('chat-hide-btn');
            if (hideB) hideB.onclick = async () => {
              if (!confirm(t('hideDialogConfirm'))) return;
              try {
                await socialApi('/api/messages/conversation/hide', { method: 'POST', body: { conversationId: activeConvId } });
                location.hash = '#/messages';
              } catch (e) { alert(e.message); }
            };
          }

          if (chatInputBarEl) {
            let noticeEl = document.getElementById('chat-blocked-notice');
            if (isBlocked) {
              chatInputBarEl.style.display = 'none';
              if (!noticeEl) {
                noticeEl = document.createElement('div');
                noticeEl.id = 'chat-blocked-notice';
                noticeEl.className = 'chat-blocked-notice';
                chatInputBarEl.parentNode.insertBefore(noticeEl, chatInputBarEl.nextSibling);
              }
              noticeEl.textContent = t('chatBlocked');
              noticeEl.style.display = '';
            } else {
              chatInputBarEl.style.display = '';
              if (noticeEl) noticeEl.style.display = 'none';
            }
          }

          const msgs = res.messages || [];
          if (!msgs.length) {
            chatMessagesEl.innerHTML = `<div style="text-align:center;padding:30px;color:var(--tx-sub);font-size:12.5px;">${t('noMessagesInChat')}</div>`;
          } else {
            let lastDay = '';
            let html = '';
            msgs.forEach(m => {
              const d = new Date(m.createdAt * 1000);
              const now = new Date();
              let dayStr = '';
              if (d.toDateString() === now.toDateString()) {
                dayStr = t('today');
              } else {
                dayStr = d.toLocaleDateString(L, { day: 'numeric', month: 'long' });
              }
              if (dayStr !== lastDay) {
                html += `<div class="chat-date-sep"><span>${esc(dayStr)}</span></div>`;
                lastDay = dayStr;
              }
              const isMine = typeof m.fromMe === 'boolean' ? m.fromMe : (conv.myUid !== undefined && m.senderId === conv.myUid);
              const timeFormatted = d.toLocaleTimeString(L, { hour: '2-digit', minute: '2-digit' });
              let tick = '';
              if (isMine) {
                const isRead = m.status === 'read' || !!m.readAt;
                tick = isRead ? '<span class="msg-status-tick" title="Read">✓✓</span>' : '<span class="msg-status-tick" title="Delivered">✓</span>';
              }
              const isDel = !!m.isDeleted;
              html += `
                <div class="msg-row ${isMine ? 'mine' : 'peer'}" id="msg-${m.id}">
                  <div class="msg-bubble ${isMine ? 'mine' : 'peer'} ${isDel ? 'deleted' : ''}">
                    ${isDel ? (L == 'ru' ? 'Сообщение удалено' : 'Message deleted') : esc(m.text)}
                    <div class="msg-meta">
                      <span>${timeFormatted}</span>
                      ${tick}
                      ${isMine && !isDel ? `<button type="button" class="msg-del-btn" data-del-msg="${m.id}" title="${t('deleteMessageConfirm')}">🗑️</button>` : ''}
                    </div>
                  </div>
                </div>`;
            });
            chatMessagesEl.innerHTML = html;

            chatMessagesEl.querySelectorAll('[data-del-msg]').forEach(b => {
              b.onclick = async () => {
                if (!confirm(t('deleteMessageConfirm'))) return;
                try {
                  await socialApi('/api/messages/delete', { method: 'POST', body: { messageId: Number(b.dataset.delMsg) } });
                  loadActiveChat(true);
                  loadConversations();
                } catch (e) { alert(e.message); }
              };
            });

            if (!silent) {
              chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
            }
          }

          socialApi('/api/messages/read', { method: 'POST', body: { conversationId: activeConvId } }).then(readRes => {
            if (readRes && readRes.readCount > 0) {
              lastUnreadCheck = 0;
              checkUnreadMessages();
              loadConversations();
            }
          }).catch(() => {});
        } catch (e) {
          if (!silent) chatMessagesEl.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
        }
      }

      async function sendMessage() {
        if (!textarea || !activeConvId) return;
        const text = textarea.value.trim();
        if (!text) return;
        if (text.length > 2000) {
          alert(L == 'ru' ? 'Сообщение слишком длинное (макс 2000 символов)' : 'Message too long (max 2000 chars)');
          return;
        }
        textarea.value = '';
        const clientMsgId = 'c_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        try {
          await socialApi('/api/messages/send', {
            method: 'POST',
            body: {
              conversationId: activeConvId,
              text,
              clientMsgId
            }
          });
          loadActiveChat(false);
          loadConversations();
        } catch (e) {
          textarea.value = text;
          alert(e.message);
        }
      }

      if (sendBtn) sendBtn.onclick = sendMessage;
      if (textarea) {
        textarea.onkeydown = e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
          }
        };
      }

      loadConversations();
      if (activeConvId) {
        loadActiveChat(false);
        window._chatPollTimer = setInterval(() => {
          if (document.visibilityState === 'visible' && (location.hash || '').startsWith('#/messages/' + activeConvId)) {
            loadActiveChat(true);
          }
        }, 3500);
      }
    }

    const loginB = document.getElementById('social-gate-login');
    if (loginB) loginB.onclick = () => openCloudAuthModal('login');
    const regB = document.getElementById('social-gate-reg');
    if (regB) regB.onclick = () => openCloudAuthModal('register');
    if (loginB || regB) {
      app.querySelectorAll('[data-soc-provider]').forEach(btn => {
        btn.onclick = () => handleSocialAuth(btn.dataset.socProvider);
      });
    }
  }

  // ---------- player ----------
  const P = document.getElementById('player');
  function play(w) {
    if (isProWorkout(w) && !isUserPro()) {
      vib(30);
      showAppToast(CFG.brand || 'RizzaFit', L == 'ru' ? 'Эта тренировка доступна только в подписке PRO' : 'This workout requires PRO subscription');
      openPaywallModal();
      return;
    }
    if (window.RizzaAnalytics) {
      window.RizzaAnalytics.trackWorkoutStart(w.id, woName(w));
    }
    unlockAudio();
    requestWakeLock();
    const getRestPreset = () => +(localStorage.restPreset || 0);
    const steps = [];
    w.s.forEach((s, si) => {
      for (let r = 0; r < s[0]; r++) s.slice(1).forEach((n, ni, arr) => {
        steps.push({ type: 'ex', n, label: `${t('set')} ${si + 1}${s[0] > 1 ? ' · ' + t('rounds') + ' ' + (r + 1) + '/' + s[0] : ''}` });
        const baseRest = n[3] || (ni < arr.length - 1 ? w.rb : 0);
        const rp = getRestPreset();
        const rest = baseRest ? (rp > 0 ? rp : baseRest) : 0;
        if (rest) steps.push({ type: 'rest', sec: rest, baseSec: baseRest, nextEx: null });
      });
      if (w.rr && si < w.s.length - 1) {
        const rp = getRestPreset();
        const rest = rp > 0 ? rp : w.rr;
        steps.push({ type: 'rest', sec: rest, baseSec: w.rr, nextEx: null });
      }
    });
    for (let k = 0; k < steps.length - 1; k++) {
      if (steps[k].type == 'rest' && steps[k + 1].type == 'ex') {
        steps[k].nextEx = steps[k + 1].n;
      }
    }
    let i = 0, timer = null, start = Date.now(), isPaused = false, afterRest = false;
    let sessionReps = 0, sessionEx = 0, sessionVolume = 0, sessionPrs = [];
    const sessionWeights = {};
    const stop = () => {
      releaseWakeLock();
      stopSpeech();
      clearInterval(timer);
      document.body.style.overflow = '';
      document.body.classList.remove('player-open');
      P.classList.add('hidden');
      P.innerHTML = '';
    };
    function show() {
      clearInterval(timer);
      document.body.style.overflow = 'hidden';
      document.body.classList.add('player-open');
      P.classList.remove('hidden');
      if (i >= steps.length) {
        releaseWakeLock();
        sfx('finish');
        vib([120, 80, 200, 80, 300]);
        speak(L == 'ru' ? 'Тренировка окончена! Отличная работа!' : 'Workout complete! Great job!');
        const totalSec = Math.round((Date.now() - start) / 1000);
        const finishTs = Date.now();
        if (window.RizzaAnalytics) {
          window.RizzaAnalytics.trackWorkoutComplete(w.id, totalSec);
        }
        const totalSetsPlanned = w.s.reduce((acc, st) => acc + (st.length - 1) * st[0], 0);
        const exDone = sessionEx || totalSetsPlanned;
        const h = hist(); h.push({ id: w.id, name: (woName(w) || '').slice(0, 48), t: finishTs, s: totalSec, reps: sessionReps, ex: exDone, vol: sessionVolume }); localStorage.hist = JSON.stringify(h);
        scheduleCloudSync();
        const minsDone = Math.max(1, Math.round(totalSec / 60));
        const kcalDone = Math.max(18, Math.round(minsDone * 7 + sessionReps * 0.35));
        const xpEarned = 150 + minsDone * 10 + sessionPrs.length * 50;
        const duelPts = 100 + minsDone * 15;
        const activeDuelsCnt = window.AthleteProfile ? window.AthleteProfile.getDuels().filter(d => d.endsAt > Date.now() && !d.claimed).length : 0;
        const activeQ = window.AthleteProfile ? window.AthleteProfile.getQuest() : null;
        const qBadge = (activeQ && !activeQ.claimed && window.AthleteProfile)
          ? (() => { const qp = window.AthleteProfile.calcQuestProgress(activeQ, h); return `<div class="p-pr-badge" style="margin-bottom:10px;border-color:var(--green);color:var(--green);background:rgba(var(--green-r),0.15);">${L == 'ru' ? 'Квест' : 'Quest'}: ${qp.total}/${qp.target} (${qp.pct}%)</div>`; })()
          : '';
        P.innerHTML = `
          <div class="p-finish-card">
            <div class="p-finish-icon">${uiSvg('trophy', 34)}</div>
            <h1>${t('finish')}</h1>
            ${activeDuelsCnt ? `<div class="p-pr-badge" style="margin-bottom:8px;">+${duelPts} XP ${L == 'ru' ? 'в активные дуэли' : 'to active duels'}</div>` : ''}
            ${qBadge}
            ${sessionPrs.length ? `<div class="p-pr-badge" style="margin-bottom:10px;">${uiSvg('trophy', 13)} ${L == 'ru' ? 'Новые рекорды:' : 'New PRs:'} ${sessionPrs.map(p => `${esc(p.name)} (${p.val})`).join(', ')}</div>` : ''}
            <div class="p-finish-grid">
              <div class="p-fstat"><b>${minsDone}</b><small>${t('sec') == 'сек' ? 'мин' : 'min'}</small></div>
              <div class="p-fstat"><b>${sessionVolume > 0 ? sessionVolume.toLocaleString() : '~' + kcalDone}</b><small>${sessionVolume > 0 ? (L == 'ru' ? 'кг тоннаж' : 'kg vol') : (L == 'ru' ? 'ккал' : 'kcal')}</small></div>
              <div class="p-fstat"><b>${sessionReps ? sessionReps : exDone}</b><small>${sessionReps ? (L == 'ru' ? 'повторов' : 'reps') : t('exercises')}</small></div>
              <div class="p-fstat"><b>+${xpEarned}</b><small>XP</small></div>
            </div>
            <div class="p-rpe-box" id="p-rpe-box">
              <div class="p-rpe-title">${L == 'ru' ? 'Как прошла тренировка?' : 'How did this workout feel?'}</div>
              <div class="p-rpe-row">
                ${RPE_OPTS.map(r => `<button type="button" class="p-rpe-btn" data-rpe="${r.id}"><span>${r.icon}</span><b>${L == 'ru' ? r.ru : r.en}</b></button>`).join('')}
              </div>
              <div class="p-rpe-hint hidden" id="p-rpe-hint"></div>
            </div>
            <div class="p-finish-actions">
              <button class="p-action-btn share-btn" id="share-card-btn">${uiSvg('image', 15)} ${L == 'ru' ? 'Карточка PNG' : 'Share Card'}</button>
              <button class="p-action-btn alt-btn" id="share-btn" style="margin-top:8px">${uiSvg('upload', 15)} ${L == 'ru' ? 'Поделиться текстом' : 'Share text'}</button>
            </div>
            <button class="p-action-btn alt-btn" id="x" style="margin-top:8px">${t('close')}</button>
          </div>`;
        P.querySelectorAll('[data-rpe]').forEach(btn => {
          btn.onclick = () => {
            vib(30);
            const rpeId = btn.dataset.rpe;
            P.querySelectorAll('[data-rpe]').forEach(b => b.classList.toggle('on', b.dataset.rpe === rpeId));
            const curH = hist();
            const entry = curH.find(item => item.t === finishTs);
            if (entry) {
              entry.rpe = rpeId;
              localStorage.hist = JSON.stringify(curH);
              if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
            }
            const meta = RPE_OPTS.find(r => r.id === rpeId);
            const hint = document.getElementById('p-rpe-hint');
            if (hint && meta) {
              hint.textContent = L == 'ru' ? meta.hintRu : meta.hintEn;
              hint.classList.remove('hidden');
            }
          };
        });
        document.getElementById('x').onclick = () => { vib(25); stop(); };
        const cardBtn = document.getElementById('share-card-btn');
        if (cardBtn) cardBtn.onclick = async () => {
          vib(35);
          let locP = {};
          try { locP = JSON.parse(localStorage.athleteProfile || '{}'); } catch (e) {}
          const athName = (locP.name || (CFG.athlete && CFG.athlete.name) || 'Flexa Athlete');
          const blob = await generateWorkoutShareCard({
            title: woName(w),
            mins: minsDone,
            kcal: kcalDone,
            vol: sessionVolume,
            reps: sessionReps,
            ex: exDone,
            xp: xpEarned,
            streak: calcStreak(h),
            prsCount: sessionPrs.length,
            athlete: athName
          });
          if (!blob) return;
          const url = URL.createObjectURL(blob);
          const bd = document.createElement('div');
          bd.className = 'ap-modal-backdrop';
          bd.innerHTML = `<div class="ap-modal">
            <h3>${L == 'ru' ? 'Карточка тренировки' : 'Workout Share Card'}</h3>
            <img class="share-preview-img" src="${url}" alt="">
            <div class="ap-modal-actions">
              <button type="button" class="btn alt" id="sc-dl">${uiSvg('download', 14)} ${L == 'ru' ? 'Скачать' : 'Save'}</button>
              <button type="button" class="btn" id="sc-send">${uiSvg('upload', 14)} ${L == 'ru' ? 'Отправить' : 'Send'}</button>
            </div>
          </div>`;
          document.body.appendChild(bd);
          const closeCard = () => { URL.revokeObjectURL(url); bd.remove(); };
          bd.onclick = ev => { if (ev.target === bd) closeCard(); };
          bd.querySelector('#sc-dl').onclick = () => {
            vib(25);
            const a = document.createElement('a');
            a.href = url;
            a.download = `flexa-${new Date().toISOString().slice(0, 10)}.png`;
            a.click();
          };
          bd.querySelector('#sc-send').onclick = async () => {
            vib(25);
            try {
              const file = new File([blob], 'flexa-workout.png', { type: 'image/png' });
              if (navigator.canShare && navigator.canShare({ files: [file] })) {
                await navigator.share({ title: CFG.brand || 'Flexa', text: woName(w), files: [file] });
                return;
              }
            } catch (e) {}
            const a = document.createElement('a');
            a.href = url;
            a.download = `flexa-${new Date().toISOString().slice(0, 10)}.png`;
            a.click();
          };
        };
        document.getElementById('share-btn').onclick = () => {
          vib(35);
          const shareText = `🏋️ ${CFG.brand} — ${woName(w)}\n⏱ ${Math.max(1, Math.round(totalSec / 60))} ${L == 'ru' ? 'минут' : 'min'} | 🏆 ${t('finish')}\n${location.origin}`;
          if (navigator.share) {
            navigator.share({ title: CFG.brand, text: shareText, url: location.href }).catch(() => {});
          } else {
            navigator.clipboard.writeText(shareText).then(() => {
              const b = document.getElementById('share-btn');
              if (b) b.textContent = '✓ ' + (L == 'ru' ? 'Скопировано!' : 'Copied!');
            }).catch(() => {});
          }
        };
        return;
      }
      const s = steps[i], pct = Math.round((i / steps.length) * 100);
      if (s.curLeft === undefined) s.curLeft = s.type == 'rest' ? s.sec : s.n[2];
      let left = s.curLeft, totalTime = s.type == 'rest' ? s.sec : s.n[2];
      const topBar = `
        <div class="p-header">
          <button class="p-btn-close" id="x" aria-label="Close">✕</button>
          <div class="p-step-badge">${i + 1} / ${steps.length} · ${s.label || t('rest')}</div>
          <div class="p-hdr-right">
            <button class="p-pause-btn" id="p-snd" aria-label="Sound">${audioIcon()}</button>
            <button class="p-pause-btn" id="p-pause" aria-label="Pause">${isPaused ? '▶' : '⏸'}</button>
          </div>
        </div>
        <div class="p-progress-track"><div class="p-progress-fill" style="width:${pct}%"></div></div>
        ${isPaused ? `<div class="p-paused-overlay">⏸ ${L == 'ru' ? 'ПАУЗА' : 'PAUSED'}</div>` : ''}`;

      if (s.type == 'rest') {
        const nextE = s.nextEx ? exMap[s.nextEx[0]] : null;
        if (!s._spoken && !isPaused) {
          s._spoken = true;
          speak(nextE
            ? (L == 'ru' ? `Отдых ${s.sec} секунд. Далее ${exName(nextE)}` : `Rest ${s.sec} seconds. Next up ${exName(nextE)}`)
            : (L == 'ru' ? `Отдых ${s.sec} секунд` : `Rest ${s.sec} seconds`));
        }
        P.innerHTML = `
          ${topBar}
          <div class="p-body rest-mode">
            <div class="p-control-pod" style="margin:auto 0;gap:10px;">
              <span class="p-rest-badge">${uiSvg('clock', 12)} ${t('rest').toUpperCase()}</span>
              <div class="p-timer-circle rest-ring">
                <svg viewBox="0 0 100 100">
                  <circle class="p-bg-ring" cx="50" cy="50" r="42"/>
                  <circle class="p-fg-ring" id="ring" cx="50" cy="50" r="42" style="stroke-dasharray:264;stroke-dashoffset:0;"/>
                </svg>
                <div class="p-circle-text">
                  <span class="p-big-num" id="c">${left}</span>
                  <span class="p-unit-sub">${t('sec')}</span>
                </div>
              </div>
              <div class="p-rest-buttons">
                <button class="p-plus-btn" id="m15">-15 ${t('sec')}</button>
                <button class="p-plus-btn" id="p15">+15 ${t('sec')}</button>
              </div>
              <div class="p-rest-presets" id="p-rest-presets">
                ${[0, 30, 45, 60, 90].map(secVal => `<button type="button" class="p-rest-chip ${getRestPreset() === secVal ? 'on' : ''}" data-rp="${secVal}">${secVal === 0 ? (L == 'ru' ? 'Авто' : 'Auto') : secVal + t('sec')}</button>`).join('')}
              </div>
            </div>
            ${nextE ? `
              <div class="p-next-card">
                <div class="p-next-thumb">${nextE.img ? `<img src="img/ex/svg_norm_${nextE.id}.svg">` : uiSvg('dumbbell', 18)}</div>
                <div class="p-next-info">
                  <small>${L == 'ru' ? 'СЛЕДУЮЩЕЕ' : 'NEXT UP'}</small>
                  <b>${esc(exName(nextE))}</b>
                  <span>${s.nextEx[2]} ${s.nextEx[1] == 'second' ? t('sec') : t('rep')}</span>
                </div>
              </div>` : ''}
            <button class="p-action-btn" id="n">${t('skip')} →</button>
          </div>`;
        const ring = document.getElementById('ring');
        const updateRing = () => {
          if (ring) ring.style.strokeDashoffset = 264 * (1 - left / totalTime);
        };
        updateRing();
        const m15 = document.getElementById('m15');
        if (m15) m15.onclick = () => {
          vib(30);
          left = Math.max(0, left - 15);
          s.curLeft = left;
          const el = document.getElementById('c');
          if (el) el.textContent = left;
          updateRing();
          if (left <= 0) {
            clearInterval(timer);
            sfx('bell');
            vib([100, 50, 150]);
            afterRest = true;
            i++; show();
          }
        };
        const p15 = document.getElementById('p15');
        if (p15) p15.onclick = () => {
          vib(35); sfx('step');
          left += 15; totalTime += 15;
          s.curLeft = left;
          const el = document.getElementById('c');
          if (el) el.textContent = left;
          updateRing();
        };
        document.querySelectorAll('#p-rest-presets [data-rp]').forEach(btn => {
          btn.onclick = () => {
            const val = +btn.dataset.rp || 0;
            localStorage.restPreset = String(val);
            if (typeof scheduleCloudSync === 'function') scheduleCloudSync();
            vib(20); sfx('step');
            const nextSec = val > 0 ? val : (s.baseSec || 30);
            s.sec = nextSec;
            totalTime = nextSec;
            left = nextSec;
            s.curLeft = left;
            for (let k = i + 1; k < steps.length; k++) {
              if (steps[k].type === 'rest') {
                steps[k].sec = val > 0 ? val : (steps[k].baseSec || steps[k].sec);
              }
            }
            const el = document.getElementById('c');
            if (el) el.textContent = left;
            updateRing();
            document.querySelectorAll('#p-rest-presets [data-rp]').forEach(b => b.classList.toggle('on', +b.dataset.rp === val));
          };
        });
        timer = setInterval(() => {
          if (isPaused) return;
          left--;
          s.curLeft = left;
          const el = document.getElementById('c');
          if (el) el.textContent = left;
          updateRing();
          if (left <= 3 && left > 0) { sfx('tick'); vib(40); }
          if (left <= 0) {
            clearInterval(timer);
            sfx('bell');
            vib([100, 50, 150]);
            afterRest = true;
            i++; show();
          }
        }, 1000);
        const nextBtn = document.getElementById('n');
        if (nextBtn) nextBtn.onclick = () => {
          vib(35);
          sfx('bell');
          afterRest = true;
          i++; show();
        };
      } else {
        const e = exMap[s.n[0]], isT = s.n[1] == 'second';
        if (e && !isPaused && !s._spoken) {
          s._spoken = true;
          const prefix = afterRest ? (L == 'ru' ? 'Вперёд! ' : 'Go! ') : '';
          speak(`${prefix}${exName(e)}, ${s.n[2]} ${isT ? t('sec') : t('rep')}`);
        }
        afterRest = false;
        const prs = JSON.parse(localStorage.prs || '{}');
        const prevPr = prs[s.n[0]] || 0;
        const prevLog = !isT ? getExLog(s.n[0]) : null;
        if (!isT && s.weight === undefined) {
          s.weight = sessionWeights[s.n[0]] !== undefined ? sessionWeights[s.n[0]] : (prevLog ? prevLog.w : 0);
        }
        const mLabels = muscleLabelsMap();
        const mFlags = e ? detectMuscles(exCleanName(e)) : {};
        const mainMuscle = Object.keys(mFlags).find(k => mFlags[k]);
        const eqTag = e && e.eq && e.eq !== 'none' ? eqLbl(e.eq) : '';
        P.innerHTML = `
          ${topBar}
          <div class="p-body">
            <div class="p-stage-card">
              <div class="p-technique-card">
                ${renderExVisual(e, { allowToggle: true, forceVideo: true })}
              </div>
              <h2 class="p-ex-title">${esc(e ? exName(e) : '#' + s.n[0])}</h2>
              <div class="p-ex-tags">
                ${mainMuscle ? `<span class="p-ex-tag">${esc(mLabels[mainMuscle])}</span>` : ''}
                ${eqTag ? `<span class="p-ex-tag">${esc(eqTag)}</span>` : ''}
                ${!isT && prevPr > 0 ? `<span class="p-ex-tag gold">${uiSvg('trophy', 11)} PR: ${prevPr}</span>` : ''}
              </div>
              <div class="p-ex-actions">
                ${e && (e.d[L] || e.d.en) ? `<button class="p-info-btn" id="p-info" type="button">${L == 'ru' ? 'Техника' : 'How to'}</button>` : ''}
                <button class="p-info-btn p-swap-btn" id="p-swap" type="button">${uiSvg('repeat', 13)} ${L == 'ru' ? 'Заменить' : 'Swap'}</button>
              </div>
              ${e && (e.d[L] || e.d.en) ? `<div class="p-info-desc hidden" id="p-desc">${esc(e.d[L] || e.d.en)}</div>` : ''}
            </div>

            <div class="p-control-pod">
              ${isT ? `
                <div class="p-timer-circle">
                  <svg viewBox="0 0 100 100">
                    <circle class="p-bg-ring" cx="50" cy="50" r="42"/>
                    <circle class="p-fg-ring" id="ring" cx="50" cy="50" r="42" style="stroke-dasharray:264;stroke-dashoffset:0;"/>
                  </svg>
                  <div class="p-circle-text">
                    <span class="p-big-num" id="c">${left}</span>
                    <span class="p-unit-sub">${t('sec')}</span>
                  </div>
                </div>` : `
                <div class="p-rep-stepper">
                  <button class="p-step-btn" id="s-sub" aria-label="decrease">−</button>
                  <div class="p-big-counter">
                    <span class="p-big-num" id="rep-num">${s.n[2]}</span>
                    <span class="p-unit-sub">${t('rep')}</span>
                  </div>
                  <button class="p-step-btn" id="s-add" aria-label="increase">＋</button>
                </div>
                <div class="p-weight-row">
                  <button type="button" class="p-w-btn" id="w-sub">−2.5</button>
                  <label class="p-w-val" title="${L == 'ru' ? 'Рабочий вес (кг)' : 'Working weight (kg)'}">
                    <input type="number" inputmode="decimal" step="0.5" min="0" max="999" id="w-inp" value="${s.weight || 0}">
                    <span>${L == 'ru' ? 'кг' : 'kg'}</span>
                  </label>
                  <button type="button" class="p-w-btn" id="w-add">+2.5</button>
                </div>
                ${prevLog ? `<div class="p-prev-log">${L == 'ru' ? 'В прошлый раз' : 'Last time'}: ${prevLog.w > 0 ? prevLog.w + ' ' + (L == 'ru' ? 'кг' : 'kg') + ' × ' : ''}${prevLog.r} ${t('rep')}</div>` : ''}
                <div id="pr-badge" class="p-pr-badge ${s.n[2] > prevPr && prevPr > 0 ? '' : 'hidden'}">${uiSvg('trophy', 13)} ${L == 'ru' ? 'Новый рекорд!' : 'New Record!'}</div>`}
            </div>

            <button class="p-action-btn" id="n">${isT ? t('skip') : '✓ ' + t('done')}</button>
          </div>`;
        if (isT) {
          const ring = document.getElementById('ring');
          const updateRing = () => {
            if (ring) ring.style.strokeDashoffset = 264 * (1 - left / totalTime);
          };
          updateRing();
          timer = setInterval(() => {
            if (isPaused) return;
            left--;
            s.curLeft = left;
            const el = document.getElementById('c');
            if (el) el.textContent = left;
            updateRing();
            if (totalTime >= 20 && left === Math.floor(totalTime / 2)) {
              sfx('half');
              speak(L == 'ru' ? 'Половина!' : 'Halfway!');
            }
            if (left <= 3 && left > 0) { sfx('tick'); vib(40); }
            if (left <= 0) { sessionEx++; sfx('bell'); vib([100, 50, 150]); i++; show(); }
          }, 1000);
        } else {
          const checkPr = () => {
            const b = document.getElementById('pr-badge');
            if (b) b.classList.toggle('hidden', !(s.n[2] > prevPr && prevPr > 0));
          };
          const bSub = document.getElementById('s-sub'), bAdd = document.getElementById('s-add');
          if (bSub) bSub.onclick = () => { s.n[2] = Math.max(1, s.n[2] - 1); document.getElementById('rep-num').textContent = s.n[2]; checkPr(); sfx('step'); vib(30); };
          if (bAdd) bAdd.onclick = () => { s.n[2] += 1; document.getElementById('rep-num').textContent = s.n[2]; checkPr(); sfx('step'); vib(30); };
          const wInp = document.getElementById('w-inp'), wSub = document.getElementById('w-sub'), wAdd = document.getElementById('w-add');
          const setW = val => {
            const wVal = Math.max(0, Math.min(999, Math.round((+val || 0) * 10) / 10));
            s.weight = wVal;
            sessionWeights[s.n[0]] = wVal;
            if (wInp) wInp.value = wVal;
          };
          if (wSub) wSub.onclick = () => { setW((s.weight || 0) - 2.5); sfx('step'); vib(20); };
          if (wAdd) wAdd.onclick = () => { setW((s.weight || 0) + 2.5); sfx('step'); vib(20); };
          if (wInp) wInp.onchange = () => { setW(wInp.value); };
        }
        const pi = document.getElementById('p-info');
        if (pi) pi.onclick = () => {
          vib(25);
          const pd = document.getElementById('p-desc');
          if (pd) pd.classList.toggle('hidden');
        };
        const ps = document.getElementById('p-swap');
        if (ps) ps.onclick = () => {
          vib(25);
          const wasPaused = isPaused;
          isPaused = true;
          const labels = muscleLabelsMap();
          let bwOnly = false, sq = '', page = 0;

          const bd = document.createElement('div');
          bd.className = 'p-swap-backdrop';
          const baseInfo = findExerciseAlternatives(s.n[0]);
          const groupTags = baseInfo.groups.map(g => labels[g] || g).join(' · ') || (L == 'ru' ? 'Похожая нагрузка' : 'Similar movement');
          bd.innerHTML = `
            <div class="p-swap-sheet">
              <div class="p-swap-head">
                <div>
                  <b style="display:flex;align-items:center;gap:6px;">${uiSvg('repeat', 15)} ${L == 'ru' ? 'Заменить упражнение' : 'Swap Exercise'}</b>
                  <small>${esc(groupTags)}</small>
                </div>
                <button type="button" class="fr-btn-del" id="ps-close">✕</button>
              </div>
              <div class="p-swap-controls">
                <input id="ps-q" placeholder="${L == 'ru' ? 'Поиск замены…' : 'Search alternative…'}">
                <button type="button" class="p-swap-bw" id="ps-bw">${L == 'ru' ? 'Без инвентаря' : 'No gear'}</button>
              </div>
              <div id="ps-body"></div>
            </div>`;
          P.appendChild(bd);

          const closeSheet = () => {
            bd.remove();
            isPaused = wasPaused;
          };
          const renderList = () => {
            const found = findExerciseAlternatives(s.n[0], { bwOnly, q: sq });
            const total = found.items.length;
            const startIdx = total ? ((page * 4) % total) : 0;
            const slice = total ? Array.from({ length: Math.min(4, total) }, (_, k) => found.items[(startIdx + k) % total]) : [];
            const body = bd.querySelector('#ps-body');
            body.innerHTML = `
              <div class="p-swap-list">
                ${slice.length ? slice.map(alt => {
                  const eqTxt = alt.eq && alt.eq !== 'none' ? eqLbl(alt.eq) : eqLbl('no_equipment');
                  const hasVid = !!getExVideo(alt);
                  return `
                  <button type="button" class="p-swap-opt" data-swap-id="${alt.id}">
                    <span class="p-swap-thumb">${alt.img ? `<img src="img/ex/svg_norm_${alt.id}.svg" alt="">` : uiSvg('dumbbell', 18)}</span>
                    <span class="p-swap-info">
                      <b>${esc(exName(alt))}</b>
                      <small>${esc(eqTxt)}${hasVid ? ' · 3D' : ''}</small>
                    </span>
                    <span class="p-swap-pick">${L == 'ru' ? 'Выбрать' : 'Pick'} ›</span>
                  </button>`;
                }).join('') : `<div class="empty" style="padding:18px 8px;">${t('nothing')}</div>`}
              </div>
              ${total > 4 ? `<button type="button" class="btn alt block" id="ps-more" style="margin-top:10px;padding:10px;">↻ ${L == 'ru' ? 'Показать другие 4' : 'Show 4 more'}</button>` : ''}`;

            const moreBtn = body.querySelector('#ps-more');
            if (moreBtn) moreBtn.onclick = () => { vib(20); page++; renderList(); };
            body.querySelectorAll('[data-swap-id]').forEach(optBtn => {
              optBtn.onclick = () => {
                const newId = +optBtn.dataset.swapId;
                const alt = exMap[newId];
                if (!alt) return;
                const oldId = s.n[0];
                for (let k = i; k < steps.length; k++) {
                  const st = steps[k];
                  if (st.type === 'ex' && st.n[0] === oldId) {
                    let unit = st.n[1];
                    let amt = st.n[2];
                    if (alt.unit === 'second' && unit !== 'second') {
                      unit = 'second';
                      amt = Math.max(20, Math.min(60, amt * 3));
                    } else if (alt.unit === 'repeat' && unit === 'second') {
                      unit = 'repeat';
                      amt = Math.max(8, Math.min(20, Math.round(amt / 3)));
                    }
                    st.n = [alt.id, unit, amt, st.n[3]];
                    delete st.curLeft;
                    delete st._spoken;
                  } else if (st.type === 'rest' && st.nextEx && st.nextEx[0] === oldId) {
                    const nextStep = steps[k + 1];
                    if (nextStep && nextStep.type === 'ex') st.nextEx = nextStep.n;
                  }
                }
                closeSheet();
                vib(35);
                show();
              };
            });
          };

          bd.onclick = ev => { if (ev.target === bd) closeSheet(); };
          bd.querySelector('#ps-close').onclick = () => { vib(20); closeSheet(); };
          const bwBtn = bd.querySelector('#ps-bw');
          bwBtn.onclick = () => { vib(20); bwOnly = !bwOnly; bwBtn.classList.toggle('on', bwOnly); page = 0; renderList(); };
          bd.querySelector('#ps-q').oninput = ev => { sq = ev.target.value; page = 0; renderList(); };
          renderList();
        };
        const nextBtn = document.getElementById('n');
        if (nextBtn) nextBtn.onclick = () => {
          sessionEx++;
          if (!isT) {
            const curW = Math.max(0, +s.weight || 0);
            sessionReps += s.n[2];
            if (curW > 0) sessionVolume += Math.round(curW * s.n[2]);
            const logRes = saveExLog(s.n[0], curW, s.n[2]);
            const isRepPr = s.n[2] > prevPr && prevPr > 0;
            const isNewPr = isRepPr || logRes.isWeightPr;
            if (isNewPr) {
              const prLabel = logRes.isWeightPr ? `${curW} ${L == 'ru' ? 'кг' : 'kg'} × ${s.n[2]}` : s.n[2];
              sessionPrs.push({ id: s.n[0], name: exName(e), val: prLabel });
            }
            const prs = JSON.parse(localStorage.prs || '{}');
            prs[s.n[0]] = Math.max(prs[s.n[0]] || 0, s.n[2]);
            localStorage.prs = JSON.stringify(prs);
            sfx(isNewPr ? 'pr' : 'done');
            vib([60, 40, 90]);
          } else {
            sfx('done');
            vib(35);
          }
          i++; show();
        };
      }
      const pSndBtn = document.getElementById('p-snd');
      if (pSndBtn) pSndBtn.onclick = () => {
        vib(25);
        const wasPaused = isPaused;
        isPaused = true;
        openAudioModal(() => { isPaused = wasPaused; });
      };
      const pauseBtn = document.getElementById('p-pause');
      if (pauseBtn) pauseBtn.onclick = () => {
        vib(30);
        isPaused = !isPaused;
        if (isPaused) stopSpeech();
        show();
      };
      const closeBtn = document.getElementById('x');
      if (closeBtn) closeBtn.onclick = () => { vib(25); stop(); };
    }
    show();
  }

  // ---------- router ----------
  let arg = null;
  const langBtn = document.getElementById('lang');
  if (langBtn) {
    langBtn.onclick = () => {
      vib(15);
      L = L == 'ru' ? 'en' : 'ru';
      localStorage.lang = L;
      if (window.RizzaAnalytics) {
        window.RizzaAnalytics.trackCta('toggle_language', 'settings');
      }
      render();
    };
  }
  function render() {
    const [, name = 'home', a] = (location.hash || '#/').slice(1).split('/');
    const key = routes[name] ? name : 'home'; arg = a;
    if (key !== 'coach' && typeof window._cancelCoachRequest === 'function') {
      try { window._cancelCoachRequest(); } catch (_) {}
    }
    const topCoachBtn = document.getElementById('top-coach-btn');
    if (topCoachBtn) {
      topCoachBtn.classList.toggle('on', key === 'coach');
      const lbl = L == 'ru' ? 'AI-тренер' : 'AI Coach';
      topCoachBtn.title = lbl;
      topCoachBtn.setAttribute('aria-label', lbl);
    }
    document.body.classList.toggle('view-messages', key === 'messages');
    document.querySelectorAll('#nav a').forEach(x => {
      const b = x.querySelector('b');
      if (b && x.dataset.i) b.textContent = t(x.dataset.i);
      x.classList.toggle('on',
        x.dataset.k == key ||
        (key == 'profile' && x.dataset.k == 'history') ||
        ((key == 'users' || key == 'user' || key == 'friends') && x.dataset.k == 'users') ||
        (key == 'messages' && x.dataset.k == 'messages') ||
        ((key == 'workout' || key == 'builder' || key == 'program' || key == 'programs') && x.dataset.k == 'workouts') ||
        (key == 'exercise' && x.dataset.k == 'exercises')
      );
    });
    if (langBtn) {
      const codeEl = langBtn.querySelector('.lang-code');
      if (codeEl) codeEl.textContent = L.toUpperCase();
      else langBtn.textContent = L.toUpperCase();
      langBtn.title = L == 'ru' ? 'Язык: RU (переключить на EN)' : 'Language: EN (switch to RU)';
      langBtn.setAttribute('aria-label', langBtn.title);
    }
    document.documentElement.lang = L;
    syncNavAthlete();
    syncSndBtn();
    app.classList.remove('fx-enter');
    app.innerHTML = routes[key](a);
    void app.offsetWidth;
    app.classList.add('fx-enter');
    after(key);
    if (window.RizzaAnalytics) {
      const pageTitle = 'RizzaFit · ' + (t(key) || key);
      window.RizzaAnalytics.trackPageView(location.pathname + (location.hash || '#/'), pageTitle);
    }
    if (!['workouts', 'exercises'].includes(key)) window.scrollTo(0, 0);
  }
  document.querySelectorAll('#nav a').forEach(a => a.addEventListener('click', () => vib(12)));
  
  document.addEventListener('click', e => {
    const btn = e.target.closest('.visual-toggle-btn');
    if (btn) {
      if (typeof vib === 'function') vib(20);
      const wrap = btn.closest('.ex-visual-wrap');
      if (!wrap) return;
      const mode = btn.dataset.mode;
      const exId = wrap.dataset.id;
      const ex = exMap[exId];
      if (!ex) return;
      localStorage.setItem('flexa_view_mode', mode);
      wrap.outerHTML = renderExVisual(ex, { allowToggle: true, forceVideo: mode === 'video' });
    }
  });

  let toastTimer = null;
  function showAppToast(title, body, href) {
    document.querySelectorAll('.ap-toast').forEach(x => x.remove());
    clearTimeout(toastTimer);
    const el = document.createElement('div');
    el.className = 'ap-toast';
    el.innerHTML = `
      <div class="ap-toast-copy">
        <b>${esc(title)}</b>
        <small>${esc(body)}</small>
      </div>
      ${href ? `<a href="${esc(href)}" class="btn ap-toast-go">▶</a>` : ''}
      <button type="button" class="ap-toast-x" aria-label="Close">✕</button>`;
    document.body.appendChild(el);
    const kill = () => el.remove();
    el.querySelector('.ap-toast-x').onclick = kill;
    const go = el.querySelector('.ap-toast-go');
    if (go) go.onclick = kill;
    toastTimer = setTimeout(kill, 6500);
  }

  function checkDailyReminder() {
    if (!window.AthleteProfile || document.body.classList.contains('player-open')) return;
    const prefs = window.AthleteProfile.getNotifPrefs();
    if (!prefs.enabled) return;
    const now = new Date();
    const todayIso = now.toISOString().slice(0, 10);
    if (prefs.lastFiredDate === todayIso) return;
    const hhmm = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
    if (hhmm < prefs.time) return;
    const doneToday = hist().some(x => new Date(x.t).toISOString().slice(0, 10) === todayIso);
    if (doneToday) return;
    window.AthleteProfile.saveNotifPrefs({ lastFiredDate: todayIso });
    const msg = L == 'ru' ? `Запланированное время (${prefs.time}) — пора на тренировку!` : `Scheduled time (${prefs.time}) — time to train!`;
    showAppToast(CFG.brand || 'Flexa', msg, '#/workouts');
    if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      try { new Notification(CFG.brand || 'Flexa', { body: msg, icon: CFG.logo || 'img/logo.svg' }); } catch (e) {}
    }
  }
  setInterval(checkDailyReminder, 30000);

  let lastUnreadCheck = 0;
  let lastNotifiedMsgId = 0;
  try { lastNotifiedMsgId = Number(localStorage.getItem('last_notified_msg_id') || 0); } catch (e) {}

  async function checkUnreadMessages() {
    if (!isLoggedIn() || document.visibilityState !== 'visible') return;
    const now = Date.now();
    if (now - lastUnreadCheck < 6000) return;
    lastUnreadCheck = now;
    try {
      const data = await socialApi('/api/messages/unread-count');
      const badge = document.getElementById('nav-msg-badge');
      if (badge) {
        if (data.unreadCount > 0) {
          badge.textContent = data.unreadCount > 99 ? '99+' : String(data.unreadCount);
          badge.classList.remove('hidden');
        } else {
          badge.classList.add('hidden');
        }
      }
      if (data.latestMessage && data.latestMessage.id > lastNotifiedMsgId) {
        lastNotifiedMsgId = data.latestMessage.id;
        try { localStorage.setItem('last_notified_msg_id', String(data.latestMessage.id)); } catch (e) {}
        const isCurrentChat = (location.hash || '').startsWith('#/messages/' + data.latestMessage.conversationId);
        if (!isCurrentChat) {
          showAppToast(
            data.latestMessage.senderName || 'RizzaFit',
            data.latestMessage.previewText || (L == 'ru' ? 'Новое сообщение' : 'New message'),
            '#/messages/' + data.latestMessage.conversationId
          );
        }
      }
    } catch (e) {}
  }
  setInterval(checkUnreadMessages, 12000);
  setTimeout(checkUnreadMessages, 2000);

  window.addEventListener('hashchange', () => { checkPendingPayment(); render(); });
  checkPendingPayment();
  if (window.AthleteProfile && window.AthleteProfile.purgeLegacyFakes) {
    window.AthleteProfile.purgeLegacyFakes();
  }
  render();
  pullCloudSync(false);
  syncCommunityUsers().then(() => {
    if (location.hash.includes('friends') || location.hash.includes('profile')) render();
  });
  setTimeout(checkDailyReminder, 1500);
})();

