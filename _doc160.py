# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.30（v2.119.158 · 2026-09-24 状态并到第一行）'
assert c.count(old) == 1
entry = """## v1.10.31（v2.119.159/160 · 2026-09-24「设备查找」从主菜单移到主机页）
- 用户要求：设备查找从主菜单并到「主机」页的**第二行后面** ✓
- 处理：
  - 「主机」页动作行末尾新增「设备查找」按钮：**[保存主机] [新增] [删除] [设备查找]** ✓（原来的第 1 行是说明文字，第 2 行就是这个动作行 ✓）
  - 三处一级菜单同步摘掉：page.html 车机左栏 ✓、diag.html 诊断台左栏 ✓、原生顶栏（平板/手机模式）✓
  - 按钮行为沿用原生雷达扫描（c3shell://tools?t=nonce）✓
- 实测（v2.119.160）：左栏一级菜单已无「设备查找」✓；主机页动作行出现该按钮 ✓；点它弹出雷达对话框「找到 1 台设备 · 192.168.31.49（当前）」✓
- 回退：releases/c3shell-2.119.158.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.31')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R67（2026-09-24 · v2.119.159/160 · 设备查找移到主机页）
用户：设备查找从主菜单并到主机页第二行后面
- 主机页动作行 → [保存主机][新增][删除][设备查找] ✓；三处一级菜单同步移除（page/diag 左栏 + 原生顶栏）✓
- 实测：左栏无「设备查找」✓；点主机页那个按钮弹出雷达扫描对话框 ✓
## R67 复盘
- 菜单项搬家要**一次搜全所有"菜单实现"**：这个项目的一级菜单有 3 份（车机左栏 page.html、诊断台左栏 diag.html、原生顶栏 MainActivity）✗ —— 只改一份就会出现"车机没了、平板还在"✓。
- 补丁脚本里 assert 失败会**中断后续替换**：这次 diag/原生两处没改上（脚本报错但构建照跑 ✗）→ 以后多处编辑要**先全部校验再统一写盘**，或者失败即停并明确提示 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R67')
