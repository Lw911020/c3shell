#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
c3shell 使用统计后端（零依赖，仅 Python3 标准库）
用法：  python3 stats-server.py [端口，默认 8099]
接口：  POST /beat     {"id":"设备ID","ver":"1.80","os":"Android 13","ts":1690000000}   ← APP 心跳
        GET  /stats    返回 JSON：{total, online, online10m, devices:[...]}
        GET  /         网页看板（总用户数 / 在线数 / 最近活跃列表）
数据：  ./stats.json（自动创建）
"""
import json, os, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")
ONLINE_MIN = 5          # 5 分钟内有心跳算在线

def load():
    try:
        with open(DB, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {}

def save(d):
    tmp = DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DB)

def summary(d):
    now = int(time.time())
    online = [k for k, v in d.items() if now - v.get("ts", 0) <= ONLINE_MIN * 60]
    online10 = [k for k, v in d.items() if now - v.get("ts", 0) <= 600]
    today = [k for k, v in d.items() if now - v.get("ts", 0) <= 86400]
    return {"total": len(d), "online": len(online), "online10m": len(online10),
            "active24h": len(today), "now": now}

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        if self.path.startswith("/beat"):
            try: d = json.loads(raw.decode("utf-8", "replace"))
            except Exception: d = {}
            did = str(d.get("id") or "unknown")
            db = load()
            rec = db.get(did, {})
            rec.update({"ts": int(d.get("ts") or time.time()), "ver": d.get("ver", ""),
                        "os": d.get("os", ""), "first": rec.get("first") or int(time.time()),
                        "beats": int(rec.get("beats", 0)) + 1,
                        "ip": self.client_address[0]})
            db[did] = rec
            save(db)
            self._send(200, json.dumps({"ok": True, **summary(db)}, ensure_ascii=False))
            return
        self._send(404, '{"ok":false}')

    def do_GET(self):
        if self.path.startswith("/stats"):
            db = load()
            s = summary(db)
            devs = sorted(db.items(), key=lambda kv: -kv[1].get("ts", 0))[:50]
            s["devices"] = [{"id": k, "ver": v.get("ver"), "os": v.get("os"),
                             "last": v.get("ts"), "beats": v.get("beats"),
                             "agoSec": int(time.time()) - v.get("ts", 0)} for k, v in devs]
            self._send(200, json.dumps(s, ensure_ascii=False, indent=1))
            return
        if self.path in ("/", "/index.html"):
            db = load(); s = summary(db)
            rows = "".join(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                    k[:10], v.get("ver", ""), v.get("os", ""), v.get("beats", 0),
                    "%d 秒前" % (int(time.time()) - v.get("ts", 0)))
                for k, v in sorted(db.items(), key=lambda kv: -kv[1].get("ts", 0))[:100])
            self._send(200, """<!doctype html><meta charset=utf-8>
<title>c3shell 使用统计</title>
<style>body{font:14px/1.6 system-ui;background:#0f1115;color:#e6edf3;padding:20px}
b{font-size:26px;color:#4b8cf7}table{border-collapse:collapse;margin-top:14px;width:100%%}
td,th{border-bottom:1px solid #2a3140;padding:6px 8px;text-align:left;font-size:12.5px}
.card{display:inline-block;background:#161a21;border:1px solid #2a3140;border-radius:12px;padding:12px 18px;margin-right:10px}</style>
<h2>c3shell 使用统计</h2>
<div class=card>总设备数<br><b>%d</b></div>
<div class=card>在线（5分钟）<br><b>%d</b></div>
<div class=card>10分钟内<br><b>%d</b></div>
<div class=card>24小时活跃<br><b>%d</b></div>
<table><tr><th>设备</th><th>版本</th><th>系统</th><th>心跳次数</th><th>最近</th></tr>%s</table>
""" % (s["total"], s["online"], s["online10m"], s["active24h"], rows), "text/html; charset=utf-8")
            return
        self._send(404, '{"ok":false}')

    def log_message(self, fmt, *a): pass

if __name__ == "__main__":
    print("统计后端已启动: http://0.0.0.0:%d/  （APP 上报地址填 http://<本机IP>:%d/beat）" % (PORT, PORT))
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
