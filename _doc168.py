# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.33（v2.119.166 · 2026-09-24 内容卡片跟随屏幕宽度）'
assert c.count(old) == 1
entry = """## v1.10.34（v2.119.167/168 · 2026-09-24 AI 分析删「设备/参数」入口，聚焦接管日记）
- 用户要求：AI 分析删掉设备与参数的分析（没什么作用），只分析行车接管日记 ✓
- 处理：删掉「设备/参数」按钮与它的 handler ✓；提示文案改为「综合分析=接管日记（路线 qlog，带进度，约 1~3 分钟）｜路线 qlog=只扫路线｜档案=存 A–H/Z 可回滚｜问 AI=带接管数据提问」✓；
  完成文案改为「综合分析完成 ✓（接管日记/路线/采样 已收录）」✓；全库已无「设备/参数」字样 ✓
- 现在这一页的入口：**综合分析 / 路线 qlog / 存为档案… / 问 AI** ✓（实测截图 v2.119.168）
- 回退：releases/c3shell-2.119.166.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.34')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip(chr(10)) + """

## R72（2026-09-24 · v2.119.167/168 · AI 分析聚焦接管日记）
用户：删掉设备与参数的分析（没什么作用），只分析行车接管日记
- 删「设备/参数」按钮 + handler ✓；提示/完成文案统一改成"接管日记（路线 qlog）"✓；全库无残留字样 ✓
- 保留：综合分析（含接管明细 ③ + 结论 ⑤）/ 路线 qlog / 存为档案 / 问 AI ✓
## R72 复盘
- 用户说"删掉某入口"时，除了按钮还要**清掉同名的提示文案与完成文案**（否则界面自相矛盾 ✗）→ 这次一起做了并 grep 校验为 0 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R72')
