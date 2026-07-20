#!/usr/bin/env python3
"""拼小豆 - 卡密分销系统（会员16位 + 代理12位）"""
import flask, sqlite3, os, random, string, datetime, hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)
ADMIN_PASSWORD = "WzS18350168663."
DB_PATH = os.path.join(os.path.dirname(__file__), "kami_data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS kami_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, type TEXT NOT NULL DEFAULT 'member', created_at TEXT, used_by TEXT, used_at TEXT, status TEXT DEFAULT 'unused')")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TEXT, kami_code TEXT, activated_at TEXT, is_agent INTEGER DEFAULT 0, agent_kami_code TEXT, wechat_id TEXT, agent_quota INTEGER DEFAULT 50)")
    # 迁移：旧表新增type列
    try: conn.execute("ALTER TABLE kami_codes ADD COLUMN type TEXT NOT NULL DEFAULT 'member'")
    except: pass
    try: conn.execute("ALTER TABLE users ADD COLUMN is_agent INTEGER DEFAULT 0")
    except: pass
    try: conn.execute("ALTER TABLE users ADD COLUMN agent_kami_code TEXT")
    except: pass
    try: conn.execute("ALTER TABLE users ADD COLUMN wechat_id TEXT")
    except: pass
    try: conn.execute("ALTER TABLE users ADD COLUMN agent_quota INTEGER DEFAULT 50")
    except: pass
    conn.commit()
    return conn

def gen_code(length=16):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.route('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), 'kami_frontend.html'), encoding='utf-8').read()

# ===== 注册登录 =====
@app.route('/api/register', methods=['POST'])
def register():
    d = request.get_json()
    u = d.get('username','').strip()
    p = d.get('password','').strip()
    if not u or not p: return jsonify({"success":False,"message":"请填写完整"})
    if len(p) < 6: return jsonify({"success":False,"message":"密码至少6位"})
    db = get_db()
    if db.execute("SELECT id FROM users WHERE username=?", (u,)).fetchone():
        db.close(); return jsonify({"success":False,"message":"用户名已存在"})
    h = hashlib.sha256(p.encode()).hexdigest()
    n = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute("INSERT INTO users (username, password, created_at) VALUES (?,?,?)", (u, h, n))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"注册成功"})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    u, p = d.get('username','').strip(), d.get('password','').strip()
    h = hashlib.sha256(p.encode()).hexdigest()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (u, h)).fetchone()
    db.close()
    if user:
        return jsonify({"success":True,"username":u,"kami_code":user["kami_code"] or "","is_agent":user["is_agent"],"agent_kami_code":user["agent_kami_code"] or ""})
    return jsonify({"success":False,"message":"用户名或密码错误"})

# ===== 会员卡密激活（16位）=====
@app.route('/api/activate', methods=['POST'])
def activate():
    d = request.get_json()
    u, c = d.get('username',''), d.get('code','').strip().upper()
    db = get_db()
    row = db.execute("SELECT * FROM kami_codes WHERE code=? AND status='unused' AND type='member'", (c,)).fetchone()
    if not row:
        used = db.execute("SELECT * FROM kami_codes WHERE code=? AND status='used'", (c,)).fetchone()
        db.close(); return jsonify({"success":False,"message":"卡密已被使用" if used else "卡密无效"})
    n = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute("UPDATE kami_codes SET status='used', used_by=?, used_at=? WHERE id=?", (u, n, row['id']))
    db.execute("UPDATE users SET kami_code=?, activated_at=? WHERE username=?", (c, n, u))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"激活成功！"})

# ===== 代理卡密激活（12位）=====
@app.route('/api/activate_agent', methods=['POST'])
def activate_agent():
    d = request.get_json()
    u, c, w = d.get('username',''), d.get('code','').strip().upper(), d.get('wechat_id','').strip()
    db = get_db()
    row = db.execute("SELECT * FROM kami_codes WHERE code=? AND status='unused' AND type='agent'", (c,)).fetchone()
    if not row:
        used = db.execute("SELECT * FROM kami_codes WHERE code=? AND status='used'", (c,)).fetchone()
        db.close(); return jsonify({"success":False,"message":"代理卡密无效或已使用" if used else "代理卡密无效"})
    n = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute("UPDATE kami_codes SET status='used', used_by=?, used_at=? WHERE id=?", (u, n, row['id']))
    db.execute("UPDATE users SET is_agent=1, agent_kami_code=?, wechat_id=? WHERE username=?", (c, w, u))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"升级代理成功！"})

