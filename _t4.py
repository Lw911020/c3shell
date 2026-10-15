# -*- coding: utf-8 -*-
import json, urllib.request, subprocess
S = int(subprocess.check_output(["date", "-d", "2026-09-23 18:30:00", "+%s"]).strip())
E = int(subprocess.check_output(["date", "-d", "2026-09-23 19:00:00", "+%s"]).strip())
root = "/data/media/0/realdata#S=%d#E=%d" % (S, E)
CMD = ("cd /data/openpilot/.dsh && timeout 200 python3 dsh-scan-routes.py --root '%s' --out /tmp/r3.json >/tmp/s3.log 2>&1; "
       "echo EXIT=$?; grep DSH_RANGE /tmp/s3.log|head -1; "
       "python3 -c 'import json;d=json.load(open(\"/tmp/r3.json\"));rs=d[\"routes\"];"
       "print(\"routes\",len(rs));"
       "[print(\"  \",r[\"route\"],\"engagedPct\",r.get(\"engagedPct\"),\"dominant\",r.get(\"dominant\"),\"classes\",r.get(\"classBreakdown\"),\"seg\",r[\"segments\"],\"vMax\",r.get(\"vMax\")) for r in rs[:5]]'" ) % (root,)
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body, headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=280).read().decode()[:1200])
