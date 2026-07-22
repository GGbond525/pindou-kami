#!/usr/bin/env python3
"""拼小豆 - 卡密分销系统（SQLite本地 / PostgreSQL生产）"""
import flask, os, random, string, datetime, hashlib, json
from flask import Flask, request, jsonify

app = Flask(__name__)
ADMIN_PASSWORD = "WzS18350168663."

# ===== 数据库适配层（同时支持SQLite和PostgreSQL）=====
DB_URL = os.environ.get("DATABASE_URL", "")

if DB_URL:
    import psycopg2
    import psycopg2.extras
    def get_db():
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kami_codes (
                id SERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL,
                type TEXT DEFAULT 'member', created_at TEXT,
                created_by TEXT, used_by TEXT, used_at TEXT, status TEXT DEFAULT 'unused'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL, created_at TEXT, kami_code TEXT,
                activated_at TEXT, is_agent INTEGER DEFAULT 0,
                agent_kami_code TEXT, wechat_id TEXT, agent_quota INTEGER DEFAULT 50
            )
        """)
        conn.commit()
        return conn

    def query(conn, sql, params=None):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or [])
        return cur

    def fetchone(conn, sql, params=None):
        cur = query(conn, sql, params)
        return cur.fetchone()

    def fetchall(conn, sql, params=None):
        cur = query(conn, sql, params)
        return cur.fetchall()

    PLACEHOLDER = "%s"
else:
    import sqlite3
    def get_db():
        db_path = os.path.join(os.path.dirname(__file__), "kami_data.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kami_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL DEFAULT 'member', created_at TEXT,
                created_by TEXT, used_by TEXT, used_at TEXT, status TEXT DEFAULT 'unused'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL, created_at TEXT, kami_code TEXT,
                activated_at TEXT, is_agent INTEGER DEFAULT 0,
                agent_kami_code TEXT, wechat_id TEXT, agent_quota INTEGER DEFAULT 50
            )
        """)
        for col in ["type","created_by"]:
            try: conn.execute(f"ALTER TABLE kami_codes ADD COLUMN {col} TEXT")
            except: pass
        for col in ["is_agent","agent_kami_code","wechat_id","agent_quota"]:
            try: conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            except: pass
        conn.commit()
        return conn

    def query(conn, sql, params=None):
        return conn.execute(sql, params or [])

    def fetchone(conn, sql, params=None):
        return conn.execute(sql, params or []).fetchone()

    def fetchall(conn, sql, params=None):
        return conn.execute(sql, params or []).fetchall()

    PLACEHOLDER = "?"

def gen_code(length=16):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def row_to_dict(row):
    if not row: return None
    return dict(row)

@app.route('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), 'kami_frontend.html'), encoding='utf-8').read()

# ===== 注册登录 =====
@app.route('/api/register', methods=['POST'])
def register():
    d = request.get_json()
    u, p = d.get('username','').strip(), d.get('password','').strip()
    if not u or not p: return jsonify({"success":False,"message":"请填写完整"})
    if len(p) < 6: return jsonify({"success":False,"message":"密码至少6位"})
    db = get_db()
    if fetchone(db, f"SELECT id FROM users WHERE username={PLACEHOLDER}", (u,)):
        db.close(); return jsonify({"success":False,"message":"用户名已存在"})
    h = hashlib.sha256(p.encode()).hexdigest()
    n = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute(f"INSERT INTO users (username, password, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})", (u, h, n))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"注册成功"})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    u, p = d.get('username','').strip(), d.get('password','').strip()
    h = hashlib.sha256(p.encode()).hexdigest()
    db = get_db()
    user = row_to_dict(fetchone(db, f"SELECT * FROM users WHERE username={PLACEHOLDER} AND password={PLACEHOLDER}", (u, h)))
    db.close()
    if user:
        return jsonify({"success":True,"username":u,"kami_code":user.get("kami_code") or "","is_agent":user.get("is_agent",0),"agent_kami_code":user.get("agent_kami_code") or ""})
    return jsonify({"success":False,"message":"用户名或密码错误"})

# ===== 会员卡密激活（16位）=====
@app.route('/api/activate', methods=['POST'])
def activate():
    d = request.get_json()
    u, c = d.get('username',''), d.get('code','').strip().upper()
    db = get_db()
    user = row_to_dict(fetchone(db, f"SELECT kami_code FROM users WHERE username={PLACEHOLDER}", (u,)))
    if user and user.get("kami_code"):
        if user["kami_code"] == c:
            db.close(); return jsonify({"success":True,"message":"已激活，无需重复操作"})
        db.close(); return jsonify({"success":False,"message":"该账号已绑定其他卡密"})
    row = row_to_dict(fetchone(db, f"SELECT * FROM kami_codes WHERE code={PLACEHOLDER} AND status='unused' AND type='member'", (c,)))
    if not row:
        used = fetchone(db, f"SELECT * FROM kami_codes WHERE code={PLACEHOLDER} AND status='used'", (c,))
        db.close(); return jsonify({"success":False,"message":"卡密已被使用" if used else "卡密无效"})
    n = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute(f"UPDATE kami_codes SET status='used', used_by={PLACEHOLDER}, used_at={PLACEHOLDER} WHERE id={PLACEHOLDER}", (u, n, row["id"]))
    db.execute(f"UPDATE users SET kami_code={PLACEHOLDER}, activated_at={PLACEHOLDER} WHERE username={PLACEHOLDER}", (c, n, u))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"激活成功！"})

