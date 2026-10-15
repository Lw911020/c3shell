# -*- coding: utf-8 -*-
"""R60：修"连接中"提示与首帧的时序竞争（先出提示再设 src，onload 才收起）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ① __castAttach：先显示"连接中"，再设 src（否则首帧快时 onload 先跑 → 提示永远留着 ✗）
rep("""      e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(true,'连接中…','正在建立画面流');
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){}""",
"""      ph(true,'连接中…','正在建立画面流');   /* 先出提示，再设 src：避免首帧先到导致提示留死 ✗ */
      e('castImg').src='http://'+HOST+':8090/?t='+Date.now();
      e('castTap').style.display=tapOnImg?'block':'none'; info('投屏中 ✓'); poll(); }catch(x){}""",
    'attach 顺序修正')

# ② 自动接入：同样顺序
rep("""        RUN=true; on=true;
        try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}
        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}""",
"""        RUN=true; on=true;
        try{ ph(true,'连接中…','正在建立画面流'); }catch(x){}   /* 先提示后设 src ✓ */
        try{ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); }catch(x){}""",
    '自动接入顺序修正')

# ③ 开始投屏：同样顺序
rep("""      setTimeout(function(){ e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); ph(true,'连接中…','正在建立画面流'); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
"""      setTimeout(function(){ ph(true,'连接中…','正在建立画面流'); e('castImg').src='http://'+HOST+':8090/?t='+Date.now(); info('已连接 '+HOST+':8090'); poll(); }, 1500);""",
    'castOn 顺序修正')

io.open(P, 'w', encoding='utf-8').write(h)
print('done')
