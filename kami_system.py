#!/usr/bin/env python3
import flask, os, random, string, datetime, hashlib
from flask import Flask, request, jsonify
app = Flask(__name__); ADMIN_PASSWORD = "WzS18350168663."
DB_URL = os.environ.get("DATABASE_URL", "")
PERMANENT = "2099-12-31 23:59:59"
DUR = {"1d":{"l":"天卡","d":1},"7d":{"l":"周卡","d":7},"perm":{"l":"永久","d":99999}}
AQ = {"1d":10,"7d":50,"perm":999}
PH = "?" if not DB_URL else "%s"

def get_db():
    if DB_URL:
        try:
            import psycopg2, psycopg2.extras
            c = psycopg2.connect(DB_URL); c.autocommit=False; cr = c.cursor()
            cr.execute("CREATE TABLE IF NOT EXISTS kami_codes (id SERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, card_type TEXT DEFAULT 'member', duration TEXT DEFAULT 'perm', duration_days INTEGER DEFAULT 99999, created_at TEXT, created_by TEXT, used_by TEXT, used_at TEXT, status TEXT DEFAULT 'unused')")
            cr.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TEXT, kami_code TEXT, member_type TEXT, activated_at TEXT, member_expire_at TEXT, is_agent INTEGER DEFAULT 0, agent_kami_code TEXT, wechat_id TEXT, agent_quota INTEGER DEFAULT 50)")
            c.commit()
            def q(sql,p=None): cr = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor); cr.execute(sql,p or []); return cr
            return c
        except: pass
    import sqlite3
    dp = os.path.join(os.path.dirname(__file__), "kami_data.db")
    c = sqlite3.connect(dp); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS kami_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, card_type TEXT DEFAULT 'member', duration TEXT DEFAULT 'perm', duration_days INTEGER DEFAULT 99999, created_at TEXT, created_by TEXT, used_by TEXT, used_at TEXT, status TEXT DEFAULT 'unused')")
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TEXT, kami_code TEXT, member_type TEXT, activated_at TEXT, member_expire_at TEXT, is_agent INTEGER DEFAULT 0, agent_kami_code TEXT, wechat_id TEXT, agent_quota INTEGER DEFAULT 50)")
    for col in ["card_type","duration","duration_days","member_type","member_expire_at"]:
        try: c.execute(f"ALTER TABLE kami_codes ADD COLUMN {col} TEXT")
        except: pass
        try: c.execute(f"ALTER TABLE kami_codes ADD COLUMN {col} INTEGER")
        except: pass
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        except: pass
    c.commit()
    def q(sql,p=None): return c.execute(sql,p or [])
    return c

def gc(l=16): return ''.join(random.choices(string.ascii_uppercase+string.digits,k=l))
def q(db,sql,p=None): return db.execute(sql,p or [])
def fo(db,sql,p=None): r=db.execute(sql,p or []); return r.fetchone() if r else None
def fa(db,sql,p=None): return db.execute(sql,p or []).fetchall()
def rd(r): return dict(r) if r else None

@app.route('/')
def idx():
    return open(os.path.join(os.path.dirname(__file__),'kami_frontend.html'),encoding='utf-8').read()

@app.route('/api/register', methods=['POST'])
def reg():
    d=request.get_json(); u=d.get('username','').strip(); p=d.get('password','').strip()
    if not u or not p: return jsonify({"s":False,"m":"请填写完整"})
    if len(p)<6: return jsonify({"s":False,"m":"密码至少6位"})
    db=get_db()
    if fo(db,f"SELECT id FROM users WHERE username={PH}",(u,)): db.close(); return jsonify({"s":False,"m":"用户名已存在"})
    h=hashlib.sha256(p.encode()).hexdigest(); n=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    q(db,f"INSERT INTO users (username,password,created_at) VALUES ({PH},{PH},{PH})",(u,h,n))
    db.commit(); db.close(); return jsonify({"s":True,"m":"注册成功"})

@app.route('/api/login', methods=['POST'])
def lgn():
    d=request.get_json(); u=d.get('username','').strip(); p=d.get('password','').strip()
    h=hashlib.sha256(p.encode()).hexdigest()
    db=get_db(); us=rd(fo(db,f"SELECT * FROM users WHERE username={PH} AND password={PH}",(u,h))); db.close()
    if us: return jsonify({"s":True,"un":u,"kc":us.get("kami_code") or "","mt":us.get("member_type") or "","ia":us.get("is_agent",0),"ak":us.get("agent_kami_code") or ""})
    return jsonify({"s":False,"m":"用户名或密码错误"})

