# -*- coding: utf-8 -*-
import json, urllib.request
PY = ("import sys;sys.path.insert(0,'/data/openpilot');"
      "from openpilot.tools.lib.logreader import LogReader;"
      "lr=list(LogReader('/data/media/0/realdata/00000022--17b8947afe--27/qlog.zst'));"
      "print('msgs',len(lr));"
      "import collections;print(collections.Counter(m.which() for m in lr).most_common(8));"
      "vs=[];eng=[];"
      "\nfor m in lr:\n"
      "  w=m.which()\n"
      "  if w=='carState': vs.append(m.carState.vEgo)\n"
      "  if w=='selfdriveState': eng.append(bool(m.selfdriveState.enabled))\n"
      "print('maxVEgo %.2f'%(max(vs) if vs else -1), 'samples', len(vs));"
      "print('selfdriveState enabled count', sum(eng), '/', len(eng))")
CMD = "cd /data/openpilot && timeout 120 /usr/local/venv/bin/python3 -c " + json.dumps(PY)
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body, headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=200).read().decode()[:1200])
