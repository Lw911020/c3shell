# -*- coding: utf-8 -*-
import urllib.request, time, json
def get(u, t=25):
    for i in range(3):
        try:
            return urllib.request.urlopen('http://127.0.0.1:3081'+u, timeout=t).read()
        except Exception as e:
            time.sleep(2)
    return None
c = get('/theme.css')
if c is None:
    print('theme.css 拉取失败（APP 服务未响应）')
else:
    t = c.decode('utf-8','replace')
    print('theme.css:', len(t), '字节')
    for pat in ('data-density="compact"', 'data-density="large"', 'html[data-density] body', 'data-density] .note'):
        print('   %-26s %d 次' % (pat, t.count(pat)))
j = get('/api/log?token=embedded')
if j:
    ls = json.loads(j.decode()).get('log','').splitlines()
    h = [x for x in ls if '[THEME]' in x]
    print('[THEME] 诊断行数:', len(h))
    for x in h[-2:]:
        print('   ', x[:300])

