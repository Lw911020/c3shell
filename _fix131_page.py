# -*- coding: utf-8 -*-
"""2026-09-24 R2 补丁：投屏页版面 + 大小档 + 悬浮窗默认 + 主机连接（见 PROJECT-LOG R45）"""
import io, os, re, shutil, sys

D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
log = []

def rep(old, new, cnt=1, tag=''):
    global h
    n = h.count(old)
    assert n == cnt, 'replace %s: found %d, expect %d' % (tag, n, cnt)
    h = h.replace(old, new)
    log.append('OK  ' + tag)

# ── ① CSS：去掉整页/整卡黑底与 !important 宽度覆盖 ──────────────────────────
old_css = """/* 2026-09-24 用户要求：投屏页黑底 + 画面自适应并置于最下 ✓ */
#tab-cast{background:#000}
#castCard{background:#000;border-color:#1b2430}
#castCard h4{color:#e6edf3}
#castCard .body>#castBox{order:50}
#castCard .body>#castRes{order:51}
#castCard .body>#tcInfo{order:52}
#castCard .body{display:flex;flex-direction:column}
#castBox{max-width:none !important;width:100% !important;border:0 !important;border-radius:8px}
#castImg{width:100%;max-height:62vh;object-fit:contain;margin:0 auto}"""
new_css = """/* 2026-09-24 R2 修正（用户反馈：HUD 黑条与整体不搭 · 未投屏时黑长条难看 · 大小档点不动）：
   ① 不再把整页/整卡涂黑 —— 只留「画面区」黑底做 letterbox ✓
   ② 未投屏时用封面照片占位，保持 2:1 高度不变（不缩短 ✓）
   ③ 删掉 !important 的宽度覆盖 —— 它盖掉了 wset() 写的内联宽度 → 大小档失效 ✗ */
#castCard .body{display:flex;flex-direction:column}
#castBox{background:#000;border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative}
#castImg{width:100%;height:auto;display:block;margin:0 auto}
#castPh{width:100%;padding-top:50%;background:#0b0f14 url(/castcover.jpg) center/cover no-repeat}
#hud{background:var(--bg2) !important;color:var(--dim) !important;border-color:var(--line) !important}"""
rep(old_css, new_css, 1, 'CSS 黑底/!important')

# ── ② HTML：整段 <section id="tab-cast"> 重排（结构修好：悬浮窗行进 .body ✓ 顺序＝视觉顺序 ✓）──
i = h.find('<section id="tab-cast"')
j = h.find('<section id="tab-term"')
assert i > 0 and j > i, 'section 定位失败'
new_sec = '''<section id="tab-cast" style="overflow:auto;padding:8px;gap:10px">
<div class="card" id="castCard">
      <h4>投屏与悬浮（主菜单）</h4>
      <div class="body">
        <div class="row" style="flex-wrap:wrap">
          <button id="castOn" class="primary">开始投屏</button>
          <button id="castStop" class="ghost">停止</button>
          <span class="note">大小</span>
          <button id="csF" class="primary">适配</button><button id="csS" class="ghost">小</button>
          <button id="csM" class="ghost">中</button>
          <button id="csL" class="primary">满宽</button>
          <span class="note" id="castInfo">未开始</span>
        </div>
        <div id="hud" style="display:flex;flex-wrap:wrap;gap:6px 14px;padding:8px 10px;background:var(--bg2);border:1px solid var(--line);border-radius:10px;font-size:12px;color:var(--dim)">
          <span id="hudTemp">主板 –</span><span id="hudMem">内存 –</span><span id="hudCpu">负载 –</span><span id="hudIp">设备 –</span>
        </div>
        <div class="row" style="flex-wrap:wrap">
          <span class="note">画质</span>
          <button id="qLow" class="ghost">低（最顺）</button>
          <button id="qMid" class="primary">中</button>
          <button id="qHigh" class="ghost">高（最清）</button>
          <span class="note" id="qInfo">中 · 1024×600</span>
        </div>
        <div class="row" style="flex-wrap:wrap;border-top:1px solid var(--line);padding-top:8px">
          <span class="note"><b>桌面悬浮窗</b></span>
          <button id="flOn" class="ghost">开启悬浮窗</button>
          <button id="flOff" class="ghost">关闭悬浮窗</button>
          <span class="note" id="flInfo">—</span>
        </div>
        <div id="castBox" style="width:100%;max-width:480px;margin:0 auto;background:#000;border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative">
          <div id="castPh"></div>
          <img id="castImg" style="width:100%;height:auto;display:block" alt="C3 界面镜像">
          <div id="castTap" style="display:none;position:absolute;left:0;top:0;right:0;bottom:0;touch-action:none"></div>
        </div>
        <div class="note" id="castRes">画面 —</div>
        <div class="note" id="tcInfo"></div>
        <div class="row" style="flex-wrap:wrap;display:none">
          <label class="note" style="display:flex;align-items:center;gap:4px"><input type="checkbox" id="tcOnImg" style="width:auto" checked> 画面上直接点按</label>
          <span class="note">方向</span>
          <button id="dir1" class="ghost">1</button><button id="dir2" class="primary">2</button><button id="dir3" class="ghost">3</button><button id="dir4" class="ghost">4</button>
          <button id="dirTest" class="ghost">测试点一下</button><button id="csGear" class="ghost">⚙ C3 设置</button>
        </div>
      </div>
    </div>
      <div class="card" id="setDisp" style="display:none">
      <h4>显示与投屏设置</h4>
      <div class="body">
        <div class="row">
          <button id="dpImm" class="ghost">全屏沉浸</button>
          <button id="dpRot" class="ghost">旋转 90°</button>
          <span class="note">自适应缩放</span>
          <button id="dpZ90" class="ghost">90%</button>
          <button id="dpZ100" class="primary">100%</button>
          <button id="dpZ110" class="ghost">110%</button>
        </div>
        <div class="note">全屏沉浸：隐藏页面所有栏（APP 内同时收起原生顶栏 ✓）· 旋转 90°：横屏大视野，自动等比铺满 ✓ · 缩放：整体放大缩小 ✓ 设置都会记住 ✓</div>
      </div>
    </div>
  </section>
'''
h = h[:i] + new_sec + h[j:]
log.append('OK  HTML section#tab-cast 重排')

