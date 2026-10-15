#!/usr/bin/env python3
"""env_dump.py — 设备系统指纹 + APP 能力探测（只读，单行 JSON）

用途：APP 连上设备后**先问这一句**，再决定给哪些功能。
  2026-09-24 新增（CP / SP2024 / SP2025 三大类系统的适配入口）。
只读：不写任何文件、不改设备状态、不启停服务。
"""
import glob
import json
import os
import subprocess
import sys

OP = '/data/openpilot'
sys.path.insert(0, OP)

# APP 真正会用到的 cereal 服务（缺哪个，对应功能就要降级）
NEEDED_SERVICES = ['carState', 'carControl', 'selfdriveState', 'controlsState', 'lateralPlan',
                   'longitudinalPlan', 'liveParameters', 'modelV2', 'radarState', 'carParams',
                   'deviceState', 'pandaStates']


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
def _reexec_env():
    """APP 用系统 python3 跑本脚本（老镜像上是 3.8，连 params_pyx.so 都加载不了）→ 自我重入 openpilot 的解释器。"""
    if os.environ.get('DSH_ENV_REEXEC') == '1':
        return
    try:
        import capnp  # noqa: F401
        return
    except Exception:
        pass
    py = _op_python()
    if py:
        os.environ['DSH_ENV_REEXEC'] = '1'
        os.execv(py, [py] + sys.argv)


_reexec_env()

def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=6).stdout.decode('utf-8', 'replace').strip()
    except Exception:
        return ''


def fork_info():
    marks = {}
    for name, path in (('carrot', 'selfdrive/carrot'), ('frogpilot', 'selfdrive/frogpilot'),
                       ('sunnypilot', 'sunnypilot'), ('sunnypilot_ui', 'selfdrive/ui/sunnypilot'),
                       ('sunnypilot_old', 'selfdrive/sunnypilot')):
        marks[name] = os.path.isdir(os.path.join(OP, path))
    origin = ''
    try:
        origin = (version_info().get('origin') or '').lower()
    except Exception:
        pass
    marks['origin_sunnypilot'] = 'sunnypilot' in origin
    if marks['carrot']:
        fork, label = 'CP', 'CarrotPilot（胡萝卜）'
    elif marks['sunnypilot'] or marks['sunnypilot_old'] or marks['origin_sunnypilot']:
        fork, label = 'SP', 'SunnyPilot（阳光）'
    else:
        fork, label = 'OP', 'openpilot（官方）'
    return fork, label, marks


def version_info():
    out = {}
    try:
        b = json.load(open(os.path.join(OP, 'build.json'), encoding='utf-8'))
        o = b.get('openpilot', {}) or {}
        out = {'version': o.get('version', ''), 'channel': b.get('channel', ''),
               'origin': o.get('git_origin', ''), 'style': o.get('build_style', ''),
               'commit_date': o.get('git_commit_date', '')}
    except Exception:
        pass
    return out


def git_info():
    """SP 的 release 整包没有 .git —— 这里如实报告，APP 不该依赖它。"""
    info = {'hasGit': os.path.isdir(os.path.join(OP, '.git'))}
    if info['hasGit']:
        info['branch'] = sh('git -C %s rev-parse --abbrev-ref HEAD' % OP)
        info['head'] = sh('git -C %s rev-parse --short HEAD' % OP)
    info['paramGitBranch'] = param_get('GitBranch')
    return info


def param_dir():
    best, best_n = None, -1
    for d in (os.environ.get('PARAMS_DIR'), '/data/params/d_sp', '/data/params/d'):
        if not d:
            continue
        try:
            n = len(os.listdir(d))
        except Exception:
            continue
        if n > best_n:
            best, best_n = d, n
    return best or '/data/params/d', max(best_n, 0)


def param_get(key):
    try:
        from openpilot.common.params import Params
        v = Params().get(key)
        if isinstance(v, bytes):
            return v.decode('utf-8', 'replace')
        return None if v is None else str(v)
    except Exception:
        return None


def services_info():
    try:
        from cereal.services import SERVICE_LIST
        have = sorted(SERVICE_LIST.keys())
    except Exception:
        return {'known': False, 'present': [], 'missing': NEEDED_SERVICES}
    present = [s for s in NEEDED_SERVICES if s in have]
    missing = [s for s in NEEDED_SERVICES if s not in have]
    return {'known': True, 'present': present, 'missing': missing, 'total': len(have)}


def cast_info():
    """投屏 = 设备端 ui 进程被 LD_PRELOAD 注入钩子 + 采集开关。APP 要据此决定给不给投屏。"""
    ui_line = ''
    try:
        txt = open(os.path.join(OP, 'system/manager/process_config.py'), encoding='utf-8', errors='replace').read()
        for line in txt.splitlines():
            if 'NativeProcess("ui"' in line or "NativeProcess('ui'" in line:
                ui_line = line.strip()
                break
    except Exception:
        pass
    proc = sh('pgrep -x ui').split()
    injected = False
    for p in proc:
        if sh('grep -c uihook /proc/%s/maps' % p) not in ('', '0'):
            injected = True
    return {
        'uiProcess': bool(proc),
        'uiLine': ui_line[:160],
        'lineHasPreload': 'LD_PRELOAD' in ui_line,
        'hookSo': os.path.isfile(os.path.join(OP, '.dsh/uihook.so')),
        'injectedNow': injected,
        'touchd': os.path.isfile(os.path.join(OP, '.dsh/touchd')),
        'switchFile': os.path.exists('/dev/shm/ui.cast.on'),
        'frameFile': os.path.exists('/dev/shm/ui.rgb'),
        # 可用 = 钩子已注入（或至少可注入：有 .so + 进程行结构认识）
        'ready': injected,
        'installable': os.path.isfile(os.path.join(OP, '.dsh/uihook.so')) or True,
    }


def routes_info():
    root = '/data/media/0/realdata'
    dirs = glob.glob(os.path.join(root, '*--*'))
    size = sh('du -sh %s 2>/dev/null' % root).split()[0:1]
    return {'root': root, 'routes': len(dirs), 'size': size[0] if size else ''}


def main():
    fork, label, marks = fork_info()
    pdir, pcount = param_dir()
    svc = services_info()
    cast = cast_info()
    routes = routes_info()
    caps = {
        'params': pcount > 5,
        'live': len(svc['missing']) < len(NEEDED_SERVICES),
        'replay': routes['routes'] > 0,
        'cast': cast['ready'],
        'castInstallable': cast['installable'],
    }
    print(json.dumps({
        'ok': True,
        'fork': fork, 'forkLabel': label, 'marks': marks,
        'version': version_info(),
        'git': git_info(),
        'params': {'dir': pdir, 'count': pcount},
        'services': svc,
        'cast': cast,
        'routes': routes,
        'caps': caps,
    }, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
