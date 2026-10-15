#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语法检查（2026-09-21）：对 app/*.js 与两页内联脚本块逐个跑 node --check。
   —— "能取到却整块不执行" 的元凶通常是解析错误 ✗，此工具让它无处可藏。"""
import os, re, subprocess, sys, tempfile
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def check(code, tag):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(code); p = f.name
    r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
    os.unlink(p)
    return (r.returncode == 0), (r.stderr or '').strip().split('\n')[:2]
bad = []
for f in sorted(os.listdir(os.path.join(SRC, 'assets/app'))):
    if not f.endswith('.js'): continue
    code = open(os.path.join(SRC, 'assets/app', f), encoding='utf-8').read()
    ok, err = check(code, f)
    print('  %s app/%-22s %s' % ('✅' if ok else '❌', f, '' if ok else err))
    if not ok: bad.append('app/' + f)
for page, url in (('page.html', 'assets/page.html'), ('diag.html', 'assets/diag.html')):
    fp = os.path.join(SRC, url)
    if not os.path.exists(fp):
        print('  – %s 不存在（已并入单一文档）→ 跳过 ✓' % page); continue
    s = open(fp, encoding='utf-8').read()
    blocks = re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', s, re.S)
    for i, b in enumerate(blocks):
        if not b.strip(): continue
        ok, err = check(b, '%s#%d' % (page, i))
        if not ok:
            print('  ❌ %s 脚本块%d: %s' % (page, i, err))
            bad.append('%s#%d' % (page, i))
    print('  %s 内联脚本块 %d 个（未列出者=语法通过）' % ('✅' if not any(x.startswith(page) for x in bad) else '❌', len(blocks)))
print('\n  语法检查: %s' % ('全部通过 ✅' if not bad else '失败 %d 处 ❌ %s' % (len(bad), bad)))
sys.exit(0 if not bad else 1)
