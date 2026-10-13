#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""申论素材库 Web 服务端：本地默认 SQLite，云端可切换 PostgreSQL。"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote
from db_layer import connect as connect_db, using_postgres
from http.cookies import SimpleCookie
from datetime import datetime, date
import hashlib, hmac, json, os, secrets, sqlite3, threading, time

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("SHENLUN_DATA_DIR", str(BASE_DIR))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "shenlun.db"
CONFIG_PATH = DATA_DIR / "config.json"
HOST = os.environ.get("SHENLUN_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", os.environ.get("SHENLUN_PORT", "8765")))

TOPICS = [
    {"key": "law_enforcement", "label": "行政执法", "en": "LAW & GOVERNANCE", "description": "民生服务、基层治理、行政执法、作风建设", "icon": "⚖"},
    {"key": "rural_revitalization", "label": "乡村振兴", "en": "RURAL REVITALIZATION", "description": "农业农村、粮食安全、城乡融合", "icon": "🌾"},
    {"key": "business_environment", "label": "营商环境", "en": "BUSINESS ENVIRONMENT", "description": "民营经济、对外开放、消费升级", "icon": "↗"},
    {"key": "sci_tech_innovation", "label": "科技创新", "en": "SCIENCE & INNOVATION", "description": "创新生态、人才工作、教育强国", "icon": "✳"},
    {"key": "green_development", "label": "绿色发展", "en": "GREEN DEVELOPMENT", "description": "生态文明、环境治理、双碳目标", "icon": "♧"},
    {"key": "industrial_upgrading", "label": "产业升级", "en": "INDUSTRIAL UPGRADING", "description": "高质量发展、先进制造、未来产业", "icon": "▥"},
    {"key": "digital_economy", "label": "数字经济", "en": "DIGITAL ECONOMY", "description": "人工智能、数字中国、数字化转型", "icon": "⌘"},
    {"key": "cultural_confidence", "label": "文化自信", "en": "CULTURAL CONFIDENCE", "description": "文化建设、非遗文博、文旅融合", "icon": "文"},
]
TOPIC_MAP = {t["key"]: t for t in TOPICS}


def now_iso(): return datetime.now().isoformat(timespec="seconds")


def db():
    return connect_db(DB_PATH, timeout=15)


