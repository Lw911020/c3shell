# -*- coding: utf-8 -*-
"""R106：主菜单行调高 + 给主题/字号加运行时诊断日志（查明"没起效果"）"""
import io
D = '/storage/emulated/0/openpilot/c3shell/'
def rd(p): return io.open(D + p, encoding='utf-8').read()
def wr(p, s): io.open(D + p, 'w', encoding='utf-8').write(s)
def sub(s, old, new, tag):
    assert s.count(old) == 1, '%s 未命中 %d' % (tag, s.count(old))
    return s.replace(old, new)

# ① 主菜单行高度 46dp → 56dp
P = 'java/com/padagent/c3shell/MainActivity.java'
s = rd(P)
n = s.count('dp(46)')
s = s.replace('dp(46)', 'dp(56)')
wr(P, s)
print('顶栏高度 dp(46)→dp(56)，共', n, '处')

# ② 页面：主题/字号点击写日志
P = 'assets/page.html'
s = rd(P)
old = """  document.querySelectorAll('#setUi button[data-th]').forEach(function(b){
    b.onclick=function(){ try{ localStorage.setItem('c3theme',b.getAttribute('data-th')); }catch(e){}
      document.documentElement.setAttribute('data-theme',b.getAttribute('data-th'));
      try{ if(window.__tellSideColor) window.__tellSideColor(); }catch(e){}
      setTimeout(function(){ location.reload(); },250); };
  };
  document.querySelectorAll('#setUi button[data-dn]').forEach(function(b){
    b.onclick=function(){ try{ localStorage.setItem('c3density',b.getAttribute('data-dn')); }catch(e){}
      var d=b.getAttribute('data-dn'); if(d==='normal') document.documentElement.removeAttribute('data-density');
      else document.documentElement.setAttribute('data-density',d);
      setTimeout(function(){ location.reload(); },250); };
  });"""
new = """  /* 2026-09-24 R106：主题/字号点击加一行诊断日志（用户报"没起效果"，先量清楚 ✓）
     日志里能看到：点了什么 → html 上的属性 → body 的实际背景色/字号 ✓ */
  function diagUI(tag){
    try{
      var cs=getComputedStyle(document.body);
      fetch('/api/log',{method:'POST',headers:{'content-type':'application/json'},
        body:JSON.stringify({msg:'UI '+tag+' theme='+document.documentElement.getAttribute('data-theme')
          +' density='+document.documentElement.getAttribute('data-density')
          +' bg='+cs.backgroundColor+' fontSize='+cs.fontSize
          +' lsTheme='+(function(){try{return localStorage.getItem('c3theme')}catch(e){return '?'}})()
          +' lsDensity='+(function(){try{return localStorage.getItem('c3density')}catch(e){return '?'}})()})});
    }catch(e){}
  }
  try{ window.__diagUI=diagUI; }catch(e){}
  document.querySelectorAll('#setUi button[data-th]').forEach(function(b){
    b.onclick=function(){ try{ localStorage.setItem('c3theme',b.getAttribute('data-th')); }catch(e){}
      document.documentElement.setAttribute('data-theme',b.getAttribute('data-th'));
      diagUI('clickTheme='+b.getAttribute('data-th'));
      try{ if(window.__tellSideColor) window.__tellSideColor(); }catch(e){}
      setTimeout(function(){ location.reload(); },250); };
  });
  document.querySelectorAll('#setUi button[data-dn]').forEach(function(b){
    b.onclick=function(){ try{ localStorage.setItem('c3density',b.getAttribute('data-dn')); }catch(e){}
      var d=b.getAttribute('data-dn'); if(d==='normal') document.documentElement.removeAttribute('data-density');
      else document.documentElement.setAttribute('data-density',d);
      diagUI('clickDensity='+d);
      setTimeout(function(){ location.reload(); },250); };
  });
  setTimeout(function(){ diagUI('afterLoad'); }, 1500);"""
s = sub(s, old, new, '主题/字号诊断')
wr(P, s)
print('OK  page.html 诊断已加')
