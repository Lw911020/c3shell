# -*- coding: utf-8 -*-
"""R63：把"连接中"变短 —— 去掉写死的 1.5s、去重复 start、首帧快速重试 + 计时"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① waitFrame：改成"快速重试"（没画面就每 500ms 重新挂一次，最多 ~6s），并在首帧时记时
rep("""  function waitFrame(){ try{
    var n=0;
    var iv=setInterval(function(){
      n++;
      var im=e('castImg');
      if(!RUN){ clearInterval(iv); return; }
      if(im && (im.naturalWidth||0)>0){ ph(false); clearInterval(iv); return; }
      if(n>30) clearInterval(iv);
    }, 400);
  }catch(x){} }""",
"""  function waitFrame(){ try{
    var n=0, t0=Date.now();
    var iv=setInterval(function(){
      n++;
      var im=e('castImg');
      if(!RUN || !HOST){ clearInterval(iv); return; }
      if(im && (im.naturalWidth||0)>0){ ph(false); clearInterval(iv); geo('firstframe +'+((Date.now()-t0)/1000).toFixed(1)+'s'); return; }
      if(n<=12){ try{ im.src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){} }   /* 服务还没起来就连不上 → 每 0.5s 重挂一次 ✓ */
      else clearInterval(iv);
    }, 500);
  }catch(x){} }""", 'waitFrame 快速重试 + 首帧计时')

# ② startCast：去掉写死的 1500ms、去掉重复 start、立刻挂画面 + 记时
rep("""  function startCast(){
    if(on) return; on=true; setCastBtn(true); info('启动中…');
    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ ph(true,'连接中…','正在建立画面流'); e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); waitFrame(); info('已连接 '+HOST+':8090'); poll(); }, 1500);
    }).catch(function(err){ info('启动失败：'+err.message); on=false; setCastBtn(false); });
  }""",
"""  function startCast(){
    if(on) return; on=true; setCastBtn(true); info('启动中…'); geo('startCast');
    RUN=true; ph(true,'连接中…','正在建立画面流');
    fetch('/api/cast/start').then(function(r){ return r.json(); }).then(function(){
      /* 2026-09-24 R63：不等 1.5s —— 立刻挂画面，连不上就由 waitFrame 每 0.5s 重试 ✓ */
      try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}
      waitFrame(); info('已连接 '+HOST+':8090'); poll();
    }).catch(function(err){ info('启动失败：'+err.message); on=false; RUN=false; setCastBtn(false); });
  }""", 'startCast 立即挂画面')

# ③ 自动接入也记时（对比用）
rep("""        try{ waitFrame(); }catch(x){}""", """        try{ geo('autoattach'); waitFrame(); }catch(x){}""", '自动接入记时')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
