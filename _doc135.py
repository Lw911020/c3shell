# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.14（v2.119.133/134 · 2026-09-24 一级菜单"选中态"）'
assert c.count(old) == 1
entry = """## v1.10.15（v2.119.135 · 2026-09-24 投屏区域最小高度 500px）
- 用户要求：**投屏区域高度最少 500px** ✓
- 背景：画面区高度原本完全由宽度决定（C3 画面 2:1，适配档约 900px 宽 → 只有约 450px 高，窗口再窄就更矮）
- 处理：
  - CSS：#castBox 加 **min-height:500px**，并改 flex 纵向 + 居中（画面比区域矮时上下留黑边，不再贴顶）✓
  - 适配档：可用高度下限由 130px 提到 **500px** → 适配会按"至少 500 高"反推宽度（受卡片可用宽限制）✓
  - 状态行同步标注：适配档显示「适配（高 ≥500px ✓）」✓
- 说明：手机/平板窗口本身不足 750px 高时，页面会**滚动**（500 区域 + 控制区），这是"高度下限"的必然结果 ✓
- 回退：releases/c3shell-2.119.134.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.15')

PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R47（2026-09-24 · v2.119.135 · 投屏区域最小高度 500px）
用户要求：投屏区域高度最少 500px。
- 原状：画面区高度 = 宽度/2（2:1），适配档约 900px 宽 → 约 450px 高；窗口变窄还会更矮 ✗
- 处理：#castBox 加 min-height:500px + flex 纵向居中；适配档可用高度下限 130 → **500**（按"至少 500 高"反推宽度，受卡片宽限制）；状态行标注「高 ≥500px ✓」
- 验证：产物页 asset 内规则核对 ✓（#castBox{...min-height:500px...}、fitPx availH<500）；页面静态体检 OK ✓
- 注意：窗口不足 750px 高时页面会滚动 —— 这是"高度下限"的必然结果，已在 CHANGELOG 写明
## R47 复盘
- **先看约束再改**：这类"最小尺寸"需求，要先算清"区域高度由谁决定"（这里是宽度/2）→ 才知道是给区域加下限，还是给宽度加下限（两个都做才稳）✓。
- 验收标准是用户给的硬指标（500px）时，尽量让**页面把实测值打出来**（状态行标注/后续可加 clientHeight），比事后靠截图量像素可靠 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R47')
