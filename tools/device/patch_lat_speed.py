# -*- coding: utf-8 -*-
"""低速猛推削一半（LOW_SPEED_Y）—— 带 dry-run / 备份 / 回退
用法：
  /usr/local/venv/bin/python3 patch_lat_speed.py dry      # 只看 diff + 语法校验，不改设备
  /usr/local/venv/bin/python3 patch_lat_speed.py apply    # 备份 + 打补丁 + 语法校验（要重启 openpilot 才生效）
  /usr/local/venv/bin/python3 patch_lat_speed.py revert   # 从备份还原
"""
import sys, os, shutil, py_compile, time, difflib
T = "/data/openpilot/selfdrive/controls/lib/latcontrol_torque.py"
BAK = T + ".c3bak"
OLD = "LOW_SPEED_Y = [15, 13, 10, 5]"
NEW = "LOW_SPEED_Y = [8, 7, 6, 4]   # C3 patch 2026-09-26: 低速猛推减半（原 [15,13,10,5]）"
TMP = "/tmp/latcontrol_torque_patched.py"

def read(): return open(T, encoding="utf-8").read()
def check(txt, path=TMP):
    open(path, "w", encoding="utf-8").write(txt)
    py_compile.compile(path, doraise=True)
    return path

act = sys.argv[1] if len(sys.argv) > 1 else "dry"
src = read()
if act == "dry":
    if OLD not in src:
        print("!! 没找到原句（可能已打过补丁）：", OLD); sys.exit(2)
    new = src.replace(OLD, NEW, 1)
    print("\n".join(difflib.unified_diff(src.splitlines(), new.splitlines(), "before", "after", lineterm="", n=1)))
    p = check(new)
    print("语法校验通过 ✓（补丁内容写在 %s，未改动设备）" % p)
elif act == "apply":
    if OLD not in src:
        print("!! 原句不在（已打过？）→ 不动"); sys.exit(2)
    shutil.copyfile(T, BAK); print("已备份:", BAK)
    open(T, "w", encoding="utf-8").write(src.replace(OLD, NEW, 1))
    check(read(), T + ".check")
    os.remove(T + ".check")
    print("已打补丁并校验 ✓ —— 生效需重启 openpilot（⚠ 车辆通电时重启会锁 LKAS 故障，见 ADAPTATION §4.24.1）")
elif act == "revert":
    if not os.path.exists(BAK):
        print("!! 没有备份:", BAK); sys.exit(2)
    shutil.copyfile(BAK, T)
    check(read(), T + ".check"); os.remove(T + ".check")
    print("已从备份还原 ✓")
else:
    print(__doc__)
