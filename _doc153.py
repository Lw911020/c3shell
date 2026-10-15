# -*- coding: utf-8 -*-
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
CL = os.path.join(D, 'CHANGELOG.md')
c = io.open(CL, encoding='utf-8').read()
old = '## v1.10.25（v2.119.150 · 2026-09-24 窗口失焦提示（"点击页面都没反应"的真因））'
assert c.count(old) == 1
entry = """## v1.10.26（v2.119.151~153 · 2026-09-24 删占位图 + 真帧率显示 + 首帧时序修复）
- 用户要求：① 删掉占位图；② 未连接直接显示「未连接 · 点开始投屏开始」；③ 质问「只有 2 帧？！」
- ① 占位图删除 ✓：assets/castcover.jpg 从包里删掉（APK 1.71MB → 1.65MB）；#castPh 改纯深色底；提示层不再压暗
- ③ 「只有 2 帧」的真因（现场查证）：C3 侧采集钩子挂在 **eglSwapBuffers** 上 —— **只在 UI 真正重绘时抓帧** ✓
  → C3 停在静态弹窗时屏幕不变 → 帧数不涨（画面其实是最新的，只是"没在动"），跟卡死无关 ✓
  · 顺带修：C3 的 /dev/shm/ui.rgb 序号当时卡死在 67（钩子没在写）→ 重启 C3 的 ui 进程让 manager 重新拉起带 LD_PRELOAD 钩子的 UI ✓（seq 恢复、帧重新流动）
  · 状态行改成有意义显示：有变化 → 「投屏中 ✓ N.N fps · XXms/帧」；无变化 → 「投屏中 ✓ 已同步（C3 画面无变化）」✓
- ② 未连接态 ✓：「未连接 / 点「开始投屏」开始」；连接中：「连接中… / 正在建立画面流」；中断：「连接中断 / 正在自动重连…」
- 修两个本轮暴露的时序/兼容 bug：
  · **MJPEG 下 img.onload 不触发** ✗ → 提示收不起来，占位与画面叠着显示（区域被撑成两倍高）→ 改成 waitFrame() **主动轮询首帧**（400ms × 30 次）+ 看门狗兜底 ✓
  · 接流时"先设 src 再出提示"会让首帧快时提示留死 → 改成**先提示后设 src** ✓
- 附带发现（记录备查）：MIUI 的 **com.xiaomi.mirror 悬浮窗**（屏幕右侧那张白色圆角小卡）曾把**输入焦点**抢走 → 表现为"点哪儿都没反应"；现场用 am start 夺回焦点后真实触摸即恢复（点「小」→320 / 点「650」→650 实测 ✓）
- 回退：releases/c3shell-2.119.150.apk ✓

"""
c = c.replace(old, entry + old)
io.open(CL, 'w', encoding='utf-8').write(c)
print('OK  CHANGELOG v1.10.26')
PL = os.path.join(D, 'PROJECT-LOG.md')
p = io.open(PL, encoding='utf-8').read().rstrip('\n') + """

## R59~R61（2026-09-24 · v2.119.151~153 · 删占位图 + 真帧率 + 首帧时序）
用户：① 删占位图 ② 未连接只显示"未连接·点开始投屏" ③「只有 2 帧？！」
- ③ 真因：采集钩子挂在 **eglSwapBuffers** → **只在 UI 重绘时抓帧**；C3 静态弹窗 → 帧数不涨（画面是最新的，不是卡死）✓
  · 现场还发现 /dev/shm/ui.rgb 的 seq 卡死（钩子没在写）→ **重启 C3 的 ui 进程**（manager 会用 LD_PRELOAD 重新注入钩子）→ 帧恢复流动 ✓
  · 状态行改为：有变化 → N.N fps；无变化 → 「已同步（C3 画面无变化）」✓
- ①② 完成：#castPh 纯深色（照片素材已删，APK 少 61KB）；未连接/连接中/中断三态文案明确 ✓
- 修两个真 bug：**MJPEG 下 img.onload 不触发** → 提示收不起来、占位与画面叠着（区域两倍高）→ 改 waitFrame() 主动轮询首帧 ✓；接流"先 src 后提示"会让首帧快时提示留死 → 改"先提示后 src" ✓
- 另记：MIUI 的 **com.xiaomi.mirror 悬浮窗**会抢**输入焦点** → 表现为"点哪儿都没反应"；am start 夺回焦点即恢复 ✓
## R59~R61 复盘
- **"帧数不动"先分清是"采集不出帧"还是"屏幕本来就没变"** ✓：钩子在 eglSwapBuffers 上 = 只随重绘出帧 —— 这是设计，不是故障；UI 上就该显示"已同步"而不是干巴巴一个"帧 2" ✗。
- 设备侧钩子会"卡死"（seq 停在某值）：**重启 ui 进程**是最省事且被验证的复活手段（manager 自动带 LD_PRELOAD 重新拉起）✓。
- 屏幕镜像类 UI 的占位/降级态，宁可显示"文字状态"，也不要放一张跟真实画面同源的照片 ✗（这轮又验证一次：照片占位会让人以为"连上了"）。
- WebView 里 MJPEG 的 onload/onerror 事件**不可靠** ✗ → 一律用**主动轮询**判断"有没有画面"（naturalWidth）✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R59~R61')
