# -*- coding: utf-8 -*-
import sys, time, os
sys.path.insert(0, "/data/openpilot")
import cereal.messaging as messaging
sm = messaging.SubMaster(["pandaStates", "deviceState", "carState", "selfdriveState", "selfdriveStateSP", "managerState"])
t0 = time.time()
while time.time() - t0 < 2.5:
    sm.update(100)
print("deviceState.started =", getattr(sm["deviceState"], "started", "?"))
try:
    ps_list = list(sm["pandaStates"])
    print("pandaStates 个数 =", len(ps_list))
    for i, p in enumerate(ps_list):
        print("  [%d] type=%s ignitionLine=%s ignitionCan=%s controlsAllowed=%s voltage=%.2fV current=%.0fmA" % (
            i, str(getattr(p, "pandaType", "?")), getattr(p, "ignitionLine", "?"), getattr(p, "ignitionCan", "?"),
            getattr(p, "controlsAllowed", "?"), getattr(p, "voltage", 0) / 1000.0, getattr(p, "current", 0)))
except Exception as e:
    print("panda 读失败:", type(e).__name__, e)
cs = sm["carState"]
print("carState: vEgo=%.2f gear=%s standstill=%s" % (cs.vEgo, str(getattr(cs, "gearShifter", "?")), getattr(cs, "standstill", "?")))
print("selfdriveState.enabled =", sm["selfdriveState"].enabled)
try:
    mm = sm["selfdriveStateSP"].mads
    print("MADS: enabled=%s active=%s available=%s state=%s" % (mm.enabled, mm.active, mm.available, mm.state))
except Exception as e:
    print("MADS 读失败:", e)
print("\n-- 进程/日志状态 --")
os.system("pgrep -af 'loggerd|encoderd' | head -4")
os.system("ls -t /data/media/0/realdata/ | head -4; date")
os.system("cat /data/params/d_sp/IsOffroad 2>/dev/null | head -c 20; echo ' <- IsOffroad'")
os.system("ls -la --time-style=+%H:%M /data/media/0/realdata/0000000c--32cbec9ac8--28/ 2>/dev/null | tail -4")
