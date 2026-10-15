# C3 · SunnyPilot 2025.002（BYD 宋Pro DMI 24）调参 / 修复操作手册

> 2026-09-26 整理。结论来自设备真实数据（qlog 逐帧 + 实时信号），推导过程见 `SYSTEM-ANALYSIS.md`。
> **本手册给的是"照着敲就行"的操作**；每个动作都写了怎么回退。

## 0. 一句话结论

|| 问题 || 成因（已证实） || 处理 ||
|| 急转/急弯力矩过大 || ① 横向控制器的**低速项**把期望曲率放大 100~220 倍（`latcontrol_torque.py`），
② 大角度时扭矩 95~100% 打到满量程 ±1.000，③ BYD 车端**非线性力矩整形**（`BydUseNonLinearTorque=1`）加重 || 见 §3（三个旋钮）||
|| 停车后不能下线 ||

- **设备不 go offroad**：点火检测线常高（`ignitionLine=True` 停车时也是真，`ignitionCan` 恒 False）→ 永远 onroad → `MaxTimeOffroad` 永不触发 → 驻车也在录日志（已 2.1 GB / 50 段）⇒ **硬件为主**，或打 §5 的驻车启发式补丁
- **辅助不解除**：`Mads=1`（SunnyPilot MADS：横纵向独立、驻车不自动解除）⇒ 参数 `Mads=0` 即可验证 |

## 1. 现状速览（不用改任何东西就能看）

|||bash|
| ssh comma@192.168.0.66 |
| cd /data/openpilot |
| /usr/local/venv/bin/python3 .dsh/sig.py      # 转向故障 / 档位 / 车速 |
| /usr/local/venv/bin/python3 .dsh/live.py     # panda 点火线 / 电压 / MADS / onroad |
| /usr/local/venv/bin/python3 .dsh/panda.py    # panda 全字段 + 生效的横向增益 |
|||
> 或直接在 **车机 APP → 运维 → 后台任务 → 点「横向诊断」**（会自动推送脚本并跑最新 10 段）✓

## 2. 基线采集（做任何改动之前先存一份）

|||bash|
| cd /data/openpilot |
| /usr/local/venv/bin/python3 .dsh/lat_report.py > /sdcard/baseline.json   # 不带参数 = 最新 10 段 |
| cat /sdcard/baseline.json |
|||

关键指标（对比就看这四个）：`sat`（饱和帧数）、`sat_low_speed`（低速饱和）、
`max_abs_steer_rate`（最大方向盘角速率 °/s）、`mean_abs_torque`。

## 3. ① 的三个旋钮（按"安全 → 激进"排序）

**旋钮 A（先试这个，纯参数、秒回退）**
|||bash|
| echo -n 0 > /data/params/d_sp/BydUseNonLinearTorque    # 关掉 BYD 非线性力矩整形 |
| # 想恢复： echo -n 1 > /data/params/d_sp/BydUseNonLinearTorque |
|||
改完**不用重启**（参数每 50 帧重读一次，约 1 秒生效）。

**旋钮 B（代码补丁：低速猛推砍一半）**
|||bash|
| cd /data/openpilot |
| /usr/local/venv/bin/python3 .dsh/patch_lat_speed.py dry     # 先看 diff + 语法校验 |
| /usr/local/venv/bin/python3 .dsh/patch_lat_speed.py apply   # 备份 + 打补丁 |
| # 回退： /usr/local/venv/bin/python3 .dsh/patch_lat_speed.py revert |
|||
生效需要**重启 openpilot**（`sudo systemctl restart comma`）——
⚠ **车辆通电时重启会锁「LKAS 故障」，必须熄火重启车辆才能清** → 请在**熄火后**打补丁。

**旋钮 C（用 Override 覆盖学习值）**
|||bash|
| echo -n 1 > /data/params/d_sp/TorqueParamsOverrideEnabled |
| echo -n 1.1 > /data/params/d_sp/TorqueParamsOverrideLatAccelFactor   # 学习值是 1.296，别用默认的 2.5！ |
| echo -n 0.12 > /data/params/d_sp/TorqueParamsOverrideFriction        # 学习值是 0.1396 |
|||
> ⚠ 默认 `TorqueParamsOverrideLatAccelFactor=2.5` ≈ 学习值的 **2 倍** → 直接打开会让转向**更猛**。
> 回退：`echo -n 0 > ...TorqueParamsOverrideEnabled`

