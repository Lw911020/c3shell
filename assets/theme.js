/* 主题 + 字号控制（2026-09-20）：四套季节主题（含配色/字体颜色自适应）+ 三档字号。
   状态存 localStorage（同源两页共享），也支持 URL 覆盖：?theme=autumn&density=compact */
(function(){
  var THEMES=[['light','白底'],['spring','春'],['summer','夏'],['autumn','秋'],['winter','冬']];
  var DENS=[['compact','小'],['normal','标准'],['large','大']];
  var q=location.search||'';
  function pick(name, def){ var m=new RegExp('[?&]'+name+'=([a-z]+)','i').exec(q); return m?m[1].toLowerCase():def; }
  /* 2026-09-22 一次性迁移：产品主题改为「白底黑字」。
     老版本默认是 winter（深色），localStorage 里存着 'winter' 会把新默认顶掉 ✗
     → 只在第一次跑新版本时把存储值改成 light；之后用户自选的主题照旧生效 ✓ */
  try{ if(!localStorage.getItem('c3themeV2')){ localStorage.setItem('c3themeV2','1'); localStorage.setItem('c3theme','light'); } }catch(e){}
  var theme=pick('theme','')||localStorage.getItem('c3theme')||'light';
  var dens=pick('density','')||localStorage.getItem('c3density')||(window.innerWidth<560?'compact':'normal');
  if(['light','spring','summer','autumn','winter'].indexOf(theme)<0) theme='light';
  if(['compact','normal','large'].indexOf(dens)<0) dens='normal';
  function apply(){
    var r=document.documentElement;
    if(theme==='winter'){ r.removeAttribute('data-theme') } else { r.setAttribute('data-theme',theme) }
    if(dens==='normal'){ r.removeAttribute('data-density') } else { r.setAttribute('data-density',dens) }
    localStorage.setItem('c3theme',theme); localStorage.setItem('c3density',dens);
    var p=document.getElementById('themePanel');
    if(p){ p.querySelectorAll('button[data-th]').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-th')===theme) });
           p.querySelectorAll('button[data-dn]').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-dn')===dens) }); }
  }
  function build(){
    // 页面自带「设置 → 界面」卡片时不再注入页头按钮（避免两处重复）
    if (document.getElementById('setUi')) { apply(); return; }
    var b=document.createElement('button'); b.id='themeBtn'; b.type='button'; b.title='主题与字号'; b.textContent='显示 ⚙';
    var p=document.createElement('div'); p.id='themePanel';
    var h='<div class="t">主题（春夏秋冬）</div><div class="row">';
    THEMES.forEach(function(t){ h+='<button type="button" data-th="'+t[0]+'">'+t[1]+'</button>' });
    h+='</div><div class="t">字号</div><div class="row">';
    DENS.forEach(function(d){ h+='<button type="button" data-dn="'+d[0]+'">'+d[1]+'</button>' });
    h+='</div>';
    p.innerHTML=h; document.body.appendChild(b); document.body.appendChild(p);
    b.onclick=function(e){ e.stopPropagation(); p.classList.toggle('on') };
    document.addEventListener('click',function(){ p.classList.remove('on') });
    p.onclick=function(e){ e.stopPropagation();
      var th=e.target.getAttribute('data-th'), dn=e.target.getAttribute('data-dn');
      if(th){ theme=th; apply() } if(dn){ dens=dn; apply() } };
    var hd=document.querySelector('header');
    if(hd) hd.appendChild(b);
    apply();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',build); else build();
})();

/* 显示模式（2026-09-22 方案A）：手机/平板 = 原始布局（一级在 APP 原生顶栏）；车机 = 页面左栏。
   APP 里点「车机/手机平板」→ 通知原生（c3shell://displaymode）由原生重建顶栏；浏览器里直接重载。 */
(function(){
  function paint(){
    var L=document.documentElement.getAttribute('data-layout')||'tablet';
    var bs=document.querySelectorAll('#setUi button[data-lm]');
    for(var i=0;i<bs.length;i++){ bs[i].classList.toggle('on', bs[i].getAttribute('data-lm')===L); }
  }
  function bind(){
    var bs=document.querySelectorAll('#setUi button[data-lm]');
    for(var i=0;i<bs.length;i++){
      bs[i].onclick=function(){
        var m=this.getAttribute('data-lm');
        try{ localStorage.setItem('c3layout', m); }catch(e){}
        document.documentElement.setAttribute('data-layout', m);
        /* 2026-09-22：统一走 URL 参数重载 —— APP 侧在 shouldOverrideUrlLoading 里读 layout= 同步原生顶栏显隐；
           浏览器里同样生效（不依赖 c3shell:// 协议，那个在 Android 12+ 上拦不到）。 */
        // 2026-09-22：保留 tab= / ui=1 与锚点 —— 否则切模式会把"界面设置"这类深链冲掉 ✗
        var _tb=/[?&]tab=([a-z]+)/i.exec(location.search), _ui=/[?&]ui=1/i.test(location.search);
        try{ localStorage.setItem('c3dm', m); }catch(e){}   // 2026-09-22 fix：记住"用户选的是哪个"，否则选中态一直停在旧值 ✗
        var _url=location.pathname+'?layout='+m+'&inapp=1&t='+Date.now()
          +(_ui?'&ui=1':'')+(_tb?('&tab='+_tb[1]):'')+(location.hash||'');
        /* 2026-09-22 用户要求：切换要有过渡动画 → 先淡出 0.17s 再跳，落地时淡入 ✓ */
        try{ document.documentElement.classList.add('c3-leaving');
             setTimeout(function(){ location.href=_url; }, 175);
        }catch(e){ location.href=_url; }
      };
    }
    paint();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bind); else bind();
  setTimeout(bind,900);
})();

/* ══════════════════════════════════════════════════════════════════════
   2026-10-05 换页过渡（用户反馈：菜单切换很生硬 + 有闪烁）
   出发：body 淡到背景色（150ms，看得到）→ sessionStorage 留标记 → 再跳；
   到达：<head> 里的内联脚本读到标记，首帧就把正文藏住 → 落地后淡入 ✓
   效果＝"淡出→淡入"的交叉淡入，把 WebView 重绘那一下白闪藏进过渡里 ✓
   ══════════════════════════════════════════════════════════════════════ */
(function(){
  var R=document.documentElement;
  setTimeout(function(){ try{ R.className=R.className.replace(/\s*c3-entering/g,' '); }catch(e){} },700);  /* 兜底摘掉 ✓ */
  window.__c3veilOut=function(cb){
    try{ sessionStorage.setItem('c3nav','1'); }catch(e){}
    if(cb) cb();                                 /* v2：**不等、不藏、不拦**，切得跟以前一样快 ✓ */
  };
  /* 页面里 <a href> 的整页跳转也补上标记（只标记，不拦默认行为、不延时）*/
  document.addEventListener('click',function(ev){
    var a=ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if(!a || a.target==='_blank') return;
    var h=a.getAttribute('href')||'';
    if(h.indexOf('/api/')===0) return;
    if(!/^(\/|c3shell:)/.test(h)) return;
    try{ sessionStorage.setItem('c3nav','1'); }catch(e){}
  },true);
})();
