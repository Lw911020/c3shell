#!/usr/bin/env python3
"""
scan_routes.py - fast triage of every recorded segment on the device.

Classifies each segment as parked / manual / openpilot-engaged / mixed-with-
interventions, and rolls the result up per route. Reads qlog (10Hz, ~15x
smaller) by default and only falls back to rlog when qlog is missing.

  python3 scan_routes.py --root /data/media/0/realdata [--limit N] [--segments] [--out /tmp/scan.json]
"""
import argparse
import collections
import glob
import json
import os
import signal
import sys
import time

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
_op_py = _op_python()
_op_py = _op_python()  # 动态解析（pyenv / venv / 运行时 manager）
VENV_CANDIDATES = ((_op_py,) if _op_py else ('/usr/local/venv/bin/python3', '/data/openpilot/.venv/bin/python3'))
LOG_ORDER = ('qlog.zst', 'qlog.bz2', 'qlog', 'rlog.zst', 'rlog.bz2', 'rlog')


def _reexec_with_venv():
    if os.environ.get('DSH_ANALYZE_REEXEC') == '1':
        return
    try:
        import capnp  # noqa: F401
        return
    except Exception:
        pass
    for cand in VENV_CANDIDATES:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            os.environ['DSH_ANALYZE_REEXEC'] = '1'
            os.execv(cand, [cand] + sys.argv)
            return


def try_import_logreader(repo):
    if repo and os.path.isdir(repo) and repo not in sys.path:
        sys.path.insert(0, repo)
    errs = []
    for mod, attr in (('openpilot.tools.lib.logreader', 'LogReader'),
                      ('tools.lib.logreader', 'LogReader'),
                      ('selfdrive.logreader', 'LogReader')):
        try:
            m = __import__(mod, fromlist=[attr])
            return getattr(m, attr), mod, None
        except Exception as e:
            errs.append(mod + ': ' + type(e).__name__ + ': ' + str(e)[:100])
    return None, None, ' | '.join(errs)


def num(v):
    try:
        f = float(v)
    except Exception:
        return None
    if f != f or f in (float('inf'), float('-inf')):
        return None
    return f


def dig(o, path):
    cur = o
    for part in path.split('.'):
        if cur is None:
            return None
        try:
            cur = getattr(cur, part)
        except Exception:
            return None
    return cur


def pick_log(d):
    for name in LOG_ORDER:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p, name
    return None, None


