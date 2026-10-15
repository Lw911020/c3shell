# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.31（v2.119.159/160 · 2026-09-24「设备查找」从主菜单移到主机页）'
assert c.count(old) == 1
entry = """## v1.10.32（v2.119.161~165 · 2026-09-24 AI 分析页四修 · 全部实测通过）
- 用户反馈四条：① 分析进度不显示（要能看"多少条/当前第几条"）② 综合分析要**一起出来** ③ 报告交给大数据平台的按钮＝下载，不要单独的"导出到下载" ④ 本地规则建议点了没反应
- ① 进度（真因在设备侧脚本）：scan_routes.py 原来 **每 25 条才写一次进度** ✗ → 扫 6 条时全程只有"正在启动扫描…"
  · 改成 **每条都写** + 开扫先写 0 进度 + 带上**当前正在读的段名** ✓；页面文案变成「扫描中 5/6 条（83.3%）· 正在读 00000024--… 约还要 0.7 秒」✓
  · 注：设备侧旧脚本由 App 按**文件大小**判断是否重传 ✓（本次已自动更新到 14128 字节 ✓）
- ② 综合分析一次性出结果：原来"启动扫描"后立刻渲染 ①②④⑤，路线 ③ 完成后才追加 ✗
  · 新增 waitScanDone()：**等扫描真正结束**（期间显示进度）→ 再一次性渲染全部 ✓
- ③ 报告下载（真因：页面里的 window.saveFile **从未定义** ✗，所以"导出到「下载」"点了没反应）
  · 新增原生端点 **/api/save**（MediaStore 写系统「下载」目录，失败回落 APP 外部目录）✓
  · 「交给大数据平台」→ 改名 **「下载报告（交大数据平台）」**：直接下载 .txt，并在弹窗里给出路径与预览 ✓
  · 删掉多余的「导出到「下载」」按钮 ✓（__c3exportReport 也改走 /api/save ✓）
- ④ 本地规则建议（真因：**跨 script 块取不到变量 → LAST is not defined** ✗）
  · 分析结果变量 LAST/LASTCTX/LASTROUTE 全部同步到 window，报告块改读 window.* ✓
  · 点击立即回"正在按本地规则库计算…"，并包 try/catch（错误也会显示出来，不再静默）✓
- 实测（v2.119.165）：进度条 5/6 条 + 当前段名 ✓；综合分析一次性出全部结果 ✓；
  本地规则建议输出「规则库共 71 条 + 命中 3 条高/中建议」✓；下载报告 → /sdcard/Download/c3-report-*.txt（2483 字节）✓
- 回退：releases/c3shell-2.119.160.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.32')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip(chr(10)) + """

## R68/R69（2026-09-24 · v2.119.161~165 · AI 分析页四修）
用户：① 进度不显示（要"多少条/第几条"）② 综合分析要一起出来 ③ 报告＝下载 ④ 本地规则建议点了没反应
- ① 设备侧 scan_routes.py 原来每 25 条才写进度 → 小范围全程看不到 ✗ → 改成每条都写 + 带当前段名 + 开扫先写 0 ✓（App 按文件大小自动重传 ✓）
- ② analyzeAll 原来"启动扫描"就渲染，路线结果后补 ✗ → 新增 waitScanDone() 等扫完再一次性渲染 ✓
- ③ 页面里的 window.saveFile 从未定义 ✗ → 新增原生 /api/save（写系统「下载」目录）；「交给大数据平台」改为「下载报告」；删掉重复按钮 ✓
- ④ 跨 script 块取不到变量 → LAST is not defined ✗（报告与规则建议都受影响）→ LAST/LASTCTX/LASTROUTE 同步到 window 并改读 window.* ✓
- 实测：进度（5/6 条+段名）✓ · 综合分析一次出全 ✓ · 规则建议（71 条库/命中 3 条）✓ · 下载到 /sdcard/Download/ ✓
## R68/R69 复盘
- **"点了没反应"多半是静默失败**：这次两处（导出、规则建议）都是未定义变量被吞掉 ✗ → 点击入口一律立即回"正在…"并 try/catch 出可见错误 ✓。
- **跨块共享靠 window**：页面是多个 IIFE，变量不共享 → 报告/规则这类跨块读分析结果的场景一律显式 window 化 ✓。
- **补丁脚本转义坑（今天第二次）**：Python 三引号里写反斜杠 n 会变成真换行导致匹配失败；多行替换改**单行子串**更稳 ✓；assert 失败会中断后续替换 → 分批写盘、失败重跑 ✓。
- **设备侧脚本重传机制**：ensureRemote 只比文件大小 → 改动改变长度就会自动更新 ✓（改完先确认大小变了再指望生效 ✓）。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R68/R69')
