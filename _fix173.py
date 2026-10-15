# -*- coding: utf-8 -*-
"""R75：修 路线 qlog 点不动（跨块用 api()/sel() → ReferenceError）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① pollScan 的状态查询：改用 fetch（不再依赖跨块的 api ✓）
rep("""      api('/routes/scan/status',{}).then(function(j){""",
    """      fetch('/api/ssh/routes/scan/status').then(function(r){ return r.json(); }).then(function(j){""",
    'pollScan 改 fetch')

# ② routeScan 的启动请求：改用 post（本块有 ✓）+ 主机用 window.c3sel（主块已导出 ✓）
rep("""    api('/routes/scan/start',{method:'POST',json:(function(){ var p=(window.__aiScopeParams?window.__aiScopeParams():{limit:6}); p.hostId=sel(); return p })()}).then(function(res){""",
"""    post('/api/ssh/routes/scan/start',(function(){ var p=(window.__aiScopeParams?window.__aiScopeParams():{limit:6});
      try{ p.hostId = (window.c3sel?window.c3sel():''); }catch(x){} return p })()).then(function(res){""",
    'routeScan 改 post')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
