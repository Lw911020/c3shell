# -*- coding: utf-8 -*-
import sys, os, time
sys.path.insert(0, "/data/openpilot")
import cereal.messaging as messaging
sm = messaging.SubMaster(["liveTorqueParameters", "liveParameters", "carParams"])
t0 = time.time()
while time.time() - t0 < 3:
    sm.update(100)
lt = sm["liveTorqueParameters"]
print("liveTorqueParameters: useParams=%s valid=%s latAccelFactor=%.4f friction=%.4f points=%s" % (
    getattr(lt, "useParams", "?"), getattr(lt, "valid", "?"),
    getattr(lt, "latAccelFactorFiltered", 0), getattr(lt, "frictionCoefficientFiltered", 0),
    getattr(lt, "totalBucketPoints", "?")))
lp = sm["liveParameters"]
print("liveParameters: valid=%s steerRatio=%.3f stiffness=%.3f angleOffset=%.3f" % (
    getattr(lp, "valid", "?"), getattr(lp, "steerRatio", 0), getattr(lp, "stiffnessFactor", 0), getattr(lp, "angleOffset", 0)))
cp = sm["carParams"]
print("CarParams.lateralTuning=%s  brand=%s" % (cp.lateralTuning.which(), str(cp.brand)))
