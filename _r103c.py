# -*- coding: utf-8 -*-
"""R103c：参数设置的深链改用诊断页既有的 pane= 机制（原来我写成 pt=p3 ✗ 没人处理）"""
import io
D = '/storage/emulated/0/openpilot/c3shell/'
def rd(p): return io.open(D + p, encoding='utf-8').read()
def wr(p, s): io.open(D + p, 'w', encoding='utf-8').write(s)
def sub(s, old, new, tag):
    assert s.count(old) == 1, '%s 未命中 %d' % (tag, s.count(old))
    return s.replace(old, new)

# ① 两个页面的菜单链接：pt=p3 → pane=params（诊断页既有机制 ✓）
P = 'assets/page.html'
s = rd(P)
s = sub(s, "item('参数设置','c3shell://page?p=diag&pt=p3', null, false, 'params');",
        "item('参数设置','c3shell://page?p=diag&pane=params', null, false, 'params');", 'page 链接')
wr(P, s)

P = 'assets/diag.html'
s = rd(P)
s = sub(s, "item('参数设置','c3shell://page?p=diag&pt=p3', null, false, 'params');",
        "item('参数设置','c3shell://page?p=diag&pane=params', null, false, 'params');", 'diag 链接')
# 撤掉我在 paneFromHash 里加的那段死代码（paneFromHash 从来没被调用 ✗）
s = sub(s, """function paneFromHash(){
  /* 2026-09-24 R103：一级菜单「参数设置」用 ?pt=p3 直达参数页 ✓（顺带兼容 #params / #p3）*/
  try{ var m=/[?&]pt=(p[1-4])/.exec(location.search||''); if(m){ showPane(m[1]); return m[1]; } }catch(e){}
  var h=""", """function paneFromHash(){
  var h=""", '撤掉 pt 死代码')
wr(P, s)

# ② 原生顶栏：pendingQuery 也改 pane=params
P = 'java/com/padagent/c3shell/MainActivity.java'
s = rd(P)
s = sub(s, 'pendingQuery = "pt=p3";', 'pendingQuery = "pane=params";', '原生栏 pendingQuery')
wr(P, s)
print('OK  R103c 完成')