## 4. A/B 对比流程（一次性做完，约 20 分钟）

|||text|
| 0) 熄火状态：先打 §3 旋钮 B 补丁（或跳过）        → 重启 openpilot |
| 1) 开同一段路（含中高速连续弯 + 一次打灯变道）     → lat_report.py > /sdcard/run-A.json |
| 2) echo -n 0 > BydUseNonLinearTorque               → 立刻生效，再开同一段 → run-B.json |
| 3) 对比： python3 - <<PY |
|    import json; A=json.load(open('/sdcard/run-A.json')); B=json.load(open('/sdcard/run-B.json')) |
|    for k in A: |
|      if k in B: print(k, 'sat', A[k]['sat'], '->', B[k]['sat'], '| 角速率', round(A[k]['max_abs_steer_rate']), '->', round(B[k]['max_abs_steer_rate'])) |
|    PY |
|||
判据：`sat` 与 `max_abs_steer_rate` 明显下降、而车道居中没变差 → 该旋钮有效，保留。

## 5. ② 的两条路

**(a) 辅助不解除** → 关 MADS（参数，秒级）
|||bash|
| echo -n 0 > /data/params/d_sp/Mads        # 恢复"驻车/踩刹车就解除"的行为 |
| # 想恢复： echo -n 1 > /data/params/d_sp/Mads |
|||

**(b) 设备不 go offroad** → 建议**先查硬件**：点火检测线是否接在常电（停车时 panda 仍报 `ignitionLine=True` + `14V`）。
硬件不好动时，可用**驻车启发式补丁**（默认关闭，可回退）：
|||bash|
| cd /data/openpilot |
| /usr/local/venv/bin/python3 .dsh/patch_offroad_parked.py dry     # 看 diff + 语法校验 |
| /usr/local/venv/bin/python3 .dsh/patch_offroad_parked.py apply   # 熄火后再做！ |
| /usr/local/venv/bin/python3 .dsh/patch_offroad_parked.py setmin 10   # 档位P+静止 10 分钟 → 视为熄火 |
| # 关闭兜底：setmin 0 ；完全回退：patch_offroad_parked.py revert |
|||
> 生效后 offroad → 再由 `MaxTimeOffroad=1800`（30 分钟）走到关机/熄屏那一步。

## 6. 回滚清单（任何一步都能退）

|| 动作 || 回退 ||
|| 旋钮 A/B/C 参数 || `echo -n <原值> > /data/params/d_sp/<参数>`（原值见 `SYSTEM-ANALYSIS.md` §2）||
|| `LOW_SPEED_Y` 补丁 || `patch_lat_speed.py revert` ||
|| 驻车启发式补丁 || `patch_offroad_parked.py revert` + `setmin 0` ||
|| 投屏钩子（换系统会丢） || 投屏页点「一键安装投屏能力」 ||
|| APP 版本 || `adb install -r c3shell/releases/c3shell-<版本>.apk`（平板 127.0.0.1:<无线调试端口>；车机 192.168.0.100:5555）||
|| 源码/整套状态 || `_attic/rollback-20260924-223509/`（+ ADAPTATION §8.1）||

## 7. 常见问题

|| 现象 || 原因 || 处理 ||
|| 仪表弹「LKAS 故障：请重启车辆以启用」 || 通电时重启设备/openpilot → 车机 EPS 锁永久故障 || 熄火 → 等 10 秒 → 重新上电（只能这样清）|
|| 投屏没画面、投屏能力一直「检查中」 || 换系统后投屏钩子丢（`/dev/shm/ui.rgb` 不存在）|| 投屏页「一键安装投屏能力」（约 1 分钟，装钩子会重启一次设备 → 熄火后做）|
|| APP 界面卡、点菜单没反应 || 设备离线时 SSH 请求堆积（旧版）|| 升级到 3.00.55+（700ms 预探测 + 8 秒负缓存 + 单飞）|
|| 驻车也在录日志、耗电 || 点火线常高（本手册 §5b）|| 硬件 或 驻车启发式补丁 |

## 8. 横向增益：真正的根因（2026-09-27 实车后新增，先看这节）

