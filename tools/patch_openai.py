p = r'd:\RENEROVKA\server.py'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')

s = s.replace("AI_DEFAULT = {'key': '', 'model': 'gemini-3.8-flash', 'enabled': True, 'prompt': ''}",
              "AI_DEFAULT = {'provider': 'gemini', 'base_url': '', 'key': '', 'model': 'gemini-3.8-flash', 'enabled': True, 'prompt': ''}")

# split ask_gemini into prompt builder + providers
a = s.index('def ask_gemini(')
b = s.index('\nclass H(SimpleHTTPRequestHandler):')
new = '''def build_system(brand):
    cfg = ai_cfg()
    system = SYSTEM.format(brand=brand) + catalog()
    if cfg.get('prompt'):
        system += '\\n\\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ ВЛАДЕЛЬЦА САЙТА:\\n' + cfg['prompt'][:2000]
    return system

def http_json(req, timeout=40):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = ''
        try:
            j = json.load(e)
            err = j.get('error', j)
            detail = err.get('message', '') if isinstance(err, dict) else str(err)
        except Exception:
            pass
        raise RuntimeError('Ошибка AI-провайдера (%s): %s' % (e.code, detail[:200]))
    except urllib.error.URLError as e:
        raise RuntimeError('Не удалось подключиться к AI-провайдеру: %s' % e.reason)

def ask_gemini(messages, brand, extra):
    cfg = ai_cfg()
    body = {
        'systemInstruction': {'parts': [{'text': build_system(brand)}]},
        'contents': [{'role': m['role'], 'parts': [{'text': m['text']}]} for m in messages],
        'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 900},
    }
    model = re.sub(r'[^a-zA-Z0-9._-]', '', cfg.get('model') or 'gemini-3.8-flash')
    req = urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent' % model,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': cfg['key']})
    j = http_json(req)
    try:
        return ''.join(pt.get('text', '') for pt in j['candidates'][0]['content']['parts']).strip() or '…'
    except Exception:
        raise RuntimeError('Пустой ответ модели (возможно, сработал фильтр безопасности)')

def ask_openai(messages, brand, extra):
    """Any OpenAI-compatible /chat/completions endpoint (OpenAI, OpenRouter, Groq, DeepSeek, Ollama, LM Studio...)."""
    cfg = ai_cfg()
    base = (cfg.get('base_url') or '').strip().rstrip('/')
    if not re.match(r'^https?://', base):
        raise RuntimeError('Укажите Base URL провайдера (например https://api.openai.com/v1)')
    msgs = [{'role': 'system', 'content': build_system(brand)}] + [
        {'role': 'assistant' if m['role'] == 'model' else 'user', 'content': m['text']} for m in messages]
    body = {'model': cfg.get('model'), 'messages': msgs, 'temperature': 0.7, 'max_tokens': 900}
    headers = {'Content-Type': 'application/json'}
    if cfg.get('key'):
        headers['Authorization'] = 'Bearer ' + cfg['key']
    j = http_json(urllib.request.Request(base + '/chat/completions', data=json.dumps(body).encode(), headers=headers), timeout=90)
    try:
        return (j['choices'][0]['message']['content'] or '').strip() or '…'
    except Exception:
        raise RuntimeError('Пустой ответ модели')

def ai_ready(c):
    if not c.get('enabled'):
        return False
    if c.get('provider') == 'openai':
        return bool((c.get('base_url') or '').strip()) and bool(c.get('model'))
    return bool(c.get('key'))

def ask_ai(messages, brand, extra):
    c = ai_cfg()
    if not ai_ready(c):
        raise RuntimeError('AI-тренер не настроен администратором')
    return (ask_openai if c.get('provider') == 'openai' else ask_gemini)(messages, brand, extra)
'''
s = s[:a] + new + s[b:]

s = s.replace("return self.send_j(200, {'enabled': bool(c.get('key')) and bool(c.get('enabled'))})",
              "return self.send_j(200, {'enabled': ai_ready(c)})")
s = s.replace("return self.send_j(200, {'hasKey': bool(c.get('key')), 'keyHint': ('…' + c['key'][-4:]) if c.get('key') else '', 'model': c['model'], 'enabled': c['enabled'], 'prompt': c.get('prompt', '')})",
              "return self.send_j(200, {'provider': c['provider'], 'baseUrl': c.get('base_url', ''), 'hasKey': bool(c.get('key')), 'keyHint': ('…' + c['key'][-4:]) if c.get('key') else '', 'model': c['model'], 'enabled': c['enabled'], 'prompt': c.get('prompt', '')})")
