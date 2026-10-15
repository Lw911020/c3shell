# -*- coding: utf-8 -*-
"""R46：一级菜单"选中态" —— 当前模块高亮、其它未选中的收起（page.html + diag.html）"""
import io, os

D = '/storage/emulated/0/openpilot/c3shell'
FILES = ['assets/page.html', 'assets/diag.html']

OLD_ITEM = """    function item(label, act, own, cur){
      if(TOP){
        var h=document.createElement('div');
        h.textContent=label;
        h.style.cssText='cursor:pointer;padding:4px 11px;margin:0;border-radius:999px;font-size:13px;font-weight:600;white-space:nowrap;'
          +(cur?'background:var(--acc);color:#fff;border:1px solid var(--acc)':'background:var(--bg3);color:var(--fg);border:1px solid var(--line)');
        h.onclick=function(){ if(cur) return; go(act); };
        nmTop.appendChild(h);
        if(cur&&own&&own.length){ own.forEach(function(c){ nmSub.appendChild(c); }); }
        return;
      }
      var wrap=document.createElement('div'); wrap.style.cssText='display:block;margin:0';
      var head=document.createElement('div');
      head.textContent=(own&&own.length?(cur?'▾ ':'▸ '):'   ')+label;
      head.style.cssText='cursor:pointer;padding:6px 8px;margin:2px 0;border-radius:8px;font-size:12.5px;font-weight:600;'
        +(cur?'background:var(--acc);color:#fff':'background:var(--bg3);color:var(--fg)')+';border:1px solid var(--line)';
      var sub=document.createElement('div');
      sub.style.cssText='display:'+(cur?'block':'none')+';margin:2px 0 6px 8px;padding-left:6px;border-left:2px solid var(--line)';
      (own||[]).forEach(function(c){ sub.appendChild(c); });
      head.onclick=function(){
        if(own&&own.length){
          if(cur){                                   // 当前页：只切换显隐
            var vis=sub.style.display!=='none';
            sub.style.display=vis?'none':'block';
            head.textContent=(vis?'▸ ':'▾ ')+label;
          } else go(act);                            // 其它页：跳过去（保证一级项始终可点回）
        } else go(act);
      };
      wrap.appendChild(head); wrap.appendChild(sub); side.appendChild(wrap);
    }"""

NEW_ITEM = """    /* 2026-09-24 R46（用户要求）：一级菜单要有"选中态" —— 当前模块高亮 ✓，其它未选中的收起 ✓
       真因：以前"是不是选中"只按 kind()（console/diag）判断，而投屏/AI 分析/界面设置/软件设置
       都是**控制台页里的二级页签** → 停在这几个页签时仍然高亮"控制台"，且它的子菜单一直展开 ✗ */
    var REG=[];
    function activeKey(){
      try{
        if(kind()==='diag') return 'diag';
        var q=String(location.search||'');
        var b=document.querySelector('nav.tabs button.on');
        var t=b?(b.getAttribute('data-tab')||''):'';
        if(t==='cast') return 'cast';                 // 二级页签 → 对应的一级模块
        if(t==='aian') return 'ai';
        if(t==='uiset') return 'ui';
        if(t==='settings') return 'settings';
        if(t&&t!=='hosts') return 'console';          // 其它二级页签都归控制台 ✓
        if(/[?&]ai=1/i.test(q)) return 'ai';          // 初始深链（页签还没被点之前）
        if(/[?&]ui=1/i.test(q)) return 'ui';
        if(/[?&]tab=cast/i.test(q)) return 'cast';
        if(/[?&]tab=aian/i.test(q)) return 'ai';
        if(/[?&]tab=uiset/i.test(q)) return 'ui';
        if(/[?&]tab=settings/i.test(q)) return 'settings';
        return 'console';
      }catch(e){ return 'console'; }
    }
    function paint(rec, cur){
      var head=rec.head, own=rec.own||[];
      if(rec.top){
        head.style.background=cur?'var(--acc)':'var(--bg3)';
        head.style.color=cur?'#fff':'var(--fg)';
        head.style.borderColor=cur?'var(--acc)':'var(--line)';
        return;
      }
      head.textContent=(own.length?(cur?(rec.open===false?'▸ ':'▾ '):'▸ '):'   ')+rec.label;
      head.style.background=cur?'var(--acc)':'var(--bg3)';
      head.style.color=cur?'#fff':'var(--fg)';
      if(rec.sub) rec.sub.style.display=(cur&&rec.open!==false)?'block':'none';
    }
    function applyState(){
      var a=activeKey();
      for(var i=0;i<REG.length;i++) paint(REG[i], REG[i].key===a);
    }
    function item(label, act, own, cur, key){
      if(TOP){
        var h=document.createElement('div');
        h.textContent=label;
        h.style.cssText='cursor:pointer;padding:4px 11px;margin:0;border-radius:999px;font-size:13px;font-weight:600;white-space:nowrap;border:1px solid var(--line)';
        h.onclick=function(){ if(activeKey()===key) return; go(act); };
        nmTop.appendChild(h);
        if(cur&&own&&own.length){ own.forEach(function(c){ nmSub.appendChild(c); }); }
        REG.push({key:key,head:h,own:own||[],label:label,top:true,open:true});
        return;
      }
      var wrap=document.createElement('div'); wrap.style.cssText='display:block;margin:0';
      var head=document.createElement('div');
      head.style.cssText='cursor:pointer;padding:6px 8px;margin:2px 0;border-radius:8px;font-size:12.5px;font-weight:600;border:1px solid var(--line)';
      var sub=document.createElement('div');
      sub.style.cssText='display:none;margin:2px 0 6px 8px;padding-left:6px;border-left:2px solid var(--line)';
      (own||[]).forEach(function(c){ sub.appendChild(c); });
      var rec={key:key,head:head,sub:sub,own:own||[],label:label,top:false,open:true};
      head.onclick=function(){
        if(own&&own.length){
          if(activeKey()===key){ rec.open=(rec.open===false); paint(rec,true); }   // 当前模块：只切换展开/收起 ✓
          else go(act);                                                           // 别的模块：跳过去（那边默认展开 ✓）
        } else go(act);
      };
      wrap.appendChild(head); wrap.appendChild(sub); side.appendChild(wrap);
      REG.push(rec); paint(rec,cur);
    }"""

