# -*- coding: utf-8 -*-
"""第 6 轮：① CAN 溢出/CAN 负载 ② 闭环学习曲线（torque/pose 参数随路段的变化）"""
import sys, os, time
sys.path.insert(0, "/data/openpilot")

print("=== ① panda 接收溢出：10 秒增量 ===")
try:
    import cereal.messaging as messaging
    sm = messaging.SubMaster(["pandaStates"])
    def snap():
        t0 = time.time()
        while time.time() - t0 < 1.0:
            sm.update(100)
        p = list(sm["pandaStates"])[0]
        return (getattr(p, "rxBufferOverflow", -1), getattr(p, "txBufferOverflow", -1),
                getattr(p, "canReceiveErrorCount", -1), getattr(p, "canSendErrorCount", -1))
    a = snap(); time.sleep(10); b = snap()
    print("  rxOverflow %s → %s（10 秒 +%s）  txOverflow %s → %s" % (a[0], b[0], b[0]-a[0], a[1], b[1]))
    print("  canRxErr %s → %s   canTxErr %s → %s" % (a[2], b[2], a[3], b[3]))
except Exception as e:
    print("  panda 读失败:", type(e).__name__, e)

print("\n=== ② 闭环学习曲线：逐路段最后的 liveTorqueParameters / liveParameters ===")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"
print("  路段   latAccelFactor  friction  steerRatio  stiffness  angleOffset  有效点数")
for r in ["3", "5", "6", "9", "11", "26", "31", "38"]:
    p = os.path.join(BASE + r, "qlog.zst")
    if not os.path.exists(p):
        continue
    lt = {}; lp = {}
    for m in LogReader(p):
        w = m.which()
        if w == "liveTorqueParameters":
            x = m.liveTorqueParameters
            lt = {"latAF": getattr(x, "latAccelFactorFiltered", 0.0), "fric": getattr(x, "frictionCoefficientFiltered", 0.0),
                  "pts": getattr(x, "totalBucketPoints", 0), "valid": getattr(x, "valid", None)}
        elif w == "liveParameters":
            y = m.liveParameters
            lp = {"sr": getattr(y, "steerRatio", 0.0), "stiff": getattr(y, "stiffnessFactor", 0.0),
                  "ao": getattr(y, "angleOffset", 0.0)}
    print("  --%-4s %-14.4f %-9.4f %-11.3f %-10.3f %-11.3f %s" % (
        r, lt.get("latAF", 0), lt.get("fric", 0), lp.get("sr", 0), lp.get("stiff", 0), lp.get("ao", 0), lt.get("pts", 0)))

print("\n=== ② CAN 负载（最近一条行驶路段，按总线统计帧率）===")
p = os.path.join(BASE + "6", "qlog.zst")
if os.path.exists(p):
    from collections import Counter
    per_bus = Counter(); addrs = Counter(); t0 = None; t1 = None
    for m in LogReader(p):
        if m.which() == "can":
            for c in m.can:
                per_bus[c.src] += 1
                addrs[(c.src, c.address)] += 1
            if t0 is None: t0 = m.logMonoTime
            t1 = m.logMonoTime
    dur = (t1 - t0) / 1e9 if t0 and t1 else 1
    print("  时长 %.0fs  各总线帧数/帧率: %s" % (dur, {k: "%d (%.0f/s)" % (v, v/dur) for k, v in per_bus.items()}))
    print("  最忙的 5 个报文:", addrs.most_common(5))
