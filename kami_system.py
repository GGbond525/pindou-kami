#!/usr/bin/env python3
import flask, os, random, string, datetime, hashlib
from flask import Flask, request, jsonify
app = Flask(__name__); ADMIN_PASSWORD = "WzS18350168663."
DB_URL = os.environ.get("DATABASE_URL", "")
PERMANENT = "2099-12-31 23:59:59"
DUR = {"1d":{"l":"天卡","d":1},"7d":{"l":"周卡","d":7},"perm":{"l":"永久","d":99999}}
AQ = {"1d":10,"7d":50,"perm":999}
if DB_URL:
    import psycopg2, psycopg2.extras
    def gd():
        c = psycopg2.connect(DB_URL); c.autocommit=False; cr = c.cursor()
        cr.execute("CREATE TABLE IF NOT EXISTS kc (id SERIAL PRIMARY KEY, co TEXT UNIQUE NOT NULL, cd TEXT NOT NULL DEFAULT 'm_perm', dr TEXT DEFAULT 'perm', dd INTEGER DEFAULT 99999, ca TEXT, cb TEXT, ub TEXT, ua TEXT, st TEXT DEFAULT 'unused')")
        cr.execute("CREATE TABLE IF NOT EXISTS us (id SERIAL PRIMARY KEY, un TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, ca TEXT, kc TEXT, mt TEXT, aa TEXT, me TEXT, ia INTEGER DEFAULT 0, ak TEXT, wi TEXT, aq INTEGER DEFAULT 50)")
        c.commit(); return c
    def q(c,s,p=None):
        cr = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor); cr.execute(s,p or []); return cr
    def fo(c,s,p=None): return q(c,s,p).fetchone()
    def fa(c,s,p=None): return q(c,s,p).fetchall()
    PH = "%s"
else:
    import sqlite3
    def gd():
        p = os.path.join(os.path.dirname(__file__), "kami_data.db"); c = sqlite3.connect(p); c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE IF NOT EXISTS kc (id INTEGER PRIMARY KEY AUTOINCREMENT, co TEXT UNIQUE NOT NULL, cd TEXT NOT NULL DEFAULT 'm_perm', dr TEXT DEFAULT 'perm', dd INTEGER DEFAULT 99999, ca TEXT, cb TEXT, ub TEXT, ua TEXT, st TEXT DEFAULT 'unused')")
        c.execute("CREATE TABLE IF NOT EXISTS us (id INTEGER PRIMARY KEY AUTOINCREMENT, un TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, ca TEXT, kc TEXT, mt TEXT, aa TEXT, me TEXT, ia INTEGER DEFAULT 0, ak TEXT, wi TEXT, aq INTEGER DEFAULT 50)")
        for x in ["kc","mt","me","dd"]:
            try: c.execute(f"ALTER TABLE us ADD COLUMN {x} TEXT")
            except: pass
            try: c.execute(f"ALTER TABLE kc ADD COLUMN {x} TEXT")
            except: pass
            try: c.execute(f"ALTER TABLE kc ADD COLUMN dd INTEGER")
            except: pass
        c.commit(); return c
    def q(c,s,p=None): return c.execute(s,p or [])
    def fo(c,s,p=None): return c.execute(s,p or []).fetchone()
    def fa(c,s,p=None): return c.execute(s,p or []).fetchall()
    PH = "?"
def gc(l=16): return ''.join(random.choices(string.ascii_uppercase+string.digits,k=l))
def rd(r): return dict(r) if r else None

@app.route('/')
def idx():
    return open(os.path.join(os.path.dirname(__file__),'kami_frontend.html'),encoding='utf-8').read()

@app.route('/api/register', methods=['POST'])
def reg():
    d=request.get_json(); u=d.get('username','').strip(); p=d.get('password','').strip()
    if not u or not p: return jsonify({"s":False,"m":"请填写完整"})
    if len(p)<6: return jsonify({"s":False,"m":"密码至少6位"})
    db=gd()
    if fo(db,f"SELECT id FROM us WHERE un={PH}",(u,)): db.close(); return jsonify({"s":False,"m":"用户名已存在"})
    h=hashlib.sha256(p.encode()).hexdigest(); n=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    db.execute(f"INSERT INTO us (un,pw,ca) VALUES ({PH},{PH},{PH})",(u,h,n))
    db.commit(); db.close(); return jsonify({"s":True,"m":"注册成功"})

@app.route('/api/login', methods=['POST'])
def lgn():
    d=request.get_json(); u=d.get('username','').strip(); p=d.get('password','').strip()
    h=hashlib.sha256(p.encode()).hexdigest()
    db=gd(); us=rd(fo(db,f"SELECT * FROM us WHERE un={PH} AND pw={PH}",(u,h))); db.close()
    if us: return jsonify({"s":True,"un":u,"kc":us.get("kc") or "","mt":us.get("mt") or "","ia":us.get("ia",0),"ak":us.get("ak") or ""})
    return jsonify({"s":False,"m":"用户名或密码错误"})

