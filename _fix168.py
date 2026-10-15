# -*- coding: utf-8 -*-
"""R72b：清理剩余提及（状态文案）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)
rep("""（想快就用旁边的「设备/参数」✓；扫描中重复点击不会重启 ✓）*/""",
    """（聚焦接管日记；扫描中重复点击不会重启 ✓）*/""", '注释清理')
rep("""el('aiInfo').textContent='综合分析完成 ✓（设备/参数'+(LASTROUTE?'/路线':'')+(diag?'/采样':'')+' 已收录）';""",
    """el('aiInfo').textContent='综合分析完成 ✓（接管日记'+(LASTROUTE?'/路线':'')+(diag?'/采样':'')+' 已收录）';""",
    '完成文案改接管日记')
io.open(P, 'w', encoding='utf-8').write(h)
print('done')
