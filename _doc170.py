# -*- coding: utf-8 -*-
import io, os
R = '/storage/emulated/0/openpilot/dsh-ssh-connector/README.md'
s = io.open(R, encoding='utf-8').read()
add = """

## 语音提醒「为什么没声了」+ 修复（2026-09-24）

**现象**：用户问「最开始让你做的『对话完成之后语音提示任务已完成』为什么没有了？」

**真因（三条）**：
1. **连接器（serve.mjs）没在运行** ✗ —— 而"每一段对话完成"的判定（会话日志的 turn/end）只有连接器在做；
2. 连接器默认端口 3081，但**该端口已被 c3shell APP 自己的内嵌 HTTP 服务占用** ✗ → 即使拉起也绑不上；
3. 连接器过去只把语音项写进自己的队列文件（DSH_HOME/ssh-connector/voice-queue.ndjson），
   而 APP 现在轮询的是**它自己**的 /api/voice/next ✗ → 两边根本不通。

**修复**：
- lib/voice.js：enqueue() 之后**直接把文本推给 APP**（GET http://127.0.0.1:3081/api/voice/say?text=…，可用 DSH_APP_VOICE 覆盖）✓；
- 连接器改用 **3088** 端口启动（DSH_SSH_PORT=3088），不再和 APP 抢 3081 ✓；
- 看门狗 bin/watchdog-connector.sh 常驻（同一环境变量），挂了 30 秒内自动拉起 ✓。

**实测**：GET /api/voice/say?text=语音提醒已恢复 → {"ok":true,"said":"语音提醒已恢复"} ✓（平板出声）；
之后每轮对话结束，连接器会在约 3 秒内推「对话已完成」；需要用户做选择时推「需要你选择」✓。
"""
if '为什么没声了' not in s:
    io.open(R, 'w', encoding='utf-8').write(s.rstrip(chr(10)) + add)
    print('OK  connector README 追加一节')
else:
    print('skip README')

PL = '/storage/emulated/0/openpilot/c3shell/PROJECT-LOG.md'
p = io.open(PL, encoding='utf-8').read().rstrip(chr(10)) + """

## R70（2026-09-24 · 连接器语音提醒恢复 · 非 APP 改动）
用户：「最开始让你做的『对话完成之后语音提示任务已完成』为什么没有了？」
- 真因：① dsh-ssh-connector 没在跑 ② 它的默认端口 3081 已被 c3shell APP 内嵌服务占用（绑不上）③ 它只写自己的队列文件，而 APP 轮询的是 APP 自己的队列 → 两边不通 ✗
- 修复：lib/voice.js 的 enqueue() 增加**直接推给 APP**（GET http://127.0.0.1:3081/api/voice/say?text=…）✓；连接器改 **3088** 启动 ✓；看门狗常驻 ✓
- 实测：/api/voice/say → {"ok":true,"said":"语音提醒已恢复"} ✓（平板出声）；每轮 turn/end 会推「对话已完成」✓
## R70 复盘
- **"功能突然没了"先查"它还在不在跑"**：这次不是代码坏了，是**服务没起来**（且起不来还有端口冲突）✗ → 先 ps + 探活，比读代码快得多 ✓。
- 两个进程抢同一个端口是很隐蔽的坑：APP 内嵌服务"替代"连接器时占了 3081，连接器就永久起不来了 ✗ → 这类替代要同时**把旧服务的端口让开**或显式换端口 ✓。
- 跨进程通信要确认"谁读谁写"：连接器写文件、APP 读自己的队列 = 单向不通 ✗ → 改成**主动推送**（HTTP 调 APP 的本机播报接口）最省事 ✓。
"""
io.open(PL, 'w', encoding='utf-8').write(p)
print('OK  PROJECT-LOG R70')
