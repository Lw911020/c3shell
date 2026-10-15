# -*- coding: utf-8 -*-
import urllib.request, json
B='http://127.0.0.1:3081'
def ex(cmd, t=300):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
# 用 heredoc 直接在设备上写（内容里没有 PYEOF ✓ 引号安全 ✓）
cmd = "mkdir -p /data/openpilot/.dsh && cat > /data/openpilot/.dsh/mjpeg.py <<'PYEOF'\n" + "#!/usr/bin/env python3
# MJPEG 投屏服务：从 openpilot roadCameraState 取帧 -> JPEG -> HTTP MJPEG（不改 openpilot ✓）
import os, sys, time, threading, http.server
import numpy as np, cv2
import cereal.messaging as messaging
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
FPS  = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
latest = {"jpg": None, "n": 0, "err": ""}
def capture():
    sm = messaging.SubMaster(["roadCameraState"])
    while True:
        try:
            sm.update(200)
            if sm.updated["roadCameraState"]:
                st = sm["roadCameraState"]
                W, H = int(st.width), int(st.height)
                yuv = np.frombuffer(st.image, dtype=np.uint8).reshape((H*3//2, W))
                bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_NV12)
                ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    latest["jpg"] = jpg.tobytes()
                    latest["n"] += 1
        except Exception as e:
            latest["err"] = str(e)[:120]
        time.sleep(1.0/FPS)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/stat"):
            body = ("frames=%d err=%s" % (latest["n"], latest["err"])).encode()
            self.send_response(200); self.send_header("Content-Type","text/plain"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                j = latest["jpg"]
                if j:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(j)).encode() + b"\r\n\r\n" + j + b"\r\n")
                time.sleep(1.0/FPS)
        except Exception:
            pass
    def log_message(self, *a): pass
threading.Thread(target=capture, daemon=True).start()
print("mjpeg on", PORT, flush=True)
http.server.ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()" + "\nPYEOF\nwc -c /data/openpilot/.dsh/mjpeg.py\npython3 -c \"import ast;ast.parse(open('/data/openpilot/.dsh/mjpeg.py').read());print('语法 OK')\""
print('写脚本:', ex(cmd)[:300])
print()
print('=== 启动服务（后台 ✓ 用设备自带 python ✓）===')
print(ex("pkill -f dsh/mjpeg.py 2>/dev/null; cd /data/openpilot && PYTHONPATH=/data/openpilot nohup /usr/local/venv/bin/python3 /data/openpilot/.dsh/mjpeg.py 8090 5 > /tmp/mjpeg.log 2>&1 & sleep 3; cat /tmp/mjpeg.log | tail -3")[:400])
print()
print('=== 探测帧数（等 6 秒看它有没有在出帧 ✓）===')
print(ex("sleep 6; curl -s --max-time 5 http://127.0.0.1:8090/stat 2>/dev/null; echo")[:300])
print()
print('=== 单个 JPEG 帧（看大小 ✓）===')
print(ex("curl -s --max-time 4 http://127.0.0.1:8090/ 2>/dev/null | head -c 2000 > /tmp/f.bin; ls -la /tmp/f.bin | awk '{print \"  首包字节:\", $5}'")[:300])