@app.route('/api/activate', methods=['POST'])
def act():
    d=request.get_json(); u=d.get('username',''); c=d.get('code','').strip().upper()
    db=gd(); us=rd(fo(db,f"SELECT kc,me FROM us WHERE un={PH}",(u,)))
    if us and us.get("kc"):
        if us["kc"]==c: db.close(); return jsonify({"s":True,"m":"已激活"})
        if us.get("me"):
            try:
                if datetime.datetime.strptime(us["me"],'%Y-%m-%d %H:%M:%S')>datetime.datetime.now():
                    db.close(); return jsonify({"s":False,"m":"该账号已有有效卡密"})
            except: pass
    r=rd(fo(db,f"SELECT * FROM kc WHERE co={PH} AND st='unused' AND cd LIKE 'm_%'",(c,)))
    if not r:
        used=fo(db,f"SELECT * FROM kc WHERE co={PH} AND st='used'",(c,))
        db.close(); return jsonify({"s":False,"m":"卡密已被使用" if used else "卡密无效"})
    n=datetime.datetime.now(); dd=r["dd"]; exp=(n+datetime.timedelta(days=int(dd))).strftime('%Y-%m-%d %H:%M:%S')
    ns=n.strftime('%Y-%m-%d %H:%M:%S')
    if dd>=99999: exp=PERMANENT
    db.execute(f"UPDATE kc SET st='used', ub={PH}, ua={PH} WHERE id={PH}",(u,ns,r["id"]))
    db.execute(f"UPDATE us SET kc={PH}, mt={PH}, aa={PH}, me={PH} WHERE un={PH}",(c,r["dr"],ns,exp,u))
    db.commit(); db.close()
    return jsonify({"s":True,"m":f"激活成功！有效期至{exp[:10]}"})

@app.route('/api/activate_agent', methods=['POST'])
def act_ag():
    d=request.get_json(); u=d.get('username',''); c=d.get('code','').strip().upper(); w=d.get('wechat_id','').strip()
    db=gd(); us=rd(fo(db,f"SELECT ia,ak FROM us WHERE un={PH}",(u,)))
    if us and us.get("ia") and us.get("ak"): db.close(); return jsonify({"s":False,"m":"已绑定代理卡密"})
    r=rd(fo(db,f"SELECT * FROM kc WHERE co={PH} AND st='unused' AND cd LIKE 'a_%'",(c,)))
    if not r:
        used=fo(db,f"SELECT * FROM kc WHERE co={PH} AND st='used'",(c,))
        db.close(); return jsonify({"s":False,"m":"代理卡密无效或已使用" if used else "代理卡密无效"})
    ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'); qa=AQ.get(r["dr"],50)
    db.execute(f"UPDATE kc SET st='used', ub={PH}, ua={PH} WHERE id={PH}",(u,ns,r["id"]))
    db.execute(f"UPDATE us SET ia=1, ak={PH}, wi={PH}, aq={PH} WHERE un={PH}",(c,w,qa,u))
    db.commit(); db.close(); return jsonify({"s":True,"m":"升级代理成功","aq":qa})

@app.route('/api/check', methods=['POST'])
def chk():
    u=request.get_json().get('username','')
    db=gd(); us=rd(fo(db,f"SELECT * FROM us WHERE un={PH}",(u,))); db.close()
    if not us: return jsonify({"s":True,"act":False})
    act=False; es=us.get("me")
    if us.get("kc") and es:
        if es==PERMANENT: act=True
        else:
            try:
                if datetime.datetime.strptime(es,'%Y-%m-%d %H:%M:%S')>datetime.datetime.now(): act=True
            except: pass
    return jsonify({"s":True,"act":act,"mt":us.get("mt") or "","me":es or "","ia":bool(us.get("ia",0)),"wi":us.get("wi") or "","aq":us.get("aq",50)})

@app.route('/api/agent/generate', methods=['POST'])
def ag_gen():
    d=request.get_json(); u=d.get('username',''); n=min(d.get('count',1),20)
    db=gd(); us=rd(fo(db,f"SELECT * FROM us WHERE un={PH} AND ia=1",(u,)))
    if not us: db.close(); return jsonify({"s":False,"m":"无权限"}),403
    ud=rd(fo(db,f"SELECT COUNT(*) as c FROM kc WHERE cb={PH}",(u,))); uc=ud["c"] if ud else 0
    qa=us.get("aq",50); rm=qa-uc
    if n>rm: n=rm
    if n<=0: db.close(); return jsonify({"s":False,"m":f"剩余配额{max(0,rm)}张"})
    cs=[]; ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        c=gc(16)
        try: db.execute(f"INSERT INTO kc (co,cd,dr,dd,ca,cb,st) VALUES ({PH},'m_perm','perm',99999,{PH},{PH},'unused')",(c,ns,u)); cs.append(c)
        except: pass
    db.commit(); db.close(); return jsonify({"s":True,"c":len(cs),"cs":cs})

