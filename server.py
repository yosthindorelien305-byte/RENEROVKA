"""Flexa server: static site + small admin API (stdlib only).
Run:  python server.py   ->  http://localhost:8080   admin: /admin.html
"""
import hashlib, hmac, json, os, re, secrets, sqlite3, sys, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, 'site')
CONTENT = os.path.join(SITE, 'content')
UPLOADS = os.path.join(CONTENT, 'uploads')
SECRET_DIR = os.path.join(ROOT, 'server_data')          # NOT served publicly
ADMIN_FILE = os.path.join(SECRET_DIR, 'admin.json')
DB_FILE = os.path.join(SECRET_DIR, 'flexa.db')
PASS_TXT = os.path.join(ROOT, 'ADMIN_PASSWORD.txt')
SYNC_KEYS = {
    'hist', 'prs', 'exLogs', 'weekPlan', 'accentTheme', 'customWorkouts',
    'progState', 'athleteProfile', 'favs', 'freezeState', 'bodyMetrics',
    'audioCfg', 'restPreset', 'duels', 'coopQuest', 'notifPrefs'
}
db_lock = threading.Lock()
PORT = int(os.environ.get('PORT', 8080))
MAX_UPLOAD = 64 * 1024 * 1024
EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.mp4', '.webm', '.mov'}
for d in (CONTENT, UPLOADS, SECRET_DIR):
    os.makedirs(d, exist_ok=True)

lock = threading.Lock()
tokens = {}          # token -> expiry
fails = {}           # ip -> (count, last)

def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 200_000).hex()

def init_admin():
    if os.path.exists(ADMIN_FILE):
        return
    pw = secrets.token_urlsafe(8)
    salt = secrets.token_hex(16)
    with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
        json.dump({'salt': salt, 'hash': hash_pw(pw, salt)}, f)
    with open(PASS_TXT, 'w', encoding='utf-8') as f:
        f.write('Пароль админки Flexa (смените его в админке, после смены файл удалится):\n' + pw + '\n')
    print('Admin password created ->', PASS_TXT)

def check_pw(pw):
    with open(ADMIN_FILE, encoding='utf-8') as f:
        a = json.load(f)
    return hmac.compare_digest(hash_pw(pw, a['salt']), a['hash'])

def set_pw(pw):
    salt = secrets.token_hex(16)
    with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
        json.dump({'salt': salt, 'hash': hash_pw(pw, salt)}, f)
    with lock:
        tokens.clear()
    if os.path.exists(PASS_TXT):
        os.remove(PASS_TXT)

def init_db():
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute(
            'CREATE TABLE IF NOT EXISTS users ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'username TEXT UNIQUE NOT NULL, '
            'pw_salt TEXT NOT NULL, '
            'pw_hash TEXT NOT NULL, '
            'display_name TEXT NOT NULL DEFAULT "", '
            'created_at INTEGER NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS user_sessions ('
            'token TEXT PRIMARY KEY, '
            'user_id INTEGER NOT NULL, '
            'expires_at INTEGER NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS user_state ('
            'user_id INTEGER PRIMARY KEY, '
            'data_json TEXT NOT NULL, '
            'updated_at INTEGER NOT NULL)'
        )
        conn.commit()

def sanitize_state(raw):
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in SYNC_KEYS and isinstance(v, str)}

def get_user_by_token(token):
    if not token:
        return None
    now = int(time.time())
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            'SELECT u.id, u.username, u.display_name, s.expires_at '
            'FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?',
            (token,)
        ).fetchone()
        if not row:
            return None
        if row[3] < now:
            conn.execute('DELETE FROM user_sessions WHERE token = ?', (token,))
            conn.commit()
            return None
        return {'id': row[0], 'username': row[1], 'displayName': row[2]}

def write_json(name, obj):
    tmp = os.path.join(CONTENT, name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(CONTENT, name))

AI_FILE = os.path.join(SECRET_DIR, 'ai.json')
AI_DEFAULT = {'provider': 'gemini', 'base_url': '', 'key': '', 'model': 'gemini-3.8-flash', 'enabled': True, 'prompt': ''}
coach_hits = {}      # ip -> [timestamps]

def ai_cfg():
    try:
        with open(AI_FILE, encoding='utf-8') as f:
            return {**AI_DEFAULT, **json.load(f)}
    except Exception:
        return dict(AI_DEFAULT)

def catalog():
    """Short catalogue so the coach can link to real workouts/programs."""
    try:
        with open(os.path.join(SITE, 'data.json'), encoding='utf-8') as f:
            D = json.load(f)
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
    return '\n'.join(lines)

