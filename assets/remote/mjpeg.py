#!/usr/bin/env python3
import sys, os, time, struct, threading, socket, http.server
sys.path.insert(0, "/data/openpilot")
# MJPEG v5.2: SRC=ui (from /dev/shm/ui.rgb) / SRC=cam
#
# v5.1：seqlock 读帧（不睡 100ms 等半截帧）+ 每个客户端只发新帧 + Condition 立即通知 + TCP_NODELAY
# v5.2（2026-09-24 用户：「一开始没延迟，开久一点就有延迟了」）：
#   MJPEG 是**服务器推**：车机 WebView 解码只要比 C3 产出慢一点，积压就会一直涨
#   （实测 stat 里 frames-sent 差到 120 帧 ≈ 6 秒，ss 里 Send-Q 1.1MB ✗）
#   所以新增 **/frame.jpg 拉帧接口**：客户端每次只取"当前这一帧"，
#   解码慢就自动跳帧、延迟恒定不累积 ✓（页面默认走拉帧，失败自动退回 MJPEG）
import numpy as np
try:
    import cv2
except Exception:
    cv2 = None
    from PIL import Image

UIRGB = "/dev/shm/ui.rgb"


def to_bgr(rgb):
    if cv2 is not None:
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return np.ascontiguousarray(rgb[:, :, ::-1])


def fit_width(bgr, wid):
    if wid and bgr.shape[1] != wid:
        h = int(bgr.shape[0] * wid / bgr.shape[1])
        if cv2 is not None:
            return cv2.resize(bgr, (wid, h), interpolation=cv2.INTER_AREA)
        return np.asarray(Image.fromarray(bgr).resize((wid, h), Image.BILINEAR))
    return bgr


def encode_jpg(bgr, q):
    if cv2 is not None:
        ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
        return jpg.tobytes() if ok else None
    import io
    buf = io.BytesIO()
    Image.fromarray(bgr).save(buf, format="JPEG", quality=int(q))
    return buf.getvalue()


PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
FPS  = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
WID  = int(sys.argv[3]) if len(sys.argv) > 3 else 640
Q    = int(sys.argv[4]) if len(sys.argv) > 4 else 65
SRC  = sys.argv[5] if len(sys.argv) > 5 else "ui"

latest = {"jpg": None, "n": 0, "err": "", "ms": 0.0, "at": 0.0}
clients = {"n": 0}
sent = {"n": 0}
pulls = {"n": 0, "t": 0.0}
torn = {"n": 0}
cond = threading.Condition()
_fd = {"v": -1}


def ui_fd():
    if _fd["v"] < 0:
        try:
            _fd["v"] = os.open(UIRGB, os.O_RDONLY)
        except Exception:
            _fd["v"] = -1
    return _fd["v"]


def read_ui(last_seq, deadline):
    """seqlock：头→体→头 再确认；半截/正在写就立刻重读（不睡 100ms ✗）"""
    while time.time() < deadline:
        fd = ui_fd()
        if fd < 0:
            time.sleep(0.05); continue
        try:
            head = os.pread(fd, 16, 0)
        except Exception:
            _fd["v"] = -1; continue
        if len(head) < 16:
            time.sleep(0.002); continue
        magic, w, h, seq = struct.unpack("<IIII", head)
        if seq == last_seq:
            time.sleep(0.003); continue
        body = os.pread(fd, w * h * 3, 16)
        try:
            head2 = os.pread(fd, 16, 0)
        except Exception:
            head2 = b""
        if len(body) < w * h * 3 or head2 != head:
            torn["n"] += 1
            continue
        return w, h, seq, body
    return None


