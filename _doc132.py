# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.12（当前）'
assert c.count(old) == 1
new_entry = """## v1.10.13（v2.119.132 · 2026-09-24 承接上一轮：投屏页版面 + 主机连接）
- 投屏页版面按用户要求重做，并修掉上一版（.130）引入的三个真 bug：
  - **大小档失效**（真因）：上一版给 #castBox 加了 width:100% !important，把页面 JS 写的**内联宽度**盖掉了 ✗ → 删除该覆盖 ✓。
    实测：小 320px / 中 480px / 满宽 838px / 适配 484px 全部生效 ✓
  - **整页/整卡黑底**：去掉 #tab-cast、#castCard 的黑底；HUD（主板/内存/负载/设备）改用主题色 var(--bg2)（原来写死 #0b0f14 → 与整体不搭的“黑条”）✓
  - **未投屏时的黑长条**（真因）：页面判定“是否在投屏”用的是 out.indexOf('running')>=0，而 C3 停流时返回的是 **notrunning** —— 里面也含 running ✗
    → 页面误以为在投屏：挂一条连不上的流，同时把封面隐藏 → 只剩一条黑长条 ✓。改为**首行严格判定** isRunning() ✓
  - 画面区移到卡片**最下面**；桌面悬浮窗开关移到**画质那一行后面**（原来那行在 .body **之外**，CSS order 永远找不到它 → 一直停在最底部 ✗；现直接写进 DOM 顺序）✓
  - 未投屏用**封面照片**占位（assets/castcover.jpg，2:1，padding-top:50% → **不缩短高度** ✓）；流断了/连不上时 img.onerror 自动回封面 ✓
- **手动保存的主机连不上**（真因两条）：
  - 后端 /api/ssh/test 只认“默认主机”，页面传的 hostId 被**忽略** ✗ → /test、/exec、/term/open 一律支持 hostId ✓
    实测：默认主机正常连通；临时建一台指向 10.255.255.1 的主机如约超时（证明 hostId 真的生效 ✓，测完已删 ✓）
  - 页面切换主机/保存主机后**不同步**“默认主机” → 后端仍打旧主机 ✗ → hostSel change 与保存主机后都补一次 action=default ✓
- 桌面悬浮窗改为**默认关闭**（floatAuto 默认 false）✓（实测 APP 日志无 FLOAT 自动开启行 ✓）
- 内置 HTTP 服务补图片 MIME（.jpg/.png/.webp/.gif）✓（封面之前是 application/octet-stream）
- 验证：check_page OK ✓ · 平板实机截图核对（投屏页 / 未投屏封面不缩高 / 大小四档 / 一级菜单九个入口全部有交互 ✓，见 _attic/now/v131_*.png、v132_ph.png）
- 回退：装 releases/c3shell-2.119.34-安全版.apk（或上一版 2.119.130）

"""
c = c.replace(old, new_entry + '## v1.10.12')
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG 加 v1.10.13')

PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read()
p = p.rstrip('\n') + """

## R45（2026-09-24 承接上一轮 · v2.119.131/132 · 投屏页版面 + 主机连接 + 悬浮窗默认）
本轮起点：上一轮（.130）末尾连续三次 LLM 流中断（SSE STREAM_CLOSED），用户 06:13~06:26 连发 5 条反馈没人处理 ✗ —— 本轮先把状态重建（读上一轮会话记录 + 现场核对），再逐条修。
| 项 | 真因 | 处理 | 实测 |
|---|---|---|---|
| 投屏大小档点不动 | .130 的 #castBox{width:100% !important} 盖掉了 JS 内联宽度 | 删掉该覆盖 | 小/中/满宽/适配 = 320/480/838/484px ✓ |
| 整页/整卡/HUD 黑底 | .130 把 #tab-cast、#castCard 涂黑；HUD 写死 #0b0f14 | 只留画面区黑底做 letterbox；HUD 用 var(--bg2) | 截图 ✓ |
| 未投屏时黑长条 | **notrunning 里含 running** → 误判“在投屏”：挂死流 + 藏封面 | 首行严格判定 isRunning()；img.onerror 回封面 | 停流后显示封面且 2:1 不缩高 ✓ |
| 画面没在最下面 / 悬浮窗开关位置 | 悬浮窗那行在 .body **之外**，CSS order 找不到 → 永远排最后 | DOM 顺序直接排好（去 JS 重排） | 截图 ✓ |
| 手动保存的主机连不上 | ① 后端 /test 忽略 hostId（只认默认主机）② 页面切/存主机不同步默认主机 | 三个端点支持 hostId + 页面补 action=default | 临时主机 10.255.255.1 如约超时 ✓（证明 hostId 生效）|
| 悬浮窗默认该关 | floatAuto 默认 true（且自动开启那段写错在 layout=auto 分支里） | 默认改 false | APP 日志 0 条 FLOAT ✓ |
| 主菜单其他入口没交互？ | 现场逐项核对：**9 个一级入口全部有交互** ✓（控制台/投屏/转向诊断/设备查找/AI 分析/软件设置/赞赏/界面设置/软件日志）—— 大概率是 .130 那版坏页面/缓存造成的假象 ✓ | 不需要改 | a11y 点击逐项验证 ✓ |
## R45 复盘
- **“点错一项” vs “没反应”**：这轮把 adb 坐标点击和 a11y 点击分开看，发现 WebView 的 a11y 坐标在这台机器上**不可靠**（点“设备查找”会落到“AI 分析”）→ 坐标类验证一律以 **a11y ACTION_CLICK** 或截图为准 ✓；不要再拿 uiautomator bounds 当点击坐标用 ✗。
- **测试状态要先清干净**：验证“未投屏封面”时必须先把 C3 侧 mjpeg 停掉（否则页面自动接入，看到的永远是流，看不出封面对不对）✓ —— 这也正是“投屏没开却像在投屏”的来源。
- **子串判定是坑**：indexOf('running') 命中 notrunning —— 状态类字符串一律按**首行/精确匹配**判定 ✓。
- 上一轮的教训（LLM 流中断后）用户连发 5 条都没人接 ✓ → 本轮开头先重建状态再动手，避免“接着瞎改” ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG 加 R45')

H = os.path.join(D, 'HANDOVER.md')
h = io.open(H, encoding='utf-8').read()
h = h.replace('## 〇、最新状态（本条最优先 ✓）',
"""## 〇、最新状态（本条最优先 ✓）
- **2026-09-24 承接上一轮（R45）→ 当前版本 = v2.119.132** ✓ 已装平板并实测
  · 投屏页：HUD 不再黑底、画面区在黑底 letterbox 里并**排在卡片最下**、悬浮窗开关跟在**画质**后面 ✓
  · 大小四档实测生效（小 320 / 中 480 / 满宽 838 / 适配 484 CSS px）✓；未投屏时用**封面照片**占位且**不缩高** ✓
  · 页面判定“在不在投屏”改为**首行严格匹配**（notrunning 曾被误判成 running ✗）✓；悬浮窗**默认关闭** ✓
  · /api/ssh/test|exec|term/open 支持 hostId + 页面切/存主机同步默认主机 → **手动保存的主机可以连了** ✓
  · 回退：releases/c3shell-2.119.130.apk（上一版）/ 2.119.34-安全版.apk（安全版）✓
  · 验证截图在 _attic/now/（v131_cast / v131_fit / v132_ph）✓
""", 1)
io.open(H, 'w', encoding='utf-8').write(h)
print('OK  HANDOVER 更新最新状态')