@app.route('/api/activate', methods=['POST'])
def act():
    d=request.get_json(); u=d.get('username',''); c=d.get('code','').strip().upper()
    db=get_db(); us=rd(fo(db,f"SELECT kami_code,member_expire_at FROM users WHERE username={PH}",(u,)))
    if us and us.get("kami_code"):
        if us["kami_code"]==c: db.close(); return jsonify({"s":True,"m":"已激活"})
        if us.get("member_expire_at"):
            try:
                if datetime.datetime.strptime(us["member_expire_at"],'%Y-%m-%d %H:%M:%S')>datetime.datetime.now():
                    db.close(); return jsonify({"s":False,"m":"该账号已有有效卡密"})
            except: pass
    r=rd(fo(db,f"SELECT * FROM kami_codes WHERE code={PH} AND status='unused' AND card_type LIKE 'm%'",(c,)))
    if not r:
        used=fo(db,f"SELECT * FROM kami_codes WHERE code={PH} AND status='used'",(c,))
        db.close(); return jsonify({"s":False,"m":"卡密已被使用" if used else "卡密无效"})
    n=datetime.datetime.now(); dd=r["duration_days"]; exp=(n+datetime.timedelta(days=int(dd))).strftime('%Y-%m-%d %H:%M:%S')
    ns=n.strftime('%Y-%m-%d %H:%M:%S')
    if dd>=99999: exp=PERMANENT
    q(db,f"UPDATE kami_codes SET status='used', used_by={PH}, used_at={PH} WHERE id={PH}",(u,ns,r["id"]))
    q(db,f"UPDATE users SET kami_code={PH}, member_type={PH}, activated_at={PH}, member_expire_at={PH} WHERE username={PH}",(c,r["duration"],ns,exp,u))
    db.commit(); db.close()
    return jsonify({"s":True,"m":f"激活成功！有效期至{exp[:10]}"})

@app.route('/api/activate_agent', methods=['POST'])
def act_ag():
    d=request.get_json(); u=d.get('username',''); c=d.get('code','').strip().upper(); w=d.get('wechat_id','').strip()
    db=get_db(); us=rd(fo(db,f"SELECT is_agent,agent_kami_code FROM users WHERE username={PH}",(u,)))
    if us and us.get("is_agent") and us.get("agent_kami_code"): db.close(); return jsonify({"s":False,"m":"已绑定代理卡密"})
    r=rd(fo(db,f"SELECT * FROM kami_codes WHERE code={PH} AND status='unused' AND card_type LIKE 'a%'",(c,)))
    if not r:
        used=fo(db,f"SELECT * FROM kami_codes WHERE code={PH} AND status='used'",(c,))
        db.close(); return jsonify({"s":False,"m":"代理卡密无效或已使用" if used else "代理卡密无效"})
    ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'); qa=AQ.get(r["duration"],50)
    q(db,f"UPDATE kami_codes SET status='used', used_by={PH}, used_at={PH} WHERE id={PH}",(u,ns,r["id"]))
    q(db,f"UPDATE users SET is_agent=1, agent_kami_code={PH}, wechat_id={PH}, agent_quota={PH} WHERE username={PH}",(c,w,qa,u))
    db.commit(); db.close(); return jsonify({"s":True,"m":"升级代理成功","aq":qa})

@app.route('/api/check', methods=['POST'])
def chk():
    u=request.get_json().get('username','')
    db=get_db(); us=rd(fo(db,f"SELECT * FROM users WHERE username={PH}",(u,))); db.close()
    if not us: return jsonify({"s":True,"act":False})
    act=False; es=us.get("member_expire_at")
    if us.get("kami_code") and es:
        if es==PERMANENT: act=True
        else:
            try:
                if datetime.datetime.strptime(es,'%Y-%m-%d %H:%M:%S')>datetime.datetime.now(): act=True
            except: pass
    return jsonify({"s":True,"act":act,"mt":us.get("member_type") or "","me":es or "","ia":bool(us.get("is_agent",0)),"wi":us.get("wechat_id") or "","aq":us.get("agent_quota",50)})

@app.route('/api/agent/generate', methods=['POST'])
def ag_gen():
    d=request.get_json(); u=d.get('username',''); n=min(d.get('count',1),20)
    db=get_db(); us=rd(fo(db,f"SELECT * FROM users WHERE username={PH} AND is_agent=1",(u,)))
    if not us: db.close(); return jsonify({"s":False,"m":"无权限"}),403
    ud=rd(fo(db,f"SELECT COUNT(*) as c FROM kami_codes WHERE created_by={PH}",(u,)))
    uc=ud["c"] if ud else 0; qa=us.get("agent_quota",50); rm=qa-uc
    if n>rm: n=rm
    if n<=0: db.close(); return jsonify({"s":False,"m":f"剩余配额{max(0,rm)}张"})
    cs=[]; ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        c=gc(16)
        try: q(db,f"INSERT INTO kami_codes (code,card_type,duration,duration_days,created_at,created_by,status) VALUES ({PH},'member_perm','perm',99999,{PH},{PH},'unused')",(c,ns,u)); cs.append(c)
        except: pass
    db.commit(); db.close(); return jsonify({"s":True,"c":len(cs),"cs":cs})

