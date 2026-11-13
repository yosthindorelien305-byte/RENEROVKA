with open('site/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Define getExVideo and renderExVisual right after exImg
ex_img_str = "  const exImg = (e, c) => e.img ? `<img src=\"img/ex/svg_norm_${e.id}.svg\" alt=\"\">` : '';"
helpers = """  const exImg = (e, c) => e.img ? `<img src=\"img/ex/svg_norm_${e.id}.svg\" alt=\"\">` : '';

  const getExVideo = e => {
    if (!e) return null;
    const m = (window.FITIFY_EX_MAP || {})[String(e.id)];
    return m ? m.video : null;
  };

  const renderExVisual = (e, options = {}) => {
    if (!e) return '💪';
    const vid = getExVideo(e);
    const preferVideo = localStorage.getItem('flexa_view_mode') !== 'schema';
    const hasVideo = !!vid;

    if (hasVideo && (options.forceVideo || preferVideo)) {
      return `
        <div class="ex-visual-wrap video-active" data-id="${e.id}">
          <video class="ex-video-elem" src="${vid}" autoplay loop muted playsinline poster="${e.img ? `img/ex/svg_norm_${e.id}.svg` : ''}"></video>
          ${options.allowToggle ? `
            <div class="ex-visual-switcher">
              <button class="visual-toggle-btn active" data-mode="video" title="${L == 'ru' ? '3D Видео' : '3D Video'}">📹 3D</button>
              <button class="visual-toggle-btn" data-mode="schema" title="${L == 'ru' ? 'Схема' : 'Schema'}">🖼️</button>
            </div>` : ''}
        </div>`;
    }

    return `
      <div class="ex-visual-wrap schema-active" data-id="${e.id}">
        ${e.img ? `<img class="ex-img-elem" src="img/ex/svg_norm_${e.id}.svg" alt="">` : '💪'}
        ${hasVideo && options.allowToggle ? `
          <div class="ex-visual-switcher">
            <button class="visual-toggle-btn" data-mode="video" title="${L == 'ru' ? '3D Видео' : '3D Video'}">📹 3D</button>
            <button class="visual-toggle-btn active" data-mode="schema" title="${L == 'ru' ? 'Схема' : 'Schema'}">🖼️</button>
          </div>` : ''}
      </div>`;
  };"""

if ex_img_str in code:
    code = code.replace(ex_img_str, helpers, 1)
    print('Added getExVideo and renderExVisual!')
else:
    print('Could not find exImg string!')

# 2. Update exercise(id) view
old_ex_view = '<div class="ex-img ${e.img ? \'\' : \'none\'}" style="border-radius:16px">${e.img ? exImg(e) : \'💪\'}</div>'
new_ex_view = '<div class="ex-img ${e.img ? \'\' : \'none\'}" style="border-radius:20px;overflow:hidden;position:relative;">${renderExVisual(e, { allowToggle: true })}</div>'

if old_ex_view in code:
    code = code.replace(old_ex_view, new_ex_view, 1)
    print('Updated exercise detail view!')
else:
    print('Could not find old_ex_view string!')

# 3. Update workout player technique card
old_p_card = """            <div class="p-technique-card">
              ${e && e.img ? `<img src="img/ex/svg_norm_${e.id}.svg" alt="">` : '💪'}
            </div>"""

new_p_card = """            <div class="p-technique-card">
              ${renderExVisual(e, { allowToggle: true, forceVideo: true })}
            </div>"""

if old_p_card in code:
    code = code.replace(old_p_card, new_p_card, 1)
    print('Updated workout player technique card!')
else:
    print('Could not find old_p_card string!')

# 4. Update exerciseCard list item to show 3D badge
old_ex_card = """  exerciseCard(e) {
    return `<a class="card" href="#/exercise/${e.id}"><div class="ex-img ${e.img ? '' : 'none'}">${e.img ? exImg(e) : '💪'}</div><div class="b"><h3>${esc(exName(e))}</h3><div class="tags"><span class="tag">${eqLbl(e.eq)}</span>${e.rating ? `<span class="tag star">★ ${e.rating}</span>` : ''}</div></div></a>`;
  }"""

new_ex_card = """  exerciseCard(e) {
    const hasVid = !!getExVideo(e);
    return `<a class="card" href="#/exercise/${e.id}">
      <div class="ex-img ${e.img ? '' : 'none'}">${e.img ? exImg(e) : '💪'}</div>
      <div class="b">
        <h3>${esc(exName(e))}</h3>
        <div class="tags">
          <span class="tag">${eqLbl(e.eq)}</span>
          ${hasVid ? `<span class="tag" style="background:rgba(0,230,153,0.15);color:#00e699;border:1px solid rgba(0,230,153,0.3);font-size:10px;font-weight:800;">📹 3D</span>` : ''}
          ${e.rating ? `<span class="tag star">★ ${e.rating}</span>` : ''}
        </div>
      </div>
    </a>`;
  }"""

if old_ex_card in code:
    code = code.replace(old_ex_card, new_ex_card, 1)
    print('Updated exerciseCard with 3D badge!')
else:
    print('Could not find old_ex_card string!')

# 5. Add global click delegate for visual-toggle-btn
click_delegate = """
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
"""

if 'window.addEventListener(\'hashchange\', render);' in code:
    code = code.replace('window.addEventListener(\'hashchange\', render);', click_delegate + '\n  window.addEventListener(\'hashchange\', render);', 1)
    print('Added click delegate for visual-toggle-btn!')
else:
    print('Could not find hashchange event listener!')

with open('site/app.js', 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated site/app.js with 3D Video features successfully!')
