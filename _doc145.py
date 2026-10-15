# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.20（v2.119.143/144 · 2026-09-24 画面区高度 400 → 380 → 360）'
assert c.count(old) == 1
entry = """## v1.10.21（v2.119.145 · 2026-09-24 画面区高度 360 → 340）
- 用户：「高度340」→ min-height 与适配下限 340（状态行标「高 ≥340px ✓」）
- 实测（视口 940×581、显示宽 650）：画面区 648×**338**（边框盒 650×340）、画面 648×324 → 黑边上下各约 7px（基本贴近画面 ✓）
- 回退：releases/c3shell-2.119.144.apk（360 那版）✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.21')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R54（2026-09-24 · v2.119.145 · 画面区高度 340）
用户：「高度340」→ min-height/适配下限 340 ✓
- 实测：画面区 648×338（边框盒 650×340）、画面 648×324 → 黑边各约 7px（已贴近画面）
## R54 复盘
- 数值微调已完全流水线化（改数 → 门禁 → 构建 → 装 → 几何自检报数 → 记档），一轮 3~4 分钟 ✓
- 画面本身 324 高是当前宽 650 的"自然高度"：区域 340 已基本贴合；若继续降（≤324）区域就由画面决定高度 ✓
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R54')
