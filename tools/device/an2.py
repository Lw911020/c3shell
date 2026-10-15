# -*- coding: utf-8 -*-
"""第 2 轮：① 实时下线相关状态 ② 给全部路段分类（真开过 / 只是停着）"""
import sys, os, glob, time
sys.path.insert(0, "/data/openpilot")

# ---------- ① 实时状态 ----------
try:
    import cereal.messaging as messaging
    sm = messaging.SubMaster(["pandaStates", "deviceState", "carState", "selfdriveState", "managerState"])
    t0 = time.time()
    while time.time() - t0 < 2.5:
        sm.update(100)
    ps = sm["pandaStates"]
    print("== 实时 ==")
    print(" 车是否在写日志（onroad 判据）: deviceState.started=%s thermal=%s" % (
        getattr(sm["deviceState"], "started", "?"), getattr(sm["deviceState"], "thermalStatus", "?")))
    try:
        for i, p in enumerate(ps[:2]):
            print(" panda[%d] ignitionLine=%s ignitionCan=%s controlsAllowed=%s safetyModel=%s" % (
                i, getattr(p, "ignitionLine", "?"), getattr(p, "ignitionCan", "?"),
                getattr(p, "controlsAllowed", "?"), getattr(p, "safetyModel", "?")))
    except Exception as e:
        print(" panda 读失败:", e)
    cs = sm["carState"]
    print(" carState: vEgo=%.2f gear=%s standstill=%s brake=%s gas=%.2f" % (
        cs.vEgo, str(getattr(cs, "gearShifter", "?")), getattr(cs, "standstill", "?"),
        getattr(cs, "brakePressed", "?"), getattr(cs, "gas", 0.0)))
    ss = sm["selfdriveState"]
    print(" selfdriveState: enabled=%s state=%s alert=%s" % (
        ss.enabled, ss.state, (getattr(ss, "alertText1", "") or "")[:40]))
except Exception as e:
    print("实时读取失败:", type(e).__name__, e)

# ---------- ② 全部路段分类 ----------
print("\n== 路段分类（读每个 qlog 直到看到 vEgo>5 或读完）==")
from tools.lib.logreader import LogReader
rows = []
for r in sorted(glob.glob("/data/media/0/realdata/0000000c--32cbec9ac8--*"),
                key=lambda p: (os.path.basename(p).split("--")[-1].zfill(4))):
    q = os.path.join(r, "qlog.zst")
    if not os.path.exists(q): continue
    vmax = 0.0; n = 0; dur = 0.0; first = last = None
    try:
        for m in LogReader(q):
            n += 1
            if first is None: first = m.logMonoTime
            last = m.logMonoTime
            if m.which() == "carState":
                v = abs(m.carState.vEgo)
                if v > vmax: vmax = v
                if vmax > 5: break
    except Exception:
        pass
    dur = (last - first) / 1e9 if first and last else 0
    idx = os.path.basename(r).split("--")[-1]
    rows.append((idx, vmax, dur, n, time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(r)))))
drv = [x for x in rows if x[1] > 5]
park = [x for x in rows if x[1] <= 5]
print(" 总 %d 段：真开过 %d 段，停着 %d 段" % (len(rows), len(drv), len(park)))
print(" 最近的「真开过」路段（路段号 / 最高车速 m/s / 时长s / 消息数 / 文件时间）:")
for x in drv[-8:]:
    print("   --%s  vmax=%.1f  dur=%.0fs  n=%d  %s" % x)
print(" 最近的「停着」路段:")
for x in park[-5:]:
    print("   --%s  vmax=%.1f  dur=%.0fs  n=%d  %s" % x)
