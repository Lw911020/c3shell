#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""浅色主题对比度审计（WCAG）：把主题变量两两组合算对比度，低于阈值即报红。
   阈值：正文 4.5:1；大字/图形/控件边框 3.0:1。"""
import re, sys, os
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
css = open(os.path.join(SRC, 'assets/theme.css'), encoding='utf-8').read()
def vars_of(theme):
    m = re.search(r'html\[data-theme="%s"\]\s*\{(.*?)\}' % theme, css, re.S)
    d = {}
    if m:
        for k, v in re.findall(r'(--[\w-]+)\s*:\s*([^;]+)', m.group(1)):
            d[k] = v.strip()
    return d
def rgb(s):
    s = s.strip().lstrip('#')
    if len(s) == 3: s = ''.join(c*2 for c in s)
    if len(s) != 6: return None
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))
def lum(c):
    def f(v):
        v = v/255.0
        return v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    r, g, b = c
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)
def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi+0.05)/(lo+0.05)
def check(theme):
    V = vars_of(theme)
    if not V: print('  ❌ 未找到主题 %s' % theme); return 1
    def g(*names):
        for n in names:
            if n in V: return rgb(V[n])
        return None
    bg, bg2, bg3 = g('--bg'), g('--bg2'), g('--bg3')
    fg, dim = g('--fg'), g('--dim')
    pairs = [
        ('正文 / 页面底',   fg,  bg,  4.5),
        ('正文 / 卡片底',   fg,  bg2, 4.5),
        ('正文 / 第三层底', fg,  bg3, 4.5),
        ('次要字 / 页面底', dim, bg,  4.5),
        ('次要字 / 卡片底', dim, bg2, 4.5),
        ('强调色 / 卡片底', g('--acc'), bg2, 3.0),
        ('黄 / 卡片底',     g('--y'),   bg2, 3.0),
        ('绿 / 卡片底',     g('--g'),   bg2, 3.0),
        ('橙 / 卡片底',     g('--o'),   bg2, 3.0),
        ('红 / 卡片底',     g('--r'),   bg2, 3.0),
        ('状态字白 / 强调', (255,255,255), g('--acc'), 3.0),
        ('边框 / 卡片底',   g('--line'), bg2, 1.2),
    ]
    bad = 0
    print('  ── %s ──' % theme)
    for name, a, b, need in pairs:
        if not a or not b: print('   ⚠ %-16s 变量缺失（跳过）' % name); continue
        r = ratio(a, b); ok = r >= need
        bad += 0 if ok else 1
        print('   %s %-16s %5.2f:1  (需 ≥%.1f)' % ('✅' if ok else '❌', name, r, need))
    return bad
tot = check('light')
print('\n  对比度审计: %s' % ('全部达标 ✅' if tot == 0 else '有 %d 项不达标 ❌' % tot))
sys.exit(0 if tot == 0 else 1)
