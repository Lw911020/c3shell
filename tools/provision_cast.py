#!/usr/bin/env python3
"""provision_cast.py — 给任意 openpilot 系统（CP / SP2024 / SP2025 / 官方）一键装投屏钩子

在平板上跑（用连接器走 SSH，不需要 adb、不需要 root）：

    python3 tools/provision_cast.py verify                  # 只看状态，不改设备
    python3 tools/provision_cast.py install                 # 装钩子 → 重启 comma → 验证出帧
    python3 tools/provision_cast.py uninstall               # 还原 process_config.py → 重启 comma
    python3 tools/provision_cast.py install --host c3-lan    # 指定主机（默认 c3-lan）

原理
    openpilot 的 ui 进程（selfdrive/ui/ui，Qt5）负责画界面。我们把一个小 .so
    （device/uihook.c）用 LD_PRELOAD 挂上去，拦住 eglSwapBuffers /
    eglSwapBuffersWithDamageKHR|EXT，并接管 eglGetProcAddress（SP2025 的 Qt 就是
    用 GetProcAddress 取 swap 指针的 —— 不接管就一帧都抓不到）。
    抓到的帧写 /dev/shm/ui.rgb，由 mjpeg.py 转 JPEG 推流；开关是 /dev/shm/ui.cast.on
    （文件在 = 采集，删掉 = 零开销）。

为什么必须重启 comma
    manager 在启动时就把 process_config.py 读进内存了 —— 只杀 ui 进程没用，
    改完必须让 manager 重新读配置（systemctl restart comma）。

安全
    · 改 process_config.py 前一定备份成 process_config.py.dsh-bak
    · 改完先 ast.parse 校验，失败立刻还原
    · 已经是装好的状态就跳过（幂等）
    · uninstall 用备份还原；没有备份就报错不动手
"""
import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REMOTE = '/data/openpilot/.dsh'
PCONF = '/data/openpilot/system/manager/process_config.py'
UI_OLD = '["_ui_"]'
FILES = ['uihook.c', 'touchd.c', 'mjpeg.py']


def load_cfg():
    p = os.path.expanduser('~/.dsh/ssh-connector.json')
    cfg = json.load(open(p, encoding='utf-8'))
    return cfg['token'], cfg.get('defaultHostId', 'c3')


def call(token, host, cmd, timeout=240):
    body = json.dumps({'hostId': host, 'command': cmd}).encode()
    req = urllib.request.Request('http://127.0.0.1:3081/api/ssh/exec', data=body,
                                 headers={'content-type': 'application/json', 'x-dsh-ssh-token': token})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode('utf-8', 'replace'))
    r2 = d.get('result', d)
    return (r2.get('stdout') or '') + (r2.get('stderr') or '')


def push(token, host, local, remote):
    import base64
    data = open(local, 'rb').read()
    b64 = base64.b64encode(data).decode()
    out = call(token, host, "printf '%s' " + b64 + " | base64 -d > " + remote + " && wc -c < " + remote)
    return out.strip()


def read_src(name):
    local = os.path.join(REPO, 'device', name)
    if not os.path.isfile(local):
        sys.exit('缺少源文件: ' + local)
    return open(local, encoding='utf-8').read()


def status(token, host):
    out = call(token, host, r'''
NP=$(pgrep -x ui | head -1)
echo "ui_pid=$NP"
echo "preload=$(tr '\0' '\n' < /proc/$NP/environ 2>/dev/null | grep -c LD_PRELOAD)"
echo "maps=$(grep -c uihook /proc/$NP/maps 2>/dev/null)"
echo "so=$(test -f /data/openpilot/.dsh/uihook.so && echo yes || echo no)"
echo "touchd=$(test -f /data/openpilot/.dsh/touchd && echo yes || echo no)"
echo "mjpeg=$(test -f /data/openpilot/.dsh/mjpeg.py && echo yes || echo no)"
echo "injected=$(grep -c LD_PRELOAD /data/openpilot/system/manager/process_config.py)"
echo "bak=$(test -f /data/openpilot/system/manager/process_config.py.dsh-bak && echo yes || echo no)"
echo "rgb=$(test -f /dev/shm/ui.rgb && echo yes || echo no)"
echo "flag=$(test -f /dev/shm/ui.cast.on && echo yes || echo no)"
''')
    st = {}
    for line in out.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            st[k.strip()] = v.strip()
    return st


def show(st):
    ok = st.get('preload') == '1' and st.get('maps', '0') != '0'
    print('  当前状态: 钩子已注入=%s  已加载=%s  出帧文件=%s  采集开关=%s' %
          (st.get('injected'), st.get('maps'), st.get('rgb'), st.get('flag')))
    print('  资产: uihook.so=%s touchd=%s mjpeg.py=%s process_config 备份=%s' %
          (st.get('so'), st.get('touchd'), st.get('mjpeg'), st.get('bak')))
    print('  → 投屏%s可用' % ('' if ok else '**不**'))
    return ok


