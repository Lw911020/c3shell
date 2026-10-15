# -*- coding: utf-8 -*-
import io, sys, shutil
D='/storage/emulated/0/openpilot/c3shell/'
p = D+'assets/diag.html'
s = io.open(p, encoding='utf-8').read()
def rep(s, old, new, tag):
    if old not in s: sys.exit('锚点没找到: '+tag)
    return s.replace(old, new, 1)

# ① 三个控件 → 一个按钮（目录显示保留为小字提示）
s = rep(s, """      <button id="pexp">导出 CSV</button>
      <button id="pdir" class="gh" title="选择 CSV 导出到哪个目录（系统目录选择器，选一次即记住）">导出目录…</button>
      <span id="pdirNow" class="note">→ 下载</span>
<label class="note" style="display:flex;gap:6px;align-items:center">导入并写入 <button id="pimpBtn" class="gh">选择文件…</button></label>""",
"""      <button id="pcsv" class="pri" title="导出 CSV / 选择导出目录 / 导入并写入，都在这一个按钮里">CSV 导入/导出…</button>
      <span id="pdirNow" class="note">→ 下载</span>""", '合成按钮')
# 兜底：若上面锚点因空格不同没命中，退化成分别替换
if 'id="pexp"' in s:
    s = rep(s, """      <button id="pexp">导出 CSV</button>""",
"""      <button id="pcsv" class="pri" title="导出 CSV / 选择导出目录 / 导入并写入，都在这一个按钮里">CSV 导入/导出…</button>""", '退路1')
    s = rep(s, """      <button id="pdir" class="gh" title="选择 CSV 导出到哪个目录（系统目录选择器，选一次即记住）">导出目录…</button>
      <span id="pdirNow" class="note">→ 下载</span>""",
"""      <span id="pdirNow" class="note">→ 下载</span>""", '退路2')
    s = rep(s, """<label class="note" style="display:flex;gap:6px;align-items:center">导入并写入 <button id="pimpBtn" class="gh">选择文件…</button></label>
""", "", '退路3')

# ② 换掉 #pexp / #pdir / #pimpBtn 的绑定 → 一个菜单
old_block_a = """document.getElementById('pexp').onclick=exportAll;
// 2026-09-22 用户要求：导出要能选目录
document.getElementById('pdir').onclick=function(){
  if(!window.__C3APP){ toast('浏览器预览里无法选择目录','warn'); return; }
  location.href='c3shell://save-dir';
};
window.__saveDir=function(name){"""
new_block_a = """/* 2026-09-22 用户要求：导出 CSV / 选导出目录 / 导入并写入 —— 合成一个按钮，点开选功能 ✓ */
function _csvMenu(){
  var old=document.getElementById('_csvMenu');
  if(old){ old.remove(); return; }
  var b=document.getElementById('pcsv'); if(!b) return;
  var r=b.getBoundingClientRect();
  var m=document.createElement('div'); m.id='_csvMenu';
  m.style.cssText='position:fixed;z-index:998;background:var(--card);border:1px solid var(--line);border-radius:10px;'
    +'box-shadow:0 10px 28px rgba(0,0,0,.22);padding:6px;min-width:230px';
  m.style.left=Math.max(8,Math.min(r.left, (window.innerWidth||360)-240))+'px';
  m.style.top=(r.bottom+6)+'px';
  function item(label, hint, fn){
    var d=document.createElement('div');
    d.style.cssText='padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13.5px';
    d.innerHTML='<b>'+label+'</b>'+(hint?('<div class="note" style="font-size:11.5px;margin-top:2px">'+hint+'</div>'):'');
    d.onmouseenter=function(){ d.style.background='var(--bg3)'; };
    d.onmouseleave=function(){ d.style.background=''; };
    d.onclick=function(){ m.remove(); fn(); };
    m.appendChild(d);
  }
  var dirTxt=((document.getElementById('pdirNow')||{}).textContent||'下载').replace(/^→\s*/,'');
  item('导出 CSV','导出全部当前参数 → '+dirTxt, function(){ exportAll(); });
  item('选择导出目录…','换一个保存 CSV 的文件夹', function(){
    if(!window.__C3APP){ toast('浏览器预览里无法选择目录','warn'); return; }
    location.href='c3shell://save-dir';
  });
  item('导入并写入…','选一个 csv，批量写入设备参数', function(){
    if(!window.__C3APP){ toast('浏览器里请用电脑选择文件','warn'); return; }
    location.href='c3shell://pick-csv';
  });
  document.body.appendChild(m);
  setTimeout(function(){
    document.addEventListener('click', function h(ev){
      if(m.contains(ev.target)) return;
      m.remove(); document.removeEventListener('click', h, true);
    }, true);
  }, 40);
}
document.getElementById('pcsv').onclick=_csvMenu;
window.__saveDir=function(name){"""
s = rep(s, old_block_a, new_block_a, '菜单绑定')

# ③ 去掉 #pimpBtn 的绑定（元素已删 ✗ 不删会抛错）
s = rep(s, """// 2026-09-22：改成原生选择器（WebView 里 <input type=file> 点不动 ✗）
document.getElementById('pimpBtn').onclick=function(){
  if(!window.__C3APP){ setSt('浏览器里请用电脑选择文件'); return; }
  location.href='c3shell://pick-csv';
};
""", "", '去掉 pimpBtn 绑定')
io.open(p,'w',encoding='utf-8').write(s)
print('diag.html OK 合成一个按钮 + 菜单')

ch = D+'CHANGELOG.md'
s = io.open(ch, encoding='utf-8').read().rstrip() + """

## v2.77
- 参数页：把「导出 CSV / 导出目录… / 导入并写入（选择文件…）」**合成一个按钮**「CSV 导入/导出…」，
  点开弹小菜单选功能 ✓（按钮旁仍显示当前导出目录）
"""
io.open(ch,'w',encoding='utf-8').write(s)
shutil.copy(ch, D+'assets/CHANGELOG.md')
print('CHANGELOG.md OK (v2.77)')

