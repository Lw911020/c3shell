# -*- coding: utf-8 -*-
"""R103 重跑（去掉误留的 noop）：参数提升为一级菜单；版本日志读精简版"""
import io
D = '/storage/emulated/0/openpilot/c3shell/'
def rd(p): return io.open(D + p, encoding='utf-8').read()
def wr(p, s): io.open(D + p, 'w', encoding='utf-8').write(s)
def sub(s, old, new, tag):
    assert s.count(old) == 1, '%s 未命中 %d' % (tag, s.count(old))
    return s.replace(old, new)

# ② 版本日志加载器
P = 'assets/page.html'
s = rd(P)
old = """/* 版本日志（2026-09-21）：从 APP 自带 assets 读 CHANGELOG.md */
(function(){
  var el=document.getElementById('verLog'); if(!el) return;
  fetch('/CHANGELOG.md').then(function(r){ return r.text(); }).then(function(t){
    el.textContent=t; 
    var m=/
##\\s*(v[0-9.]+)/.exec(t);
    var now=document.getElementById('verNow'); if(now) now.textContent='当前版本：v'+ ('__APPVER__'||'');
  }).catch(function(e){ el.textContent='读取失败：'+e.message });
})();"""
new = """/* 版本日志（2026-09-21 起）
   2026-09-24 R103 修：原来这段找的是 #verLog —— 而页面上**根本没有这个元素** ✗
   → 函数第一行就 return，于是「版本日志加载中…」永远不变 ✗（用户看到的就是"一直在加载中"）
   同时 74KB 全文塞进 <pre> 也慢 ✗ → 改为读**精简版** assets/CHANGELOG-lite.md ✓
   （只记重要功能与重要修复）；精简版缺失再回落完整版，且最多只取前 120 行做保险 ✓ */
(function(){
  function put(t){
    var txt=String(t==null?'':t).split('\\n').slice(0,120).join('\\n');
    var a=document.getElementById('sLog'); if(a) a.textContent=txt;
    var b=document.getElementById('verLog'); if(b) b.textContent=txt;
    var now=document.getElementById('verNow'); if(now) now.textContent='当前版本：v__APPVER__';
  }
  put('版本日志加载中…');
  fetch('/CHANGELOG-lite.md').then(function(r){ if(!r.ok) throw new Error('no lite'); return r.text(); })
    .then(put)
    .catch(function(){ return fetch('/CHANGELOG.md').then(function(r){ return r.text(); }).then(put); })
    .catch(function(e){ put('读取失败：'+(e&&e.message||'')); });
})();"""
s = sub(s, old, new, '版本日志加载器')

# ③ 侧边栏加「参数设置」+ 隐藏二级里的"参数"
s = sub(s, "    item('转向诊断','c3shell://page?p=diag',  k==='diag'?kids:null,    false, 'diag');",
"    item('转向诊断','c3shell://page?p=diag',  k==='diag'?kids:null,    false, 'diag');\n"
+ "    item('参数设置','c3shell://page?p=diag&pt=p3', null, false, 'params');   /* 2026-09-24 R103：参数从二级页签提升为一级菜单 ✓ */",
'page.html 侧边栏参数设置')
s = sub(s, "    var kids=Array.prototype.slice.call(side.children);   // 原页签（保留事件）",
"    var kids=Array.prototype.slice.call(side.children);   // 原页签（保留事件）\n"
+ "    /* 2026-09-24 R103：参数已提升为一级菜单「参数设置」→ 二级里不再重复（页签按钮也隐藏 ✓）*/\n"
+ "    kids=kids.filter(function(c){ var t=String(c.textContent||'').trim();\n"
+ "      if(t==='参数'||t==='参数设置'){ c.style.display='none'; return false; } return true; });",
'page.html 隐藏参数页签')
wr(P, s)

# ④ diag.html
P = 'assets/diag.html'
s = rd(P)
s = sub(s, "    item('转向诊断','c3shell://page?p=diag',  k==='diag'?kids:null,    false, 'diag');",
"    item('转向诊断','c3shell://page?p=diag',  k==='diag'?kids:null,    false, 'diag');\n"
+ "    item('参数设置','c3shell://page?p=diag&pt=p3', null, false, 'params');   /* 2026-09-24 R103：参数提升为一级菜单 ✓ */",
'diag 侧边栏参数设置')
s = sub(s, "    var kids=Array.prototype.slice.call(side.children);   // 原页签（保留事件）",
"    var kids=Array.prototype.slice.call(side.children);   // 原页签（保留事件）\n"
+ "    kids=kids.filter(function(c){ var t=String(c.textContent||'').trim();\n"
+ "      if(t==='参数'||t==='参数设置'){ c.style.display='none'; return false; } return true; });   /* R103 ✓ */",
'diag 隐藏参数页签')
s = sub(s, "      function activeKey(){\n        try{\n          if(kind()==='diag') return 'diag';",
"      function activeKey(){\n        try{\n          if(kind()==='diag'){\n"
+ "            var _p3=document.getElementById('p3');\n"
+ "            if(_p3 && (' '+(_p3.className||'')+' ').indexOf(' on ')>=0) return 'params';   /* R103：参数页高亮「参数设置」✓ */\n"
+ "            return 'diag';\n          }", 'diag activeKey')
i = s.find('function paneFromHash(){')
j = s.find("document.querySelectorAll('.tab').forEach(function(t){ t.onclick=function(){")
assert i > 0 and j > i, 'diag paneFromHash 定位失败'
inject = """function paneFromHash(){
  /* 2026-09-24 R103：一级菜单「参数设置」用 ?pt=p3 直达参数页 ✓（顺带兼容 #params / #p3）*/
  try{
    var m=/[?&]pt=(p[1-4])/.exec(location.search||'');
    if(m){ showPane(m[1]); return m[1]; }
  }catch(e){}
"""
s = s[:i] + inject + s[i + len('function paneFromHash(){'):]
wr(P, s)

# ⑤ 原生顶栏
P = 'java/com/padagent/c3shell/MainActivity.java'
s = rd(P)
s = sub(s, """        bDiag = tab("转向诊断", P_DIAG);
        bar.addView(bConsole);
        bar.addView(bDiag);""",
"""        bDiag = tab("转向诊断", P_DIAG);
        bar.addView(bConsole);
        bar.addView(bDiag);
        /* 2026-09-24 R103（用户要求）：参数从「转向诊断」的二级页签提升为一级菜单「参数设置」 ✓ */
        bar.addView(action("参数设置", new View.OnClickListener() {
            public void onClick(View v) { page = P_DIAG; pendingQuery = "pt=p3"; pendingHash = ""; load(); }
        }));""", '原生栏参数设置')
wr(P, s)
print('OK  R103 重跑完成')