# ── ③ JS：删掉 order 重排 IIFE（顺序已写进 HTML）──────────────────────────
old_ord = """  (function(){ try{
    var body=document.querySelector("#castCard .body"); if(!body) return;
    body.style.display="flex"; body.style.flexDirection="column";
    var rows=body.querySelectorAll(":scope > .row"), i, rSize=null, rQual=null, rFloat=null;
    for(i=0;i<rows.length;i++){ var el=rows[i];
      if(el.querySelector("#qLow")) rQual=el;
      else if(el.querySelector("#flOn")) rFloat=el;
      else if(el.querySelector("#castOn")) rSize=el; }
    function ord(el,n){ if(el) el.style.order=n; }
    ord(rSize,1); ord(document.getElementById("hud"),2); ord(rQual,3); ord(rFloat,4);
    ord(document.getElementById("castBox"),50); ord(document.getElementById("castRes"),51); ord(document.getElementById("tcInfo"),52);
  }catch(x){} })();"""
new_ord = """  /* 2026-09-24 R2：视觉顺序＝DOM 顺序（HTML 里已排好）✓
     旧实现靠 CSS order 重排，但「悬浮窗」那一行当时在 .body **之外** → 永远找不到 → 一直停最底部 ✗ */
  function ph(show){ try{ var p=e('castPh'); if(p) p.style.display=show?'block':'none'; }catch(x){} }"""
rep(old_ord, new_ord, 1, 'JS 去掉 order 重排 + 占位图开关')

# ── ④ JS：fitPx 适配"画面已置底"（迭代收敛）────────────────────────────────
old_fit = """  function fitPx(){
    var bx=e('castBox');
    if(!bx) return 480;
    var availW=(bx.parentNode?bx.parentNode.clientWidth:0);
    if(!availW) availW=window.innerWidth-40;
    /* 2026-09-23 用户反馈「满屏看不全」：不能按视口比例猜 ✗，
       要按画面顶部到底部的**真实剩余高度**算（画面底部留 16px）✓ */
    /* 排版未稳/滚到顶时 getBoundingClientRect().top 会≈0 → 会算成"满屏高"进而退化成满宽 ✗
       → 顶部对齐时改用视口比例兜底 ✓；正常情况按画面顶部到底部的真实剩余高度 ✓ */
    var top=Math.round(bx.getBoundingClientRect().top);
    var availH;
    if(top<60) availH=Math.round(window.innerHeight*0.52);
    else availH=window.innerHeight-top-16;
    if(availH<130) availH=130;
    var w=Math.round(availH*2);                         /* C3 画面 2:1 ✓ */
    if(w>availW) w=availW;
    if(w<240) w=240;
    return w;
  }"""
