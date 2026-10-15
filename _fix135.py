# -*- coding: utf-8 -*-
"""R47：投屏区域最小高度 500px（用户要求）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new)
    print('OK  ' + tag)

# ① CSS：画面区最小高度 500px + 内容垂直居中（黑边上下留、不再是一条矮条）
rep("#castBox{background:#000;border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative}",
    "#castBox{background:#000;border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative;min-height:500px;display:flex;flex-direction:column;justify-content:center}",
    'CSS #castBox min-height:500px')

# ② 适配：按可用高度算宽，但**高度下限 500px** ✓
rep("""      var availH=window.innerHeight-top-16;
      if(availH<130) availH=130;""",
"""      var availH=window.innerHeight-top-16;
      if(availH<500) availH=500;                        /* 2026-09-24 R47：用户要求"投屏区域高度最少 500px" ✓ */""",
    'fitPx 高度下限 500')

# ③ 状态行把"最小高度"写出来，方便核对 ✓
rep("""        rr.textContent='画面 '+sz+(fit?'适配（整屏可见 ✓）':((w>=1000)?'满宽':((w<=360)?'小':'中')))+' · 显示宽 '+bw+'px'; } }catch(x){}""",
"""        rr.textContent='画面 '+sz+(fit?'适配（高 ≥500px ✓）':((w>=1000)?'满宽':((w<=360)?'小':'中')))+' · 显示宽 '+bw+'px'; } }catch(x){}""",
    '状态行标注最小高度')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
