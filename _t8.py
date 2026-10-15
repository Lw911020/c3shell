# -*- coding: utf-8 -*-
import json, urllib.request
SCRIPT = '''import sys, glob, os
sys.path.insert(0, "/data/openpilot")
from openpilot.tools.lib.logreader import LogReader
dirs = sorted(glob.glob("/data/media/0/realdata/*--*"), key=os.path.getmtime)
# 取昨天(09-23)的段，均匀抽 10 个
import time
picks = [d for d in dirs if time.strftime("%m-%d", time.localtime(os.path.getmtime(d))) == "09-23"]
step = max(1, len(picks)//10)
for d in picks[::step][:10]:
    p = os.path.join(d, "qlog.zst")
    if not os.path.exists(p):
        p = os.path.join(d, "rlog.zst")
    try:
        vs = []
        eng = 0; sd = 0
        for m in LogReader(p):
            w = m.which()
            if w == "carState": vs.append(m.carState.vEgo)
            if w == "selfdriveState":
                sd += 1
                if m.selfdriveState.enabled: eng += 1
        print("%s  maxVEgo=%5.1f  engaged=%d/%d" % (os.path.basename(d), max(vs) if vs else -1, eng, sd))
    except Exception as e:
        print(os.path.basename(d), "读取失败", str(e)[:50])
'''
CMD = "cat > /tmp/chk2.py <<'PYEOF'\n" + SCRIPT + "PYEOF\ncd /data/openpilot && timeout 240 /usr/local/venv/bin/python3 /tmp/chk2.py"
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body, headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=300).read().decode()[:2000])
