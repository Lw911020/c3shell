# -*- coding: utf-8 -*-
"""R55：默认改为"自适应"——以 648×324（画面本身）为基准，随 APP 窗口自动缩放"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 区域最小高度 = 画面本身高度（324）→ 画面正好贴满区域，不再有黑边
rep("min-height:340px;display:flex;flex-direction:column;justify-content:center}",
    "min-height:324px;display:flex;flex-direction:column;justify-content:center}   /* 2026-09-24 R55：以画面本身 648×324 为基准 ✓ */",
    'CSS min-height 324')

# ② 自适应下限 = 画面本身高度 324（宽 = 324*2 = 648 = 基准 ✓）
rep("""      if(availH<340) availH=340;                        /* 2026-09-24 R54：用户要求"高度 340" ✓ */""",
    """      if(availH<324) availH=324;                        /* 2026-09-24 R55：下限=画面本身高 324（宽 648）—— 窗口变小也不会比基准更小 ✓ */""",
    'fitPx 下限 324')

# ③ 默认档 = 自适应（换键丢弃旧值 650/9999）
rep("var HOST='', on=false, t2=null, busy=false, lastT=0, cw=650;   /* 2026-09-24 R51 用户要求：显示宽度 650 ✓ */",
    "var HOST='', on=false, t2=null, busy=false, lastT=0, cw='fit';   /* 2026-09-24 R55：默认「自适应」——随 APP 窗口自动调 ✓ */",
    '默认 cw=fit')
rep("""  try{ var sv=localStorage.getItem('c3castw7'); cw=(sv==='320'||sv==='650'||sv==='9999'||sv==='fit')?sv:'650'; }catch(x){}   /* 2026-09-24 R51：默认「650」✓ */""",
    """  try{ var sv=localStorage.getItem('c3castw8'); cw=(sv==='320'||sv==='650'||sv==='9999'||sv==='fit')?sv:'fit'; }catch(x){}   /* 2026-09-24 R55：默认「自适应」✓ */""",
    '存储键 c3castw8 默认 fit')
rep("try{ if(persist) localStorage.setItem('c3castw7',String(w)); }catch(x){}",
    "try{ if(persist) localStorage.setItem('c3castw8',String(w)); }catch(x){}", '持久化键升级')

# ④ 按钮：默认高亮「适配」，650 保留为手动档
rep("""          <button id="csF" class="ghost">适配</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="primary">650</button>
          <button id="csL" class="ghost">满宽</button>""",
"""          <button id="csF" class="primary">自适应</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="ghost">650</button>
          <button id="csL" class="ghost">满宽</button>""", '按钮默认「自适应」')

# ⑤ 状态行
rep("""rr.textContent='画面 '+sz+(fit?'适配（高 ≥340px ✓）'""",
    """rr.textContent='画面 '+sz+(fit?'自适应（随窗口 ✓）'""", '状态行标注自适应')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
