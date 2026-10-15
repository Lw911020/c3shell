# -*- coding: utf-8 -*-
"""把 theme.css 里两段 @media (min-width:900px) 车机块，改成只在 html[data-layout="car"] 下生效。
   默认（手机/平板）= 1.97 那套：菜单永远在最上面。"""
import io, sys, re

p = 'theme.css'
s = io.open(p, encoding='utf-8').read()
if 'data-layout="car"' in s:
    sys.exit('已经改过了')

def split_sel(sel):
    parts, depth, cur = [], 0, ''
    for ch in sel:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur); cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [x.strip() for x in parts if x.strip()]

def transform(inner):
    inner = re.sub(r'/\*.*?\*/', '', inner, flags=re.S)
    out, i = [], 0
    while i < len(inner):
        j = inner.find('{', i)
        if j < 0:
            break
        sel = inner[i:j].strip()
        depth, k = 1, j + 1
        while k < len(inner) and depth:
            if inner[k] == '{':
                depth += 1
            elif inner[k] == '}':
                depth -= 1
            k += 1
        body = inner[j:k].strip()
        if sel:
            pref = ', '.join('html[data-layout="car"] ' + x for x in split_sel(sel))
            out.append(pref + ' ' + body)
        i = k
    return '\n'.join(out)

count = 0
while True:
    m = re.search(r'@media\s*\(min-width:900px\)\s*\{', s)
    if not m:
        break
    depth, k = 1, m.end()
    while k < len(s) and depth:
        if s[k] == '{':
            depth += 1
        elif s[k] == '}':
            depth -= 1
        k += 1
    inner = s[m.end():k-1]
    new = ('/* ── 车机模式（2026-09-22 改：只在 html[data-layout="car"] 下生效）──\n'
           '   手机/平板默认 = 1.97 原始布局：菜单永远在最上面，不再按宽度自动变左栏。 */\n'
           + transform(inner) + '\n')
    s = s[:m.start()] + new + s[k:]
    count += 1

io.open(p, 'w', encoding='utf-8').write(s)
print('转换了 %d 段 → html[data-layout="car"]' % count)

