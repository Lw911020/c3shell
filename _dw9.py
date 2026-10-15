# -*- coding: utf-8 -*-
import urllib.request, json, time
B='http://127.0.0.1:3081'
def ex(cmd, t=180):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
print('=== ① 谁在占着那把锁（关键 ✓）===')
print(ex("fuser -v /dev/shm/dsh-drivewatch.lock 2>&1 | head -6; echo '--- 进程 ---'; ps -eo pid,etimes,args 2>/dev/null | grep '[d]rive_watch' | head -6 | sed 's/  */ /g'")[:900])
print()
print('=== ② 判断：占锁的进程是【我测试用的】还是【App 的】(看父进程 ✓)===')
print(ex("for p in $(pgrep -f 'drive_watch.py' | head -4); do echo \"pid=$p ppid=$(ps -o ppid= -p $p | tr -d ' ') etimes=$(ps -o etimes= -p $p | tr -d ' ') cmd=$(ps -o args= -p $p | cut -c1-60)\"; done")[:700])
print()
print('=== ③ App 的实时流现在是否连着（状态来源 ✓）===')
print(ex("ps -ef 2>/dev/null | grep -c '[l]ive_stream.py'")[:20].strip(), '个 live_stream')
print(ex("ps -ef 2>/dev/null | grep -c '[d]sh_remote'")[:20].strip(), '个 dsh_remote')

