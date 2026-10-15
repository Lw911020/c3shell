#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crosswatch.py — 「预测压线」守望（只读，不干预控制）

为什么需要它：modelV2 车道线在紧弯里会丢（实测段 32-40 有 62%~100% 的帧没线），
而驾驶员每次都在压线前把车拉回来 —— 于是「压线次数」永远统计不到。
本脚本同时记两路信号，给驾驶员拉回的那一瞬间做「反事实」取证：
  A. 车道线几何（有线时）：dev = 车道中心偏移/半车道宽，|dev|=1 即压线；
  B. 控制器自身误差（永远有）：Δa = 期望横向加速度 - 实际横向加速度（torqueState），
     outward = Δa × sign(κ) > 0 表示「朝弯外少给了」→ 偏移会继续长大。
用法: cd /data/openpilot && /usr/local/venv/bin/python3 .dsh/crosswatch.py [秒数=1800]
输出: /data/openpilot/.dsh/crosswatch-<UTC>.csv / .events.jsonl / .live.jsonl
"""
import sys, os, time, json, csv
os.chdir("/data/openpilot")
sys.path.insert(0, "/data/openpilot")
import cereal.messaging as messaging

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 1800.0
stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
outdir = "/data/openpilot/.dsh"
csvf = open(outdir + "/crosswatch-" + stamp + ".csv", "w", newline="")
evf = open(outdir + "/crosswatch-" + stamp + ".events.jsonl", "w")
livf = open(outdir + "/crosswatch-" + stamp + ".live.jsonl", "w")
w = csv.writer(csvf)
w.writerow(["t", "v", "kappa_des", "kappa_act", "dev", "leftY", "rightY", "lp", "rp", "a_des", "a_act", "a_out", "tau", "sat", "lat", "pressed", "blink"])

sm = messaging.SubMaster(["carState", "carControl", "controlsState", "modelV2", "driverAssistance", "selfdriveState"], poll="carState")
hist = []          # (t, dev) 最近 1.5 s
events = 0; maxdev = 0.0; min_tcross = None; n_frames = 0; last_sum = 0.0
t0 = time.monotonic()
prev_pressed = False; prev_lat = None
last_dev = None
while time.monotonic() - t0 < DUR:
    sm.update(10)
    if not sm.updated["modelV2"]:
        continue
    try:
        cs = sm["carState"]; cc = sm["carControl"]; cst = sm["controlsState"]; mv = sm["modelV2"]
    except Exception:
        continue
    t = round(time.monotonic() - t0, 2)
    v = abs(cs.vEgo); kappa = float(cst.curvature)
    try:
        ts = cst.lateralControlState.torqueState
        a_des = float(ts.desiredLateralAccel); a_act = float(ts.actualLateralAccel)
        tau = float(ts.output); sat = bool(ts.saturated)
    except Exception:
        a_des = a_act = tau = 0.0; sat = False
    a_out = (a_des - a_act) * (1.0 if kappa > 0 else -1.0)
    try:
        kappa_act = float(cs.yawRate) / max(v, 1.0)
    except Exception:
        kappa_act = 0.0
    dev = None; yl = yr = lp = rp = 0.0
    try:
        probs = mv.laneLineProbs; lp = float(probs[1]); rp = float(probs[2])
        yl = float(mv.laneLines[1].y[0]); yr = float(mv.laneLines[2].y[0])
        width = yr - yl
        if lp > 0.5 and rp > 0.5 and 1.2 < width < 6.5:
            dev = ((yl + yr) / 2.0) / (width / 2.0)
    except Exception:
        pass
    lat = bool(cc.latActive); pressed = bool(cs.steeringPressed)
    blink = bool(cs.leftBlinker or cs.rightBlinker)
    n_frames += 1
    w.writerow([t, round(v, 2), round(kappa, 5), round(kappa_act, 5),
                "" if dev is None else round(dev, 3), round(yl, 2), round(yr, 2), round(lp, 2), round(rp, 2),
                round(a_des, 3), round(a_act, 3), round(a_out, 3), round(tau, 3), int(sat), int(lat), int(pressed), int(blink)])
    if dev is not None:
        last_dev = dev
        if abs(dev) > maxdev: maxdev = abs(dev)
        hist.append((t, dev))
        hist = [h for h in hist if t - h[0] <= 1.5]
    # 向外漂移速率（用最近 1.5 s 内的首末差）
    rate = None; tcross = None
    if len(hist) >= 3 and last_dev is not None:
        dt = hist[-1][0] - hist[0][0]
        if dt > 0.3:
            rate = (hist[-1][1] - hist[0][1]) / dt
            moving_out = (rate > 0 and last_dev > 0) or (rate < 0 and last_dev < 0)
            if moving_out and abs(rate) > 0.05:
                tcross = max(0.0, (1.0 - abs(last_dev)) / abs(rate))
                if min_tcross is None or tcross < min_tcross: min_tcross = tcross
    # 驾驶员接管（OP 在控时打方向 / 退控）
    intervention = (pressed and not prev_pressed and lat) or (prev_lat is True and not lat and v > 5)
    prev_pressed = pressed; prev_lat = lat
    if intervention or (tcross is not None and tcross < 1.5):
        events += 1
        ev = {"t": t, "v": round(v, 2), "dev": None if last_dev is None else round(last_dev, 3),
              "dev_rate_per_s": None if rate is None else round(rate, 3), "t_cross_s": None if tcross is None else round(tcross, 2),
              "kappa_des": round(kappa, 5), "a_des": round(a_des, 3), "a_act": round(a_act, 3), "a_out": round(a_out, 3),
              "tau": round(tau, 3), "saturated": sat, "latActive": lat, "pressed": pressed, "blinker": blink,
              "why": "driver_steer" if (pressed and not prev_pressed and lat) else ("lat_off" if (prev_lat is not None and not lat and v > 5) else "predicted_cross"),
              "traj": [[round(h[0], 2), round(h[1], 3)] for h in hist[-12:]]}
        evf.write(json.dumps(ev, ensure_ascii=False) + "\n"); evf.flush()
        print("EVENT " + json.dumps(ev, ensure_ascii=False), flush=True)
    if t - last_sum >= 5.0:
        last_sum = t
        liv = {"t": t, "v": round(v, 2), "dev": None if last_dev is None else round(last_dev, 3),
               "a_out": round(a_out, 3), "tau": round(tau, 3), "sat": sat, "lat": lat, "pressed": pressed,
               "events": events, "maxdev": round(maxdev, 3), "min_tcross": None if min_tcross is None else round(min_tcross, 2),
               "frames": n_frames}
        livf.write(json.dumps(liv) + "\n"); livf.flush()
        print("LIVE " + json.dumps(liv), flush=True)
csvf.close(); evf.close(); livf.close()
print("done frames=%d events=%d maxdev=%.3f" % (n_frames, events, maxdev))