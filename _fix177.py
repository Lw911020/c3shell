# -*- coding: utf-8 -*-
"""R78：① 设备脚本负数 limit 被切尾（1天/3天失效）② 提示文字挪到「数据来源」下面"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

# ① 脚本：只有正数才截断
SR = os.path.join(D, 'assets/remote/scan_routes.py')
s = io.open(SR, encoding='utf-8').read()
old = """    if args.limit:
        dirs = dirs[:args.limit]"""
new = """    # 2026-09-24 R78：**只有正数才截断**！负数（最近 N 天）在这里会被当成 dirs[:-N] 砍掉尾巴 ✗
    if args.limit > 0:
        dirs = dirs[:args.limit]"""
assert s.count(old) == 1, '脚本截断处未命中'
s = s.replace(old, new)
io.open(SR, 'w', encoding='utf-8').write(s)
print('OK  scan_routes.py：负数不再被切尾')

# ② 页面：提示文字挪到「数据来源」下面
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
hint_start = h.find('<div class="note" style="margin:-2px 0 3px;font-size:11px;opacity:.85;line-height:1.35">路线 qlog=')
assert hint_start > 0, '提示块未找到'
hint_end = h.find('</div>', hint_start) + len('</div>')
hint = h[hint_start:hint_end]
h = h[:hint_start] + h[hint_end:]
src_marker = '<div class="note" style="margin-top:6px">数据来源：'
i = h.find(src_marker)
assert i > 0, '数据来源块未找到'
j = h.find('</div>', i) + len('</div>')
h = h[:j] + '\n        ' + hint + h[j:]
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  提示已挪到数据来源下面')