def scan_segment(LogReader, path):
    st = {
        'messages': 0, 'durationS': 0.0,
        'engaged': 0, 'latActive': 0, 'longActive': 0,
        'sdMessages': 0, 'sdEngaged': 0, 'csMessages': 0, 'csEngaged': 0,
        'ccMessages': 0, 'csTimes': [],
        'vMax': 0.0, 'vSum': 0.0, 'vN': 0,
        'steerAbsMax': 0.0, 'torqueAbsMax': 0.0,
        'disengagements': 0, 'disengageTimes': [],
        'alerts': {}, 'events': {},
    }
    t0 = None
    prev_enabled = None
    for m in LogReader(path):
        try:
            t = m.logMonoTime / 1e9
        except Exception:
            continue
        if t0 is None:
            t0 = t
        rel = t - t0
        st['messages'] += 1
        w = m.which()
        if w == 'carState':
            st['csTimes'].append(t)
            v = num(dig(m.carState, 'vEgo'))
            if v is not None:
                st['vN'] += 1
                st['vSum'] += v
                if v > st['vMax']:
                    st['vMax'] = v
            s = num(dig(m.carState, 'steeringAngleDeg'))
            if s is not None and abs(s) > st['steerAbsMax']:
                st['steerAbsMax'] = abs(s)
        elif w == 'carControl':
            st['ccMessages'] += 1
            if dig(m.carControl, 'latActive'):
                st['latActive'] += 1
            if dig(m.carControl, 'longActive'):
                st['longActive'] += 1
            tq = num(dig(m.carControl, 'actuators.torque'))
            if tq is not None and abs(tq) > st['torqueAbsMax']:
                st['torqueAbsMax'] = abs(tq)
        elif w == 'selfdriveState':
            obj = m.selfdriveState
            st['sdMessages'] += 1
            val = bool(dig(obj, 'enabled'))
            if val:
                st['sdEngaged'] += 1
            if prev_enabled and not val:
                st['disengagements'] += 1
                if len(st['disengageTimes']) < 20:
                    st['disengageTimes'].append(round(rel, 1))
            prev_enabled = val
            for fld in ('alertText1', 'alertText2'):
                txt = dig(obj, fld)
                if txt:
                    txt = str(txt)[:80]
                    st['alerts'][txt] = st['alerts'].get(txt, 0) + 1
        elif w == 'controlsState':
            # kept as a separate signal: on forks that publish both, mixing them
            # in one denominator halves the engagement number.
            st['csMessages'] += 1
            if dig(m.controlsState, 'enabled'):
                st['csEngaged'] += 1
        elif w == 'onroadEvents':
            try:
                evs = m.onroadEvents or []
            except Exception:
                evs = []
            for ev in evs:
                nm = dig(ev, 'name')
                if nm and dig(ev, 'enable'):
                    nm = str(nm)[:60]
                    st['events'][nm] = st['events'].get(nm, 0) + 1

    st['engaged'] = st['sdEngaged'] if st['sdMessages'] else st['csEngaged']
    st['sdUsed'] = st['sdMessages'] if st['sdMessages'] else st['csMessages']
    sd = st['sdUsed']
    st['engagedPct'] = round(100.0 * st['engaged'] / sd, 1) if sd else 0.0

    # The first message of a qlog often carries a stale logMonoTime (route start, not
    # segment start), which inflates last-first. Trim both ends of the dense carState
    # series instead.
    times = st.pop('csTimes', [])
    if len(times) >= 20:
        times.sort()
        lo = times[int(len(times) * 0.005)]
        hi = times[int(len(times) * 0.995)]
        st['durationS'] = max(0.0, hi - lo)
    else:
        st['durationS'] = 0.0
    st.pop('sdEngaged', None)
    st.pop('csEngaged', None)
    st['latActivePct'] = round(100.0 * st['latActive'] / st['ccMessages'], 1) if st['ccMessages'] else 0.0
    st['vAvg'] = round(st['vSum'] / st['vN'], 2) if st['vN'] else 0.0
    st['vMax'] = round(st['vMax'], 2)
    st['steerAbsMax'] = round(st['steerAbsMax'], 1)
    st['torqueAbsMax'] = round(st['torqueAbsMax'], 3)
    st.pop('vSum', None)
    st.pop('vN', None)
    st['topAlerts'] = [k for k, _ in sorted(st['alerts'].items(), key=lambda x: -x[1])[:4]]
    st['topEvents'] = [k for k, _ in sorted(st['events'].items(), key=lambda x: -x[1])[:4]]
    st.pop('alerts', None)
    st.pop('events', None)
    return st


VALID_CLASSES = ('op', 'op_with_intervention', 'mixed')


def classify(st):
    if st['vMax'] < 0.5 and st['engagedPct'] < 1:
        return 'parked'
    if st['engagedPct'] >= 80:
        return 'op' if not st['disengagements'] else 'op_with_intervention'
    if st['engagedPct'] >= 5:
        return 'mixed'
    return 'manual'


def write_progress(path, obj):
    """2026-09-24 R82：**原子**写进度文件（临时文件 + os.replace）✓
    原来 open(path,'w') 是先截断再写 → 读侧可能读到半截 JSON → 解析成 null →
    页面回落到"正在启动扫描…3%" → 这就是进度条"往回跳"的元凶之一 ✗"""
    if not path:
        return
    try:
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            f.write(json.dumps(obj))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        pass


