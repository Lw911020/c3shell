# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.18（v2.119.141 · 2026-09-24 投屏显示宽度默认 600）'
assert c.count(old) == 1
entry = """## v1.10.19（v2.119.142 · 2026-09-24 投屏显示宽度默认 650）
- 用户要求：「宽度650」→ 中间档 600 → **650**（按钮显示「650」，仍是默认档 ✓）；存储键 c3castw6 → **c3castw7**（丢弃旧值，升级后直接是 650 ✓）
- 4:3 窗口实测（视口 940×581）：画面区 648×398（边框盒 **650×400**）、画面 **648×324**、状态行「画面 650 · 显示宽 650px」✓
  - 画面区顶 125 → 125+400 = 525 < 581 → **一屏装下，完全不用滚** ✓
- 回退：releases/c3shell-2.119.141.apk（600 那版）✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.19')

PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R51（2026-09-24 · v2.119.142 · 显示宽度 650）
用户：「宽度650」→ 中间档 600 → 650；存储键 c3castw6 → c3castw7（丢弃旧值）✓
- 4:3 实测：画面区 648×398（边框盒 650×400）、画面 648×324、状态行「画面 650 · 显示宽 650px」；画面区顶 125 → 525 < 581 → **完全不用滚** ✓
## R51 复盘
- 数字型需求连着来（600 → 650）时，**换存储键**这一步不能省，否则用户看到的还是旧值 ✗（本次同样换了键 ✓）。
- 画面区高度 400 + 宽度 650 的组合下，控制区+画面区 = 525 < 视口 581：**"硬下限 400"和"一屏装下"最终能同时成立** ✓ —— 之前 500 时是互斥的，说明"下限值"要贴着用户的真实窗口来定 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R51')