SYSTEM = (
    "Ты — дружелюбный AI-тренер фитнес-сайта {brand}. Помогаешь с тренировками, техникой упражнений, "
    "планами, восстановлением, сном и общими принципами питания. Отвечай на языке пользователя, коротко и по делу "
    "(до ~180 слов), используй списки и **жирный** для ключевого. Не ставь диагнозов; при болях, травмах, "
    "беременности и хронических болезнях советуй обратиться к врачу. Не рассуждай на темы вне фитнеса и здоровья. "
    "Когда уместно, рекомендуй реальные программы, тренировки и упражнения ИЗ КАТАЛОГА ниже и вставляй их ровно в формате "
    "[[тип:ID|название]] (тип: program, workout или exercise) — сайт превратит это в ссылку. Не выдумывай ID.\n\nКАТАЛОГ:\n"
)

def build_system(brand):
    cfg = ai_cfg()
    system = SYSTEM.format(brand=brand) + catalog()
    if cfg.get('prompt'):
        system += '\n\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ ВЛАДЕЛЬЦА САЙТА:\n' + cfg['prompt'][:2000]
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
    if 'api.deepseek.com' in base:
        body['thinking'] = {'type': 'disabled'}     # fast chat answers, no reasoning mode
    headers = {'Content-Type': 'application/json'}
    if cfg.get('key'):
        headers['Authorization'] = 'Bearer ' + cfg['key']
    j = http_json(urllib.request.Request(base + '/chat/completions', data=json.dumps(body).encode(), headers=headers), timeout=90)
    try:
        return (j['choices'][0]['message']['content'] or '').strip() or '…'
    except Exception:
        raise RuntimeError('Пустой ответ модели')

def ask_builtin(messages, brand='Flexa'):
    q = (messages[-1]['text'] if messages else '').lower()
    if re.search(r'похуде|сброс|жир|вес|кардио|сушк|weight|fat', q):
        return (
            f"Для эффективного снижения веса в **{brand}** важен комплексный подход:\n\n"
            "1. **Дефицит калорий:** держите небольшой дефицит в 10–15% от суточной нормы. Пейте достаточно воды (от 1.5–2 л в день).\n"
            "2. **Регулярные тренировки:** 3–4 раза в неделю, сочетая силовые упражнения и интервалы.\n"
            "3. **Рекомендуемая программа:** начните с программы [[program:2|100 отжиманий]] для разгона метаболизма и укрепления мышц.\n"
            "4. **Базовые упражнения:** приседания, планка, отжимания и берпи.\n\n"
            "Главное правило: регулярность и постепенность!"
        )
    if re.search(r'мышц|масс|сил|накач|подтягиван|muscle|bulk|strength|pull', q):
        return (
            f"Для роста силы и мышечной массы в **{brand}**:\n\n"
            "1. **Прогрессия нагрузки:** увеличивайте количество повторений или сокращайте отдых между подходами.\n"
            "2. **Питание:** небольшой профицит калорий и 1.6–2.0 г белка на 1 кг веса.\n"
            "3. **Программы для мощного верха тела:**\n"
            "   • [[program:1|50 подтягиваний]] — построение сильной спины и бицепсов\n"
            "   • [[program:212|Frank Medrano's Routine]] — легендарная программа калистеники\n"
            "4. **Ключевые упражнения:** [[exercise:1|Подтягивания прямым хватом]], [[exercise:2|Отжимания на брусьях]], [[exercise:3|Классические отжимания]].\n\n"
            "Давайте мышцам минимум 48 часов на отдых между интенсивными тренировками одной группы!"
        )
    if re.search(r'сон|спат|восстановл|отдых|sleep|recover', q):
        return (
            "Восстановление — это 50% вашего спортивного результата:\n\n"
            "1. **Сон:** 7.5–9 часов в полной темноте. Именно во сне вырабатывается гормон роста и восстанавливаются мышечные волокна.\n"
            "2. **Дни отдыха:** тренируйтесь по схеме «день тренировка — день отдых» (например: Пн / Ср / Пт).\n"
            "3. **Разминка и растяжка:** перед тренировкой суставная разминка 5 минут, после — легкая заминка и растяжка.\n"
            "4. **Питание после тренировки:** порция белка и сложных углеводов в течение 1–2 часов."
        )
    if re.search(r'нович|нач|start|begin|зал|перв', q):
        return (
            f"Добро пожаловать в **{brand}**! Вот план для отличного старта:\n\n"
            "1. **График:** 3 тренировки в неделю с перерывом в 1 день (Пн, Ср, Пт).\n"
            "2. **Техника превыше всего:** первые 2 недели сосредоточьтесь на правильной биомеханике, а не на количестве.\n"
            "3. **Стартовая программа:** [[program:2|100 отжиманий]] — отлично развивает силу груди, плеч и кора.\n"
            "4. **Разминка:** обязательно разминайтесь перед каждым занятием.\n\n"
            "Выберите любую подходящую тренировку в каталоге [[workout:1|Тренировки]] и начните с 2–3 кругов!"
        )
    if re.search(r'пресс|живот|кор|abs|core', q):
        return (
            "Для крепкого и рельефного пресса важны два фактора:\n\n"
            "1. **Планка** — статическое укрепление глубоких мышц кора (делайте 3–4 подхода по 30–60 секунд).\n"
            "2. **Скручивания и подъемы ног** — проработка прямой и косых мышц пресса.\n"
            "3. **Питание:** рельеф пресса делается на кухне — контролируйте простые сахара и фастфуд."
        )
    return (
        f"Привет! Я ваш персональный AI-тренер **{brand}**! 🏋️\n\n"
        "Я могу составить план занятий, разобрать технику или подсказать по питанию и восстановлению.\n\n"
        "**Рекомендую начать с популярных программ:**\n"
        "• [[program:1|50 подтягиваний]] — мощная спина, руки и хват\n"
        "• [[program:2|100 отжиманий]] — сила груди, плеч и трицепса\n"
        "• [[program:212|Frank Medrano Routine]] — круговой силовой комплекс\n\n"
        "Спросите меня: *«Как похудеть?»*, *«План для новичка»* или *«Как нарастить мышцы?»*."
    )

