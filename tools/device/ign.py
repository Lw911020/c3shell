# -*- coding: utf-8 -*-
"""点火线 vs CAN 点火：行车时/停车时分别是什么？（决定能否用 ignitionCan 替代）"""
import sys, os
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
BASE = "/data/media/0/realdata/0000000c--32cbec9ac8--"
for r in ["3", "4", "9", "11", "26", "31"]:
    q = os.path.join(BASE + r, "qlog.zst")
    if not os.path.exists(q):
        print("--%s 无" % r); continue
    v = 0.0
    stat = {}
    n = 0
    try:
        for m in LogReader(q):
            n += 1
            w = m.which()
            if w == "carState":
                v = abs(m.carState.vEgo)
            elif w == "pandaStates":
                for p in m.pandaStates:
                    key = ("开动" if v > 1.0 else "静止", bool(p.ignitionLine), bool(p.ignitionCan))
                    stat[key] = stat.get(key, 0) + 1
    except Exception as e:
        print("--%s 解析中断 %s" % (r, e))
    print("\n--%s (消息 %d)" % (r, n))
    for k in sorted(stat, key=lambda x: -stat[x])[:6]:
        print("   %s  点火线=%-5s CAN点火=%-5s  帧数 %d" % (k[0], k[1], k[2], stat[k]))
