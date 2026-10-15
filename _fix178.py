# -*- coding: utf-8 -*-
"""R79：修 jint() 兜底解析——负数被吞（-1 变成默认 6）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
AP = os.path.join(D, 'java/com/padagent/c3shell/Api.java')
s = io.open(AP, encoding='utf-8').read()
old = """                if (i >= 0) { int c = body.indexOf(':', i); if (c >= 0) { int j = c + 1; while (j < body.length() && " \\t".indexOf(body.charAt(j)) >= 0) j++; int e = j; while (e < body.length() && Character.isDigit(body.charAt(e))) e++; return Integer.parseInt(body.substring(j, e)); } }"""
new = """                // 2026-09-24 R79：**负数也要认**！原来只扫数字 → "-1" 解析成空串抛异常 → 回落默认值 ✗
                //   （这就是"选最近 1 天却按 limit=6 扫"的根因）
                if (i >= 0) { int c = body.indexOf(':', i); if (c >= 0) {
                    int j = c + 1; while (j < body.length() && " \\t".indexOf(body.charAt(j)) >= 0) j++;
                    int e = j; if (e < body.length() && (body.charAt(e) == '-' || body.charAt(e) == '+')) e++;
                    int d0 = e; while (e < body.length() && Character.isDigit(body.charAt(e))) e++;
                    if (e > d0) return Integer.parseInt(body.substring(j, e));
                } }"""
assert s.count(old) == 1, 'jint 未命中'
s = s.replace(old, new)
io.open(AP, 'w', encoding='utf-8').write(s)
print('OK  jint 支持负数')
