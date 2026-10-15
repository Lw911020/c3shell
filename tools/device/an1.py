# -*- coding: utf-8 -*-
"""最近行车记录分析（第 1 轮）：先探 schema，再出摘要"""
import sys, os, glob, time, statistics as st
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader

ROUTES = sorted(glob.glob("/data/media/0/realdata/0000000c--32cbec9ac8--*"),
                key=lambda p: os.path.getmtime(p))[-3:]
print("分析路段:", [os.path.basename(r) for r in ROUTES])

CUSTOM = ["carStateSP", "selfdriveStateSP", "carControlSP", "onroadEventsSP", "longitudinalPlanSP", "liveMapDataSP"]
seen_custom = {}

def keys_of(msg):
    try:
        d = msg.to_dict()
        d.pop("logMonoTime", None); d.pop("valid", None)
        return d
    except Exception as e:
        return {"<err>": str(e)}

for r in ROUTES[-1:]:
    q = os.path.join(r, "qlog.zst")
    if not os.path.exists(q):
        continue
    for m in LogReader(q):
        w = m.which()
        if w in CUSTOM and w not in seen_custom:
            seen_custom[w] = keys_of(m)
            print("\n== %s 字段 ==\n%s" % (w, str(seen_custom[w])[:600]))

print("\n===== 每条路段摘要 =====")
for r in ROUTES:
    q = os.path.join(r, "qlog.zst")
    if not os.path.exists(q):
        continue
    t0 = t1 = None
    n = 0
    vmax = 0.0; vsum = 0.0; vn = 0
    eng_t = 0.0; tot_t = 0.0
    torque = []; angle = []; latacc = []
    alerts = {}
    evs = {}
    lane_ch = 0
    last = {}
    prev_t = None
    try:
        for m in LogReader(q):
            n += 1
            t = m.logMonoTime
            if t0 is None: t0 = t
            t1 = t
            w = m.which()
            if w == "carState":
                cs = m.carState
                v = abs(cs.vEgo)
                vmax = max(vmax, v); vsum += v; vn += 1
                angle.append(getattr(cs, "steeringAngleDeg", 0.0))
                last["v"] = v; last["gear"] = str(cs.gearShifter)
                last["press"] = bool(getattr(cs, "steeringPressed", False))
                last["ign"] = None
                if getattr(cs, "leftBlinker", False) or getattr(cs, "rightBlinker", False):
                    last["blink"] = True
            elif w == "carControl":
                try:
                    torque.append(m.carControl.actuators.torque)
                    latacc.append(m.carControl.latAccel)
                except Exception:
                    pass
            elif w == "selfdriveState":
                ss = m.selfdriveState
                enabled = bool(ss.enabled)
                last["en"] = enabled
                if prev_t is not None:
                    tot_t += (t - prev_t) / 1e9
                    if last.get("_en"): eng_t += (t - prev_t) / 1e9
                last["_en"] = enabled
                a1 = getattr(ss, "alertText1", "") or ""
                if a1: alerts[a1] = alerts.get(a1, 0) + 1
            elif w == "onroadEvents":
                for e in m.onroadEvents:
                    evs[e.name] = evs.get(e.name, 0) + 1
            elif w == "selfdriveStateSP":
                if getattr(m.selfdriveStateSP, "laneChangeState", 0) not in (0, "off", None):
                    lane_ch += 1
            prev_t = t
    except Exception as e:
        print(" 解析中断:", type(e).__name__, e)
    dur = (t1 - t0) / 1e9 if t0 else 0
    print("\n-- %s" % os.path.basename(r))
    print("   消息 %d · 时长 %.0fs · 最高 %.1f m/s · 平均 %.1f m/s · 解除占比 %.0f%%" % (
        n, dur, vmax, (vsum / vn if vn else 0), 100 * (1 - eng_t / tot_t) if tot_t else 0))
    if torque:
        print("   扭矩 torque: min %.3f  max %.3f  p95 %.3f |latAccel| p95 %.2f" % (
            min(torque), max(torque), sorted(map(abs, torque))[int(0.95 * len(torque))], 
            sorted(map(abs, latacc))[int(0.95 * len(latacc))] if latacc else 0))
    if angle:
        print("   方向盘角度: 最大 %.1f° · p95 %.1f°" % (max(map(abs, angle)), sorted(map(abs, angle))[int(0.95 * len(angle))]))
    print("   laneChange 相关消息 %d · 结尾状态 v=%.1f gear=%s en=%s" % (
        lane_ch, last.get("v", -1), last.get("gear", "?"), last.get("_en", "?")))
    top_a = sorted(alerts.items(), key=lambda kv: -kv[1])[:5]
    top_e = sorted(evs.items(), key=lambda kv: -kv[1])[:6]
    print("   提示 Top:', %s" % top_a)
    print("   事件 Top:', %s" % top_e)
