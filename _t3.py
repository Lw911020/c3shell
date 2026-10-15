# -*- coding: utf-8 -*-
import json, urllib.request, subprocess, time
S = int(subprocess.check_output(["date", "-d", "2026-09-23 10:00:00", "+%s"]).strip())
E = int(subprocess.check_output(["date", "-d", "2026-09-23 11:00:00", "+%s"]).strip())
root = "/data/media/0/realdata#S=%d#E=%d" % (S, E)
CMD = ("cd /data/openpilot/.dsh && timeout 200 python3 dsh-scan-routes.py --root '%s' "
       "--progress /tmp/p2.json --out /tmp/r2.json > /tmp/s2.log 2>&1; echo EXIT=$?; "
       "grep -E 'DSH_RANGE' /tmp/s2.log | head -2; python3 -c 'import json;d=json.load(open(\"/tmp/r2.json\"));"
       "rs=d[\"routes\"];"
       "print(\"candidates\",d[\"candidates\"],\"routes\",len(rs));"
       "[print(\"  \",r[\"route\"],\"接管%%\",r.get(\"engagedPct\"),\"主导\",r.get(\"dominant\"),\"段\",r[\"segments\"],\"接管次数\",r.get(\"disengagements\")) for r in rs[:6]]'") % (root,)
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body,
                             headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=260).read().decode()[:1500])
