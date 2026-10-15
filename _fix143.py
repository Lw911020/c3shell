# -*- coding: utf-8 -*-
"""R52：画面区最小高度 400 → 380（用户指定）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

rep("min-height:400px;display:flex;flex-direction:column;justify-content:center}",
    "min-height:380px;display:flex;flex-direction:column;justify-content:center}", 'CSS min-height 380')
rep("""      if(availH<400) availH=400;                        /* 2026-09-24 R49：用户要求"高度该到 400" ✓ */""",
    """      if(availH<380) availH=380;                        /* 2026-09-24 R52：用户要求"高度 380" ✓ */""",
    'fitPx 下限 380')
rep("""rr.textContent='画面 '+sz+(fit?'适配（高 ≥400px ✓）'""",
    """rr.textContent='画面 '+sz+(fit?'适配（高 ≥380px ✓）'""", '状态行标注 380')
io.open(P, 'w', encoding='utf-8').write(h)
print('done')
