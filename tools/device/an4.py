# -*- coding: utf-8 -*-
"""第 4 轮：真开过的路段做横向深挖（急弯力矩 / 是否压到旁边车道）"""
import sys, os, glob, math
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

DRV = ["3", "4", "5", "6", "9", "10", "11"]
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"

# 先看两个自定义消息的字段（便于后面取值）
def schema(route, which, limit=1):
    q = os.path.join(BASE + route, "qlog.zst")
    n = 0
    for m in LogReader(q):
        if m.which() == which:
            d = m.to_dict(); d.pop("logMonoTime", None); d.pop("valid", None)
            print("   %s → %s" % (which, str(d)[:420]))
            n += 1
            if n >= limit: break

print("== 自定义消息字段抽样（--9）==")
for w in ["selfdriveStateSP", "carStateSP", "carControlSP", "driverAssistance", "onroadEventsSP"]:
    try: schema("9", w)
    except Exception as e: print("   %s 取样失败: %s" % (w, e))

print("\n== 各路段横向统计 ==")
for r in DRV:
    q = os.path.join(BASE + r, "qlog.zst")
    if not os.path.exists(q):
        print("--%s 无 qlog" % r); continue
    n = 0; t0 = t1 = None; en_t = tot_t = 0.0; prev = None
    vmax = 0.0; vsum = 0; vn = 0
    tq = []; ang = []; lat = []; lat_req = []
    tq_hi = []          # |角度| > 25° 时的扭矩
    alerts = {}; evs = {}; evsp = {}
    blink = 0; lc_states = {}
    st = {}
    try:
        for m in LogReader(q):
            n += 1; t = m.logMonoTime
            if t0 is None: t0 = t
            t1 = t
            w = m.which()
            if w == "carState":
                cs = m.carState
                v = abs(cs.vEgo); vmax = max(vmax, v); vsum += v; vn += 1
                a = abs(getattr(cs, "steeringAngleDeg", 0.0)); ang.append(a)
                st["v"] = v; st["gear"] = str(cs.gearShifter)
                if getattr(cs, "leftBlinker", False) or getattr(cs, "rightBlinker", False): blink += 1
            elif w == "carControl":
                try:
                    tau = m.carControl.actuators.torque
                    tq.append(tau)
                    if ang and ang[-1] > 25: tq_hi.append(abs(tau))
                    lat_req.append(m.carControl.latAccel)
                except Exception: pass
            elif w == "selfdriveState":
                ss = m.selfdriveState
                en = bool(ss.enabled)
                if prev is not None:
                    tot_t += (t - prev) / 1e9
                    if st.get("_en"): en_t += (t - prev) / 1e9
                prev = t; st["_en"] = en
                a1 = (getattr(ss, "alertText1", "") or "").strip()
                if a1: alerts[a1] = alerts.get(a1, 0) + 1
            elif w == "onroadEvents":
                for e in m.onroadEvents: evs[str(e.name)] = evs.get(str(e.name), 0) + 1
            elif w == "onroadEventsSP":
                try:
                    for e in m.onroadEventsSP: evsp[str(e.name)] = evsp.get(str(e.name), 0) + 1
                except Exception: pass
            elif w == "selfdriveStateSP":
                try:
                    v = getattr(m.selfdriveStateSP, "laneChangeState", None)
                    if v is not None: lc_states[str(v)] = lc_states.get(str(v), 0) + 1
                except Exception: pass
            elif w == "controlsState":
                try: lat.append(m.controlsState.curvature if hasattr(m.controlsState, "curvature") else 0.0)
                except Exception: pass
    except Exception as e:
        print("--%s 解析中断: %s %s" % (r, type(e).__name__, e))
    dur = (t1 - t0) / 1e9 if t0 else 0
    def p95(xs):
        if not xs: return 0.0
        s = sorted(xs); return s[min(len(s) - 1, int(0.95 * len(s)))]
    print("\n--%s 消息%d 时长%.0fs 最高%.1fm/s 平均%.1f 接管时en占%.0f%%" % (
        r, n, dur, vmax, (vsum / vn if vn else 0), 100 * en_t / tot_t if tot_t else 0))
    print("   扭矩 |τ|: max %.3f p95 %.3f · 大角度(|ang|>25°) |τ| p95 %.3f (样本 %d)" % (
        max(map(abs, tq)) if tq else 0, p95(list(map(abs, tq))), p95(tq_hi), len(tq_hi)))
    print("   请求 latAccel: p95 %.2f max %.2f | 方向盘角度 p95 %.1f° max %.1f°" % (
        p95(list(map(abs, lat_req))), max(map(abs, lat_req)) if lat_req else 0, p95(ang), max(ang) if ang else 0))
    print("   转向灯帧 %d · laneChangeState 分布 %s" % (blink, lc_states))
    print("   结尾 v=%.1f gear=%s en=%s" % (st.get("v", -1), st.get("gear", "?"), st.get("_en", "?")))
    print("   提示 Top5: %s" % sorted(alerts.items(), key=lambda x: -x[1])[:5])
    print("   事件 Top5: %s" % sorted(evs.items(), key=lambda x: -x[1])[:5])
    if evsp: print("   SP 事件 Top5: %s" % sorted(evsp.items(), key=lambda x: -x[1])[:5])