def cmd_verify(token, host):
    print('== verify（只读）==')
    show(status(token, host))


def cmd_install(token, host):
    print('== install ==')
    st = status(token, host)
    if st.get('injected') == '1' and st.get('maps', '0') != '0' and st.get('so') == 'yes':
        print('  已经是装好的状态 → 只做验证')
        verify_frames(token, host)
        return
    print('  1/5 推源码与脚本')
    for name in FILES:
        n = push(token, host, os.path.join(REPO, 'device', name), REMOTE + '/' + name)
        print('     %-10s %s 字节' % (name, n))
    print('  2/5 设备上编译')
    print('     ' + call(token, host,
          "cd " + REMOTE + " && gcc -shared -fPIC -O2 -o uihook.so uihook.c -ldl -lpthread 2>&1 | tail -2; "
          "gcc -O2 -o touchd touchd.c 2>&1 | tail -2; ls -l uihook.so touchd | awk '{print $5, $9}'").strip().replace(chr(10), ' | '))
    print('  3/5 备份 + 注入 process_config.py 的 ui 行')
    out = call(token, host, r'''
cd /data/openpilot/system/manager
[ -f process_config.py.dsh-bak ] || cp -n process_config.py process_config.py.dsh-bak
python3 - <<'PYEOF'
p = '/data/openpilot/system/manager/process_config.py'
s = open(p, encoding='utf-8').read()
if 'LD_PRELOAD' in s:
    print('SKIP 已注入')
else:
    old = '  NativeProcess("ui", "selfdrive/ui", ["./ui"], always_run'
    new = '  NativeProcess("ui", "selfdrive/ui", ["env", "LD_PRELOAD=/data/openpilot/.dsh/uihook.so", "./ui"], always_run'
    if s.count(old) != 1:
        print('FAIL 找不到 ui 行（本系统结构不同，需人工确认）'); raise SystemExit(1)
    s = s.replace(old, new)
    import ast; ast.parse(s)
    open(p, 'w', encoding='utf-8').write(s)
    print('OK 已注入')
PYEOF
''')
    print('     ' + out.strip().replace(chr(10), ' | '))
    if 'OK' not in out and 'SKIP' not in out:
        sys.exit('注入失败，设备未改动')
    print('  4/5 重启 comma（manager 重新读配置）')
    call(token, host, "nohup sh -c 'sleep 1; sudo -n systemctl restart comma' >/dev/null 2>&1 & echo sent")
    time.sleep(35)
    print('  5/5 验证出帧')
    verify_frames(token, host)


def verify_frames(token, host):
    out = call(token, host, r'''
for i in 1 2 3 4 5 6; do NP=$(pgrep -x ui | head -1); [ -n "$NP" ] && break; sleep 5; done
echo "ui_pid=$NP preload=$(tr '\0' '\n' < /proc/$NP/environ 2>/dev/null | grep -c LD_PRELOAD) maps=$(grep -c uihook /proc/$NP/maps 2>/dev/null)"
touch /dev/shm/ui.cast.on; sleep 5
if [ -f /dev/shm/ui.rgb ]; then echo "帧: $(ls -l /dev/shm/ui.rgb | awk '{print $5}') 字节 头部 $(head -c 16 /dev/shm/ui.rgb | od -An -tu4 | tr -s ' ')"; else echo '帧: 无（看 /dev/shm/uihook.log 判断 Qt 走哪个入口）'; fi
cat /dev/shm/uihook.log 2>/dev/null | head -3
''')
    print(out.strip())
    print('\n  回退：python3 tools/provision_cast.py uninstall')


def cmd_uninstall(token, host):
    print('== uninstall ==')
    out = call(token, host, r'''
cd /data/openpilot/system/manager
if [ ! -f process_config.py.dsh-bak ]; then echo 'FAIL 没有 .dsh-bak 备份，拒绝改动'; exit 1; fi
cp process_config.py.dsh-bak process_config.py
rm -f /dev/shm/ui.cast.on
echo 'OK 已还原 process_config.py，钩子开关已删（.so 留着不影响：没注入就不加载）'
''')
    print('  ' + out.strip().replace(chr(10), ' | '))
    if 'OK' not in out:
        sys.exit('还原失败')
    print('  重启 comma')
    call(token, host, "nohup sh -c 'sleep 1; sudo -n systemctl restart comma' >/dev/null 2>&1 & echo sent")
    time.sleep(30)
    print('  完成后状态：')
    show(status(token, host))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['install', 'uninstall', 'verify'])
    ap.add_argument('--host', default=None)
    a = ap.parse_args()
    token, dhost = load_cfg()
    host = a.host or dhost
    print('主机: %s' % host)
    {'install': cmd_install, 'uninstall': cmd_uninstall, 'verify': cmd_verify}[a.action](token, host)


if __name__ == '__main__':
    main()
