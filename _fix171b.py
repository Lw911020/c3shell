# -*- coding: utf-8 -*-
"""R74：① 去掉「综合分析」入口 ② 路线分析显式报告"扫了多少条/用时多少"并顺带备好报告数据"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 删「综合分析」按钮 + handler
rep("""        <div class="row"><button id="aiAll" class="primary">综合分析</button>
          <button id="aiRoute" class="ghost">路线 qlog</button>""",
"""        <div class="row"><button id="aiRoute" class="primary">路线 qlog</button>""", '删综合分析按钮')
rep("""  if(el('aiAll')) el('aiAll').onclick=analyzeAll;
""", "", '删综合分析 handler')
rep("""综合分析=接管日志 + 结论（带进度，约 1~3 分钟）｜路线 qlog=只扫路线｜档案=存 A–H/Z 可回滚｜问 AI=自动带上接管日志与设备/参数数据""",
"""路线 qlog=扫描最近路线（接管日志；带进度、条数与用时）｜档案=存 A–H/Z 可回滚｜问 AI=自动带上接管日志与设备/参数数据""",
    '提示文案')

# ② 路线扫描：记开始时间 + 完成后报告条数/用时 + 备好报告数据（设备/参数，供问 AI）
rep("""  function routeScan(){
    el('aiInfo').textContent='正在扫描最近路线（读 qlog，约 1~3 分钟，请稍等）…';""",
"""  var LASTROUTE_T0=0;
  function routeScan(){
    LASTROUTE_T0=Date.now();
    el('aiInfo').textContent='正在扫描最近路线（读 qlog，约 1~3 分钟，请稍等）…';""", 'routeScan 记开始时间')

rep("""        if(j&&j.result){
          showProgress(100, '✓ 扫描完成');
          LASTROUTE=j.result; try{ window.LASTROUTE=LASTROUTE; }catch(e){} renderRoute(j.result);
          var _sc=document.getElementById('aiScope'); var _sv=_sc?Number(_sc.value):6;
          el('aiInfo').textContent='路线扫描完成：范围='+(_sv>0?('最新 '+_sv+' 条'):(_sv<0?('最近 '+(-_sv)+' 天'):'全部'))+' · 实际扫到 '+((j.result.routes||[]).length)+' 条 route（只统计被接管的 ✓）';
          setTimeout(function(){ var b=el('scanBar'); if(b) b.style.display='none'; }, 2500);
          return;
        }""",
"""        if(j&&j.result){
          showProgress(100, '✓ 扫描完成');
          LASTROUTE=j.result; try{ window.LASTROUTE=LASTROUTE; }catch(e){} renderRoute(j.result);
          var _rs=(j.result.routes||[]);
          var _eng=_rs.filter(function(r){ return Number(r.engagedPct)>0||Number(r.engaged)>0; }).length;
          var _seg=0; _rs.forEach(function(r){ _seg+=(r.segments||0); });
          var _sec=LASTROUTE_T0?Math.max(0.1,(Date.now()-LASTROUTE_T0)/1000):0;
          var _sc=document.getElementById('aiScope'); var _sv=_sc?Number(_sc.value):6;
          el('aiInfo').textContent='路线分析完成 ✓ 范围='+(_sv>0?('最新 '+_sv+' 条'):(_sv<0?('最近 '+(-_sv)+' 天'):'全部'))
            +' · 读入 '+_rs.length+' 条 route（其中被接管 '+_eng+' 条 · 跳过 '+Math.max(0,_rs.length-_eng)+' 条驻车/手动）· 合计 '+_seg+' 段'
            +(_sec?(' · 用时 '+_sec.toFixed(1)+' 秒'):'') + '　（qlog 是设备本地 10Hz 小文件，本来就快 ✓）';
          prepReport();                       /* 顺带把设备/参数数据备好（问 AI / 报告要用 ✓） */
          setTimeout(function(){ var b=el('scanBar'); if(b) b.style.display='none'; }, 2500);
          return;
        }""", '完成后报告条数/用时')

# ③ 新增 prepReport()：只取数据（不渲染），并在取完后触发报告弹窗
rep("""  /* 2026-09-24 R68：等扫描**真正结束**再返回结果（综合分析要"一次性出全部" ✓） */""",
"""  /* 2026-09-24 R74：只把设备现状/参数差异取回（不显示 ✓），供「问 AI」与体检报告引用 ✓ */
  function prepReport(){
    var out={status:'', all:null};
    var ps=post('/api/ssh/exec',{command:'/usr/local/venv/bin/python3 /data/openpilot/dsh-status.py 2>&1 | head -8; echo "---"; echo "proc manager=$(pgrep -fc manager.py) controlsd=$(pgrep -fc controlsd) card=$(pgrep -fc card.py)"'})
        .then(function(r){ out.status=((r&&r.result)||{}).stdout||''; }).catch(function(){});
    var pa=getj('/api/ssh/params/all').then(function(j){ out.all=j; }).catch(function(){});
    Promise.all([ps,pa]).then(function(){
      try{ renderAll(out, true); }catch(e){}                 /* 只要数据（LAST/LASTCTX）✓ */
      try{ if(window.__c3afterAnalysis) setTimeout(window.__c3afterAnalysis, 300); }catch(e){}
    });
  }
  /* 2026-09-24 R68：等扫描**真正结束**再返回结果（综合分析要"一次性出全部" ✓） */""",
    '新增 prepReport()')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
