# -*- coding: utf-8 -*-
import sys, time
sys.path.insert(0, "/data/openpilot")
try:
    import cereal.messaging as messaging
    sm = messaging.SubMaster(["carState", "controlsState", "selfdriveState", "carParams"])
    t0 = time.time()
    while time.time() - t0 < 3:
        sm.update(100)
    cs = sm["carState"]
    print("carState: vEgo=%.2f gearShifter=%s steerFaultTemporary=%s steerFaultPermanent=%s" % (
        cs.vEgo, str(cs.gearShifter), cs.steerFaultTemporary, cs.steerFaultPermanent))
    ctl = sm["controlsState"]
    print("controlsState: lateralActive=%s lateralAvailable=%s" % (
        getattr(ctl, "lateralActive", "?"), getattr(ctl, "lateralAvailable", "?")))
    print("selfdriveState: enabled=%s state=%s" % (sm["selfdriveState"].enabled, sm["selfdriveState"].state))
    try:
        print("carParams: ", sm["carParams"].carFingerprint)
    except Exception:
        pass
except Exception as e:
    print("读信号失败:", type(e).__name__, e)
