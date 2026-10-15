# -*- coding: utf-8 -*-
"""R51：投屏显示宽度 600 → 650（用户指定）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

rep('<button id="csM" class="primary">600</button>', '<button id="csM" class="primary">650</button>', '按钮 650')
rep("busy=false, lastT=0, cw=600;   /* 2026-09-24 R50 用户要求：显示宽度 600 ✓ */",
    "busy=false, lastT=0, cw=650;   /* 2026-09-24 R51 用户要求：显示宽度 650 ✓ */", '默认 cw=650')
rep("""  try{ var sv=localStorage.getItem('c3castw6'); cw=(sv==='320'||sv==='600'||sv==='9999'||sv==='fit')?sv:'600'; }catch(x){}   /* 2026-09-24 R50：默认「600」✓ */""",
    """  try{ var sv=localStorage.getItem('c3castw7'); cw=(sv==='320'||sv==='650'||sv==='9999'||sv==='fit')?sv:'650'; }catch(x){}   /* 2026-09-24 R51：默认「650」✓ */""",
    '存储键 c3castw7 默认 650')
rep("try{ if(persist) localStorage.setItem('c3castw6',String(w)); }catch(x){}",
    "try{ if(persist) localStorage.setItem('c3castw7',String(w)); }catch(x){}", '持久化键升级')
rep("if(e('csM')) e('csM').onclick=function(){ wset(600,1); };",
    "if(e('csM')) e('csM').onclick=function(){ wset(650,1); };", 'csM → 650')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
