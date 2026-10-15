# -*- coding: utf-8 -*-
"""R54：画面区最小高度 360 → 340"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)
rep("min-height:360px;display:flex;flex-direction:column;justify-content:center}",
    "min-height:340px;display:flex;flex-direction:column;justify-content:center}", 'CSS min-height 340')
rep("""      if(availH<360) availH=360;                        /* 2026-09-24 R53：用户要求"高度 360" ✓ */""",
    """      if(availH<340) availH=340;                        /* 2026-09-24 R54：用户要求"高度 340" ✓ */""",
    'fitPx 下限 340')
rep("""rr.textContent='画面 '+sz+(fit?'适配（高 ≥360px ✓）'""",
    """rr.textContent='画面 '+sz+(fit?'适配（高 ≥340px ✓）'""", '状态行标注 340')
io.open(P, 'w', encoding='utf-8').write(h)
print('done')
