# -*- coding: utf-8 -*-
"""R57：投屏"未连接/连接中/中断"要有明确提示（封面不再冒充实时画面）+ 掉流看门狗"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① HTML：封面之上加一层状态提示（点按穿透）
rep("""          <div id="castPh"></div>
          <img id="castImg" style="width:100%;height:auto;display:block" alt="C3 界面镜像">
          <div id="castTap" style="display:none;position:absolute;left:0;top:0;right:0;bottom:0;touch-action:none"></div>""",
"""          <div id="castPh"></div>
          <img id="castImg" style="width:100%;height:auto;display:block" alt="C3 界面镜像">
          <div id="castTap" style="display:none;position:absolute;left:0;top:0;right:0;bottom:0;touch-action:none"></div>
          <div id="castPhTip" style="display:none;position:absolute;left:0;top:0;right:0;bottom:0;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#e6edf3;background:rgba(6,10,16,.55);text-align:center;padding:10px;pointer-events:none">
            <span id="castPhMsg" style="font-size:13px;font-weight:600">未连接</span>
            <span id="castPhSub" style="font-size:11.5px;opacity:.85"></span>
          </div>""", 'HTML 状态提示层')

# ② ph() 支持提示文案
rep("""  function ph(show){ try{ var p=e('castPh'); if(p) p.style.display=show?'block':'none'; }catch(x){} }""",
"""  /* 2026-09-24 R57：未连接/连接中/中断 必须一眼看出来 ✓
     起因：封面占位照片跟实时画面长得一样 → 失焦暂停时用户以为"连上了但不动/连不上" ✗ */
  function ph(show, msg, sub){ try{
    var p=e('castPh'); if(p) p.style.display=show?'block':'none';
    var t=e('castPhTip'); if(t) t.style.display=show?'flex':'none';
    if(msg!==undefined) { var a=e('castPhMsg'); if(a) a.textContent=msg; }
    if(sub!==undefined) { var b=e('castPhSub'); if(b) b.textContent=sub; }
  }catch(x){} }""", 'ph() 带提示')

# ③ 各处调用：明确"在不在投屏"
rep("""      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(false);
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){}""",
"""      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(true,'连接中…','正在建立画面流');
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){}""", 'attach → 连接中')

rep("""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none'; ph(true); setTimeout(function(){ geo('detach'); }, 300);""",
"""    window.__castDetach = function(){ try{ RUN=false; on=false; e('castImg').src=''; e('castTap').style.display='none'; ph(true,'画面在悬浮窗里','本页已暂停（省一份解码 ✓）'); setTimeout(function(){ geo('detach'); }, 300);""",
    'detach → 悬浮窗提示')

rep("""        try{ ph(false); }catch(x){}""", """        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}""", '自动接入 → 连接中')

rep("""    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(false); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
"""    fetch('/api/cast/start').then(function(){ return fetch('/api/cast/start'); }).then(function(){
      setTimeout(function(){ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(true,'连接中…','正在建立画面流'); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
    'castOn → 连接中')

rep("""    on=false; RUN=false; if(t2) clearTimeout(t2); t2=null; e('castImg').src=''; ph(true); fetch('/api/cast/stop'); info('已停止（零开销 ✓）');""",
"""    on=false; RUN=false; if(t2) clearTimeout(t2); t2=null; e('castImg').src=''; ph(true,'未连接','点「开始投屏」开始'); fetch('/api/cast/stop'); info('已停止（零开销 ✓）');""",
    'stop → 未连接')

# ④ 图片加载成功 = 真的收到画面 → 收起提示；失败 = 明确提示并自动重连
rep("""    try{ var _im=e('castImg'); if(_im){ _im.onerror=function(){ ph(true); info('画面未连上（已显示封面 ✓）'); }; } }catch(x){}""",
"""    try{ var _im=e('castImg');
      _im.onload=function(){ if(RUN) ph(false); };                        /* 真收到画面才收起提示 ✓ */
      _im.onerror=function(){ ph(true,'连接中断','正在自动重连…'); info('画面未连上（自动重连中 ✓）'); };
    }catch(x){}""", 'onload/onerror 明确化')

# ⑤ 看门狗：投屏中却一直没画面 → 自动重连（失焦暂停/流卡死都能自愈）
rep("""  try{ window.addEventListener('resize', function(){ try{ if(cw==='fit') wset('fit'); }catch(x){} reattach('窗口变化'); });""",
"""  /* 2026-09-24 R57：看门狗 —— APP 失焦时 WebView 会暂停消费 MJPEG（画面卡住/连接积压），
     回到前台后不一定自己恢复 ✗ → 投屏中却一直没画面就自动重连 ✓ */
  setInterval(function(){ try{
    if(!RUN || !HOST) return;
    var im=e('castImg'); if(!im) return;
    if((im.naturalWidth||0)===0) reattach('未收到画面');
  }catch(x){} }, 5000);
  try{ window.addEventListener('resize', function(){ try{ if(cw==='fit') wset('fit'); }catch(x){} reattach('窗口变化'); });""",
    '看门狗自动重连')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
