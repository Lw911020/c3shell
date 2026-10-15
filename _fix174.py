# -*- coding: utf-8 -*-
"""R76：把 renderAll 的"取数"挪到最前（dataOnly 时真的一点都不渲染）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()

start = h.find('    /* ② 参数分析 */\n')
end_marker = '    if(dataOnly) return;'
end = h.find(end_marker, start)
assert start > 0 and end > start, '定位失败'
end = h.find('\n', end) + 1
block = h[start:end]
print('搬移块长度', len(block), '首行:', block.split(chr(10))[0][:40])

# 摘掉旧块（② 参数分析 的数据部分 + 提前返回）
h = h[:start] + '    /* ② 参数分析（list 已在上面算好 ✓） */\n' + h[end:]

# 末尾那行旧的 LASTCTX（现在不需要重复）
tail_old = "    el('aiInfo').textContent='已分析：参数差异 '+list.length+' 项 · 状态与录制已读取 ✓';\n    LASTCTX=st; try{ window.LASTCTX=LASTCTX; }catch(e){}\n"
assert h.count(tail_old) == 1, '尾部定位失败'
h = h.replace(tail_old, "    el('aiInfo').textContent='已分析：参数差异 '+list.length+' 项 · 状态与录制已读取 ✓';\n")

# 插到 renderAll 开头（st 定义之后）
anchor = "  function renderAll(out, dataOnly){\n"
i = h.find(anchor)
assert i > 0, 'renderAll 定位失败'
j = h.find('    var st=String(out.status||\'\');\n', i)
assert j > i, 'st 定位失败'
j += len('    var st=String(out.status||\'\');\n')
note = ('    /* 2026-09-24 R76：数据先算好（参数差异 list / 设备现状 st）→ dataOnly 直接返回，\n'
        '       ① 设备现状、② 参数列表、③ 操作提示全部不渲染 ✓（避免路线分析后又冒出 ① 块 ✗） */\n')
h = h[:j] + note + block + h[j:]

io.open(P, 'w', encoding='utf-8').write(h)
print('OK  取数已前置')
