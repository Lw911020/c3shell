# -*- coding: utf-8 -*-
import urllib.request, json, time
B='http://127.0.0.1:3081'
def api(p, t=120):
    return json.loads(urllib.request.urlopen(B+p+'?token=embedded', timeout=t).read().decode())
print('启动浮窗:', str(api('/api/float/start'))[:150])
time.sleep(10)
print('浮窗状态:', str(api('/api/float/status'))[:250])
print('投屏服务:', str(api('/api/cast/status'))[:200])