new_fit = """  function fitPx(){
    /* 2026-09-24 R2：画面区已移到卡片最下面 ✓
       「适配」= 按画面顶部→视口底部的**真实剩余高度**把整屏装下（宽不超过卡片可用宽）✓
       画面在底部时"宽度↔剩余高度"互相影响 → 迭代 3 次收敛 ✓ */
    var bx=e('castBox');
    if(!bx) return 480;
    var availW=(bx.parentNode?bx.parentNode.clientWidth:0);
    if(!availW) availW=window.innerWidth-40;
    var w=availW, i;
    for(i=0;i<3;i++){
      try{ bx.style.maxWidth=w+'px'; bx.style.width=w+'px'; }catch(x){}
      var top=Math.round(bx.getBoundingClientRect().top);
      var availH=window.innerHeight-top-16;
      if(availH<130) availH=130;
      var nw=Math.round(availH*2);                      /* C3 画面 2:1 ✓ */
      if(nw>availW) nw=availW;
      if(nw<240) nw=240;
      if(Math.abs(nw-w)<10){ w=nw; break; }
      w=nw;
    }
    return w;
  }"""
rep(old_fit, new_fit, 1, 'JS fitPx 置底迭代')

# ── ⑤ JS：投屏接流/断开时切占位图 ────────────────────────────────────────
rep("""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none';
      info('画面在悬浮窗里 ✓（本页已暂停，省资源）'); }catch(x){} };
    window.__castAttach = function(){ try{ if(!HOST) return; RUN=true; on=true;
      e('castImg').src='http://'+HOST+':8090/?t='+Date.now();
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){} };""",
"""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none'; ph(true);
      info('画面在悬浮窗里 ✓（本页已暂停，省资源）'); }catch(x){} };
    window.__castAttach = function(){ try{ if(!HOST) return; RUN=true; on=true;
      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(false);
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){} };""", 1, 'JS detach/attach 占位图')

rep("""        RUN=true; on=true;
        try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}""",
"""        RUN=true; on=true;
        try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}
        try{ ph(false); }catch(x){}""", 1, 'JS 自动接入占位图')

rep("""    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
"""    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(false); info('已连接 '+HOST+':8090'); poll(); }, 1500);""", 1, 'JS castOn 占位图')

rep("""    on=false; if(t2) clearTimeout(t2); t2=null; e('castImg').src=''; fetch('/api/cast/stop'); info('已停止（零开销 ✓）');""",
"""    on=false; RUN=false; if(t2) clearTimeout(t2); t2=null; e('castImg').src=''; ph(true); fetch('/api/cast/stop'); info('已停止（零开销 ✓）');""", 1, 'JS castStop 占位图')

# ── ⑥ JS：切主机/保存主机 → 同步"默认主机"（此前只在页面里选，后端仍用旧默认 ✗）──
rep("""$('#hostSel').addEventListener('change',function(){ fillHostForm(); listDir(state.rootFor()) });""",
"""$('#hostSel').addEventListener('change',function(){
    fillHostForm(); listDir(state.rootFor());
    /* 2026-09-24 R2：页面选中的主机必须同步成后端"默认主机" ✓
       否则 /test、/exec、终端仍打旧默认主机 → 手动保存/切换的主机"连不上" ✗ */
    try{ api('/hosts',{method:'POST',json:{action:'default',id:sel()}}); }catch(e){}
  });""", 1, 'JS hostSel 同步默认主机')

rep("""    api('/hosts',{method:'POST',json:{action:'upsert',host:h}}).then(function(){
      toast('已保存 '+(h.label||h.id),'ok');""",
"""    api('/hosts',{method:'POST',json:{action:'upsert',host:h}}).then(function(){
      try{ return api('/hosts',{method:'POST',json:{action:'default',id:h.id}}); }catch(e){}
      return null;
    }).then(function(){
      toast('已保存 '+(h.label||h.id),'ok');""", 1, 'JS 保存主机后设为默认')

io.open(P, 'w', encoding='utf-8').write(h)
print('\n'.join(log))

# ── ⑦ 封面照片：真实 C3 画面帧 → assets/castcover.jpg ─────────────────────
src = os.path.join(D, '_attic/frame_new.jpg')
dst = os.path.join(D, 'assets/castcover.jpg')
if os.path.isfile(src):
    shutil.copyfile(src, dst)
    print('OK  封面照片 assets/castcover.jpg ←', os.path.basename(src), os.path.getsize(dst), 'bytes')
else:
    print('WARN 找不到 _attic/frame_new.jpg，封面用纯色底（仍不缩高）')
