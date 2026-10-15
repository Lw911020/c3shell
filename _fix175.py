# -*- coding: utf-8 -*-
"""R76b：dataOnly 时不要清空 aiList（否则会把接管日志表清掉 ✗）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
old = """    var box=el('aiList'); box.innerHTML='';
    var j=out.all||{}, v=j.values||{}, d=j.defaults||{}, meta=j.meta||{}, groups=j.groups||{};"""
new = """    var j=out.all||{}, v=j.values||{}, d=j.defaults||{}, meta=j.meta||{}, groups=j.groups||{};"""
assert h.count(old) == 1, '定位失败(1)'
h = h.replace(old, new)
old2 = """    if(dataOnly) return;                       /* 数据已就绪 → 不渲染 ①②③ ✓ */"""
new2 = """    if(dataOnly) return;                       /* 数据已就绪 → 不渲染、也不清空列表 ✓ */
    var box=el('aiList'); box.innerHTML='';"""
assert h.count(old2) == 1, '定位失败(2)'
h = h.replace(old2, new2)
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  dataOnly 不再清空列表')
