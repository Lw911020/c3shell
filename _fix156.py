# -*- coding: utf-8 -*-
"""R64：停止=暂停采集（服务不杀）→ 再开始近乎秒连；开始前先探服务在不在"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 采集开关的两个助手（直接走 SSH 改 /dev/shm/ui.cast.on，不重启服务）
rep("""  function setCastBtn(isOn){ try{""",
"""  /* 2026-09-24 R64：采集开关 = /dev/shm/ui.cast.on（钩子每次 swap 都看它 ✓）
     停止只把它删掉（采集立刻停、服务进程留着）→ 再开始不用重启 python（省下约 1s）✓ */
  function flagCmd(c){ try{
    fetch('/api/ssh/exec',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command:c})});
  }catch(x){} }
  function flagOn(){ flagCmd('touch /dev/shm/ui.cast.on; echo ok'); }
  function flagOff(){ flagCmd('rm -f /dev/shm/ui.cast.on; echo ok'); }
  function attachImg(){ try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){} waitFrame(); info('已连接 '+HOST+':8090'); poll(); }
  function setCastBtn(isOn){ try{""", '新增采集开关助手')

# ② startCast：先探服务 → 在则只开采集（快路），不在才拉起服务
rep("""  function startCast(){
    if(on) return; on=true; setCastBtn(true); info('启动中…'); geo('startCast');
    RUN=true; ph(true,'连接中…','正在建立画面流');
    fetch('/api/cast/start').then(function(r){ return r.json(); }).then(function(){
      /* 2026-09-24 R63：不等 1.5s —— 立刻挂画面，连不上就由 waitFrame 每 0.5s 重试 ✓ */
      try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}
      waitFrame(); info('已连接 '+HOST+':8090'); poll();
    }).catch(function(err){ info('启动失败：'+err.message); on=false; RUN=false; setCastBtn(false); });
  }""",
"""  function startCast(){
    if(on) return; on=true; setCastBtn(true); info('启动中…'); geo('startCast');
    RUN=true; ph(true,'连接中…','正在建立画面流');
    fetch('/api/cast/status').then(function(r){ return r.json(); }).then(function(j){
      if(isRunning((j||{}).out)){            /* 快路：服务还在 → 只开采集 ✓ */
        flagOn(); geo('fastpath'); attachImg();
      } else {
        fetch('/api/cast/start').then(function(r2){ return r2.json(); }).then(function(){ attachImg(); })
          .catch(function(err){ info('启动失败：'+err.message); on=false; RUN=false; setCastBtn(false); });
      }
    }).catch(function(){
      fetch('/api/cast/start').then(function(r2){ return r2.json(); }).then(function(){ attachImg(); })
        .catch(function(err){ info('启动失败：'+err.message); on=false; RUN=false; setCastBtn(false); });
    });
  }""", 'startCast 快路/慢路')

# ③ stopCast：只暂停采集，不杀服务
rep("""  function stopCast(){
    on=false; RUN=false; setCastBtn(false); if(t2) clearTimeout(t2); t2=null; e('castImg').src='';
    ph(true,'未连接','点「开始投屏」开始'); fetch('/api/cast/stop'); info('已停止（零开销 ✓）');
  }""",
"""  function stopCast(){
    on=false; RUN=false; setCastBtn(false); if(t2) clearTimeout(t2); t2=null; e('castImg').src='';
    ph(true,'未连接','点「开始投屏」开始'); flagOff();
    info('已停止（采集已暂停 ✓ 再开始秒连）');
  }""", 'stopCast 只暂停采集')

# ④ 自动接入时也要恢复采集开关（否则钩子还停着 → 画面不刷新 ✗）
rep("""        RUN=true; on=true; try{ setCastBtn(true); }catch(x){}
        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}   /* 先提示后设 src ✓ */""",
"""        RUN=true; on=true; try{ setCastBtn(true); }catch(x){}
        try{ flagOn(); }catch(x){}                              /* 恢复采集开关 ✓ */
        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}   /* 先提示后设 src ✓ */""",
    '自动接入恢复采集')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
