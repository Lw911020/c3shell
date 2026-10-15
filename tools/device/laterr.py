# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

def med(a):
    if not a: return None
    b = sorted(a); return round(b[len(b) // 2], 3)

def analyze(name):
    cs = None; cc = None
    variant = None; vfields = None
    n = 0; vmax = 0.0
    errs = []; errs_curve = []; curve_n = 0; track_n = 0
    over02 = over05 = 0; drift15 = drift30 = 0; sat_frames = 0
    sat_when_err = 0
    errs_by_curv = []
    for m in LogReader(name + "/rlog.zst"):
        w = m.which()
        if w == "carState":
            cs = m.carState
            if abs(cs.vEgo) > vmax: vmax = abs(cs.vEgo)
        elif w == "carControl":
            cc = m.carControl
        elif w == "controlsState":
            cst = m.controlsState
            lcs = cst.lateralControlState
            variant = lcs.which()
            ob = getattr(lcs, variant)
            if vfields is None:
                vfields = sorted([q for q in dir(ob) if not q.startswith("_")])
            if cs is None or cc is None: continue
            if not cc.latActive: continue
            v = abs(cs.vEgo)
            a_act = None; a_des = None
            for nm in ("actualLateralAccel", "actualLatAccel"):
                if hasattr(ob, nm): a_act = float(getattr(ob, nm))
            for nm in ("desiredLateralAccel", "desiredLatAccel"):
                if hasattr(ob, nm): a_des = float(getattr(ob, nm))
            if a_act is None or a_des is None:
                ac = getattr(ob, "actualCurvature", None); dc = getattr(ob, "desiredCurvature", None)
                if ac is not None and dc is not None:
                    a_act = v * v * float(ac); a_des = v * v * float(dc)
            if a_act is None or a_des is None: continue
            kappa = abs(getattr(cst, "curvature", 0.0))
            err = a_des - a_act
            n += 1
            errs.append(err)
            d2 = 0.5 * abs(err) * 4.0
            if kappa > 0.002:
                curve_n += 1; errs_curve.append(err); errs_by_curv.append((round(kappa, 4), round(err, 3), round(v, 1)))
                if abs(err) > 0.2: over02 += 1
                if abs(err) > 0.5: over05 += 1
                if d2 > 1.5: drift15 += 1
                if d2 > 3.0: drift30 += 1
                if bool(getattr(ob, "saturated", False)): sat_frames += 1
                if abs(err) > 0.3 and bool(getattr(ob, "saturated", False)): sat_when_err += 1
    errs_curve_sorted = sorted(errs_curve)
    return {"seg": name.split("--")[-1], "variant": variant, "fields": vfields, "n_lat": n, "vmax": round(vmax, 1),
            "curve_n": curve_n, "err_med_all": med(errs), "err_med_curve": med(errs_curve),
            "err_p90_curve": round(errs_curve_sorted[int(0.9 * len(errs_curve_sorted))], 2) if errs_curve_sorted else None,
            "err_max_curve": round(errs_curve_sorted[-1], 2) if errs_curve_sorted else None,
            "frac_over_0.2": round(100.0 * over02 / curve_n, 1) if curve_n else 0,
            "frac_over_0.5": round(100.0 * over05 / curve_n, 1) if curve_n else 0,
            "frac_drift2s_gt1.5m": round(100.0 * drift15 / curve_n, 1) if curve_n else 0,
            "frac_drift2s_gt3m": round(100.0 * drift30 / curve_n, 1) if curve_n else 0,
            "sat_in_curve": sat_frames, "sat_with_err": sat_when_err,
            "worst": sorted(errs_by_curv, key=lambda x: -abs(x[1]))[:5]}

prefix = sys.argv[1]
out = []
for r in sys.argv[2:]:
    name = prefix + r
    if not os.path.exists(name + "/rlog.zst"): continue
    try: out.append(analyze(name))
    except Exception as e: out.append({"seg": r, "err": str(e)[:130]})
print(json.dumps(out, ensure_ascii=False))