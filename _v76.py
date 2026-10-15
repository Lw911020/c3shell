# -*- coding: utf-8 -*-
import urllib.request, json, time
B='http://127.0.0.1:3081'
def ex(cmd, t=180):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
def api(p, payload=None, t=120):
    if payload is None: return json.loads(urllib.request.urlopen(B+p+'?token=embedded',timeout=t).read().decode())
    r=urllib.request.Request(B+p+'?token=embedded', data=json.dumps(payload).encode(), headers={'content-type':'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(r,timeout=t).read().decode())
print('=== ① 触发 App 的实时通道（会重新上传脚本 ✓）===')
try:
    print('  /live/start:', str(api('/api/live/start', {'hostId':'c3'}))[:140])
except Exception as e:
    print('  ', str(e)[:120])
time.sleep(6)
print()
print('=== ② 设备上的脚本现在含锁了吗（关键 ✓）===')
print('  锁标记数:', ex("grep -c 'dsh-drivewatch.lock' /data/openpilot/.dsh/drive_watch.py")[:20].strip(), '(1 = ✓ 新资产已上传)')
print(ex("sed -n '10,18p' /data/openpilot/.dsh/drive_watch.py")[:400])
print()
print('=== ③ 连起 4 个 → 只应活 1 个（验证锁生效 ✓）===')
print('  ', ex("cd /data/openpilot && for i in 1 2 3 4; do PYTHONPATH=/data/openpilot nohup /usr/local/venv/bin/python3 -u /data/openpilot/.dsh/drive_watch.py >/dev/null 2>&1 & done; sleep 6; echo 行数=$(ps -ef 2>/dev/null | grep -c '[d]rive_watch.py')")[:160].strip())
print()
print('=== ④ 再等 20 秒（不应增长 ✓）===')
time.sleep(20)
print('  ', ex("echo 行数=$(ps -ef 2>/dev/null | grep -c '[d]rive_watch.py'); cat /proc/loadavg")[:120].strip())
print()
print('=== ⑤ 收尾：关采集 + 停投屏服务 ===')
print('  ', ex("rm -f /dev/shm/ui.cast.on; ps -ef 2>/dev/null | grep '[m]jpeg.py' | awk '{print $2}' | while read p; do kill -9 $p 2>/dev/null; done; sleep 1; echo 8090=$(ss -ltn 2>/dev/null | grep -c 8090) 开关=$(ls /dev/shm/ui.cast.on 2>/dev/null || echo off)")[:120].strip())
print('  负载:', ex('cat /proc/loadavg')[:40].strip())

