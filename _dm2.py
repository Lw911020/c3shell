# -*- coding: utf-8 -*-
import urllib.request, json, time
B='http://127.0.0.1:3081'
def ex(cmd, t=300):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
print('=== 后台化工具 ===')
print(ex('for c in setsid nohup start-stop-daemon; do p=$(command -v $c 2>/dev/null || echo none); echo "  $c -> $p"; done')[:400])
print()
print('=== setsid 常驻 ===')
print(ex("cd /data/openpilot && PYTHONPATH=/data/openpilot setsid /usr/local/venv/bin/python3 /data/openpilot/.dsh/mjpeg.py 8090 5 </dev/null >/tmp/mjpeg.log 2>&1 & echo STARTED")[:200])
time.sleep(7)
print(ex("pgrep -af mjpeg.py | head -2; echo '--- log ---'; tail -3 /tmp/mjpeg.log 2>/dev/null")[:500])
print()
print('出帧统计:', ex("curl -s --max-time 5 http://127.0.0.1:8090/stat; echo")[:250])
print('拉流首包:', ex("curl -s --max-time 5 http://127.0.0.1:8090/ 2>/dev/null | head -c 60000 | wc -c")[:150])