def grab_cam(cli, WID, Q):
    if cv2 is None: return None
    b = cli.recv()
    if b is None: return None
    W, H, S = int(b.width), int(b.height), int(b.stride)
    raw = np.frombuffer(bytes(b.data), dtype=np.uint8)
    Yp = raw[:S*H].reshape((H, S))
    UVp = raw[S*H:S*H + S*(H//2)].reshape((H//2, S//2, 2))
    step = max(1, round(W / float(WID)))
    Ys = Yp[::step, :W:step]; Us = UVp[::step, ::step, 0]; Vs = UVp[::step, ::step, 1]
    h2 = (Ys.shape[0]//2)*2; w2 = (Ys.shape[1]//2)*2
    Ys = Ys[:h2,:w2]; Us = Us[:h2//2,:w2//2]; Vs = Vs[:h2//2,:w2//2]
    nv12 = np.vstack((Ys, np.dstack((Us, Vs)).reshape(h2//2, w2)))
    return cv2.cvtColor(nv12, cv2.COLOR_YUV2BGR_NV12)


def active():
    """有 MJPEG 客户端，或最近 3 秒有人在拉 /frame.jpg → 才采集（没人看就别烧 CPU ✓）"""
    return clients["n"] > 0 or (time.time() - pulls["t"] < 3.0)


def capture():
    cli = None; last_seq = -1
    while True:
        try:
            if not active():
                time.sleep(0.3); cli = None; last_seq = -1; continue
            ta = time.time()
            if SRC == "ui":
                r = read_ui(last_seq, ta + 0.2)
                if r is None:
                    continue
                w, h, seq, body = r
                last_seq = seq
                try:
                    bgr = to_bgr(np.frombuffer(body, np.uint8).reshape((h, w, 3)))
                except Exception as e:
                    latest["err"] = "ui: " + str(e)[:60]; continue
            else:
                if cli is None:
                    from msgq.visionipc import VisionIpcClient, VisionStreamType
                    cli = VisionIpcClient("camerad", VisionStreamType.VISION_STREAM_ROAD, True)
                    if not cli.connect(True): cli = None; time.sleep(1); continue
                    t0 = time.time()
                    while not cli.is_connected and time.time()-t0 < 8: time.sleep(0.05)
                bgr = grab_cam(cli, WID, Q)
                if bgr is None: time.sleep(0.02); continue
            bgr = fit_width(bgr, WID)
            jpg = encode_jpg(bgr, Q)
            if jpg:
                with cond:
                    latest["jpg"] = jpg; latest["n"] += 1
                    latest["ms"] = (time.time()-ta)*1000.0
                    latest["at"] = time.time()
                    latest["err"] = ""
                    cond.notify_all()
                left = (1.0/FPS) - (time.time()-ta)
                if left > 0: time.sleep(left)
        except Exception as e:
            latest["err"] = str(e)[:100]; cli = None; time.sleep(0.4)


class H(http.server.BaseHTTPRequestHandler):
    # HTTP/1.1 + Content-Length = 连接可复用：拉帧路径每帧复用同一条 TCP（HTTP/1.0 会每帧新建，
    # 15 帧/秒 × 1 分钟就攒下几百个 TIME_WAIT，反而越开越卡 ✗）；MJPEG 那条显式 Connection: close ✓
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        p = self.path
        if p.startswith("/stat"):
            lag = latest["n"] - sent["n"]
            body = ("src=%s frames=%d ms=%.1f enc=%.1f sent=%d clients=%d pulls=%d lag=%d age=%.2f torn=%d err=%s" %
                    (SRC, latest["n"], latest["ms"], latest["ms"], sent["n"], clients["n"],
                     pulls["n"], lag, (time.time() - latest["at"]) if latest["at"] else -1.0, torn["n"], latest["err"])).encode()
            self.send_response(200); self.send_header("Content-Type","text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if p.startswith("/frame"):
            pulls["n"] += 1; pulls["t"] = time.time()
            # 第一帧可能要几十毫秒才产出（以前直接 503 → 页面一上来就报错 ✗）→ 先等最多 2 秒 ✓
            dl = time.time() + 2.0
            while latest["jpg"] is None and time.time() < dl:
                time.sleep(0.02)
            j = latest["jpg"]
            if not j:
                self.send_response(503); self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store"); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Access-Control-Allow-Origin", "*")   # ★ 页面用 fetch().blob() 拉帧，跨源必须给 ✓
            self.send_header("Cache-Control", "no-store, no-cache")
            self.send_header("Content-Length", str(len(j)))
            self.end_headers()
            try: self.wfile.write(j)
            except Exception: pass
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store, no-cache")
        self.send_header("Connection", "close")      # 无 Content-Length 的流：用关闭来界定结束 ✓
        self.end_headers()
        self.close_connection = True
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.connection.settimeout(8.0)
        except Exception: pass
        clients["n"] += 1
        mine = -1
        try:
            while True:
                with cond:
                    if latest["n"] == mine:
                        cond.wait(0.5)
                    n = latest["n"]; j = latest["jpg"]
                if j is None or n == mine:
                    continue
                self.wfile.write(b"--frame" + bytes([13,10]) + b"Content-Type: image/jpeg" + bytes([13,10]) +
                                 b"Content-Length: " + str(len(j)).encode() + bytes([13,10,13,10]) + j + bytes([13,10]))
                mine = n; sent["n"] += 1
        except Exception: pass
        finally: clients["n"] -= 1

    def log_message(self, *a): pass


threading.Thread(target=capture, daemon=True).start()
print("mjpeg v5.3 src=%s on %d fps %s wid %d q %d" % (SRC, PORT, FPS, WID, Q), flush=True)
http.server.ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
