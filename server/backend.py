#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c3shell 后台（单文件 / 只用标准库，Python 3.8+）
对应 APP 里 java/com/padagent/c3shell/Lic.java 的四个兄弟端点：
  POST {你填的端点}   激活/校验   {"code","device","version","app"} -> {"ok":true,"plan","expiresAt"}
  POST .../feedback   反馈       {"device","version","contact","text","logText","imageB64"} -> {"ok":true}
  POST .../appreciate 赞赏登记   {"device","version","amount","contact"} -> {"ok":true}
  POST .../heartbeat  心跳       {"device","feature","hostCount","mode"} -> {"ok":true}
  GET  .../stats      统计       -> {"ok":true,"online":N,"devices":N,"today":N,...}
  GET  /admin?token=  后台页     （卡密台账 / 反馈 / 赞赏 / 设备）

部署（阿里云）：
  python3 backend.py serve --port 8080 --db ./backend.db --data ./data --token <你的管理口令>
  nginx 反代：location / { proxy_pass http://127.0.0.1:8080; proxy_read_timeout 60s; client_max_body_size 16m; }
  注意：若站点前面有「访问验证」页面，需把 /verify /feedback /appreciate /heartbeat /stats 放行。

发卡（离线也支持：Card 由 APP 侧离线验签；这里是联网卡密）：
  python3 backend.py mint --plan 1y --days 365 --count 10
  python3 backend.py list
  python3 backend.py bind --code XXXX --device DDDD      # 手动解绑/换机
"""
import argparse, base64, json, os, random, sqlite3, string, sys, threading, time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

MAXBODY = 12 * 1024 * 1024
DB = "./backend.db"
DATA = "./data"
TOKEN = ""
ONLINE_WINDOW = 600


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.executescript("""
CREATE TABLE IF NOT EXISTS cards(code TEXT PRIMARY KEY, plan TEXT, expires_at TEXT, max_devices INTEGER DEFAULT 1, note TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS binds(code TEXT, device TEXT, first_seen TEXT, last_seen TEXT, version TEXT, PRIMARY KEY(code, device));
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, device TEXT, version TEXT, contact TEXT, text TEXT, log_path TEXT, img_path TEXT);
CREATE TABLE IF NOT EXISTS appreciate(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, device TEXT, version TEXT, amount TEXT, contact TEXT);
CREATE TABLE IF NOT EXISTS heartbeat(device TEXT PRIMARY KEY, feature TEXT, host_count INTEGER, mode TEXT, ts TEXT);
""")
    c.commit()
    c.close()


def mint(plan, days, count):
    out = []
    c = conn()
    for _ in range(count):
        code = "C3-" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12))
        exp = "" if days <= 0 else (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO cards(code,plan,expires_at,note,created) VALUES(?,?,?,?,?)", (code, plan, exp, "", now()))
        out.append({"code": code, "plan": plan, "expiresAt": exp})
    c.commit()
    c.close()
    return out


def verify(body):
    code = (body.get("code") or "").strip().upper()
    dev = (body.get("device") or "").strip()
    ver = (body.get("version") or "").strip()
    if len(code) < 6:
        return {"ok": False, "error": {"message": "卡密太短"}}
    if not dev:
        return {"ok": False, "error": {"message": "缺少设备标识"}}
    c = conn()
    row = c.execute("SELECT * FROM cards WHERE code=?", (code,)).fetchone()
    if row is None:
        c.close()
        return {"ok": False, "error": {"message": "卡密无效"}}
    exp = row["expires_at"] or ""
    if exp:
        try:
            if datetime.strptime(exp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                c.close()
                return {"ok": False, "error": {"message": "卡密已过期（" + exp + " UTC）"}}
        except Exception:
            pass
    binds = c.execute("SELECT device FROM binds WHERE code=?", (code,)).fetchall()
    devs = [b["device"] for b in binds]
    if dev not in devs and len(devs) >= (row["max_devices"] or 1):
        c.close()
        return {"ok": False, "error": {"message": "该卡密已绑定其它设备（可用后台解绑换机）"}}
    c.execute("INSERT INTO binds(code,device,first_seen,last_seen,version) VALUES(?,?,?,?,?) ON CONFLICT(code,device) DO UPDATE SET last_seen=?, version=?",
              (code, dev, now(), now(), ver, now(), ver))
    c.execute("INSERT INTO heartbeat(device,feature,host_count,mode,ts) VALUES(?,?,?,?,?) ON CONFLICT(device) DO UPDATE SET feature=?, host_count=?, mode=?, ts=?",
              (dev, "license", 0, body.get("app", ""), now(), "license", 0, body.get("app", ""), now()))
    c.commit()
    c.close()
    return {"ok": True, "plan": row["plan"] or "", "expiresAt": exp}


def save_feedback(body):
    dev = (body.get("device") or "unknown").strip()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch for ch in dev if ch.isalnum() or ch in "-_")[:32] or "dev"
    os.makedirs(os.path.join(DATA, "feedback"), exist_ok=True)
    logp = imgp = ""
    logtxt = body.get("logText") or ""
    if logtxt:
        logp = os.path.join(DATA, "feedback", ts + "-" + safe + ".log")
        open(logp, "w", encoding="utf-8", errors="replace").write(logtxt)
    img = body.get("imageB64") or ""
    if len(img) > 100:
        try:
            raw = base64.b64decode(img.split(",")[-1])
            imgp = os.path.join(DATA, "feedback", ts + "-" + safe + ".jpg")
            open(imgp, "wb").write(raw)
        except Exception:
            imgp = ""
    c = conn()
    c.execute("INSERT INTO feedback(ts,device,version,contact,text,log_path,img_path) VALUES(?,?,?,?,?,?,?)",
              (now(), dev, body.get("version", ""), body.get("contact", ""), body.get("text", "")[:4000], logp, imgp))
    c.execute("INSERT INTO heartbeat(device,feature,host_count,mode,ts) VALUES(?,?,?,?,?) ON CONFLICT(device) DO UPDATE SET feature=?, ts=?",
              (dev, "feedback", 0, "", now(), "feedback", now()))
    c.commit()
    c.close()
    return {"ok": True}


def save_appreciate(body):
    dev = (body.get("device") or "").strip()
    c = conn()
    c.execute("INSERT INTO appreciate(ts,device,version,amount,contact) VALUES(?,?,?,?,?)",
              (now(), dev, body.get("version", ""), body.get("amount", ""), body.get("contact", "")))
    c.commit()
    c.close()
    return {"ok": True}


def do_heartbeat(body):
    dev = (body.get("device") or "").strip()
    if not dev:
        return {"ok": False, "error": {"message": "缺少设备标识"}}
    c = conn()
    c.execute("INSERT INTO heartbeat(device,feature,host_count,mode,ts) VALUES(?,?,?,?,?) ON CONFLICT(device) DO UPDATE SET feature=?, host_count=?, mode=?, ts=?",
              (dev, body.get("feature", ""), int(body.get("hostCount") or 0), body.get("mode", ""), now(),
               body.get("feature", ""), int(body.get("hostCount") or 0), body.get("mode", ""), now()))
    c.commit()
    c.close()
    return {"ok": True}


def stats():
    c = conn()
    cut = (datetime.now(timezone.utc) - timedelta(seconds=ONLINE_WINDOW)).strftime("%Y-%m-%d %H:%M:%S")
    online = c.execute("SELECT COUNT(*) n FROM heartbeat WHERE ts>=?", (cut,)).fetchone()["n"]
    devices = c.execute("SELECT COUNT(DISTINCT device) n FROM binds").fetchone()["n"]
    cards = c.execute("SELECT COUNT(*) n FROM cards").fetchone()["n"]
    used = c.execute("SELECT COUNT(DISTINCT code) n FROM binds").fetchone()["n"]
    fb = c.execute("SELECT COUNT(*) n FROM feedback").fetchone()["n"]
    ap = c.execute("SELECT COUNT(*) n, COALESCE(SUM(CAST(amount AS REAL)),0) s FROM appreciate").fetchone()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    todayn = c.execute("SELECT COUNT(*) n FROM heartbeat WHERE ts LIKE ?", (today + "%",)).fetchone()["n"]
    c.close()
    return {"ok": True, "online": online, "devices": devices, "cards": cards, "cardsUsed": used,
            "feedback": fb, "appreciate": ap["n"], "appreciateAmount": round(ap["s"] or 0, 2),
            "today": todayn, "serverTime": now()}


def admin_html(q):
    tok = (q.get("token") or [""])[0]
    if TOKEN and tok != TOKEN:
        return ("<html><body style='font-family:sans-serif;padding:40px'>"
                "<h3>c3shell 后台</h3><p>需要口令：<code>/admin?token=你的口令</code></p></body></html>").encode()
    st = stats()
    c = conn()
    cards = c.execute("SELECT * FROM cards ORDER BY created DESC LIMIT 200").fetchall()
    binds = c.execute("SELECT * FROM binds ORDER BY last_seen DESC LIMIT 200").fetchall()
    fbs = c.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT 100").fetchall()
    aps = c.execute("SELECT * FROM appreciate ORDER BY id DESC LIMIT 100").fetchall()
    hb = c.execute("SELECT * FROM heartbeat ORDER BY ts DESC LIMIT 100").fetchall()
    c.close()

    def rows(rs, cols):
        h = "".join("<th>" + x + "</th>" for x in cols)
        b = "".join("<tr>" + "".join("<td>" + str(r[x] if x in r.keys() else "") + "</td>" for x in cols) + "</tr>" for r in rs)
        return "<table border=1 cellspacing=0 cellpadding=4><tr>" + h + "</tr>" + b + "</table>"

    out = ["<html><head><meta charset=utf-8><meta http-equiv=refresh content=60><title>c3shell 后台</title>",
           "<style>body{font-family:sans-serif;margin:24px}table{border-collapse:collapse;font-size:13px;margin:10px 0}h2{margin-top:24px}</style></head><body>",
           "<h1>c3shell 后台 <span style='font-size:14px;color:#666'>（每 60 秒自动刷新）</span></h1>",
           "<p>在线 %s ｜ 累计设备 %s ｜ 今日活跃 %s ｜ 卡密 %s（已用 %s）｜ 反馈 %s ｜ 赞赏 %s 笔 / ￥%s ｜ 服务器 %s</p>" % (
               st["online"], st["devices"], st["today"], st["cards"], st["cardsUsed"], st["feedback"], st["appreciate"], st["appreciateAmount"], st["serverTime"]),
           "<h2>设备心跳（最近 100）</h2>", rows(hb, ["device", "feature", "host_count", "mode", "ts"]),
           "<h2>卡密（最近 200）</h2>", rows(cards, ["code", "plan", "expires_at", "max_devices", "created"]),
           "<h2>绑定</h2>", rows(binds, ["code", "device", "first_seen", "last_seen", "version"]),
           "<h2>反馈（最近 100）</h2>", rows(fbs, ["id", "ts", "device", "version", "contact", "text", "log_path", "img_path"]),
           "<h2>赞赏</h2>", rows(aps, ["id", "ts", "device", "version", "amount", "contact"]),
           "</body></html>"]
    return "".join(out).encode()


class H(BaseHTTPRequestHandler):
    server_version = "c3shell-backend/1.0"

    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except Exception:
            pass

    def log_message(self, fmt, *a):
        sys.stderr.write("[%s] %s %s\n" % (now(), self.address_string(), fmt % a))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAXBODY:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8", "replace") or "{}")
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send(200, b"", "text/plain")

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        _seg = p.rsplit("/", 1)[-1]
        if _seg in ("verify", "activate", "feedback", "appreciate", "heartbeat", "stats", "admin", "health"):
            p = "/" + _seg
        q = parse_qs(u.query)
        if p == "/stats":
            return self._send(200, stats())
        if p == "/admin":
            return self._send(200, admin_html(q), "text/html; charset=utf-8")
        if p in ("/", "/health"):
            return self._send(200, {"ok": True, "service": "c3shell-backend", "time": now()})
        return self._send(404, {"ok": False, "error": {"message": "no such path: " + p}})

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        _seg = p.rsplit("/", 1)[-1]
        if _seg in ("verify", "activate", "feedback", "appreciate", "heartbeat", "stats", "admin", "health"):
            p = "/" + _seg
        b = self._body()
        try:
            if p in ("/", "/verify", "/activate"):
                r = verify(b)
            elif p == "/feedback":
                r = save_feedback(b)
            elif p == "/appreciate":
                r = save_appreciate(b)
            elif p == "/heartbeat":
                r = do_heartbeat(b)
            else:
                r = {"ok": False, "error": {"message": "no such path: " + p}}
        except Exception as e:
            r = {"ok": False, "error": {"message": "server error: " + str(e)[:120]}}
        self._send(200 if r.get("ok") else 400, r)


def serve(port, host):
    init_db()
    srv = ThreadingHTTPServer((host, port), H)
    print("c3shell backend on http://%s:%d  db=%s data=%s token=%s" % (host, port, DB, DATA, "set" if TOKEN else "none"))
    srv.serve_forever()


def main():
    global DB, DATA, TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve", "mint", "list", "bind", "stats"])
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--token", default=os.environ.get("C3_TOKEN", ""))
    ap.add_argument("--plan", default="1y")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--code", default="")
    ap.add_argument("--device", default="")
    a = ap.parse_args()
    DB, DATA, TOKEN = a.db, a.data, a.token
    os.makedirs(DATA, exist_ok=True)
    init_db()
    if a.cmd == "serve":
        serve(a.port, a.host)
    elif a.cmd == "mint":
        for x in mint(a.plan, a.days, a.count):
            print(json.dumps(x, ensure_ascii=False))
    elif a.cmd == "list":
        c = conn()
        for r in c.execute("SELECT code,plan,expires_at FROM cards ORDER BY created DESC LIMIT 200"):
            print(r["code"], r["plan"], r["expires_at"] or "(永久)")
        c.close()
    elif a.cmd == "bind":
        c = conn()
        c.execute("DELETE FROM binds WHERE code=? AND device=?", (a.code.upper(), a.device))
        c.commit()
        c.close()
        print("unbound", a.code, a.device)
    elif a.cmd == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
