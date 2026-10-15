# -*- coding: utf-8 -*-
"""第 4 轮(2)：车道变更（自动变道/转向灯变道）到底有没有被触发 —— 直接对应"老是转到旁边车道去"""
import sys, os
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"
for r in ["3", "4", "5", "6", "9", "10", "11"]:
    p = BASE + r + "/qlog.zst"
    if not os.path.exists(p): continue
    lc_states = {}; lc_dirs = {}; probs = []
    blink_lr = [0, 0]; n = 0
    for m in LogReader(p):
        n += 1
        w = m.which()
        if w == "lateralPlanDEPRECATED":
            lp = m.lateralPlanDEPRECATED
            st = str(getattr(lp, "laneChangeState", "?"))
            lc_states[st] = lc_states.get(st, 0) + 1
            d = str(getattr(lp, "laneChangeDirection", "?"))
            if st not in ("off", "?"): lc_dirs[d] = lc_dirs.get(d, 0) + 1
            pb = getattr(lp, "laneChangeProb", None)
            if pb is not None: probs.append(pb)
        elif w == "carState":
            cs = m.carState
            if getattr(cs, "leftBlinker", False): blink_lr[0] += 1
            if getattr(cs, "rightBlinker", False): blink_lr[1] += 1
    print("--%-3s laneChangeState %s | 触发方向 %s | prob max %.3f | 转向灯帧 L/R %s" % (
        r, lc_states, lc_dirs, max(probs) if probs else 0, blink_lr))
