with open('site/admin.js', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update loadAll() and effE
old_load = """    OV = Object.assign({ w: {}, p: {}, c: [] }, o || {});
  }

  const saveCfg = () => post('save?file=config', CFG);
  const saveOv = () => post('save?file=overrides', OV);

  const exMap = {};
  const exName = e => e.n.ru || e.n.en || '#' + e.id;
  const effP = id => Object.assign({}, D.programs.find(p => p.id == id), OV.p[id] || {});
  const effW = id => OV.c.find(w => w.id == id) || Object.assign({}, D.workouts.find(w => w.id == id), OV.w[id] || {});"""

new_load = """    OV = Object.assign({ w: {}, p: {}, c: [], e: {} }, o || {});
    OV.e = OV.e || {};
  }

  const saveCfg = () => post('save?file=config', CFG);
  const saveOv = () => post('save?file=overrides', OV);

  const exMap = {};
  const exName = e => e.n.ru || e.n.en || '#' + e.id;
  const effP = id => Object.assign({}, D.programs.find(p => p.id == id), OV.p[id] || {});
  const effW = id => OV.c.find(w => w.id == id) || Object.assign({}, D.workouts.find(w => w.id == id), OV.w[id] || {});
  const effE = id => Object.assign({}, D.exercises.find(e => e.id == id), (OV.e || {})[id] || {});"""

if old_load in code:
    code = code.replace(old_load, new_load, 1)
    print('Updated loadAll and effE!')
else:
    print('Could not find old_load!')

# 2. Update shell tabs
old_shell_tabs = """    <div class="wrap"><div class="tabs">${[
      ['ui', '🎨 Интерфейс'],
      ['programs', '📋 Программы'],
      ['workouts', '🏋️ Тренировки'],
      ['ai', '🤖 AI-тренер'],
      ['settings', '⚙️ Настройки']
    ].map(([k, n]) => `<button data-t="${k}" class="${tab == k ? 'on' : ''}">${n}</button>`).join('')}</div><div id="tabc"></div></div>`;

    $('#lo').onclick = () => { token = ''; sessionStorage.removeItem('atok'); showLogin(); };
    $$('.tabs button').forEach(b => b.onclick = () => { tab = b.dataset.t; sub = null; shell(); });

    const tabs = { ui: tabUI, programs: tabPrograms, workouts: tabWorkouts, ai: tabAI, settings: tabSettings };"""

new_shell_tabs = """    <div class="wrap"><div class="tabs">${[
      ['ui', '🎨 Интерфейс'],
      ['programs', '📋 Программы'],
      ['workouts', '🏋️ Тренировки'],
      ['exercises', '🤸 Упражнения & Видео'],
      ['ai', '🤖 AI-тренер'],
      ['settings', '⚙️ Настройки']
    ].map(([k, n]) => `<button data-t="${k}" class="${tab == k ? 'on' : ''}">${n}</button>`).join('')}</div><div id="tabc"></div></div>`;

    $('#lo').onclick = () => { token = ''; sessionStorage.removeItem('atok'); showLogin(); };
    $$('.tabs button').forEach(b => b.onclick = () => { tab = b.dataset.t; sub = null; shell(); });

    const tabs = { ui: tabUI, programs: tabPrograms, workouts: tabWorkouts, exercises: tabExercises, ai: tabAI, settings: tabSettings };"""

if old_shell_tabs in code:
    code = code.replace(old_shell_tabs, new_shell_tabs, 1)
    print('Updated shell tabs to include exercises!')
else:
    print('Could not find old_shell_tabs!')

# 3. Add tabExercises before tabAI
target_ai = '  // ---------- tab: ai ----------'
tab_exercises_code = """  // ---------- tab: exercises ----------
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

          <div class="box" style="background:rgba(0,0,0,0.25);border:1px solid rgba(0,230,153,0.3);border-radius:16px;margin-bottom:20px;padding:18px;">
            <h3 style="margin-top:0;display:flex;align-items:center;gap:8px;color:#00e699;">📹 Видео / Анимация упражнения</h3>
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
                  ${e.video ? '<span style="background:rgba(0,230,153,0.2);color:#00e699;border:1px solid rgba(0,230,153,0.3);padding:1px 6px;border-radius:6px;font-size:10px;font-weight:800;">📹 Видео подключено</span>' : '<span style="color:var(--mut);font-size:10px;">Без видео (схема)</span>'}
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

"""

if target_ai in code:
    code = code.replace(target_ai, tab_exercises_code + target_ai, 1)
    print('Inserted tabExercises before tabAI!')
else:
    print('Could not find target_ai string!')

with open('site/admin.js', 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated site/admin.js successfully!')
