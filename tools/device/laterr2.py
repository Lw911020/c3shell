# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

def q(a, p):
    if not a: return None
    b = sorted(a); return round(b[min(len(b) - 1, int(p * len(b)))], 3)

def analyze(name):
    cs = None; cc = None
    out = []; inn = []; n = 0; kappa_n = 0
    gt02 = gt03 = gt05 = 0
    line15 = oncom3 = 0
    worst = []
    for m in LogReader(name + "/rlog.zst"):
        w = m.which()
        if w == "carState":
            cs = m.carState
        elif w == "carControl":
            cc = m.carControl
        elif w == "controlsState":
            cst = m.controlsState
            if cs is None or cc is None or not cc.latActive: continue
            ts = cst.lateralControlState.torqueState
            kappa = float(getattr(cst, "curvature", 0.0))
            if abs(kappa) < 0.002: continue
            v = abs(cs.vEgo)
            err = float(ts.desiredLateralAccel) - float(ts.actualLateralAccel)
            sgn = 1.0 if kappa > 0 else -1.0
            outward = err * sgn
            n += 1
            if outward > 0:
                out.append(outward); kappa_n += 1
                d2 = 0.5 * outward * 4.0
                if outward > 0.2: gt02 += 1
                if outward > 0.3: gt03 += 1
                if outward > 0.5: gt05 += 1
                if d2 > 1.5: line15 += 1
                if d2 > 3.0: oncom3 += 1
                worst.append((round(outward, 2), round(d2, 2), round(v, 1), round(abs(kappa), 4)))
            else:
                inn.append(-outward)
    return {"seg": name.split("--")[-1], "curve_lat_frames": n, "outward_frames": kappa_n,
            "out_med": q(out, 0.5), "out_p90": q(out, 0.9), "out_max": q(out, 1.0),
            "in_med": q(inn, 0.5), "in_max": q(inn, 1.0),
            "f2": round(100.0 * gt02 / n, 1) if n else 0,
            "f3": round(100.0 * gt03 / n, 1) if n else 0,
            "f5": round(100.0 * gt05 / n, 1) if n else 0,
            "l15": round(100.0 * line15 / n, 1) if n else 0,
            "o3": round(100.0 * oncom3 / n, 1) if n else 0,
            "worst": sorted(worst, key=lambda x: -x[0])[:5]}

prefix = sys.argv[1]
outp = []
for r in sys.argv[2:]:
    name = prefix + r
    if not os.path.exists(name + "/rlog.zst"): continue
    try: outp.append(analyze(name))
    except Exception as e: outp.append({"seg": r, "err": str(e)[:130]})
print(json.dumps(outp, ensure_ascii=False))