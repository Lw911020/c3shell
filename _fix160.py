# -*- coding: utf-8 -*-
"""R67b：补完 diag.html 与原生顶栏的「设备查找」移除"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

DG = os.path.join(D, 'assets/diag.html')
d = io.open(DG, encoding='utf-8').read()
old = "    item('设备查找','c3shell://tools', null, false, 'tools');\n"
assert d.count(old) == 1, 'diag 未命中: ' + str(d.count(old))
d = d.replace(old, "    /* 2026-09-24 R67：设备查找已移到「设备查找」→「主机」页动作行 ✓ */\n")
io.open(DG, 'w', encoding='utf-8').write(d)
print('OK  diag 主菜单去掉设备查找')

MA = os.path.join(D, 'java/com/padagent/c3shell/MainActivity.java')
m = io.open(MA, encoding='utf-8').read()
old2 = """        bar.addView(action("设备查找", new View.OnClickListener() {
            public void onClick(View v) { scanC3Devices(); }   // 2026-09-22：直接开始扫描（雷达动画）✓
        }));
"""
assert m.count(old2) == 1, 'MainActivity 未命中'
m = m.replace(old2, "")
io.open(MA, 'w', encoding='utf-8').write(m)
print('OK  原生顶栏去掉设备查找')