# 两文件共用的 item 调用替换（各自文本相同）
CALLS = [
 ("    item('投屏','c3shell://page?p=console&cast=1', null, false);",
  "    item('投屏','c3shell://page?p=console&cast=1', null, false, 'cast');"),
 ("    item('设备查找','c3shell://tools', null, false);",
  "    item('设备查找','c3shell://tools', null, false, 'tools');"),
 ("    item('AI 分析','c3shell://page?p=console&ai=1', null, false);",
  "    item('AI 分析','c3shell://page?p=console&ai=1', null, false, 'ai');"),
 ("    item('赞赏','c3shell://reward', null, false);",
  "    item('赞赏','c3shell://reward', null, false, 'reward');"),
 ("    item('界面设置','c3shell://page?p=console&ui=1', null, false);",
  "    item('界面设置','c3shell://page?p=console&ui=1', null, false, 'ui');"),
 ("    item('软件日志','c3shell://logs', null, false);",
  "    item('软件日志','c3shell://logs', null, false, 'logs');"),
]

for rel in FILES:
    p = os.path.join(D, rel)
    h = io.open(p, encoding='utf-8').read()
    assert h.count(OLD_ITEM) == 1, rel + ': item() 未命中'
    h = h.replace(OLD_ITEM, NEW_ITEM)
    for old, new in CALLS:
        assert h.count(old) == 1, rel + ': 未命中 ' + old[:40]
        h = h.replace(old, new)
    # 控制台 / 转向诊断 两项
    o1 = "    item('控制台','c3shell://page?p=console', k==='console'?_rest:null, k==='console');"
    n1 = "    item('控制台','c3shell://page?p=console', k==='console'?_rest:null, false, 'console');"
    assert h.count(o1) == 1, rel + ': 控制台 未命中'
    h = h.replace(o1, n1)
    o2 = "    item('转向诊断','c3shell://page?p=diag',  k==='diag'?kids:null,    k==='diag');"
    n2 = "    item('转向诊断','c3shell://page?p=diag',  k==='diag'?kids:null,    false, 'diag');"
    assert h.count(o2) == 1, rel + ': 转向诊断 未命中'
    h = h.replace(o2, n2)
    # 软件设置（自定义块）→ 注册进 REG，参与高亮
    o3 = """      head.onclick=function(){
        if(k==='console' && _setTab){ try{ _setTab.click(); }catch(e){} }
        else { try{ localStorage.setItem('c3pendingTab','软件设置'); }catch(e){} go('c3shell://page?p=console'); }
      };
      (TOP?nmTop:side).appendChild(head);
    })();"""
    n3 = """      head.onclick=function(){
        if(k==='console' && _setTab){ try{ _setTab.click(); }catch(e){} }
        else { try{ localStorage.setItem('c3pendingTab','软件设置'); }catch(e){} go('c3shell://page?p=console'); }
      };
      (TOP?nmTop:side).appendChild(head);
      REG.push({key:'settings',head:head,sub:null,own:[],label:'软件设置',top:!!TOP,open:true});
      paint(REG[REG.length-1],false);
    })();"""
    assert h.count(o3) == 1, rel + ': 软件设置 未命中'
    h = h.replace(o3, n3)
    # 构建完 + 定时刷新（切页签后选中态自动跟上 ✓）
    o4 = """  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',build); else build();
  setTimeout(build,700);
})();"""
    n4 = """  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',build); else build();
  setTimeout(build,700);
  /* 选中态刷新：app 用 jsSwitchTab 切页签不会重载页面 → 定时把高亮/收起对齐当前模块 ✓（只改样式，很轻）*/
  setInterval(function(){ try{ if(window.__nmApply) window.__nmApply(); }catch(e){} }, 900);
})();"""
    assert h.count(o4) == 1, rel + ': 收尾 未命中'
    h = h.replace(o4, n4)
    # 暴露 applyState
    o5 = "      wrap.appendChild(head); wrap.appendChild(sub); side.appendChild(wrap);\n      REG.push(rec); paint(rec,cur);\n    }"
    n5 = "      wrap.appendChild(head); wrap.appendChild(sub); side.appendChild(wrap);\n      REG.push(rec); paint(rec,cur);\n    }\n    try{ window.__nmApply=applyState; }catch(e){}"
    assert h.count(o5) == 1, rel + ': 暴露 applyState 未命中'
    h = h.replace(o5, n5)
    io.open(p, 'w', encoding='utf-8').write(h)
    print('OK  ' + rel)
print('done')
