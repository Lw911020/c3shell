# -*- coding: utf-8 -*-
import urllib.request, json, time
B='http://127.0.0.1:3081'
def ex(cmd, t=180):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
print('=== ① 占锁的是谁（父进程判断 ✓）===')
print(ex("for p in $(pgrep -f 'drive_watch.py'); do echo \"pid=$p ppid=$(ps -o ppid= -p $p 2>/dev/null | tr -d ' ') 已运行=$(ps -o etimes= -p $p 2>/dev/null | tr -d ' ')s  cmd=$(ps -o args= -p $p 2>/dev/null | cut -c1-52)\"; done | head -8")[:900])
print()
print('=== ② 全部清掉（把锁释放 ✓）===')
print(ex("pkill -9 -f 'drive_watch.py'; sleep 2; echo 剩余=$(pgrep -fc 'drive_watch.py' || echo 0)")[:100].strip())
print()
print('=== ③ 触发 App 的实时流（让它自己拉起一个 ✓）===')
try:
    r=urllib.request.Request(B+'/api/live/start?token=embedded', data=json.dumps({'hostId':'c3'}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    print('  /live/start:', urllib.request.urlopen(r, timeout=60).read().decode()[:150])
except Exception as e:
    print('  live/start 失败:', str(e)[:90])
time.sleep(8)
print()
print('=== ④ 现在活着几个？（应 = App 拉起的 1 个 ✓）===')
print(ex("pgrep -fc 'drive_watch.py' || echo 0")[:20].strip())
print(ex("ps -eo pid,ppid,etimes,args 2>/dev/null | grep '[d]rive_watch' | head -4 | sed 's/  */ /g'")[:500])
print()
print('=== ⑤ 它有没有真的在输出（语音/状态的来源 ✓）===')
print(ex("ls -la /dev/shm/ | grep -iE 'live|drive' | head -5; head -c 300 /dev/shm/dsh-live* 2>/dev/null")[:400])

