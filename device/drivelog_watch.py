#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drivelog_watch.py -- 后台读盘式行驶日志守望（不影响通信）

原则：
  1) 只读磁盘上的路测日志（qlog/rlog），**绝不订阅 cereal**（不进实时通信总线）；
  2) 以 nice -n 19 启动（有 ionice 则 ionice -c 3）：controlsd/modeld 是实时线程，不会被抢；
  3) 只处理「已封段」的目录（存在更新的段，或目录 mtime 超过 30 s），不碰正在写的那段；
  4) 每轮最多 3 段；rlog（车道线几何）至少间隔 RLOG_GAP 秒才啃一个；
  5) 结果只追加到 .dsh/drivewatch.jsonl 与 .dsh/drivewatch-status.json —— 查看只需读小文件。
用法: nice -n 19 /usr/local/venv/bin/python3 .dsh/drivelog_watch.py
"""
import os, sys, json, time, glob, traceback
os.chdir("/data/openpilot")
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

BASE = "/data/media/0/realdata"
D = "/data/openpilot/.dsh"
JSONL = D + "/drivewatch.jsonl"
STATUS = D + "/drivewatch-status.json"
STATE = D + "/drivewatch-state.json"
POLL = 8
MAX_PER_LOOP = 3
RLOG_GAP = 60.0
LOOKBACK_H = 3.0
SEAL_AGE = 30.0


def log(*a):
    print(time.strftime("[%H:%M:%S]", time.gmtime()), *a, flush=True)


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"done_qlog": [], "done_rlog": [], "last_rlog_ts": 0.0}


def save_state(s):
    tmp = STATE + ".tmp"
    json.dump(s, open(tmp, "w"))
    os.replace(tmp, STATE)


def list_dirs():
    now = time.time()
    out = []
    try:
        names = os.listdir(BASE)
    except Exception:
        return out
    for n in names:
        p = BASE + "/" + n
        try:
            if not os.path.isdir(p):
                continue
            m = os.path.getmtime(p)
        except Exception:
            continue
        if now - m > LOOKBACK_H * 3600:
            continue
        out.append((m, p, n))
    out.sort()
    return out


def qlog_metrics(p):
    f = p + "/qlog.zst"
    if not os.path.exists(f):
        return None
    n = 0; vmax = 0.0; sat = 0; sat_low = 0; sat_big = 0; tau_sum = 0.0; tau_n = 0
    lat = 0; cc_n = 0; ldw = [0, 0]; cs = None
    out_frames = 0; out_sum = 0.0; out_max = 0.0
    for m in LogReader(f):
        w = m.which(); n += 1
        if w == "carState":
            cs = m.carState
            if abs(cs.vEgo) > vmax:
                vmax = abs(cs.vEgo)
        elif w == "carControl":
            cc_n += 1
            try:
                if bool(m.carControl.latActive):
                    lat += 1
                t = abs(m.carControl.actuators.torque); tau_sum += t; tau_n += 1
                if t > 0.95:
                    sat += 1
                    if cs is not None:
                        if abs(cs.vEgo) < 5:
                            sat_low += 1
                        if abs(getattr(cs, "steeringAngleDeg", 0.0)) > 25:
                            sat_big += 1
            except Exception:
                pass
        elif w == "driverAssistance":
            da = m.driverAssistance
            if da.leftLaneDeparture:
                ldw[0] += 1
            if da.rightLaneDeparture:
                ldw[1] += 1
        elif w == "controlsState":
            try:
                cst = m.controlsState
                ts = cst.lateralControlState.torqueState
                err = float(ts.desiredLateralAccel) - float(ts.actualLateralAccel)
                sgn = 1.0 if cst.curvature > 0 else -1.0
                o = err * sgn
                out_frames += 1; out_sum += o
                if o > out_max:
                    out_max = o
            except Exception:
                pass
    return {"frames": n, "vmax": round(vmax, 2), "sat": sat, "sat_low": sat_low, "sat_big": sat_big,
            "tau": round(tau_sum / tau_n, 3) if tau_n else 0, "lat_frames": lat, "cc_frames": cc_n,
            "lat_pct": round(100.0 * lat / cc_n, 1) if cc_n else 0, "ldw": ldw,
            "a_out_avg": round(out_sum / out_frames, 3) if out_frames else 0, "a_out_max": round(out_max, 3)}


def rlog_metrics(p):
    f = p + "/rlog.zst"
    if not os.path.exists(f):
        return None
    devs = []; wide = 0; tight = 0; cross = 0; near = 0
    probs_lost = 0; model_n = 0; steer_ev = 0
    cs = None; cc = None; cst = None; press = False; pv = False
    for m in LogReader(f):
        w = m.which()
        if w == "carState":
            cs = m.carState
            pr = bool(cs.steeringPressed)
            if pr and not pv and cc is not None and cc.latActive and abs(cs.vEgo) > 5:
                steer_ev += 1
            pv = pr
        elif w == "carControl":
            cc = m.carControl
        elif w == "controlsState":
            cst = m.controlsState
        elif w == "modelV2":
            model_n += 1
            if cs is None or cc is None:
                continue
            try:
                lp = m.modelV2.laneLineProbs
                if len(lp) < 3 or lp[1] < 0.5 or lp[2] < 0.5:
                    probs_lost += 1
                    continue
                yl = float(m.modelV2.laneLines[1].y[0]); yr = float(m.modelV2.laneLines[2].y[0])
                width = yr - yl
                if not (1.2 < width < 6.5):
                    continue
                dev = ((yl + yr) / 2.0) / (width / 2.0)
                devs.append(abs(dev))
                if abs(dev) >= 1.0:
                    cross += 1
                if abs(dev) >= 0.85:
                    near += 1
                if cst is not None and cc.latActive and abs(float(cst.curvature)) > 0.002:
                    if dev * float(cst.curvature) < 0:
                        wide += 1
                    else:
                        tight += 1
            except Exception:
                continue
    devs.sort()

    def q(a, x):
        return round(a[min(len(a) - 1, int(x * len(a)))], 3) if a else None

    return {"model": model_n, "valid": len(devs), "probs_lost": probs_lost,
            "dev_med": q(devs, 0.5), "dev_p95": q(devs, 0.95), "dev_max": q(devs, 1.0),
            "near085": near, "cross10": cross, "wide": wide, "tight": tight,
            "driver_steer_events": steer_ev}


def write_status(segs):
    tmp = STATUS + ".tmp"
    json.dump({"updated": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC",
               "segs": [{"seg": k, **v} for k, v in segs[-30:]]},
              open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, STATUS)


def main():
    state = load_state()
    dq = set(state.get("done_qlog", []))
    dr = set(state.get("done_rlog", []))
    last_rlog = float(state.get("last_rlog_ts", 0.0))
    segs = []
    segmap = {}
    log("drivelog_watch started (read-only, no cereal)")
    while True:
        try:
            ds = list_dirs()
            if ds:
                newest = ds[-1][2]
                todo = []
                for m, p, n in ds:
                    if n == newest:
                        continue
                    if time.time() - m < SEAL_AGE:
                        continue
                    if n not in dq:
                        todo.append((m, p, n))
                for m, p, n in todo[:MAX_PER_LOOP]:
                    try:
                        r = qlog_metrics(p)
                        if r:
                            rec = {"seg": n, "t": time.strftime("%H:%M:%S", time.gmtime(m))}
                            rec.update(r)
                            open(JSONL, "a").write(json.dumps(rec, ensure_ascii=False) + "\n")
                            segmap[n] = r
                            if n not in [s[0] for s in segs]:
                                segs.append((n, r))
                            log("qlog", n, "vmax", r["vmax"], "sat", r["sat"], "lat%", r["lat_pct"])
                    except Exception as e:
                        log("qlog err", n, str(e)[:90])
                    dq.add(n)
                    state["done_qlog"] = sorted(dq)[-4000:]
                    save_state(state)
                if todo:
                    write_status(segs)
                for m, p, n in reversed(ds[-16:]):
                    if n == newest or n in dr or n not in dq:
                        continue
                    if time.time() - m < SEAL_AGE:
                        continue
                    rq = segmap.get(n)
                    if rq is not None and rq.get("vmax", 0) < 5:
                        dr.add(n)
                        state["done_rlog"] = sorted(dr)[-4000:]
                        save_state(state)
                        continue
                    if time.time() - last_rlog < RLOG_GAP:
                        break
                    try:
                        r = rlog_metrics(p)
                        if r:
                            rec = {"seg": n, "t": time.strftime("%H:%M:%S", time.gmtime(m))}
                            rec.update(r)
                            open(JSONL, "a").write(json.dumps(rec, ensure_ascii=False) + "\n")
                            log("rlog", n, "dev_max", r["dev_max"], "cross", r["cross10"],
                                "wide/tight", r["wide"], r["tight"], "steer", r["driver_steer_events"])
                    except Exception as e:
                        log("rlog err", n, str(e)[:90])
                    dr.add(n)
                    last_rlog = time.time()
                    state["done_rlog"] = sorted(dr)[-4000:]
                    state["last_rlog_ts"] = last_rlog
                    save_state(state)
                    write_status(segs)
                    break
            time.sleep(POLL)
        except Exception:
            log("loop err", traceback.format_exc()[-300:])
            time.sleep(POLL)


if __name__ == "__main__":
    main()
