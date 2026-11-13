import re
# ---------- texts ----------
p = r'd:\RENEROVKA\site\texts.js'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')
s += '''Object.assign(window.TEXTS.ru, { coach: 'AI', coachTitle: 'Спроси AI-тренера', coachSub: 'Планы тренировок, техника, питание и восстановление — персональные советы за секунды.', coachPh: 'Напишите сообщение…', coachOff: 'AI-тренер пока не подключён. Администратор может включить его в админке.', coachHi: 'Привет! 👋 Я твой AI-тренер. Какая у тебя главная цель сегодня?', coachBanner: 'Спроси AI-тренера', coachClear: 'Очистить чат', c1: 'Составь план тренировок для похудения', c2: 'Как быстрее нарастить мышцы?', c3: 'Как улучшить сон и восстановление?', c4: 'Что делать новичку в зале?', coachTyping: 'печатает…' });
Object.assign(window.TEXTS.en, { coach: 'AI', coachTitle: 'Ask Your AI Coach', coachSub: 'Workout plans, technique, nutrition and recovery — personal advice in seconds.', coachPh: 'Type your message…', coachOff: 'The AI coach is not connected yet. The admin can enable it in the admin panel.', coachHi: "Hi! 👋 I'm your AI coach. What's your main goal today?", coachBanner: 'Ask your AI coach', coachClear: 'Clear chat', c1: 'Create a workout plan for weight loss', c2: 'How to build muscle faster?', c3: 'How to improve my sleep & recovery?', c4: "What should a beginner do at the gym?", coachTyping: 'typing…' });
'''
open(p, 'w', encoding='utf-8', newline='').write(s)

# ---------- index nav ----------
p = r'd:\RENEROVKA\site\index.html'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')
s = s.replace('  <a href="#/exercises"', '  <a href="#/coach" data-k="coach" data-i="coach"><i>🤖</i><b></b></a>\n  <a href="#/exercises"', 1)
open(p, 'w', encoding='utf-8', newline='').write(s)

# ---------- app.js ----------
p = r'd:\RENEROVKA\site\app.js'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')
s = s.replace("  let L = localStorage.lang || 'ru';\n",
 "  let L = localStorage.lang || 'ru';\n  const COACH = await fetch('/api/coach/status').then(r => r.json()).catch(() => ({ enabled: false }));\n", 1)
s = s.replace("    (CFG.hidden || []).forEach(k =>", "    if (!COACH.enabled) (CFG.hidden = (CFG.hidden || []).concat('coach'));\n    (CFG.hidden || []).forEach(k =>", 1)

coach_route = r'''    coach() {
      if (!COACH.enabled) return `<h1>🤖 ${esc(t('coachTitle'))}</h1><div class="empty">${esc(t('coachOff'))}</div>`;
      return `<div class="chat"><div class="chat-head"><div class="orb"><span>AI</span></div><h1>${esc(t('coachTitle'))}</h1><p>${esc(t('coachSub'))}</p></div>
      <div class="chips" id="chips">${['c1', 'c2', 'c3', 'c4'].map(k => `<button class="chip2" data-q="${esc(t(k))}">${esc(t(k))}</button>`).join('')}</div>
      <div class="msgs" id="msgs"></div>
      <form class="composer" id="cform"><input id="cin" placeholder="${esc(t('coachPh'))}" autocomplete="off" maxlength="1000"><button class="send" aria-label="send">➤</button></form>
      <p style="text-align:center"><button class="btn alt" id="cclr" style="padding:6px 14px;font-size:12px">${esc(t('coachClear'))}</button></p></div>`;
    },
'''
s = s.replace("    programs() {", coach_route + "    programs() {", 1)

coach_js = r'''    if (name == 'coach' && COACH.enabled) {
      const box = document.getElementById('msgs'), inp = document.getElementById('cin');
      let hist2 = JSON.parse(localStorage.coach || '[]'), busy = false;
      const md = x => esc(x)
        .replace(/\[\[(program|workout|exercise):(\d+)\|([^\]]+)\]\]/g, (m, k, id, nm) => `<a class="ref" href="#/${k}/${id}">${nm}</a>`)
        .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
        .replace(/^\s*[*-] /gm, '• ')
        .replace(/\n/g, '<br>');
      const bubble = (role, text) => `<div class="m ${role}"><div class="mb">${role == 'model' ? md(text) : esc(text).replace(/\n/g, '<br>')}</div></div>`;
      const draw = () => { box.innerHTML = bubble('model', t('coachHi')) + hist2.map(m => bubble(m.role, m.text)).join(''); window.scrollTo(0, document.body.scrollHeight); };
      const send = async q => {
        q = (q || '').trim(); if (!q || busy) return; busy = true; inp.value = '';
        hist2.push({ role: 'user', text: q }); draw();
        box.insertAdjacentHTML('beforeend', `<div class="m model" id="typ"><div class="mb typing"><i></i><i></i><i></i></div></div>`); window.scrollTo(0, document.body.scrollHeight);
        try {
          const r = await fetch('/api/coach', { method: 'POST', body: JSON.stringify({ messages: hist2.slice(-12) }) });
          const j = await r.json();
          hist2.push({ role: 'model', text: r.ok ? j.reply : '⚠️ ' + (j.error || 'Error') });
        } catch (e) { hist2.push({ role: 'model', text: '⚠️ ' + (L == 'ru' ? 'Нет связи с сервером' : 'Connection error') }); }
        hist2 = hist2.slice(-30); localStorage.coach = JSON.stringify(hist2); busy = false; draw();
      };
      document.getElementById('cform').onsubmit = e => { e.preventDefault(); send(inp.value); };
      document.querySelectorAll('.chip2').forEach(b => b.onclick = () => send(b.dataset.q));
      document.getElementById('cclr').onclick = () => { hist2 = []; localStorage.coach = '[]'; draw(); };
      draw(); window.scrollTo(0, 0);
    }
'''
s = s.replace("    if (name == 'workout') {", coach_js + "    if (name == 'workout') {", 1)

s = s.replace("      ${on('activity') ?",
 "      ${COACH.enabled ? `<a class=\"coachcard\" href=\"#/coach\"><div class=\"orb sm\"><span>AI</span></div><div><b>${esc(t('coachBanner'))}</b><small>${esc(t('coachSub'))}</small></div><span class=\"go\">›</span></a>` : ''}\n      ${on('activity') ?", 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
