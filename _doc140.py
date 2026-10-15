# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.16（v2.119.136~139 · 2026-09-24 4:3 窗口下的投屏页 + 几何自检 + JS 门禁）'
assert c.count(old) == 1
entry = """## v1.10.17（v2.119.140 · 2026-09-24 画面区高度下限 500 → 400）
- 用户改口：「高度该到400」→ #castBox 的 min-height 与「适配」的高度下限一并 **500 → 400** ✓（状态行改标「高 ≥400px ✓」）
- 4:3 窗口实测（视口 940×581，控制区 244）：
  | 档位 | 画面区 | 画面 | 黑边 |
  |---|---|---|---|
  | 适配 | 798×**398**（边框盒 400）| **798×399** | **无**（画面正好填满 ✓）|
  | 中 480 | 478×398 | 478×239 | 有（档位本身小）|
  - 控制区 244 + 400 = 644 > 581 → 仍需**下滚约 63px**（比 500 时的 163px 好很多 ✓）
- 回退：releases/c3shell-2.119.139.apk（下限 500 那版）✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.17')

PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R49（2026-09-24 · v2.119.140 · 画面区下限 400）
用户：「高度该到400」→ min-height 与适配下限 500→400 ✓
- 4:3 实测：适配 = 画面区 798×398、**画面 798×399（正好填满、零黑边 ✓）**；控制区 244 + 400 = 644 vs 视口 581 → 下滚约 63px
## R49 复盘
- 400 这个数恰好把"画面填满区域"和"别太占地方"两头都满足了（适配档画面 2:1 → 高 399 ≈ 下限 400 ✓）——**下限值贴着画面比例走时黑边自然消失**，以后设下限先算这个数 ✓。
- 有几何自检（CASTGEO）之后，这类数值调整**一轮就能给出实测表**，不用再截图量像素 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R49')
