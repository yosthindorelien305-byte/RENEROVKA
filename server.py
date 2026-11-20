"""Flexa server: static site + small admin API (stdlib only).
Run:  python server.py   ->  http://localhost:8080   admin: /admin.html
"""
import base64, hashlib, hmac, html, json, os, re, secrets, sqlite3, sys, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, parse_qsl

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
FREE_ACCESS_MODE = os.environ.get('FLEXA_FREE_MODE', '1').strip().lower() not in ('0', 'false', 'no', 'off')
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
            'email TEXT NOT NULL DEFAULT "", '
            'plan TEXT NOT NULL DEFAULT "free", '
            'plan_expires_at INTEGER NOT NULL DEFAULT 0, '
            'is_blocked INTEGER NOT NULL DEFAULT 0, '
            'last_login_at INTEGER NOT NULL DEFAULT 0, '
            'created_at INTEGER NOT NULL)'
        )
        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        migrations = [
            ('email', 'TEXT NOT NULL DEFAULT ""'),
            ('plan', 'TEXT NOT NULL DEFAULT "free"'),
            ('plan_expires_at', 'INTEGER NOT NULL DEFAULT 0'),
            ('is_blocked', 'INTEGER NOT NULL DEFAULT 0'),
            ('last_login_at', 'INTEGER NOT NULL DEFAULT 0'),
            ('oauth_provider', 'TEXT NOT NULL DEFAULT ""'),
            ('oauth_id', 'TEXT NOT NULL DEFAULT ""'),
            ('avatar', 'TEXT NOT NULL DEFAULT ""'),
        ]
        for col, ddl in migrations:
            if col not in cols:
                conn.execute(f'ALTER TABLE users ADD COLUMN {col} {ddl}')
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email '
            'ON users(email) WHERE email != ""'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_users_oauth '
            'ON users(oauth_provider, oauth_id) WHERE oauth_provider != ""'
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
        conn.execute(
            'CREATE TABLE IF NOT EXISTS password_resets ('
            'code TEXT PRIMARY KEY, '
            'user_id INTEGER NOT NULL, '
            'expires_at INTEGER NOT NULL, '
            'used INTEGER NOT NULL DEFAULT 0, '
            'created_at INTEGER NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS payments ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'user_id INTEGER NOT NULL, '
            'plan TEXT NOT NULL, '
            'days INTEGER NOT NULL DEFAULT 0, '
            'amount INTEGER NOT NULL DEFAULT 0, '
            'currency TEXT NOT NULL DEFAULT "RUB", '
            'provider TEXT NOT NULL DEFAULT "manual", '
            'status TEXT NOT NULL DEFAULT "paid", '
            'note TEXT NOT NULL DEFAULT "", '
            'payment_id TEXT NOT NULL DEFAULT "", '
            'updated_at INTEGER NOT NULL DEFAULT 0, '
            'created_at INTEGER NOT NULL)'
        )
        pay_cols = {r[1] for r in conn.execute('PRAGMA table_info(payments)').fetchall()}
        for col, ddl in [('payment_id', 'TEXT NOT NULL DEFAULT ""'), ('updated_at', 'INTEGER NOT NULL DEFAULT 0')]:
            if col not in pay_cols:
                conn.execute(f'ALTER TABLE payments ADD COLUMN {col} {ddl}')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_payments_payment_id ON payments(payment_id)')

        # Social & Direct Messaging tables
        conn.execute(
            'CREATE TABLE IF NOT EXISTS friendships ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'requester_id INTEGER NOT NULL, '
            'addressee_id INTEGER NOT NULL, '
            'pair_min INTEGER NOT NULL, '
            'pair_max INTEGER NOT NULL, '
            'status TEXT NOT NULL DEFAULT "pending", '
            'created_at INTEGER NOT NULL, '
            'updated_at INTEGER NOT NULL)'
        )
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_friendships_pair ON friendships(pair_min, pair_max)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_friendships_req ON friendships(requester_id, status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_friendships_addr ON friendships(addressee_id, status)')

        conn.execute(
            'CREATE TABLE IF NOT EXISTS conversations ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'user1_id INTEGER NOT NULL, '
            'user2_id INTEGER NOT NULL, '
            'created_at INTEGER NOT NULL, '
            'last_message_at INTEGER NOT NULL DEFAULT 0, '
            'last_message_text TEXT NOT NULL DEFAULT "", '
            'last_sender_id INTEGER NOT NULL DEFAULT 0, '
            'user1_hidden_at INTEGER NOT NULL DEFAULT 0, '
            'user2_hidden_at INTEGER NOT NULL DEFAULT 0)'
        )
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_pair ON conversations(user1_id, user2_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_conversations_u1 ON conversations(user1_id, last_message_at DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_conversations_u2 ON conversations(user2_id, last_message_at DESC)')

        conn.execute(
            'CREATE TABLE IF NOT EXISTS messages ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'conversation_id INTEGER NOT NULL, '
            'sender_id INTEGER NOT NULL, '
            'recipient_id INTEGER NOT NULL, '
            'body TEXT NOT NULL, '
            'client_msg_id TEXT NOT NULL DEFAULT "", '
            'created_at INTEGER NOT NULL, '
            'delivered_at INTEGER NOT NULL DEFAULT 0, '
            'read_at INTEGER NOT NULL DEFAULT 0, '
            'deleted_at INTEGER NOT NULL DEFAULT 0)'
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(recipient_id, read_at, deleted_at)')
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_client_id '
            'ON messages(sender_id, client_msg_id) WHERE client_msg_id != ""'
        )

        conn.execute(
            'CREATE TABLE IF NOT EXISTS user_blocks ('
            'blocker_id INTEGER NOT NULL, '
            'blocked_id INTEGER NOT NULL, '
            'created_at INTEGER NOT NULL, '
            'PRIMARY KEY (blocker_id, blocked_id))'
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_user_blocks_blocked ON user_blocks(blocked_id)')

        conn.execute(
            'CREATE TABLE IF NOT EXISTS user_reports ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'reporter_id INTEGER NOT NULL, '
            'target_user_id INTEGER NOT NULL, '
            'message_id INTEGER NOT NULL DEFAULT 0, '
            'reason TEXT NOT NULL, '
            'created_at INTEGER NOT NULL)'
        )
        conn.commit()

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def user_dto(row, respect_free_mode=True):
    """row: (id, username, display_name, email, plan, plan_expires_at, is_blocked, [avatar]) or sqlite3.Row"""
    now = int(time.time())
    if isinstance(row, sqlite3.Row) or isinstance(row, dict):
        plan = row['plan'] or 'free'
        exp = int(row['plan_expires_at'] or 0)
        real_pro = (plan == 'pro') and (exp == 0 or exp > now)
        eff_pro = True if (respect_free_mode and FREE_ACCESS_MODE) else real_pro
        return {
            'id': row['id'],
            'username': row['username'],
            'displayName': row['display_name'] if 'display_name' in row.keys() and row['display_name'] else row['username'],
            'email': row['email'] if 'email' in row.keys() and row['email'] else '',
            'avatar': row['avatar'] if 'avatar' in row.keys() and row['avatar'] else '',
            'plan': 'pro' if eff_pro else 'free',
            'planExpiresAt': (0 if (respect_free_mode and FREE_ACCESS_MODE and not real_pro) else exp) if eff_pro else 0,
            'isPro': eff_pro,
            'freeAccessMode': bool(FREE_ACCESS_MODE),
            'isBlocked': bool(row['is_blocked']) if 'is_blocked' in row.keys() else False,
        }
    plan = row[4] or 'free'
    exp = int(row[5] or 0)
    real_pro = (plan == 'pro') and (exp == 0 or exp > now)
    eff_pro = True if (respect_free_mode and FREE_ACCESS_MODE) else real_pro
    av = row[7] if len(row) > 7 and row[7] else ''
    return {
        'id': row[0],
        'username': row[1],
        'displayName': row[2] or row[1],
        'email': row[3] or '',
        'avatar': av,
        'plan': 'pro' if eff_pro else 'free',
        'planExpiresAt': (0 if (respect_free_mode and FREE_ACCESS_MODE and not real_pro) else exp) if eff_pro else 0,
        'isPro': eff_pro,
        'freeAccessMode': bool(FREE_ACCESS_MODE),
        'isBlocked': bool(row[6]),
    }

def sanitize_state(raw):
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in SYNC_KEYS and isinstance(v, str)}

SAFE_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{3,8}$')
DEFAULT_AV_COLORS = ['#3b4a34', '#4d3e28', '#2b3930', '#3b3342', '#2e3f2d', '#44372b', '#283635', '#334155']
DEFAULT_AV_SHIRTS = ['#6b8e4e', '#c68932', '#4f6d5a', '#7b6894', '#5b8a47', '#b87d38', '#486c68', '#38bdf8']

def safe_hex_color(val, fallback):
    s = str(val or '').strip()
    return s if SAFE_HEX_COLOR_RE.match(s) else fallback

msg_rate_lock = threading.Lock()
msg_hits = {}  # user_id -> [timestamps]

def check_message_rate_limit(uid):
    now = time.time()
    with msg_rate_lock:
        if len(msg_hits) > 1000:
            msg_hits.clear()
        recent = [t for t in msg_hits.get(uid, []) if now - t < 60]
        burst = [t for t in recent if now - t < 10]
        if len(burst) >= 15 or len(recent) >= 40:
            msg_hits[uid] = recent
            return False
        recent.append(now)
        msg_hits[uid] = recent
        return True

def extract_public_user_card(r, now=None, include_details=False):
    """Build safe public profile card from DB row (id, username, display_name, avatar, plan, plan_expires_at, last_login_at, created_at, data_json).
    Never exposes email, password hashes, tokens, or raw internal integer user_id.
    Never generates synthetic/fake PRs or workout stats.
    """
    if now is None:
        now = int(time.time())
    uid = int(r['id'])
    uname = str(r['username'] or '').strip()
    uname_low = uname.lower()
    dname = str(r['display_name'] or '').strip() or uname
    handle = '@' + uname_low
    last_active = int(r['last_login_at'] or r['created_at'] or 0)
    is_online = (now - last_active) < 1800
    plan = r['plan'] or 'free'
    exp = int(r['plan_expires_at'] or 0)
    is_pro = True if FREE_ACCESS_MODE else (plan == 'pro' and (exp == 0 or exp > now))
    db_avatar = str(r['avatar'] or '').strip() if 'avatar' in r.keys() else ''

    profile_data = {}
    hist_data = []
    prs_data = {}
    raw_json = r['data_json'] if 'data_json' in r.keys() else None
    if raw_json:
        try:
            st = json.loads(raw_json)
            if isinstance(st, dict):
                st_data = st.get('state') if isinstance(st.get('state'), dict) else st
                prof_raw = st_data.get('athleteProfile')
                if isinstance(prof_raw, str):
                    try:
                        profile_data = json.loads(prof_raw)
                    except Exception:
                        profile_data = {}
                elif isinstance(prof_raw, dict):
                    profile_data = prof_raw
                h_raw = st_data.get('hist')
                if isinstance(h_raw, str):
                    try:
                        hist_data = json.loads(h_raw)
                    except Exception:
                        hist_data = []
                elif isinstance(h_raw, list):
                    hist_data = h_raw
                if include_details:
                    p_raw = st_data.get('prs')
                    if isinstance(p_raw, str):
                        try:
                            prs_data = json.loads(p_raw)
                        except Exception:
                            prs_data = {}
                    elif isinstance(p_raw, dict):
                        prs_data = p_raw
        except Exception:
            pass

    if not isinstance(profile_data, dict):
        profile_data = {}
    if not isinstance(hist_data, list):
        hist_data = []
    if not isinstance(prs_data, dict):
        prs_data = {}

    h_len = len(hist_data)
    try:
        base_pts = max(0, int(profile_data.get('points') or 0))
    except Exception:
        base_pts = 0
    calc_pts = max(base_pts, h_len * 250)
    try:
        lvl = max(1, int(profile_data.get('level') or max(1, 1 + h_len // 3)))
    except Exception:
        lvl = max(1, 1 + h_len // 3)
    try:
        streak = max(0, int(profile_data.get('streakDays') or 0))
    except Exception:
        streak = 0

    prof_name = str(profile_data.get('name') or '').strip()
    if prof_name in ('', 'Mr.Bobrovsky', 'Атлет', 'Athlete'):
        name = dname or uname
    else:
        name = prof_name[:40]

    avatar = str(profile_data.get('avatar') or db_avatar or '').strip()
    if avatar and not (avatar.startswith('http://') or avatar.startswith('https://') or avatar.startswith('content/uploads/') or avatar.startswith('img/') or avatar.startswith('data:image/')):
        avatar = ''

    c_idx = uid % len(DEFAULT_AV_COLORS)
    color = safe_hex_color(profile_data.get('color'), DEFAULT_AV_COLORS[c_idx])
    shirt = safe_hex_color(profile_data.get('shirt'), DEFAULT_AV_SHIRTS[c_idx])

    card = {
        'id': 'u_' + uname_low,
        'userId': uid,
        'username': uname_low,
        'name': name,
        'displayName': name,
        'handle': handle,
        'level': lvl,
        'streak': streak,
        'points': calc_pts,
        'online': is_online,
        'color': color,
        'shirt': shirt,
        'avatar': avatar,
        'isPro': is_pro,
        'workoutsCount': h_len,
    }
    if include_details:
        total_sec = 0
        for item in hist_data:
            if isinstance(item, dict):
                try:
                    total_sec += max(0, int(item.get('s') or 0))
                except Exception:
                    pass
        real_prs = []
        for ex_id, val in prs_data.items():
            try:
                reps = int(val)
                if reps > 0:
                    real_prs.append({'exerciseId': str(ex_id), 'reps': reps})
            except Exception:
                pass
        real_prs.sort(key=lambda x: x['reps'], reverse=True)
        card['totalMinutes'] = round(total_sec / 60)
        card['prs'] = {x['exerciseId']: x['reps'] for x in real_prs}
        card['prsList'] = real_prs[:10]
        card['prsCount'] = len(real_prs)
        card['joinedAt'] = int(r['created_at'] or 0)
    return card

def get_friendship_status_map(conn, my_uid, other_uids):
    """Return dict {other_uid: 'friends' | 'outgoing' | 'incoming' | 'none'}."""
    res = {u: 'none' for u in other_uids}
    if not other_uids:
        return res
    rows = conn.execute(
        'SELECT requester_id, addressee_id, status FROM friendships '
        'WHERE requester_id = ? OR addressee_id = ?',
        (my_uid, my_uid)
    ).fetchall()
    for req_id, addr_id, st in rows:
        other = addr_id if req_id == my_uid else req_id
        if other not in res:
            continue
        if st == 'accepted':
            res[other] = 'friends'
        elif st == 'pending':
            res[other] = 'outgoing' if req_id == my_uid else 'incoming'
    return res

def get_block_relation(conn, my_uid, other_uid):
    """Return (blocked_by_me: bool, blocked_me: bool)."""
    rows = conn.execute(
        'SELECT blocker_id, blocked_id FROM user_blocks '
        'WHERE (blocker_id = ? AND blocked_id = ?) OR (blocker_id = ? AND blocked_id = ?)',
        (my_uid, other_uid, other_uid, my_uid)
    ).fetchall()
    by_me = any(r[0] == my_uid for r in rows)
    by_other = any(r[0] == other_uid for r in rows)
    return by_me, by_other

def resolve_target_user(conn, raw_identifier):
    """Resolve user row by username or @handle (or legacy u_<username> / u_<id>)."""
    ident = str(raw_identifier or '').strip().lower()
    if not ident:
        return None
    if ident.startswith('@'):
        ident = ident[1:]
    elif ident.startswith('u_'):
        ident = ident[2:]
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT u.id, u.username, u.display_name, u.avatar, u.plan, u.plan_expires_at, u.last_login_at, u.created_at, u.is_blocked, s.data_json '
        'FROM users u LEFT JOIN user_state s ON s.user_id = u.id '
        'WHERE lower(u.username) = ? AND u.is_blocked = 0',
        (ident,)
    ).fetchone()
    if not row and ident.isdigit():
        row = conn.execute(
            'SELECT u.id, u.username, u.display_name, u.avatar, u.plan, u.plan_expires_at, u.last_login_at, u.created_at, u.is_blocked, s.data_json '
            'FROM users u LEFT JOIN user_state s ON s.user_id = u.id '
            'WHERE u.id = ? AND u.is_blocked = 0',
            (int(ident),)
        ).fetchone()
    return row

def get_user_by_token(token):
    if not token:
        return None
    now = int(time.time())
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            'SELECT u.id, u.username, u.display_name, u.email, u.plan, u.plan_expires_at, u.is_blocked, u.avatar, s.expires_at '
            'FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?',
            (token,)
        ).fetchone()
        if not row:
            return None
        if row[8] < now or row[6]:
            conn.execute('DELETE FROM user_sessions WHERE token = ?', (token,))
            conn.commit()
            return None
        return user_dto(row[:8])

def write_json(name, obj):
    tmp = os.path.join(CONTENT, name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(CONTENT, name))

AI_FILE = os.path.join(SECRET_DIR, 'ai.json')
AI_DEFAULT = {'provider': 'gemini', 'base_url': '', 'key': '', 'model': 'gemini-3.8-flash', 'enabled': True, 'prompt': ''}
coach_hits = {}      # ip -> [timestamps]

PLANS = {
    '1m': {'id': '1m', 'name': '1 месяц', 'days': 30, 'price': 290, 'badge': 'Базовый', 'desc': '30 дней PRO-доступа'},
    '3m': {'id': '3m', 'name': '3 месяца', 'days': 90, 'price': 690, 'badge': 'ХИТ 🔥', 'desc': '90 дней (~230 ₽/мес, скидка 20%)'},
    '1y': {'id': '1y', 'name': '1 год', 'days': 365, 'price': 1490, 'badge': 'ВЫГОДА 57% ⚡', 'desc': '365 дней (~124 ₽/мес)'}
}

YOOKASSA_FILE = os.path.join(SECRET_DIR, 'yookassa.json')
YOOKASSA_DEFAULT = {
    'shop_id': '',
    'secret_key': '',
    'enabled': False,
    'sbp_only': True
}

def yookassa_cfg():
    try:
        with open(YOOKASSA_FILE, encoding='utf-8') as f:
            return {**YOOKASSA_DEFAULT, **json.load(f)}
    except Exception:
        return dict(YOOKASSA_DEFAULT)

def save_yookassa_cfg(cfg):
    cur = yookassa_cfg()
    cur.update(cfg)
    with open(YOOKASSA_FILE, 'w', encoding='utf-8') as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)

def yookassa_create_payment(shop_id, secret_key, amount_rub, return_url, description, metadata=None, sbp_only=True):
    auth_str = base64.b64encode(f'{shop_id}:{secret_key}'.encode('utf-8')).decode('ascii')
    idempotence_key = secrets.token_hex(16)
    payload = {
        'amount': {
            'value': f'{amount_rub:.2f}',
            'currency': 'RUB'
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': return_url
        },
        'capture': True,
        'description': description[:128]
    }
    if sbp_only:
        payload['payment_method_data'] = {'type': 'sbp'}
    if metadata:
        payload['metadata'] = metadata

    req = urllib.request.Request(
        'https://api.yookassa.ru/v3/payments',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Idempotence-Key': idempotence_key,
            'Authorization': f'Basic {auth_str}'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_msg = 'Ошибка ЮKassa (%s)' % e.code
        try:
            err_body = json.loads(e.read().decode('utf-8'))
            err_msg = err_body.get('description') or err_body.get('error') or err_msg
        except Exception:
            pass
        raise RuntimeError(err_msg)
    except urllib.error.URLError as e:
        raise RuntimeError('Не удалось соединиться с сервером ЮKassa: %s' % e.reason)

def yookassa_get_payment(shop_id, secret_key, payment_id):
    if not shop_id or not secret_key or not payment_id:
        return None
    auth_str = base64.b64encode(f'{shop_id}:{secret_key}'.encode('utf-8')).decode('ascii')
    req = urllib.request.Request(
        f'https://api.yookassa.ru/v3/payments/{payment_id}',
        headers={
            'Authorization': f'Basic {auth_str}'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def yookassa_test_connection(shop_id, secret_key):
    auth_str = base64.b64encode(f'{shop_id}:{secret_key}'.encode('utf-8')).decode('ascii')
    req = urllib.request.Request(
        'https://api.yookassa.ru/v3/me',
        headers={
            'Authorization': f'Basic {auth_str}'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            req2 = urllib.request.Request('https://api.yookassa.ru/v3/payments?limit=1', headers={'Authorization': f'Basic {auth_str}'})
            with urllib.request.urlopen(req2, timeout=15) as r2:
                return json.loads(r2.read().decode('utf-8'))
        err_msg = 'Ошибка авторизации ЮKassa (%s)' % e.code
        try:
            err_body = json.loads(e.read().decode('utf-8'))
            err_msg = err_body.get('description') or err_body.get('error') or err_msg
        except Exception:
            pass
        raise RuntimeError(err_msg)
    except urllib.error.URLError as e:
        raise RuntimeError('Не удалось подключиться к ЮKassa: %s' % e.reason)

def sync_pending_yookassa_payment(pay_id):
    """Verify an existing pending payment with YooKassa API and update DB idempotently.
    Never creates new payment rows and never grants PRO without YooKassa confirmation.
    """
    if not pay_id:
        return None
    now = int(time.time())
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            'SELECT id, user_id, plan, days, amount, status FROM payments WHERE payment_id = ?',
            (pay_id,)
        ).fetchone()
    if not row:
        return None
    db_pay_id, uid, plan_id, days, amount, status = row
    if status == 'paid':
        return {'status': 'paid', 'uid': uid, 'verified': True, 'alreadyPaid': True}
    if status != 'pending':
        return {'status': status, 'uid': uid, 'verified': False, 'alreadyPaid': False}

    cfg = yookassa_cfg()
    if not cfg.get('shop_id') or not cfg.get('secret_key'):
        return {'status': status, 'uid': uid, 'verified': False, 'alreadyPaid': False}

    yk_pay = yookassa_get_payment(cfg['shop_id'], cfg['secret_key'], pay_id)
    if not yk_pay:
        return {'status': status, 'uid': uid, 'verified': False, 'alreadyPaid': False}

    yk_status = str(yk_pay.get('status') or '').strip().lower()
    if yk_status == 'succeeded':
        with db_lock, sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute(
                'UPDATE payments SET status = "paid", updated_at = ? WHERE id = ? AND status = "pending"',
                (now, db_pay_id)
            )
            if cur.rowcount == 1 and uid:
                u_row = conn.execute('SELECT plan, plan_expires_at FROM users WHERE id = ?', (uid,)).fetchone()
                if u_row:
                    cur_exp = int(u_row[1] or 0)
                    base = max(now, cur_exp) if u_row[0] == 'pro' and cur_exp > now else now
                    new_exp = base + int(days or 0) * 86400
                    conn.execute('UPDATE users SET plan = "pro", plan_expires_at = ? WHERE id = ?', (new_exp, uid))
            conn.commit()
        return {'status': 'paid', 'uid': uid, 'verified': True, 'alreadyPaid': False}
    if yk_status == 'canceled':
        with db_lock, sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                'UPDATE payments SET status = "canceled", updated_at = ? WHERE id = ? AND status = "pending"',
                (now, db_pay_id)
            )
            conn.commit()
        return {'status': 'canceled', 'uid': uid, 'verified': True, 'alreadyPaid': False}
    return {'status': yk_status or status, 'uid': uid, 'verified': True, 'alreadyPaid': False}

# ----------------------------------------------------------------------
# TELEGRAM BOT AUTH & DEEP-LINK REDIRECT
# ----------------------------------------------------------------------
TELEGRAM_FILE = os.path.join(SECRET_DIR, 'telegram.json')
TELEGRAM_DEFAULT = {
    'bot_token': '',
    'bot_username': '',
    'enabled': True
}

def telegram_cfg():
    try:
        with open(TELEGRAM_FILE, encoding='utf-8') as f:
            return {**TELEGRAM_DEFAULT, **json.load(f)}
    except Exception:
        return dict(TELEGRAM_DEFAULT)

def save_telegram_cfg(cfg):
    cur = telegram_cfg()
    cur.update(cfg)
    with open(TELEGRAM_FILE, 'w', encoding='utf-8') as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)

TG_AUTH_TTL = 900
TG_INITDATA_MAX_AGE = 300
tg_auth_lock = threading.Lock()
tg_pending_auth = {} # auth_token -> dict
tg_used_init_hashes = {} # hash_hex -> expires_at

def verify_telegram_webapp_init_data(init_data, bot_token, max_age=TG_INITDATA_MAX_AGE):
    """Verify Telegram Mini App initData HMAC-SHA256 signature, auth_date freshness, and single-use hash."""
    if not isinstance(init_data, str) or not init_data.strip() or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    except Exception:
        return None
    parsed = dict(pairs)
    received_hash = parsed.pop('hash', None)
    if not received_hash or not re.fullmatch(r'[0-9a-fA-F]{64}', received_hash):
        return None
    try:
        auth_date = int(parsed.get('auth_date', '0'))
    except ValueError:
        return None
    now = int(time.time())
    if auth_date <= 0 or (now - auth_date) > max_age or (auth_date - now) > 60:
        return None
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode('utf-8'), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
    hash_lower = received_hash.lower()
    if not hmac.compare_digest(expected_hash, hash_lower):
        return None
    user_raw = parsed.get('user')
    if not user_raw:
        return None
    try:
        user_obj = json.loads(user_raw)
    except Exception:
        return None
    if not isinstance(user_obj, dict) or not user_obj.get('id'):
        return None
    with tg_auth_lock:
        for h_key in [k for k, exp in tg_used_init_hashes.items() if exp <= now]:
            tg_used_init_hashes.pop(h_key, None)
        if hash_lower in tg_used_init_hashes:
            return None
        tg_used_init_hashes[hash_lower] = now + max_age + 60
    return user_obj

def process_telegram_auth_code(auth_code, from_user, chat_id, bot_token):
    now = int(time.time())
    auth_code = str(auth_code or '').strip()
    tg_id = str(from_user.get('id', '')).strip()
    if not auth_code or not tg_id:
        return False

    # Validate pending auth_code and TTL BEFORE any DB changes or Telegram replies
    with tg_auth_lock:
        rec = tg_pending_auth.get(auth_code)
        if not rec:
            return False
        created_at = rec.get('created_at', 0)
        if (now - created_at) > TG_AUTH_TTL:
            tg_pending_auth.pop(auth_code, None)
            return False
        if rec.get('status') != 'pending':
            return False
        rec['status'] = 'processing'

    fname = str(from_user.get('first_name') or '').strip()
    lname = str(from_user.get('last_name') or '').strip()
    display_name = (f"{fname} {lname}".strip() or f"User {tg_id}")[:40]
    tg_uname = str(from_user.get('username') or '').strip().lower()

    clean_uname = re.sub(r'[^a-z0-9_]', '', tg_uname)
    if len(clean_uname) < 3:
        clean_uname = f"tg_{tg_id[:10]}"
    clean_uname = clean_uname[:20]

    with db_lock, sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            'SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked, avatar '
            'FROM users WHERE oauth_provider = "telegram" AND oauth_id = ?',
            (tg_id,)
        ).fetchone()

        if row:
            if row[6]: # is_blocked
                with tg_auth_lock:
                    if auth_code in tg_pending_auth:
                        tg_pending_auth[auth_code] = {
                            'created_at': created_at,
                            'status': 'blocked',
                            'error': 'Аккаунт заблокирован администратором'
                        }
                return False
            uid = row[0]
            conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (now, uid))
            u_data = user_dto(row)
        else:
            uname = clean_uname
            idx = 1
            while conn.execute('SELECT 1 FROM users WHERE username = ?', (uname,)).fetchone():
                uname = f"{clean_uname[:16]}_{idx}"
                idx += 1
            cur = conn.execute(
                'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, oauth_provider, oauth_id, avatar, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                'VALUES (?, "", "", ?, "", "telegram", ?, "", "free", 0, 0, ?, ?)',
                (uname, display_name, tg_id, now, now)
            )
            uid = cur.lastrowid
            u_data = user_dto((uid, uname, display_name, "", "free", 0, 0, ""))

        stok = secrets.token_urlsafe(32)
        conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (stok, uid, now + 30 * 86400))
        st_row = conn.execute('SELECT data_json, updated_at FROM user_state WHERE user_id = ?', (uid,)).fetchone()
        conn.commit()

        u_state = json.loads(st_row[0]) if st_row else {}
        up_at = st_row[1] if st_row else 0

    with tg_auth_lock:
        if auth_code in tg_pending_auth:
            tg_pending_auth[auth_code] = {
                'created_at': created_at,
                'status': 'confirmed',
                'sessionToken': stok,
                'user': u_data,
                'state': u_state,
                'updatedAt': up_at
            }

    if bot_token and chat_id:
        try:
            send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            safe_name = html.escape(display_name)
            reply_text = f"✅ <b>Вход в RizzaFit подтверждён!</b>\n\nДобро пожаловать, <b>{safe_name}</b>!\nВы успешно авторизовались в приложении. Можете вернуться в браузер — ваш профиль уже открыт!"
            payload = json.dumps({'chat_id': chat_id, 'text': reply_text, 'parse_mode': 'HTML'}).encode('utf-8')
            req = urllib.request.Request(send_url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': 'FlexaBot/1.0'})
            urllib.request.urlopen(req, timeout=8)
        except Exception:
            pass
    return True

def telegram_bot_worker():
    offset = 0
    while True:
        try:
            cfg = telegram_cfg()
            token = cfg.get('bot_token', '').strip()
            if not token or not cfg.get('enabled', True):
                time.sleep(5)
                continue
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=15"
            req = urllib.request.Request(url, headers={'User-Agent': 'FlexaBot/1.0'})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if not data.get('ok'):
                    time.sleep(4)
                    continue
                updates = data.get('result', [])
                for u in updates:
                    offset = max(offset, u['update_id'] + 1)
                    msg = u.get('message') or u.get('edited_message')
                    if not msg:
                        continue
                    text = (msg.get('text') or '').strip()
                    chat_id = msg.get('chat', {}).get('id')
                    from_user = msg.get('from', {})
                    if text.startswith('/start auth_'):
                        auth_code = text.split('auth_')[1].strip()
                        process_telegram_auth_code(auth_code, from_user, chat_id, token)
        except Exception:
            time.sleep(3)

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
            if p == '/api/community/users' or p == '/api/users':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if p == '/api/users' and not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                qs = parse_qs(urlparse(self.path).query)
                q = qs.get('q', [''])[0].strip().lstrip('@').lower()
                try:
                    limit = max(1, min(60, int(qs.get('limit', ['30'])[0])))
                except Exception:
                    limit = 30
                try:
                    offset = max(0, int(qs.get('offset', ['0'])[0]))
                except Exception:
                    offset = 0
                include_self = (p == '/api/community/users')
                now = int(time.time())
                my_uid = usr['id'] if usr else None
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    params = []
                    where_parts = ['u.is_blocked = 0']
                    if not include_self and my_uid is not None:
                        where_parts.append('u.id != ?')
                        params.append(my_uid)
                    if q:
                        like = '%' + q + '%'
                        where_parts.append('(lower(u.username) LIKE ? OR lower(u.display_name) LIKE ?)')
                        params.extend([like, like])
                    where_sql = ' AND '.join(where_parts)
                    total = conn.execute(f'SELECT COUNT(*) FROM users u WHERE {where_sql}', tuple(params)).fetchone()[0]
                    rows = conn.execute(
                        'SELECT u.id, u.username, u.display_name, u.avatar, u.plan, u.plan_expires_at, u.last_login_at, u.created_at, '
                        's.data_json '
                        f'FROM users u LEFT JOIN user_state s ON s.user_id = u.id '
                        f'WHERE {where_sql} '
                        'ORDER BY u.last_login_at DESC, u.id DESC LIMIT ? OFFSET ?',
                        tuple(params + [limit, offset])
                    ).fetchall()
                    if my_uid is not None:
                        other_uids = [int(r['id']) for r in rows if int(r['id']) != my_uid]
                        fmap = get_friendship_status_map(conn, my_uid, other_uids)
                    else:
                        fmap = {}
                    users_list = []
                    for r in rows:
                        uid = int(r['id'])
                        card = extract_public_user_card(r, now=now, include_details=False)
                        card['friendshipStatus'] = 'self' if (my_uid is not None and uid == my_uid) else fmap.get(uid, 'none')
                        users_list.append(card)
                if p == '/api/community/users' and not q:
                    users_list.sort(key=lambda x: x['points'], reverse=True)
                return self.send_j(200, {
                    'ok': True,
                    'users': users_list,
                    'total': total,
                    'hasMore': (offset + len(users_list)) < total
                })
            if p == '/api/users/profile':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                qs = parse_qs(urlparse(self.path).query)
                target_ident = qs.get('username', [''])[0].strip()
                if not target_ident:
                    return self.send_j(400, {'error': 'Укажите username пользователя'})
                my_uid = usr['id']
                now = int(time.time())
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    row = resolve_target_user(conn, target_ident)
                    if not row:
                        return self.send_j(404, {'error': 'Пользователь не найден'})
                    t_uid = int(row['id'])
                    profile = extract_public_user_card(row, now=now, include_details=True)
                    if t_uid == my_uid:
                        profile['friendshipStatus'] = 'self'
                        profile['isBlockedByMe'] = False
                        profile['hasBlockedMe'] = False
                        profile['isSelf'] = True
                    else:
                        fmap = get_friendship_status_map(conn, my_uid, [t_uid])
                        by_me, by_other = get_block_relation(conn, my_uid, t_uid)
                        profile['friendshipStatus'] = fmap.get(t_uid, 'none')
                        profile['isBlockedByMe'] = by_me
                        profile['hasBlockedMe'] = by_other
                        profile['isSelf'] = False
                return self.send_j(200, {'ok': True, 'profile': profile, 'user': profile, 'isBlockedByMe': profile.get('isBlockedByMe', False)})
            if p == '/api/friends':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                my_uid = usr['id']
                now = int(time.time())
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    f_rows = conn.execute(
                        'SELECT id, requester_id, addressee_id, status, created_at, updated_at '
                        'FROM friendships WHERE requester_id = ? OR addressee_id = ? '
                        'ORDER BY updated_at DESC, id DESC',
                        (my_uid, my_uid)
                    ).fetchall()
                    friends_list = []
                    incoming_list = []
                    outgoing_list = []
                    for fr in f_rows:
                        req_id = int(fr['requester_id'])
                        addr_id = int(fr['addressee_id'])
                        other_uid = addr_id if req_id == my_uid else req_id
                        u_row = conn.execute(
                            'SELECT u.id, u.username, u.display_name, u.avatar, u.plan, u.plan_expires_at, u.last_login_at, u.created_at, '
                            's.data_json FROM users u LEFT JOIN user_state s ON s.user_id = u.id '
                            'WHERE u.id = ? AND u.is_blocked = 0',
                            (other_uid,)
                        ).fetchone()
                        if not u_row:
                            continue
                        card = extract_public_user_card(u_row, now=now, include_details=False)
                        card['requestCreatedAt'] = int(fr['created_at'] or 0)
                        card['requestId'] = int(fr['id'])
                        card['user'] = card
                        if fr['status'] == 'accepted':
                            card['friendshipStatus'] = 'friends'
                            friends_list.append(card)
                        elif fr['status'] == 'pending':
                            if addr_id == my_uid:
                                card['friendshipStatus'] = 'incoming'
                                incoming_list.append(card)
                            else:
                                card['friendshipStatus'] = 'outgoing'
                                outgoing_list.append(card)
                return self.send_j(200, {
                    'ok': True,
                    'friends': friends_list,
                    'incoming': incoming_list,
                    'outgoing': outgoing_list
                })
            if p == '/api/messages/conversations':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                my_uid = usr['id']
                now = int(time.time())
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    # Mark undelivered incoming messages as delivered
                    conn.execute(
                        'UPDATE messages SET delivered_at = ? WHERE recipient_id = ? AND delivered_at = 0 AND deleted_at = 0',
                        (now, my_uid)
                    )
                    c_rows = conn.execute(
                        'SELECT id, user1_id, user2_id, created_at, last_message_at, last_message_text, last_sender_id, '
                        'user1_hidden_at, user2_hidden_at '
                        'FROM conversations WHERE user1_id = ? OR user2_id = ? '
                        'ORDER BY last_message_at DESC, id DESC LIMIT 100',
                        (my_uid, my_uid)
                    ).fetchall()
                    convs = []
                    for c in c_rows:
                        cid = int(c['id'])
                        u1 = int(c['user1_id'])
                        u2 = int(c['user2_id'])
                        is_u1 = (my_uid == u1)
                        peer_uid = u2 if is_u1 else u1
                        hidden_at = int(c['user1_hidden_at'] if is_u1 else c['user2_hidden_at'] or 0)
                        last_msg_at = int(c['last_message_at'] or 0)
                        if hidden_at > 0 and last_msg_at <= hidden_at:
                            continue
                        p_row = conn.execute(
                            'SELECT u.id, u.username, u.display_name, u.avatar, u.plan, u.plan_expires_at, u.last_login_at, u.created_at, '
                            's.data_json FROM users u LEFT JOIN user_state s ON s.user_id = u.id '
                            'WHERE u.id = ?',
                            (peer_uid,)
                        ).fetchone()
                        if not p_row:
                            continue
                        peer_card = extract_public_user_card(p_row, now=now, include_details=False)
                        unread_cnt = conn.execute(
                            'SELECT COUNT(*) FROM messages '
                            'WHERE conversation_id = ? AND recipient_id = ? AND read_at = 0 AND deleted_at = 0 AND created_at > ?',
                            (cid, my_uid, hidden_at)
                        ).fetchone()[0]
                        by_me, by_other = get_block_relation(conn, my_uid, peer_uid)
                        convs.append({
                            'id': cid,
                            'peer': peer_card,
                            'lastMessageText': str(c['last_message_text'] or ''),
                            'lastMessageAt': last_msg_at or int(c['created_at'] or 0),
                            'lastMessageFromMe': int(c['last_sender_id'] or 0) == my_uid,
                            'unreadCount': int(unread_cnt),
                            'isBlockedByMe': by_me,
                            'hasBlockedMe': by_other
                        })
                    conn.commit()
                return self.send_j(200, {'ok': True, 'conversations': convs})
            if p == '/api/messages/history':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                qs = parse_qs(urlparse(self.path).query)
                try:
                    cid = int(qs.get('conversationId', ['0'])[0])
                except Exception:
                    cid = 0
                try:
                    before_id = int(qs.get('beforeId', ['0'])[0])
                except Exception:
                    before_id = 0
                try:
                    limit = max(1, min(80, int(qs.get('limit', ['40'])[0])))
                except Exception:
                    limit = 40
                if cid <= 0:
                    return self.send_j(400, {'error': 'Укажите conversationId'})
                my_uid = usr['id']
                now = int(time.time())
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    c_row = conn.execute(
                        'SELECT id, user1_id, user2_id, user1_hidden_at, user2_hidden_at '
                        'FROM conversations WHERE id = ?',
                        (cid,)
                    ).fetchone()
                    if not c_row:
                        return self.send_j(404, {'error': 'Диалог не найден'})
                    u1 = int(c_row['user1_id'])
                    u2 = int(c_row['user2_id'])
                    if my_uid not in (u1, u2):
                        return self.send_j(403, {'error': 'Нет доступа к чужому диалогу'})
                    is_u1 = (my_uid == u1)
                    peer_uid = u2 if is_u1 else u1
                    hidden_at = int(c_row['user1_hidden_at'] if is_u1 else c_row['user2_hidden_at'] or 0)
                    p_row = conn.execute(
                        'SELECT u.id, u.username, u.display_name, u.avatar, u.plan, u.plan_expires_at, u.last_login_at, u.created_at, '
                        's.data_json FROM users u LEFT JOIN user_state s ON s.user_id = u.id WHERE u.id = ?',
                        (peer_uid,)
                    ).fetchone()
                    peer_card = extract_public_user_card(p_row, now=now, include_details=False) if p_row else {'username': 'user', 'name': 'User', 'handle': '@user'}
                    by_me, by_other = get_block_relation(conn, my_uid, peer_uid)
                    fmap = get_friendship_status_map(conn, my_uid, [peer_uid])
                    peer_card['friendshipStatus'] = fmap.get(peer_uid, 'none')

                    conn.execute(
                        'UPDATE messages SET delivered_at = ? '
                        'WHERE conversation_id = ? AND recipient_id = ? AND delivered_at = 0 AND deleted_at = 0',
                        (now, cid, my_uid)
                    )
                    q_params = [cid, hidden_at]
                    id_clause = ''
                    if before_id > 0:
                        id_clause = ' AND id < ?'
                        q_params.append(before_id)
                    q_params.append(limit + 1)
                    m_rows = conn.execute(
                        'SELECT id, sender_id, body, created_at, delivered_at, read_at, deleted_at '
                        f'FROM messages WHERE conversation_id = ? AND created_at > ?{id_clause} '
                        'ORDER BY id DESC LIMIT ?',
                        tuple(q_params)
                    ).fetchall()
                    has_more = len(m_rows) > limit
                    m_slice = list(reversed(m_rows[:limit]))
                    msgs = []
                    for m in m_slice:
                        is_del = int(m['deleted_at'] or 0) > 0
                        is_mine = int(m['sender_id']) == my_uid
                        read_ts = int(m['read_at'] or 0)
                        deliv_ts = int(m['delivered_at'] or 0)
                        st_lbl = 'read' if read_ts > 0 else ('delivered' if deliv_ts > 0 else 'sent')
                        msgs.append({
                            'id': int(m['id']),
                            'fromMe': is_mine,
                            'text': '' if is_del else str(m['body'] or ''),
                            'isDeleted': is_del,
                            'createdAt': int(m['created_at'] or 0),
                            'status': st_lbl
                        })
                    conn.commit()
                return self.send_j(200, {
                    'ok': True,
                    'conversationId': cid,
                    'peer': peer_card,
                    'isBlockedByMe': by_me,
                    'hasBlockedMe': by_other,
                    'messages': msgs,
                    'hasMore': has_more
                })
            if p == '/api/messages/unread-count':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                my_uid = usr['id']
                now = int(time.time())
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    conn.execute(
                        'UPDATE messages SET delivered_at = ? WHERE recipient_id = ? AND delivered_at = 0 AND deleted_at = 0',
                        (now, my_uid)
                    )
                    # Count unread messages only in non-hidden ranges
                    unread_rows = conn.execute(
                        'SELECT m.id, m.conversation_id, m.sender_id, m.body, m.created_at, '
                        'c.user1_id, c.user1_hidden_at, c.user2_hidden_at, u.username, u.display_name '
                        'FROM messages m '
                        'JOIN conversations c ON c.id = m.conversation_id '
                        'JOIN users u ON u.id = m.sender_id '
                        'WHERE m.recipient_id = ? AND m.read_at = 0 AND m.deleted_at = 0 '
                        'ORDER BY m.id DESC',
                        (my_uid,)
                    ).fetchall()
                    valid_unreads = []
                    for r in unread_rows:
                        h_at = int(r['user1_hidden_at'] if int(r['user1_id']) == my_uid else r['user2_hidden_at'] or 0)
                        if int(r['created_at']) > h_at:
                            valid_unreads.append(r)
                    inc_reqs = conn.execute(
                        'SELECT COUNT(*) FROM friendships WHERE addressee_id = ? AND status = "pending"',
                        (my_uid,)
                    ).fetchone()[0]
                    conn.commit()
                latest_msg = None
                if valid_unreads:
                    top = valid_unreads[0]
                    latest_msg = {
                        'id': int(top['id']),
                        'conversationId': int(top['conversation_id']),
                        'senderUsername': str(top['username'] or '').lower(),
                        'senderName': str(top['display_name'] or top['username'] or ''),
                        'text': str(top['body'] or '')[:120],
                        'createdAt': int(top['created_at'] or 0)
                    }
                return self.send_j(200, {
                    'ok': True,
                    'unreadCount': len(valid_unreads),
                    'incomingRequestsCount': int(inc_reqs),
                    'latestMessage': latest_msg
                })
            if p == '/api/ai/settings' and self.authed():
                c = ai_cfg()
                return self.send_j(200, {'provider': c['provider'], 'baseUrl': c.get('base_url', ''), 'hasKey': bool(c.get('key')), 'keyHint': ('…' + c['key'][-4:]) if c.get('key') else '', 'model': c['model'], 'enabled': c['enabled'], 'prompt': c.get('prompt', '')})
            if p == '/api/uploads' and self.authed():
                return self.send_j(200, sorted(os.listdir(UPLOADS)))
            if p == '/api/admin/users' and self.authed():
                q = parse_qs(urlparse(self.path).query).get('q', [''])[0].strip().lower()
                now = int(time.time())
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    if q:
                        like = '%' + q + '%'
                        rows = conn.execute(
                            'SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked, created_at, last_login_at '
                            'FROM users WHERE lower(username) LIKE ? OR lower(email) LIKE ? ORDER BY id DESC LIMIT 200',
                            (like, like)
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            'SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked, created_at, last_login_at '
                            'FROM users ORDER BY id DESC LIMIT 200'
                        ).fetchall()
                    tot = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
                    pro_cnt = conn.execute(
                        'SELECT COUNT(*) FROM users WHERE plan = "pro" AND is_blocked = 0 AND (plan_expires_at = 0 OR plan_expires_at > ?)',
                        (now,)
                    ).fetchone()[0]
                    blk_cnt = conn.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1').fetchone()[0]
                    pays = conn.execute(
                        'SELECT p.id, u.username, p.plan, p.days, p.amount, p.currency, p.provider, p.status, p.note, p.created_at '
                        'FROM payments p LEFT JOIN users u ON u.id = p.user_id ORDER BY p.id DESC LIMIT 40'
                    ).fetchall()
                users_list = []
                for r in rows:
                    dto = user_dto(r[:7], respect_free_mode=False)
                    dto['createdAt'] = r[7]
                    dto['lastLoginAt'] = r[8]
                    users_list.append(dto)
                pay_list = [
                    {
                        'id': x[0], 'username': x[1] or '?', 'plan': x[2], 'days': x[3],
                        'amount': x[4], 'currency': x[5], 'provider': x[6], 'status': x[7],
                        'note': x[8], 'createdAt': x[9]
                    } for x in pays
                ]
                return self.send_j(200, {'users': users_list, 'stats': {'total': tot, 'pro': pro_cnt, 'blocked': blk_cnt}, 'payments': pay_list})
            if p == '/api/user/me':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                return self.send_j(200, {'user': usr})
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
            if p == '/api/payment/plans':
                cfg = yookassa_cfg()
                return self.send_j(200, {
                    'plans': list(PLANS.values()),
                    'sbpOnly': cfg.get('sbp_only', True),
                    'enabled': False if FREE_ACCESS_MODE else bool(cfg.get('enabled') and cfg.get('shop_id') and cfg.get('secret_key')),
                    'freeAccessMode': bool(FREE_ACCESS_MODE)
                })
            if p == '/api/payment/check':
                tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
                usr = get_user_by_token(tok)
                if not usr:
                    return self.send_j(401, {'error': 'unauthorized'})
                pid = parse_qs(urlparse(self.path).query).get('paymentId', [''])[0].strip()
                if not pid:
                    return self.send_j(400, {'error': 'Укажите paymentId'})
                with db_lock, sqlite3.connect(DB_FILE) as conn:
                    owner_row = conn.execute(
                        'SELECT user_id FROM payments WHERE payment_id = ?',
                        (pid,)
                    ).fetchone()
                if not owner_row:
                    return self.send_j(404, {'error': 'Платеж не найден'})
                if owner_row[0] != usr['id']:
                    return self.send_j(403, {'error': 'forbidden'})
                res = sync_pending_yookassa_payment(pid)
                if not res:
                    return self.send_j(404, {'error': 'Платеж не найден'})
                st = res['status']
                return self.send_j(200, {
                    'ok': True,
                    'status': st,
                    'isPro': True if (st == 'paid' or FREE_ACCESS_MODE) else False,
                    'freeAccessMode': bool(FREE_ACCESS_MODE)
                })
            if p == '/api/admin/yookassa' and self.authed():
                cfg = yookassa_cfg()
                host = self.headers.get('Host') or 'rizzafit.ru'
                proto = 'https' if not host.startswith('localhost') else 'http'
                webhook_url = f'{proto}://{host}/api/payment/yookassa/webhook'
                return self.send_j(200, {
                    'enabled': bool(cfg.get('enabled')),
                    'shopId': str(cfg.get('shop_id', '')),
                    'hasKey': bool(cfg.get('secret_key')),
                    'keyHint': ('…' + cfg['secret_key'][-4:]) if cfg.get('secret_key') else '',
                    'sbpOnly': bool(cfg.get('sbp_only', True)),
                    'webhookUrl': webhook_url,
                    'plans': list(PLANS.values())
                })
            if p == '/api/auth/telegram/poll':
                q_token = parse_qs(urlparse(self.path).query).get('token', [''])[0].strip()
                if not q_token:
                    return self.send_j(200, {'ok': True, 'confirmed': False})
                now_ts = time.time()
                with tg_auth_lock:
                    rec = tg_pending_auth.get(q_token)
                    if not rec:
                        return self.send_j(200, {'ok': True, 'confirmed': False})
                    if (now_ts - rec.get('created_at', 0)) > TG_AUTH_TTL:
                        tg_pending_auth.pop(q_token, None)
                        return self.send_j(200, {'ok': True, 'confirmed': False})
                    if rec.get('status') == 'blocked':
                        tg_pending_auth.pop(q_token, None)
                        return self.send_j(403, {
                            'ok': False,
                            'confirmed': False,
                            'error': rec.get('error', 'Аккаунт заблокирован администратором')
                        })
                    if rec.get('status') == 'confirmed':
                        rec = tg_pending_auth.pop(q_token, None)
                        return self.send_j(200, {
                            'ok': True,
                            'confirmed': True,
                            'sessionToken': rec.get('sessionToken'),
                            'user': rec.get('user'),
                            'state': rec.get('state'),
                            'updatedAt': rec.get('updatedAt', 0)
                        })
                return self.send_j(200, {'ok': True, 'confirmed': False})
            if p == '/api/admin/telegram' and self.authed():
                cfg = telegram_cfg()
                return self.send_j(200, {
                    'ok': True,
                    'botUsername': cfg.get('bot_username', ''),
                    'enabled': cfg.get('enabled', True),
                    'hasToken': bool(cfg.get('bot_token'))
                })
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
            ip = self.headers.get('X-Real-IP') or self.client_address[0]
            c, last = fails.get('reg:' + ip, (0, 0))
            if c >= 10 and time.time() - last < 300:
                return self.send_j(429, {'error': 'Слишком много регистраций, подождите 5 минут'})
            try:
                raw_b = self.body(2 * 1024 * 1024)
                if raw_b is None:
                    return self.send_j(413, {'error': 'Слишком большой запрос'})
                j = json.loads(raw_b or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            uname = re.sub(r'[^a-z0-9_]', '', str(j.get('username') or '').strip().lower())
            email = str(j.get('email') or '').strip().lower()
            pw = str(j.get('password') or '')
            dname = str(j.get('displayName') or uname)[:40].strip()
            if len(uname) < 3 or len(uname) > 24:
                return self.send_j(400, {'error': 'Логин: от 3 до 24 латинских букв/цифр/_'})
            if not EMAIL_RE.match(email):
                return self.send_j(400, {'error': 'Укажите корректный Email'})
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
                if conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone():
                    return self.send_j(409, {'error': 'Этот Email уже зарегистрирован'})
                cur = conn.execute(
                    'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                    'VALUES (?, ?, ?, ?, ?, "free", 0, 0, ?, ?)',
                    (uname, salt, pwh, dname, email, now, now)
                )
                uid = cur.lastrowid
                conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tok, uid, now + 30 * 86400))
                if state:
                    conn.execute('INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?)', (uid, json.dumps(state, ensure_ascii=False), now))
                conn.commit()
            if len(fails) > 400:
                fails.clear()
            fails['reg:' + ip] = (c + 1, time.time())
            usr = user_dto((uid, uname, dname, email, 'free', 0, 0))
            return self.send_j(200, {'token': tok, 'user': usr, 'state': state, 'updatedAt': now if state else 0})
        if p == '/api/user/login':
            ip = self.headers.get('X-Real-IP') or self.client_address[0]
            c, last = fails.get(ip, (0, 0))
            if c >= 8 and time.time() - last < 60:
                return self.send_j(429, {'error': 'Слишком много попыток, подождите минуту'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            raw_login = str(j.get('username') or j.get('email') or '').strip().lower()
            pw = str(j.get('password') or '')
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                if '@' in raw_login:
                    row = conn.execute(
                        'SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked, pw_salt, pw_hash '
                        'FROM users WHERE email = ?', (raw_login,)
                    ).fetchone()
                else:
                    uname = re.sub(r'[^a-z0-9_]', '', raw_login)
                    row = conn.execute(
                        'SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked, pw_salt, pw_hash '
                        'FROM users WHERE username = ?', (uname,)
                    ).fetchone()
                if not row or not hmac.compare_digest(hash_pw(pw, row[7]), row[8]):
                    if len(fails) > 400:
                        fails.clear()
                    fails[ip] = (c + 1, time.time())
                    time.sleep(0.5)
                    return self.send_j(401, {'error': 'Неверный логин/email или пароль'})
                if row[6]:
                    return self.send_j(403, {'error': 'Аккаунт заблокирован администратором'})
                fails.pop(ip, None)
                now = int(time.time())
                tok = secrets.token_urlsafe(32)
                conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (now, row[0]))
                conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tok, row[0], now + 30 * 86400))
                st_row = conn.execute('SELECT data_json, updated_at FROM user_state WHERE user_id = ?', (row[0],)).fetchone()
                conn.commit()
            state = json.loads(st_row[0]) if st_row else {}
            updated_at = st_row[1] if st_row else 0
            return self.send_j(200, {'token': tok, 'user': user_dto(row[:7]), 'state': state, 'updatedAt': updated_at})
        if p == '/api/auth/telegram/start':
            auth_token = secrets.token_urlsafe(16)
            now_ts = time.time()
            with tg_auth_lock:
                tg_pending_auth[auth_token] = {'created_at': now_ts, 'status': 'pending'}
                for k in list(tg_pending_auth.keys()):
                    if now_ts - tg_pending_auth[k].get('created_at', 0) > TG_AUTH_TTL:
                        tg_pending_auth.pop(k, None)
            cfg = telegram_cfg()
            buser = cfg.get('bot_username', '').lstrip('@').strip()
            configured = bool(cfg.get('bot_token') and buser and cfg.get('enabled', True))
            url = f"https://t.me/{buser}?start=auth_{auth_token}" if (buser and configured) else ""
            return self.send_j(200, {
                'ok': True,
                'token': auth_token,
                'botUsername': buser,
                'url': url,
                'configured': configured
            })
        if p == '/api/user/social-login':
            ip = self.headers.get('X-Real-IP') or self.client_address[0]
            c, last = fails.get('soc:' + ip, (0, 0))
            if c >= 20 and time.time() - last < 60:
                return self.send_j(429, {'error': 'Слишком много попыток, подождите минуту'})
            try:
                raw_b = self.body(2 * 1024 * 1024)
                if raw_b is None:
                    return self.send_j(413, {'error': 'Слишком большой запрос'})
                j = json.loads(raw_b or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})

            provider = str(j.get('provider') or '').strip().lower()
            if provider in ('vk', 'google', 'yandex'):
                return self.send_j(501, {'error': 'Вход через данного провайдера временно отключён. Используйте Telegram или логин и пароль.'})
            if provider != 'telegram':
                return self.send_j(400, {'error': 'Неизвестный провайдер соцсети'})

            init_data = str(j.get('initData') or '').strip()
            if not init_data:
                if len(fails) > 400:
                    fails.clear()
                fails['soc:' + ip] = (c + 1, time.time())
                return self.send_j(401, {'error': 'Требуется подтверждённая подпись Telegram WebApp (initData)'})

            cfg = telegram_cfg()
            bot_token = cfg.get('bot_token', '').strip()
            if not bot_token or not cfg.get('enabled', True):
                return self.send_j(503, {'error': 'Telegram-авторизация не настроена на сервере'})

            tg_user = verify_telegram_webapp_init_data(init_data, bot_token)
            if not tg_user:
                if len(fails) > 400:
                    fails.clear()
                fails['soc:' + ip] = (c + 1, time.time())
                return self.send_j(401, {'error': 'Недействительная или устаревшая подпись Telegram'})

            social_id = str(tg_user.get('id') or '').strip()
            raw_username = str(tg_user.get('username') or '').strip().lower()
            fname = str(tg_user.get('first_name') or '').strip()
            lname = str(tg_user.get('last_name') or '').strip()
            display_name = (f"{fname} {lname}".strip() or raw_username or f"User {social_id}")[:40]
            avatar = str(tg_user.get('photo_url') or '').strip()
            email = ''

            now = int(time.time())
            state = sanitize_state(j.get('state'))
            tok = secrets.token_urlsafe(32)

            with db_lock, sqlite3.connect(DB_FILE) as conn:
                # Look up strictly by verified (oauth_provider, oauth_id); never auto-link by email
                row = conn.execute(
                    'SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked, avatar '
                    'FROM users WHERE oauth_provider = ? AND oauth_id = ?',
                    ('telegram', social_id)
                ).fetchone()

                if row:
                    if row[6]: # is_blocked
                        return self.send_j(403, {'error': 'Аккаунт заблокирован администратором'})
                    uid = row[0]
                    conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (now, uid))
                    if avatar and not row[7]:
                        conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (avatar, uid))
                    conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tok, uid, now + 30 * 86400))
                    st_row = conn.execute('SELECT data_json, updated_at FROM user_state WHERE user_id = ?', (uid,)).fetchone()
                    conn.commit()
                    fails.pop('soc:' + ip, None)
                    user_data = user_dto((row[0], row[1], row[2], row[3], row[4], row[5], row[6], avatar or row[7]))
                    user_st = json.loads(st_row[0]) if st_row else {}
                    up_at = st_row[1] if st_row else 0
                    return self.send_j(200, {'ok': True, 'token': tok, 'user': user_data, 'state': user_st, 'updatedAt': up_at})

                # Create new verified Telegram user
                clean_name = re.sub(r'[^a-z0-9_]', '', raw_username)
                if len(clean_name) < 3:
                    clean_name = f"tg_{re.sub(r'[^a-z0-9_]', '', social_id)[:10]}"
                clean_name = clean_name[:20]
                uname = clean_name
                idx = 1
                while conn.execute('SELECT 1 FROM users WHERE username = ?', (uname,)).fetchone():
                    uname = f"{clean_name[:16]}_{idx}"
                    idx += 1

                cur = conn.execute(
                    'INSERT INTO users (username, pw_salt, pw_hash, display_name, email, oauth_provider, oauth_id, avatar, plan, plan_expires_at, is_blocked, last_login_at, created_at) '
                    'VALUES (?, "", "", ?, ?, ?, ?, ?, "free", 0, 0, ?, ?)',
                    (uname, display_name, email, 'telegram', social_id, avatar, now, now)
                )
                uid = cur.lastrowid
                conn.execute('INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)', (tok, uid, now + 30 * 86400))
                if state:
                    conn.execute('INSERT INTO user_state (user_id, data_json, updated_at) VALUES (?, ?, ?)', (uid, json.dumps(state, ensure_ascii=False), now))
                conn.commit()

            fails.pop('soc:' + ip, None)
            new_user = user_dto((uid, uname, display_name, email, 'free', 0, 0, avatar))
            return self.send_j(200, {'ok': True, 'token': tok, 'user': new_user, 'state': state, 'updatedAt': now if state else 0})
        if p == '/api/user/profile':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                if 'email' in j:
                    em = str(j.get('email') or '').strip().lower()
                    if not EMAIL_RE.match(em):
                        return self.send_j(400, {'error': 'Укажите корректный Email'})
                    exists = conn.execute('SELECT id FROM users WHERE email = ? AND id != ?', (em, usr['id'])).fetchone()
                    if exists:
                        return self.send_j(409, {'error': 'Этот Email уже используется'})
                    conn.execute('UPDATE users SET email = ? WHERE id = ?', (em, usr['id']))
                if j.get('newPassword'):
                    old_pw = str(j.get('oldPassword') or '')
                    new_pw = str(j.get('newPassword') or '')
                    if len(new_pw) < 6:
                        return self.send_j(400, {'error': 'Новый пароль: минимум 6 символов'})
                    pw_row = conn.execute('SELECT pw_salt, pw_hash FROM users WHERE id = ?', (usr['id'],)).fetchone()
                    if not pw_row or not hmac.compare_digest(hash_pw(old_pw, pw_row[0]), pw_row[1]):
                        return self.send_j(400, {'error': 'Старый пароль указан неверно'})
                    nsalt = secrets.token_hex(16)
                    conn.execute('UPDATE users SET pw_salt = ?, pw_hash = ? WHERE id = ?', (nsalt, hash_pw(new_pw, nsalt), usr['id']))
                row = conn.execute('SELECT id, username, display_name, email, plan, plan_expires_at, is_blocked FROM users WHERE id = ?', (usr['id'],)).fetchone()
                conn.commit()
            return self.send_j(200, {'ok': True, 'user': user_dto(row)})
        if p == '/api/user/reset/confirm':
            ip = self.headers.get('X-Real-IP') or self.client_address[0]
            c, last = fails.get('rst:' + ip, (0, 0))
            if c >= 8 and time.time() - last < 300:
                return self.send_j(429, {'error': 'Слишком много попыток, подождите 5 минут'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            code = str(j.get('code') or '').strip().upper()
            new_pw = str(j.get('newPassword') or '')
            if len(new_pw) < 6:
                return self.send_j(400, {'error': 'Пароль: минимум 6 символов'})
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                r = conn.execute('SELECT user_id, expires_at, used FROM password_resets WHERE code = ?', (code,)).fetchone()
                if not r or r[2] or r[1] < now:
                    fails['rst:' + ip] = (c + 1, time.time())
                    return self.send_j(400, {'error': 'Неверный или просроченный код сброса'})
                nsalt = secrets.token_hex(16)
                conn.execute('UPDATE users SET pw_salt = ?, pw_hash = ? WHERE id = ?', (nsalt, hash_pw(new_pw, nsalt), r[0]))
                conn.execute('UPDATE password_resets SET used = 1 WHERE code = ?', (code,))
                conn.execute('DELETE FROM user_sessions WHERE user_id = ?', (r[0],))
                conn.commit()
            fails.pop('rst:' + ip, None)
            return self.send_j(200, {'ok': True})
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
                if 'athleteProfile' in state:
                    try:
                        ap_obj = json.loads(state['athleteProfile'])
                        if isinstance(ap_obj, dict):
                            ap_name = str(ap_obj.get('name') or '').strip()[:40]
                            if ap_name and ap_name not in ('Mr.Bobrovsky', 'Атлет', 'Athlete'):
                                conn.execute('UPDATE users SET display_name = ? WHERE id = ?', (ap_name, usr['id']))
                    except Exception:
                        pass
                conn.commit()
            return self.send_j(200, {'ok': True, 'updatedAt': now})
        if p in ('/api/friends/request', '/api/friends/accept', '/api/friends/decline', '/api/friends/cancel', '/api/friends/remove'):
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            req_id_raw = j.get('requestId')
            target_ident = str(j.get('targetUserId') or j.get('targetId') or j.get('userId') or j.get('username') or j.get('handle') or '').strip()
            if not target_ident and not req_id_raw:
                return self.send_j(400, {'error': 'Укажите пользователя или requestId'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                existing = None
                t_uid = None
                if req_id_raw:
                    try:
                        r_id = int(req_id_raw)
                        existing = conn.execute(
                            'SELECT id, requester_id, addressee_id, status FROM friendships WHERE id = ?',
                            (r_id,)
                        ).fetchone()
                    except Exception:
                        existing = None
                    if existing:
                        t_uid = int(existing[1]) if int(existing[2]) == my_uid else int(existing[2])
                if not existing and target_ident:
                    t_row = resolve_target_user(conn, target_ident)
                    if not t_row:
                        return self.send_j(404, {'error': 'Пользователь не найден'})
                    t_uid = int(t_row['id'])
                    if t_uid == my_uid:
                        return self.send_j(400, {'error': 'Нельзя добавить в друзья самого себя'})
                    p_min = min(my_uid, t_uid)
                    p_max = max(my_uid, t_uid)
                    existing = conn.execute(
                        'SELECT id, requester_id, addressee_id, status FROM friendships WHERE pair_min = ? AND pair_max = ?',
                        (p_min, p_max)
                    ).fetchone()
                if not existing and not t_uid:
                    return self.send_j(404, {'error': 'Заявка или пользователь не найдены'})

                if p == '/api/friends/request':
                    if not t_uid:
                        return self.send_j(400, {'error': 'Укажите пользователя'})
                    by_me, by_other = get_block_relation(conn, my_uid, t_uid)
                    if by_me or by_other:
                        return self.send_j(403, {'error': 'Действие недоступно из-за ограничений блокировки'})
                    if existing:
                        fid, req_id, addr_id, st = int(existing[0]), int(existing[1]), int(existing[2]), existing[3]
                        if st == 'accepted':
                            return self.send_j(400, {'error': 'Вы уже друзья', 'friendshipStatus': 'friends'})
                        if req_id == my_uid:
                            return self.send_j(400, {'error': 'Заявка уже отправлена', 'friendshipStatus': 'outgoing'})
                        # Counter-request exists from target -> auto-accept!
                        conn.execute('UPDATE friendships SET status = "accepted", updated_at = ? WHERE id = ?', (now, fid))
                        conn.commit()
                        return self.send_j(200, {'ok': True, 'friendshipStatus': 'friends', 'autoAccepted': True})
                    p_min = min(my_uid, t_uid)
                    p_max = max(my_uid, t_uid)
                    cur = conn.execute(
                        'INSERT INTO friendships (requester_id, addressee_id, pair_min, pair_max, status, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, "pending", ?, ?)',
                        (my_uid, t_uid, p_min, p_max, now, now)
                    )
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'friendshipStatus': 'outgoing', 'requestId': cur.lastrowid})

                if p == '/api/friends/accept':
                    if not existing or existing[3] != 'pending':
                        return self.send_j(404, {'error': 'Входящая заявка не найдена'})
                    if int(existing[2]) != my_uid:
                        return self.send_j(403, {'error': 'Нельзя принять чужую заявку'})
                    conn.execute('UPDATE friendships SET status = "accepted", updated_at = ? WHERE id = ?', (now, int(existing[0])))
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'friendshipStatus': 'friends'})

                if p == '/api/friends/decline':
                    if not existing or existing[3] != 'pending':
                        return self.send_j(404, {'error': 'Входящая заявка не найдена'})
                    if int(existing[2]) != my_uid:
                        return self.send_j(403, {'error': 'Нельзя отклонить чужую заявку'})
                    conn.execute('DELETE FROM friendships WHERE id = ?', (int(existing[0]),))
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'friendshipStatus': 'none'})

                if p == '/api/friends/cancel':
                    if not existing or existing[3] != 'pending':
                        return self.send_j(404, {'error': 'Исходящая заявка не найдена'})
                    if int(existing[1]) != my_uid:
                        return self.send_j(403, {'error': 'Нельзя отменить чужую заявку'})
                    conn.execute('DELETE FROM friendships WHERE id = ?', (int(existing[0]),))
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'friendshipStatus': 'none'})

                if p == '/api/friends/remove':
                    if not existing or existing[3] != 'accepted':
                        return self.send_j(404, {'error': 'Пользователь не находится в списке друзей'})
                    conn.execute('DELETE FROM friendships WHERE id = ?', (int(existing[0]),))
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'friendshipStatus': 'none'})

        if p == '/api/messages/open':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            target_ident = str(j.get('targetUserId') or j.get('targetId') or j.get('userId') or j.get('username') or j.get('handle') or '').strip()
            if not target_ident:
                return self.send_j(400, {'error': 'Укажите собеседника'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                t_row = resolve_target_user(conn, target_ident)
                if not t_row:
                    return self.send_j(404, {'error': 'Пользователь не найден'})
                t_uid = int(t_row['id'])
                if t_uid == my_uid:
                    return self.send_j(400, {'error': 'Нельзя начать чат с самим собой'})
                by_me, by_other = get_block_relation(conn, my_uid, t_uid)
                if by_me or by_other:
                    return self.send_j(403, {'error': 'Переписка недоступна из-за блокировки пользователя'})
                u1 = min(my_uid, t_uid)
                u2 = max(my_uid, t_uid)
                c_row = conn.execute(
                    'SELECT id, user1_hidden_at, user2_hidden_at FROM conversations WHERE user1_id = ? AND user2_id = ?',
                    (u1, u2)
                ).fetchone()
                if c_row:
                    cid = int(c_row[0])
                else:
                    cur = conn.execute(
                        'INSERT INTO conversations (user1_id, user2_id, created_at, last_message_at, last_message_text, last_sender_id) '
                        'VALUES (?, ?, ?, ?, "", 0)',
                        (u1, u2, now, now)
                    )
                    cid = cur.lastrowid
                peer_card = extract_public_user_card(t_row, now=now, include_details=False)
                fmap = get_friendship_status_map(conn, my_uid, [t_uid])
                peer_card['friendshipStatus'] = fmap.get(t_uid, 'none')
                conn.commit()
            conv_obj = {'id': cid, 'peer': peer_card}
            return self.send_j(200, {'ok': True, 'conversationId': cid, 'conversation': conv_obj, 'peer': peer_card})

        if p == '/api/messages/send':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                raw_b = self.body(32 * 1024)
                if raw_b is None:
                    return self.send_j(413, {'error': 'Слишком длинный запрос'})
                j = json.loads(raw_b or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            text = str(j.get('text') or '').strip()
            if not text:
                return self.send_j(400, {'error': 'Сообщение не может быть пустым'})
            if len(text) > 2000:
                return self.send_j(400, {'error': 'Сообщение слишком длинное (максимум 2000 символов)'})
            client_msg_id = re.sub(r'[^a-zA-Z0-9_:-]', '', str(j.get('clientMsgId') or '').strip())[:64]
            my_uid = usr['id']
            now = int(time.time())

            with db_lock, sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                # Idempotency check first before consuming rate-limit token
                if client_msg_id:
                    dup = conn.execute(
                        'SELECT id, conversation_id, body, created_at, delivered_at, read_at '
                        'FROM messages WHERE sender_id = ? AND client_msg_id = ?',
                        (my_uid, client_msg_id)
                    ).fetchone()
                    if dup:
                        st_lbl = 'read' if int(dup['read_at'] or 0) > 0 else ('delivered' if int(dup['delivered_at'] or 0) > 0 else 'sent')
                        return self.send_j(200, {
                            'ok': True,
                            'conversationId': int(dup['conversation_id']),
                            'message': {
                                'id': int(dup['id']),
                                'fromMe': True,
                                'text': str(dup['body']),
                                'isDeleted': False,
                                'createdAt': int(dup['created_at']),
                                'status': st_lbl
                            },
                            'deduplicated': True
                        })

                cid = 0
                try:
                    cid = int(j.get('conversationId') or 0)
                except Exception:
                    cid = 0
                target_ident = str(j.get('username') or j.get('handle') or '').strip()

                if cid > 0:
                    c_row = conn.execute('SELECT id, user1_id, user2_id FROM conversations WHERE id = ?', (cid,)).fetchone()
                    if not c_row:
                        return self.send_j(404, {'error': 'Диалог не найден'})
                    u1, u2 = int(c_row['user1_id']), int(c_row['user2_id'])
                    if my_uid not in (u1, u2):
                        return self.send_j(403, {'error': 'Нет доступа к чужому диалогу'})
                    peer_uid = u2 if my_uid == u1 else u1
                elif target_ident:
                    t_row = resolve_target_user(conn, target_ident)
                    if not t_row:
                        return self.send_j(404, {'error': 'Получатель не найден'})
                    peer_uid = int(t_row['id'])
                    if peer_uid == my_uid:
                        return self.send_j(400, {'error': 'Нельзя отправить сообщение самому себе'})
                    u1, u2 = min(my_uid, peer_uid), max(my_uid, peer_uid)
                    c_row = conn.execute('SELECT id FROM conversations WHERE user1_id = ? AND user2_id = ?', (u1, u2)).fetchone()
                    if c_row:
                        cid = int(c_row['id'])
                    else:
                        by_me, by_other = get_block_relation(conn, my_uid, peer_uid)
                        if by_me or by_other:
                            return self.send_j(403, {'error': 'Отправка невозможна: один из пользователей заблокировал переписку'})
                        cur = conn.execute(
                            'INSERT INTO conversations (user1_id, user2_id, created_at, last_message_at, last_message_text, last_sender_id) '
                            'VALUES (?, ?, ?, ?, "", 0)',
                            (u1, u2, now, now)
                        )
                        cid = cur.lastrowid
                else:
                    return self.send_j(400, {'error': 'Укажите conversationId или username получателя'})

                if peer_uid == my_uid:
                    return self.send_j(400, {'error': 'Нельзя отправить сообщение самому себе'})

                by_me, by_other = get_block_relation(conn, my_uid, peer_uid)
                if by_me or by_other:
                    return self.send_j(403, {'error': 'Отправка невозможна: один из пользователей заблокировал переписку'})

                if not check_message_rate_limit(my_uid):
                    return self.send_j(429, {'error': 'Слишком много сообщений подряд. Подождите несколько секунд.'})

                cur = conn.execute(
                    'INSERT INTO messages (conversation_id, sender_id, recipient_id, body, client_msg_id, created_at, delivered_at, read_at, deleted_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)',
                    (cid, my_uid, peer_uid, text, client_msg_id, now)
                )
                mid = cur.lastrowid
                preview = text[:140]
                conn.execute(
                    'UPDATE conversations SET last_message_at = ?, last_message_text = ?, last_sender_id = ? WHERE id = ?',
                    (now, preview, my_uid, cid)
                )
                conn.commit()
            return self.send_j(200, {
                'ok': True,
                'conversationId': cid,
                'message': {
                    'id': mid,
                    'fromMe': True,
                    'text': text,
                    'isDeleted': False,
                    'createdAt': now,
                    'status': 'sent'
                }
            })

        if p == '/api/messages/read':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
                cid = int(j.get('conversationId') or 0)
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            if cid <= 0:
                return self.send_j(400, {'error': 'Укажите conversationId'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                c_row = conn.execute('SELECT user1_id, user2_id FROM conversations WHERE id = ?', (cid,)).fetchone()
                if not c_row:
                    return self.send_j(404, {'error': 'Диалог не найден'})
                if my_uid not in (int(c_row[0]), int(c_row[1])):
                    return self.send_j(403, {'error': 'Нет доступа к чужому диалогу'})
                cur = conn.execute(
                    'UPDATE messages SET read_at = ?, delivered_at = CASE WHEN delivered_at = 0 THEN ? ELSE delivered_at END '
                    'WHERE conversation_id = ? AND recipient_id = ? AND read_at = 0 AND deleted_at = 0',
                    (now, now, cid, my_uid)
                )
                marked = cur.rowcount
                conn.commit()
            return self.send_j(200, {'ok': True, 'markedCount': marked, 'readCount': marked})

        if p == '/api/messages/delete':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
                mid = int(j.get('messageId') or 0)
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            if mid <= 0:
                return self.send_j(400, {'error': 'Укажите messageId'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                m_row = conn.execute(
                    'SELECT id, conversation_id, sender_id, deleted_at FROM messages WHERE id = ?',
                    (mid,)
                ).fetchone()
                if not m_row:
                    return self.send_j(404, {'error': 'Сообщение не найдено'})
                if int(m_row[2]) != my_uid:
                    return self.send_j(403, {'error': 'Можно удалять только собственные сообщения'})
                cid = int(m_row[1])
                conn.execute(
                    'UPDATE messages SET deleted_at = ?, body = "" WHERE id = ?',
                    (now, mid)
                )
                # Refresh conversation preview from latest non-deleted message
                latest = conn.execute(
                    'SELECT body, sender_id, created_at FROM messages '
                    'WHERE conversation_id = ? AND deleted_at = 0 ORDER BY id DESC LIMIT 1',
                    (cid,)
                ).fetchone()
                if latest:
                    conn.execute(
                        'UPDATE conversations SET last_message_text = ?, last_sender_id = ?, last_message_at = ? WHERE id = ?',
                        (str(latest[0])[:140], int(latest[1]), int(latest[2]), cid)
                    )
                else:
                    conn.execute(
                        'UPDATE conversations SET last_message_text = "" WHERE id = ?',
                        (cid,)
                    )
                conn.commit()
            return self.send_j(200, {'ok': True, 'deletedId': mid})

        if p == '/api/messages/conversation/hide':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
                cid = int(j.get('conversationId') or 0)
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            if cid <= 0:
                return self.send_j(400, {'error': 'Укажите conversationId'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                c_row = conn.execute(
                    'SELECT user1_id, user2_id, last_message_at FROM conversations WHERE id = ?',
                    (cid,)
                ).fetchone()
                if not c_row:
                    return self.send_j(404, {'error': 'Диалог не найден'})
                u1, u2 = int(c_row[0]), int(c_row[1])
                if my_uid not in (u1, u2):
                    return self.send_j(403, {'error': 'Нет доступа к чужому диалогу'})
                hide_ts = max(now, int(c_row[2] or 0))
                if my_uid == u1:
                    conn.execute('UPDATE conversations SET user1_hidden_at = ? WHERE id = ?', (hide_ts, cid))
                else:
                    conn.execute('UPDATE conversations SET user2_hidden_at = ? WHERE id = ?', (hide_ts, cid))
                conn.execute(
                    'UPDATE messages SET read_at = ?, delivered_at = CASE WHEN delivered_at = 0 THEN ? ELSE delivered_at END '
                    'WHERE conversation_id = ? AND recipient_id = ? AND read_at = 0',
                    (now, now, cid, my_uid)
                )
                conn.commit()
            return self.send_j(200, {'ok': True, 'hiddenConversationId': cid})

        if p in ('/api/users/block', '/api/users/unblock'):
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            target_ident = str(j.get('targetUserId') or j.get('targetId') or j.get('userId') or j.get('username') or j.get('handle') or '').strip()
            if not target_ident:
                return self.send_j(400, {'error': 'Укажите пользователя'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                t_row = resolve_target_user(conn, target_ident)
                if not t_row:
                    return self.send_j(404, {'error': 'Пользователь не найден'})
                t_uid = int(t_row['id'])
                if t_uid == my_uid:
                    return self.send_j(400, {'error': 'Нельзя заблокировать самого себя'})
                if p == '/api/users/block':
                    conn.execute(
                        'INSERT OR IGNORE INTO user_blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)',
                        (my_uid, t_uid, now)
                    )
                    conn.execute(
                        'DELETE FROM friendships WHERE pair_min = ? AND pair_max = ?',
                        (min(my_uid, t_uid), max(my_uid, t_uid))
                    )
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'isBlockedByMe': True})
                else:
                    conn.execute(
                        'DELETE FROM user_blocks WHERE blocker_id = ? AND blocked_id = ?',
                        (my_uid, t_uid)
                    )
                    conn.commit()
                    return self.send_j(200, {'ok': True, 'isBlockedByMe': False})

        if p == '/api/users/report':
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(8192) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            target_ident = str(j.get('targetUserId') or j.get('targetId') or j.get('userId') or j.get('username') or j.get('handle') or '').strip()
            reason = str(j.get('reason') or '').strip()[:500]
            try:
                mid = max(0, int(j.get('messageId') or 0))
            except Exception:
                mid = 0
            if not target_ident or not reason:
                return self.send_j(400, {'error': 'Укажите пользователя и причину жалобы'})
            my_uid = usr['id']
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                t_row = resolve_target_user(conn, target_ident)
                if not t_row:
                    return self.send_j(404, {'error': 'Пользователь не найден'})
                t_uid = int(t_row['id'])
                if t_uid == my_uid:
                    return self.send_j(400, {'error': 'Нельзя пожаловаться на самого себя'})
                conn.execute(
                    'INSERT INTO user_reports (reporter_id, target_user_id, message_id, reason, created_at) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (my_uid, t_uid, mid, reason, now)
                )
                conn.commit()
            return self.send_j(200, {'ok': True})
        if p == '/api/payment/create':
            if FREE_ACCESS_MODE:
                return self.send_j(403, {
                    'error': 'Все функции доступны бесплатно. Оформление новых подписок отключено.',
                    'paymentsDisabled': True,
                    'freeAccessMode': True
                })
            tok = self.headers.get('Authorization', '').replace('Bearer ', '').strip()
            usr = get_user_by_token(tok)
            if not usr:
                return self.send_j(401, {'error': 'Для оформления подписки войдите в аккаунт или зарегистрируйтесь'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            plan_id = str(j.get('planId') or '3m').strip()
            plan = PLANS.get(plan_id)
            if not plan:
                return self.send_j(400, {'error': 'Некорректный тарифный план'})
            cfg = yookassa_cfg()
            if not cfg.get('enabled') or not cfg.get('shop_id') or not cfg.get('secret_key'):
                return self.send_j(400, {
                    'error': 'Приём платежей ЮKassa пока не настроен. Укажите Shop ID и Секретный ключ в панели управления (раздел 💳 ЮKassa & СБП).',
                    'notConfigured': True
                })
            host = self.headers.get('Host') or 'rizzafit.ru'
            proto = 'https' if not host.startswith('localhost') else 'http'
            return_url = f'{proto}://{host}/#pay_success'
            desc = f'RizzaFit PRO — {plan["name"]} (@{usr["username"]})'
            meta = {
                'user_id': str(usr['id']),
                'username': usr['username'],
                'plan_id': plan_id,
                'days': str(plan['days'])
            }
            try:
                pay_res = yookassa_create_payment(
                    shop_id=cfg['shop_id'],
                    secret_key=cfg['secret_key'],
                    amount_rub=plan['price'],
                    return_url=return_url,
                    description=desc,
                    metadata=meta,
                    sbp_only=bool(cfg.get('sbp_only', True))
                )
            except RuntimeError as e:
                return self.send_j(502, {'error': str(e)})
            except Exception as e:
                return self.send_j(500, {'error': 'Не удалось создать платеж в ЮKassa'})

            pay_id = pay_res.get('id', '')
            conf = pay_res.get('confirmation') or {}
            conf_url = conf.get('confirmation_url', '')
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    'INSERT INTO payments (user_id, plan, days, amount, currency, provider, status, note, payment_id, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, "RUB", "yookassa", "pending", ?, ?, ?, ?)',
                    (usr['id'], plan_id, plan['days'], plan['price'], 'YooKassa ' + ('СБП' if cfg.get('sbp_only', True) else 'Касса'), pay_id, now, now)
                )
                conn.commit()
            return self.send_j(200, {'ok': True, 'paymentUrl': conf_url, 'paymentId': pay_id, 'plan': plan})
        if p == '/api/payment/yookassa/webhook':
            if FREE_ACCESS_MODE:
                return self.send_j(200, {'ok': True, 'ignored': True, 'freeAccessMode': True})
            try:
                raw_b = self.body(64 * 1024)
                j = json.loads(raw_b or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            event = str(j.get('event') or '').strip()
            obj = j.get('object') if isinstance(j.get('object'), dict) else {}
            pay_id = str(obj.get('id') or '').strip()
            if event in ('payment.succeeded', 'payment.canceled') and pay_id:
                res = sync_pending_yookassa_payment(pay_id)
                if not res:
                    return self.send_j(200, {'ok': True, 'ignored': True})
                return self.send_j(200, {'ok': True, 'status': res['status'], 'verified': res['verified']})
            return self.send_j(200, {'ok': True, 'ignored': True})
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
        if p == '/api/admin/user/plan':
            try:
                j = json.loads(self.body(4096) or b'{}')
                uid = int(j.get('userId') or 0)
                plan = 'pro' if j.get('plan') == 'pro' else 'free'
                days = int(j.get('days') or 0)
                amount = int(j.get('amount') or 0)
                note = str(j.get('note') or '')[:120]
            except Exception:
                return self.send_j(400, {'error': 'bad request'})
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                row = conn.execute('SELECT plan, plan_expires_at FROM users WHERE id = ?', (uid,)).fetchone()
                if not row:
                    return self.send_j(404, {'error': 'user not found'})
                if plan == 'free':
                    exp = 0
                elif days <= 0:
                    exp = 0     # lifetime PRO
                else:
                    base = max(now, int(row[1] or 0)) if row[0] == 'pro' and int(row[1] or 0) > now else now
                    exp = base + days * 86400
                conn.execute('UPDATE users SET plan = ?, plan_expires_at = ? WHERE id = ?', (plan, exp, uid))
                conn.execute(
                    'INSERT INTO payments (user_id, plan, days, amount, currency, provider, status, note, created_at) '
                    'VALUES (?, ?, ?, ?, "RUB", "admin", "paid", ?, ?)',
                    (uid, plan, days, amount, note, now)
                )
                conn.commit()
            return self.send_j(200, {'ok': True, 'plan': plan, 'planExpiresAt': exp})
        if p == '/api/admin/user/block':
            try:
                j = json.loads(self.body(4096) or b'{}')
                uid = int(j.get('userId') or 0)
                blk = 1 if j.get('blocked') else 0
            except Exception:
                return self.send_j(400, {'error': 'bad request'})
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                conn.execute('UPDATE users SET is_blocked = ? WHERE id = ?', (blk, uid))
                if blk:
                    conn.execute('DELETE FROM user_sessions WHERE user_id = ?', (uid,))
                conn.commit()
            return self.send_j(200, {'ok': True, 'blocked': bool(blk)})
        if p == '/api/admin/user/reset-code':
            try:
                j = json.loads(self.body(4096) or b'{}')
                uid = int(j.get('userId') or 0)
            except Exception:
                return self.send_j(400, {'error': 'bad request'})
            code = secrets.token_hex(4).upper()
            now = int(time.time())
            with db_lock, sqlite3.connect(DB_FILE) as conn:
                if not conn.execute('SELECT 1 FROM users WHERE id = ?', (uid,)).fetchone():
                    return self.send_j(404, {'error': 'user not found'})
                conn.execute('DELETE FROM password_resets WHERE user_id = ?', (uid,))
                conn.execute(
                    'INSERT INTO password_resets (code, user_id, expires_at, used, created_at) VALUES (?, ?, ?, 0, ?)',
                    (code, uid, now + 86400, now)
                )
                conn.commit()
            return self.send_j(200, {'ok': True, 'code': code})
        if p == '/api/admin/yookassa':
            try:
                j = json.loads(self.body(16 * 1024) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            cur = yookassa_cfg()
            if 'shopId' in j:
                cur['shop_id'] = str(j['shopId']).strip()
            if j.get('secretKey'):
                cur['secret_key'] = str(j['secretKey']).strip()
            if j.get('clearKey'):
                cur['secret_key'] = ''
            if 'enabled' in j:
                cur['enabled'] = bool(j['enabled'])
            if 'sbpOnly' in j:
                cur['sbp_only'] = bool(j['sbpOnly'])
            save_yookassa_cfg(cur)
            return self.send_j(200, {'ok': True})
        if p == '/api/admin/yookassa/test':
            try:
                j = json.loads(self.body(16 * 1024) or b'{}')
            except Exception:
                j = {}
            cur = yookassa_cfg()
            shop_id = str(j.get('shopId') or cur.get('shop_id', '')).strip()
            secret_key = str(j.get('secretKey') or cur.get('secret_key', '')).strip()
            if not shop_id or not secret_key:
                return self.send_j(400, {'error': 'Укажите Shop ID и Секретный ключ для проверки соединения'})
            try:
                res = yookassa_test_connection(shop_id, secret_key)
                return self.send_j(200, {'ok': True, 'account': res})
            except RuntimeError as e:
                return self.send_j(400, {'error': str(e)})
            except Exception as e:
                return self.send_j(500, {'error': f'Ошибка соединения: {e}'})
        if p == '/api/admin/telegram':
            if not self.authed():
                return self.send_j(401, {'error': 'unauthorized'})
            try:
                j = json.loads(self.body(4096) or b'{}')
            except Exception:
                return self.send_j(400, {'error': 'bad json'})
            update_data = {}
            if 'botUsername' in j:
                update_data['bot_username'] = str(j.get('botUsername') or '').lstrip('@').strip()
            if 'botToken' in j and j.get('botToken') != '***':
                update_data['bot_token'] = str(j.get('botToken') or '').strip()
            if 'enabled' in j:
                update_data['enabled'] = bool(j.get('enabled'))
            save_telegram_cfg(update_data)
            return self.send_j(200, {'ok': True})
        if p == '/api/admin/telegram/test':
            if not self.authed():
                return self.send_j(401, {'error': 'unauthorized'})
            cfg = telegram_cfg()
            tok = cfg.get('bot_token', '').strip()
            if not tok:
                return self.send_j(400, {'error': 'Токен бота не указан'})
            try:
                req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/getMe', headers={'User-Agent': 'FlexaBot/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get('ok'):
                        b_info = data.get('result', {})
                        return self.send_j(200, {'ok': True, 'bot': b_info})
                    return self.send_j(400, {'error': data.get('description', 'Ошибка Telegram API')})
            except Exception as e:
                return self.send_j(400, {'error': f'Не удалось соединиться с Telegram: {e}'})
        self.send_j(404, {'error': 'not found'})

if __name__ == '__main__':
    init_admin()
    init_db()
    threading.Thread(target=telegram_bot_worker, daemon=True).start()
    print('Flexa: http://localhost:%d   Admin: http://localhost:%d/admin.html' % (PORT, PORT))
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(('0.0.0.0', PORT), H)
    httpd.serve_forever()
