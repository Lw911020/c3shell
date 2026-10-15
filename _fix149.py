# -*- coding: utf-8 -*-
"""R57b：停止时别被 img.onerror 覆盖成"连接中断"（只在 RUN 时才提示中断）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
old = """      _im.onerror=function(){ ph(true,'连接中断','正在自动重连…'); info('画面未连上（自动重连中 ✓）'); };"""
new = """      _im.onerror=function(){ if(!RUN) return; ph(true,'连接中断','正在自动重连…'); info('画面未连上（自动重连中 ✓）'); };"""
assert h.count(old) == 1, '未命中 onerror'
h = h.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  onerror 仅在投屏中提示中断')
