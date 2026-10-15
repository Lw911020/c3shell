# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.24（v2.119.148/149 · 2026-09-24 投屏"到底连上没有"要一眼看出来 + 掉流自愈）'
assert c.count(old) == 1
entry = """## v1.10.25（v2.119.150 · 2026-09-24 窗口失焦提示（"点击页面都没反应"的真因））
- 用户反馈「点击页面都没反应」→ 现场诊断：
  - APP 窗口本身正常（BASE_APPLICATION、可见、无遮挡、无 JS 报错、页面轮询正常）
  - 真因：**输入焦点不在 APP** —— dumpsys input 的 FocusedWindow 是 **桌面(launcher)** ✗
    → 真实触摸全落到桌面上 → "点哪儿都没反应" ✓（我自己用 input tap 也复现了：点"开始投屏"毫无反应）
  - 触发场景：平板息屏 + 锁屏解锁之后，自由窗口的输入焦点留在了桌面
- 现场处置：am start -n .MainActivity 把焦点夺回 APP ✓ → **真实触摸立刻恢复**（实测：点「小」→ 显示宽 320 ✓；点「650」→ 显示宽 650 ✓）
- 产品化：投屏卡片顶部加一条提示条（窗口失焦时显示）：
  「窗口未激活 · 点一下窗口（或标题栏）再操作 —— 自由窗口失焦时点击会落到别的窗口上」✓
  回焦时自动隐藏并重连画面流 ✓
- 回退：releases/c3shell-2.119.149.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.25')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R58（2026-09-24 · v2.119.150 · 窗口失焦 → 点击无效）
用户：「点击页面都没反应。」
- 诊断：页面/APP 都正常（无 JS 报错、轮询正常、窗口可见无遮挡），但 **dumpsys input 的 FocusedWindow = 桌面 launcher** ✗ → 真实触摸全落到桌面
- 复现：input tap 点"开始投屏" → 无任何 /api/cast/start、无 geo 变化 ✓（真复现了）
- 处置：am start -n .MainActivity 夺回焦点 → 真实触摸恢复（点「小」→ cw=320；点「650」→ cw=650 ✓ 都是 input tap 实测）
- 产品化：卡片顶部加"窗口未激活"提示条（blur 显示 / focus 隐藏 + 自动重连）✓
## R58 复盘
- **"点击没反应"先查输入焦点，不要先怀疑页面** ✓：dumpsys input 里的 FocusedWindow 一行就能定性 —— 这次它直接指出是 launcher ✗，比翻 JS 日志快得多 ✓。
- **验证要用真实触摸（input tap）**，不要只用无障碍点击：无障碍 ACTION_CLICK 会绕过命中测试，焦点不在 APP 时照样"成功" ✗ → 会得出"页面没问题"的错误结论 ✓。
- 多窗口（分屏/小窗）场景下，息屏-解锁、切窗口都可能让自由窗口丢焦点 → 产品上给**可见提示**比让用户猜便宜得多 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R58')