@app.route('/api/agent/info', methods=['POST'])
def ag_info():
    u=request.get_json().get('username','')
    db=gd(); us=rd(fo(db,f"SELECT * FROM us WHERE un={PH} AND ia=1",(u,)))
    if not us: db.close(); return jsonify({"s":False}),403
    ud=rd(fo(db,f"SELECT COUNT(*) as c FROM kc WHERE cb={PH}",(u,))); uc=ud["c"] if ud else 0
    qa=us.get("aq",50); db.close()
    return jsonify({"s":True,"wi":us.get("wi") or "","qa":qa,"ud":uc,"rm":qa-uc})

@app.route('/api/agent/list', methods=['POST'])
def ag_list():
    d=request.get_json(); u=d.get('username',''); t=d.get('t','all')
    wh="" if t=="all" else f"AND st='{t}'"
    db=gd(); rs=fa(db,f"SELECT cd,ca,st,ua FROM kc WHERE cd LIKE 'm_%' AND cb={PH} {wh} ORDER BY id DESC LIMIT 200",(u,))
    db.close(); return jsonify({"s":True,"cs":[dict(r) for r in rs]})

@app.route('/api/agent/set_wx', methods=['POST'])
def ag_wx():
    d=request.get_json(); db=gd()
    db.execute(f"UPDATE us SET wi={PH} WHERE un={PH}",(d.get('wi',''),d.get('username','')))
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
    db=gd(); cs=[]; ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        c=gc(cl)
        try: db.execute(f"INSERT INTO kc (co,cd,dr,dd,ca,st) VALUES ({PH},{PH},{PH},{PH},{PH},'unused')",(c,ct,dr,du["d"],ns)); cs.append(c)
        except: pass
    db.commit(); db.close(); return jsonify({"s":True,"c":len(cs),"cs":cs,"ct":ct})

@app.route('/api/admin/list')
def ad_ls():
    if request.args.get('pw','')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    tb=request.args.get('t','unused'); tp=request.args.get('tp','all')
    db=gd()
    wt="" if tp=="all" else f"AND cd LIKE '{tp}%'"
    rs=fa(db,f"SELECT * FROM kc WHERE st='{tb}' {wt} ORDER BY id DESC LIMIT 500")
    def c(sql): r=fo(db,sql); return r["c"] if r else 0
    tl=c("SELECT COUNT(*) as c FROM kc"); ul=c("SELECT COUNT(*) as c FROM kc WHERE st='unused'")
    sl=c("SELECT COUNT(*) as c FROM kc WHERE st='used'")
    mc=c("SELECT COUNT(*) as c FROM kc WHERE cd LIKE 'm_%' AND st='unused'")
    ac=c("SELECT COUNT(*) as c FROM kc WHERE cd LIKE 'a_%' AND st='unused'")
    db.close()
    return jsonify({"s":True,"cs":[dict(r) for r in rs],"st":{"tl":tl,"ul":ul,"sl":sl,"mc":mc,"ac":ac}})

@app.route('/api/admin/del', methods=['POST'])
def ad_dl():
    d=request.get_json()
    if d.get('pw')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    db=gd(); db.execute(f"DELETE FROM kc WHERE id={PH}",(d['id'],)); db.commit(); db.close()
    return jsonify({"s":True})

@app.route('/api/admin/users')
def ad_us():
    if request.args.get('pw','')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    db=gd()
    rs=fa(db,"SELECT un,ca,kc,mt,me,aa,ia,ak,wi,aq FROM us ORDER BY id DESC LIMIT 200")
    db.close(); return jsonify({"s":True,"us":[dict(r) for r in rs]})

@app.route('/api/get_wx', methods=['POST'])
def gwx():
    cd=request.get_json().get('code','').strip().upper()
    db=gd(); r=rd(fo(db,f"SELECT cb FROM kc WHERE co={PH} AND cb IS NOT NULL",(cd,)))
    if r:
        a=rd(fo(db,f"SELECT wi FROM us WHERE un={PH}",(r["cb"],)))
        if a and a.get("wi"): db.close(); return jsonify({"s":True,"wi":a["wi"]})
    db.close(); return jsonify({"s":False,"m":"无客服信息"})

if __name__=='__main__':
    p=int(os.environ.get('PORT',9876))
    print(f"拼小豆 端口:{p} 密码:{ADMIN_PASSWORD}")
    app.run(host='0.0.0.0',port=p,debug=False)
