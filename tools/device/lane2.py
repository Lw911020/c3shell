# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

def pct(a, q):
    if not a: return 0.0
    return round(a[min(len(a) - 1, int(q * len(a)))], 2)

def analyze(name):
    cs = None; cc = None; cst = None
    n_model = 0; valid = 0
    devs = []; corner = []; straight = []
    wide = 0; tight = 0; near = 0; cross = []
    tau_sum = 0.0; tau_n = 0; sat = 0; sat_low = 0; sat_big = 0
    ldw = [0, 0]; vmax = 0.0; t0 = None
    for m in LogReader(name + "/rlog.zst"):
        w = m.which()
        if t0 is None: t0 = m.logMonoTime
        if w == "carState":
            cs = m.carState
            v = abs(cs.vEgo)
            if v > vmax: vmax = v
        elif w == "carControl":
            cc = m.carControl
            try:
                t = abs(cc.actuators.torque); tau_sum += t; tau_n += 1
                if t > 0.95:
                    sat += 1
                    if cs is not None:
                        if abs(cs.vEgo) < 5: sat_low += 1
                        if abs(getattr(cs, "steeringAngleDeg", 0.0)) > 25: sat_big += 1
            except Exception: pass
        elif w == "controlsState":
            cst = m.controlsState
        elif w == "driverAssistance":
            da = m.driverAssistance
            if da.leftLaneDeparture: ldw[0] += 1
            if da.rightLaneDeparture: ldw[1] += 1
        elif w == "modelV2":
            n_model += 1
            if cs is None or cc is None: continue
            mv = m.modelV2
            lp = mv.laneLineProbs
            if len(lp) < 3 or lp[1] < 0.5 or lp[2] < 0.5: continue
            yl = mv.laneLines[1].y[0]; yr = mv.laneLines[2].y[0]
            width = yr - yl
            if not (1.2 < width < 6.5): continue
            valid += 1
            half = width / 2.0; center = (yl + yr) / 2.0
            dev = center / half
            adev = abs(dev)
            v = abs(cs.vEgo)
            curv = getattr(cst, "curvature", 0.0) if cst is not None else 0.0
            devs.append(adev)
            if abs(curv) > 0.003:
                corner.append(adev)
                if dev * curv < 0: wide += 1
                else: tight += 1
            else:
                straight.append(adev)
            if adev >= 1.0:
                cross.append({"t": round((m.logMonoTime - t0) / 1e9, 1), "dev": round(dev, 2), "v": round(v, 1),
                              "ang": round(cs.steeringAngleDeg, 1), "curv": round(curv, 5),
                              "lat": bool(cc.latActive), "press": bool(cs.steeringPressed),
                              "blink": bool(cs.leftBlinker or cs.rightBlinker)})
            if adev >= 0.85: near += 1
    sa = sorted(devs); sc = sorted(corner); ss = sorted(straight)
    return {"seg": name.split("--")[-1], "model": n_model, "valid": valid, "vmax": round(vmax, 1),
            "sat": sat, "sat_low": sat_low, "sat_big": sat_big, "tau": round(tau_sum / tau_n, 3) if tau_n else 0,
            "ldw": ldw,
            "dev_mean": round(sum(devs) / len(devs), 3) if devs else 0, "dev_p95": pct(sa, 0.95),
            "dev_max": sa[-1] if sa else 0, "near085": near, "cross10": len(cross),
            "corner_n": len(corner), "corner_mean": round(sum(corner) / len(corner), 3) if corner else 0,
            "corner_p95": pct(sc, 0.95), "corner_max": sc[-1] if sc else 0, "wide": wide, "tight": tight,
            "straight_n": len(straight), "straight_mean": round(sum(straight) / len(straight), 3) if straight else 0,
            "straight_p95": pct(ss, 0.95), "straight_max": ss[-1] if ss else 0,
            "cross_samples": cross[:8]}

prefix = sys.argv[1]
out = []
for r in sys.argv[2:]:
    name = prefix + r
    if not os.path.exists(name + "/rlog.zst"): continue
    try: out.append(analyze(name))
    except Exception as e: out.append({"seg": r, "err": str(e)[:120]})
print(json.dumps(out, ensure_ascii=False))