# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.32（v2.119.161~165 · 2026-09-24 AI 分析页四修 · 全部实测通过）'
assert c.count(old) == 1
entry = """## v1.10.33（v2.119.166 · 2026-09-24 内容卡片跟随屏幕宽度）
- 用户要求：软件设置里面的卡片自适应屏幕 ✓
- 真因：基础样式 .card 写死 width:min(860px,96vw) ✗ → 宽屏（平板/车机大屏）右侧留一大片白
- 处理：新增 main section>.card{width:auto;max-width:none} ✓
  · 只作用于**内容卡片**（main 下的 section 直接子卡片）；弹窗里的 .card 仍用各自行内宽度，不受影响 ✓
- 实测（v2.119.166）：软件设置页「AI 模型与网址」「语音设置」两张卡片已铺满可用宽度，输入框同步拉伸 ✓
- 回退：releases/c3shell-2.119.165.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.33')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip(chr(10)) + """

## R71（2026-09-24 · v2.119.166 · 内容卡片自适应屏幕宽度）
用户：软件设置里面的卡片自适应屏幕
- 真因：基础 .card 写死 width:min(860px,96vw) ✗（宽屏右侧留白）→ 新增 main section>.card{width:auto;max-width:none} ✓；弹窗不受影响 ✓
- 实测截图：设置页两张卡片铺满可用宽度 ✓
## R71 复盘
- 一个"全局基础组件"（.card）同时服务**内容卡片 + 弹窗**时，改宽度要**按选择器限定作用域**（这里用 main section> 只命中内容区 ✓），否则会把弹窗也拉宽 ✗。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R71')
