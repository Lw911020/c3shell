# -*- coding: utf-8 -*-
"""R49：画面区最小高度 500 → 400（用户改口）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

rep("min-height:500px;display:flex;flex-direction:column;justify-content:center}",
    "min-height:400px;display:flex;flex-direction:column;justify-content:center}", 'CSS min-height 400')

rep("""      var availH=window.innerHeight-top-16;
      if(availH<500) availH=500;                        /* 2026-09-24 R47：用户要求"投屏区域高度最少 500px" ✓ */""",
"""      var availH=window.innerHeight-top-16;
      if(availH<400) availH=400;                        /* 2026-09-24 R49：用户要求"高度该到 400" ✓ */""",
    'fitPx 下限 400')

rep("""rr.textContent='画面 '+sz+(fit?'适配（高 ≥500px ✓）'""",
    """rr.textContent='画面 '+sz+(fit?'适配（高 ≥400px ✓）'""", '状态行标注 400')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
