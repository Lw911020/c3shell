# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.27（v2.119.154 · 2026-09-24 按钮合并 + 行序调整 + 删触控坐标显示）'
assert c.count(old) == 1
entry = """## v1.10.28（v2.119.155/156 · 2026-09-24「连接中」从 2 秒缩到 0.7 秒）
- 用户问「现在显示连接中要这么久吗？」→ 现场把耗时拆开量：
  | 环节 | 实测 |
  |---|---|
  | App 下发 /api/cast/start | 0.1s ✓ |
  | C3 侧 python 投屏服务起来并监听 8090 | **约 1.1s** ← 主要开销 |
  | 页面：写死等 1.5s 才挂画面（我上一版写的）+ 重复调了两次 start + 首次挂不上要等 5s 看门狗 | **1.5~3s+** ← 真正的大头 ✗ |
- 优化（v2.119.155）：去掉写死的 1.5s、去掉重复 start、**立刻挂画面 + 每 0.5s 快速重试**（服务没起来也能自己接上）→ 实测 **1.5~2.0s** ✓
- 优化（v2.119.156）：**停止 = 只暂停采集，不杀服务** ✓
  · 采集开关就是 /dev/shm/ui.cast.on（C3 的钩子每次 swap 都看它 ✓）→ 停止时删掉它（采集立即停），服务进程留着
  · 再开始：先探服务在不在 → 在就只把开关打开 + 挂画面（**快路**）→ 实测 **0.5s** 出画面（startCast→firstframe 共 **0.7s** ✓，此前 2.0s）
  · 服务不在才走慢路（拉起 python，约 1.5s）✓
  · 代价：停止后 python 进程常驻（内存约 50MB、clients=0 不采集不编码 → CPU 近 0）✓；要彻底停仍可用 /api/cast/stop
- 回退：releases/c3shell-2.119.154.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.28')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R63/R64（2026-09-24 · v2.119.155/156 · 把"连接中"从 2s 压到 0.7s）
用户：「现在显示连接中要这么久吗？」
- 分段实测：App 下发 start 0.1s ／ C3 侧 python 服务起来 **1.1s** ／ 页面**写死 1.5s 才挂画面 + 重复 start + 首挂失败等 5s 看门狗 = 1.5~3s+（真正大头 ✗，是我上一版自己写的）
- R63：去掉写死延时、去重复 start、立刻挂 + 0.5s 快速重试 → 1.5~2.0s ✓
- R64：**停止只暂停采集（删 /dev/shm/ui.cast.on），不杀服务**；开始时先探服务 → 在则只开开关+挂画面（快路）→ **0.5s 出画面（总 0.7s）** ✓；不在才拉起 python
## R63/R64 复盘
- **"慢"要分段量**：这次把"App 下发／服务启动／页面等待"三段分别计时，一眼看出 1.5s 是**我自己在页面里写死的** ✗ —— 不量就会去瞎优化设备侧 ✓。
- 采集开关是个**文件**（/dev/shm/ui.cast.on）：钩子每次 swap 都查它 → 所以"暂停采集"不需要重启服务，删文件即可 ✓ —— 便宜的重启开关要优先找这种"已有机制"，而不是反复拉进程 ✓。
- 起步延时的优化顺序：先去掉自造的等待 → 再复用常驻进程 → 最后才是动设备侧 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R63/R64')
