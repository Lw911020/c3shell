# -*- coding: utf-8 -*-
"""R59：① 删掉封面占位图（未连接只显示文字）② 状态行改成真实 fps / "已同步" """
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 占位改纯深色（不再用照片）
rep("#castPh{width:100%;padding-top:50%;background:#0b0f14 url(/castcover.jpg) center/cover no-repeat}",
    "#castPh{width:100%;padding-top:50%;background:#0b0f14}   /* 2026-09-24 R59：用户要求删掉封面占位图 ✓ */",
    'CSS 占位改纯色')
rep("""  <div id="castPhTip" style="display:none;position:absolute;left:0;top:0;right:0;bottom:0;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#e6edf3;background:rgba(6,10,16,.55);text-align:center;padding:10px;pointer-events:none">""",
    """  <div id="castPhTip" style="display:none;position:absolute;left:0;top:0;right:0;bottom:0;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#e6edf3;background:transparent;text-align:center;padding:10px;pointer-events:none">""",
    '提示层不再压暗')

# ② 状态行：真实 fps（帧数增量）／无变化时显示"已同步"
rep("""  function poll(){
    if(!on) return;
    fetch('/api/cast/status').then(function(r){return r.json()}).then(function(j){
      var o=(j.out||'');
      info('投屏中 ✓ 帧 '+((o.match(/frames=(\\d+)/)||[])[1]||'?')+' · '+((o.match(/ms=([0-9.]+)/)||[])[1]||'?')+'ms/帧');
    }).catch(function(){});
    t2=setTimeout(poll, 5000);
  }""",
"""  /* 2026-09-24 R59：帧数只在"UI 真的重绘"时才会涨（钩子挂在 eglSwapBuffers 上 ✓）
     → 静态画面显示"帧 1/2"会让用户以为卡死 ✗ → 改成真实 fps + "已同步（画面无变化）" ✓ */
  var _pf=-1, _pt=0;
  function poll(){
    if(!on) return;
    fetch('/api/cast/status').then(function(r){return r.json()}).then(function(j){
      var o=(j.out||'');
      var fr=parseInt(((o.match(/frames=(\\d+)/)||[])[1]||'-1'),10);
      var ms=((o.match(/ms=([0-9.]+)/)||[])[1]||'?');
      var t=Date.now(), fps=null;
      if(_pf>=0 && fr>=0 && (t-_pt)>0){ var d=fr-_pf, dt=(t-_pt)/1000.0; if(dt>0) fps=d/dt; }
      _pf=fr; _pt=t;
      if(fps===null) info('投屏中 ✓ 同步中…');
      else if(fps>=0.2) info('投屏中 ✓ '+fps.toFixed(1)+' fps · '+ms+'ms/帧');
      else info('投屏中 ✓ 已同步（C3 画面无变化）');
    }).catch(function(){});
    t2=setTimeout(poll, 5000);
  }""", '状态行改真实 fps')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
