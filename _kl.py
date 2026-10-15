# -*- coding: utf-8 -*-
import urllib.request, json, time, socket
B='http://127.0.0.1:3081'
def ex(cmd, t=200):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
def api(p, t=120):
    return json.loads(urllib.request.urlopen(B+p+'?token=embedded', timeout=t).read().decode())
print('=== 谁占着 8090 ===')
print(ex("ss -ltnp 2>/dev/null | grep 8090 || fuser -n tcp 8090 2>&1 | head -2")[:300])
print()
print('=== 杀掉占用者（按端口找 PID ✓ 命令行里只有数字 ✓ 无自匹配风险）===')
print(ex("P=$(ss -ltnp 2>/dev/null | grep 8090 | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); echo holder=$P; [ -n \\"$P\\" ] && kill -9 $P 2>/dev/null; sleep 2; ss -ltn 2>/dev/null | grep 8090 || echo '端口已释放 ✓'")[:400])
print()
print('=== 重启服务 ===')
print('start:', str(api('/api/cast/start'))[:150])
time.sleep(9)
print('状态:', str(api('/api/cast/status'))[:300])
time.sleep(8)
print('再查:', str(api('/api/cast/status'))[:300])
print()
print('=== 跨网拉流 ===')
CR, LF = chr(13), chr(10)
try:
    s = socket.create_connection(('192.168.0.66', 8090), 6)
    s.sendall(('GET / HTTP/1.0' + CR + LF + 'Host: x' + CR + LF + CR + LF).encode())
    time.sleep(4)
    d = s.recv(60000)
    print('  %d 字节 · boundary=%s · JPEG头=%s' % (len(d), b'--frame' in d, b'\xff\xd8' in d))
    s.close()
except Exception as e:
    print('  失败:', e)

