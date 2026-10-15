# -*- coding: utf-8 -*-
"""R48：4:3 窗口（940x705 CSS）下压控制区，给 500px 画面区腾地方"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new)
    print('OK  ' + tag)

# ① 控制区压缩：4 行 + HUD 块 → 2 行 + 一行细字 HUD（悬浮窗与画质同行 ✓ 也正好落在"画质按钮后面"）
old_rows = """        <div id="hud" style="display:flex;flex-wrap:wrap;gap:6px 14px;padding:8px 10px;background:var(--bg2);border:1px solid var(--line);border-radius:10px;font-size:12px;color:var(--dim)">
          <span id="hudTemp">主板 –</span><span id="hudMem">内存 –</span><span id="hudCpu">负载 –</span><span id="hudIp">设备 –</span>
        </div>
        <div class="row" style="flex-wrap:wrap">
          <span class="note">画质</span>
          <button id="qLow" class="ghost">低（最顺）</button>
          <button id="qMid" class="primary">中</button>
          <button id="qHigh" class="ghost">高（最清）</button>
          <span class="note" id="qInfo">中 · 1024×600</span>
        </div>
        <div class="row" style="flex-wrap:wrap;border-top:1px solid var(--line);padding-top:8px">
          <span class="note"><b>桌面悬浮窗</b></span>
          <button id="flOn" class="ghost">开启悬浮窗</button>
          <button id="flOff" class="ghost">关闭悬浮窗</button>
          <span class="note" id="flInfo">—</span>
        </div>"""
new_rows = """        <div id="hud" style="display:flex;flex-wrap:wrap;gap:0 12px;padding:0 2px 2px;background:transparent;border:0;font-size:11.5px;color:var(--dim);line-height:1.5">
          <span id="hudTemp">主板 –</span><span id="hudMem">内存 –</span><span id="hudCpu">负载 –</span><span id="hudIp">设备 –</span>
        </div>
        <div class="row" style="flex-wrap:wrap;margin-bottom:6px">
          <span class="note">画质</span>
          <button id="qLow" class="ghost">低（最顺）</button>
          <button id="qMid" class="primary">中</button>
          <button id="qHigh" class="ghost">高（最清）</button>
          <span class="note" id="qInfo">中 · 1024×600</span>
          <span class="note" style="margin-left:8px"><b>悬浮窗</b></span>
          <button id="flOn" class="ghost">开启</button>
          <button id="flOff" class="ghost">关闭</button>
          <span class="note" id="flInfo">—</span>
        </div>"""
rep(old_rows, new_rows, '控制区压缩（2 行 + 细字 HUD）')

# 状态行也压紧一点
rep("""        <div class="row" style="flex-wrap:wrap">
          <button id="castOn" class="primary">开始投屏</button>""",
"""        <div class="row" style="flex-wrap:wrap;margin-bottom:4px">
          <button id="castOn" class="primary">开始投屏</button>""", '第一行 margin')

# ② HUD 的 CSS 规则跟着改成"无底色无边框"（否则 !important 又把底色盖回来）
rep("#hud{background:var(--bg2) !important;color:var(--dim) !important;border-color:var(--line) !important}",
    "#hud{background:transparent !important;color:var(--dim) !important;border:0 !important}",
    'CSS #hud 无底色')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
