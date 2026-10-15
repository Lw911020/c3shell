# -*- coding: utf-8 -*-
"""第 7 轮：用真实数据量化"低速项"对手感的贡献（预测 LOW_SPEED_Y 补丁的效果）"""
import sys, os, math
import numpy as np
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"
LSX = [0, 10, 20, 30]

def lsf(v, Y):
    return float(np.interp(v, LSX, Y)) ** 2

for r in ["6", "3", "9"]:
    p = BASE + r + "/qlog.zst"
    if not os.path.exists(p): continue
    v = 0.0; dc = 0.0; tau = 0.0
    cur_term = []; new_term = []; base_term = []; ratio = []
    sat_cur = []; sat_new = []; n_sat = 0; n = 0
    for m in LogReader(p):
        w = m.which(); n += 1
        if w == "carState":
            v = abs(m.carState.vEgo)
        elif w == "controlsState":
            dc = getattr(m.controlsState, "desiredCurvature", 0.0)
        elif w == "carControl":
            try: tau = m.carControl.actuators.torque
            except Exception: continue
            if abs(tau) > 0.95:
                n_sat += 1
                t_now = lsf(v, [15, 13, 10, 5]) * dc
                t_new = lsf(v, [8, 7, 6, 4]) * dc
                b = (v ** 2) * dc
                cur_term.append(abs(t_now)); new_term.append(abs(t_new)); base_term.append(abs(b))
                if abs(b) > 1e-9: ratio.append(abs(t_now) / abs(b))
    def med(x): return float(np.median(x)) if x else 0.0
    print("--%-3s 饱和帧 %-5d  | 中位数: 低速项(现)=%.4f  低速项(补丁后)=%.4f  基座 v²·dc=%.4f" % (
        r, n_sat, med(cur_term), med(new_term), med(base_term)))
    if ratio:
        print("        低速项 / 基座 的倍数（中位）: %.1f 倍 → 补丁后 %.1f 倍（降 %.0f%%）" % (
            med(ratio), med(ratio) * (med(new_term) / med(cur_term) if med(cur_term) else 0),
            100 * (1 - (med(new_term) / med(cur_term) if med(cur_term) else 1))))
    # 全帧统计：低速项占 setpoint 的比例
    print("        补丁把低速项整体砍掉 %.0f%%（[15,13,10,5]→[8,7,6,4]，平方后 225→64）" % (100 * (1 - (8/15.0) ** 2)))
