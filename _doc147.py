# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.22（v2.119.146 · 2026-09-24 以画面 648×324 为基准「自适应」）'
assert c.count(old) == 1
entry = """## v1.10.23（v2.119.147 · 2026-09-24 回退到 145 的内容）
- 用户要求「退回145」。系统**拒绝降级**（versionCode 445 < 446，连 adb install -r -d 也被拒 ✗）；按项目一贯做法：
  把 145 的页面**原样取回源码**（tools/extract_assets.py → assets/page.html），再打成**版本号更高**的 2.119.147 ✓
  → 不用卸载重装，**不丢主机配置与内置密钥** ✓（卸载会清 APP 私有目录 ✗）
- 145 的内容特征（已确认）：#castBox min-height **340**、默认显示宽 **650**、适配下限 340、存储键 c3castw7 ✓
- 实测（4:3 窗口，视口 940×581）：画面区 648×**338**（边框盒 650×**340**）、状态行「画面 1200×600 px · 650 · 显示宽 650px」✓；
  未投屏时封面占位 324 高并居中 ✓
- 相关包：releases/c3shell-2.119.145.apk（同内容的原始 145）、2.119.146.apk（自适应那版，已被回退）/ 2.119.147.apk（当前）✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.23')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R56（2026-09-24 · v2.119.147 · 回退到 145 内容）
用户：「退回145」。
- 直接降级被系统拒（INSTALL_FAILED_VERSION_DOWNGRADE 445<446，-d 也不行 ✗）→ 用项目老办法：**把 145 的 page.html 从 APK 里原样取回源码，打成版本号更高的 2.119.147** ✓（不卸载 → 不丢主机配置/密钥 ✓）
- 实测（4:3，视口 940×581）：画面区 648×338（边框盒 650×340）、显示宽 650px ✓；未投屏时封面占位 324 高居中 ✓
## R56 复盘
- "退回某版"在这个项目里有两个选项：① 卸载重装旧包（**会清 APP 私有目录的密钥** ✗，HANDOVER 明确警告过）② **旧页面 + 新版本号重打包** ✓ —— 永远选 ②，除非用户明确要求连数据一起清 ✓。
- 顺带补上了上轮欠的实机核对（R55 只做了静态核对）✓：这轮 147 的 CASTGEO 数据也说明"回退后几何尺寸与 145 完全一致" ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R56')
