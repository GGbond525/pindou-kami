#!/usr/bin/env python3
"""拼小豆 - 卡密分销系统"""
import flask, sqlite3, os, random, string, datetime, hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)
ADMIN_PASSWORD = "WzS18350168663."
DB_PATH = os.path.join(os.path.dirname(__file__), "kami_data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS kami_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, created_at TEXT, used_at TEXT, status TEXT DEFAULT 'unused')")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TEXT, kami_code TEXT, activated_at TEXT)")
    conn.commit()
    return conn

def gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

@app.route('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), 'kami_frontend.html'), encoding='utf-8').read()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username','').strip()
    password = data.get('password','').strip()
    if not username or not password:
        return jsonify({"success":False,"message":"请输入用户名和密码"})
    if len(password) < 6:
        return jsonify({"success":False,"message":"密码至少6位"})
    db = get_db()
    exists = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if exists:
        db.close()
        return jsonify({"success":False,"message":"用户名已存在"})
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute("INSERT INTO users (username, password, created_at) VALUES (?,?,?)", (username, pw_hash, now))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"注册成功，请登录"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username','').strip()
    password = data.get('password','').strip()
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, pw_hash)).fetchone()
    db.close()
    if user:
        return jsonify({"success":True,"message":"登录成功","username":username,"kami_code":user['kami_code'] or ''})
    return jsonify({"success":False,"message":"用户名或密码错误"})

@app.route('/api/activate', methods=['POST'])
def activate():
    data = request.get_json()
    username = data.get('username','')
    code = data.get('code','').strip().upper()
    db = get_db()
    # 验证卡密
    row = db.execute("SELECT * FROM kami_codes WHERE code=? AND status='unused'", (code,)).fetchone()
    if not row:
        row2 = db.execute("SELECT * FROM kami_codes WHERE code=? AND status='used'", (code,)).fetchone()
        db.close()
        return jsonify({"success":False,"message":"卡密已被使用" if row2 else "卡密无效"})
    # 标记卡密已用
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute("UPDATE kami_codes SET status='used', used_at=? WHERE id=?", (now, row['id']))
    # 记录到用户
    db.execute("UPDATE users SET kami_code=?, activated_at=? WHERE username=?", (code, now, username))
    db.commit(); db.close()
    return jsonify({"success":True,"message":"激活成功"})

@app.route('/api/check_activated', methods=['POST'])
def check_activated():
    data = request.get_json()
    username = data.get('username','')
    db = get_db()
    user = db.execute("SELECT kami_code, activated_at FROM users WHERE username=?", (username,)).fetchone()
    db.close()
    if user and user['kami_code']:
        return jsonify({"success":True,"activated":True,"kami_code":user['kami_code']})
    return jsonify({"success":True,"activated":False})

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    return jsonify({"success": request.get_json().get('password','') == ADMIN_PASSWORD})

@app.route('/api/admin/generate', methods=['POST'])
def admin_generate():
    d = request.get_json()
    if d.get('password') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    n = min(d.get('count',1), 200)
    db = get_db(); codes = []
    for _ in range(n):
        c = gen_code()
        try:
            db.execute("INSERT INTO kami_codes (code,created_at,status) VALUES (?,?,'unused')", (c, datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
            codes.append(c)
        except: pass
    db.commit(); db.close()
    return jsonify({"success":True,"count":len(codes),"codes":codes})

@app.route('/api/admin/list')
def admin_list():
    if request.args.get('pw','') != ADMIN_PASSWORD: return jsonify({"success":False}), 403
    tab = request.args.get('t','unused')
    db = get_db()
    rows = db.execute(f"SELECT * FROM kami_codes WHERE status='{tab}' ORDER BY id DESC LIMIT 500").fetchall()
    t = db.execute("SELECT COUNT(*) as c FROM kami_codes").fetchone()['c']
    u = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE status='unused'").fetchone()['c']
    s = db.execute("SELECT COUNT(*) as c FROM kami_codes WHERE status='used'").fetchone()['c']
    db.close()
    return jsonify({"success":True,"codes":[dict(r) for r in rows],"stats":{"total":t,"unused":u,"used":s}})

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
    rows = db.execute("SELECT username, created_at, kami_code, activated_at FROM users ORDER BY id DESC LIMIT 200").fetchall()
    db.close()
    return jsonify({"success":True,"users":[dict(r) for r in rows]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9876))
    print("="*55)
    print(" 拼小豆卡密分销系统")
    print(f" 地址: http://127.0.0.1:{port}")
    print(f" 管理密码: {ADMIN_PASSWORD}")
    print("="*55)
    app.run(host='0.0.0.0', port=port, debug=False)
