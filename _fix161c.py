# -*- coding: utf-8 -*-
"""R68b(修正转义)：报告对话框改造"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 按钮：删「导出到「下载」」，大数据平台按钮 = 下载报告
rep("""      +'<button id="cBig" class="ghost">交给大数据平台</button>'
      +'<button id="cLoc" class="ghost">本地规则建议</button>'
      +'<button id="cExp" class="ghost">导出到「下载」</button><button id="cCopy" class="ghost">复制报告</button>'""",
"""      +'<button id="cBig" class="ghost">下载报告（交大数据平台）</button>'
      +'<button id="cLoc" class="ghost">本地规则建议</button>'
      +'<button id="cCopy" class="ghost">复制报告</button>'""", '按钮：下载 / 去掉导出')

rep("""    function out(s){ var o=e('cOut'); o.style.display='block'; o.textContent=s; }""",
"""    function out(s){ var o=e('cOut'); if(!o) return; o.style.display='block'; o.textContent=s; try{ o.scrollTop=0; }catch(x){} }""",
    'out() 加保护')

rep("""    var _ex=e('cExp'); if(_ex) _ex.onclick=function(){ try{ var r=window.__c3exportReport(); out('已导出到「下载」目录 ✓ 并已复制到剪贴板 ✓'); }catch(x){ out('导出失败：'+x.message); } };\n""",
    "", '删 cExp 处理')

rep("""    e('cLoc').onclick=function(){ out(window.__c3localAdvice()); };""",
"""    e('cLoc').onclick=function(){
      out('正在按本地规则库计算…');
      setTimeout(function(){
        try{ out(String((window.__c3localAdvice?window.__c3localAdvice():'（规则模块未加载，请重开 APP ✓）'))); }
        catch(x){ out('本地规则建议失败：'+((x&&x.message)||x)); }
      }, 30);
    };""", '本地规则建议容错')

# ⑤ 大数据平台 = 下载（注意：JS 源码里的 \n 要写成 \\n 才不会在 Python 里变成换行）
rep("""    e('cBig').onclick=function(){
      var u=localStorage.getItem('c3bigUrl')||'';
      var u2=prompt('大数据平台接口地址（POST JSON，和你配置的 AI 端点同样用法 ✓ 留空=取消）', u);
      if(u2===null) return;
      try{ localStorage.setItem('c3bigUrl', u2||''); }catch(x){}
      ask('（目标平台：'+(u2||'未配置')+'）\\n\\n' + window.__c3buildReport());
    };""",
"""    /* 2026-09-24 R68（用户要求）：交给大数据平台 = 下载报告文件（自己上传给平台）✓ */
    e('cBig').onclick=function(){
      out('正在生成报告并写入系统「下载」目录…');
      var r=window.__c3buildReport();
      var name='c3-report-'+Date.now()+'.txt';
      fetch('/api/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:name,text:r})})
        .then(function(x){return x.json()}).then(function(j){
          if(j&&j.ok) out('已下载 ✓\\n文件：'+j.path+'\\n（在「文件管理器 → 下载」里，直接发给大数据平台即可 ✓）\\n\\n── 报告预览 ──\\n'+r.slice(0,1500));
          else out('下载失败：'+((j&&j.error&&j.error.message)||'未知'));
        }).catch(function(x){ out('下载失败：'+x.message+'\\n\\n（报告内容如下，可手动复制保存）\\n'+r.slice(0,1500)); });
    };""", '大数据平台→下载')

rep("""  window.__c3exportReport = function(){
    var r = window.__c3buildReport();
    try{ if(window.saveFile){ saveFile('data:text/plain;charset=utf-8,'+encodeURIComponent(r), 'c3-report-'+Date.now()+'.txt'); } }catch(e){}
    try{ navigator.clipboard.writeText(r); }catch(e){}
    return r;
  };""",
"""  window.__c3exportReport = function(){   /* 2026-09-24 R68：改走 /api/save（原来的 window.saveFile 从未定义 ✗） */
    var r = window.__c3buildReport();
    try{ navigator.clipboard.writeText(r); }catch(e){}
    try{ fetch('/api/save',{method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({name:'c3-report-'+Date.now()+'.txt',text:r})}); }catch(e){}
    return r;
  };""", 'exportReport 改走 /api/save')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
