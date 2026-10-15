# -*- coding: utf-8 -*-
"""第 5 轮：搞清信号量纲与真实控制状态（MADS / latActive / 时间序列）"""
import sys, os
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"

for r in ["3", "9"]:
    q = os.path.join(BASE + r, "qlog.zst")
    print("\n===== 路段 --%s 时间序列（每约 2 秒一行）=====" % r)
    rows = []; last = None
    mads = {"active": 0, "n": 0}
    lat_act = []; lat_avail = []
    st = {}
    try:
        for m in LogReader(q):
            w = m.which()
            if w == "carState":
                cs = m.carState
                st.update(t=m.logMonoTime / 1e9, v=cs.vEgo, gear=str(cs.gearShifter),
                          ang=getattr(cs, "steeringAngleDeg", 0.0),
                          tqDrv=getattr(cs, "steeringTorque", 0.0),
                          tqEps=getattr(cs, "steeringTorqueEps", 0.0),
                          pressed=getattr(cs, "steeringPressed", False),
                          brake=getattr(cs, "brakePressed", False), gas=getattr(cs, "gas", 0.0))
            elif w == "carControl":
                try:
                    st["latActive"] = bool(m.carControl.latActive)
                    st["enabled"] = bool(m.carControl.enabled)
                    st["tau"] = m.carControl.actuators.torque
                    st["latReq"] = m.carControl.latAccel
                except Exception: pass
            elif w == "controlsState":
                try: st["curv"] = m.controlsState.desiredCurvature if hasattr(m.controlsState, "desiredCurvature") else 0.0
                except Exception: pass
            elif w == "selfdriveStateSP":
                try:
                    mm = m.selfdriveStateSP.mads
                    mads["n"] += 1
                    if mm.active: mads["active"] += 1
                    st["mads"] = "%s/%s" % (str(mm.state), bool(mm.active))
                except Exception: pass
            elif w == "liveParameters":
                try: st["sr"] = m.liveParameters.steerRatio; st["stiff"] = m.liveParameters.stiffnessFactor; st["ao"] = m.liveParameters.angleOffset
                except Exception: pass
            elif w == "liveTorqueParameters":
                try: st["latAF"] = m.liveTorqueParameters.latAccelFactorFiltered; st["fric"] = m.liveTorqueParameters.frictionCoefficientFiltered; st["tqOK"] = m.liveTorqueParameters.valid
                except Exception: pass
            if "v" in st and (last is None or st["t"] - last >= 2.0):
                last = st["t"]; rows.append(dict(st))
    except Exception as e:
        print(" 解析中断:", type(e).__name__, e)
    print(" MADS: active 占比 %.0f%%（%d/%d）" % (100.0 * mads["active"] / mads["n"] if mads["n"] else 0, mads["active"], mads["n"]))
    print(" %-7s %-6s %-6s %-8s %-8s %-8s %-7s %-8s %s" % ("t", "v", "gear", "angle°", "τ_cmd", "τ_eps", "latReq", "latAct", "mads"))
    for x in rows[:26]:
        print(" %-7.1f %-6.1f %-6s %-8.1f %-8.3f %-8.1f %-7.2f %-8s %s" % (
            x.get("t", 0), x.get("v", 0), x.get("gear", "?")[:5], x.get("ang", 0), x.get("tau", 0),
            x.get("tqEps", 0), x.get("latReq", 0), x.get("latActive", "?"), x.get("mads", "-")))
    print(" steerRatio=%s stiffness=%s angleOffset=%s | 学到的 latAccelFactor=%s friction=%s valid=%s" % (
        round(st.get("sr", 0), 3), round(st.get("stiff", 0), 3), round(st.get("ao", 0), 3),
        round(st.get("latAF", 0), 4), round(st.get("fric", 0), 4), st.get("tqOK")))