@app.route('/api/agent/info', methods=['POST'])
def ag_info():
    u=request.get_json().get('username','')
    db=get_db(); us=rd(fo(db,f"SELECT * FROM users WHERE username={PH} AND is_agent=1",(u,)))
    if not us: db.close(); return jsonify({"s":False}),403
    ud=rd(fo(db,f"SELECT COUNT(*) as c FROM kami_codes WHERE created_by={PH}",(u,))); uc=ud["c"] if ud else 0
    qa=us.get("agent_quota",50); db.close()
    return jsonify({"s":True,"wi":us.get("wechat_id") or "","qa":qa,"ud":uc,"rm":qa-uc})

@app.route('/api/agent/list_codes', methods=['POST'])
def ag_list():
    d=request.get_json(); u=d.get('username',''); t=d.get('t','all')
    wh="" if t=="all" else f"AND status='{t}'"
    db=get_db(); rs=fa(db,f"SELECT code,created_at,status,used_at FROM kami_codes WHERE card_type LIKE 'm%' AND created_by={PH} {wh} ORDER BY id DESC LIMIT 200",(u,))
    db.close(); return jsonify({"s":True,"cs":[dict(r) for r in rs]})

@app.route('/api/agent/set_wechat', methods=['POST'])
def ag_wx():
    d=request.get_json(); db=get_db()
    q(db,f"UPDATE users SET wechat_id={PH} WHERE username={PH}",(d.get('wechat_id',''),d.get('username','')))
    db.commit(); db.close(); return jsonify({"s":True})

@app.route('/api/admin/login', methods=['POST'])
def ad_lg():
    return jsonify({"s":request.get_json().get('password','')==ADMIN_PASSWORD})

@app.route('/api/admin/gen', methods=['POST'])
def ad_gen():
    d=request.get_json()
    if d.get('pw')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    n=min(d.get('n',1),200); ct=d.get('ct','m_perm')
    p=ct.split('_'); dr=p[1] if len(p)>1 else "perm"
    du=DUR.get(dr,DUR["perm"]); cl=12 if ct.startswith("a") else 16
    db=get_db(); cs=[]; ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        c=gc(cl)
        try: q(db,f"INSERT INTO kami_codes (code,card_type,duration,duration_days,created_at,status) VALUES ({PH},{PH},{PH},{PH},{PH},'unused')",(c,ct,dr,du["d"],ns)); cs.append(c)
        except: pass
    db.commit(); db.close(); return jsonify({"s":True,"c":len(cs),"cs":cs,"ct":ct})

@app.route('/api/admin/list')
def ad_ls():
    if request.args.get('pw','')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    tb=request.args.get('t','unused'); tp=request.args.get('tp','all')
    db=get_db()
    wt="" if tp=="all" else f"AND card_type LIKE '{tp}%'"
    rs=fa(db,f"SELECT * FROM kami_codes WHERE status='{tb}' {wt} ORDER BY id DESC LIMIT 500")
    tl=rd(fo(db,"SELECT COUNT(*) as c FROM kami_codes")); ul=rd(fo(db,"SELECT COUNT(*) as c FROM kami_codes WHERE status='unused'"))
    sl=rd(fo(db,"SELECT COUNT(*) as c FROM kami_codes WHERE status='used'")); mc=rd(fo(db,"SELECT COUNT(*) as c FROM kami_codes WHERE card_type LIKE 'm%' AND status='unused'"))
    ac=rd(fo(db,"SELECT COUNT(*) as c FROM kami_codes WHERE card_type LIKE 'a%' AND status='unused'"))
    db.close()
    return jsonify({"s":True,"cs":[dict(r) for r in rs],"st":{"tl":tl["c"] if tl else 0,"ul":ul["c"] if ul else 0,"sl":sl["c"] if sl else 0,"mc":mc["c"] if mc else 0,"ac":ac["c"] if ac else 0}})

@app.route('/api/admin/delete', methods=['POST'])
def ad_dl():
    d=request.get_json()
    if d.get('pw')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    db=get_db(); q(db,f"DELETE FROM kami_codes WHERE id={PH}",(d['id'],)); db.commit(); db.close()
    return jsonify({"s":True})

@app.route('/api/admin/users')
def ad_us():
    if request.args.get('pw','')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    db=get_db()
    rs=fa(db,"SELECT username,created_at,kami_code,member_type,member_expire_at,activated_at,is_agent,agent_kami_code,wechat_id,agent_quota FROM users ORDER BY id DESC LIMIT 200")
    db.close(); return jsonify({"s":True,"us":[dict(r) for r in rs]})

@app.route('/api/get_agent_wechat', methods=['POST'])
def gwx():
    cd=request.get_json().get('code','').strip().upper()
    db=get_db(); r=rd(fo(db,f"SELECT created_by FROM kami_codes WHERE code={PH} AND created_by IS NOT NULL",(cd,)))
    if r:
        a=rd(fo(db,f"SELECT wechat_id FROM users WHERE username={PH}",(r["created_by"],)))
        if a and a.get("wechat_id"): db.close(); return jsonify({"s":True,"wi":a["wechat_id"]})
    db.close(); return jsonify({"s":False,"m":"无客服信息"})

if __name__=='__main__':
    p=int(os.environ.get('PORT',9876))
    print(f"Pindou Kami System running on {p}")
    app.run(host='0.0.0.0',port=p,debug=False)
