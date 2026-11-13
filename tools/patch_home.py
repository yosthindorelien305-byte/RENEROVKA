p = r'd:\RENEROVKA\site\app.js'
s = open(p, encoding='utf-8', newline='').read()
a = s.index("      const star = D.programs")
b = s.index("    },\n    programs()")
new = r'''      const S = CFG.sections || {};
      const on = k => S[k] !== false;
      const star = D.programs.filter(p => p.img).slice(0, 6);
      const top = D.workouts.filter(w => w.t.ru || w.t.en).sort((a, b) => b.rating - a.rating).slice(0, 10);
      const wk = Date.now() - 7 * 864e5, h = hist().filter(x => x.t > wk);
      const goal = Math.max(1, +CFG.goal || 5), pct = Math.min(100, Math.round(h.length / goal * 100));
      const mins = Math.round(h.reduce((s, x) => s + x.s, 0) / 60);
      const hp = D.programs.find(p => p.id == CFG.heroProgram) || D.programs.find(p => p.img) || star[0];
      const heroT = (CFG.heroTitle && CFG.heroTitle[L]) || pName(hp);
      const heroP = (CFG.heroText && CFG.heroText[L]) || t('heroP');
      const heroLink = CFG.heroLink || ('#/program/' + hp.id);
      const logo = CFG.logo || 'img/logo.svg';
      return `<div class="greet"><div class="avatar"></div><div><small>${esc(t('welcome'))}</small><b>${esc(CFG.brand)}</b></div></div>
      ${on('hero') ? `<section class="hero" style="--hero:url(${(CFG.heroImage) || pImg(hp)})"><span class="chip">✦ ${esc(t('potd'))}</span>
      <h1>${esc(heroT)}</h1><p>${esc(heroP)}</p><a class="btn" href="${esc(heroLink)}">${esc(t('startShort'))} →</a></section>` : ''}
      ${on('activity') ? `<h2>${esc(t('weekAct'))}<a href="#/history">${t('history')}</a></h2>
      <div class="activity"><div class="ring" style="--p:${pct}"><span>${pct}%</span></div><div class="mstats">
        <div class="mstat"><i>🔥</i><b>${h.length} / ${goal}</b><small>${t('workouts')}</small></div>
        <div class="mstat"><i>⏱</i><b>${mins} min</b><small>${esc(t('time'))}</small></div>
        <div class="mstat"><i>📚</i><b>${D.exercises.length}</b><small>${t('ex')}</small></div></div></div>` : ''}
      ${on('quick') ? `<h2>${esc(t('quick'))}<a href="#/workouts">${esc(t('seeAll'))}</a></h2><div class="hscroll">${top.map(workoutCard).join('')}</div>` : ''}
      ${on('featured') ? `<h2>${t('prev')}<a href="#/programs">${esc(t('seeAll'))}</a></h2><div class="grid">${star.map(programCard).join('')}</div>` : ''}`;
'''
s = s[:a] + new + s[b:]
open(p, 'w', encoding='utf-8', newline='').write(s)
