p = r'd:\RENEROVKA\server.py'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')

s = s.replace("import hashlib, hmac, json, os, re, secrets, sys, threading, time",
              "import hashlib, hmac, json, os, re, secrets, sys, threading, time, urllib.request, urllib.error")

helpers = '''
AI_FILE = os.path.join(SECRET_DIR, 'ai.json')
AI_DEFAULT = {'key': '', 'model': 'gemini-2.5-flash', 'enabled': True, 'prompt': ''}
coach_hits = {}      # ip -> [timestamps]

def ai_cfg():
    try:
        return | json.load(open(AI_FILE, encoding='utf-8'))
    except Exception:
        return dict(AI_DEFAULT)

def catalog():
    """Short catalogue so the coach can link to real workouts/programs."""
    try:
        D = json.load(open(os.path.join(SITE, 'data.json'), encoding='utf-8'))
    except Exception:
        return ''
    lines = ['PROGRAMS:']
    for p in D['programs']:
        lines.append('[[program:%s|%s]]' % (p['id'], p['t'].get('ru') or p['t'].get('en')))
    lines.append('WORKOUTS:')
    for w in D['workouts']:
        n = w['t'].get('ru') or w['t'].get('en')
        if n:
            lines.append('[[workout:%s|%s]]' % (w['id'], n))
    lines.append('EXERCISES:')
    for e in D['exercises']:
        if e.get('img') and e['n'].get('ru'):
            lines.append('[[exercise:%s|%s]]' % (e['id'], e['n']['ru']))
    return '\\n'.join(lines)

SYSTEM = (
    "Ты — дружелюбный AI-тренер фитнес-сайта {brand}. Помогаешь с тренировками, техникой упражнений, "
    "планами, восстановлением, сном и общими принципами питания. Отвечай на языке пользователя, коротко и по делу "
    "(до ~180 слов), используй списки и **жирный** для ключевого. Не ставь диагнозов; при болях, травмах, "
    "беременности и хронических болезнях советуй обратиться к врачу. Не рассуждай на темы вне фитнеса и здоровья. "
    "Когда уместно, рекомендуй реальные программы, тренировки и упражнения ИЗ КАТАЛОГА ниже и вставляй их ровно в формате "
    "[[тип:ID|название]] (тип: program, workout или exercise) — сайт превратит это в ссылку. Не выдумывай ID.\\n\\nКАТАЛОГ:\\n"
)

def ask_gemini(messages, brand, extra):
    cfg = ai_cfg()
    if not cfg.get('key'):
        raise RuntimeError('AI-тренер не настроен администратором')
    system = SYSTEM.format(brand=brand) + catalog()
    if cfg.get('prompt'):
        system += '\\n\\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ ВЛАДЕЛЬЦА САЙТА:\\n' + cfg['prompt'][:2000]
    body = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': [{'role': m['role'], 'parts': [{'text': m['text']}]} for m in messages],
        'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 900},
    }
    model = re.sub(r'[^a-zA-Z0-9._-]', '', cfg.get('model') or AI_DEFAULT['model'])
    req = urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent' % model,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': cfg['key']})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            j = json.load(r)
    except urllib.error.HTTPError as e:
        detail = ''
        try:
            detail = json.load(e).get('error', {}).get('message', '')
        except Exception:
            pass
        raise RuntimeError('Ошибка Gemini API (%s): %s' % (e.code, detail[:200]))
    try:
        return ''.join(pt.get('text', '') for pt in j['candidates'][0]['content']['parts']).strip() or '…'
    except Exception:
        raise RuntimeError('Пустой ответ модели (возможно, сработал фильтр безопасности)')
'''.replace('Return | ', '').replace('return | json', 'return {**AI_DEFAULT, **json')
helpers = helpers.replace("{**AI_DEFAULT, **json.load(open(AI_FILE, encoding='utf-8'))", "{**AI_DEFAULT, **json.load(open(AI_FILE, encoding='utf-8'))}")
s = s.replace("\nclass H(SimpleHTTPRequestHandler):", helpers + "\nclass H(SimpleHTTPRequestHandler):", 1)

# GET endpoints
s = s.replace("            if p == '/api/uploads' and self.authed():",
"""            if p == '/api/coach/status':
                c = ai_cfg()
                return self.send_j(200, {'enabled': bool(c.get('key')) and bool(c.get('enabled'))})
            if p == '/api/ai/settings' and self.authed():
                c = ai_cfg()
                return self.send_j(200, {'hasKey': bool(c.get('key')), 'keyHint': ('…' + c['key'][-4:]) if c.get('key') else '', 'model': c['model'], 'enabled': c['enabled'], 'prompt': c.get('prompt', '')})
            if p == '/api/uploads' and self.authed():""", 1)

# POST: public coach + authed settings
s = s.replace("        if p == '/api/login':",
"""        if p == '/api/coach':
            ip = self.client_address[0]
            now = time.time()
            hits = [t for t in coach_hits.get(ip, []) if now - t < 300]
            if len(hits) >= 20:
                return self.send_j(429, {'error': 'Слишком много сообщений, подождите пару минут'})
            coach_hits[ip] = hits + [now]
            try:
                j = json.loads(self.body(32 * 1024) or b'{}')
                msgs = []
                for m in (j.get('messages') or [])[-12:]:
                    role = 'model' if m.get('role') == 'model' else 'user'
                    txt = str(m.get('text', ''))[:1000].strip()
                    if txt:
                        msgs.append({'role': role, 'text': txt})
                while msgs and msgs[0]['role'] != 'user':
                    msgs.pop(0)
                if not msgs or msgs[-1]['role'] != 'user':
                    return self.send_j(400, {'error': 'Пустое сообщение'})
                brand = 'Flexa'
                try:
                    brand = json.load(open(os.path.join(CONTENT, 'config.json'), encoding='utf-8')).get('brand') or brand
                except Exception:
                    pass
                return self.send_j(200, {'reply': ask_gemini(msgs, brand, None)})
            except RuntimeError as e:
                return self.send_j(502, {'error': str(e)})
            except Exception:
                return self.send_j(400, {'error': 'Некорректный запрос'})
        if p == '/api/login':""", 1)
s = s.replace("        if p == '/api/save':",
"""        if p == '/api/ai/settings':
            try:
                j = json.loads(self.body(16 * 1024))
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            c = ai_cfg()
            if j.get('key'):
                c['key'] = str(j['key']).strip()
            if j.get('clearKey'):
                c['key'] = ''
            c['model'] = re.sub(r'[^a-zA-Z0-9._-]', '', str(j.get('model') or c['model'])) or AI_DEFAULT['model']
            c['enabled'] = bool(j.get('enabled', True))
            c['prompt'] = str(j.get('prompt', ''))[:2000]
            json.dump(c, open(AI_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
            return self.send_j(200, {'ok': True})
        if p == '/api/save':""", 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
