#!/usr/bin/env python3
"""
live_stream.py - compact JSON sample stream out of openpilot.

  --live                 subscribe to the running openpilot (cereal SubMaster)
  --replay <dir|file>    replay a recorded segment instead (same output shape,
                         so the whole viewer can be validated without a car)
  --hz 10                output rate (default 10)
  --fast                 replay as fast as possible instead of real time
  --seconds N            stop after N seconds (0 = run forever)

One JSON object per line. The first line carries metadata:

  {"meta": {"car": "...", "safety": "...", "repo": "...", "python": "..."}}
  {"t": 12.3, "v": 20.1, "en": 1, "lat": 1, "sa": -1.2, "sc": -1.1, "err": 0.1,
   "curv": 0.0012, "la": 0.48, "tq": 0.31, "sr": 19.5, "ao": 4.2, "stf": 1.01,
   "lp": 0.9, "al": "..."}

Field reads are defensive: forks differ, missing values come out as null.
"""
import argparse
import glob
import json
import os
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
try:
    import numpy as _np
except Exception:
    _np = None
# 独立版 APP：诊断要 CAN/车辆数据，qlog 才有 → 优先 qlog（设备侧连接器那份不受影响）
LOG_ORDER = ('qlog.zst', 'qlog.bz2', 'qlog', 'rlog.zst', 'rlog.bz2', 'rlog')
# deviceState 曾经订了但从不消费（2026-09-20 去掉：少一路解码）
SUBSCRIBE_WANT = ['carState', 'carControl', 'selfdriveState', 'controlsState', 'lateralPlan',
                  'liveParameters', 'modelV2',
                  'radarState', 'longitudinalPlan', 'carParams',
                  # 2026-09-20：加这两路，样本里带上「点火 / openpilot 是否运行」，
                  # 页面才能区分「没上电」和「坏了」（实测未上电时只有这两路在发）。
                  'deviceState', 'pandaStates']


def _available(want):
    """按设备实际的 SERVICE_LIST 过滤订阅表。
    2026-09-24 实测：SP2025 没有 lateralPlan 服务 → 原来 SubMaster 直接 KeyError，
    运行曲线整页不可用。宁可少订一路，也不能让整页崩掉。"""
    try:
        from cereal.services import SERVICE_LIST
        have = [sv for sv in want if sv in SERVICE_LIST]
        missing = [sv for sv in want if sv not in SERVICE_LIST]
        if missing:
            sys.stderr.write('[live_stream] 设备无此服务，已跳过: ' + ', '.join(missing) + chr(10))
        return have or ['carState']
    except Exception as e:
        sys.stderr.write('[live_stream] 服务表不可用，按原表订阅: ' + str(e)[:120] + chr(10))
        return want


SUBSCRIBE = list(SUBSCRIBE_WANT)   # 真正的过滤在 run_live 里做（那时 sys.path 才含 repo，导入才成功）
# 车道中心拟合（numpy polyfit）是纯计算里最贵的一段：真机实测占单核 14.4%，
# 而它只是画「车道参考 / 30m 偏移」两条线 —— 2Hz 足够，不必跟着采样率跑。
LANE_FIT_PERIOD_S = 0.5


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


def first(o, name):
    # capnp 列表不能直接切片，取第 0 个元素
    try:
        v = getattr(o, name)
        return num(v[0]) if len(v) > 0 else None
    except Exception:
        return None


def find_log(p):
    if os.path.isfile(p):
        return p
    for name in LOG_ORDER:
        c = os.path.join(p, name)
        if os.path.isfile(c):
            return c
    return None