s = s.replace("ask_gemini(msgs, brand, None)})", "ask_ai(msgs, brand, None)})")
s = s.replace("            c['model'] = re.sub(r'[^a-zA-Z0-9._-]', '', str(j.get('model') or c['model'])) or AI_DEFAULT['model']",
"""            c['provider'] = 'openai' if j.get('provider') == 'openai' else 'gemini'
            bu = str(j.get('baseUrl', '')).strip()
            if bu and not re.match(r'^https?://', bu):
                return self.send_j(400, {'error': 'Base URL должен начинаться с http:// или https://'})
            c['base_url'] = bu
            c['model'] = re.sub(r'[^a-zA-Z0-9._:/-]', '', str(j.get('model') or c['model'])) or AI_DEFAULT['model']""")
open(p, 'w', encoding='utf-8', newline='').write(s)

# ---------- admin ----------
p = r'd:\RENEROVKA\site\admin.js'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')
a = s.index('  async function tabAI(el) {')
b = s.index('  // ---------- tab: settings')
ai = r'''  async function tabAI(el) {
    let c = {};
    try { c = await api('ai/settings'); } catch (e) { return toast(e.message, 1); }
    const PRESETS = [['OpenAI', 'https://api.openai.com/v1', 'gpt-4o-mini'], ['OpenRouter', 'https://openrouter.ai/api/v1', 'meta-llama/llama-3.3-70b-instruct'], ['Groq', 'https://api.groq.com/openai/v1', 'llama-3.3-70b-versatile'], ['DeepSeek', 'https://api.deepseek.com/v1', 'deepseek-chat'], ['Ollama (локально)', 'http://localhost:11434/v1', 'llama3.2']];
    el.innerHTML = `<div class="box"><h2 style="margin-top:0">AI-тренер</h2>
      <label class="f">Провайдер<select id="ai-prov"><option value="openai" ${c.provider == 'openai' ? 'selected' : ''}>OpenAI-совместимый (OpenAI, OpenRouter, Groq, DeepSeek, Ollama…)</option><option value="gemini" ${c.provider != 'openai' ? 'selected' : ''}>Google Gemini (доступен не во всех регионах)</option></select></label>
      <div id="ai-presets" class="up" style="margin-bottom:12px">${PRESETS.map((p, i) => `<button type="button" class="btn alt" style="padding:6px 12px;font-size:12px" data-p="${i}">${p[0]}</button>`).join('')}</div>
      <label class="f" id="ai-bu-w">Base URL<input id="ai-bu" value="${esc(c.baseUrl)}" placeholder="https://api.openai.com/v1"></label>
      <p>Статус ключа: <b style="color:${c.hasKey ? 'var(--ac)' : 'var(--mut)'}">${c.hasKey ? 'сохранён (' + esc(c.keyHint) + ')' : 'не задан'}</b></p>
      <label class="f">API-ключ (пусто = не менять; для локального Ollama ключ не нужен)<input id="ai-key" type="password" autocomplete="off"></label>
      <label class="f">Модель<input id="ai-model" value="${esc(c.model)}"></label>
      <label class="chk"><input type="checkbox" id="ai-on" ${c.enabled ? 'checked' : ''}> Показывать AI-тренера на сайте</label>
      <label class="f" style="margin-top:12px">Дополнительные инструкции тренеру (тон, ограничения, акценты)<textarea id="ai-prompt" rows="5">${esc(c.prompt)}</textarea></label>
      <p style="color:var(--mut);font-size:12px">Ключ хранится только на сервере и не отправляется в браузер посетителей. Используйте тот провайдер, который доступен в вашем регионе и по его правилам.</p>
      <div class="up"><button class="btn" id="ai-save" style="animation:none">💾 Сохранить</button>${c.hasKey ? '<button class="btn alt" id="ai-clr">Удалить ключ</button>' : ''}</div></div>`;
    const sync = () => { $('#ai-bu-w').style.display = $('#ai-prov').value == 'openai' ? '' : 'none'; $('#ai-presets').style.display = $('#ai-prov').value == 'openai' ? '' : 'none'; };
    $('#ai-prov').onchange = () => { sync(); if ($('#ai-prov').value == 'gemini' && !/gemini/.test($('#ai-model').value)) $('#ai-model').value = 'gemini-3.8-flash'; };
    $$('[data-p]').forEach(b => b.onclick = () => { const p = PRESETS[b.dataset.p]; $('#ai-bu').value = p[1]; $('#ai-model').value = p[2]; });
    sync();
    const save = async extra => {
      try { await post('ai/settings', Object.assign({ provider: $('#ai-prov').value, baseUrl: $('#ai-bu').value, key: $('#ai-key').value, model: $('#ai-model').value, enabled: $('#ai-on').checked, prompt: $('#ai-prompt').value }, extra || {})); toast('Сохранено ✓'); tabAI(el); } catch (e) { toast(e.message, 1); }
    };
    $('#ai-save').onclick = () => save();
    const cl = $('#ai-clr'); if (cl) cl.onclick = () => confirm('Удалить ключ?') && save({ clearKey: true, key: '' });
  }

'''
s = s[:a] + ai + s[b:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched')
