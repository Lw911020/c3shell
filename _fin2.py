# -*- coding: utf-8 -*-
import urllib.request, json, time, socket
B='http://127.0.0.1:3081'
def api(p, t=90):
    return json.loads(urllib.request.urlopen(B+p+'?token=embedded', timeout=t).read().decode())
print('状态:', str(api('/api/cast/status'))[:240])
CR, LF = chr(13), chr(10)
JPEG_MAGIC = bytes([255, 216])
BOUNDARY = bytes([45, 45, 102, 114, 97, 109, 101])   # --frame
try:
    s = socket.create_connection(('192.168.0.66', 8090), 6)
    s.sendall(('GET / HTTP/1.0' + CR + LF + 'Host: x' + CR + LF + CR + LF).encode())
    time.sleep(3)
    d = s.recv(50000)
    print('MJPEG: %d 字节 · boundary=%s · JPEG=%s' % (len(d), BOUNDARY in d, JPEG_MAGIC in d))
    s.close()
except Exception as e:
    print('拉流失败:', e)
print()
print('=== 保存一帧到本地看看（验证真实画面 ✓）===')
try:
    s = socket.create_connection(('192.168.0.66', 8090), 6)
    s.sendall(('GET / HTTP/1.0' + CR + LF + 'Host: x' + CR + LF + CR + LF).encode())
    buf = b''
    t0 = time.time()
    while time.time() - t0 < 6 and len(buf) < 300000:
        try:
            c = s.recv(65536)
        except Exception:
            break
        if not c: break
        buf += c
    s.close()
    i = buf.find(JPEG_MAGIC)
    j = buf.find(bytes([255, 217]), i + 2)
    if i >= 0 and j > i:
        open('/storage/emulated/0/openpilot/c3shell/_attic/live.jpg', 'wb').write(buf[i:j+2])
        print('  已存一帧:', j + 2 - i, '字节')
    else:
        print('  没解析出完整帧')
except Exception as e:
    print('  失败:', e)