# ===== 代理卡密激活（12位）=====
@app.route('/api/activate_agent', methods=['POST'])
def activate_agent():
    d = request.get_json()
    u, c, w = d.get('username',''), d.get('code','').strip().upper(), d.get('wechat_id','').strip()
    db = get_db()
    user = row_to_dict(fetchone(db, f"SELECT is_agent, agent_kami_code FROM users WHERE username={PLACEHOLDER}", (u,)))
    if user and user.get("is_agent") and user.get("agent_kami_code"):
        db.close(); return jsonify({"success":False,"message":"该账号已绑定代理卡密"})
    row = row_to_dict(fetchone(db, f"SELECT * FROM kami_codes WHERE code={PLACEHOLDER} AND status='unused' AND type='agent'", (c,)))
    if not row:
        used = fetchone(db, f"SELECT * FROM kami_codes WHERE code={PLACEHOLDER} AND status='used'", (c,))
        db.close(); return jsonify({"success":False,"message":"代理卡密无效或已使用" if used else "代理卡密无效"})
    n = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute(f"UPDATE kami_codes SET status='used', used_by={PLACEHOLDER}, used_at={PLACEHOLDER} WHERE id={PLACEHOLDER}", (u, n, row["id"]))
    db.execute(f"UPDATE users SET is_agent=1, agent_kami_code={PLACEHOLDER}, wechat_id={PLACEHOLDER} WHERE username={PLACEHOLDER}", (c, w, u))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"升级代理成功！"})

@app.route('/api/check_activated', methods=['POST'])
def check_activated():
    u = request.get_json().get('username','')
    db = get_db()
    user = row_to_dict(fetchone(db, f"SELECT kami_code, activated_at, is_agent, wechat_id, agent_quota FROM users WHERE username={PLACEHOLDER}", (u,)))
    db.close()
    if not user: return jsonify({"success":True,"activated":False})
    return jsonify({"success":True,"activated":bool(user.get("kami_code")),"is_agent":bool(user.get("is_agent",0)),"wechat_id":user.get("wechat_id") or "","agent_quota":user.get("agent_quota",50)})

# ===== 代理后台 =====
@app.route('/api/agent/generate', methods=['POST'])
def agent_generate():
    d = request.get_json()
    u, n = d.get('username',''), min(d.get('count',1), 20)
    db = get_db()
    user = row_to_dict(fetchone(db, f"SELECT * FROM users WHERE username={PLACEHOLDER} AND is_agent=1", (u,)))
    if not user: db.close(); return jsonify({"success":False,"message":"无权限"}), 403
    used = row_to_dict(fetchone(db, f"SELECT COUNT(*) as c FROM kami_codes WHERE type='member' AND created_by={PLACEHOLDER}", (u,)))
    used_cnt = used["c"] if used else 0
    remaining = user.get("agent_quota",50) - used_cnt
    if n > remaining: n = remaining
    if n <= 0: db.close(); return jsonify({"success":False,"message":f"剩余额度{remaining}张，不足"})
    codes = []
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        c = gen_code(16)
        try:
            db.execute(f"INSERT INTO kami_codes (code,type,created_at,created_by,status) VALUES ({PLACEHOLDER},'member',{PLACEHOLDER},{PLACEHOLDER},'unused')", (c, now_str, u))
            codes.append(c)
        except: pass
    db.commit(); db.close()
    return jsonify({"success":True,"count":len(codes),"codes":codes})

@app.route('/api/agent/info', methods=['POST'])
def agent_info():
    u = request.get_json().get('username','')
    db = get_db()
    user = row_to_dict(fetchone(db, f"SELECT * FROM users WHERE username={PLACEHOLDER} AND is_agent=1", (u,)))
    if not user: db.close(); return jsonify({"success":False}), 403
    used = row_to_dict(fetchone(db, f"SELECT COUNT(*) as c FROM kami_codes WHERE type='member' AND created_by={PLACEHOLDER}", (u,)))
    used_cnt = used["c"] if used else 0
    quota = user.get("agent_quota",50)
    db.close()
    return jsonify({"success":True,"wechat_id":user.get("wechat_id") or "","quota":quota,"used":used_cnt,"remaining":quota-used_cnt})

