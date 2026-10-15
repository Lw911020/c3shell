# -*- coding: utf-8 -*-
"""R2-b 补丁：① notrunning 误判为 running（→ 未投屏时黑长条/封面被隐藏）② 图片 MIME"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
W = os.path.join(D, 'java/com/padagent/c3shell/Web.java')

h = io.open(P, encoding='utf-8').read()
def rep(s, old, new, tag):
    assert s.count(old) == 1, tag + ': count=' + str(s.count(old))
    print('OK  ' + tag)
    return s.replace(old, new)

# ① 判定"投屏服务是否在跑"：第一行必须真正是 running，别被 notrunning 里的 running 骗到 ✗
h = rep(h, """  function ph(show){ try{ var p=e('castPh'); if(p) p.style.display=show?'block':'none'; }catch(x){} }""",
"""  function ph(show){ try{ var p=e('castPh'); if(p) p.style.display=show?'block':'none'; }catch(x){} }
  /* 2026-09-24 R2b：状态首行严格判定 ✓
     此前用 out.indexOf('running')>=0 —— "notrunning" 里也含 running ✗
     → 页面误以为在投屏：隐藏封面 + 挂一条连不上的流 → 未投屏时只剩一条黑长条 ✗ */
  function isRunning(out){ try{ var l=String(out||'').split('\\n')[0].trim().toLowerCase(); return l.indexOf('running')===0; }catch(x){ return false; } }""", 'isRunning 严格判定')

h = rep(h, """      if(((j2||{}).out||'').indexOf('running')>=0 && HOST){""",
"""      if(isRunning((j2||{}).out) && HOST){""", '自动接入改用 isRunning')

# ② 流断了/连不上时自动把封面放回来（不再留黑条）✓
h = rep(h, """    window.__floatNow = false;""",
"""    window.__floatNow = false;
    try{ var _im=e('castImg'); if(_im){ _im.onerror=function(){ ph(true); info('画面未连上（已显示封面 ✓）'); }; } }catch(x){}""", '画面加载失败 → 回封面')

io.open(P, 'w', encoding='utf-8').write(h)

w = io.open(W, encoding='utf-8').read()
w = rep(w, """        if (n.endsWith(".html")) return "text/html; charset=utf-8";""",
"""        if (n.endsWith(".html")) return "text/html; charset=utf-8";
        if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";     // 2026-09-24 R2b：封面/赞赏图给对 MIME ✓
        if (n.endsWith(".png")) return "image/png";
        if (n.endsWith(".webp")) return "image/webp";
        if (n.endsWith(".gif")) return "image/gif";""", 'Web.java 图片 MIME')
io.open(W, 'w', encoding='utf-8').write(w)
print('done')
