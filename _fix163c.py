# -*- coding: utf-8 -*-
"""R69c：同上，修正 if(LASTROUTE){ 的出现次数（4 处都转 window）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag, cnt=1):
    global h
    c = h.count(old)
    assert c == cnt, tag + ': count=' + str(c) + ' 期望 ' + str(cnt)
    h = h.replace(old, new); print('OK  ' + tag)
rep("    LAST=list;", "    LAST=list; try{ window.LAST=LAST; }catch(e){}", '导出 LAST')
rep("    LASTCTX=st;", "    LASTCTX=st; try{ window.LASTCTX=LASTCTX; }catch(e){}", '导出 LASTCTX')
rep("LASTROUTE=j.result; renderRoute(j.result);",
    "LASTROUTE=j.result; try{ window.LASTROUTE=LASTROUTE; }catch(e){} renderRoute(j.result);", '导出 LASTROUTE(pollScan)')
rep("((j.result.routes||[]).length)){ LASTROUTE=j.result; }",
    "((j.result.routes||[]).length)){ LASTROUTE=j.result; try{ window.LASTROUTE=LASTROUTE; }catch(e){} }", '导出 LASTROUTE(resumeScan)')
rep("if(res) LASTROUTE=res;",
    "if(res){ LASTROUTE=res; try{ window.LASTROUTE=LASTROUTE; }catch(e){} }", '导出 LASTROUTE(analyzeAll)')
rep("if(LASTCTX) t.push('', '【设备现状】', String(LASTCTX).slice(0,1500));",
    "if(window.LASTCTX) t.push('', '【设备现状】', String(window.LASTCTX).slice(0,1500));", '读 LASTCTX(1)')
rep("if(LAST && LAST.length){", "if(window.LAST && window.LAST.length){", '读 LAST(1)')
rep("【参数：与厂商默认不同的 '+LAST.length+' 项】",
    "【参数：与厂商默认不同的 '+window.LAST.length+' 项】", '读 LAST(2)')
rep("LAST.slice(0,60).forEach(function(x){", "window.LAST.slice(0,60).forEach(function(x){", '读 LAST(3)')
rep("if(LASTROUTE){", "if(window.LASTROUTE){", '读 LASTROUTE(branch ×4)', 4)
rep("var rs=(LASTROUTE.routes||[]);", "var rs=((window.LASTROUTE||{}).routes||[]);", '读 LASTROUTE(1)')
rep("var rs=LASTROUTE.routes||[];", "var rs=(window.LASTROUTE||{}).routes||[];", '读 LASTROUTE(2)')
rep("(LAST||[]).forEach(function(x){", "((window.LAST)||[]).forEach(function(x){", '读 LAST(4)')
rep("var s=String(LASTCTX||'');", "var s=String(window.LASTCTX||'');", '读 LASTCTX(2)')
rep("'报告摘要：参数差异 '+((LAST||[]).length)+' 项 · 路线 '+((LASTROUTE&&LASTROUTE.routes)?LASTROUTE.routes.length:0)+' 条 · 采样 '",
    "'报告摘要：参数差异 '+(((window.LAST)||[]).length)+' 项 · 路线 '+((window.LASTROUTE&&window.LASTROUTE.routes)?window.LASTROUTE.routes.length:0)+' 条 · 采样 '", '读 LAST/ROUTE(摘要)')
rep("for(var i=0;i<(LAST||[]).length;i++){ if(LAST[i].key===k) return LAST[i].cur; }",
    "var _L=(window.LAST)||[]; for(var i=0;i<_L.length;i++){ if(_L[i].key===k) return _L[i].cur; }", '读 LAST(5)')
io.open(P, 'w', encoding='utf-8').write(h)
print('done')
