# -*- coding: utf-8 -*-
import json, urllib.request
CMD = ("echo '[media 目录]'; ls /data/media/0/ | head -20; echo; "
       "echo '[realdata 里是否有别的 route 开头]'; ls -d /data/media/0/realdata/*--* | sed 's#.*/##; s#--[^-]*$##' | sort -u | head -8; echo; "
       "echo '[抽一条 09-23 10 点的段，看 qlog 里的车速/接管]'; "
       "D=$(ls -t /data/media/0/realdata | grep '^0000' | sed -n '300p'); echo seg=$D; "
       "ls /data/media/0/realdata/$D | head -6")
body = json.dumps({"command": CMD}).encode()
req = urllib.request.Request("http://127.0.0.1:3081/api/ssh/exec", data=body, headers={"content-type": "application/json"})
print(urllib.request.urlopen(req, timeout=120).read().decode()[:1500])
