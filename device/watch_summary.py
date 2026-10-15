#!/usr/bin/env python3
# 只读 drivewatch-status.json（小文件），一行式汇总；用于轻量定时汇报
import json, time
try:
    d = json.load(open("/data/openpilot/.dsh/drivewatch-status.json"))
except Exception as e:
    print("status unreadable:", e); raise SystemExit
segs = d.get("segs", [])
def tag(s):
    return s.get("seg", "?").split("--")[-1]
print("UP", d.get("updated"), "| 已读段", len(segs), "| 最近:", ", ".join(
    "%s v%.1f lat%.0f%% sat%d" % (tag(s), s.get("vmax", 0), s.get("lat_pct", 0), s.get("sat", 0)) for s in segs[-3:]))
notable = [s for s in segs[-20:] if (s.get("sat") or 0) > 0 or (s.get("dev_max") or 0) > 0.7
           or (s.get("cross10") or 0) > 0 or (s.get("driver_steer_events") or 0) > 0]
for s in notable[-8:]:
    print("  ⚠ seg", tag(s), "vmax %.1f" % s.get("vmax", 0), "lat%", s.get("lat_pct"),
          "sat", s.get("sat"), "(low", s.get("sat_low"), "big", s.get("sat_big"), ")",
          "a_out_avg", s.get("a_out_avg"), "dev_max", s.get("dev_max"), "cross", s.get("cross10"),
          "steer", s.get("driver_steer_events"), "lines_lost", s.get("probs_lost"))
