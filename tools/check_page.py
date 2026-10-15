# -*- coding: utf-8 -*-
"""页面完整性检查器（防止 style/link/script 标签被补丁吃掉 ✗）"""
import io, re, sys
def check(path):
    h = io.open(path, encoding='utf-8').read()
    bad = []
    for tag in ('style','script','head','body','textarea'):
        o = len(re.findall(r'<'+tag+r'[ >]', h)); c = h.count('</'+tag+'>')
        limit = 2 if tag=='script' else 0
        if o - c > limit: bad.append('%s: 开=%d 闭=%d' % (tag, o, c))
    if 'page.html' in path and h.count('<link') < 2: bad.append('<link> 只有 %d 个（应≥2）' % h.count('<link'))
    if 'theme.css' not in h: bad.append('缺少 theme.css 引用 ✗')
    return bad
for p in ('/storage/emulated/0/openpilot/c3shell/assets/page.html',
          '/storage/emulated/0/openpilot/c3shell/assets/diag.html'):
    b = check(p)
    print('  %-14s %s' % (p.split('/')[-1], 'OK ✓' if not b else ('✗ ' + '; '.join(b))))
sys.exit(0)

