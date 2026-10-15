# -*- coding: utf-8 -*-
"""R62：① 开始/停止合成一个按钮 ② 画质+悬浮窗第2行、HUD第3行 ③ 删掉「已点/面板」提示"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 按钮合并 + ② 行序（画质/悬浮窗第2行，HUD 第3行）
rep("""        <div class="row" style="flex-wrap:wrap;margin-bottom:4px">
          <button id="castOn" class="primary">开始投屏</button>
          <button id="castStop" class="ghost">停止</button>
          <span class="note">大小</span>
          <button id="csF" class="ghost">适配</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="primary">650</button>
          <button id="csL" class="ghost">满宽</button>
          <span class="note" id="castInfo">未开始</span>
        </div>
        <div id="hud" style="display:flex;flex-wrap:wrap;gap:0 12px;padding:0 2px 2px;background:transparent;border:0;font-size:11.5px;color:var(--dim);line-height:1.5">
          <span id="hudTemp">主板 –</span><span id="hudMem">内存 –</span><span id="hudCpu">负载 –</span><span id="hudIp">设备 –</span>
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
"""        <div class="row" style="flex-wrap:wrap;margin-bottom:4px">
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
        </div>
        <div id="hud" style="display:flex;flex-wrap:wrap;gap:0 12px;padding:0 2px 2px;background:transparent;border:0;font-size:11.5px;color:var(--dim);line-height:1.5">
          <span id="hudTemp">主板 –</span><span id="hudMem">内存 –</span><span id="hudCpu">负载 –</span><span id="hudIp">设备 –</span>
        </div>""", '按钮合并 + 行序调整')

# ③ 合并后的按钮逻辑
rep("""  if(e('castOn')) e('castOn').onclick=function(){
    if(on) return; on=true; info('启动中…');
    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ ph(true,'连接中…','正在建立画面流'); e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); waitFrame(); info('已连接 '+HOST+':8090'); poll(); }, 1500);
    }).catch(function(err){ info('启动失败：'+err.message); on=false; });
  };
  if(e('castStop')) e('castStop').onclick=function(){
    on=false; RUN=false; if(t2) clearTimeout(t2); t2=null; e('castImg').src=''; ph(true,'未连接','点「开始投屏」开始'); fetch('/api/cast/stop'); info('已停止（零开销 ✓）');
  };""",
"""  /* 2026-09-24 R62：开始/停止合成一个按钮 —— 未投屏显示「开始投屏」，投屏中显示「停止投屏」✓ */
  function setCastBtn(isOn){ try{
    var b=e('castToggle'); if(!b) return;
    b.textContent = isOn ? '停止投屏' : '开始投屏';
    b.className = isOn ? 'ghost' : 'primary';
  }catch(x){} }
  function startCast(){
    if(on) return; on=true; setCastBtn(true); info('启动中…');
    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ ph(true,'连接中…','正在建立画面流'); e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); waitFrame(); info('已连接 '+HOST+':8090'); poll(); }, 1500);
    }).catch(function(err){ info('启动失败：'+err.message); on=false; setCastBtn(false); });
  }
  function stopCast(){
    on=false; RUN=false; setCastBtn(false); if(t2) clearTimeout(t2); t2=null; e('castImg').src='';
    ph(true,'未连接','点「开始投屏」开始'); fetch('/api/cast/stop'); info('已停止（零开销 ✓）');
  }
  if(e('castToggle')) e('castToggle').onclick=function(){ if(on || RUN) stopCast(); else startCast(); };""",
    '合并按钮逻辑')

# 接流/断流时同步按钮文案
rep("""      ph(true,'连接中…','正在建立画面流');   /* 先出提示，再设 src：避免首帧先到导致提示留死 ✗ */""",
    """      setCastBtn(true);
      ph(true,'连接中…','正在建立画面流');   /* 先出提示，再设 src：避免首帧先到导致提示留死 ✗ */""",
    'attach 同步按钮')
rep("""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none'; ph(true,'画面在悬浮窗里','本页已暂停（省一份解码 ✓）');""",
    """    window.__castDetach = function(){ try{ RUN=false; on=false; setCastBtn(true); e('castImg').src=''; e('castTap').style.display='none'; ph(true,'画面在悬浮窗里','本页已暂停（省一份解码 ✓）');""",
    'detach 同步按钮')
rep("""        RUN=true; on=true;
        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}""",
    """        RUN=true; on=true; try{ setCastBtn(true); }catch(x){}
        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}""",
    '自动接入同步按钮')

# ④ 删掉「已点 / 面板」显示
rep("""        tinfo('已发送 ['+(mode==='tap'?'轻点':'滑动')+'] 面板('+Math.round(p1[0])+','+Math.round(p1[1])+')');""",
    """        /* 2026-09-24 R62 用户要求：删掉"面板(...)"这类显示 ✓ */""", '删「面板」显示(1)')
rep("""        tinfo('已点 ('+Math.round(nx*100)+'%, '+Math.round(ny*100)+'%) → 面板('+Math.round(p1[0])+','+Math.round(p1[1])+') ✓');""",
    """        /* 2026-09-24 R62：删「已点 ... → 面板(...)」显示 ✓ */""", '删「已点/面板」显示(2)')
rep("""        tinfo('已滑动 → 面板('+Math.round(p1[0])+','+Math.round(p1[1])+') ✓');""",
    """        /* 2026-09-24 R62：删「已滑动 → 面板(...)」显示 ✓ */""", '删「已滑动/面板」显示(3)')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
