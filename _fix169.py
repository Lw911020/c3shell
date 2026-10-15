# -*- coding: utf-8 -*-
"""R73：AI 分析界面只显示「接管日志 + 结论」；设备/参数数据照算（问 AI / 报告仍引用）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① renderAll 支持"只要数据"
rep("""  function renderAll(out){
    var box=el('aiList'); box.innerHTML='';""",
"""  function renderAll(out, dataOnly){
    /* 2026-09-24 R73：dataOnly=true 时只把 LAST/LASTCTX 算好（报告与「问 AI」要用），
       ② 参数列表、① 设备行、③ 操作提示都不渲染 ✓ */
    var box=el('aiList'); box.innerHTML='';""", 'renderAll 加 dataOnly')

rep("""    LAST=list; try{ window.LAST=LAST; }catch(e){}
    var h2='<div class="pcat">② 参数分析 · 与厂商默认不同 '+list.length+' 项</div>';""",
"""    LAST=list; try{ window.LAST=LAST; }catch(e){}
    LASTCTX=st; try{ window.LASTCTX=LASTCTX; }catch(e){}
    if(dataOnly) return;                       /* 数据已就绪 → 不渲染 ①②③ ✓ */
    var h2='<div class="pcat">② 参数分析 · 与厂商默认不同 '+list.length+' 项</div>';""", 'renderAll 提前返回')

# ② 接管日志标题去掉编号
rep("""    var h='<div class="pcat">④ 最近路线（qlog 分诊 · 只看**设备接管**过的）</div>';""",
"""    var h='<div class="pcat">接管日志（最近路线 · 只看设备接管过的）</div>';""", '路线标题改接管日志')

# ③ analyzeAll：只渲染接管日志 + 结论
rep("""      /* 2026-09-24 R68：等三路都齐了再一次性渲染（用户要求"综合分析一起出来"✓） */
      renderAll(out);
      if(LASTROUTE) renderRoute(LASTROUTE);
      var h='<div class="pcat">④ 诊断页采样报告'+(diagAt?('（'+esc2(diagAt)+'）'):'')+'</div>';
      h+= diag? ('<pre style="white-space:pre-wrap;font-size:12px;background:var(--bg3);border:1px solid var(--line);border-radius:8px;padding:8px;margin:0">'+esc2(diag)+'</pre>')
              : '<div class="note">暂无（去「转向诊断」采样后点「分析本次采样」✓）</div>';
      var vs=verdict(out, diag);
      h+='<div class="pcat" style="margin-top:8px">⑤ 综合结论</div>';
      h+='<pre style="white-space:pre-wrap;font-size:12.5px;margin:0">'+vs.map(esc2).join(NL)+NL+NL+'（想深挖 → 点下面「问 AI」，它已带上 ①②③④ 全部数据 ✓）</pre>';
      el('aiList').innerHTML += h;
      try{ if(window.__c3afterAnalysis) setTimeout(window.__c3afterAnalysis, 400); }catch(e){}
      el('aiInfo').textContent='综合分析完成 ✓（接管日记'+(LASTROUTE?'/路线':'')+(diag?'/采样':'')+' 已收录）';""",
"""      /* 2026-09-24 R73（用户要求）：界面**只显示接管日志 + 结论** ✓
         设备/参数数据照样算好（LAST/LASTCTX ✓）→ 下载报告与「问 AI」仍会引用 ✓ */
      renderAll(out, true);
      el('aiList').innerHTML='';
      if(LASTROUTE) renderRoute(LASTROUTE);
      var vs=verdict(out, diag);
      el('aiList').innerHTML += '<div class="pcat" style="margin-top:8px">结论</div>'
        + '<pre style="white-space:pre-wrap;font-size:12.5px;margin:0">'+vs.map(esc2).join(NL)+NL+NL
        + '（想深挖 → 点下面「问 AI」：它会自动带上接管日志 + 设备/参数数据 ✓）</pre>';
      try{ if(window.__c3afterAnalysis) setTimeout(window.__c3afterAnalysis, 400); }catch(e){}
      el('aiInfo').textContent='分析完成 ✓（接管日志 + 结论；设备/参数已收进报告，问 AI 时自动带上 ✓）';""",
    'analyzeAll 只渲染接管日志+结论')

# ④ 卡片标题与提示同步
rep("""      <h4>AI 分析 / 参数建议</h4>""",
"""      <h4>AI 分析（接管日志 · 结论）</h4>""", '卡片标题')
rep("""综合分析=接管日记（路线 qlog，带进度，约 1~3 分钟）｜路线 qlog=只扫路线｜档案=存 A–H/Z 可回滚｜问 AI=带接管数据提问""",
"""综合分析=接管日志 + 结论（带进度，约 1~3 分钟）｜路线 qlog=只扫路线｜档案=存 A–H/Z 可回滚｜问 AI=自动带上接管日志与设备/参数数据""",
    '提示文案')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