def kill_previous_scan(path):
    """单实例：把还在跑的上一轮扫描杀掉 ✓
    两个扫描进程同时写同一个进度文件 → 一个报 43/508、另一个报 175/447 →
    页面每 1.5 秒在两组数字之间来回切 → 进度条疯狂"前后跳" ✗（现场实测就是这样）"""
    try:
        with open(path) as f:
            old = json.load(f)
        pid = int(old.get('pid') or 0)
        if pid > 1 and pid != os.getpid():
            try:
                cl = open('/proc/%d/cmdline' % pid, 'rb').read().decode('utf-8', 'ignore')
            except Exception:
                cl = ''
            if 'scan_routes' in cl or 'dsh-scan' in cl:
                os.kill(pid, signal.SIGKILL)
                sys.stderr.write("DSH_KILLED_OLD %d%s" % (pid, chr(10)))
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/data/media/0/realdata')
    ap.add_argument('--repo', default='/data/openpilot')
    ap.add_argument('--limit', type=int, default=0, help='only scan N newest segments')
    ap.add_argument('--segments', action='store_true', help='include per-segment detail')
    ap.add_argument('--out', default='')
    ap.add_argument('--progress', default='')
    args = ap.parse_args()
    _reexec_with_venv()

    t_start = time.time()
    kill_previous_scan(args.progress)
    # 2026-09-23 自定义时间窗：#S=/#E= 后缀必须在"收集目录"之前剥掉 ✗ 否则路径不存在 → 0 条
    _rng_s = 0; _rng_e = 4102444800
    try:
        _r0 = str(args.root)
        import re as _re
        _ms = _re.search(r"#S=(\d+)", _r0); _me = _re.search(r"#E=(\d+)", _r0)
        if _ms or _me:
            _rng_s = int(_ms.group(1)) if _ms else 0
            _rng_e = int(_me.group(1)) if _me else 4102444800
            args.root = _re.sub(r"#.*$", "", _r0)
    except Exception:
        pass
    dirs = [d for d in glob.glob(os.path.join(args.root, '*--*')) if os.path.isdir(d)]
    # 2026-09-23 时间过滤：自定义窗(#S/#E) 或 最近 N 天(--limit 负数) ✓
    try:
        if _rng_s or _rng_e < 4102444800:
            _b = len(dirs)
            dirs = [d for d in dirs if _rng_s <= os.path.getmtime(d) <= _rng_e]
            sys.stderr.write("DSH_RANGE %d -> %d\n" % (_b, len(dirs)))
        elif args.limit < 0:
            _cut = time.time() - abs(args.limit) * 86400
            _b = len(dirs)
            dirs = [d for d in dirs if os.path.getmtime(d) >= _cut]
            sys.stderr.write("DSH_DAYS %d -> %d\n" % (_b, len(dirs)))
    except Exception:
        pass
    dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    # 2026-09-24 R78：**只有正数才截断**！负数（最近 N 天）在这里会被当成 dirs[:-N] 砍掉尾巴 ✗
    if args.limit > 0:
        dirs = dirs[:args.limit]

    out = {'ok': True, 'root': args.root, 'python': sys.executable,
           'scopeLimit': args.limit, 'scopeFrom': _rng_s, 'scopeTo': _rng_e,
           'candidates': len(dirs), 'errors': [], 'summary': {}, 'routes': []}

    LogReader, modname, err = try_import_logreader(args.repo)
    out['logreader'] = modname
    if LogReader is None:
        out['ok'] = False
        out['error'] = 'cannot import LogReader (' + str(err) + ')'
        print(json.dumps(out))
        return

    per_seg = []
    # 2026-09-24 R68：开扫先写一条 0 进度（进度条立刻出现 ✓）
    # 2026-09-24 R82：改成两阶段 + 原子写 + 带 pid ✓
    write_progress(args.progress, {'phase': 1, 'phaseName': '扫描分类', 'pid': os.getpid(),
        'scanned': 0, 'total': len(dirs), 'pct': 0.0, 'cur': '', 'elapsedS': 0, 'etaS': None,
        'valid': 0, 'invalid': 0})
    for i, d in enumerate(dirs):
        log, name = pick_log(d)
        if log is None:
            continue
        try:
            st = scan_segment(LogReader, log)
        except Exception as e:
            out['errors'].append(os.path.basename(d) + ': ' + type(e).__name__ + ': ' + str(e)[:90])
            continue
        st['dir'] = os.path.basename(d)
        st['log'] = name
        st['mtime'] = int(os.path.getmtime(d))
        st['class'] = classify(st)
        per_seg.append(st)
        # 2026-09-24 R68：**每条都写进度**（原来 %25 → 扫 6 条时全程看不到进度 ✗）
        if args.progress:
            _el = time.time() - t_start
            _v = sum(1 for x in per_seg if x['class'] in VALID_CLASSES)
            write_progress(args.progress, {
                'phase': 1, 'phaseName': '扫描分类', 'pid': os.getpid(),
                'scanned': i + 1, 'total': len(dirs),
                'pct': round(100.0 * (i + 1) / max(1, len(dirs)), 1),
                'cur': os.path.basename(d)[:44],
                'elapsedS': round(_el, 1),
                'etaS': round(_el / max(1, i + 1) * (len(dirs) - i - 1), 1),
                'valid': _v, 'invalid': len(per_seg) - _v})

    # ═══ 阶段②：只对「有效数据」（被 openpilot 接管过的段）做分析 ═══
    valid_segs = [st for st in per_seg if st['class'] in VALID_CLASSES]
    write_progress(args.progress, {'phase': 2, 'phaseName': '分析有效数据', 'pid': os.getpid(),
        'scanned': 0, 'total': max(1, len(valid_segs)), 'pct': 0.0, 'cur': '',
        'elapsedS': round(time.time() - t_start, 1), 'etaS': None,
        'valid': len(valid_segs), 'invalid': len(per_seg) - len(valid_segs)})
    _t2 = time.time()

    # route rollup（只汇总有效数据 ✓）
    by_route = collections.OrderedDict()
    for _k, st in enumerate(valid_segs):
        _el = time.time() - t_start
        write_progress(args.progress, {'phase': 2, 'phaseName': '分析有效数据', 'pid': os.getpid(),
            'scanned': _k + 1, 'total': max(1, len(valid_segs)),
            'pct': round(100.0 * (_k + 1) / max(1, len(valid_segs)), 1),
            'cur': str(st['dir'])[:44], 'elapsedS': round(_el, 1),
            'etaS': round((time.time() - _t2) / max(1, _k + 1) * (len(valid_segs) - _k - 1), 1),
            'valid': len(valid_segs), 'invalid': len(per_seg) - len(valid_segs)})
        name = st['dir']
        i = name.rfind('--')
        route = name[:i] if i > 0 else name
        seg = name[i + 2:] if i > 0 else '?'
        r = by_route.setdefault(route, {
            'route': route, 'segments': 0, 'engaged': 0, 'sdMessages': 0, 'disengTimes': [],
            'durationS': 0.0, 'vMax': 0.0, 'disengagements': 0,
            'classes': collections.Counter(), 'alerts': collections.Counter(),
            'events': collections.Counter(), 'mtime': 0, 'segList': [],
        })
        r['segments'] += 1
        r['engaged'] += st['engaged']
        r['sdMessages'] += st.get('sdUsed', 0)
        r['durationS'] += st['durationS']
        r['vMax'] = max(r['vMax'], st['vMax'])
        r['disengagements'] += st['disengagements']
        if st['disengagements']:
            r['disengTimes'].append({'seg': seg, 'times': st['disengageTimes'][:6]})
        r['classes'][st['class']] += 1
        for a in st['topAlerts']:
            r['alerts'][a] += 1
        for e in st['topEvents']:
            r['events'][e] += 1
        r['mtime'] = max(r['mtime'], st['mtime'])
        r['segList'].append(seg)

    routes = []
    for r in by_route.values():
        r['engagedPct'] = round(100.0 * r['engaged'] / r['sdMessages'], 1) if r['sdMessages'] else 0.0
        r['vMax'] = round(r['vMax'], 1)
        r['durationMin'] = round(r['durationS'] / 60.0, 1)
        if r['vMax'] < 0.5 and r['engagedPct'] < 1:
            r['dominant'] = 'parked'
        elif r['engagedPct'] >= 80:
            r['dominant'] = 'op' if not r['disengagements'] else 'op_with_intervention'
        elif r['engagedPct'] >= 5:
            r['dominant'] = 'mixed'
        else:
            r['dominant'] = 'manual'
        r['classBreakdown'] = dict(r['classes'])
        r['segList'] = ','.join(sorted(r['segList'], key=lambda x: int(x) if x.isdigit() else 0))
        r['topAlerts'] = [k for k, _ in r['alerts'].most_common(5)]
        r['topEvents'] = [k for k, _ in r['events'].most_common(5)]
        r.pop('alerts', None)
        r.pop('events', None)
        r.pop('engaged', None)
        r.pop('sdMessages', None)
        r.pop('durationS', None)
        routes.append(r)
    routes.sort(key=lambda x: x['mtime'], reverse=True)

    summary = collections.Counter()
    for st in per_seg:
        summary[st['class']] += 1
    engaged_s = sum(st['durationS'] * st['engagedPct'] / 100.0 for st in per_seg)
    total_s = sum(st['durationS'] for st in per_seg)
    out['summary'] = {
        'segments': len(per_seg),
        'validSegments': len(valid_segs),
        'invalidSegments': len(per_seg) - len(valid_segs),
        'validClasses': dict(collections.Counter(st['class'] for st in valid_segs)),
        'routes': len(routes),
        'totalHours': round(total_s / 3600.0, 2),
        'engagedHours': round(engaged_s / 3600.0, 2),
        'classes': dict(summary),
        'withIntervention': sum(st['disengagements'] for st in per_seg),
        'withRlogOnly': sum(1 for st in per_seg if st['log'].startswith('rlog')),
    }
    out['routes'] = routes
    if args.segments:
        out['segmentDetail'] = per_seg
    out['tookS'] = round(time.time() - t_start, 1)

    write_progress(args.progress, {'phase': 2, 'phaseName': '分析有效数据', 'pid': os.getpid(),
        'scanned': len(valid_segs), 'total': max(1, len(valid_segs)), 'pct': 100.0, 'cur': '',
        'elapsedS': round(time.time() - t_start, 1), 'etaS': 0, 'done': True,
        'valid': len(valid_segs), 'invalid': len(per_seg) - len(valid_segs)})

    text = json.dumps(out)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text)
    print(text)


if __name__ == '__main__':
    main()
