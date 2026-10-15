# -*- coding: utf-8 -*-
"""R66：状态（投屏中/帧率）挪到悬浮窗按钮后面，不再单独一行"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
old = """        <div class="row" style="flex-wrap:wrap;margin-bottom:2px;align-items:center">
          <button id="castToggle" class="primary">开始投屏</button>
          <button id="flToggle" class="ghost">开启悬浮窗</button>
          <span style="flex:1 1 auto"></span>
          <button id="setBtn" class="ghost">⚙ 设置</button>
        </div>
        <div class="row" style="flex-wrap:wrap;margin-bottom:6px">
          <span class="note" id="castInfo">未开始</span>
          <span class="note" id="flInfo"></span>
        </div>"""
new = """        <div class="row" style="flex-wrap:wrap;margin-bottom:6px;align-items:center">
          <button id="castToggle" class="primary">开始投屏</button>
          <button id="flToggle" class="ghost">开启悬浮窗</button>
          <span class="note" id="castInfo">未开始</span>
          <span class="note" id="flInfo"></span>
          <span style="flex:1 1 auto"></span>
          <button id="setBtn" class="ghost">⚙ 设置</button>
        </div>"""
assert h.count(old) == 1, '未命中行结构'
h = h.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  状态并入第一行（悬浮窗按钮后面）')
