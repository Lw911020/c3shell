# -*- coding: utf-8 -*-
"""R73b：结论里"见 ②"的引用已失效（② 不再显示）→ 改成指向报告/问 AI"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
old = """v.push('· 参数与厂商默认不同 '+n+' 项（见 ②，其中驾驶相关的已标 ⚠）');"""
new = """v.push('· 参数与厂商默认不同 '+n+' 项（已收进体检报告；点「问 AI」会自动带上这些参数 ✓）');"""
assert h.count(old) == 1, '未命中 verdict 文案'
h = h.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  结论引用改指向报告/问 AI')

CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
o2 = '## v1.10.34（v2.119.167/168 · 2026-09-24 AI 分析删「设备/参数」入口，聚焦接管日记）'
assert c.count(o2) == 1
entry = """## v1.10.35（v2.119.169/170 · 2026-09-24 AI 分析只显示「接管日志 + 结论」）
- 用户要求：AI 分析只要接管日志数据与结论；但**问 AI 时可以引用设备与参数** ✓
- 处理：
  - renderAll 增加 dataOnly 参数：**照旧计算** LAST（参数差异）与 LASTCTX（设备现状）✓，但**不渲染** ①设备现状 / ②参数分析 / ③操作提示 ✓
  - analyzeAll 只渲染 **接管日志（路线）+ 结论** ✓（诊断页采样报告不再单独展示，其数据仍在报告与结论里 ✓）
  - 卡片标题改「AI 分析（接管日志 · 结论）」；提示文案改「问 AI=自动带上接管日志与设备/参数数据」✓
  - 结论里原先「参数差异 N 项（见 ②…）」的失效引用改为「已收进体检报告；点问 AI 会自动带上」✓
- 关键：**下载报告 / 交给 AI 分析的 prompt 仍然包含设备现状 + 参数差异 + 路线 + 采样** ✓（用户要的"问 AI 可以引用" ✓）
- 实测（v2.119.169 截图）：结果区只有「接管日志」+「结论」两段 ✓
- 回退：releases/c3shell-2.119.168.apk ✓

"""
c = c.replace(o2, entry + o2)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.35')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip(chr(10)) + """

## R73（2026-09-24 · v2.119.169/170 · AI 分析只显示接管日志 + 结论）
用户：AI 分析只要接管日志数据与结论；但问 AI 时可以引用设备与参数
- renderAll(out, dataOnly)：数据照算（LAST/LASTCTX），不渲染 ①②③ ✓；analyzeAll 只渲染「接管日志 + 结论」✓
- 报告与「问 AI」的 prompt 不变（仍含设备/参数/路线/采样）✓；结论里的失效引用（见 ②）已改 ✓
## R73 复盘
- "界面少显示" ≠ "数据不要"：正确做法是**把取数与渲染拆开**（dataOnly 开关 ✓），而不是删掉取数逻辑 ✗ —— 否则报告/问 AI 就少了内容 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R73')