def ai_ready(c):
    if not c.get('enabled'):
        return False
    if c.get('provider') == 'builtin':
        return True
    if c.get('provider') == 'openai':
        return bool((c.get('base_url') or '').strip()) and bool(c.get('model'))
    return bool(c.get('key'))

def ask_ai(messages, brand, extra):
    c = ai_cfg()
    if not ai_ready(c):
        raise RuntimeError('AI-тренер не настроен администратором')
    if c.get('provider') == 'builtin':
        return ask_builtin(messages, brand)
    try:
        if c.get('provider') == 'openai':
            return ask_openai(messages, brand, extra)
        return ask_gemini(messages, brand, extra)
    except RuntimeError as e:
        msg = str(e)
        if '402' in msg or 'Insufficient Balance' in msg:
            # Fallback gracefully to built-in trainer so the user still gets a great answer
            ans = ask_builtin(messages, brand)
            return ans + "\n\n*(💡 Баланс DeepSeek пуст, ответ подготовлен встроенным тренером)*"
        raise

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=SITE, **k)

    def end_headers(self):
        p = getattr(self, 'path', '')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Referrer-Policy', 'same-origin')
        if p.startswith('/content/uploads/'):
            self.send_header('Content-Security-Policy', "default-src 'none'; img-src 'self'; media-src 'self'; sandbox")
        if p.startswith('/api/'):
            self.send_header('Cache-Control', 'no-store')
        elif any(p.endswith(ext) or (ext + '?') in p for ext in ('.html', '.css', '.js', '.json', '/')):
            self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    def log_message(self, fmt, *a):
        pass

    def send_j(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def authed(self):
        t = self.headers.get('Authorization', '').replace('Bearer ', '')
        with lock:
            exp = tokens.get(t)
            if exp and exp > time.time():
                return True
            tokens.pop(t, None)
        return False

    def body(self, limit=MAX_UPLOAD):
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return None
        if n < 0 or n > limit:
            return None
        return self.rfile.read(n)

    def do_GET(self):
        p = urlparse(self.path).path
        if '..' in p.split('/'):
            return self.send_j(400, {'error': 'bad path'})
        if p.startswith('/api/'):
            if p == '/api/coach/status':
                c = ai_cfg()
                return self.send_j(200, {'enabled': ai_ready(c)})
            if p == '/api/ai/settings' and self.authed():
                c = ai_cfg()
                return self.send_j(200, {'provider': c['provider'], 'baseUrl': c.get('base_url', ''), 'hasKey': bool(c.get('key')), 'keyHint': ('…' + c['key'][-4:]) if c.get('key') else '', 'model': c['model'], 'enabled': c['enabled'], 'prompt': c.get('prompt', '')})
            if p == '/api/uploads' and self.authed():
                return self.send_j(200, sorted(os.listdir(UPLOADS)))
            if p == '/api/user/sync':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    row = conn.execute('SELECT data_json, updated_at FROM user_state WHERE user_id = ?', (usr['id'],)).fetchone()
                state = json.loads(row[0]) if row else {}
                updated_at = row[1] if row else 0
                return self.send_j(200, {'user': usr, 'state': state, 'updatedAt': updated_at})
            return self.send_j(404, {'error': 'not found'})
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path); p = u.path
        if p == '/api/coach':
            ip = self.client_address[0]
            now = time.time()
            hits = [t for t in coach_hits.get(ip, []) if now - t < 300]
            if len(hits) >= 20:
                return self.send_j(429, {'error': 'Слишком много сообщений, подождите пару минут'})
            if len(coach_hits) > 200:
                coach_hits.clear()
            coach_hits[ip] = hits + [now]
            try:
                raw_c = self.body(32 * 1024)
                if raw_c is None:
                    return self.send_j(413, {'error': 'Слишком большой запрос'})
                j = json.loads(raw_c or b'{}')
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
                    with open(os.path.join(CONTENT, 'config.json'), encoding='utf-8') as f:
                        brand = json.load(f).get('brand') or brand
                except Exception:
                    pass
                return self.send_j(200, {'reply': ask_ai(msgs, brand, None)})
            except RuntimeError as e:
                return self.send_j(502, {'error': str(e)})
            except Exception:
                return self.send_j(400, {'error': 'Некорректный запрос'})
        if p == '/api/user/register':
            try:
                raw_b = self.body(2 * 1024 * 1024)
                if raw_b is None:
                    return self.send_j(413, {'error': 'Слишком большой запрос'})
                j = json.loads(raw_b or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            uname = re.sub(r'[^a-z0-9_]', '', str(j.get('username') or '').strip().lower())
            pw = str(j.get('password') or '')
            dname = str(j.get('displayName') or uname)[:40].strip()
            if len(uname) < 3 or len(uname) > 24:
                return self.send_j(400, {'error': 'Логин: от 3 до 24 латинских букв/цифр/_'})
            if len(pw) < 6:
                return self.send_j(400, {'error': 'Пароль: минимум 6 символов'})
            salt = secrets.token_hex(16)
            pwh = hash_pw(pw, salt)
            now = int(time.time())
            state = sanitize_state(j.get('state'))
            tok = secrets.token_urlsafe(32)
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                if conn.execute('SELECT 1 FROM users WHERE username = ?', (uname,)).fetchone():
                    return self.send_j(409, {'error': 'Такой логин уже занят'})
                cur = conn.execute(
                    'INSERT INTO users (username, pw_salt, pw_hash, display_name, created_at) VALUES (?, ?, ?, ?, ?)',
                    (uname, salt, pwh, dname, now)
                )
                uid = cur.lastrowid
                conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tok, uid, now + 30 * 86400))
                if state:
                    conn.execute('INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?)', (uid, json.dumps(state, ensure_ascii=False), now))
                conn.commit()
            return self.send_j(200, {'token': tok, 'user': {'id': uid, 'username': uname, 'displayName': dname}, 'state': state, 'updatedAt': now if state else 0})
        if p == '/api/user/login':
            ip = self.client_address[0]
            c, last = fails.get(ip, (0, 0))
            if c >= 8 and time.time() - last < 60:
                return self.send_j(429, {'error': 'Слишком много попыток, подождите минуту'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            uname = re.sub(r'[^a-z0-9_]', '', str(j.get('username') or '').strip().lower())
            pw = str(j.get('password') or '')
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                row = conn.execute('SELECT id, username, pw_salt, pw_hash, display_name FROM users WHERE username = ?', (uname,)).fetchone()
                if not row or not hmac.compare_digest(hash_pw(pw, row[2]), row[3]):
                    if len(fails) > 200:
                        fails.clear()
                    fails[ip] = (c + 1, time.time())
                    time.sleep(0.5)
                    return self.send_j(401, {'error': 'Неверный логин или пароль'})
                fails.pop(ip, None)
                now = int(time.time())
                tok = secrets.token_urlsafe(32)
                conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tok, row[0], now + 30 * 86400))
                st_row = conn.execute('SELECT data_json, updated_at FROM user_state WHERE user_id = ?', (row[0],)).fetchone()
                conn.commit()
            state = json.loads(st_row[0]) if st_row else {}
            updated_at = st_row[1] if st_row else 0
            return self.send_j(200, {'token': tok, 'user': {'id': row[0], 'username': row[1], 'displayName': row[4]}, 'state': state, 'updatedAt': updated_at})
        if p == '/api/user/logout':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            if tok:
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    conn.execute('DELETE FROM user_sessions WHERE token = ?', (tok,))
                    conn.commit()
            return self.send_j(200, {'ok': True})
        if p == '/api/user/sync':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            raw_b = self.body(2 * 1024 * 1024)
            if raw_b is None:
                return self.send_j(413, {'error': 'Слишком большой объём данных'})
            try:
                j = json.loads(raw_b or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            state = sanitize_state(j.get('state'))
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    'INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?) '
                    'ON CONFLICT(user_id) DO UPDATE SET data_json=excluded.data_json, updated_at=excluded.updated_at',
                    (usr['id'], json.dumps(state, ensure_ascii=False), now)
                )
                conn.commit()
            return self.send_j(200, {'ok': True, 'updatedAt': now})
        if p == '/api/login':
            ip = self.client_address[0]
            c, last = fails.get(ip, (0, 0))
            if c >= 5 and time.time() - last < 60:
                return self.send_j(429, {'error': 'Слишком много попыток, подождите минуту'})
            try:
                pw = json.loads(self.body(4096) or b'{}').get('password', '')
            except Exception:
                pw = ''
            if check_pw(pw):
                fails.pop(ip, None)
                t = secrets.token_urlsafe(32)
                with lock:
                    tokens[t] = time.time() + 12 * 3600
                return self.send_j(200, {'token': t})
            if len(fails) > 200:
                fails.clear()
            fails[ip] = (c + 1, time.time())
            time.sleep(1)
            return self.send_j(401, {'error': 'Неверный пароль'})
        if not self.authed():
            return self.send_j(401, {'error': 'unauthorized'})
        if p == '/api/ai/settings':
            try:
                j = json.loads(self.body(16 * 1024))
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            c = ai_cfg()
            if j.get('key'):
                c['key'] = str(j['key']).strip()
            if j.get('clearKey'):
                c['key'] = ''
            prov = j.get('provider')
            c['provider'] = prov if prov in ('openai', 'gemini', 'builtin') else 'builtin'
            bu = str(j.get('baseUrl', '')).strip()
            if bu and not re.match(r'^https?://', bu):
                return self.send_j(400, {'error': 'Base URL должен начинаться с http:// или https://'})
            c['base_url'] = bu
            c['model'] = re.sub(r'[^a-zA-Z0-9._:/-]', '', str(j.get('model') or c['model'])) or AI_DEFAULT['model']
            c['enabled'] = bool(j.get('enabled', True))
            c['prompt'] = str(j.get('prompt', ''))[:2000]
            with open(AI_FILE, 'w', encoding='utf-8') as f:
                json.dump(c, f, ensure_ascii=False)
            return self.send_j(200, {'ok': True})
        if p == '/api/save':          # ?file=config|overrides  body: JSON
            f = parse_qs(u.query).get('file', [''])[0]
            if f not in ('config', 'overrides'):
                return self.send_j(400, {'error': 'bad file'})
            raw = self.body(5 * 1024 * 1024)
            if raw is None:
                return self.send_j(413, {'error': 'too large'})
            try:
                obj = json.loads(raw)
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            write_json(f + '.json', obj)
            return self.send_j(200, {'ok': True})
        if p == '/api/upload':        # ?name=program_2  body: raw image; header X-Filename for ext
            name = re.sub(r'[^a-zA-Z0-9_-]', '', parse_qs(u.query).get('name', ['file'])[0])[:40] or 'file'
            ext = os.path.splitext(self.headers.get('X-Filename', ''))[1].lower()
            if ext not in EXT:
                return self.send_j(400, {'error': 'Разрешены: png, jpg, webp, gif, svg, mp4, webm'})
            raw = self.body()
            if raw is None or not raw:
                return self.send_j(400, {'error': 'Файл пустой или больше 64 МБ'})
            for old in os.listdir(UPLOADS):
                if os.path.splitext(old)[0] == name:
                    os.remove(os.path.join(UPLOADS, old))
            fn = name + ext
            with open(os.path.join(UPLOADS, fn), 'wb') as f:
                f.write(raw)
            return self.send_j(200, {'path': 'content/uploads/' + fn + '?v=' + str(int(time.time()))})
        if p == '/api/password':
            try:
                pw = json.loads(self.body(4096)).get('password', '')
            except Exception:
                pw = ''
            if len(pw) < 6:
                return self.send_j(400, {'error': 'Минимум 6 символов'})
            set_pw(pw)
            return self.send_j(200, {'ok': True})
        self.send_j(404, {'error': 'not found'})

if __name__ == '__main__':
    init_admin()
    init_db()
    print('Flexa: http://localhost:%d   Admin: http://localhost:%d/admin.html' % (PORT, PORT))
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
