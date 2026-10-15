# -*- coding: utf-8 -*-
import json, urllib.request
CMD = ("ls -l --time-style=+%m-%d_%H /data/media/0/realdata | awk 'NR>1 && $6 ~ /^09-23/ {print $6}' "
       "| cut -d_ -f2 | sort | uniq -c | sort -k2 | head -30")
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body,
                             headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=120).read().decode()[:1200])
