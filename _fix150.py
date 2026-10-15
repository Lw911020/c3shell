# -*- coding: utf-8 -*-
"""R58：自由窗口失焦时给明确提示（用户反馈"点击页面都没反应"的真因）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① 投屏卡片顶部加一条"窗口未激活"提示
rep("""      <h4>投屏与悬浮（主菜单）</h4>
      <div class="body">""",
"""      <h4>投屏与悬浮（主菜单）</h4>
      <div id="castFocusTip" style="display:none;align-items:center;gap:6px;margin:0 0 6px;padding:6px 10px;border-radius:8px;background:#fff4d1;color:#7a5200;font-size:12px;border:1px solid #f0d79a">
        <b>窗口未激活</b><span>点一下窗口（或标题栏）再操作 —— 自由窗口失焦时点击会落到别的窗口上</span>
      </div>
      <div class="body">""", 'HTML 失焦提示条')

# ② 失焦/回焦显隐 + 回焦自动重连接流
rep("""  try{ window.addEventListener('resize', function(){ try{ if(cw==='fit') wset('fit'); }catch(x){} reattach('窗口变化'); });""",
"""  /* 2026-09-24 R58：自由窗口（车机/平板分屏）失焦时点击会落到别的窗口 → 明确提示 ✓
     起因：用户反馈"点击页面都没反应"，实测是输入焦点跑到了桌面（launcher）✗ */
  function focusHint(on){ try{ var h=e('castFocusTip'); if(h) h.style.display=on?'flex':'none'; }catch(x){} }
  try{
    window.addEventListener('blur', function(){ focusHint(true); });
    window.addEventListener('focus', function(){ focusHint(false); reattach('窗口回到前台'); });
  }catch(x){}
  try{ window.addEventListener('resize', function(){ try{ if(cw==='fit') wset('fit'); }catch(x){} reattach('窗口变化'); });""",
    'JS 失焦提示')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
