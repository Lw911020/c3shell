# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.13（v2.119.132 · 2026-09-24 承接上一轮：投屏页版面 + 主机连接）'
assert c.count(old) == 1
entry = """## v1.10.14（v2.119.133/134 · 2026-09-24 一级菜单"选中态"）
- 用户要求：**在用哪个模块，对应的一级菜单要高亮；其它未选中的要收起** ✓
- 真因：菜单里"是不是选中"原来只按 kind()（console/diag）判断 ✗ —— 而投屏 / AI 分析 / 界面设置 / 软件设置
  都是**控制台页里的二级页签** → 停在这几个页签时仍然高亮"控制台"，且它的子菜单一直展开 ✗
- 处理（page.html 与 diag.html 两份左栏菜单同步改）：
  - 新增 activeKey()：① 先认"当前激活的 section"（#tab-cast/#tab-aian/#tab-uiset/#tab-settings 谁带 on）② 回落看高亮的二级页签按钮 ③ 再回落看 URL 深链
  - 一级项与模块一一对应（控制台 / 投屏 / 转向诊断 / 设备查找 / AI 分析 / 软件设置 / 赞赏 / 界面设置 / 软件日志）→ 命中才高亮 ✓，未命中的一律**收起**子菜单（▸）✓
  - 点"当前模块"= 只切换展开/收起；点别的模块 = 跳过去（那边默认展开）✓
  - app 用 jsSwitchTab 切页签**不会重载页面** → 加 900ms 轻量 applyState() 把高亮/收起对齐（只改样式）✓
- 实测（v2.119.134 平板）：投屏页 → 投屏高亮 + 控制台收起 ✓；软件设置页 → 软件设置高亮 + 控制台收起 ✓
  （截图：_attic/now/v134_cast_menu.png、v134_set_menu.png）
- 回退：releases/c3shell-2.119.132.apk（无选中态那版）✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.14')

PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R46（2026-09-24 · v2.119.133/134 · 一级菜单选中态）
用户补充需求（承接 R45 的"菜单交互"）：**在用哪个模块，对应的一级菜单要有选中展示，其它未选中的要收起。**
| 现象 | 真因 | 处理 | 实测 |
|---|---|---|---|
| 停在任何页都高亮"控制台"，且它的子菜单一直展开 | 选中判定只看 kind()（console/diag），而投屏/AI分析/界面设置/软件设置都是控制台页的二级页签 ✗ | 新增 activeKey()：激活 section → 高亮页签按钮 → URL 深链，三级判定；9 个一级项各自对应模块 | 投屏页高亮"投屏" ✓ |
| 软件设置点进去不高亮 | 二级页签被搬进左栏后，**软件设置那个按钮脱离 DOM** → 查 nav.tabs button.on 查不到它 ✗ | 判定改为优先看"带 on 的 section"（section 始终在 <main> 里）✓ | 软件设置页高亮"软件设置" ✓ |
| app 切页签后高亮不刷新 | jsSwitchTab 是页内切页签，不重载 → 菜单不会重建 ✗ | 加 900ms 轻量 applyState()（只改样式，不重建 DOM，不打断用户的手动收起 ✓） | 两个模块来回切都跟得上 ✓ |
## R46 复盘
- **"选中的定义"要先问清**：我上一轮把"菜单没交互"理解成点击没反应 ✗，实际用户说的是**选中态**（高亮 + 收起）→ 需求描述含糊时先按用户原话再确认一次，比按自己的理解修便宜得多 ✓。
- **DOM 搬移会留下"孤儿节点"**：车机模式把二级页签搬进左栏时，软件设置那个按钮被留在了 DOM 之外 ✗ —— 凡是"按元素状态判定"的逻辑，都要考虑元素可能已脱离文档 ✓（改用 section 的 on 类最稳 ✓）。
- **页内切页签不重载** → 任何"随页面变化"的 UI 都要有刷新机制（这里用轻量定时 applyState ✓）；但刷新不能覆盖用户的临时操作（手动收起要保留）→ 状态里记 open ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R46')

H = os.path.join(D, 'HANDOVER.md')
h = io.open(H, encoding='utf-8').read()
assert h.count('- **2026-09-24 承接上一轮（R45）→ 当前版本 = v2.119.132** ✓ 已装平板并实测') == 1
h = h.replace('- **2026-09-24 承接上一轮（R45）→ 当前版本 = v2.119.132** ✓ 已装平板并实测',
"""- **2026-09-24 承接上一轮（R46）→ 当前版本 = v2.119.134** ✓ 已装平板并实测
  · 一级菜单**选中态**：在用哪个模块就高亮哪个，其它未选中的收起 ✓（投屏/软件设置两例实测 ✓）""")
io.open(H, 'w', encoding='utf-8').write(h)
print('OK  HANDOVER')
