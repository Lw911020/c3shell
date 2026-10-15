# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.36（v2.119.171~174 · 2026-09-24 路线分析：去掉综合分析入口 + 进度条修好 + 报条数/用时）'
assert c.count(old) == 1
entry = """## v1.10.37（v2.119.175 · 2026-09-24 范围下拉挪位 + 「最近 N 天」真生效）
- 用户：① 范围选择挪到「存为档案…」前面 ② 选"最近 1 天/3 天"结果都跟"最新 6 条"一样，怀疑数据有问题
- ① 已挪：现在第一行是 [路线 qlog] 范围[下拉] [存为档案…] ✓（原范围单独占第二行）
- ② 真 bug（已修）：APP 侧拼命令时写的是 (limit > 0 ? " --limit N" : "") ✗ → **负数（-1/-3/-7/-30 = 最近 N 天）被丢掉** →
  扫描变成"不带范围"，选几天都一样 ✗。改成 limit != 0 就传 ✓（0 = 全部，本来就该不传）
  · 实测：limit=1 → candidates=1 ✓；limit=-1 → candidates=6 ✓（范围真的生效了）
- 顺带说明（数据本身没问题）：这台 C3 现在**只录到 1 条 route（6 段，全部是 parked 驻车）**，而且是今天的 →
  所以"最近 1 天/3 天/最新 6 条"给出的结果**确实一样** ✓；也因为没有接管段，接管日志会显示「没有被 openpilot 接管过的记录」✓
  想看到有意义的接管分析，需要**开着 openpilot 实际驾驶**录几段 ✓
- 回退：releases/c3shell-2.119.174.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.37')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip(chr(10)) + """

## R77（2026-09-24 · v2.119.175 · 范围下拉挪位 + 最近 N 天生效）
用户：① 范围选择挪到「存为档案…」前 ② 选 1 天/3 天结果都和最新 6 条一样，怀疑数据有问题
- ① 已挪 ✓（第一行：[路线 qlog] 范围[下拉] [存为档案…]）
- ② 真 bug：APP 拼命令用了 limit 大于 0 才追加参数 → 负数（最近 N 天）被丢 → 范围无效；改成 limit 不等于 0 就传 ✓（实测 limit=1 → 1 个候选；limit=-1 → 6 个 ✓）
- 数据本身：C3 只录到 1 条 route（6 段全 parked、今天的）→ 各范围结果确实相同 ✓；无接管段 → 接管日志为空 ✓（需实车开着 OP 跑一段）
## R77 复盘
- 用户质疑"数据有问题"时，**先把参数链每一跳都验一遍**（页面 → API → Java → 脚本）✓：这次就是 Java 那一跳把小负号吃了 ✗。
- 同时要**如实告诉他数据本身是什么样**（只有 1 条驻车 route）—— 否则用户会一直以为是软件坏了 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R77')
