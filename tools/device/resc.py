# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

def near(hist, t, dt):
    best = None; bd = 1e9
    for h in hist:
        d = abs(h[0] - (t + dt))
        if d < bd: bd = d; best = h
    return best

def analyze(name):
    cs = None; cc = None; cst = None
    n_model = 0; valid = 0; rej_prob = 0; rej_width = 0; blind = 0
    lat_prev = None; press_prev = None
    events = []; hist = []; lastdev = None; t0 = None
    lat_dev_max = 0.0
    def snap():
        return (abs(cs.vEgo) if cs else 0.0,
                getattr(cst, "curvature", 0.0) if cst is not None else 0.0,
                getattr(cs, "steeringAngleDeg", 0.0) if cs else 0.0,
                bool(getattr(cs, "steeringPressed", False)) if cs else False,
                bool(cc.latActive) if cc is not None else False,
                abs(getattr(cc.actuators, "torque", 0.0)) if cc is not None else 0.0)
    for m in LogReader(name + "/rlog.zst"):
        w = m.which()
        if t0 is None: t0 = m.logMonoTime
        tt = (m.logMonoTime - t0) / 1e9
        if w == "carState":
            cs = m.carState
            press = bool(cs.steeringPressed)
            if press_prev is False and press and abs(cs.vEgo) > 5 and cc is not None and cc.latActive:
                v, curv, ang, p, lat, tau = snap()
                events.append({"kind": "driver_steer", "t": round(tt, 1), "v": round(v, 1), "curv": round(curv, 5), "ang": round(ang, 1), "dev": lastdev, "tau": round(tau, 2)})
            press_prev = press
        elif w == "carControl":
            cc = m.carControl
            lat = bool(cc.latActive)
            if lat_prev is True and not lat and cs is not None and abs(cs.vEgo) > 5:
                v, curv, ang, p, l2, tau = snap()
                events.append({"kind": "lat_off", "t": round(tt, 1), "v": round(v, 1), "curv": round(curv, 5), "ang": round(ang, 1), "dev": lastdev, "tau": round(tau, 2)})
            lat_prev = lat
        elif w == "controlsState":
            cst = m.controlsState
        elif w == "modelV2":
            n_model += 1
            if cs is None: continue
            mv = m.modelV2
            lp = mv.laneLineProbs
            if len(lp) < 3 or lp[1] < 0.5 or lp[2] < 0.5:
                rej_prob += 1
                if lastdev is not None and abs(lastdev) > 0.6: blind += 1
                continue
            yl = mv.laneLines[1].y[0]; yr = mv.laneLines[2].y[0]
            width = yr - yl
            if not (1.2 < width < 6.5):
                rej_width += 1; continue
            valid += 1
            dev = ((yl + yr) / 2.0) / (width / 2.0)
            lastdev = round(dev, 2)
            if cc is not None and cc.latActive and abs(dev) > lat_dev_max: lat_dev_max = abs(dev)
            hist.append((round(tt, 2), round(dev, 3), round(abs(cs.vEgo), 1), round(getattr(cst, "curvature", 0.0) if cst is not None else 0.0, 5)))
            if len(hist) > 6000: hist.pop(0)
    # enrich
    for e in events:
        h1 = near(hist, e["t"], -1.0); h2 = near(hist, e["t"], -2.0); h0 = near(hist, e["t"], 0.0)
        e["dev_1s"] = h1[1] if h1 else None
        e["dev_2s"] = h2[1] if h2 else None
        e["dev_at"] = h0[1] if h0 else e["dev"]
        if h1 and h2:
            rate = (h1[1] - h2[1]) / 1.0
            e["rate_per_s"] = round(rate, 2)
            d = e["dev_at"] if e["dev_at"] is not None else 0.0
            if rate < 0 and d < 0:
                e["t_cross_s"] = round((1.0 - abs(d)) / abs(rate), 2) if abs(rate) > 1e-6 else None
            elif rate > 0 and d > 0:
                e["t_cross_s"] = round((1.0 - abs(d)) / abs(rate), 2) if abs(rate) > 1e-6 else None
    tc = [e["t_cross_s"] for e in events if e.get("t_cross_s") is not None and e["t_cross_s"] >= 0]
    return {"seg": name.split("--")[-1], "model": n_model, "valid": valid, "rej_prob": rej_prob, "rej_width": rej_width,
            "blind_after_near_line": blind, "lat_dev_max": round(lat_dev_max, 2),
            "n_driver_steer": sum(1 for e in events if e["kind"] == "driver_steer"),
            "n_lat_off": sum(1 for e in events if e["kind"] == "lat_off"),
            "tc_min": round(min(tc), 2) if tc else None, "tc_lt1": sum(1 for x in tc if x < 1.0), "tc_lt2": sum(1 for x in tc if x < 2.0),
            "events": sorted([e for e in events if e.get("t_cross_s") is not None and e["t_cross_s"] < 2.0], key=lambda x: x["t_cross_s"])[:6]}

prefix = sys.argv[1]
out = []
for r in sys.argv[2:]:
    name = prefix + r
    if not os.path.exists(name + "/rlog.zst"): continue
    try: out.append(analyze(name))
    except Exception as e: out.append({"seg": r, "err": str(e)[:130]})
print(json.dumps(out, ensure_ascii=False))