class Sampler(object):
    """Turns carState/carControl/... into one flat sample dict."""

    def __init__(self):
        self.cur = {}
        self.meta = {}
        self.last_alert = None
        self._next_fit = 0.0

    def feed_message(self, which, obj):
        c = self.cur
        if which == 'carState':
            c['v'] = num(dig(obj, 'vEgo'))
            c['sa'] = num(dig(obj, 'steeringAngleDeg'))
            c['stq'] = num(dig(obj, 'steeringTorque'))
            c['ae'] = num(dig(obj, 'aEgo'))
            c['gas'] = 1 if dig(obj, 'gasPressed') else 0
            c['brk'] = 1 if dig(obj, 'brakePressed') else 0
            c['gear'] = str(dig(obj, 'gearShifter') or '')
        elif which == 'carControl':
            c['lat'] = 1 if dig(obj, 'latActive') else 0
            c['lon'] = 1 if dig(obj, 'longActive') else 0
            sc = num(dig(obj, 'actuators.steeringAngleDeg'))
            if sc is None:
                sc = num(dig(obj, 'actuators.steer'))
            c['sc'] = sc
            c['tq'] = num(dig(obj, 'actuators.torque'))
            if c['tq'] is None:
                c['tq'] = num(dig(obj, 'actuators.torqueOutputCan'))
            curv = num(dig(obj, 'actuators.curvature'))
            if curv is None:
                curv = num(dig(obj, 'currentCurvature'))
            c['curv'] = curv
            c['oa'] = num(dig(obj, 'actuators.accel'))
        elif which == 'deviceState':
            sd = dig(obj, 'started')
            if sd is not None:
                c['started'] = 1 if sd else 0
        elif which == 'pandaStates':
            p0 = None
            try:
                if len(obj):
                    p0 = obj[0]
            except Exception:
                p0 = None
            if p0 is not None:
                il = dig(p0, 'ignitionLine')
                ic = dig(p0, 'ignitionCan')
                if il is not None:
                    c['ign'] = 1 if il else 0
                elif ic is not None:
                    c['ign'] = 1 if ic else 0
        elif which == 'selfdriveState':
            e = dig(obj, 'enabled')
            if e is not None:
                c['en'] = 1 if e else 0
            act = dig(obj, 'active')
            if act is not None:
                c['act'] = 1 if act else 0
            txt = dig(obj, 'alertText1')
            if txt:
                self.last_alert = str(txt)[:80]
                c['al'] = self.last_alert
        elif which == 'controlsState':
            c['mk'] = num(dig(obj, 'curvature'))
            c['dk'] = num(dig(obj, 'desiredCurvature'))
            c['all'] = 1 if dig(obj, 'activeLaneLine') else 0
            c['fd'] = 1 if dig(obj, 'forceDecel') else 0
            try:
                _st = obj.lateralControlState.torqueState
            except Exception:
                _st = None
            if _st is not None:
                c['td'] = num(dig(_st, 'desiredLateralAccel'))
                c['ta'] = num(dig(_st, 'actualLateralAccel'))
                c['sat'] = 1 if dig(_st, 'saturated') else 0
                # latcontrol 的内部输出（carcontroller 缩放/限幅之前）——设备调试图表 case6 用的就是它
                c['to'] = num(dig(_st, 'output'))
        elif which == 'lateralPlan':
            c['ull'] = 1 if dig(obj, 'useLaneLines') else 0
            c['co'] = num(dig(obj, 'curvatureOffset'))
        elif which == 'longitudinalPlan':
            c['pa'] = first(obj, 'accels')     # 规划加速度
            c['ps'] = first(obj, 'speeds')     # 规划车速
        elif which == 'radarState':
            l = dig(obj, 'leadOne')
            if l is not None and dig(l, 'status'):
                c['rd'] = num(dig(l, 'dRel'))
                c['rv'] = num(dig(l, 'vRel'))
                c['ra'] = num(dig(l, 'aLead'))
                c['rak'] = num(dig(l, 'aLeadK'))
                c['rj'] = num(dig(l, 'jLead'))
            else:
                c['rd'] = c['rv'] = c['ra'] = c['rj'] = None
        elif which == 'liveParameters':
            c['sr'] = num(dig(obj, 'steerRatio'))
            ao = num(dig(obj, 'angleOffsetAverageDeg'))
            if ao is None:
                ao = num(dig(obj, 'angleOffsetDeg'))
            c['ao'] = ao
            c['stf'] = num(dig(obj, 'stiffnessFactor'))
        elif which == 'modelV2':
            probs = []
            try:
                flat = dig(obj, 'laneLineProbs')
                if flat is not None:
                    probs = [num(x) for x in flat]
            except Exception:
                probs = []
            if not probs:
                try:
                    probs = [num(dig(l, 'probability')) for l in obj.laneLines]
                except Exception:
                    probs = []
            probs = [p for p in probs if p is not None and p > 0]
            if len(probs) >= 3:
                c['lp'] = min(probs[1], probs[2])
            elif probs:
                c['lp'] = min(probs)
            _v = None
            try:
                _v = float(c.get('v') or 0.0)
            except Exception:
                _v = 0.0
            # 车道中心线曲率与前方 30m 处横向偏移（前 40m 二次拟合，与离线分析同法）
            # 限速到 LANE_FIT_PERIOD_S：拟合结果变化很慢，没必要每个 modelV2 都算。
            if _np is not None and time.monotonic() >= self._next_fit:
                self._next_fit = time.monotonic() + LANE_FIT_PERIOD_S
                try:
                    ll = obj.laneLines
                    if len(ll) >= 4:
                        lx = _np.asarray([float(ll[1].x[i]) for i in range(len(ll[1].x))])
                        ly = _np.asarray([float(ll[1].y[i]) for i in range(len(ll[1].y))])
                        rx = _np.asarray([float(ll[2].x[i]) for i in range(len(ll[2].x))])
                        ry = _np.asarray([float(ll[2].y[i]) for i in range(len(ll[2].y))])
                        n = min(len(lx), len(rx))
                        cx = (lx[:n] + rx[:n]) / 2.0
                        cy = (ly[:n] + ry[:n]) / 2.0
                        m = (cx >= 0.0) & (cx <= 40.0)
                        if m.sum() >= 5:
                            a2, b2, c2 = _np.polyfit(cx[m], cy[m], 2)
                            c['lkc'] = round(float(2.0 * a2), 6)
                            c['loff30'] = round(float(a2 * 900.0 + b2 * 30.0 + c2), 3)
                except Exception:
                    pass
                try:
                    c['mx'] = num(obj.position.x[32])
                    c['mv32'] = num(obj.velocity.x[32])
                    c['mv0'] = num(obj.velocity.x[0])
                except Exception:
                    pass
        elif which == 'carParams':
            sm = ''
            try:
                sm = str(obj.safetyConfigs[0].safetyModel)
            except Exception:
                pass
            self.meta = {'car': str(dig(obj, 'carFingerprint') or ''), 'safety': sm,
                         'longControl': bool(dig(obj, 'openpilotLongitudinalControl')),
                         'steerRatio': num(dig(obj, 'steerRatio'))}

    def sample(self, rel):
        c = self.cur
        s = {'t': round(rel, 3)}
        for k in ('v', 'en', 'act', 'lat', 'lon', 'sa', 'sc', 'tq', 'curv', 'mk', 'dk', 'co',
                  'ta', 'td', 'lae', 'dce', 'sat', 'all', 'ull', 'fd', 'sr', 'ao', 'stf', 'lp', 'gas', 'brk', 'ae',
                  'to', 'oa', 'pa', 'ps', 'rd', 'rv', 'ra', 'rj', 'rak',
                  'lkc', 'loff30', 'mx', 'mv32', 'mv0',
                  'ign', 'started'):
            if k in c:
                s[k] = c[k]
        # 2026-09-19 FIX: carControl.actuators.steeringAngleDeg is NEVER populated on
        # this fork (verified on-device: stays 0.0 while torque/curvature/accel are live),
        # so |command - actual| steering error degenerated to |actual|. Emit the two error
        # signals the controller genuinely fills instead:
        #   lae = desiredLateralAccel - actualLateralAccel   (latcontrol_torque.py:340)
        #   dce = desiredCurvature    - curvature            (controlsd.py:448 - 445)
        if s.get('td') is not None and s.get('ta') is not None:
            s['lae'] = round(s['td'] - s['ta'], 4)
        if s.get('dk') is not None and s.get('mk') is not None:
            s['dce'] = round(s['dk'] - s['mk'], 5)
        v, curv = s.get('v'), s.get('curv')
        if v is not None and curv is not None:
            s['la'] = round(v * v * curv, 3)
        if c.get('al'):
            s['al'] = c['al']
        return s


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def _msg(sm, w):
    """取解码后的消息。本 fork 的 SubMaster 没有属性访问（sm.carState 直接
    AttributeError），解码结果在 sm.data（dict）或 sm[w] 里。
    旧代码是 `getattr(sm, w)` 且被 `except Exception: pass` 吞掉 ——
    于是每个样本只剩 {"t": ...}，页面上一条曲线都画不出来。"""
    d = getattr(sm, 'data', None)
    if isinstance(d, dict):
        m = d.get(w)
        if m is not None:
            return m
    try:
        return sm[w]
    except Exception:
        return None