@app.route('/api/check_activated', methods=['POST'])
def check_activated():
    u = request.get_json().get('username','')
    db = get_db()
    user = db.execute("SELECT kami_code, activated_at, is_agent, agent_kami_code, wechat_id, agent_quota FROM users WHERE username=?", (u,)).fetchone()
    db.close()
    if not user: return jsonify({"success":True,"activated":False})
    return jsonify({"success":True,"activated":bool(user["kami_code"]),"is_agent":bool(user["is_agent"]),"wechat_id":user["wechat_id"] or "","agent_quota":user["agent_quota"]})

# ===== 代理后台 =====
@app.route('/api/agent/generate', methods=['POST'])
def agent_generate():
    d = request.get_json()
    u, n = d.get('username',''), min(d.get('count',1), 20)
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND is_agent=1", (u,)).fetchone()
    if not user: db.close(); return jsonify({"success":False,"message":"无权限"}), 403
    used = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE type='member' AND used_by=?", (u,)).fetchone()['c']
    remaining = user['agent_quota'] - used
    if n > remaining: n = remaining
    if n <= 0: db.close(); return jsonify({"success":False,"message":f"剩余额度{remaining}张，不足"})
    codes = []
    for _ in range(n):
        c = gen_code(16)
        try:
            db.execute("INSERT INTO kami_codes (code,type,created_at,status) VALUES (?,'member',?,'unused')", (c, datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
            codes.append(c)
        except: pass
    db.commit(); db.close()
    return jsonify({"success":True,"count":len(codes),"codes":codes})

@app.route('/api/agent/info', methods=['POST'])
def agent_info():
    u = request.get_json().get('username','')
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND is_agent=1", (u,)).fetchone()
    if not user: db.close(); return jsonify({"success":False}), 403
    used = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE type='member' AND used_by=?", (u,)).fetchone()['c']
    db.close()
    return jsonify({"success":True,"wechat_id":user["wechat_id"] or "","quota":user["agent_quota"],"used":used,"remaining":user["agent_quota"]-used})

@app.route('/api/agent/set_wechat', methods=['POST'])
def agent_set_wechat():
    d = request.get_json()
    db = get_db()
    db.execute("UPDATE users SET wechat_id=? WHERE username=?", (d.get('wechat_id',''), d.get('username','')))
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
    for _ in range(cnt):
        c = gen_code(clen)
        try:
            db.execute("INSERT INTO kami_codes (code,type,created_at,status) VALUES (?,?,?,'unused')", (c, tp, datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
            codes.append(c)
        except: pass
    db.commit(); db.close()
    return jsonify({"success":True,"count":len(codes),"codes":codes,"type":t})

@app.route('/api/admin/list')
def admin_list():
    if request.args.get('pw','') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    tab, tp = request.args.get('t','unused'), request.args.get('type','all')
    db = get_db()
    wt = "" if tp == 'all' else f"AND type='{tp}'"
    rows = db.execute(f"SELECT * FROM kami_codes WHERE status='{tab}' {wt} ORDER BY id DESC LIMIT 500").fetchall()
    t = db.execute("SELECT COUNT(*) as c FROM kami_codes").fetchone()['c']
    u = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE status='unused'").fetchone()['c']
    s = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE status='used'").fetchone()['c']
    mt = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE type='member' AND status='unused'").fetchone()['c']
    at = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE type='agent' AND status='unused'").fetchone()['c']
    db.close()
    return jsonify({"success":True,"codes":[dict(r) for r in rows],
        "stats":{"total":t,"unused":u,"used":s,"member":mt,"agent":at}})

@app.route('/api/admin/delete', methods=['POST'])
def admin_delete():
    d = request.get_json()
    if d.get('password') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    db = get_db(); db.execute("DELETE FROM kami_codes WHERE id=?", (d['id'],)); db.commit(); db.close()
    return jsonify({"success":True})

@app.route('/api/admin/users')
def admin_users():
    if request.args.get('pw','') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    db = get_db()
    rows = db.execute("SELECT username, created_at, kami_code, activated_at, is_agent, agent_kami_code, wechat_id, agent_quota FROM users ORDER BY id DESC LIMIT 200").fetchall()
    db.close()
    return jsonify({"success":True,"users":[dict(r) for r in rows]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9876))
    print("="*55)
    print(" 拼小豆卡密分销系统")
    print(f" 地址: http://127.0.0.1:{port}")
    print(f" 管理密码: {ADMIN_PASSWORD}")
    print(" 会员卡密: 16位 | 代理卡密: 12位")
    print("="*55)
    app.run(host='0.0.0.0', port=port, debug=False)
