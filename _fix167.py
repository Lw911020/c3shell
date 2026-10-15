# -*- coding: utf-8 -*-
"""R72：AI 分析删掉「设备/参数」入口，聚焦行车接管日记（路线 qlog）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 删按钮
rep("""          <button id="aiScan" class="ghost">设备/参数</button>
""", "", '删「设备/参数」按钮')
# ② 删 handler
rep("""  if(el('aiScan')) el('aiScan').onclick=scan;
""", "", '删 handler')
# ③ 提示文案：改成以"接管日记（路线 qlog）"为主
rep("""综合=完整分析（含真扫描 1~3 分钟）｜设备/参数=秒出｜路线=只扫路线（带进度）｜档案=存 A–H/Z 可回滚｜问AI=带设备数据提问""",
"""综合分析=接管日记（路线 qlog，带进度，约 1~3 分钟）｜路线 qlog=只扫路线｜档案=存 A–H/Z 可回滚｜问 AI=带接管数据提问""",
    '提示文案改为接管日记')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
