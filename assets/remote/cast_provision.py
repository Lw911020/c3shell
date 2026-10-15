#!/usr/bin/env python3
"""cast_provision.py — 在**设备上**一键装/卸/查投屏钩子（由 APP 通过 SSH 推过来执行）

为什么需要它：投屏是把一个小 .so 用 LD_PRELOAD 挂到 openpilot 的 ui 进程上（改 process_config.py），
不同系统（CP / SP2025 / 老 SP 0.9.8）这一步的做法一样，但每台设备都必须装一次。
装在 APP 里 → 用户点一下就行，不用懂这些。

幂等：重复执行安全（已装则跳过注入）。
用法：python3 cast_provision.py install|uninstall|verify
输出：最后一行 JSON（APP 直接解析显示）。
"""
import glob
import json
import os
import subprocess
import sys
import time

DSH = '/data/openpilot/.dsh'
PCONF = '/data/openpilot/system/manager/process_config.py'
BAK = PCONF + '.dsh-bak'
HOOK = DSH + '/uihook.so'
FLAG = '/dev/shm/ui.cast.on'
RGB = '/dev/shm/ui.rgb'


def sh(cmd, timeout=60):
    try:
        p = subprocess.run(['sh', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return -1, str(e)


def find_python():
    """openpilot 自己的解释器（要能 import capnp）——各镜像不同，逐个试。"""
    cands = []
    try:
        rc, out = sh('for p in $(pgrep -f manager.py | head -3); do tr "\\0" "\\n" < /proc/$p/cmdline | head -1; done')
        cands += [l for l in out.split() if 'python' in l]
    except Exception:
        pass
    cands += ['/usr/local/venv/bin/python3', '/data/openpilot/.venv/bin/python3']
    cands += sorted(glob.glob('/usr/local/pyenv/versions/*/bin/python3*'), reverse=True)
    for c in cands:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            try:
                subprocess.check_call([c, '-c', 'import capnp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                return c
            except Exception:
                continue
    return None


def ui_state():
    rc, pid = sh('pgrep -x ui | head -1')
    pid = pid.strip()
    if not pid:
        return {'uiProcess': False, 'loaded': False, 'preload': False, 'frames': False}
    rc, pre = sh('grep -c LD_PRELOAD /proc/%s/environ' % pid)
    rc, maps = sh('grep -c uihook /proc/%s/maps' % pid)
    seq = ''
    try:
        with open(RGB, 'rb') as f:
            import struct
            d = f.read(16)
            if len(d) == 16:
                magic, w, h, s = struct.unpack('<IIII', d)
                seq = '%dx%d#%d' % (w, h, s)
    except Exception:
        pass
    return {'uiProcess': True, 'pid': pid, 'preload': pre.strip() != '0', 'loaded': maps.strip() not in ('', '0'),
            'frames': bool(seq), 'frame': seq}


def do_install():
    steps = []
    # 1) 编译（源码与 mjpeg.py 由 APP 一起推过来）
    have = [f for f in ('uihook.c', 'touchd.c') if os.path.isfile(DSH + '/' + f)]
    if len(have) < 2:
        return {'ok': False, 'error': '缺少源码 %s（APP 应先推送）' % have, 'steps': steps}
    rc, out = sh('cd %s && gcc -shared -fPIC -O2 -o uihook.so uihook.c -ldl -lpthread && gcc -O2 -o touchd touchd.c' % DSH, timeout=180)
    steps.append('编译 uihook.so/touchd: rc=%d' % rc)
    if rc != 0 or not os.path.isfile(HOOK):
        return {'ok': False, 'error': '编译失败：' + out[-400:], 'steps': steps}

    # 2) 注入（幂等）
    try:
        src = open(PCONF, encoding='utf-8').read()
    except Exception as e:
        return {'ok': False, 'error': '读不到 process_config.py: %s' % e, 'steps': steps}
    if 'LD_PRELOAD' in src:
        steps.append('注入: 已存在，跳过')
        st0 = ui_state()
        if st0.get('loaded'):                       # 已经装好且加载了 → 不折腾设备
            st0['ok'] = True
            st0['steps'] = steps + ['钩子已在运行，无需重启']
            return st0
    else:
        if not os.path.isfile(BAK):
            sh('cp -n %s %s' % (PCONF, BAK))
        old = '  NativeProcess("ui", "selfdrive/ui", ["./ui"], always_run'
        new = '  NativeProcess("ui", "selfdrive/ui", ["env", "LD_PRELOAD=%s", "./ui"], always_run' % HOOK
        if src.count(old) != 1:
            return {'ok': False, 'error': '找不到 ui 行（本系统结构不同，需人工看）', 'steps': steps}
        src = src.replace(old, new, 1)
        import ast
        ast.parse(src)                     # 写完先自检，坏了立刻回退
        open(PCONF, 'w', encoding='utf-8').write(src)
        steps.append('注入: OK（原文件已备份为 %s）' % os.path.basename(BAK))

    # 3) 重启 manager（后台跑，避免自己的 SSH 会话被切断）
    sh("nohup sh -c 'sleep 1; sudo -n systemctl restart comma' >/dev/null 2>&1 & echo sent")
    steps.append('重启 comma: 已下发')
    time.sleep(30)

    # 4) 验证出帧
    sh('touch ' + FLAG)
    st = ui_state()
    for _ in range(6):
        if st.get('frames'):
            break
        time.sleep(5)
        st = ui_state()
    st['ok'] = bool(st.get('loaded'))
    st['steps'] = steps
    return st


def do_uninstall():
    steps = []
    if not os.path.isfile(BAK):
        return {'ok': False, 'error': '没有 .dsh-bak 备份，拒绝改动', 'steps': steps}
    sh('cp %s %s' % (BAK, PCONF))
    sh('rm -f ' + FLAG)
    steps.append('已还原 process_config.py，并清掉采集开关')
    sh("nohup sh -c 'sleep 1; sudo -n systemctl restart comma' >/dev/null 2>&1 & echo sent")
    steps.append('重启 comma: 已下发')
    time.sleep(30)
    st = ui_state()
    st['ok'] = True
    st['steps'] = steps
    return st


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if action == 'install':
        r = do_install()
    elif action == 'uninstall':
        r = do_uninstall()
    else:
        r = ui_state()
        r['ok'] = True
    r['action'] = action
    r['python'] = find_python()
    print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
