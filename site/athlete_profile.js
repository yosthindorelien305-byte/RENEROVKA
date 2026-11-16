(function () {
  const DEFAULT_FRIENDS = [
    { id: 'f1', name: 'Алекс Волков', handle: '@alex_fit', level: 11, streak: 42, points: 24800, online: true, color: '#3b4a34', shirt: '#6b8e4e' },
    { id: 'f2', name: 'Мария Соколова', handle: '@masha_run', level: 9, streak: 28, points: 19450, online: true, color: '#4d3e28', shirt: '#c68932' },
    { id: 'f3', name: 'Дмитрий К.', handle: '@dima_iron', level: 7, streak: 19, points: 15200, online: false, color: '#2b3930', shirt: '#4f6d5a' },
    { id: 'f4', name: 'Елена Громова', handle: '@lena_flex', level: 10, streak: 31, points: 21300, online: true, color: '#3b3342', shirt: '#7b6894' }
  ];

  const SUGGESTED_FRIENDS = [
    { id: 's1', name: 'Иван Титов', handle: '@ivan_titan', level: 12, streak: 50, points: 28100, online: true, color: '#2e3f2d', shirt: '#5b8a47' },
    { id: 's2', name: 'Анна К.', handle: '@anna_yoga', level: 8, streak: 22, points: 16800, online: true, color: '#44372b', shirt: '#b87d38' },
    { id: 's3', name: 'Максим Барс', handle: '@bars_sw', level: 14, streak: 64, points: 31900, online: false, color: '#283635', shirt: '#486c68' }
  ];

  const DEFAULTS = {
    name: 'Атлет',
    handle: '@athlete',
    avatar: '',
    points: 0,
    winRate: 70,
    level: 1,
    days: 0,
    streakDays: 0,
    friendsOnline: 14,
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
    useLiveStats: true,
    friends: null
  };

  function getFriends(cfgAthlete) {
    try {
      const raw = localStorage.getItem('athleteFriends');
      if (raw !== null) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    if (cfgAthlete && Array.isArray(cfgAthlete.friends) && cfgAthlete.friends.length) {
      return cfgAthlete.friends;
    }
    return DEFAULT_FRIENDS.map(f => Object.assign({}, f));
  }

  function saveFriends(list) {
    localStorage.setItem('athleteFriends', JSON.stringify(list || []));
  }

  function getDuels() {
    try {
      const raw = JSON.parse(localStorage.getItem('athleteDuels') || '[]');
      return Array.isArray(raw) ? raw : [];
    } catch (e) {
      return [];
    }
  }

  function saveDuels(list) {
    localStorage.setItem('athleteDuels', JSON.stringify(list || []));
  }

  function getDuelStats() {
    try {
      const raw = JSON.parse(localStorage.getItem('athleteDuelStats') || '{}');
      return { wins: Number(raw.wins) || 0, bonusXp: Number(raw.bonusXp) || 0 };
    } catch (e) {
      return { wins: 0, bonusXp: 0 };
    }
  }

  function startDuel(friend) {
    if (!friend) return null;
    const duels = getDuels();
    const now = Date.now();
    const active = duels.find(d => String(d.friendId) === String(friend.id) && d.endsAt > now && !d.claimed);
    if (active) return active;
    const duel = {
      id: 'd_' + now + '_' + Math.random().toString(36).slice(2, 6),
      friendId: friend.id,
      friendName: friend.name,
      friendHandle: friend.handle,
      friendLevel: Number(friend.level) || 6,
      friendStreak: Number(friend.streak) || 10,
      friendColor: friend.color || '#3b4a34',
      friendShirt: friend.shirt || '#6b8e4e',
      friendAvatar: friend.avatar || '',
      startedAt: now,
      endsAt: now + 7 * 86400000,
      bonusPts: 0,
      claimed: false
    };
    const filtered = duels.filter(d => String(d.friendId) !== String(friend.id) || d.claimed);
    filtered.unshift(duel);
    saveDuels(filtered.slice(0, 12));
    return duel;
  }

  function calcMyDuelScore(duel, histList) {
    if (!duel) return 0;
    const h = Array.isArray(histList) ? histList : [];
    const since = Number(duel.startedAt) || 0;
    let pts = Number(duel.bonusPts) || 0;
    h.forEach(x => {
      if ((Number(x.t) || 0) >= since && (Number(x.t) || 0) <= (Number(duel.endsAt) || Infinity)) {
        const mins = Math.max(1, Math.round((Number(x.s) || 0) / 60));
        pts += 100 + mins * 15;
      }
    });
    return Math.round(pts);
  }

  function calcRivalDuelScore(duel) {
    if (!duel) return 0;
    const now = Math.min(Date.now(), Number(duel.endsAt) || Date.now());
    const elapsedHrs = Math.max(0.5, (now - (Number(duel.startedAt) || now)) / 3600000);
    const lvl = Number(duel.friendLevel) || 6;
    const str = Number(duel.friendStreak) || 10;
    const ratePerHour = 10 + Math.min(18, lvl * 1.1 + str * 0.12);
    const seed = String(duel.id || '').split('').reduce((s, c) => s + c.charCodeAt(0), 0);
    const wave = Math.sin(elapsedHrs * 0.4 + seed) * 28;
    return Math.max(40, Math.round(elapsedHrs * ratePerHour + wave));
  }

  function addDuelBonus(pts) {
    const add = Number(pts) || 0;
    if (!add) return 0;
    const now = Date.now();
    const duels = getDuels();
    let activeCount = 0;
    duels.forEach(d => {
      if (d.endsAt > now && !d.claimed) {
        d.bonusPts = (Number(d.bonusPts) || 0) + add;
        activeCount++;
      }
    });
    if (activeCount) saveDuels(duels);
    return activeCount;
  }

  function claimDuel(duelId, histList, rewardXp) {
    const duels = getDuels();
    const d = duels.find(x => x.id === duelId);
    if (!d || d.claimed) return false;
    const my = calcMyDuelScore(d, histList);
    const rv = calcRivalDuelScore(d);
    d.claimed = true;
    d.finalMy = my;
    d.finalRival = rv;
    saveDuels(duels);
    if (my >= rv) {
      const st = getDuelStats();
      st.wins += 1;
      st.bonusXp += Number(rewardXp) || 500;
      localStorage.setItem('athleteDuelStats', JSON.stringify(st));
      return { won: true, reward: Number(rewardXp) || 500 };
    }
    return { won: false, reward: 0 };
  }

  const QUEST_TEMPLATES = [
    { type: 'workouts', titleRu: 'Сделать 10 тренировок на двоих', titleEn: 'Complete 10 workouts together', target: 10, unitRu: 'трен.', unitEn: 'wkt', reward: 500 },
    { type: 'minutes', titleRu: 'Набрать 180 минут активности вместе', titleEn: 'Log 180 active minutes together', target: 180, unitRu: 'мин', unitEn: 'min', reward: 600 },
    { type: 'xp', titleRu: 'Заработать 1 500 XP в паре', titleEn: 'Earn 1,500 XP together', target: 1500, unitRu: 'XP', unitEn: 'XP', reward: 650 }
  ];

  function getQuest() {
    try {
      const q = JSON.parse(localStorage.getItem('athleteQuest') || 'null');
      return q && typeof q === 'object' ? q : null;
    } catch (e) {
      return null;
    }
  }

  function saveQuest(q) {
    if (!q) localStorage.removeItem('athleteQuest');
    else localStorage.setItem('athleteQuest', JSON.stringify(q));
  }

  function getQuestStats() {
    try {
      const s = JSON.parse(localStorage.getItem('athleteQuestStats') || '{}');
      return { done: Number(s.done) || 0, bonusXp: Number(s.bonusXp) || 0 };
    } catch (e) {
      return { done: 0, bonusXp: 0 };
    }
  }

  function startQuest(friend, tplType, customReward) {
    if (!friend) return null;
    const tpl = QUEST_TEMPLATES.find(t => t.type === tplType) || QUEST_TEMPLATES[0];
    const now = Date.now();
    const q = {
      id: 'q_' + now,
      friendId: friend.id,
      friendName: friend.name,
      friendHandle: friend.handle,
      friendLevel: Number(friend.level) || 6,
      friendStreak: Number(friend.streak) || 10,
      friendColor: friend.color || '#3b4a34',
      friendShirt: friend.shirt || '#6b8e4e',
      friendAvatar: friend.avatar || '',
      type: tpl.type,
      titleRu: tpl.titleRu,
      titleEn: tpl.titleEn,
      target: tpl.target,
      unitRu: tpl.unitRu,
      unitEn: tpl.unitEn,
      reward: Number(customReward) > 0 ? Number(customReward) : tpl.reward,
      startedAt: now,
      endsAt: now + 7 * 86400000,
      claimed: false
    };
    saveQuest(q);
    return q;
  }

  function calcQuestProgress(q, histList) {
    if (!q) return { my: 0, friend: 0, total: 0, target: 1, pct: 0, done: false };
    const h = Array.isArray(histList) ? histList : [];
    const since = Number(q.startedAt) || 0;
    const until = Number(q.endsAt) || Infinity;
    let myW = 0, myMin = 0;
    h.forEach(x => {
      const t = Number(x.t) || 0;
      if (t >= since && t <= until) {
        myW += 1;
        myMin += Math.max(1, Math.round((Number(x.s) || 0) / 60));
      }
    });
    const my = q.type === 'minutes' ? myMin : (q.type === 'xp' ? myW * 100 + myMin * 15 : myW);
    const now = Math.min(Date.now(), until);
    const elapsedRatio = Math.max(0.06, Math.min(1, (now - since) / (7 * 86400000)));
    const lvlFactor = 0.55 + Math.min(0.4, (Number(q.friendLevel) || 6) * 0.03);
    const friendCap = Math.round(q.target * 0.55);
    const friend = Math.min(friendCap, Math.max(q.type === 'workouts' ? 1 : (q.type === 'minutes' ? 12 : 80), Math.round(q.target * 0.55 * elapsedRatio * lvlFactor)));
    const total = my + friend;
    const pct = Math.min(100, Math.round((total / Math.max(1, q.target)) * 100));
    return { my, friend, total, target: q.target, pct, done: total >= q.target };
  }

  function claimQuest(histList) {
    const q = getQuest();
    if (!q || q.claimed) return null;
    const pr = calcQuestProgress(q, histList);
    if (!pr.done) return null;
    q.claimed = true;
    saveQuest(q);
    const st = getQuestStats();
    st.done += 1;
    st.bonusXp += Number(q.reward) || 500;
    localStorage.setItem('athleteQuestStats', JSON.stringify(st));
    return { reward: Number(q.reward) || 500 };
  }

  function formatDuelLeft(endsAt, lang) {
    const ms = Math.max(0, Number(endsAt) - Date.now());
    if (ms <= 0) return lang === 'ru' ? 'Завершена' : 'Finished';
    const hrs = Math.floor(ms / 3600000);
    const d = Math.floor(hrs / 24);
    const h = hrs % 24;
    if (d > 0) return lang === 'ru' ? `${d}д ${h}ч` : `${d}d ${h}h`;
    const mins = Math.max(1, Math.floor((ms % 3600000) / 60000));
    return h > 0 ? (lang === 'ru' ? `${h}ч ${mins}м` : `${h}h ${mins}m`) : (lang === 'ru' ? `${mins}м` : `${mins}m`);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  function getNotifPrefs() {
    let raw = {};
    try { raw = JSON.parse(localStorage.getItem('athleteNotifPrefs') || '{}'); } catch (e) {}
    return {
      enabled: !!raw.enabled,
      time: /^\d{2}:\d{2}$/.test(raw.time || '') ? raw.time : '19:00',
      duels: raw.duels !== false,
      streak: raw.streak !== false,
      lastFiredDate: raw.lastFiredDate || ''
    };
  }

  function saveNotifPrefs(next) {
    const merged = Object.assign(getNotifPrefs(), next || {});
    localStorage.setItem('athleteNotifPrefs', JSON.stringify(merged));
    return merged;
  }

  function getReadNotifs() {
    try {
      const arr = JSON.parse(localStorage.getItem('athleteReadNotifs') || '[]');
      return new Set(Array.isArray(arr) ? arr : []);
    } catch (e) {
      return new Set();
    }
  }

  function markNotifsRead(ids) {
    const cur = getReadNotifs();
    (ids || []).forEach(id => cur.add(String(id)));
    const trimmed = [...cur].slice(-120);
    localStorage.setItem('athleteReadNotifs', JSON.stringify(trimmed));
  }

  function getFreezeState() {
    let raw = {};
    try { raw = JSON.parse(localStorage.getItem('athleteFreeze') || '{}'); } catch (e) {}
    return {
      tokens: raw.tokens === undefined ? 1 : Math.max(0, Math.min(5, Number(raw.tokens) || 0)),
      usedDates: Array.isArray(raw.usedDates) ? raw.usedDates : [],
      spentXp: Math.max(0, Number(raw.spentXp) || 0)
    };
  }

  function saveFreezeState(st) {
    const clean = {
      tokens: Math.max(0, Math.min(5, Number(st.tokens) || 0)),
      usedDates: Array.isArray(st.usedDates) ? st.usedDates.slice(-90) : [],
      spentXp: Math.max(0, Number(st.spentXp) || 0)
    };
    localStorage.setItem('athleteFreeze', JSON.stringify(clean));
    return clean;
  }

  function useFreezeOnDate(isoDate) {
    const st = getFreezeState();
    if (st.tokens <= 0 || st.usedDates.includes(isoDate)) return false;
    st.tokens -= 1;
    st.usedDates.push(isoDate);
    saveFreezeState(st);
    return true;
  }

  function buyFreezeToken(curXp, cost = 300) {
    const st = getFreezeState();
    if (st.tokens >= 3) return { ok: false, reason: 'max' };
    if ((Number(curXp) || 0) < cost) return { ok: false, reason: 'xp' };
    st.tokens += 1;
    st.spentXp += cost;
    saveFreezeState(st);
    return { ok: true, state: st };
  }

  function calcStreakSimple(list) {
    const dates = new Set((list || []).map(x => new Date(x.t).toISOString().slice(0, 10)));
    getFreezeState().usedDates.forEach(d => dates.add(d));
    if (!dates.size) return 0;
    let s = 0, d = new Date();
    if (!dates.has(d.toISOString().slice(0, 10))) d.setDate(d.getDate() - 1);
    while (dates.has(d.toISOString().slice(0, 10))) {
      s++;
      d.setDate(d.getDate() - 1);
    }
    return s;
  }

  function buildNotifications(opts) {
    const o = opts || {};
    const L = o.lang === 'en' ? 'en' : 'ru';
    const allH = Array.isArray(o.hist) ? o.hist : (() => {
      try { return JSON.parse(localStorage.getItem('hist') || '[]'); } catch (e) { return []; }
    })();
    const prefs = getNotifPrefs();
    const readSet = getReadNotifs();
    const now = Date.now();
    const todayIso = new Date(now).toISOString().slice(0, 10);
    const doneDates = new Set(allH.map(x => new Date(x.t).toISOString().slice(0, 10)));
    const doneToday = doneDates.has(todayIso);
    const streak = calcStreakSimple(allH);
    const rewardXp = Number((o.cfgAthlete && o.cfgAthlete.duelReward) || 500);
    const list = [];

    if (prefs.enabled && !doneToday) {
      const d = new Date(now);
      const hhmm = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
      if (hhmm >= prefs.time) {
        list.push({
          id: 'rem_due_' + todayIso,
          icon: '⏰',
          tone: 'gold',
          title: L === 'ru' ? `Время тренировки (${prefs.time})` : `Workout time (${prefs.time})`,
          body: L === 'ru' ? 'Вы запланировали тренировку на это время — выберите программу и начните!' : 'Scheduled session is due — pick a workout and start!',
          href: '#/workouts'
        });
      }
    }

    if (prefs.duels) {
      const duels = getDuels().filter(d => !d.claimed);
      duels.forEach(d => {
        const my = calcMyDuelScore(d, allH);
        const rv = calcRivalDuelScore(d);
        if (now >= d.endsAt) {
          list.push({
            id: 'duel_end_' + d.id,
            icon: my >= rv ? '🏆' : '🏁',
            tone: my >= rv ? 'gold' : 'green',
            title: L === 'ru' ? `Дуэль с ${d.friendName} завершена` : `Duel vs ${d.friendName} finished`,
            body: my >= rv
              ? (L === 'ru' ? `Вы победили (${my}:${rv} XP)! Заберите +${rewardXp} XP` : `You won (${my}:${rv} XP)! Claim +${rewardXp} XP`)
              : (L === 'ru' ? `Счёт ${my}:${rv} XP — откройте, чтобы бросить реванш` : `Score ${my}:${rv} XP — tap to launch a rematch`),
            href: '#/friends'
          });
        } else if (rv > my) {
          list.push({
            id: 'duel_behind_' + d.id + '_' + todayIso,
            icon: '⚔️',
            tone: 'gold',
            title: L === 'ru' ? `${d.friendName} обгоняет в дуэли` : `${d.friendName} leads your duel`,
            body: L === 'ru' ? `Отставание ${rv - my} XP — завершите 1 тренировку сегодня (+100+ XP)` : `Behind by ${rv - my} XP — finish 1 workout today to retake the lead`,
            href: '#/friends'
          });
        } else {
          list.push({
            id: 'duel_lead_' + d.id + '_' + todayIso,
            icon: '🥇',
            tone: 'green',
            title: L === 'ru' ? `Вы впереди против ${d.friendName}` : `Leading vs ${d.friendName}`,
            body: L === 'ru' ? `Отрыв +${my - rv} XP · осталось ${formatDuelLeft(d.endsAt, L)}` : `Up by +${my - rv} XP · ${formatDuelLeft(d.endsAt, L)} left`,
            href: '#/friends'
          });
        }
      });

      const q = getQuest();
      if (q && !q.claimed) {
        const qp = calcQuestProgress(q, allH);
        if (qp.done) {
          list.push({
            id: 'quest_done_' + q.id,
            icon: '🤝',
            tone: 'green',
            title: L === 'ru' ? `Квест с ${q.friendName} выполнен!` : `Co-op quest with ${q.friendName} done!`,
            body: L === 'ru' ? `Откройте раздел друзей и заберите +${q.reward} XP` : `Open Friends to claim your +${q.reward} XP reward`,
            href: '#/friends'
          });
        } else {
          const left = Math.max(0, qp.target - qp.total);
          list.push({
            id: 'quest_prog_' + q.id + '_' + todayIso,
            icon: '🎯',
            tone: 'green',
            title: L === 'ru' ? `Совместный квест: ${qp.pct}%` : `Co-op quest: ${qp.pct}%`,
            body: L === 'ru' ? `Вместе с ${q.friendName} осталось набрать ${left}` : `${left} remaining together with ${q.friendName}`,
            href: '#/friends'
          });
        }
      }
    }

    if (prefs.streak) {
      if (!allH.length) {
        list.push({
          id: 'first_wo',
          icon: '⚡',
          tone: 'gold',
          title: L === 'ru' ? 'Пора открыть статистику' : 'Start your first workout',
          body: L === 'ru' ? 'Сделайте первую тренировку, чтобы запустить серию и получить +150 XP' : 'Complete your first workout to start a streak and earn +150 XP',
          href: '#/workouts'
        });
      } else if (!doneToday && streak > 0) {
        list.push({
          id: 'streak_risk_' + todayIso,
          icon: '🔥',
          tone: 'gold',
          title: L === 'ru' ? `Сохраните серию ${streak} дн.` : `Keep your ${streak}-day streak`,
          body: L === 'ru' ? 'Сегодня ещё не было занятия — подойдёт даже короткая разминка на 3 мин' : 'No workout logged today yet — even a 3-min warm-up keeps it alive',
          href: '#/workouts'
        });
      }
      const last = allH.length ? allH[allH.length - 1] : null;
      if (last && last.rpe === 'hard' && !doneToday && (now - last.t) < 40 * 3600000) {
        list.push({
          id: 'rpe_recover_' + last.t,
          icon: '🧘',
          tone: 'green',
          title: L === 'ru' ? 'Совет по восстановлению' : 'Recovery tip',
          body: L === 'ru' ? 'Прошлое занятие отмечено как тяжёлое — сегодня лучше выбрать лёгкий темп или растяжку' : 'Your last workout felt hard — try an easy session or stretching today',
          href: '#/workouts'
        });
      }
    }

    return list.map(n => Object.assign({}, n, { read: readSet.has(n.id) }));
  }

  function getUnreadNotifCount(opts) {
    return buildNotifications(opts).filter(n => !n.read).length;
  }

  function merge(cfgAthlete, live) {
    const a = Object.assign({ duelReward: 500, questReward: 500 }, DEFAULTS, cfgAthlete || {});
    const uName = (localStorage.getItem('userName') || '').trim();
    let locProf = {};
    try { locProf = JSON.parse(localStorage.getItem('athleteProfile') || '{}'); } catch (e) {}
    if (uName) {
      if (!locProf.name || locProf.name === 'Mr.Bobrovsky' || locProf.name === 'Атлет') {
        a.name = uName;
      }
      if (!locProf.handle || locProf.handle === '@mr.bobrovsky' || locProf.handle === '@athlete') {
        a.handle = '@' + uName.toLowerCase();
      }
    } else {
      if (a.name === 'Mr.Bobrovsky') a.name = 'Атлет';
      if (a.handle === '@mr.bobrovsky') a.handle = '@athlete';
    }
    const ds = getDuelStats();
    const qs = getQuestStats();
    const fz = getFreezeState();
    if (live && a.useLiveStats !== false) {
      const doneCount = live.workoutsCount || 0;
      const streak = live.streak || 0;
      const prsCount = live.prsCount || 0;
      const weekPct = live.weekPct;
      if (doneCount > 0) {
        a.points = Math.max(0, (Number(a.points) || 0) + doneCount * 150 + prsCount * 80 + ds.bonusXp + qs.bonusXp - fz.spentXp);
        a.level = Math.max(Number(a.level) || 1, 1 + Math.floor((doneCount + prsCount + ds.wins + qs.done) / 2));
        a.days = Math.max(Number(a.days) || 0, live.uniqueDays || doneCount);
        a.streakDays = Math.max(Number(a.streakDays) || 0, streak);
        if (typeof weekPct === 'number' && weekPct > 0) {
          a.winRate = Math.min(100, weekPct);
        }
      } else if (ds.bonusXp > 0 || qs.bonusXp > 0 || fz.spentXp > 0) {
        a.points = Math.max(0, (Number(a.points) || 0) + ds.bonusXp + qs.bonusXp - fz.spentXp);
      }
    }
    return a;
  }

  function formatPoints(n) {
    const num = Number(n) || 0;
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function buildWeek(lang, doneDatesSet) {
    const now = new Date();
    const currentDay = (now.getDay() + 6) % 7; // Mon=0..Sun=6
    const frozenSet = new Set(getFreezeState().usedDates);
    const names = lang === 'ru'
      ? ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
      : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(now);
      d.setDate(now.getDate() - currentDay + i);
      const iso = d.toISOString().slice(0, 10);
      const isToday = i === currentDay;
      const isDone = (doneDatesSet ? doneDatesSet.has(iso) : false) || frozenSet.has(iso);
      days.push({
        label: names[i],
        num: d.getDate(),
        iso,
        isToday,
        isDone
      });
    }
    return days;
  }

  function defaultAvatarSvg() {
    return `<svg viewBox="0 0 80 80" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="avBg" cx="50%" cy="35%" r="65%">
          <stop offset="0%" stop-color="#263042"/>
          <stop offset="100%" stop-color="#11151E"/>
        </radialGradient>
      </defs>
      <rect width="80" height="80" fill="url(#avBg)"/>
      <circle cx="40" cy="31" r="14" fill="#d9d5c0"/>
      <circle cx="28" cy="22" r="4.5" fill="#b4b19d"/>
      <circle cx="52" cy="22" r="4.5" fill="#b4b19d"/>
      <ellipse cx="40" cy="34" rx="7" ry="5" fill="#ece9d8"/>
      <circle cx="35" cy="29" r="2" fill="#11151E"/>
      <circle cx="45" cy="29" r="2" fill="#11151E"/>
      <path d="M37 33h6l-3 3z" fill="#1C222E"/>
      <path d="M18 74c2-15 11-22 22-22s20 7 22 22" fill="#6d4b23"/>
      <path d="M31 52c3 4 6 6 9 6s6-2 9-6" fill="#1C222E"/>
    </svg>`;
  }

  function trophySvg() {
    return `<svg class="ap-trophy-svg" viewBox="0 0 110 110" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="trBody" x1="25" y1="14" x2="88" y2="85" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#ffe194"/>
          <stop offset="45%" stop-color="#d89e48"/>
          <stop offset="100%" stop-color="#6e4a14"/>
        </linearGradient>
        <linearGradient id="trRim" x1="28" y1="12" x2="82" y2="26" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#fff0c2"/>
          <stop offset="100%" stop-color="#b47e28"/>
        </linearGradient>
        <linearGradient id="trBase" x1="34" y1="82" x2="76" y2="104" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#273042"/>
          <stop offset="100%" stop-color="#11151E"/>
        </linearGradient>
      </defs>
      <g transform="rotate(-10 55 55)">
        <path d="M27 26c-11 0-16 8-13 18 2 7 9 12 17 12" stroke="url(#trBody)" stroke-width="6.5" stroke-linecap="round"/>
        <path d="M83 26c11 0 16 8 13 18-2 7-9 12-17 12" stroke="url(#trBody)" stroke-width="6.5" stroke-linecap="round"/>
        <path d="M27 20h56v22c0 17-12 29-28 29S27 59 27 42V20z" fill="url(#trBody)"/>
        <ellipse cx="55" cy="20" rx="28" ry="6.5" fill="url(#trRim)"/>
        <ellipse cx="55" cy="20" rx="22" ry="4" fill="#4f360d" opacity="0.45"/>
        <rect x="49" y="68" width="12" height="16" rx="4" fill="url(#trBody)"/>
        <path d="M35 84h40l5 14H30l5-14z" fill="url(#trBase)"/>
        <path d="M38 30c2 16 6 24 11 28" stroke="#fff6d6" stroke-width="3" stroke-linecap="round" opacity="0.55"/>
      </g>
    </svg>`;
  }

  function taskDiscSvg() {
    return `<svg class="ap-disc-svg" viewBox="0 0 120 96" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="discMain" x1="12" y1="12" x2="76" y2="82" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#ffe5a3"/>
          <stop offset="55%" stop-color="#d89e48"/>
          <stop offset="100%" stop-color="#6b4815"/>
        </linearGradient>
        <linearGradient id="discSm" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#5EEAD4"/>
          <stop offset="100%" stop-color="#0F766E"/>
        </linearGradient>
      </defs>
      <circle cx="90" cy="26" r="16" fill="url(#discSm)" opacity="0.92"/>
      <path d="M88 20l-6 6 6 6M92 20l6 6-6 6" fill="#0F1218"/>
      <circle cx="76" cy="70" r="11" fill="url(#discSm)" opacity="0.72"/>
      <circle cx="42" cy="48" r="34" fill="url(#discMain)"/>
      <circle cx="42" cy="48" r="32" stroke="#fff1c4" stroke-opacity="0.4" stroke-width="1.5"/>
      <path d="M39 36l-13 12 13 12V36zM45 36l13 12-13 12V36z" fill="#11151E"/>
    </svg>`;
  }

  function miniAvatar(bg, shirt, avatarUrl) {
    if (avatarUrl) {
      return `<span class="ap-mini-av" style="background:${bg || '#283327'}"><img src="${esc(avatarUrl)}" alt="" style="width:100%;height:100%;object-fit:cover;"></span>`;
    }
    return `<span class="ap-mini-av" style="background:${bg || '#283327'}"><svg viewBox="0 0 32 32"><circle cx="16" cy="12" r="5.5" fill="#e2e5dd"/><path d="M6 30c1-7 5-10 10-10s9 3 10 10" fill="${shirt || '#5b8a47'}"/></svg></span>`;
  }

  function renderCard(cfgAthlete, opts) {
    const o = opts || {};
    const L = o.lang || 'ru';
    const a = merge(cfgAthlete, o.live);
    const week = buildWeek(L, o.doneDates);
    const friendsList = o.friends || getFriends(cfgAthlete);
    const hasCustomFriends = localStorage.getItem('athleteFriends') !== null || (cfgAthlete && Array.isArray(cfgAthlete.friends));
    const onlineCount = hasCustomFriends ? friendsList.filter(f => f.online).length : (a.friendsOnline ?? friendsList.filter(f => f.online).length);
    const friendsTitle = L === 'ru' ? (a.friendsLabelRu || DEFAULTS.friendsLabelRu) : (a.friendsLabelEn || DEFAULTS.friendsLabelEn);
    const streakTitle = L === 'ru' ? (a.streakTitleRu || DEFAULTS.streakTitleRu) : (a.streakTitleEn || DEFAULTS.streakTitleEn);
    const streakSubTpl = L === 'ru' ? (a.streakSubRu || DEFAULTS.streakSubRu) : (a.streakSubEn || DEFAULTS.streakSubEn);
    const streakSub = streakSubTpl.replace('{n}', String(a.streakDays || 0));
    const taskTitle = L === 'ru' ? (a.taskTitleRu || DEFAULTS.taskTitleRu) : (a.taskTitleEn || DEFAULTS.taskTitleEn);
    const taskSub = L === 'ru' ? (a.taskSubRu || DEFAULTS.taskSubRu) : (a.taskSubEn || DEFAULTS.taskSubEn);

    const lblStat1 = L === 'ru' ? 'Цель/Готово' : 'Win/Goal';
    const lblStat2 = L === 'ru' ? 'Уровень' : 'Level';
    const lblStat3 = L === 'ru' ? 'Дней' : 'Days';
    const onlineTxt = L === 'ru' ? `${onlineCount} онлайн · ${friendsList.length}` : `${onlineCount} online · ${friendsList.length}`;

    const avatarHtml = a.avatar
      ? `<img src="${esc(a.avatar)}" alt="${esc(a.name)}">`
      : defaultAvatarSvg();

    const unreadCount = o.preview ? 1 : getUnreadNotifCount({ lang: L, hist: o.hist, cfgAthlete });
    const streakProgress = Math.min(6, Math.max(1, Math.round(((a.streakDays || 1) % 7) || 4)));

    return `
    <section class="ap-shell ${o.preview ? 'ap-preview' : ''}">
      <div class="ap-topbar">
        <div class="ap-top-icons">
          <button type="button" class="ap-icon-btn" data-ap-action="settings" title="${L === 'ru' ? 'Настроить профиль' : 'Profile settings'}" aria-label="Settings">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
          </button>
          <button type="button" class="ap-icon-btn ap-bell" data-ap-action="notify" title="${L === 'ru' ? 'Уведомления' : 'Notifications'}" aria-label="Notifications">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 0 0 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
            ${unreadCount > 0 ? `<span class="ap-notif-badge">${unreadCount > 9 ? '9+' : unreadCount}</span>` : ''}
          </button>
        </div>
        <div class="ap-balance-pill" data-ap-action="points">
          <span class="ap-coin-ic">
            <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8.5" fill="var(--ac)"/><path d="M8.5 6.5L5.5 10l3 3.5V6.5zM11.5 6.5l3 3.5-3 3.5V6.5z" fill="#111"/></svg>
          </span>
          <b class="ap-balance-val">${esc(formatPoints(a.points))}</b>
          <span class="ap-plus-ic">+</span>
        </div>
      </div>

      <div class="ap-hero">
        <div class="ap-avatar-ring" data-ap-action="settings" style="cursor:pointer" title="${L === 'ru' ? 'Нажмите, чтобы изменить фото' : 'Tap to change photo'}">
          <div class="ap-avatar-inner">${avatarHtml}</div>
        </div>
        <h2 class="ap-name">${esc(a.name)}</h2>
        <div class="ap-handle">${esc(a.handle)}</div>
      </div>

      <div class="ap-stats-bar">
        <div class="ap-stat-col">
          <div class="ap-stat-top">
            <span class="ap-st-ic">
              <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="var(--ac)" stroke-width="2.4"/><path d="M10 5a5 5 0 1 1-3.5 8.5" stroke="var(--ac)" stroke-width="2" stroke-linecap="round"/></svg>
            </span>
            <b>${esc(a.winRate)}%</b>
          </div>
          <small>${esc(lblStat1)}</small>
        </div>
        <div class="ap-stat-col">
          <div class="ap-stat-top">
            <span class="ap-st-ic">
              <svg viewBox="0 0 20 20" fill="none"><path d="M10 2l2.1 1.7 2.7-.2.9 2.5 2.3 1.4-.7 2.6.7 2.6-2.3 1.4-.9 2.5-2.7-.2L10 18l-2.1-1.7-2.7.2-.9-2.5L2 12.6l.7-2.6L2 7.4 4.3 6l.9-2.5 2.7.2L10 2z" fill="var(--ac)"/><path d="M7.2 10.2l1.8 1.8 3.8-4" stroke="#111" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </span>
            <b>${esc(a.level)}</b>
          </div>
          <small>${esc(lblStat2)}</small>
        </div>
        <div class="ap-stat-col">
          <div class="ap-stat-top">
            <span class="ap-st-ic">
              <svg viewBox="0 0 20 20" fill="none"><rect x="3" y="4" width="14" height="13" rx="3" fill="var(--ac)"/><path d="M6 2.5v3M14 2.5v3M6 9h8M6 12.5h5" stroke="#111" stroke-width="1.8" stroke-linecap="round"/></svg>
            </span>
            <b>${esc(a.days)}</b>
          </div>
          <small>${esc(lblStat3)}</small>
        </div>
      </div>

      <div class="ap-week-strip">
        ${week.map(d => `
          <div class="ap-day ${d.isToday ? 'today' : ''} ${d.isDone ? 'done' : ''}">
            <div class="ap-day-dots">
              ${d.isToday ? '<i class="on"></i><i></i><i></i>' : `<i class="${d.isDone ? 'on' : ''}"></i>`}
            </div>
            <span class="ap-day-lbl">${esc(d.label)}</span>
            <b class="ap-day-num">${d.num}</b>
          </div>
        `).join('')}
      </div>

      <div class="ap-bento">
        <div class="ap-bento-card ap-friends-card" data-ap-action="friends">
          <div class="ap-av-stack">
            ${(friendsList.length ? friendsList.slice(0, 3) : DEFAULT_FRIENDS.slice(0, 3)).map(f => miniAvatar(f.color, f.shirt, f.avatar)).join('')}
          </div>
          <div class="ap-bento-title">${esc(friendsTitle)}</div>
          <div class="ap-bento-green">${esc(onlineTxt)}</div>
        </div>

        <div class="ap-bento-card ap-streak-card" data-ap-action="streak">
          <div class="ap-streak-copy">
            <div class="ap-bento-title">${esc(streakTitle)}</div>
            <div class="ap-bento-muted">${esc(streakSub)}</div>
            <div class="ap-progress-dots">
              ${[0, 1, 2, 3, 4, 5].map(idx => {
                if (idx === streakProgress) return `<span class="ap-pdot check">✓</span>`;
                if (idx < streakProgress) return `<span class="ap-pdot lit"></span>`;
                return `<span class="ap-pdot"></span>`;
              }).join('')}
            </div>
          </div>
          ${trophySvg()}
        </div>
      </div>

      <div class="ap-task-banner" data-ap-action="tasks">
        <div class="ap-task-visual">${taskDiscSvg()}</div>
        <div class="ap-task-copy">
          <div class="ap-bento-title">${esc(taskTitle)}</div>
          <div class="ap-bento-muted">${esc(taskSub)}</div>
        </div>
      </div>
    </section>`;
  }

  window.AthleteProfile = {
    DEFAULTS,
    DEFAULT_FRIENDS,
    SUGGESTED_FRIENDS,
    QUEST_TEMPLATES,
    getFriends,
    saveFriends,
    getDuels,
    saveDuels,
    getDuelStats,
    startDuel,
    calcMyDuelScore,
    calcRivalDuelScore,
    addDuelBonus,
    claimDuel,
    getQuest,
    saveQuest,
    getQuestStats,
    startQuest,
    calcQuestProgress,
    claimQuest,
    formatDuelLeft,
    miniAvatar,
    getFreezeState,
    saveFreezeState,
    useFreezeOnDate,
    buyFreezeToken,
    calcStreakSimple,
    getNotifPrefs,
    saveNotifPrefs,
    getReadNotifs,
    markNotifsRead,
    buildNotifications,
    getUnreadNotifCount,
    merge,
    renderCard
  };
})();

