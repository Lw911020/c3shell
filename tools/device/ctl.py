# -*- coding: utf-8 -*-
"""第 4 轮(1)：确认行车时到底用哪套横向控制器 + 生效参数（防止前几轮结论错位）"""
import sys, os
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"

for r in ["6", "3"]:
    p = BASE + r + "/qlog.zst"
    kinds = {}
    sample = {}
    cp_info = {}
    for m in LogReader(p):
        w = m.which()
        if w == "controlsState":
            cs = m.controlsState
            try:
                k = cs.lateralControlState.which()
            except Exception:
                k = "?"
            kinds[k] = kinds.get(k, 0) + 1
            if k not in sample:
                try:
                    sample[k] = cs.lateralControlState.to_dict()
                except Exception as e:
                    sample[k] = {"err": str(e)}
        elif w == "carParams" and not cp_info:
            cp = m.carParams
            cp_info = {"fingerprint": cp.carFingerprint, "brand": str(cp.brand),
                       "tuning": cp.lateralTuning.which()}
            try:
                if cp.lateralTuning.which() == "torque":
                    t = cp.lateralTuning.torque
                    cp_info["torque"] = {"kp": t.kp, "ki": t.ki, "kf": t.kf, "friction": round(t.friction, 4),
                                         "latAccelFactor": round(t.latAccelFactor, 4), "offset": round(t.latAccelOffset, 4),
                                         "deadzone": getattr(t, "steeringAngleDeadzoneDeg", None)}
                elif cp.lateralTuning.which() == "pid":
                    p2 = cp.lateralTuning.pid
                    cp_info["pid"] = {"kpV": list(p2.kpV), "kpBP": list(p2.kpBP), "kiV": list(p2.kiV), "kf": p2.kf}
            except Exception as e:
                cp_info["err"] = str(e)
    print("\n== 路段 --%s ==" % r)
    print("   lateralControlState 分布:", kinds)
    for k, v in sample.items():
        keep = {kk: vv for kk, vv in v.items() if kk in ("active", "saturated", "p", "i", "f", "output", "error",
                                                          "actualLateralAccel", "desiredLateralAccel", "steeringAngleDeadzoneDeg")}
        print("   %s 样例: %s" % (k, keep))
    print("   CarParams:", cp_info)
