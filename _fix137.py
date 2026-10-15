# -*- coding: utf-8 -*-
"""R48b：画面区几何自检（写 APP 日志）—— 用于精确核对最小高度/占位/图片尺寸"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 诊断函数（真实渲染尺寸 → /api/log）
rep("""  function ph(show){ try{ var p=e('castPh'); if(p) p.style.display=show?'block':'none'; }catch(x){} }""",
"""  function ph(show){ try{ var p=e('castPh'); if(p) p.style.display=show?'block':'none'; }catch(x){} }
  /* 2026-09-24 R48：几何自检 —— 画面区/占位/图片的真实渲染尺寸写进 APP 日志（用户要求"高度最少500px"要能量得出来 ✓） */
  function geo(tag){ try{
    var b=e('castBox'), p=e('castPh'), im=e('castImg'), r=b?b.getBoundingClientRect():null;
    var s='CASTGEO '+(tag||'')+' box='+(b?Math.round(b.clientWidth)+'x'+Math.round(b.clientHeight):'-')
      +' rect='+(r?(Math.round(r.left)+','+Math.round(r.top)):'-')
      +' ph='+(p?((p.style.display||'block')+'x'+Math.round(p.clientHeight)):'-')
      +' img='+(im?(Math.round(im.clientWidth)+'x'+Math.round(im.clientHeight)+' nat='+im.naturalWidth+'x'+im.naturalHeight):'-')
      +' cw='+cw+' vh='+window.innerHeight;
    fetch('/api/log',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({msg:s})}); }catch(x){} }""",
    'geo() 几何自检')

# ② wset 末尾上报
rep("""    try{ if(persist) localStorage.setItem('c3castw5',String(w)); }catch(x){} }""",
"""    try{ if(persist) localStorage.setItem('c3castw5',String(w)); }catch(x){}
    setTimeout(function(){ geo('wset'); }, 60); }""", 'wset 后上报')

# ③ 接流/断流上报
rep("""      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(false);
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){} };""",
"""      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(false);
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){}
      setTimeout(function(){ geo('attach'); }, 800); };""", 'attach 后上报')

rep("""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none'; ph(true);""",
"""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none'; ph(true); setTimeout(function(){ geo('detach'); }, 300);""",
    'detach 后上报')

# ④ 首屏 2 秒后上报一次
rep("""  try{ fetch('http://127.0.0.1:8091/').catch(function(){}); }catch(x){}   /* 探测占位（真正探测在拿到 HOST 后）*/""",
"""  try{ fetch('http://127.0.0.1:8091/').catch(function(){}); }catch(x){}   /* 探测占位（真正探测在拿到 HOST 后）*/
  setTimeout(function(){ geo('boot'); }, 2000);""", '首屏上报')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
