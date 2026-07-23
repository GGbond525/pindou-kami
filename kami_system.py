#!/usr/bin/env python3
import flask, os, random, string, datetime, hashlib, sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
ADMIN_PASSWORD = "WzS18350168663."
PERMANENT = "2099-12-31 23:59:59"
DUR = {"1d":"天卡","7d":"周卡","perm":"永久"}
AQ = {"1d":10,"7d":50,"perm":999}

def gd():
    p = os.path.join(os.path.dirname(__file__), "kami.db")
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS kc (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
        ct TEXT DEFAULT 'm', dr TEXT DEFAULT 'perm', dd INTEGER DEFAULT 99999,
        ca TEXT, cb TEXT, ub TEXT, ua TEXT, st TEXT DEFAULT 'unused'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS us (
        id INTEGER PRIMARY KEY AUTOINCREMENT, un TEXT UNIQUE NOT NULL,
        pw TEXT NOT NULL, ca TEXT, kc TEXT, mt TEXT, aa TEXT, me TEXT,
        ia INTEGER DEFAULT 0, ak TEXT, wi TEXT, aq INTEGER DEFAULT 50
    )""")
    c.commit()
    return c

def gc(l=16): return ''.join(random.choices(string.ascii_uppercase+string.digits,k=l))
def rd(r): return dict(r) if r else None
def q(c,s,p=None): return c.execute(s,p or [])
def fo(c,s,p=None): r=c.execute(s,p or []); return r.fetchone()
def fa(c,s,p=None): return c.execute(s,p or []).fetchall()

@app.route('/')
def idx():
    return open(os.path.join(os.path.dirname(__file__),'kami_frontend.html'),encoding='utf-8').read()

@app.route('/api/register', methods=['POST'])
def reg():
    d=request.get_json(); u=d.get('username','').strip(); p=d.get('password','').strip()
    if not u or not p: return jsonify({"s":False,"m":"请填写完整"})
    if len(p)<6: return jsonify({"s":False,"m":"密码至少6位"})
    c=gd()
    if fo(c,"SELECT id FROM us WHERE un=?",(u,)): c.close(); return jsonify({"s":False,"m":"用户名已存在"})
    h=hashlib.sha256(p.encode()).hexdigest(); n=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    q(c,"INSERT INTO us (un,pw,ca) VALUES (?,?,?)",(u,h,n))
    c.commit(); c.close(); return jsonify({"s":True,"m":"注册成功"})

@app.route('/api/login', methods=['POST'])
def lgn():
    d=request.get_json(); u=d.get('username','').strip(); p=d.get('password','').strip()
    h=hashlib.sha256(p.encode()).hexdigest()
    c=gd(); us=rd(fo(c,"SELECT * FROM us WHERE un=? AND pw=?",(u,h))); c.close()
    if us: return jsonify({"s":True,"un":u,"kc":us.get("kc") or "","mt":us.get("mt") or "","ia":us.get("ia",0),"ak":us.get("ak") or ""})
    return jsonify({"s":False,"m":"用户名或密码错误"})

@app.route('/api/activate', methods=['POST'])
def act():
    d=request.get_json(); u=d.get('username',''); c=d.get('code','').strip().upper()
    db=gd(); us=rd(fo(db,"SELECT kc,me FROM us WHERE un=?",(u,)))
    if us and us.get("kc"):
        if us["kc"]==c: db.close(); return jsonify({"s":True,"m":"已激活"})
        if us.get("me"):
            try:
                if datetime.datetime.strptime(us["me"],'%Y-%m-%d %H:%M:%S')>datetime.datetime.now():
                    db.close(); return jsonify({"s":False,"m":"该账号已有有效卡密"})
            except: pass
    r=rd(fo(db,"SELECT * FROM kc WHERE code=? AND st='unused' AND ct LIKE 'm%'",(c,)))
    if not r:
        used=fo(db,"SELECT * FROM kc WHERE code=? AND st='used'",(c,))
        db.close(); return jsonify({"s":False,"m":"卡密已被使用" if used else "卡密无效"})
    n=datetime.datetime.now(); dd=r["dd"]; exp=(n+datetime.timedelta(days=int(dd))).strftime('%Y-%m-%d %H:%M:%S')
    ns=n.strftime('%Y-%m-%d %H:%M:%S')
    if dd>=99999: exp=PERMANENT
    q(db,"UPDATE kc SET st='used', ub=?, ua=? WHERE id=?",(u,ns,r["id"]))
    q(db,"UPDATE us SET kc=?, mt=?, aa=?, me=? WHERE un=?",(c,r["dr"],ns,exp,u))
    db.commit(); db.close()
    return jsonify({"s":True,"m":f"激活成功！有效期至{exp[:10]}"})

@app.route('/api/activate_agent', methods=['POST'])
def act_ag():
    d=request.get_json(); u=d.get('username',''); c=d.get('code','').strip().upper(); w=d.get('wechat_id','').strip()
    db=gd(); us=rd(fo(db,"SELECT ia,ak FROM us WHERE un=?",(u,)))
    if us and us.get("ia") and us.get("ak"): db.close(); return jsonify({"s":False,"m":"已绑定代理卡密"})
    r=rd(fo(db,"SELECT * FROM kc WHERE code=? AND st='unused' AND ct LIKE 'a%'",(c,)))
    if not r:
        used=fo(db,"SELECT * FROM kc WHERE code=? AND st='used'",(c,))
        db.close(); return jsonify({"s":False,"m":"代理卡密无效或已使用" if used else "代理卡密无效"})
    ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'); qa=AQ.get(r["dr"],50)
    q(db,"UPDATE kc SET st='used', ub=?, ua=? WHERE id=?",(u,ns,r["id"]))
    q(db,"UPDATE us SET ia=1, ak=?, wi=?, aq=? WHERE un=?",(c,w,qa,u))
    db.commit(); db.close(); return jsonify({"s":True,"m":"升级代理成功","aq":qa})

@app.route('/api/check', methods=['POST'])
def chk():
    u=request.get_json().get('username','')
    db=gd(); us=rd(fo(db,"SELECT * FROM us WHERE un=?",(u,))); db.close()
    if not us: return jsonify({"s":True,"act":False})
    ac=False; es=us.get("me")
    if us.get("kc") and es:
        if es==PERMANENT: ac=True
        else:
            try:
                if datetime.datetime.strptime(es,'%Y-%m-%d %H:%M:%S')>datetime.datetime.now(): ac=True
            except: pass
    return jsonify({"s":True,"act":ac,"mt":us.get("mt") or "","me":es or "","ia":bool(us.get("ia",0)),"wi":us.get("wi") or "","aq":us.get("aq",50)})

@app.route('/api/agent/generate', methods=['POST'])
def ag_gen():
    d=request.get_json(); u=d.get('username',''); n=min(d.get('count',1),20)
    db=gd(); us=rd(fo(db,"SELECT * FROM us WHERE un=? AND ia=1",(u,)))
    if not us: db.close(); return jsonify({"s":False,"m":"无权限"}),403
    ud=rd(fo(db,"SELECT COUNT(*) as c FROM kc WHERE cb=?",(u,))); uc=ud["c"] if ud else 0
    qa=us.get("aq",50); rm=qa-uc
    if n>rm: n=rm
    if n<=0: db.close(); return jsonify({"s":False,"m":f"剩余配额{max(0,rm)}张"})
    cs=[]; ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        code=gc(16)
        try:
            q(db,"INSERT INTO kc (code,ct,dr,dd,ca,cb,st) VALUES (?,'m','perm',99999,?,?,'unused')",(code,ns,u))
            cs.append(code)
        except: pass
    db.commit(); db.close(); return jsonify({"s":True,"c":len(cs),"cs":cs})

@app.route('/api/agent/info', methods=['POST'])
def ag_info():
    u=request.get_json().get('username','')
    db=gd(); us=rd(fo(db,"SELECT * FROM us WHERE un=? AND ia=1",(u,)))
    if not us: db.close(); return jsonify({"s":False}),403
    ud=rd(fo(db,"SELECT COUNT(*) as c FROM kc WHERE cb=?",(u,))); uc=ud["c"] if ud else 0
    qa=us.get("aq",50); db.close()
    return jsonify({"s":True,"wi":us.get("wi") or "","qa":qa,"ud":uc,"rm":qa-uc})

@app.route('/api/agent/list_codes', methods=['POST'])
def ag_ls():
    d=request.get_json(); u=d.get('username',''); t=d.get('t','all')
    wh="" if t=="all" else f"AND st='{t}'"
    db=gd(); rs=fa(db,f"SELECT code,ca,st,ua FROM kc WHERE ct LIKE 'm%' AND cb=? {wh} ORDER BY id DESC LIMIT 200",(u,))
    db.close(); return jsonify({"s":True,"cs":[dict(r) for r in rs]})

@app.route('/api/agent/set_wechat', methods=['POST'])
def ag_wx():
    d=request.get_json(); db=gd()
    q(db,"UPDATE us SET wi=? WHERE un=?",(d.get('wechat_id',''),d.get('username','')))
    db.commit(); db.close(); return jsonify({"s":True})

@app.route('/api/admin/login', methods=['POST'])
def ad_lg():
    return jsonify({"s":request.get_json().get('password','')==ADMIN_PASSWORD})

@app.route('/api/admin/gen', methods=['POST'])
def ad_gen():
    d=request.get_json()
    if d.get('pw')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    n=min(d.get('n',1),200); ct=d.get('ct','m_perm')
    p=ct.split('_'); dr=p[1] if len(p)>1 else "perm"; cl=12 if ct.startswith("a") else 16
    DD_MAP={"1d":1,"7d":7,"perm":99999}
    dd_val=DD_MAP.get(dr,99999)
    db=gd(); cs=[]; ns=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for _ in range(n):
        code=gc(cl)
        try:
            q(db,"INSERT INTO kc (code,ct,dr,dd,ca,st) VALUES (?,?,?,?,?,'unused')",(code,ct,dr,dd_val,ns))
            cs.append(code)
        except: pass
    db.commit(); db.close(); return jsonify({"s":True,"c":len(cs),"cs":cs,"ct":ct})

@app.route('/api/admin/list')
def ad_ls():
    if request.args.get('pw','')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    tb=request.args.get('t','unused'); tp=request.args.get('tp','all')
    db=gd(); wt="" if tp=="all" else f"AND ct LIKE '{tp}%'"
    rs=fa(db,f"SELECT * FROM kc WHERE st='{tb}' {wt} ORDER BY id DESC LIMIT 500")
    def sc(s): r=fo(db,s); return r["c"] if r else 0
    db.close()
    return jsonify({"s":True,"cs":[dict(r) for r in rs],"st":{
        "tl":sc("SELECT COUNT(*) as c FROM kc"),
        "ul":sc("SELECT COUNT(*) as c FROM kc WHERE st='unused'"),
        "sl":sc("SELECT COUNT(*) as c FROM kc WHERE st='used'"),
        "mc":sc("SELECT COUNT(*) as c FROM kc WHERE ct LIKE 'm%' AND st='unused'"),
        "ac":sc("SELECT COUNT(*) as c FROM kc WHERE ct LIKE 'a%' AND st='unused'")
    }})

@app.route('/api/admin/delete', methods=['POST'])
def ad_dl():
    d=request.get_json()
    if d.get('pw')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    db=gd(); q(db,"DELETE FROM kc WHERE id=?",(d['id'],)); db.commit(); db.close()
    return jsonify({"s":True})

@app.route('/api/admin/users')
def ad_us():
    if request.args.get('pw','')!=ADMIN_PASSWORD: return jsonify({"s":False}),403
    db=gd(); rs=fa(db,"SELECT un,ca,kc,mt,me,aa,ia,ak,wi,aq FROM us ORDER BY id DESC LIMIT 200")
    db.close(); return jsonify({"s":True,"us":[dict(r) for r in rs]})

@app.route('/api/get_agent_wechat', methods=['POST'])
def gwx():
    cd=request.get_json().get('code','').strip().upper()
    db=gd(); r=rd(fo(db,"SELECT cb FROM kc WHERE code=? AND cb IS NOT NULL",(cd,)))
    if r:
        a=rd(fo(db,"SELECT wi FROM us WHERE un=?",(r["cb"],)))
        if a and a.get("wi"): db.close(); return jsonify({"s":True,"wi":a["wi"]})
    db.close(); return jsonify({"s":False,"m":"无客服信息"})

if __name__=='__main__':
    p=int(os.environ.get('PORT',9876))
    print(f"Pindou Kami System - Port:{p}")
    app.run(host='0.0.0.0',port=p,debug=False)
