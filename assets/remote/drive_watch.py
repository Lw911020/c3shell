#!/usr/bin/env python3
"""drive_watch.py — 常驻监听 C3 设备的「辅助驾驶」开关，只在翻转时输出一行。

只订阅 selfdriveState / deviceState，不做计算。输出：
  {"init": true, "en": 0|1, "started": 0|1}   首次观测（不播报，仅证通道活着）
  {"en": 1}  /  {"en": 0}                     状态翻转（连接器据此播报）
"""
import json
import os
import sys
import time

# 与 live_stream.py 同样的坑：远端裸 python3 没有 capnp，必须 re-exec 到 openpilot 的 venv
def _op_python():
    """找 openpilot 自己的解释器（**必须能 import capnp**）。
    坑（2026-09-24 实测）：不能只看 /proc/<pid>/exe —— 它会把符号链接解析掉，
    venv 路径（/usr/local/venv/bin/python3）被解析成 /usr/bin/python3.12，venv 就丢了 ✗，
    结果拿到一个没有 capnp 的解释器，注册表/服务全都降级。
    正确做法：① 读运行进程 cmdline 的 argv[0]（venv 路径只出现在这）
              ② 固定位置 + pyenv
              ③ **逐个试 import capnp**，选第一个真能用的 ✓"""
    import glob as _g
    import subprocess as _sp
    cands = []
    try:
        out = _sp.check_output(['sh', '-c',
            'for p in $(pgrep -f manager.py | head -3); do tr "\0" "\n" < /proc/$p/cmdline | head -1; done'],
            stderr=_sp.DEVNULL, timeout=6)
        for line in out.decode('utf-8', 'replace').split():
            if 'python' in line:
                cands.append(line)
    except Exception:
        pass
    cands += ['/usr/local/venv/bin/python3', '/data/openpilot/.venv/bin/python3']
    try:
        cands += sorted(_g.glob('/usr/local/pyenv/versions/*/bin/python3*'), reverse=True)
    except Exception:
        pass
    cands += ['/usr/local/pyenv/shims/python3', '/usr/bin/python3']
    seen = set()
    for c in cands:
        if c in seen or not (os.path.isfile(c) and os.access(c, os.X_OK)):
            continue
        seen.add(c)
        try:
            _sp.check_call([c, '-c', 'import capnp'], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=12)
            return c
        except Exception:
            continue
    return None
_op_py = _op_python()  # 动态解析（pyenv / venv / 运行时 manager）
VENV_CANDIDATES = ((_op_py,) if _op_py else ('/usr/local/venv/bin/python3', '/data/openpilot/.venv/bin/python3'))
if os.environ.get('DSH_DRIVE_REEXEC') != '1':
    try:
        import capnp  # noqa: F401
    except Exception:
        for cand in VENV_CANDIDATES:
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                os.environ['DSH_DRIVE_REEXEC'] = '1'
                os.execv(cand, [cand] + sys.argv)
                break

sys.path.insert(0, '/data/openpilot')


def emit(o):
    sys.stdout.write(json.dumps(o, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def flag(sm, svc, field):
    try:
        return 1 if getattr(sm[svc], field) else 0
    except Exception:
        return None


def main():
    try:
        from cereal import messaging
    except Exception as e:
        emit({'error': 'cannot import cereal.messaging: ' + str(e)[:160]})
        return 2
    # 2026-09-24：老镜像 0.9.8 没有 selfdriveState 服务（只有 controlsState）→ 动态挑一个，别硬订
    en_svc = 'selfdriveState'
    try:
        from cereal.services import SERVICE_LIST
        if 'selfdriveState' not in SERVICE_LIST:
            en_svc = 'controlsState' if 'controlsState' in SERVICE_LIST else 'selfdriveState'
    except Exception:
        pass
    sm = messaging.SubMaster([en_svc, 'deviceState'])
    last = None
    first = True
    while True:
        sm.update(1000)
        en = flag(sm, en_svc, 'enabled')
        started = flag(sm, 'deviceState', 'started')
        if first:
            first = False
            emit({'init': True, 'en': en if en is not None else -1,
                  'started': started if started is not None else -1})
            last = en
            continue
        if en is not None and en != last:
            emit({'en': en, 't': round(time.time(), 3)})
            last = en
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
