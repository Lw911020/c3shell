# -*- coding: utf-8 -*-
"""R77：① 范围下拉挪到「存为档案…」前面 ② 修负数 limit 被丢（1天/3天失效）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

# ① 页面：移动范围下拉
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
A = '<span class="note" style="white-space:nowrap">范围</span>'
i = h.find(A)
assert i > 0, '范围 span 未找到'
B = h.find('</select>', i)
assert B > i, 'select 未找到'
B += len('</select>')
chunk = h[i:B]
h = h[:i] + h[B:]
# 插到「存为档案…」按钮前面
anchor = '<button id="aiSaveProf" class="ghost">存为档案…</button>'
j = h.find(anchor)
assert j > 0, '存为档案 未找到'
h = h[:j] + chunk + '\n          ' + h[j:]
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  范围下拉已挪到「存为档案…」前')

# ② Java：负数 limit（最近 N 天）要传给脚本
S = os.path.join(D, 'java/com/padagent/c3shell/Ssh.java')
s = io.open(S, encoding='utf-8').read()
old1 = """            String cmd = "rm -f " + SCAN_PROG + " " + SCAN_RES + "; "
                    + "nohup python3 " + path + " --root " + shq(r) + (limit > 0 ? (" --limit " + limit) : "")"""
new1 = """            // 2026-09-24 R77：负数 = 最近 N 天（脚本支持）—— 原来只传 >0，导致"最近 1/3 天"选了没用 ✗
            String cmd = "rm -f " + SCAN_PROG + " " + SCAN_RES + "; "
                    + "nohup python3 " + path + " --root " + shq(r) + (limit != 0 ? (" --limit " + limit) : "")"""
assert s.count(old1) == 1, 'routesScanStart 未命中'
s = s.replace(old1, new1)

old2 = """        String args = "--root " + shq(r) + (limit > 0 ? (" --limit " + limit) : "") + (segments ? " --segments" : "");"""
new2 = """        String args = "--root " + shq(r) + (limit != 0 ? (" --limit " + limit) : "") + (segments ? " --segments" : "");   // R77：负数=最近 N 天 ✓"""
assert s.count(old2) == 1, 'routesScanJson 未命中'
s = s.replace(old2, new2)
io.open(S, 'w', encoding='utf-8').write(s)
print('OK  Java 支持负数 limit（最近 N 天）')
