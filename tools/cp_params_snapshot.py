#!/usr/bin/env python3
"""cp_params_snapshot.py — CP/SP 参数快照与对比（换版本前后各跑一次，一眼看出改了什么）

为什么要它：换系统/换适配版时，参数表会变（新增、改名、丢掉、默认值变），
肉眼比不出来；备一份快照再 diff，就能精确知道「APP 要不要跟着改、备注要不要补」。

用法（在平板上跑，自动走 APP 的接口，不需要 adb）：
    python3 tools/cp_params_snapshot.py snap            # 采一份快照存到 _attic/cp-baseline-<时间>/
    python3 tools/cp_params_snapshot.py diff            # 和上一份快照对比（自动找最近两份）
    python3 tools/cp_params_snapshot.py diff <旧目录> <新目录>

输出：新增键 / 消失键 / 值有变化的键，以及「新键里有多少条词库还没有备注」。
"""
import glob
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ATTIC = os.path.join(REPO, '_attic')
PORTFILE = os.path.join(ATTIC, 'app-port.txt')
NOTES = os.path.join(REPO, 'assets/remote/param-notes-zh.json')


def app_port():
    try:
        p = open(PORTFILE, encoding='utf-8').read().strip()
        if p:
            return p
    except Exception:
        pass
    # 退而求其次：从 adb logcat 里捞（APP 每次启动会打印）
    try:
        import subprocess
        out = subprocess.run(['sh', '-c',
            "adb -s 127.0.0.1:42073 logcat -d -s C3ShellWeb 2>/dev/null | grep -o 'embedded server on 127.0.0.1:[0-9]*' | tail -1"],
            stdout=subprocess.PIPE, timeout=20).stdout.decode('utf-8', 'replace')
        m = re.search(r':(\d+)$', out.strip())
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def app(path, body=None, timeout=200):
    port = app_port()
    if not port:
        sys.exit('找不到 APP 端口（先打开 APP，或把端口写进 _attic/app-port.txt）')
    b = json.dumps(body or {}).encode()
    req = urllib.request.Request('http://127.0.0.1:%s%s' % (port, path), data=b,
                                 headers={'content-type': 'application/json', 'x-dsh-ssh-token': 'embedded'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def collect():
    e = app('/api/ssh/env', {})
    env = (e.get('result') or e) or {}
    d = app('/api/ssh/params/all?force=1', {})
    rr = (d.get('result') or d)
    if isinstance(rr, str):
        rr = json.loads(rr)
    return env, rr


def snap():
    env, rr = collect()
    ts = time.strftime('%Y%m%d-%H%M%S')
    out = os.path.join(ATTIC, 'cp-baseline-' + ts)
    os.makedirs(out, exist_ok=True)
    json.dump(env, open(out + '/env.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(rr, open(out + '/params-full.json', 'w', encoding='utf-8'), ensure_ascii=False)
    reg = rr.get('registry') or []
    vals = rr.get('values') or {}
    keys = sorted(set([x.get('name') for x in reg]) | set(vals.keys()))
    open(out + '/keys.txt', 'w', encoding='utf-8').write(chr(10).join(keys))
    with open(out + '/values.txt', 'w', encoding='utf-8') as f:
        for k in sorted(vals.keys()):
            f.write('%s=%s' % (k, vals[k]))
            f.write(chr(10))
    print('快照: %s' % out)
    print('  版本 %s · fork %s · 注册表 %d · 运行时键 %d · 有值 %d'
          % ((env.get('version') or {}).get('version'), env.get('fork'),
             len(reg), len(keys), len([v for v in vals.values() if v not in (None, '')])))
    return out


def load(dirpath):
    keys = set(l.strip() for l in open(dirpath + '/keys.txt', encoding='utf-8') if l.strip())
    vals = {}
    for line in open(dirpath + '/values.txt', encoding='utf-8'):
        if '=' in line:
            k, v = line.rstrip(chr(10)).split('=', 1)
            vals[k] = v
    return keys, vals


def diff(old, new):
    ko, vo = load(old)
    kn, vn = load(new)
    added, gone = sorted(kn - ko), sorted(ko - kn)
    changed = sorted([k for k in (kn & ko) if vo.get(k) != vn.get(k)])
    notes = {}
    try:
        notes = json.load(open(NOTES, encoding='utf-8'))
    except Exception:
        pass
    noNote = [k for k in added if k not in notes]
    print('对比 %s → %s' % (os.path.basename(old), os.path.basename(new)))
    print('  键: %d → %d' % (len(ko), len(kn)))
    print('  新增 %d: %s' % (len(added), added[:40]))
    print('  消失 %d: %s' % (len(gone), gone[:40]))
    print('  值变化 %d: %s' % (len(changed), changed[:40]))
    print('  新增里词库没备注的 %d: %s' % (len(noNote), noNote[:40]))
    return added, gone, changed, noNote


def main():
    a = sys.argv[1] if len(sys.argv) > 1 else 'snap'
    if a == 'snap':
        snap()
        return
    if a == 'diff':
        if len(sys.argv) >= 4:
            diff(sys.argv[2], sys.argv[3])
            return
        dirs = sorted(glob.glob(os.path.join(ATTIC, 'cp-baseline-*')))
        if len(dirs) < 2:
            sys.exit('至少要有两份快照才能对比（先 snap 一次，换完再 snap 一次）')
        diff(dirs[-2], dirs[-1])
        return
    sys.exit('用法: snap | diff [旧目录 新目录]')


if __name__ == '__main__':
    main()
