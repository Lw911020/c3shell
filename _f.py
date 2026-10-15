# -*- coding: utf-8 -*-
import urllib.request, json, re
print('=== 1) 服务出去的 theme.css 里，字号(density)规则还在吗 ===')
c = urllib.request.urlopen('http://127.0.0.1:3081/theme.css', timeout=10).read().decode('utf-8','replace')
print('  文件大小:', len(c))
for pat in ('data-density="compact"', 'data-density="large"', 'data-density body', 'data-density] .note'):
    print('   %-28s 出现 %d 次' % (pat, c.count(pat)))
print()
print('=== 2) theme.js 能加载吗（现在链接合法 ✓）===')
for u in ('/theme.css', '/theme.js'):
    try:
        r = urllib.request.urlopen('http://127.0.0.1:3081'+u, timeout=10)
        print('  %-12s HTTP %s  %d 字节' % (u, r.status, len(r.read())))
    except Exception as e:
        print('  %-12s 失败: %s' % (u, e))
print()
print('=== 3) [THEME] 诊断（theme.css 加载后会打印样表明细 ✓）===')
ls = json.loads(urllib.request.urlopen('http://127.0.0.1:3081/api/log?token=embedded', timeout=8).read().decode()).get('log','').splitlines()
h = [x for x in ls if '[THEME]' in x]
print('  行数:', len(h))
for x in h[-3:]:
    print('  ', x[:300])

