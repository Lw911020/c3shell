# -*- coding: utf-8 -*-
"""R48c：切页签后也做一次几何自检（否则拿到的是隐藏态 0x0）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

rep("""    fetch('/api/log',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({msg:s})}); }catch(x){} }""",
"""    fetch('/api/log',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({msg:s})}); }catch(x){}
  try{ window.__castGeo=geo; }catch(x){}""", '暴露 __castGeo')

rep("""      b.classList.add('on'); $('#tab-'+b.dataset.tab).classList.add('on');""",
"""      b.classList.add('on'); $('#tab-'+b.dataset.tab).classList.add('on');
      try{ if(window.__castGeo) setTimeout(function(){ window.__castGeo('tab='+b.dataset.tab); }, 350); }catch(e){}""",
    '切页签后自检')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