def init_db():
    conn = db()
    if using_postgres():
        schema = '''
        CREATE TABLE IF NOT EXISTS topics (
          key TEXT PRIMARY KEY, label TEXT NOT NULL, en TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', icon TEXT NOT NULL DEFAULT '•'
        );
        CREATE TABLE IF NOT EXISTS users (
          id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS materials (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, column_author TEXT NOT NULL DEFAULT '', publish_date TEXT NOT NULL,
          source_name TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '', core_view TEXT NOT NULL DEFAULT '',
          quotes_json TEXT NOT NULL DEFAULT '[]', argument_structure TEXT NOT NULL DEFAULT '', topics_json TEXT NOT NULL DEFAULT '[]',
          writing_angles_json TEXT NOT NULL DEFAULT '[]', original_summary TEXT NOT NULL DEFAULT '', original_content TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'published', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS favorites (
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
          created_at TEXT NOT NULL, PRIMARY KEY(user_id, material_id)
        );
        CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_materials_date ON materials(publish_date DESC);
        CREATE INDEX IF NOT EXISTS idx_materials_title ON materials(title);
        CREATE INDEX IF NOT EXISTS idx_materials_owner ON materials(owner_id);
        '''
        conn.executescript(schema)
        columns = {r['column_name'] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='materials'").fetchall()}
        if 'owner_id' not in columns:
            conn.execute('ALTER TABLE materials ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_materials_owner ON materials(owner_id)')
    else:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS topics (
          key TEXT PRIMARY KEY, label TEXT NOT NULL, en TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', icon TEXT NOT NULL DEFAULT '•'
        );
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS materials (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, column_author TEXT NOT NULL DEFAULT '', publish_date TEXT NOT NULL,
          source_name TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '', core_view TEXT NOT NULL DEFAULT '',
          quotes_json TEXT NOT NULL DEFAULT '[]', argument_structure TEXT NOT NULL DEFAULT '', topics_json TEXT NOT NULL DEFAULT '[]',
          writing_angles_json TEXT NOT NULL DEFAULT '[]', original_summary TEXT NOT NULL DEFAULT '', original_content TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'published', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS favorites (
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
          created_at TEXT NOT NULL, PRIMARY KEY(user_id, material_id)
        );
        CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_materials_date ON materials(publish_date DESC);
        CREATE INDEX IF NOT EXISTS idx_materials_title ON materials(title);
        ''')
        material_columns = {r['name'] for r in conn.execute('PRAGMA table_info(materials)')}
        if 'owner_id' not in material_columns:
            conn.execute('ALTER TABLE materials ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_materials_owner ON materials(owner_id)')
    for item in TOPICS:
        conn.execute("INSERT INTO topics(key,label,en,description,icon) VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET label=excluded.label,en=excluded.en,description=excluded.description,icon=excluded.icon",
            (item['key'], item['label'], item['en'], item['description'], item['icon']))
    conn.commit()
    conn.close()


def config_read():
    if not CONFIG_PATH.exists():
        default = {
            "schedule_time": "07:30",
            "sources": [
                {"name": "人民日报", "feed_url": "", "enabled": False},
                {"name": "求是网", "feed_url": "", "enabled": False},
                {"name": "共产党员网", "feed_url": "", "enabled": False},
                {"name": "重要讲话（人民网/新华网/求是网）", "feed_url": "", "enabled": False}
            ],
            "ai": {"base_url": "https://api.openai.com/v1", "api_key": "", "model": ""},
            "auto_publish": False
        }
        CONFIG_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding='utf-8')
    try: return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception: return {"schedule_time":"07:30", "sources":[], "ai":{}, "auto_publish":False}


def json_list(value):
    try:
        x = json.loads(value or '[]')
        return x if isinstance(x, list) else []
    except Exception: return []


def material_dict(row, user_id=None, conn=None, favorite_ids=None):
    d = dict(row)
    d['quotes'] = json_list(d.pop('quotes_json', '[]'))
    d['topics'] = json_list(d.pop('topics_json', '[]'))
    d['writing_angles'] = json_list(d.pop('writing_angles_json', '[]'))
    d['is_favorite'] = False
    owner_id = d.pop('owner_id', None)
    d['can_edit'] = bool(user_id and owner_id == user_id)
    if user_id and favorite_ids is not None:
        d['is_favorite'] = d['id'] in favorite_ids
    elif user_id and conn:
        d['is_favorite'] = conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND material_id=?", (user_id, d['id'])).fetchone() is not None
    d['topic_labels'] = [TOPIC_MAP[k]['label'] for k in d['topics'] if k in TOPIC_MAP]
    return d


def get_cookie_token(handler):
    try:
        cookie = SimpleCookie(handler.headers.get('Cookie', ''))
        return cookie['shenlun_session'].value if 'shenlun_session' in cookie else None
    except Exception: return None


def get_user(handler, conn):
    token = get_cookie_token(handler)
    if not token: return None
    row = conn.execute("SELECT users.id, users.username FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token=?", (token,)).fetchone()
    return dict(row) if row else None


def parse_material(raw, existing=None):
    if not isinstance(raw, dict): raise ValueError('素材数据格式不正确')
    title = str(raw.get('title', '')).strip()
    if not title: raise ValueError('请填写素材标题')
    pub = str(raw.get('publish_date', '')).strip()
    try: pub_date = date.fromisoformat(pub)
    except Exception: raise ValueError('发布日期请使用 YYYY-MM-DD 格式')
    if pub_date > date.today(): raise ValueError('发布日期不能晚于今天')
    topics = raw.get('topics', [])
    if isinstance(topics, str): topics = [topics]
    topics = [x for x in topics if x in TOPIC_MAP]
    quotes = raw.get('quotes', [])
    angles = raw.get('writing_angles', [])
    if isinstance(quotes, str): quotes = [x.strip() for x in quotes.splitlines() if x.strip()]
    if isinstance(angles, str): angles = [x.strip() for x in angles.splitlines() if x.strip()]
    topics = list(dict.fromkeys(topics))
    def s(k, default=''): return str(raw.get(k, default) or '').strip()
    return {
      'id': str(raw.get('id') or (existing['id'] if existing else secrets.token_hex(12))),
      'title': title, 'column_author': s('column_author'), 'publish_date': pub,
      'source_name': s('source_name'), 'source_url': s('source_url'), 'core_view': s('core_view'),
      'quotes_json': json.dumps([str(x).strip() for x in quotes if str(x).strip()][:30], ensure_ascii=False),
      'argument_structure': s('argument_structure'), 'topics_json': json.dumps(topics, ensure_ascii=False),
      'writing_angles_json': json.dumps([str(x).strip() for x in angles if str(x).strip()][:20], ensure_ascii=False),
      'original_summary': s('original_summary'), 'original_content': s('original_content'),
      'status': 'draft' if s('status') == 'draft' else 'published'
    }


def session_cookie(handler, token, max_age=2592000):
    # Render terminates TLS at its edge and forwards the original protocol.
    secure = handler.headers.get('X-Forwarded-Proto', '').lower() == 'https' or getattr(handler, 'is_https', False)
    parts = [f'shenlun_session={token}', 'HttpOnly', 'SameSite=Lax', 'Path=/']
    if secure: parts.append('Secure')
    if max_age is not None: parts.append(f'Max-Age={max_age}')
    return '; '.join(parts)


class Handler(SimpleHTTPRequestHandler):
    server_version = "ShenlunLibrary/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        super().end_headers()

    def send_json(self, data, status=200, extra_headers=None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store')
        if extra_headers:
            for k,v in extra_headers.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 50_000_000: raise ValueError('请求内容过大（单次导入上限约 50 MB）')
        raw = self.rfile.read(length) if length else b'{}'
        return json.loads(raw.decode('utf-8') or '{}')

    def do_GET(self):
        parsed = urlparse(self.path); path = unquote(parsed.path); qs = parse_qs(parsed.query)
        if path.startswith('/api/'):
            conn = db()
            try:
                user = get_user(self, conn)
                if path == '/api/health':
                    self.send_json({'ok': True, 'service': 'shenlun-material-library-new', 'database': 'postgresql' if using_postgres() else 'sqlite'}); return
                if path == '/api/meta':
                    topics = [dict(r) for r in conn.execute('SELECT * FROM topics ORDER BY label')]
                    scope = "(owner_id IS NULL" + (" OR owner_id=?" if user else "") + ")"
                    scope_args = [user['id']] if user else []
                    count = conn.execute(f"SELECT COUNT(*) n FROM materials WHERE status='published' AND {scope}", scope_args).fetchone()['n']
                    drafts = conn.execute(f"SELECT COUNT(*) n FROM materials WHERE status='draft' AND {scope}", scope_args).fetchone()['n']
                    sources = config_read().get('sources', [])
                    self.send_json({'topics': topics, 'user': user, 'stats': {'total': count,
                        'favorites': conn.execute('SELECT COUNT(*) n FROM favorites WHERE user_id=?',(user['id'],)).fetchone()['n'] if user else 0,
                        'drafts': drafts,
                        'sources_enabled': sum(1 for s in sources if s.get('enabled') and s.get('feed_url'))}}); return
                if path == '/api/me': self.send_json({'user': user}); return
                if path == '/api/daily-report':
                    today = date.today().isoformat()
                    if not user:
                        self.send_json({'error':'请先登录后下载当日整理文档'}, 401); return
                    rows = conn.execute("SELECT * FROM materials WHERE updated_at LIKE ? AND (owner_id IS NULL OR owner_id=?) ORDER BY publish_date DESC, updated_at DESC", (today+'%', user['id'])).fetchall()
                    if not rows:
                        self.send_json({'error':'今天还没有新增或更新的素材，完成录入或运行更新任务后再下载。'},404); return
                    lines = [f'# 申论素材整理文档（{today}）', '', f'整理条数：{len(rows)}', '', '> 本文由本地素材库根据当日新增或更新的记录生成；请核对来源信息并结合题目要求使用。', '']
                    for i, row in enumerate(rows, 1):
                        it = material_dict(row)
                        lines += [f"## {i}. {it['title']}", '', f"- 栏目/作者：{it.get('column_author') or '未标注'}", f"- 发布日期：{it['publish_date']}", f"- 来源：{it.get('source_name') or '未标注'}", f"- 来源地址（纯文本）：`{it.get('source_url') or '未记录'}`", f"- 主题 key：{', '.join(it.get('topics', [])) or '待标注'}", f"- 状态：{'待整理' if it.get('status')=='draft' else '已入库'}", '', '### 核心观点', it.get('core_view') or '待补充', '', '### 金句 / 短语', *([f'- {q}' for q in it.get('quotes', [])] or ['- 待补充']), '', '### 论证结构', it.get('argument_structure') or '待补充', '', '### 写作角度', *([f'- {a}' for a in it.get('writing_angles', [])] or ['- 待补充']), '', '### 原文摘要', it.get('original_summary') or '待补充', '', '---', '']
                    body = ('\n'.join(lines)).encode('utf-8')
                    self.send_response(200); self.send_header('Content-Type','text/markdown; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(f'申论素材整理_{today}.md')); self.end_headers(); self.wfile.write(body); return
                if path == '/api/update/status':
                    cfg = config_read(); m = {r['key']:r['value'] for r in conn.execute('SELECT key,value FROM app_meta')}
                    self.send_json({'schedule_time':cfg.get('schedule_time','07:30'), 'sources':cfg.get('sources',[]), 'ai_configured':bool(cfg.get('ai',{}).get('api_key') and cfg.get('ai',{}).get('model')),
                      'last_update':m.get('last_update'), 'last_update_message':m.get('last_update_message','尚未运行更新任务'),
                      'next_hint':'每日 '+str(cfg.get('schedule_time','07:30'))+'（需保持本程序运行）'}); return
                if path == '/api/materials':
                    # Public materials plus this account's private materials only.
                    sql = "SELECT * FROM materials WHERE (owner_id IS NULL" + (" OR owner_id=?" if user else "") + ")"; args=[user['id']] if user else []
                    status = (qs.get('status') or ['published'])[0]
                    if status != 'all': sql += ' AND status=?'; args.append(status)
                    q = (qs.get('q') or [''])[0].strip()
                    if q:
                        like = '%'+q+'%'; sql += " AND (title LIKE ? OR core_view LIKE ? OR original_summary LIKE ? OR quotes_json LIKE ? OR writing_angles_json LIKE ? OR argument_structure LIKE ?)"; args += [like]*6
                    topic = (qs.get('topic') or [''])[0]
                    if topic in TOPIC_MAP:
                        # Topics are stored using the required English keys.
                        sql += " AND topics_json LIKE ?"; args.append('%"'+topic+'"%')
                    start = (qs.get('from') or [''])[0]; end = (qs.get('to') or [''])[0]
                    if start: sql += ' AND publish_date>=?'; args.append(start)
                    if end: sql += ' AND publish_date<=?'; args.append(end)
                    only_fav = (qs.get('favorite') or ['0'])[0] == '1'
                    if only_fav:
                        if not user: self.send_json({'error':'请先登录后查看收藏'}, 401); return
                        sql += ' AND id IN (SELECT material_id FROM favorites WHERE user_id=?)'; args.append(user['id'])
                    sql += " ORDER BY publish_date DESC, updated_at DESC"
                    limit = min(max(int((qs.get('limit') or ['1000'])[0]),1),5000)
                    rows = conn.execute(sql+' LIMIT ?', args+[limit]).fetchall()
                    favorite_ids = {r['material_id'] for r in conn.execute('SELECT material_id FROM favorites WHERE user_id=?', (user['id'],)).fetchall()} if user else set()
                    self.send_json({'items':[material_dict(r, user['id'] if user else None, conn, favorite_ids) for r in rows], 'count':len(rows)}); return
                if path.startswith('/api/materials/'):
                    material_id = path.rsplit('/',1)[1]
                    row = conn.execute('SELECT * FROM materials WHERE id=? AND (owner_id IS NULL' + (' OR owner_id=?' if user else '') + ')', (material_id, user['id']) if user else (material_id,)).fetchone()
                    if not row: self.send_json({'error':'素材不存在或无权访问'},404); return
                    self.send_json({'item':material_dict(row, user['id'] if user else None, conn)}); return
                if path == '/api/export':
                    rows = conn.execute('SELECT * FROM materials WHERE (owner_id IS NULL' + (' OR owner_id=?' if user else '') + ') ORDER BY publish_date DESC', (user['id'],) if user else ()).fetchall()
                    items = [material_dict(r, user['id'] if user else None, conn) for r in rows]
                    self.send_json({'app':'申论素材库','version':1,'exported_at':now_iso(),'items':items}); return
                self.send_json({'error':'接口不存在'},404)
            except Exception as e:
                self.send_json({'error':str(e)},500)
            finally: conn.close()
        if path == '/' or path == '/index.html':
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        try: data = self.read_json()
        except Exception as e: self.send_json({'error':'请求数据无法解析：'+str(e)},400); return
        conn = db()
        try:
            if path == '/api/auth/register':
                username = str(data.get('username','')).strip(); password = str(data.get('password',''))
                if len(username) < 2 or len(username) > 24: self.send_json({'error':'用户名长度需为 2—24 个字符'},400); return
                if len(password) < 6: self.send_json({'error':'密码至少需要 6 位'},400); return
                salt = secrets.token_hex(16); ph = hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),180000).hex()
                try:
                    if using_postgres():
                        uid = conn.execute('INSERT INTO users(username,password_hash,salt,created_at) VALUES(?,?,?,?) RETURNING id',(username,ph,salt,now_iso())).fetchone()['id']
                    else:
                        uid = conn.execute('INSERT INTO users(username,password_hash,salt,created_at) VALUES(?,?,?,?)',(username,ph,salt,now_iso())).lastrowid
                    token=secrets.token_urlsafe(32); conn.execute('INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)',(token,uid,now_iso())); conn.commit()
                    self.send_json({'user':{'id':uid,'username':username}},201,{'Set-Cookie':session_cookie(self, token)})
                except sqlite3.IntegrityError: self.send_json({'error':'该用户名已注册'},409)
                return
            if path == '/api/auth/login':
                username=str(data.get('username','')).strip(); password=str(data.get('password',''))
                row=conn.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                if not row: self.send_json({'error':'用户名或密码不正确'},401); return
                ph=hashlib.pbkdf2_hmac('sha256',password.encode(),row['salt'].encode(),180000).hex()
                if not hmac.compare_digest(ph,row['password_hash']): self.send_json({'error':'用户名或密码不正确'},401); return
                token=secrets.token_urlsafe(32); conn.execute('INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)',(token,row['id'],now_iso())); conn.commit()
                self.send_json({'user':{'id':row['id'],'username':username}},200,{'Set-Cookie':session_cookie(self, token)}); return
            if path == '/api/auth/logout':
                token=get_cookie_token(self)
                if token: conn.execute('DELETE FROM sessions WHERE token=?',(token,)); conn.commit()
                self.send_json({'ok':True},200,{'Set-Cookie':session_cookie(self, '', max_age=0)}); return
            if path == '/api/materials':
                user = get_user(self, conn)
                if not user:
                    self.send_json({'error': '请先登录后新增素材'}, 401); return
                incoming = parse_material(data)
                incoming['created_at'] = now_iso(); incoming['updated_at'] = now_iso(); incoming['owner_id'] = user['id']
                conn.execute('''INSERT INTO materials(
                    id,title,column_author,publish_date,source_name,source_url,core_view,quotes_json,
                    argument_structure,topics_json,writing_angles_json,original_summary,original_content,
                    status,created_at,updated_at,owner_id
                ) VALUES(
                    :id,:title,:column_author,:publish_date,:source_name,:source_url,:core_view,:quotes_json,
                    :argument_structure,:topics_json,:writing_angles_json,:original_summary,:original_content,
                    :status,:created_at,:updated_at,:owner_id
                )''', incoming)
                conn.commit()
                row = conn.execute('SELECT * FROM materials WHERE id=?', (incoming['id'],)).fetchone()
                self.send_json({'item': material_dict(row, user['id'], conn)}, 201); return
            if path == '/api/import':
                user=get_user(self,conn)
                if not user: self.send_json({'error':'请先登录后导入素材'},401); return
                items=data.get('items',[]) if isinstance(data,dict) else data
                if not isinstance(items,list): self.send_json({'error':'导入文件中没有 items 数组'},400); return
                added=0; updated=0; skipped=[]
                for i, raw in enumerate(items):
                    try:
                        mid=str(raw.get('id') or '') if isinstance(raw,dict) else ''
                        exists=conn.execute('SELECT * FROM materials WHERE id=? AND owner_id=?',(mid,user['id'])).fetchone() if mid else None
                        parsed=parse_material(raw,dict(exists) if exists else None)
                        # Avoid overwriting an existing record with a generated random ID if no matching ID exists.
                        dup=conn.execute('SELECT id FROM materials WHERE source_url=? AND source_url<>\'\' AND owner_id=?',(parsed['source_url'],user['id'])).fetchone() if parsed['source_url'] else None
                        if exists or dup:
                            target=exists['id'] if exists else dup['id']; parsed['id']=target
                            conn.execute('''UPDATE materials SET title=:title,column_author=:column_author,publish_date=:publish_date,source_name=:source_name,source_url=:source_url,core_view=:core_view,quotes_json=:quotes_json,argument_structure=:argument_structure,topics_json=:topics_json,writing_angles_json=:writing_angles_json,original_summary=:original_summary,original_content=:original_content,status=:status,updated_at=:updated_at WHERE id=:id''',{**parsed,'id':target,'updated_at':now_iso()}); updated+=1
                        else:
                            conn.execute('''INSERT INTO materials(id,title,column_author,publish_date,source_name,source_url,core_view,quotes_json,argument_structure,topics_json,writing_angles_json,original_summary,original_content,status,created_at,updated_at,owner_id) VALUES(:id,:title,:column_author,:publish_date,:source_name,:source_url,:core_view,:quotes_json,:argument_structure,:topics_json,:writing_angles_json,:original_summary,:original_content,:status,:created_at,:updated_at,:owner_id)''',{**parsed,'created_at':now_iso(),'updated_at':now_iso(),'owner_id':user['id']}); added+=1
                    except Exception as e: skipped.append({'index':i+1,'title':raw.get('title','') if isinstance(raw,dict) else '', 'reason':str(e)})
                conn.commit(); self.send_json({'added':added,'updated':updated,'skipped':skipped}); return
            if path == '/api/update/run':
                user=get_user(self,conn)
                if not user: self.send_json({'error':'请先登录后运行更新任务'},401); return
                conn.close()
                try:
                    from updater import run_update
                    result = run_update(DB_PATH, CONFIG_PATH)
                    self.send_json(result, 200 if result.get('ok') else 400)
                except Exception as e:
                    c=db(); c.execute('INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_update_message','更新失败：'+str(e))); c.commit(); c.close()
                    self.send_json({'ok':False,'error':str(e)},500)
                return
            if path.startswith('/api/favorites/'):
                material_id=path.rsplit('/',1)[1]; user=get_user(self,conn)
                if not user: self.send_json({'error':'请先登录，再收藏素材'},401); return
                if not conn.execute('SELECT 1 FROM materials WHERE id=? AND (owner_id IS NULL OR owner_id=?)',(material_id,user['id'])).fetchone(): self.send_json({'error':'素材不存在或无权访问'},404); return
                conn.execute('INSERT INTO favorites(user_id,material_id,created_at) VALUES(?,?,?) ON CONFLICT DO NOTHING',(user['id'],material_id,now_iso())); conn.commit(); self.send_json({'ok':True,'is_favorite':True}); return
            self.send_json({'error':'接口不存在'},404)
        except ValueError as e: self.send_json({'error':str(e)},400)
        except sqlite3.IntegrityError as e: self.send_json({'error':'数据重复或违反约束：'+str(e)},409)
        except Exception as e: self.send_json({'error':'服务器错误：'+str(e)},500)
        finally:
            try: conn.close()
            except Exception: pass

    def do_PUT(self):
        path = unquote(urlparse(self.path).path)
        try:
            data = self.read_json()
        except Exception as e:
            self.send_json({'error': str(e)}, 400); return
        if not path.startswith('/api/materials/'):
            self.send_json({'error': '接口不存在'}, 404); return
        mid = path.rsplit('/', 1)[1]
        conn = db()
        try:
            user = get_user(self, conn)
            if not user:
                self.send_json({'error': '请先登录后编辑素材'}, 401); return
            old = conn.execute('SELECT * FROM materials WHERE id=? AND owner_id=?', (mid, user['id'])).fetchone()
            if not old:
                self.send_json({'error': '素材不存在或你没有修改权限'}, 404); return
            data['id'] = mid
            parsed = parse_material(data, dict(old))
            conn.execute('''UPDATE materials SET title=:title,column_author=:column_author,publish_date=:publish_date,
                source_name=:source_name,source_url=:source_url,core_view=:core_view,quotes_json=:quotes_json,
                argument_structure=:argument_structure,topics_json=:topics_json,writing_angles_json=:writing_angles_json,
                original_summary=:original_summary,original_content=:original_content,status=:status,updated_at=:updated_at
                WHERE id=:id AND owner_id=:owner_id''', {**parsed, 'updated_at': now_iso(), 'owner_id': user['id']})
            conn.commit()
            row = conn.execute('SELECT * FROM materials WHERE id=?', (mid,)).fetchone()
            self.send_json({'item': material_dict(row, user['id'], conn)}); return
        except ValueError as e:
            self.send_json({'error': str(e)}, 400)
        except Exception as e:
            self.send_json({'error': '服务器错误：' + str(e)}, 500)
        finally:
            conn.close()

    def do_DELETE(self):
        path=unquote(urlparse(self.path).path); conn=db()
        try:
            if path.startswith('/api/favorites/'):
                mid=path.rsplit('/',1)[1]; user=get_user(self,conn)
                if not user: self.send_json({'error':'请先登录'},401); return
                conn.execute('DELETE FROM favorites WHERE user_id=? AND material_id=?',(user['id'],mid)); conn.commit(); self.send_json({'ok':True,'is_favorite':False}); return
            if path.startswith('/api/materials/'):
                mid=path.rsplit('/',1)[1]; user=get_user(self,conn)
                if not user: self.send_json({'error':'请先登录后删除素材'},401); return
                cur=conn.execute('DELETE FROM materials WHERE id=? AND owner_id=?',(mid,user['id']))
                if cur.rowcount == 0: self.send_json({'error':'素材不存在或你没有删除权限'},404); return
                conn.commit(); self.send_json({'ok':True}); return
            self.send_json({'error':'接口不存在'},404)
        except Exception as e: self.send_json({'error':str(e)},500)
        finally: conn.close()


def scheduler_loop():
    """日定时任务：程序持续运行时，在 config.json 所设时间触发。"""
    last_trigger = None
    while True:
        try:
            cfg = config_read(); schedule = str(cfg.get('schedule_time','07:30'))
            current = datetime.now()
            if current.strftime('%H:%M') == schedule and last_trigger != current.date().isoformat():
                last_trigger = current.date().isoformat()
                from updater import run_update
                result = run_update(DB_PATH, CONFIG_PATH)
                print('[daily-update]', result)
        except Exception as e: print('[daily-update-error]', e)
        time.sleep(25)


if __name__ == '__main__':
    # Honor a configured TZ (Render deployments in this package default to Asia/Tokyo).
    if os.environ.get('TZ') and hasattr(time, 'tzset'):
        time.tzset()
    init_db()
    config_read()
    print('申论素材库已启动： http://%s:%s' % (HOST, PORT))
    print('数据目录：%s' % DATA_DIR)
    threading.Thread(target=scheduler_loop, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()
