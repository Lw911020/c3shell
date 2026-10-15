# -*- coding: utf-8 -*-
"""R65：大小/画质收进「设置」弹窗（右侧）；悬浮窗做成一个开关放投屏按钮后"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 第一行：投屏开关 + 悬浮窗开关 +（右）设置；状态行单独一行
rep("""        <div class="row" style="flex-wrap:wrap;margin-bottom:4px">
          <button id="castToggle" class="primary">开始投屏</button>
          <span class="note">大小</span>
          <button id="csF" class="ghost">适配</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="primary">650</button>
          <button id="csL" class="ghost">满宽</button>
          <span class="note" id="castInfo">未开始</span>
        </div>
        <div class="row" style="flex-wrap:wrap;margin-bottom:6px">
          <span class="note">画质</span>
          <button id="qLow" class="ghost">低（最顺）</button>
          <button id="qMid" class="primary">中</button>
          <button id="qHigh" class="ghost">高（最清）</button>
          <span class="note" id="qInfo">中 · 1024×600</span>
          <span class="note" style="margin-left:8px"><b>悬浮窗</b></span>
          <button id="flOn" class="ghost">开启</button>
          <button id="flOff" class="ghost">关闭</button>
          <span class="note" id="flInfo">—</span>
        </div>""",
"""        <div class="row" style="flex-wrap:wrap;margin-bottom:2px;align-items:center">
          <button id="castToggle" class="primary">开始投屏</button>
          <button id="flToggle" class="ghost">开启悬浮窗</button>
          <span style="flex:1 1 auto"></span>
          <button id="setBtn" class="ghost">⚙ 设置</button>
        </div>
        <div class="row" style="flex-wrap:wrap;margin-bottom:6px">
          <span class="note" id="castInfo">未开始</span>
          <span class="note" id="flInfo"></span>
        </div>""", '第一行重排')

# ② 设置弹窗（大小 + 画质）插到 castCard 与 setDisp 之间
rep("""    </div>
      <div class="card" id="setDisp" style="display:none">""",
"""    </div>
      <div class="modal" id="castSetModal">
        <div class="card" style="width:min(420px,94vw)">
          <h3>投屏设置</h3>
          <div class="body">
            <div class="row" style="margin-bottom:8px;align-items:center">
              <span class="note" style="min-width:52px">大小</span>
              <button id="csF" class="ghost">适配</button><button id="csS" class="ghost">小</button>
              <button id="csM" class="primary">650</button><button id="csL" class="ghost">满宽</button>
            </div>
            <div class="row" style="align-items:center">
              <span class="note" style="min-width:52px">画质</span>
              <button id="qLow" class="ghost">低（最顺）</button>
              <button id="qMid" class="primary">中</button>
              <button id="qHigh" class="ghost">高（最清）</button>
              <span class="note" id="qInfo">中 · 1024×600</span>
            </div>
          </div>
          <div class="foot"><button id="castSetDone" class="primary">完成</button></div>
        </div>
      </div>
      <div class="card" id="setDisp" style="display:none">""", '设置弹窗')

# ③ 悬浮窗单按钮 + 设置弹窗逻辑（替换旧的 flOn/flOff 处理）
rep("""  if(e('flOn')) e('flOn').onclick=function(){
    try{ localStorage.setItem('c3float','1'); }catch(x){}
    try{ location.href='c3shell://float?on=1'; }catch(x){}
    setTimeout(function(){ var i=e('flInfo'); if(i) i.textContent='已请求开启 ✓（若没出现请检查系统权限 ✓）'; }, 300);
  };
  if(e('flOff')) e('flOff').onclick=function(){
    try{ localStorage.setItem('c3float','0'); }catch(x){}
    try{ location.href='c3shell://float?on=0'; }catch(x){}
    setTimeout(function(){ var i=e('flInfo'); if(i) i.textContent='已请求关闭 ✓'; }, 300);
  };""",
"""  /* 2026-09-24 R65（用户要求）：大小/画质收进「设置」弹窗（按钮在右侧）；
     悬浮窗做成一个开关按钮，跟在投屏按钮后面 ✓ */
  function setLabel(){ try{
    var b=e('setBtn'); if(!b) return;
    var t=(cw==='fit')?'自适应':((cw>=1000)?'满宽':(String(cw)+'px'));
    b.textContent='⚙ 设置 · '+t;
  }catch(x){} }
  function flUI(on){ try{
    var b=e('flToggle'); if(!b) return;
    b.textContent = on ? '关闭悬浮窗' : '开启悬浮窗';
  }catch(x){} }
  function flNow(){ try{
    fetch('/api/float/status').then(function(r){return r.json()}).then(function(j){ flUI(!!(j&&j.running)); }).catch(function(){});
  }catch(x){} }
  if(e('setBtn')) e('setBtn').onclick=function(){ try{ e('castSetModal').classList.add('on'); }catch(x){} };
  if(e('castSetDone')) e('castSetDone').onclick=function(){ try{ e('castSetModal').classList.remove('on'); }catch(x){} };
  try{ e('castSetModal').addEventListener('click', function(ev){ if(ev.target===e('castSetModal')) e('castSetModal').classList.remove('on'); }); }catch(x){}
  if(e('flToggle')) e('flToggle').onclick=function(){
    var wantOn = (String(e('flToggle').textContent||'').indexOf('关闭')<0);   /* 当前是"开启悬浮窗" → 请求开启 ✓ */
    try{ localStorage.setItem('c3float', wantOn?'1':'0'); }catch(x){}
    try{ location.href='c3shell://float?on='+(wantOn?'1':'0'); }catch(x){}
    try{ var i=e('flInfo'); if(i) i.textContent = wantOn?'已请求开启 ✓（若没出现请检查系统权限）':'已请求关闭 ✓'; }catch(x){}
    setTimeout(flNow, 1500);
  };
  flNow();""", '悬浮窗单按钮 + 设置弹窗逻辑')

# ④ wset 更新设置按钮上的档位 + 画质切换后刷新
rep("""    setTimeout(function(){ geo('wset'); }, 60); }""",
    """    try{ setLabel(); }catch(x){}
    setTimeout(function(){ geo('wset'); }, 60); }""", 'wset 刷新设置按钮')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
