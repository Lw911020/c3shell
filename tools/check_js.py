#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_js.py —— 构建门禁：页面内联 <script> 的 JS 语法体检（不依赖浏览器）

用法: python3 tools/check_js.py [html...]      默认 page.html + diag.html
背景（2026-09-24 踩坑）：我给投屏脚本块插自检代码时吞掉了一个收尾大括号 ✗
→ 整个块语法错误 → 投屏页功能全失效，但页面结构体检（check_page.py）看不出来 ✗
→ 所以每版必须跑这条：任何一个"新增的坏块"都直接失败 ✓
已知误报：page.html 的块 #10/#11（页面里含字面量 </script> 的字符串，HTML 解析本就在那里断块），
用 KNOWN_BAD 白名单放行，但**不允许新增** ✓
"""
import io, os, re, subprocess, sys

# 2026-09-24 R107：白名单清空 —— 原以为这两块可以忽略，结果里面藏着一个真语法错误（见 CHANGELOG）
# 现在只要出现坏块就报错 ✓（本次修复后两页坏块数均为 0 ✓）
KNOWN_BAD = {'page.html': set()}
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def blocks(path):
    h = io.open(path, encoding='utf-8').read()
    return re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', h, flags=re.S)

def main():
    files = sys.argv[1:] or ['assets/page.html', 'assets/diag.html']
    bad_all = 0
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(SRC, f)
        name = os.path.basename(p)
        bs = blocks(p)
        bad = []
        for i, b in enumerate(bs):
            tmp = os.path.join(SRC, '.jscheck.tmp.js')
            io.open(tmp, 'w', encoding='utf-8').write(b)
            r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
            if r.returncode != 0:
                err = [l for l in r.stderr.splitlines() if 'SyntaxError' in l]
                bad.append((i, (err[0] if err else '?')[:120]))
        try:
            os.remove(os.path.join(SRC, '.jscheck.tmp.js'))
        except OSError:
            pass
        known = KNOWN_BAD.get(name, set())
        new = [x for x in bad if x[0] not in known]
        print('%-12s 块=%d 坏=%d 新增坏=%d %s' % (name, len(bs), len(bad), len(new),
              ('✗ ' + str(new)) if new else 'OK ✓'))
        bad_all += len(new)
    sys.exit(1 if bad_all else 0)

if __name__ == '__main__':
    main()
