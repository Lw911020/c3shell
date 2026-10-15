# -*- coding: utf-8 -*-
"""R106c：抓页面 JS 异常 + 设置块进度标记"""
import io
P = '/storage/emulated/0/openpilot/c3shell/assets/page.html'
s = io.open(P, encoding='utf-8').read()
def sub(s, old, new, tag):
    assert s.count(old) == 1, '%s 未命中 %d' % (tag, s.count(old))
    return s.replace(old, new)

# ① 全局错误捕获（放在最前面的块里，越早越好）
s = sub(s, '<html lang="zh-CN" data-theme="light">',
'<html lang="zh-CN" data-theme="light">', 'noop') if False else s
i = s.find('<body>')
assert i > 0
hook = '''<body>
<script>
/* 2026-09-24 R106：抓页面 JS 异常（用户报"主题/字体没起效果"，先拿到真实报错 ✓） */
(function(){
  function rep(m){
    try{ fetch('/api/log',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({msg:m})}); }catch(e){}
  }
  try{ window.__rep=rep; }catch(e){}
  window.addEventListener('error', function(e){
    rep('JSERR '+(e.message||'')+' @line'+(e.lineno||'?')+':'+(e.colno||'?')
      +' file='+String(e.filename||'').split('/').pop());
  });
  window.addEventListener('unhandledrejection', function(e){
    rep('JSPROMISE '+((e.reason&&e.reason.message)||String(e.reason)).slice(0,120));
  });
})();
</script>'''
s = s[:i] + hook + s[i + len('<body>'):]

# ② 设置块进度标记
s = sub(s, "  if(!el('tab-settings')) return;\n  function getj(u){",
        "  if(!el('tab-settings')) return;\n  try{ window.__rep && window.__rep('SET start'); }catch(e){}\n  function getj(u){", 'SET start')
s = sub(s, "  document.querySelectorAll('#setUi button[data-th]').forEach(function(b){",
        "  try{ window.__rep && window.__rep('SET beforeThemeBind'); }catch(e){}\n  document.querySelectorAll('#setUi button[data-th]').forEach(function(b){", 'SET beforeTheme')
s = sub(s, "  /* 2026-09-22 卡密激活 / 设备绑定 / 功能开关（服务端接口见 CHANGELOG 约定 ✓） */",
        "  try{ window.__rep && window.__rep('SET afterThemeBind ok'); }catch(e){}\n  /* 2026-09-22 卡密激活 / 设备绑定 / 功能开关（服务端接口见 CHANGELOG 约定 ✓） */", 'SET afterTheme')
io.open(P, 'w', encoding='utf-8').write(s)
print('OK  错误捕获 + 3 个进度标记已加')