def _flag(d, k):
    """sm.updated / sm.alive 取标志；取不到就当 True（宁多喂，不空转）。"""
    try:
        return bool(d.get(k))
    except Exception:
        try:
            return bool(dict(d).get(k))
        except Exception:
            return True


def run_live(args, sampler):
    try:
        from cereal import messaging
    except Exception as e:
        emit({'error': 'cannot import cereal.messaging: ' + str(e)[:160]})
        return 2
    global SUBSCRIBE
    SUBSCRIBE = _available(SUBSCRIBE_WANT)
    sm = messaging.SubMaster(SUBSCRIBE, poll='carState')
    period = 1.0 / max(1.0, args.hz)
    t0 = time.monotonic()
    next_emit = t0
    seen = set()
    meta_sent = False
    # 2026-09-20 性能修复（真机实测，CPU 占单核）：
    #   update(period) 里 poll='carState' 一有新帧就返回 —— carState 是 100Hz，
    #   于是循环按 100Hz 空转解码，跟 --hz 设多少无关（20Hz 与 5Hz 的 CPU 一模一样：
    #   8.9% vs 9.4%）。改成非阻塞 update(0) + 按 period 睡：解码次数 = 采样率。
    #   配套：只在 updated 为真时取消息（旧值本来就在 sampler 里），
    #   并把车道拟合限到 2Hz（那一段 numpy 单独占 14.4%）。
    while True:
        sm.update(0)
        for w in SUBSCRIBE:
            try:
                if _flag(sm.updated, w):
                    m = _msg(sm, w)
                    if m is not None:
                        sampler.feed_message(w, m)
            except Exception as e:
                key = w + ':' + type(e).__name__
                if key not in seen:
                    seen.add(key)
                    emit({'error': 'feed ' + key + ' -> ' + str(e)[:160]})
        if sampler.meta and not meta_sent:
            meta_sent = True
            emit({'meta': dict(sampler.meta, mode='live')})
        now = time.monotonic()
        if now >= next_emit:
            rel = now - t0
            emit(sampler.sample(rel))
            next_emit += period
            if next_emit < now:
                next_emit = now + period
            if args.seconds and rel >= args.seconds:
                return 0
        time.sleep(max(0.0, min(next_emit - time.monotonic(), period)))


