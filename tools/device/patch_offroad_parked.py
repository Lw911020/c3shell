# -*- coding: utf-8 -*-
"""下线兜底补丁：点火线常高时，用"驻车 N 分钟 → 视为熄火"判定 offroad
用法：
  /usr/local/venv/bin/python3 patch_offroad_parked.py dry       # 只看 diff + 语法校验（不改设备）
  /usr/local/venv/bin/python3 patch_offroad_parked.py apply     # 备份 + 打补丁 + 校验
  /usr/local/venv/bin/python3 patch_offroad_parked.py revert    # 还原
  /usr/local/venv/bin/python3 patch_offroad_parked.py setmin 10 # 设置"驻车几分钟算熄火"（0=关闭）
说明：默认 **不改变** 原有行为（OffroadParkedMin 不存在/为 0 时走原逻辑）✓
"""
import sys, os, shutil, py_compile, difflib
T = "/data/openpilot/system/hardware/hardwared.py"
BAK = T + ".c3bak"
PARAM = "/data/params/d_sp/OffroadParkedMin"
TMP = "/tmp/hardwared_patched.py"

R1_OLD = '  sm = messaging.SubMaster(["peripheralState", "gpsLocationExternal", "selfdriveState", "pandaStates"], poll="pandaStates")'
R1_NEW = '  sm = messaging.SubMaster(["peripheralState", "gpsLocationExternal", "selfdriveState", "pandaStates", "carState"], poll="pandaStates")  # C3 patch: 需要 carState 判断驻车'

R2_OLD = '  last_uptime_ts: float = time.monotonic()'
R2_NEW = '  last_uptime_ts: float = time.monotonic()\n  _c3_parked_since = None  # C3 patch: 驻车起点（秒）'

R3_OLD = '      onroad_conditions["ignition"] = any(ps.ignitionLine or ps.ignitionCan for ps in pandaStates if ps.pandaType != log.PandaState.PandaType.unknown)'
R3_NEW = '''      # ── C3 patch 2026-09-26：这台 BYD 点火线常高（ignitionCan 恒 False）→ 可选"驻车视为熄火"兜底 ──
      _ign_raw = any(ps.ignitionLine or ps.ignitionCan for ps in pandaStates if ps.pandaType != log.PandaState.PandaType.unknown)
      try:
        _c3_min = float(params.get("OffroadParkedMin", return_default=True) or 0)
      except Exception:
        _c3_min = 0.0
      if _c3_min > 0 and _ign_raw and sm.updated['carState']:
        _cs = sm['carState']
        _parked = (str(_cs.gearShifter) == "park") and abs(_cs.vEgo) < 0.1
        if _parked:
          if _c3_parked_since is None:
            _c3_parked_since = time.monotonic()
          elif (time.monotonic() - _c3_parked_since) > _c3_min * 60.0:
            cloudlog.warning("C3 patch: 驻车超过 %.0f 分钟 → 视为熄火（点火线常高兜底）" % _c3_min)
            _ign_raw = False
        else:
          _c3_parked_since = None
      onroad_conditions["ignition"] = _ign_raw'''

def read():
  return open(T, encoding="utf-8").read()

def patch(txt):
  for old, new in ((R1_OLD, R1_NEW), (R2_OLD, R2_NEW), (R3_OLD, R3_NEW)):
    if old not in txt:
      raise SystemExit("找不到锚点（可能已打过补丁或版本不同）：\n" + old[:90])
    txt = txt.replace(old, new, 1)
  return txt

def check(txt, path):
  open(path, "w", encoding="utf-8").write(txt)
  py_compile.compile(path, doraise=True)
  return path

act = sys.argv[1] if len(sys.argv) > 1 else "dry"
src = read()
if "C3 patch" in src and act in ("dry", "apply"):
  print("看起来已经打过补丁（含 C3 patch 标记）→ 不动"); sys.exit(3)
elif act == "dry":
  new = patch(src)
  print("\n".join(difflib.unified_diff(src.splitlines(), new.splitlines(), "before", "after", lineterm="", n=1)))
  check(new, TMP)
  print("语法校验通过 ✓（补丁副本 %s，未改动设备）" % TMP)
elif act == "apply":
  shutil.copyfile(T, BAK); print("已备份:", BAK)
  new = patch(src)
  open(T, "w", encoding="utf-8").write(new)
  check(read(), T + ".check"); os.remove(T + ".check")
  print("已打补丁并校验 ✓  生效需重启 openpilot；开启兜底：")
  print("   echo 10 > %s   （驻车 10 分钟视为熄火；0 = 关闭）" % PARAM)
  print("   ⚠ 车辆通电时重启会锁 LKAS 故障（ADAPTATION §4.24.1）")
elif act == "revert":
  if not os.path.exists(BAK):
    print("!! 没有备份:", BAK); sys.exit(2)
  shutil.copyfile(BAK, T); check(read(), T + ".check"); os.remove(T + ".check")
  print("已从备份还原 ✓")
elif act == "setmin":
  n = sys.argv[2] if len(sys.argv) > 2 else "10"
  os.system('echo %s > %s' % (n, PARAM))
  print("OffroadParkedMin =", open(PARAM).read().strip(), "（分钟；0=关闭）")
else:
  print(__doc__)
