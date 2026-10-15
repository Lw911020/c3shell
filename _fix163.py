# -*- coding: utf-8 -*-
"""R69：把 LAST / LASTCTX / LASTROUTE 跨 script 块共享（修 LAST is not defined）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
n = 0
def rep(old, new, tag, cnt=1):
    global h, n
    assert h.count(old) == cnt, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); n += 1; print('OK  ' + tag)

# ── 第一块：赋值时同步到 window ──────────────────────────────
rep("    LAST=list;", "    LAST=list; try{ window.LAST=LAST; }catch(e){}", '导出 LAST')
rep("    LASTCTX=st;", "    LASTCTX=st; try{ window.LASTCTX=LASTCTX; }catch(e){}", '导出 LASTCTX')
rep("          LASTROUTE=j.result; renderRoute(j.result);",
    "          LASTROUTE=j.result; try{ window.LASTROUTE=LASTROUTE; }catch(e){} renderRoute(j.result);", '导出 LASTROUTE(pollScan)')
rep("      if(j&&j.result&&((j.result.routes||[]).length)){ LASTROUTE=j.result; }",
    "      if(j&&j.result&&((j.result.routes||[]).length)){ LASTROUTE=j.result; try{ window.LASTROUTE=LASTROUTE; }catch(e){} }", '导出 LASTROUTE(resumeScan)')
rep("    }).then(function(res){ if(res) LASTROUTE=res; }).catch(function(){});",
    "    }).then(function(res){ if(res){ LASTROUTE=res; try{ window.LASTROUTE=LASTROUTE; }catch(e){} } }).catch(function(){});", '导出 LASTROUTE(analyzeAll)')

# ── 第二块：全部改成 window.* 读取 ───────────────────────────
rep("try{ if(LASTCTX) t.push('', '【设备现状】', String(LASTCTX).slice(0,1500)); }catch(x){}",
    "try{ if(window.LASTCTX) t.push('', '【设备现状】', String(window.LASTCTX).slice(0,1500)); }catch(x){}", '读 LASTCTX(1)')
rep("    if(LAST && LAST.length){", "    if(window.LAST && window.LAST.length){", '读 LAST(1)')
rep("      t.push('', '【参数：与厂商默认不同的 '+LAST.length+' 项】');", "      t.push('', '【参数：与厂商默认不同的 '+window.LAST.length+' 项】');", '读 LAST(2)')
rep("      LAST.slice(0,60).forEach(function(x){", "      window.LAST.slice(0,60).forEach(function(x){", '读 LAST(3)')
rep("    if(LASTROUTE){\n      var rs=(LASTROUTE.routes||[]);", "    if(window.LASTROUTE){\n      var rs=((window.LASTROUTE||{}).routes||[]);", '读 LASTROUTE(1)')
rep("      (LAST||[]).forEach(function(x){", "      ((window.LAST)||[]).forEach(function(x){", '读 LAST(4)')
rep("      var s=String(LASTCTX||'');", "      var s=String(window.LASTCTX||'');", '读 LASTCTX(2)')
rep("      if(LASTROUTE){\n        var rs=LASTROUTE.routes||[]; var seg=0, ds=0, derate=0;",
    "      if(window.LASTROUTE){\n        var rs=(window.LASTROUTE||{}).routes||[]; var seg=0, ds=0, derate=0;", '读 LASTROUTE(2)')
rep("'报告摘要：参数差异 '+((LAST||[]).length)+' 项 · 路线 '+((LASTROUTE&&LASTROUTE.routes)?LASTROUTE.routes.length:0)+' 条 · 采样 '",
    "'报告摘要：参数差异 '+(((window.LAST)||[]).length)+' 项 · 路线 '+((window.LASTROUTE&&window.LASTROUTE.routes)?window.LASTROUTE.routes.length:0)+' 条 · 采样 '", '读 LAST/LASTROUTE(摘要)')
rep("    try{ for(var i=0;i<(LAST||[]).length;i++){ if(LAST[i].key===k) return LAST[i].cur; } }catch(x){}",
    "    try{ var _L=(window.LAST)||[]; for(var i=0;i<_L.length;i++){ if(_L[i].key===k) return _L[i].cur; } }catch(x){}", '读 LAST(5)')

io.open(P, 'w', encoding='utf-8').write(h)
print('共改', n, '处')
