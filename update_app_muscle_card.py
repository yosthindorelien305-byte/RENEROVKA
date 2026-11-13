with open('site/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

new_render_muscle = """  function renderMuscleCard(w) {
    const text = ((w.t && (w.t.ru || w.t.en)) || '') + ' ' + ((w.d && (w.d.ru || w.d.en)) || '') + ' ' +
      (w.s || []).map(s => s.slice(1).map(n => {
        const e = exMap[n[0]];
        return e ? (e.n.ru + ' ' + e.n.en) : '';
      }).join(' ')).join(' ');
    const m = {
      chest: /груд|отжим|pushup|chest|dips|брусь/i.test(text),
      back: /спин|подтягив|тяг|pullup|chinup|back|lats/i.test(text),
      abs: /пресс|живот|кор|abs|core|plank|планк|скручив/i.test(text),
      arms: /рук|бицеп|трицеп|arm|bicep|tricep|curl/i.test(text),
      shoulders: /плеч|дельт|shoulder|pike|handstand/i.test(text),
      legs: /ног|присед|выпад|leg|squat|lunge|calf|икр|бедр/i.test(text)
    };
    const hasAny = Object.values(m).some(Boolean);
    if (!hasAny) m.arms = m.chest = true;
    const labels = {
      chest: L == 'ru' ? 'Грудь' : 'Chest',
      back: L == 'ru' ? 'Спина' : 'Back',
      abs: L == 'ru' ? 'Пресс / Кор' : 'Core / Abs',
      arms: L == 'ru' ? 'Руки' : 'Arms',
      shoulders: L == 'ru' ? 'Плечи' : 'Shoulders',
      legs: L == 'ru' ? 'Ноги' : 'Legs'
    };

    const frontSvg = window.FITIFY_FRONT_SVG || '';
    const backSvg = window.FITIFY_BACK_SVG || '';

    return `
    <div class="fitify-mannequin-card" id="m3d-box" data-muscles='${JSON.stringify(m)}'>
      <div class="m3d-header">
        <div class="m3d-title">💀 ${L == 'ru' ? 'Целевые группы мышц' : 'Target Muscle Groups'}</div>
        <a href="fitify/muscles.html" class="m3d-link-map" style="font-size:12px;color:#00e699;text-decoration:none;font-weight:700;">${L == 'ru' ? 'Полная карта 3D ↗' : 'Full 3D Map ↗'}</a>
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
  }"""

start_tag = '  function renderMuscleCard(w) {'
end_tag = '  const routes = {'
idx_start = code.find(start_tag)
idx_end = code.find(end_tag, idx_start)

if idx_start != -1 and idx_end != -1:
    code = code[:idx_start] + new_render_muscle + '\n\n  ' + code[idx_end:]
    with open('site/app.js', 'w', encoding='utf-8') as f:
        f.write(code)
    print('Updated renderMuscleCard in site/app.js successfully!')
else:
    print('Failed to find tags:', idx_start, idx_end)