@app.route('/api/agent/list_codes', methods=['POST'])
def agent_list_codes():
    d = request.get_json()
    u, t = d.get('username',''), d.get('t','all')
    where = "" if t == "all" else f"AND status='{t}'"
    db = get_db()
    rows = fetchall(db, f"SELECT code, created_at, status, used_at FROM kami_codes WHERE type='member' AND created_by={PLACEHOLDER} {where} ORDER BY id DESC LIMIT 200", (u,))
    db.close()
    return jsonify({"success":True,"codes":[dict(r) for r in rows]})

@app.route('/api/agent/set_wechat', methods=['POST'])
def agent_set_wechat():
    d = request.get_json()
    db = get_db()
    db.execute(f"UPDATE users SET wechat_id={PLACEHOLDER} WHERE username={PLACEHOLDER}", (d.get('wechat_id',''), d.get('username','')))
    db.commit(); db.close()
    return jsonify({"success":True})

# ===== 管理后台 =====
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    return jsonify({"success": request.get_json().get('password','') == ADMIN_PASSWORD})

@app.route('/api/admin/generate', methods=['POST'])
def admin_generate():
    d = request.get_json()
    if d.get('password') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    cnt = min(d.get('count',1), 200)
    tp = d.get('type','member')
    clen = 12 if tp == 'agent' else 16
    db = get_db(); codes = []
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(cnt):
        c = gen_code(clen)
        try:
            db.execute(f"INSERT INTO kami_codes (code,type,created_at,status) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},'unused')", (c, tp, now_str))
            codes.append(c)
        except: pass
    db.commit(); db.close()
    return jsonify({"success":True,"count":len(codes),"codes":codes,"type":tp})

@app.route('/api/admin/list')
def admin_list():
    if request.args.get('pw','') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    tab, tp = request.args.get('t','unused'), request.args.get('type','all')
    db = get_db()
    wt = "" if tp == 'all' else f"AND type='{tp}'"
    rows = fetchall(db, f"SELECT * FROM kami_codes WHERE status='{tab}' {wt} ORDER BY id DESC LIMIT 500")
    stats = row_to_dict(fetchone(db, "SELECT COUNT(*) as total FROM kami_codes")) or {}
    u = row_to_dict(fetchone(db, "SELECT COUNT(*) as c FROM kami_codes WHERE status='unused'")) or {}
    s = row_to_dict(fetchone(db, "SELECT COUNT(*) as c FROM kami_codes WHERE status='used'")) or {}
    mt = row_to_dict(fetchone(db, "SELECT COUNT(*) as c FROM kami_codes WHERE type='member' AND status='unused'")) or {}
    at = row_to_dict(fetchone(db, "SELECT COUNT(*) as c FROM kami_codes WHERE type='agent' AND status='unused'")) or {}
    db.close()
    return jsonify({"success":True,"codes":[dict(r) for r in rows],
        "stats":{"total":stats.get("total",0),"unused":u.get("c",0),"used":s.get("c",0),"member":mt.get("c",0),"agent":at.get("c",0)}})

@app.route('/api/admin/delete', methods=['POST'])
def admin_delete():
    d = request.get_json()
    if d.get('password') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    db = get_db(); db.execute(f"DELETE FROM kami_codes WHERE id={PLACEHOLDER}", (d['id'],)); db.commit(); db.close()
    return jsonify({"success":True})

@app.route('/api/admin/users')
def admin_users():
    if request.args.get('pw','') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    db = get_db()
    rows = fetchall(db, "SELECT username, created_at, kami_code, activated_at, is_agent, agent_kami_code, wechat_id, agent_quota FROM users ORDER BY id DESC LIMIT 200")
    db.close()
    return jsonify({"success":True,"users":[dict(r) for r in rows]})

@app.route('/api/get_agent_wechat', methods=['POST'])
def get_agent_wechat():
    code = request.get_json().get('code','').strip().upper()
    db = get_db()
    row = row_to_dict(fetchone(db, f"SELECT created_by FROM kami_codes WHERE code={PLACEHOLDER} AND created_by IS NOT NULL", (code,)))
    if row:
        agent = row_to_dict(fetchone(db, f"SELECT wechat_id FROM users WHERE username={PLACEHOLDER}", (row["created_by"],)))
        if agent and agent.get("wechat_id"):
            db.close(); return jsonify({"success":True,"wechat_id":agent["wechat_id"]})
    db.close()
    return jsonify({"success":False,"message":"无客服信息"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9876))
    db_type = "PostgreSQL" if DB_URL else "SQLite"
    print("="*55)
    print(" 拼小豆卡密分销系统")
    print(f" 数据库: {db_type}")
    print(f" 地址: http://127.0.0.1:{port}")
    print(f" 管理密码: {ADMIN_PASSWORD}")
    print(f" 会员卡密: 16位 | 代理卡密: 12位")
    print("="*55)
    app.run(host='0.0.0.0', port=port, debug=False)
