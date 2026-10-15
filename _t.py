# -*- coding: utf-8 -*-
import json, urllib.request
CMD = ("cd /data/openpilot/.dsh && timeout 110 python3 dsh-scan-routes.py --root /data/media/0/realdata "
       "--limit -1 --progress /tmp/p1.json --out /tmp/r1.json > /tmp/s1.log 2>&1; "
       "echo EXIT=$?; echo ---; grep -E 'DSH_DAYS|DSH_RANGE' /tmp/s1.log | head -3; echo ---; "
       "python3 -c 'import json;d=json.load(open(\"/tmp/r1.json\"));print(\"candidates\",d[\"candidates\"],\"routes\",len(d[\"routes\"]))'")
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body,
                             headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=180).read().decode()[:900])