**一句话**：车的数据要求 `latAccelFactor = 2.20`，但栈把它夹在 `[0.5, 1.5]`，实际只给 **1.30** → 弯道只输出约六成力矩 ⇒ **弯里向外侧跑、大角度打满、感觉「力矩大还压线」**。

**先确认现状**（只读）：
|||bash|
| for k in EnforceTorqueControl LiveTorqueParamsToggle LiveTorqueParamsRelaxedToggle TorqueParamsOverrideEnabled TorqueParamsOverrideLatAccelFactor; do printf "%s=" $k; cat /data/params/d_sp/$k 2>/dev/null; echo; done |
|||
> 期望：`LiveTorqueParamsToggle=1`、`LiveTorqueParamsRelaxedToggle=1`、`TorqueParamsOverrideEnabled=0`；**`EnforceTorqueControl` 为空（=0），就是它让夹子停在 ±0.5**。

**第 1 步（熄火后做，需重启 OP）——解锁夹子**：
|||bash|
| echo -n 1 > /data/params/d_sp/EnforceTorqueControl   # 只在 init 读一次，必须重启 openpilot |
|||
重启后跑一段带弯的路：`latAccelFactorFiltered` 应从 1.30 往 2.0 爬（`latAccelFactorRaw` 一直是 2.2）。

**第 2 步（热生效，无需重启）——显式覆盖做 A/B**：
|||bash|
| P=/data/params/d_sp
| # 打开覆盖（先 1.6，观察后 1.8 → 2.0；千万别留出厂默认 2.5，会过冲）
| echo -n 1    > $P/TorqueParamsOverrideEnabled
| echo -n 1.6  > $P/TorqueParamsOverrideLatAccelFactor
| echo -n 0.15 > $P/TorqueParamsOverrideFriction
| echo -n 0.0  > $P/TorqueParamsOverrideLatAccelOffset
| echo -n 0.3  > $P/TorqueParamsOverrideSteerActuatorDelay
| # A/B 的另一半：echo -n 0 > $P/TorqueParamsOverrideEnabled
|||
生效时间 ≤3 秒（控制器每 300 帧重读）。

**验证过了的标志**：APP「横向诊断」里弯道段 `dev` 不再 100% 外偏、大角度饱和帧下降；若 `dev` 明显变负（往内侧压）说明给多了，退 1.4。

**回滚**：`echo -n 0 > /data/params/d_sp/TorqueParamsOverrideEnabled`（立刻回学习值）；`echo -n 0 > /data/params/d_sp/EnforceTorqueControl`（需重启，回到今天状态）。

## 9. 反事实取证：crosswatch（回答「我不拉回来会不会压线」）

**为什么需要**：紧弯里 modelV2 会丢车道线（实测段 32–40 有 62%–100% 的帧没线），而驾驶员每次在压线前拉回 →「压线次数」永远统计不到。
crosswatch 一边记车道线几何、一边记控制器自报的期望/实际横向加速度，并在**你拉回的那一瞬间**把「当时往外漂多快、还有几秒压线」写进事件文件。

**开（车机上，只读不干预控制；建议 2 小时 = 7200 秒）**：
|||bash|
| ssh comma@192.168.0.66 "cd /data/openpilot && nohup /usr/local/venv/bin/python3 .dsh/crosswatch.py 7200 > .dsh/crosswatch.log 2>&1 &" |
|||

**看（实时每 5 秒一行）**：
|||bash|
| ssh comma@192.168.0.66 "tail -2 /data/openpilot/.dsh/crosswatch-*.live.jsonl"            # dev / 外偏Δa / 事件数 / maxdev |
| ssh comma@192.168.0.66 "tail -20 /data/openpilot/.dsh/crosswatch-*.events.jsonl"          # 每次接管的反事实记录 |
|||
> 事件字段：`dev`、`dev_rate_per_s`、`t_cross_s`（还有几秒压线）、`a_out`（朝外少给多少 m/s²）、`traj`（前 1.5 s 轨迹）、`why`（driver_steer / lat_off / predicted_cross）。

**收工**：
|||bash|
| ssh comma@192.168.0.66 "pkill -f crosswatch[.]py; ls -t /data/openpilot/.dsh/crosswatch-* | head -3" |
|||

**读结果**：把 CSV/events 拷回来（`scp comma@192.168.0.66:/data/openpilot/.dsh/crosswatch-*.csv .`），或直接在这里贴 events.jsonl 让我算。
