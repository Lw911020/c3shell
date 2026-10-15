# -*- coding: utf-8 -*-
"""R61：不靠 img.onload（MJPEG 下不触发），改主动轮询首帧 → 收到画面才收起提示"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 新增 waitFrame()：设了 src 之后每 400ms 看一次 naturalWidth，收到首帧就收起提示
rep("""  function geo(tag){ try{""",
"""  /* 2026-09-24 R61：WebView 里 MJPEG 的 img.onload 不触发 ✗ → 主动轮询首帧 ✓ */
  function waitFrame(){ try{
    var n=0;
    var iv=setInterval(function(){
      n++;
      var im=e('castImg');
      if(!RUN){ clearInterval(iv); return; }
      if(im && (im.naturalWidth||0)>0){ ph(false); clearInterval(iv); return; }
      if(n>30) clearInterval(iv);
    }, 400);
  }catch(x){} }
  function geo(tag){ try{""", '新增 waitFrame()')

# ② 三处接流后调用 waitFrame()
rep("""      ph(true,'连接中…','正在建立画面流');   /* 先出提示，再设 src：避免首帧先到导致提示留死 ✗ */
      e('castImg').src='http://'+HOST+':8090/?t='+Date.now();""",
"""      ph(true,'连接中…','正在建立画面流');   /* 先出提示，再设 src：避免首帧先到导致提示留死 ✗ */
      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); waitFrame();""", 'attach 后 waitFrame')

rep("""        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}   /* 先提示后设 src ✓ */
        try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}""",
"""        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}   /* 先提示后设 src ✓ */
        try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}
        try{ waitFrame(); }catch(x){}""", '自动接入后 waitFrame')

rep("""      setTimeout(function(){ ph(true,'连接中…','正在建立画面流'); e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
"""      setTimeout(function(){ ph(true,'连接中…','正在建立画面流'); e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); waitFrame(); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
    'castOn 后 waitFrame')

# ③ 看门狗里也顺手收起提示（有画面就别显示"连接中"）
rep("""    if((im.naturalWidth||0)===0) reattach('未收到画面');
  }catch(x){} }, 5000);""",
"""    if((im.naturalWidth||0)===0) reattach('未收到画面');
    else ph(false);                      /* 已经有画面 → 确保提示收起 ✓ */
  }catch(x){} }, 5000);""", '看门狗收提示')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
