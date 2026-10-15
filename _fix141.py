# -*- coding: utf-8 -*-
"""R50：投屏显示宽度默认 600（新增/替换中间档；默认档 = 600）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 按钮：默认高亮 600（适配改为普通）
rep("""          <button id="csF" class="primary">适配</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="ghost">中</button>
          <button id="csL" class="primary">满宽</button>""",
"""          <button id="csF" class="ghost">适配</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="primary">600</button>
          <button id="csL" class="ghost">满宽</button>""", '按钮默认 600')

# ② 默认值
rep("var HOST='', on=false, t2=null, busy=false, lastT=0, cw='fit';   /* 默认「适配」：整屏可见 ✓ */",
    "var HOST='', on=false, t2=null, busy=false, lastT=0, cw=600;   /* 2026-09-24 R50 用户要求：显示宽度 600 ✓ */",
    '默认 cw=600')

# ③ 存储键升级（丢弃旧值，保证用户看到 600）
rep("""  try{ var sv=localStorage.getItem('c3castw5'); cw=(sv==='320'||sv==='480'||sv==='9999'||sv==='fit')?sv:'fit'; }catch(x){}   /* 默认「适配」✓ */""",
"""  try{ var sv=localStorage.getItem('c3castw6'); cw=(sv==='320'||sv==='600'||sv==='9999'||sv==='fit')?sv:'600'; }catch(x){}   /* 2026-09-24 R50：默认「600」✓ */""",
    '存储键 c3castw6 默认 600')

rep("try{ if(persist) localStorage.setItem('c3castw5',String(w)); }catch(x){}",
    "try{ if(persist) localStorage.setItem('c3castw6',String(w)); }catch(x){}", '持久化键升级')

# ④ 点击 600 档
rep("if(e('csM')) e('csM').onclick=function(){ wset(480,1); };",
    "if(e('csM')) e('csM').onclick=function(){ wset(600,1); };", 'csM → 600')

# ⑤ 状态行档位名：中间档直接显示数字
rep("""'画面 '+sz+(fit?'适配（高 ≥400px ✓）':((w>=1000)?'满宽':((w<=360)?'小':'中')))+' · 显示宽 '+bw+'px'""",
    """'画面 '+sz+(fit?'适配（高 ≥400px ✓）':((w>=1000)?'满宽':((w<=360)?'小':String(w))))+' · 显示宽 '+bw+'px'""",
    '状态行档位名显示数字')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
