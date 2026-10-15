# -*- coding: utf-8 -*-
"""R74b：特色介绍里 AI 分析的描述同步（已改为接管日志为主）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
old = """      ['🤖','AI 分析','一键跑完设备现状+参数差异+路线 qlog 分诊+采样报告，给综合结论；还能带上真实数据问 AI，解答车主疑问。','aian'],"""
new = """      ['🤖','AI 分析','扫最近路线（接管日志）给出结论；问 AI 时自动带上设备现状与参数差异等真实数据，解答车主疑问。','aian'],"""
assert h.count(old) == 1, '未命中特色介绍'
h = h.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  特色介绍描述同步')
