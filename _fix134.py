# -*- coding: utf-8 -*-
"""R46b：选中态判定改看"当前激活的 section"（软件设置的页签按钮被移出 DOM，查页签按钮查不到 ✗）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
OLD = """        var q=String(location.search||'');
        var b=document.querySelector('nav.tabs button.on');
        var t=b?(b.getAttribute('data-tab')||''):'';
        if(t==='cast') return 'cast';                 // 二级页签 → 对应的一级模块
        if(t==='aian') return 'ai';
        if(t==='uiset') return 'ui';
        if(t==='settings') return 'settings';
        if(t&&t!=='hosts') return 'console';          // 其它二级页签都归控制台 ✓"""
NEW = """        var q=String(location.search||'');
        /* ① 先看"当前激活的 section"（最可靠）：二级页签被搬进左栏后，
           软件设置那个按钮会脱离 DOM → 查 nav.tabs button.on 查不到它 ✗ */
        var secs=document.querySelectorAll('section');
        for(var i=0;i<secs.length;i++){
          var el=secs[i], cn=' '+(el.className||'')+' ';
          if(cn.indexOf(' on ')<0) continue;
          var id=el.id||'';
          if(id==='tab-cast') return 'cast';
          if(id==='tab-aian') return 'ai';
          if(id==='tab-uiset') return 'ui';
          if(id==='tab-settings') return 'settings';
        }
        /* ② 回落：看高亮的二级页签按钮 */
        var b=document.querySelector('nav.tabs button.on');
        var t=b?(b.getAttribute('data-tab')||''):'';
        if(t==='cast') return 'cast';
        if(t==='aian') return 'ai';
        if(t==='uiset') return 'ui';
        if(t==='settings') return 'settings';
        if(t&&t!=='hosts') return 'console';          // 其它二级页签都归控制台 ✓"""
for rel in ['assets/page.html','assets/diag.html']:
    p=os.path.join(D,rel); h=io.open(p,encoding='utf-8').read()
    assert h.count(OLD)==1, rel+' 未命中'
    io.open(p,'w',encoding='utf-8').write(h.replace(OLD,NEW))
    print('OK  '+rel)
print('done')
