# -*- coding: utf-8 -*-
"""横向报告（A/B 基线用）：逐路段统计扭矩饱和 / 低速大角度 / 压线 / 角度速率
用法：cd /data/openpilot && /usr/local/venv/bin/python3 .dsh/lat_report.py [路段号...]
"""
import sys, os, json, glob
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"
routes = sys.argv[1:]
# 2026-09-26：不带参数 → 自动取最新 10 段
if not routes:
    import glob as _g
    _all = sorted(_g.glob(BASE + '*'), key=lambda p: int(p.split('--')[-1]) if p.split('--')[-1].isdigit() else -1)
    routes = [p.split('--')[-1] for p in _all[-10:]]
out = {}
for r in routes:
    p = BASE + r + "/qlog.zst"
    if not os.path.exists(p):
        continue
    v = 0.0; ang = 0.0; rate = 0.0; tau = 0.0
    n = 0; sat = 0; sat_low = 0; sat_hi_ang = 0; ratemax = 0.0
    dep_l = dep_r = 0; tau_abs_sum = 0.0; tau_n = 0
    for m in LogReader(p):
        n += 1
        w = m.which()
        if w == "carState":
            cs = m.carState
            v = abs(cs.vEgo); ang = getattr(cs, "steeringAngleDeg", 0.0); rate = getattr(cs, "steeringRateDeg", 0.0)
        elif w == "carControl":
            try:
                tau = m.carControl.actuators.torque
                tau_abs_sum += abs(tau); tau_n += 1
            except Exception:
                continue
        elif w == "driverAssistance":
            dep_l += 1 if getattr(m.driverAssistance, "leftLaneDeparture", False) else 0
            dep_r += 1 if getattr(m.driverAssistance, "rightLaneDeparture", False) else 0
        if tau_n and abs(tau) > 0.95:
            sat += 1
            if v < 5: sat_low += 1
            if abs(ang) > 25: sat_hi_ang += 1
            ratemax = max(ratemax, abs(rate))
    out[r] = {"frames": n, "sat": sat, "sat_low_speed": sat_low, "sat_big_angle": sat_hi_ang,
              "mean_abs_torque": round(tau_abs_sum / tau_n, 4) if tau_n else 0,
              "max_abs_steer_rate": ratemax, "lane_departure_lr": [dep_l, dep_r]}
print(json.dumps(out, ensure_ascii=False, indent=1))
