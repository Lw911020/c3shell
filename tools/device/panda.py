# -*- coding: utf-8 -*-
import sys, time
sys.path.insert(0, "/data/openpilot")
import cereal.messaging as messaging
from cereal import car
sm = messaging.SubMaster(["pandaStates", "carParams", "sendcan", "can", "deviceState"])
t0 = time.time()
while time.time() - t0 < 3:
    sm.update(100)
print("== pandaStates 全字段 ==")
for i, p in enumerate(list(sm["pandaStates"])):
    d = p.to_dict()
    for k in ("safetyModel", "safetyParam", "pandaType", "ignitionLine", "ignitionCan", "controlsAllowed",
              "canReceiveErrorCount", "canSendErrorCount", "rxBufferOverflow", "txBufferOverflow", "faults", "powerSaveEnabled"):
        if k in d:
            print("  [%d] %-22s %s" % (i, k, d[k]))
print("== CarParams 安全配置 ==")
try:
    cp = sm["carParams"]
    print("  carFingerprint:", cp.carFingerprint, " brand:", str(cp.brand))
    for i, sc in enumerate(cp.safetyConfigs):
        print("  safetyConfigs[%d]: model=%s param=%s" % (i, str(sc.safetyModel), sc.safetyParam))
    print("  passive:", cp.passive, " openpilotLongitudinalControl:", cp.openpilotLongitudinalControl)
    lt = cp.lateralTuning
    print("  lateralTuning.which():", lt.which())
    if lt.which() == "torque":
        t = lt.torque
        print("  torque: kp=%.3f ki=%.3f kf=%.3f friction=%.3f latAccelFactor=%.3f offset=%.3f deadzone=%.2f" % (
            t.kp, t.ki, t.kf, t.friction, t.latAccelFactor, t.latAccelOffset, getattr(t, "steeringAngleDeadzoneDeg", 0)))
except Exception as e:
    print("  CarParams 读失败:", type(e).__name__, e)
print("== 哪个 panda 在发 CAN ==")
try:
    sc = sm["sendcan"]
    print("  sendcan 有效:", sc.valid if hasattr(sc, "valid") else "?")
except Exception as e:
    print("  sendcan:", e)
