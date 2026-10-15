# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.29（v2.119.157 · 2026-09-24 投屏页控件重排：设置弹窗 + 悬浮窗开关）'
assert c.count(old) == 1
entry = """## v1.10.30（v2.119.158 · 2026-09-24 状态并到第一行）
- 用户要求：投屏中/帧率这类状态**跟在悬浮窗按钮后面**，不要单独占一行 ✓
- 第一行现在是：[开始/停止投屏] [开启/关闭悬浮窗] **投屏中 ✓ 已同步（C3 画面无变化）**（居中偏左）……（右侧）[⚙ 设置 · 当前档]
- 后面一行直接是主板/内存/负载/设备（原来的"状态单独一行"已删除）✓
- 实测截图（v2.119.158）：一行内四个元素 + 右侧设置按钮，无多余空行 ✓
- 回退：releases/c3shell-2.119.157.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.30')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R66（2026-09-24 · v2.119.158 · 状态并入第一行）
用户：投屏中/帧率显示放到悬浮窗按钮后面，不要单独一行
- 第一行：[投屏开关] [悬浮窗开关] [状态：投屏中 ✓ 已同步…] ……（右）[⚙ 设置 · 当前档]；下一行直接是 HUD ✓
- 实测截图核对 ✓；控件行数从 3 行降到 2 行，画面区更宽松 ✓
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R66')
