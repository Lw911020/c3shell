# -*- coding: utf-8 -*-
import json, urllib.request
SCRIPT = '''import sys, collections
sys.path.insert(0, "/data/openpilot")
from openpilot.tools.lib.logreader import LogReader
p = "/data/media/0/realdata/00000022--17b8947afe--27/qlog.zst"
lr = list(LogReader(p))
print("msgs", len(lr))
print(collections.Counter(m.which() for m in lr).most_common(8))
vs = []
eng = 0
sd = 0
for m in lr:
    w = m.which()
    if w == "carState":
        vs.append(m.carState.vEgo)
    if w == "selfdriveState":
        sd += 1
        if m.selfdriveState.enabled: eng += 1
print("maxVEgo", round(max(vs), 2) if vs else -1, "carState样本", len(vs))
print("selfdriveState enabled", eng, "/", sd)
'''
CMD = "cat > /tmp/chk.py <<'PYEOF'\n" + SCRIPT + "PYEOF\ncd /data/openpilot && timeout 150 /usr/local/venv/bin/python3 /tmp/chk.py"
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body, headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=220).read().decode()[:1200])
