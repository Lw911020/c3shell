# -*- coding: utf-8 -*-
"""R2 补丁（后端）：/api/ssh/test|exec|term/open 支持 hostId；悬浮窗默认关闭"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
AP = os.path.join(D, 'java/com/padagent/c3shell/Api.java')
MA = os.path.join(D, 'java/com/padagent/c3shell/MainActivity.java')

a = io.open(AP, encoding='utf-8').read()
def rep(s, old, new, tag):
    assert s.count(old) == 1, tag + ': count=' + str(s.count(old))
    print('OK  ' + tag)
    return s.replace(old, new)

a = rep(a, '''        if (path.equals("/api/ssh/test")) {
            Store.Host d = store.defaultHost(); return ssh.testJson(''',
'''        if (path.equals("/api/ssh/test")) {
            // 2026-09-24 R2：按页面"选中的主机"测试（此前只认默认主机 → 手动保存/切换的主机永远测不到 ✗）
            Store.Host d = store.hostById(jstr(body, "hostId")); return ssh.testJson(''', 'Api /test 支持 hostId')

a = rep(a, '''            Store.Host d2 = store.defaultHost(); return ssh.execJson(cmd,''',
'''            Store.Host d2 = store.hostById(jstr(body, "hostId")); return ssh.execJson(cmd,''', 'Api /exec 支持 hostId')

a = rep(a, '''            Store.Host d3 = store.defaultHost(); return ssh.openTermJson(''',
'''            Store.Host d3 = store.hostById(jstr(body, "hostId")); return ssh.openTermJson(''', 'Api /term/open 支持 hostId')
io.open(AP, 'w', encoding='utf-8').write(a)

m = io.open(MA, encoding='utf-8').read()
m = rep(m, 'getBoolean("floatAuto", true)', 'getBoolean("floatAuto", false)', '悬浮窗默认关闭（floatAuto 默认 false）')
io.open(MA, 'w', encoding='utf-8').write(m)
print('done')
