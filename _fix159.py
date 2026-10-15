# -*- coding: utf-8 -*-
"""R67：设备查找从主菜单移到「主机」页动作行末尾"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
def rep(s, old, new, tag, cnt=1):
    assert s.count(old) == cnt, tag + ': count=' + str(s.count(old))
    print('OK  ' + tag)
    return s.replace(old, new)

# ① 主机页动作行加「设备查找」（第二行：保存主机/新增/删除 那一行）
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
h = rep(h, """      <button id="hSave" class="primary">保存主机</button>
      <button id="hNew" class="ghost">新增</button>
      <button id="hDel" class="danger ghost">删除</button>
      <span class="grow"></span>""",
"""      <button id="hSave" class="primary">保存主机</button>
      <button id="hNew" class="ghost">新增</button>
      <button id="hDel" class="danger ghost">删除</button>
      <button id="hScan" class="ghost">设备查找</button>   <!-- 2026-09-24 R67：从主菜单移到这里 ✓ -->
      <span class="grow"></span>""", '主机页加「设备查找」按钮')

# ② 去掉主菜单里的「设备查找」（page.html）
h = rep(h, "    item('设备查找','c3shell://tools', null, false, 'tools');\n", "    /* 2026-09-24 R67：设备查找已移到「主机」页动作行 ✓ */\n", 'page 主菜单去掉设备查找')

# ③ 按钮行为（复用原生雷达扫描 c3shell://tools，需带 nonce）
h = rep(h, """  $('#hDel').addEventListener('click',function(){""",
"""  /* 2026-09-24 R67：设备查找（原生雷达扫描对话框）—— 从主菜单搬到这里 ✓ */
  if($('#hScan')) $('#hScan').addEventListener('click',function(){
    try{ location.href='c3shell://tools?t='+Date.now(); }catch(e){}
  });
  $('#hDel').addEventListener('click',function(){""", '主机页按钮行为')
io.open(P, 'w', encoding='utf-8').write(h)

# ④ diag.html 主菜单也去掉
DG = os.path.join(D, 'assets/diag.html')
d = io.open(DG, encoding='utf-8').read()
d = rep(d, "    item('设备查找','c3shell://tools', null, false);\n", "    /* 2026-09-24 R67：设备查找已移到「主机」页动作行 ✓ */\n", 'diag 主菜单去掉设备查找')
io.open(DG, 'w', encoding='utf-8').write(d)

# ⑤ 原生顶栏（平板模式）也去掉
MA = os.path.join(D, 'java/com/padagent/c3shell/MainActivity.java')
m = io.open(MA, encoding='utf-8').read()
m = rep(m, """        bar.addView(action("设备查找", new View.OnClickListener() {
            public void onClick(View v) { scanC3Devices(); }   // 2026-09-22：直接开始扫描（雷达动画）✓
        }));
""", "", '原生顶栏去掉设备查找')
io.open(MA, 'w', encoding='utf-8').write(m)
print('done')