def run_replay(args, sampler, LogReader):
    path = find_log(args.replay)
    if path is None:
        emit({'error': 'no log found in ' + args.replay})
        return 2
    period = 1.0 / max(1.0, args.hz)
    t0 = None
    last_emit_log_t = -1e9
    wall0 = time.monotonic()
    for m in LogReader(path):
        try:
            t = m.logMonoTime / 1e9
        except Exception:
            continue
        if t0 is None:
            t0 = t
            emit({'meta': {'car': '', 'safety': '', 'replay': path}})
        rel = t - t0
        w = m.which()
        if w == 'carParams':
            sampler.feed_message('carParams', m.carParams)
            if sampler.meta:
                emit({'meta': dict(sampler.meta, replay=path)})
            continue
        sampler.feed_message(w, getattr(m, w, None))
        if rel - last_emit_log_t >= period:
            last_emit_log_t = rel
            emit(sampler.sample(rel))
            if args.seconds and rel >= args.seconds:
                return 0
            if not args.fast:
                target = wall0 + rel
                now = time.monotonic()
                if target > now:
                    time.sleep(min(target - now, 0.5))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', action='store_true')
    ap.add_argument('--replay', default='')
    ap.add_argument('--repo', default='/data/openpilot')
    ap.add_argument('--hz', type=float, default=10.0)
    ap.add_argument('--fast', action='store_true')
    ap.add_argument('--seconds', type=float, default=0.0)
    args = ap.parse_args()
    _reexec_with_venv()

    if args.repo and os.path.isdir(args.repo) and args.repo not in sys.path:
        sys.path.insert(0, args.repo)

    sampler = Sampler()
    if args.live:
        emit({'meta': {'mode': 'live', 'python': sys.executable}})
        return run_live(args, sampler)

    if not args.replay:
        emit({'error': 'either --live or --replay is required'})
        return 2
    LogReader = None
    err = None
    for mod in ('openpilot.tools.lib.logreader', 'tools.lib.logreader'):
        try:
            LogReader = getattr(__import__(mod, fromlist=['LogReader']), 'LogReader')
            break
        except Exception as e:
            err = type(e).__name__ + ': ' + str(e)[:120]
    if LogReader is None:
        emit({'error': 'cannot import LogReader (' + str(err) + ')'})
        return 2
    return run_replay(args, sampler, LogReader)


if __name__ == '__main__':
    sys.exit(main())
