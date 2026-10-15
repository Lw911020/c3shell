# C3 设备系统分析（SunnyPilot 2025.002 · BYD 口）

> 2026-09-26 第 1 轮。设备 comma three（SDA845，8 核）；系统 SunnyPilot 2025.002.000 / release-c3 / origin sunnypilot。
> 全部基于设备真实数据（qlog + 实时信号）。

## 0. 调试工具箱（仓库 tools/device/ + 设备 /data/openpilot/.dsh/）

| 脚本 | 作用 |
|---|---|
| `sig.py` | 实时 carState/controlsState/selfdriveState 关键位（转向故障/档位/车速/横向是否允许）|
| `live.py` | panda（点火线/电压/controlsAllowed）+ onroad 判据 + MADS 状态 + loggerd 是否在跑 |
| `an1.py` | 最近路段概览：时长/车速/接管率/扭矩/角度/提示/事件 |
| `an2.py` | 全部路段分类（真开过 / 只是停着），找最近一次行车 |
| `an4.py` | 单路段横向深挖：扭矩 vs 转向角、latAccel、事件、SP 自定义消息 |
| `an5.py` | 时间序列（每 2 秒一行）+ MADS 占比 + steerRatio/学习扭矩参数 |

要点：必须 `/usr/local/venv/bin/python3`（系统 python 没 capnp/numpy）；必须先 `cd /data/openpilot`；
路段在 `/data/media/0/realdata/0000000c--32cbec9ac8--NN/`（分析用 qlog.zst 就够）；设备时钟是 **UTC**（比平板慢 8 小时）。

## 1. 运行逻辑

`@
modeld ─► 期望曲率/轨迹 ─► controlsd
                             │ 横向：latcontrol_torque/pid/angle.py + sunnypilot 扩展 latcontrol_torque_ext*.py
                             │ 纵向：ACC/雷达为主
                             ▼
                        carControl ─► card（BYD 车端为 pyc 字节码，源码不可见；非线性力矩整形在这里）
                                        ▼
                                   panda ─► 车机 EPS ─► 方向盘
                                        ▲
      相机/pose ◄── 车的实际响应 ◄───────┘
               └─► locationd 学 steerRatio/stiffness/angleOffset；torqued 学 latAccelFactor/friction
                   └─ 学到的值回灌横向控制器 = 闭环自适应 ✓
`@

- **MADS**（SP 横向独立助手）：实测 `mads.enabled=True, active=100%`，而 `selfdriveState.enabled` 一直 False
  → 用 enabled 判断"有没有在控车"是错的（我第一版脚本就踩了这个坑）。
- 本次学习值：`steerRatio=18.9`、`stiffness=0.999`（=默认，没学出）、`angleOffset=0`、
  `latAccelFactor=1.295`、`friction=0.1397`（后两个在动 → 扭矩学习在跑）。

## 2. 闭环？外部参数有没有用？

**是闭环**（相机/pose → 学车模型 → 回灌控制器；证据：扭矩参数非默认且在变化）。
但 `stiffness` 停在 1.0、`angleOffset=0` → 只学了扭矩类，刚度/偏置没学（BYD 用扭矩控制，正常）。

| 类别 | 例子（当前值） | 有用吗 |
|---|---|---|
| 系统自写的学习值 | `LiveTorqueParameters` / `LateralPIDLearnedParams` / `LateralPIDOffsets`(ki_mid=-0.006) | 有用，但**会被学习覆盖**（手改也会被重写）|
| 真正生效的开关 | `BydUseNonLinearTorque=1` ★ / `LateralRulePlannerEnabled=1` / `MadsSteeringMode=0` / `NeuralNetworkLateralControl=0` / `BlinkerPauseLateralControl=0` / `BlinkerMinLateralControlSpeed=20` | 有用（决定用哪套控制器、力矩怎么整形）|
| **当前是死的** | `TorqueParamsOverrideEnabled=0` → 下面的 `Friction=0.1 / LatAccelFactor=2.5 / LatAccelOffset=0` **完全没生效**；`CustomTorqueParams=0` 同理 | **没用**（改了也白改，除非先打开 Override）|

> 结论：**不是随便调都有效**。要改横向手感，动第二类开关，或先打开 Override 再改那三个值。

## 3. 问题①：急转时横向力矩过大、压到旁边车道

实测（--3 / --9 城市路 0~12.7 m/s）：

`@
--3  |τ| max 1.000  p95 1.000   |angle|>25° 时 p95 1.000（191 样本）
    时间序列：v=1.7 angle=-519° → τ=-0.992；v=4.2 angle=-137.9° → τ=+1.000；v=4.3 angle=123.5° → τ=+1.000
    MADS 频繁 overriding（用户在跟方向盘抢）
--9  |τ| max 1.000  p95 0.907   |angle|>25° 时 p95 1.000（200 样本）；v=5.3 angle=-110° → τ=-1.000
`@

- 扭矩**打到满量程 ±1.000**，集中在**低速 + 大转向角**（掉头/急弯/揉库）→ 与"急转时力矩过大"完全吻合。
- 头号嫌疑 **`BydUseNonLinearTorque=1`**（BYD 专口非线性力矩整形，大角度放大力矩；实现在 pyc 里）。
- 次要：`LateralPIDOffsets.ki_mid=-0.006`、`CustomTorqueParams=0`。

**A/B 计划（需你开一段车）**：置 0 → 跑同一段（含急弯）→ 我再出 τ 饱和次数/大角度 τ 对比；
若没变化 → 查 `LateralRulePlannerEnabled` 或开 Override 调 `LatAccelFactor`。

## 4. 问题②：停了之后不能"下线"

实测（**现在**就成立）：

`@
pandaStates[0]: ignitionLine=True  ignitionCan=False  controlsAllowed=False  voltage=14.17V
carState: vEgo=0.00  gear=park  standstill=True     IsOffroad=0
./loggerd ./encoderd 在跑；路段 --29/--30 正在写（停车也在录）
manager.py:147   ignition = any(ps.ignitionLine or ps.ignitionCan for ps in pandaStates ...)
hardwared.py:227 onroad_conditions["ignition"] = 同上
`@

- **点火线常高** → manager 用 OR 判定 → 永远认为车还开着 → **永远 onroad** → 永不 offroad
  → `MaxTimeOffroad=1800`（30 分钟）这条**永远不触发** → C3 一直不关机（耗车电、一直录）。
- **参数救不了**（MaxTimeOffroad 只在 offroad 时生效；IsOffroad 是结果不是开关）。

对策（按推荐）：① **硬件**：查点火检测线是否接在常电 → 换受点火控制的 12V（ACC）；
② **软件补丁（可选）**：`system/manager/manager.py` 与 `system/hardware/hardwared.py` 的 OR 判据改成
"只信 ignitionCan / 加驻车启发式（档位 P + 静止 N 分钟 → 视为熄火）"；改前先备份。

## 5. 与 LKAS 故障的关系

`steerFaultPermanent=True` → `car_specific.py:213` → `EventName.steerUnavailable` →「LKAS 故障：请重启车辆以启用」。
车辆通电时换系统/重启设备 → 握手中断 → 车机 EPS 锁永久故障 → 只能点火循环清（详见 ADAPTATION §4.24.1）。

## 6. 下一轮计划

1. 你：**熄火一次**（清 LKAS 故障）→ 我复读 `steerFaultPermanent` 确认；
2. 你：**开一段带急弯的路**（先别动参数）→ 我出基线数据（an4/an5）；
3. 我：读 `latcontrol_torque.py` / `latcontrol_torque_ext*.py` / `latcontrol_pid.py`，列"哪些参数真进控制器"的调参表；
4. 我：`BydUseNonLinearTorque` A/B 对比报告；
5. 我：offroad 补丁 diff（manager/hardwared），先给你看再决定打不打。

## 7. 第 2 轮补充（同日，代码级根因 + 证据链补全）

### 7.1 问题① 的**代码级**根因（不是猜的）

横向闭环核心在 `selfdrive/controls/lib/latcontrol_torque.py`：

`@
desired_lateral_accel = desired_curvature * vEgo^2
low_speed_factor      = interp(vEgo, [0,10,20,30], [15,13,10,5]) ** 2
setpoint              = desired_lateral_accel + low_speed_factor * desired_curvature     ← ★
freeze_integrator     = steer_limited_by_safety or CS.steeringPressed or CS.vEgo < 5     ← 低速冻结积分
output_torque         = torque_from_lateral_accel(pid.update(setpoint - measurement, ff), torque_params)
pid_log.saturated     = abs(output_torque) 顶到 steer_max
`@

`low_speed_factor` 的取值：v=1 → ≈**219**、v=5 → ≈166、v=10 → ≈169、v=20 → 100、v=30 → 25。
也就是说**低速时把"期望曲率"乘以一两百倍再加进 setpoint** → PID 猛要横向加速度 → 扭矩映射直接打到 ±1.000。
这与我实测到的"低速 + 大转向角时 τ 饱和"完全对上 ✓ 低速下积分被冻结，全靠近似"前馈+比例"猛推，更容易冲。

BYD 口自己的调参（`opendbc_repo/opendbc/car/byd/interface.py:87-89`）：
`kp=0.7 / ki=0.2 / kf=0.85`（注释写明"从 1.0/0.3/1.0 降下来，减少 30% 响应强度/积分/前馈"）→ 作者已察觉过猛。
同文件还留着他的调参笔记，其中一句：**"Add the steering angle speed (angle slew rate) to stop the control loop from turning wheel too sharp"**
≈"轮子转太猛"正是你反馈的现象 ✓

非线性力矩整形：`BydUseNonLinearTorque=1`，实现在 **BYD 车端编译产物** `opendbc/car/byd/carcontroller.so` 里，
系数来自 `BydNonLinearTorqueParams_a/b/c` —— **当前参数库里这三个不存在**（用默认系数）。

**三个可操作旋钮（按安全性排序）**：
1. `BydUseNonLinearTorque=0` —— 纯参数、可秒回退，先做 A/B；
2. 补丁 `LOW_SPEED_Y = [15,13,10,5]` → 例如 `[8,7,6,4]` —— 直接削掉"低速猛推"（改前备份，可回退）；
3. `TorqueParamsOverrideEnabled=1` + 合理值 —— ⚠ **默认 `TorqueParamsOverrideLatAccelFactor=2.5` ≈ 学习值 1.295 的两倍**，
   直接打开会让转向**更猛**；要开就把 factor 设 ≈1.0-1.2、`friction` ≈0.12。

### 7.2 问题② 的证据链补全（含一个"幸好先验证"的发现）

||
|| 实测：`ignitionCan` **行车、停车全程 False**（6 条路段 100% 帧）→ "只信 CAN 点火"这条补丁**没用** ✗
|| 实测：`ignitionLine` **全程 True**（停车时 14.19V）→ 点火检测接在常电上（硬件问题）
|| 单 panda `uno`、`safetyModel=byd`、`rxBufferOverflow=34386`（接收溢出 3.4 万次 ← 值得单独查 CAN/USB）
|| 停车时 `carFingerprint` 为空（CAN 静默、认不出车），系统仍 onroad（因为点火线为真）
||

结论：**根治只能靠硬件**（点火检测线改到受点火开关控制的 12V）；
软件补丁只能用"驻车启发式"：**档位 P + 静止 + vEgo≈0 持续 N 分钟 → 视为熄火**（然后 `MaxTimeOffroad=1800` 才会生效）。

### 7.3 「停了也不解除」的直接原因：**MADS 开着**

`@
Mads=1   MadsUnifiedEngagementMode=1   MadsMainCruiseAllowed=1   MadsSteeringMode=0   DisengageOnAccelerator=0
驻车实测：MADS state=paused（不转向）但 enabled=True（显示仍是"开着"）
`@

SunnyPilot 的 MADS 就是"横向/纵向可独立 + 驻车不自动解除"。**想恢复"停车/踩刹车就解除"，把 `Mads` 关掉**（或改 `MadsSteeringMode`）。

### 7.4 顺带确认的两件事

- **LKAS 永久故障已清**：实测 `steerFaultPermanent=False`（现在只剩 `steerFaultTemporary=True`）→ 熄火/重启循环确实能清 ✓
- 设备近期**重启过**（uptime 34 分钟），仍在 onroad 录日志（--31/--32/--33）✓

## 8. 第 3 轮：饱和量化 + 基线固化 + 补丁就绪（同日）

### 8.1 现有 7 条行驶路段的**量化基线**（存 `SYSTEM-ANALYSIS-baseline.json`，A/B 就比这张表）

| 路段 | 帧数 | 饱和(|τ|>0.95) | 其中低速(<5m/s) | 其中大角度(>25°) | 平均|τ| | 最大角度速率 °/s | 压线 L/R |
|---|---|---|---|---|---|---|---|
| --3 | 14016 | 1494 | 1197 | **1427 (95%)** | 0.281 | 476 | 0/0 |
| --4 | 14007 | 423 | 0 | **423 (100%)** | 0.203 | 44 | 0/0 |
| --5 | 14021 | 1135 | 0 | **1108 (98%)** | 0.234 | 132 | 0/0 |
| --6 | 14001 | **3511** | 3473 | **3479 (99%)** | 0.415 | **568** | 0/0 |
| --9 | 13970 | 512 | 326 | 512 (100%) | 0.205 | 120 | 0/0 |
| --10 | 14044 | 1503 | 1453 | 1503 (100%) | 0.216 | 344 | 0/0 |
| --11 | 13994 | 746 | 746 | 719 (96%) | 0.173 | 460 | 0/0 |

**读法**：饱和几乎**全部**发生在"大转向角"（95%~100%），其中多数还叠加低速；
最大角度速率到 **568°/s**（--6）——方向盘被抡得很快。这与"急转时力矩过大"完全一致 ✓

**诚实标注**：这 7 条里 `driverAssistance.leftLaneDeparture/rightLaneDeparture` **始终 0/0** ——
也就是说**"压到旁边车道"这件事在现有数据里没有被记录到**（现有数据都是低速场地/城区段）。
要坐实它，需要一段**中高速 + 连续弯**的路（就是你日常遇到的那种），这也是第 4 轮要的输入。

### 8.2 补丁就绪（已 dry-run 验证，未动设备）

`@
tools/device/patch_lat_speed.py dry      # 只看 diff + 语法校验（不改设备）→ 已验证 ✓
tools/device/patch_lat_speed.py apply    # 备份 + 打补丁 + 校验（生效需重启 openpilot ⚠ LKAS 风险）
tools/device/patch_lat_speed.py revert   # 一键还原
`@

dry-run 实际输出（语法校验通过）：
`@
-LOW_SPEED_Y = [15, 13, 10, 5]
+LOW_SPEED_Y = [8, 7, 6, 4]   # C3 patch 2026-09-26: 低速猛推减半（原 [15,13,10,5]）
`@

### 8.3 基线/对比工具

`@
tools/device/lat_report.py       # 逐路段出 JSON：饱和帧数/低速饱和/大角度饱和/平均|τ|/最大角度速率/压线
tools/device/sat.py              # 饱和时刻明细（v, 角度, 角度速率）+ 压线联动
tools/device/ign.py              # 点火线 vs CAN 点火（已经证伪 ignitionCan 方案）
`@

### 8.4 第 4 轮要做的（等一段带弯的路）

1. 你开一段**中高速连续弯**（不动参数）→ 我跑 `lat_report.py` 存 **基线B**；
2. 把 `BydUseNonLinearTorque` 置 0 → 再开同一段 → 存 **对比C**；出 A/B 表；
3. 若低速猛推仍明显 → 打 `LOW_SPEED_Y` 补丁（上面那个脚本），再开一段 → 存 **对比D**；
4. 结论落表：哪种组合能把"饱和帧数/最大角度速率"压下来而不影响车道居中。

## 9. 第 4 轮：控制器核实 + 两个假设的**排除**（同日）

### 9.1 核实：行车时用的确实是**扭矩控制器**，车认出来了

`@
路段 --6 / --3：controlsState.lateralControlState = torqueState（600/600 帧）
CarParams: carFingerprint = BYD_SONG_PRO_DMI_24 · brand = byd · lateralTuning = torque
生效增益: kp=1.0  ki=0.3  kf=1.0  friction=0.15  latAccelFactor=1.0  deadzone=0.1
`@

→ 前面基于 `latcontrol_torque.py` 的分析（低速项 + torque_from_lateral_accel）**成立** ✓

### 9.2 ⚠ 一处必须更正：**.so 盖住了 .py**

`@
$ python3 -c "import opendbc.car.byd.interface as m; print(m.__file__)"
/data/openpilot/opendbc/car/byd/interface.so        ← 实际导入的是**编译产物**
`@

所以 `interface.py:87-89` 里那句"kp 0.7 / ki 0.2 / kf 0.85（减少 30% 响应强度）"——**没有生效**；
真正生效的是 .so 里的 **kp=1.0 / ki=0.3 / kf=1.0**（上面 CarParams 实测）。也就是说：
- 这辆车的横向响应**比作者在 .py 里想要的更猛**；
- 想调它，**改 .py 没用**（被 .so 遮蔽）→ 只能走**参数**（Override / 非线性力矩开关 / LOW_SPEED_Y 补丁）；
- .so 里能看到 `torque_from_lateral_accel.linear_speed_interp` / `lateral_accel_from_torque.linear_speed_interp_inverse`
  —— BYD 的力矩映射确实是"随速度插值"的（非线性整形的入口就在这）。

### 9.3 假设①：自动变道（Auto Lane Change）——**排除**

`@
7 条路段全部：lateralPlanDEPRECATED.laneChangeState = off(120/120) · laneChangeProb 最大 0.000 · 转向灯帧 L/R = 0/0
`@
→ 日志里**从未**发生变道请求/执行（这批数据也没打过转向灯）。

### 9.4 假设②：SunnyPilot 的「Lane Turn Desire」（打灯自动拐进旁边车道）——**当前是关着的**

`@
LaneTurnDesire        参数不存在 → params.get_bool() = False → 功能未启用
LaneTurnValue         19.0   （=19 mph ≈ 8.5 m/s；若启用，低于此速打灯就会自动拐进该车道）
相关: AutoLaneChangeBsmDelay=1 · AutoLaneChangeTimer=2 · BlinkerMinLateralControlSpeed=20 · BlinkerPauseLateralControl=0
`@
代码（`sunnypilot/selfdrive/controls/lib/lane_turn_desire.py`）：打灯 + 该侧无盲区 + v < LaneTurnValue → 生成 TurnDirection；
`desire_helper.py:130` 会据此把 `desire` 设成 TURN_DESIRE（=车自己拐）。
**提醒**：这个开关如果哪天被打开（LaneTurnDesire=1），在城区低速打灯时车会自己拐进邻道 —— 与你反馈的现象一模一样。
建议保持关闭；要用也要知道 LaneTurnValue 是"最高多少速度下才允许"。

### 9.5 所以"压到旁边车道"的**最可能机制**（基于现有数据）

现有数据里没有变道请求、没有压线标志位，但有一条稳定可复现的事实：
**大转向角时扭矩 95~100% 打到满量程（±1.000），且低速段占多数**。
当**驾驶员自己**在路口/掉头处快速打方向盘时，控制器会把"角度误差"当成需求，
在**同方向再叠加最大扭矩** → 车比预期多转 → 视觉上就是"冲到旁边车道去了" ✓
这与"低速项把期望曲率放大 ~100-220 倍"的代码根因一致（§7.1）。

### 9.6 下轮（第 5 轮）要做

1. **你开一段中高速连续弯 + 城区打灯变道**（真实场景），我存基线 B；
2. 我出 **offroad 驻车启发式补丁**（hardwared.py 加 carState + "档位P+静止N分钟→视为熄火"），dry-run 验证后给你审；
3. 参数 A/B：`BydUseNonLinearTorque=0` 与（若需要）`LOW_SPEED_Y` 补丁对比；
4. 最后落一张"调参/补丁 → 饱和帧数/角度速率 变化"的结论表。

## 10. 第 5 轮：下线兜底**补丁就绪**（dry-run 验证，未动设备）

### 10.1 为什么不能用 ignitionCan（复述结论）

`@
实测 6 条路段：ignitionCan 行车/停车**全程 False** → 换 CAN 判据会让系统误以为"车已熄火"（行驶中也判熄火）✗
实测 ignitionLine 全程 True（停车 14.19V）→ 点火检测接在常电上（硬件问题）
`@

### 10.2 折中方案：**驻车启发式**（默认关闭，可回退）

补丁内容（`tools/device/patch_offroad_parked.py`，改 `system/hardware/hardwared.py` 三处）：

`@
1) SubMaster 增加 "carState"
2) 增加 _c3_parked_since = None
3) 点火判定改为：
   _ign_raw = any(ignitionLine or ignitionCan ...)
   _c3_min  = OffroadParkedMin（新参数，缺省 0 = 不启用）
   若 _c3_min>0 且 点火线为真 且 档位=P 且 |vEgo|<0.1 持续 > _c3_min 分钟 → 视为熄火（ign_raw=False）
`@

dry-run 实测：diff 正常、`py_compile` 通过、**设备文件未被改动**（grep "C3 patch" = 0）✓

用法（设备上）：
`@
/usr/local/venv/bin/python3 .dsh/patch_offroad_parked.py dry | apply | revert
/usr/local/venv/bin/python3 .dsh/patch_offroad_parked.py setmin 10    # 驻车 10 分钟视为熄火（0=关闭）
`@

> ⚠️ 两点必须说清：
> 1. 这是**兜底**，不是根治 —— 根治是硬件（点火检测改到受点火开关控制的 12V）；
> 2. 打补丁后要**重启 openpilot** 才生效，而车辆通电时重启会锁 LKAS 故障 → **熄火后再打**；
> 3. 生效后 offroad → `MaxTimeOffroad=1800`（30 分钟）才会走到"关机/熄屏"那一步（否则只是停止录日志）。

### 10.3 问题②的两条路（用户按现象二选一或都做）

|| 现象 || 病因（实测） || 处理 ||
|| 设备一直不 go offroad（一直录日志、不省电）|| 点火线常高（ignitionCan 恒 False）|| ① 硬件优先；② 上 `OffroadParkedMin` 补丁 ||
|| 停车后辅助驾驶不"解除/下线" || `Mads=1`（SP 的 MADS：横向/纵向独立、驻车不自动解除）|| 参数 `Mads=0`（或在 SP 设置里改 MADS 模式）||

### 10.4 待办（下一轮）

1. 你开一段中高速连续弯 + 打灯变道 → 基线 B；
2. `BydUseNonLinearTorque=0` A/B；
3. 视情况打 `LOW_SPEED_Y` / `OffroadParkedMin` 补丁（都要你点头）；
4. 最后出结论表 + 把这套调试流程固化进 APP（运维页一键跑分析/对比）。

## 11. 第 6 轮：闭环判定**定稿** + 两个"看不见的坑"排查（同日）

### 11.1 闭环：**是闭环，而且已经收敛**（代码 + 实时双重证据）

`@
torqued.py:37   ALLOWED_CARS = ['toyota','hyundai','rivian','honda','byd']      ← byd 在白名单里 ✓
torqued.py:79   use_params = CP.brand in ALLOWED_CARS and lateralTuning=='torque' → 本车 = True
实时           liveTorqueParameters.useParams = True ✓
controlsd:101   if sm.all_checks(['liveTorqueParameters']) and torque_params.useParams:
controlsd:102       self.LaC.update_live_torque_params(latAccelFactorFiltered, latAccelOffsetFiltered, friction)
                → 学到的值**确实被推给横向控制器** ✓
`@

**学习曲线（逐路段末值）——已经不再变了**：

|| 路段 || latAccelFactor || friction || steerRatio || stiffness || 有效点数 ||
|| --3 || 1.2952 || 0.1397 || 18.914 || 0.999 || 8636 ||
|| --6 || 1.2958 || 0.1397 || 18.880 || 0.994 || 8636 ||
|| --11 || 1.2967 || 0.1396 || 18.735 || 1.001 || 8636 ||
|| --38 || 1.2991 || 0.1394 || 18.735 || 1.001 || 8636 ||

- `totalBucketPoints` 从 --3 到 --38 **一直是 8636**（没再涨），latAccelFactor 8 条路段只动了 0.3%（1.2952→1.2991），
  friction 只在第 4 位小数动 → **学习已收敛**（不是"还在自适应"）；
- `stiffness≈1.0、angleOffset=0.000` 说明这台车的角度/刚度模型没被辨识（扭矩控制下正常）。

> **对"外部参数有没有用"的最终答案**：
> 1. **在有生效路径的参数里**，真正决定手感的是**学习值**（latAccelFactor≈1.296 / friction≈0.1396 / steerRatio≈18.7）——
>    它们**会**覆盖 CarParams 里的静态值（1.0 / 0.15）✓
> 2. 想让手感脱离"学习值"，只有 `TorqueParamsOverrideEnabled=1` 这条路（override 优先于学习值）；
>    ⚠ 但默认 `TorqueParamsOverrideLatAccelFactor=2.5` ≈ 学习值的 **2 倍** → 直接开会更猛（见 §7.1）
> 3. 与"力矩过大"直接相关的**非学习**开关仍然只有两个：`BydUseNonLinearTorque`（BYD 专属整形）与 `LOW_SPEED_Y` 补丁。

### 11.2 两个"看不见的坑"排查结果

|| 项 || 结果 || 结论 ||
|| `rxBufferOverflow=34386` || 10 秒增量 **+0** || **不是持续故障**，是历史累计（某次启动/CAN 风暴留下的）；先降级观察 ||
|| CAN 负载（--6 行驶段）|| 总线 0/130 各约 2 帧/秒（qlog 只记了子集，rlog 更全）|| 日志里看不出过载；如需精确得看 rlog ||
|| `canReceiveErrorCount` || 该构建字段返回 -1（不可用）|| 用 `rxBufferOverflow` 增量代替监控 ||

## 12. 第 7 轮：低速项贡献**量化**（补丁效果的预测，仍待实车验证）

方法：用真实 qlog 逐帧取 `carState.vEgo` / `controlsState.desiredCurvature` / `carControl.actuators.torque`，
只看"扭矩饱和帧"（|τ|>0.95），算三个量（都取中位数）：
- 低速项（现状）= `interp(v,[0,10,20,30],[15,13,10,5])² · desiredCurvature`
- 低速项（补丁后）= 同式但 `[8,7,6,4]`
- 基座项 = `v² · desiredCurvature`

| 路段 | 低速项/基座（现状） | 补丁后 | 削减 |
|---|---|---|---|
| --6 | **70.9 倍** | 20.2 倍 | −71% |
| --3 | 10.8 倍 | 3.1 倍 | −71% |
| --9 | 8.6 倍 | 2.5 倍 | −71% |

**读法**：在扭矩打满的那些瞬间，**setpoint 里占绝对主导的是低速项**（是物理需求项的 8~70 倍）；
把它按 `[15,13,10,5]→[8,7,6,4]` 改（平方后 225→64）**直接砍掉 72%** ——
这就是"低速急转时被抡"的定量解释，也是补丁效果的预测 ✓

> 免责：这是**需求侧**的量化（setpoint），不是完整闭环复现（PID 增益/限幅/车端非线性整形没参与）；
> 真正结论仍要等你开一段路做 A/B。但方向明确：**低速项是"低速大角度饱和"的第一主因**。

### 12.1 到这一轮的结论汇总（目标里的四个问题）

|| 目标问题 || 结论 || 证据/产物 ||
|| 运行逻辑 || modeld→controlsd（横向 torque 控制器 + sunnypilot 扩展）→card(.so)→panda→EPS；MADS 叠加在横向之上 || §1、§9.1 ||
|| 怎么调试 || 14 个设备脚本 + APP 侧数据；qlog 逐帧 + 实时信号 + 参数库；工具在 `tools/device/` || §0、§8.3 ||
|| 是不是闭环 || **是**：useParams=True，学到的 latAccelFactor/friction 覆盖静态值并推给控制器；且**已收敛** || §11.1 ||
|| 外部参数有没有用 || 三层：学习值（生效，会覆盖）／Override（能覆盖学习值，⚠默认值 2.5 过猛）／死的（Override 关闭时的三个值、CustomTorqueParams） || §2、§11.1 ||
|| ① 急转力矩过大 || 低速项主导 setpoint（8~70 倍）+ 大角度 95~100% 饱和；BYD 非线性整形加重 || §7.1、§8.1、§12 ||
|| ① 压到旁边车道 || 现有数据无变道请求/无压线标志；机制推断=驾驶员急打时同向叠加满扭矩 → 过冲；**待中高速弯数据验证** || §9.3、§9.5 ||
|| ② 不能下线（设备） || 点火线常高（ignitionCan 恒 False）→ 永远 onroad；参数无解，需硬件或驻车启发式补丁（已就绪） || §7.2、§10 ||
|| ② 不能下线（辅助） || MADS=1（横纵向独立、驻车不自动解除）→ 参数 `Mads=0` || §7.3、§10.3 ||

## 13. 第 8 轮：把诊断流程做进 APP（一键「横向诊断」）3.00.66

### 13.1 做了什么

运维页「后台任务」那一行旁边多了一个 **「横向诊断」** 按钮，点一下：
`@
1) 从 APP 自己的资源里取脚本  fetch('./remote/lat_report.py')
2) 推到设备上            POST /api/ssh/write {path:/data/openpilot/.dsh/lat_report.py, b64}
3) 丢后台跑              POST /api/jobs/start  command = cd /data/openpilot && python3 .dsh/lat_report.py
4) 输出流进下面的任务面板   followJob() → /api/jobs/stream
`@
脚本也升级了：**不带参数时自动分析最新 10 段**（原来写死路段号）✓

### 13.2 验证（对**发布包**做的，不是看源码）

解密 `releases/c3shell-3.00.66.apk` 里的资产后核对：
`@
page.html  266,390 字节 | 按钮 id="jobLatDiag" ✓ | 处理逻辑标记 ✓ | ./remote/lat_report.py 引用 ✓
assets/remote/lat_report.py.enc → 解密 1,999 字节 ✓ | 含"自动取最新 10 段" ✓
`@

### 13.3 一个环境怪现象（与功能无关，记录下来）

平板的 c3shell 正在服务自己的 WebView（logcat 里 `C3ShellWeb: GET /api/voice/next` 每 1.5 秒一次 ✓），
adb 视角 `/proc/net/tcp` 也能看到 **3081 LISTEN** ✓，
但**从本机 DSH 这个壳去连 127.0.0.1:3081 / [::1]:3081 都被拒**（今天上午还连得通）。
→ 说明是本机"跨应用 loopback 可达性"的问题（SELinux/绑定变化），**不是按钮的问题**；
下一轮改在**车机**上点一次做真人验证（车机 shell 有 curl ✓，可走 adb 直接调它的 API）。

### 13.4 这一轮的净产出

- APP 侧：一键横向诊断（3.00.66，已装平板；车机待装）
- 设备侧：无改动
- 文档：本节 + 目标四问结论表（§12.1）

## 14. 第 9 轮：一键诊断**改走 exec**（发现内置版没实现 /jobs）+ 实机验证

### 14.1 抓到一个真 bug（我自己集成时踩的）

在车机上按 API 契约实测：
`@
GET  /remote/lat_report.py            → 2095 字节 ✓（资源可取）
POST /api/ssh/write {path,b64}        → {"ok":true,"size":2095} ✓（脚本已推到设备）
POST /api/ssh/jobs/start              → {"ok":false,"error":{"code":"embedded-todo",
                                         "message":"APP 内置版还没实现该接口：/api/ssh/jobs/start"}} ✗
`@
**内置版 APP（平板/车机自带的那个服务器）根本没有实现 /jobs/**，所以"后台任务"那套（以及我第一版按钮）
在车机上必然失败 ✗ → 改成**同步走 /api/ssh/exec**（这个内置版实现了 ✓）：

实测（车机，同一台设备）：
`@
POST /api/ssh/exec {"command":"cd /data/openpilot && /usr/local/venv/bin/python3 .dsh/lat_report.py"}
→ 3.8 秒返回完整 JSON（最新 10 段）✓
`@

### 14.2 改完 + 实机核对

- 按钮逻辑：取脚本 → `/api/ssh/write` 推送 → `/api/ssh/exec` 同步跑（最多 180 秒）→
  把 JSON **渲染成每段一行**（饱和 / 低速饱和 / 大角度 / 平均|τ| / 最大角度速率 / 压线）写进输出面板 ✓
- 3.00.67 已装 **平板 + 车机**；
- 在**车机**上直接拉它自己的页面核对：`grep -c jobLatDiag` = **2**（按钮+处理器）、含新标记 ✓

> 顺带发现（不是本次引入）：运维页那个「运行」按钮用的也是 `/jobs/start` →
> **内置版里同样是 embedded-todo**（那套"后台任务"只在 DSH 连接器模式下可用）。要不要改成 exec 版，你说一声。

### 14.3 ② 的一个新证据：驻车也在疯狂录

`@
/data/media/0/realdata  已 2.1 GB · 46 个路段目录（最新的都是停车段，sat=0）
设备 up 46 分钟，load 5.2
`@
= 点火线常高导致"永远 onroad"的**直接代价**（磁盘 + 车电池）。补丁已就绪（§10），等你点头。

## 15. 第 10 轮：运维页「运行」也改 exec + 车机界面确认

- 3.00.68 已装 **平板 + 车机**；
- 运维页「后台任务」那行的两个按钮现在都在内置版可用：
  `[后台命令…] [横向诊断] [运行] [抓诊断日志]` ✓（车机实拍 `_attic/v-hu-job.png`）；
  「运行」原来走 `/jobs/start`（内置版 embedded-todo）→ 已改成 **`/api/ssh/exec`** 同步执行、输出进面板 ✓
- 静态核对：`api('/jobs/start'` 已 **0** 处；50 段脚本全部语法通过 ✓

**诚实标注**：点按钮后"渲染进输出面板"这一步我**没能在车机上肉眼确认** ——
我的 adb 点击只让按钮获得焦点、切「输出」标签的点击也没生效（坐标/焦点问题）；
但**机制本身在握手层已验证**：`/api/ssh/exec` 跑诊断 3.8 秒返回完整 JSON ✓（§14.1），
按钮逻辑与页面脚本语法也都检查过 ✓。下次你在车机上点一下就能看到表格，若不出内容告我一声我改用别的渲染位置。

## 16. 目标完成度自查（第 10 轮末）

|| 目标要求 || 状态 || 证据 ||
|| 运行逻辑 || ✅ || §1、§9.1（torque 控制器 + MADS 叠加 + card .so + panda） ||
|| 怎么去调试 || ✅ 且已产品化 || §0 工具表、§13/§14/§15 一键诊断（平板+车机） ||
|| 是不是闭环 || ✅ 定稿 || §11.1（useParams=True + 学习收敛） ||
|| 外部参数有用吗 || ✅ 三层结论 || §2、§11.1 ||
|| ① 证据与成因 || ✅ || §7.1 代码根因 + §8.1 饱和量化（95~100% 在大角度）+ §12 低速项占 8~70 倍 ||
|| ① 修复建议 || ✅ 三个旋钮 + 补丁 dry-run 就绪 || §7.1、§10.2 ||
|| ① 实车验证 || ⏳ **真车基线已就位**（§18：8 段 / 105 段扫描），待 A/B：BydUseNonLinearTorque=0 vs LOW_SPEED_Y 补丁 || §18 ||
|| ② 证据与成因 || ✅ || §7.2（点火线常高/ignitionCan 恒 False）+ §14.3（2.1GB 驻车日志） ||
|| ② 修复建议 || ✅ 硬件优先 + 补丁 dry-run 就绪 + MADs 参数 || §10 ||
|| ② 设备上验证 || ⏳ 补丁需你点头（且要熄火后打，避免 LKAS）|| — ||

## 17. 第 11 轮：一键诊断支持「与基线对比」（3.00.69）+ 操作手册成册

- 新增 `c3shell/BYD-TUNING-RUNBOOK.md`（115 行 / 8 节）：**照着敲就能做完基线 → 三个旋钮 → A/B → 回滚 → FAQ**；
  手册引用的 6 个设备脚本已逐个核对在设备上存在 ✓
- 一键诊断升级：**第一次跑自动存基线，之后每次跑显示 Δ**（`localStorage.c3latbase`）：
`@
横向诊断结果（饱和=扭矩打到 ±0.95 以上；低速<5m/s；大角度>25°）:
与上次基线对比：
  --6  sat 3511 → 2400  (Δ-1111)   角速率 568 → 410
  --3  sat 1494 → 900   (Δ-594)    角速率 476 → 380
（首次运行：已存为基线，下次点按钮就能看变化）
`@
- 3.00.69 已装 **平板 + 车机**；车机侧核对：`versionName=3.00.69` ✓、服务出来的页面含 `c3latbase`（基线对比逻辑）✓、
  `/api/ssh/exec` 跑诊断仍正常返回 ✓
- 数据面：设备已有 **51** 个路段目录，**仍全是停车段**（sat=0）→ 实车 A/B 仍待用户那段路。
## 18. 第 12 轮：实车数据落地（横向真实数据确认 + OffroadMode 已复位）

- 用户「下午跑了一段很长时间」→ 设备实际记录窗口 **11:01–12:51 设备UTC（= 19:01–20:51 CST）**：
  跨 dongle 前缀扫描到 **105 个行驶段**，最高车速 **21.8 m/s ≈ 78 km/h**（`c3shell/tools/device/find_drives.py` + `deep.py`）。
- **诚实结论**：13:33–20:50 CST 这段**没有日志** —— 是我 13:33 为解开「始终离线」开关死锁把 `OffroadMode` 置 1，导致全程 offroad。
  现已改回：实测 `OffroadMode=0 / IsOffroad=0` ✓，下次开车会正常记录（§14.4 的死锁也顺带验证了）。
- **真车基线**（替代 §12 的模拟量化基准）：`c3shell/SYSTEM-ANALYSIS-baseline-real.json`，共 8 段（每段 ≈13.9k 帧）：

| 段（--末位） | vmax m/s | sat | 低速饱和 | 大角度饱和 | 饱和中位车速 | mean\|τ\| | 最大角速率 | 压线 |
|---|---|---|---|---|---|---|---|---|
| 431 | 0.24 | 628 | 204 | 204 | 12.48 | 0.243 | 240 | 0/0 |
| 429 | 0.00 | 0 | 0 | 0 | — | 0.011 | 36 | 0/0 |
| 428 | 7.24 | 635 | 635 | 635 | 2.22 | 0.214 | 304 | 0/0 |
| 425 | 0.00 | **1374** | 523 | **1023** | 5.59 | 0.239 | 236 | 0/0 |
| 423 | 0.00 | 0 | 0 | 0 | — | 0.042 | 28 | 0/0 |
| 422 | **14.09** | 443 | 0 | 0 | 13.05 | 0.228 | **80** | 0/0 |
| 421 | 2.69 | 75 | 75 | 75 | 1.26 | 0.101 | 152 | 0/0 |
| 420 | 9.49 | 723 | 0 | 26 | 10.07 | 0.270 | 168 | 0/0 |

- 读法（对标 §12 的低速项预测）：饱和集中在两类 —— **低速**（`--428` 全 635 帧低速饱和、`--425` 有 1023 帧大角度饱和）
  与 **10–13 m/s**（`--420/422/431` 饱和中位 10.1 / 13.1 / 12.5 m/s）。
- `--422` 是最干净的一段：vmax 14.09、大角度饱和 0、最大角速率仅 80°/s。**8 段压线均为 0/0** → 这批数据里没有出现「转到旁边车道」的压线事件，
  说明该工况尚未命中（或不在被采样段内）；`--425` 的 1374 帧饱和是最该复现的一段。
- **下次开车的 A/B（一条命令）**：
  `adb shell "echo -n 0 > /data/params/d_sp/BydUseNonLinearTorque"` → 原路由再开一遍 → APP「横向诊断」
  （第一次跑自动存基线，之后每次显示 Δ；基线已就位，直接看 Δ 即可）。回滚：`echo -n 1 > /data/params/d_sp/BydUseNonLinearTorque`。

## 19. 第 13 轮：2026-09-27 上午实车（46 段）+「转弯压线」实测 + 抓到真根因（学习值被 ±0.5 夹住）

### 19.1 数据
- 目录 `00000012--c7c89304f5--0…45`（**又一次新 dongle 前缀**），02:12–02:53 设备UTC = **10:12–10:53 CST**，共 46 段，行驶段 4–40。
- 最高 **21.0 m/s（75.6 km/h）**；结构：起步/低速 4–7 → 巡航 8–31（13–21 m/s）→ 紧弯低速 32–40（曲率最大 **0.17 m⁻¹**，≈6 m 半径）→ 驻车 41–45。
- 落盘：`SYSTEM-ANALYSIS-drive-20260927-sat.json`（46 段，含 latActive 分档）、`-lane-hw.json`（8 段高速）、`-lane-curve.json`（11 段弯道）；脚本 `tools/device/sat3.py`、`tools/device/lane2.py`（读 rlog，因为 **qlog 里没有 modelV2**）。

### 19.2 力矩饱和：**全部发生在 OP 在控时**（`sat_lat == sat` 逐段成立，每段 600 帧 carControl）

| 段 | 中位车速 m/s | mean\|τ\| | 饱和帧 | 低速(<5) | 大角度(>25°) | 归因 |
|---|---|---|---|---|---|---|
| 4 | 2.3 | 0.617 | 50/145 | 50 | 48 | 起步/低速项 |
| 37 | 3.6 | 0.325 | 95/600 | 95 | 95 | 低速紧弯 |
| 38 | 2.3 | 0.406 | 60/600 | 60 | 60 | 低速紧弯 |
| 39 | 2.3 | **0.571** | 96/600 | 96 | 93 | 低速紧弯（最重）|
| 40 | 1.5 | **0.661** | 78/600 | 78 | 78 | 低速紧弯（最重）|
| 7 | 10.0 | 0.230 | 55/600 | 0 | 49 | 中速大角度 |
| 14 | 19.3 | 0.272 | 71/600 | 0 | 21 | 高速弯 |
| 32 | 12.8 | 0.264 | 58/600 | 28 | **58（全部）** | 中速弯 + 积分顶死 |
| 35 | 5.8 | 0.261 | 54/600 | 50 | 54 | 低速弯 |
| 13/15/16/18–21/24/27–31 | 13–18 | 0.06–0.18 | **0** | 0 | 0 | 巡航/缓弯：完全正常 |

→ 结论没变（和 §12 的预测一致）：**问题只在「弯 + 低速」**；直路与缓弯零饱和。

### 19.3 「转弯压线」实测（modelV2 车道线，rlog 20 Hz）
- 判据：`dev = 车道中心偏移 / 半车道宽`（+ = 车偏左，− = 车偏右；`|dev| = 1` ⇒ 车轮压线）；仅取 `laneLineProbs[1],[2] > 0.5` 且车道宽 1.2–6.5 m 的帧。
- **19 段、1.3 万+ 有效帧里，真正压线 `|dev| ≥ 1.0` = 0 次**；`|dev| ≥ 0.85` 只有 1 帧（段 25 的 0.868）。
- 但**弯道 100% 向外侧偏**（wide/tight 计数）：段 7 `35/0`、14 `146/0`、22 `763/0`、25 `170/0`、30 `456/0`、32 `74/0`（段 23 `78/4`、26 `65/14` 属噪声级）；直路段 mean\|dev\| 仅 0.03–0.10。
- 幅度：段 14（19.8 m/s）弯中 p95 **0.75** / max **0.80**；段 22（15.9 m/s）mean **0.39** / p95 0.47 / max 0.53；段 30（15.7）p95 0.48。实测车道宽 ≈3.0 m（半宽 1.5 m）→ `dev 0.8` ≈ 离中心 1.2 m ≈ **离车道线只剩 ~0.3 m**。
  ⇒ 这就是你感觉的「快压线」，但**这次数据里还没真压过去**。
- 段 23/33/34/40 的 latActive 只有 **38%–50%** → 极紧弯（曲率 0.16–0.17）是**你自己接管**的，OP 不在控。
- ⚠ **修正旧结论**：`driverAssistance.left/rightLaneDeparture` **测不到 OP 在控时的压线** —— `selfdrive/controls/lib/ldw.py` 要求 `not CC.latActive`（只在 OP 没控时报警）+ 车速 >31 mph + 变道概率 >0.1，所以「压线 0/0」从来不是证据。本次改用 modelV2 车道线几何，判据可复算。

### 19.4 根因（这次抓到代码级）
- 实车 CarParams（rlog `carParams`）：`lateralTuning = torque`，**kp=1.0 / ki=0.3 / kf=1.0**，`latAccelFactor=1.0`，`friction=0.15`（readable `opendbc/car/byd/interface.py` 里的 0.7/0.2/0.85 仍被 `interface.so` 遮蔽，**未生效**）。
- 学习值（`liveTorqueParameters`，段 30）：`useParams=True`、`liveValid=True`、`calPerc=100%`、`totalBucketPoints=12000`（= 全部桶满 ⇒ **已收敛，不是没学好**），
  **`latAccelFactorFiltered = 1.30` 而 `latAccelFactorRaw = 2.20`**（friction 0.154/0.147，未触夹子）。
- 夹子：`selfdrive/locationd/torqued.py:98-99` → `min/max_lataccel_factor = (1 ± factor_sanity) × offline_latAccelFactor`；
  `EnforceTorqueControl` **在 `/data/params/d*` 里不存在（=0）** ⇒ `sunnypilot/selfdrive/locationd/torqued_ext.py:initialize_custom_params` 整段跳过 ⇒ `factor_sanity` 用 `torqued.py` 的 **0.5**、`offline_latAccelFactor` = 1.0 ⇒ 夹子 **`[0.5, 1.5]`**。
- ⇒ **车的数据要求 2.20，栈最多给 1.50，当前实际给 1.30（≈需求的 59%）** → 同样的期望横向加速度只输出约六成力矩 → **弯道系统性向外侧跑（wide 100/0）+ 大角度打满 + 「转急弯力矩很大却还压线」**。
- 交叉证据：段 22 完全无饱和（sat=0）却 **763/763 全外偏** ⇒ 不是「力矩太大」，而是**给少了**；段 32 的 58 帧饱和全在大角度 ⇒ 增益不足时积分器顶到极限。

### 19.5 修复阶梯（按可逆性排序；⚠ 涉及开关的第一次都要**熄火后**做）
1. **参数级（需熄火后重启一次 OP）**：`echo -n 1 > /data/params/d_sp/EnforceTorqueControl`。该开关**只在 init 读一次**；开了以后 `LiveTorqueParamsRelaxedToggle=1`（当前就是 1）把 `factor_sanity` 提到 **1.0** ⇒ 夹子变 **`[0, 2.0]`**，学习值才有机会爬到 ~2.0（缓存 `LiveTorqueParameters` 会恢复；`decay=250` 很慢，要跑一段带弯的路）。
2. **参数级 + 热生效（无需重启）**：在第 1 条之后 `TorqueParamsOverrideEnabled=1` + `TorqueParamsOverrideLatAccelFactor=1.6`（再 1.8 → 2.0 递增）+ `TorqueParamsOverrideFriction=0.15` + `TorqueParamsOverrideLatAccelOffset=0.0` + `TorqueParamsOverrideSteerActuatorDelay=0.3`。
   `sunnypilot/selfdrive/controls/lib/latcontrol_torque_ext_override.py` 每 300 帧（≈3 s）重读 ⇒ **可开着车切 0↔1 做 A/B**。⚠ 出厂默认 `LatAccelFactor=2.5` 会过冲（≈实际 2 倍），**必须显式写值**。
3. **代码级（最后手段）**：把 `torqued.py` 的 `FACTOR_SANITY` 从 0.5 提高（如 1.2）放宽夹子；需熄火重启。

### 19.6 下次开车怎么验（同一条路）
- 开 `EnforceTorqueControl=1`（熄火重启）后正常开一段**含弯**的路 → APP 点「横向诊断」看 Δ：
  期望方向：弯道（corner）段的 `dev` 变小（不再 100% 外偏）、大角度饱和帧下降、`mean|τ|` 略降；若 `dev` 反而明显变负（往内侧压）说明增益过头，退到 1.4。
- 想更快试出效果就用 §19.5 第 2 条（1.6 → 1.8），20 分钟就能看出弯道外偏是否收敛。

## 20. 第 14 轮：用户质疑「没压线是因为我自己拉回来的」→ 三路取证 + crosswatch 守望器

### 20.1 先承认：**「压线 0 次」是被截断的统计，不能当反证**
两个截断源：
1. 驾驶员每次都在压线前拉回（用户自述，数据里能看到拉回动作，但看不到「不拉会怎样」）。
2. **紧弯里 modelV2 根本没有车道线**：段 37 `rej_prob=1111/1200`、**段 38/39/40 = 1200/1200（整段丢失）**、段 33 `952`、段 35 `935`、段 32 `743`。
   ⇒ 我的 dev 判据在这些段**测不到任何东西**，而这几段恰恰就是「会冲对向车道」的那几段。之前那句「0 次压线」在紧弯上不成立。

### 20.2 驾驶员接管频率（OP 在控时的打方向 / 退控）

| 段 | 7 | 14 | 32 | 34 | 26 | 30 | 35 | 23 | 33 | 36 | 37 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 打方向次数 | **9** | 5 | 4 | 3 | 2 | 2 | 2 | 1 | 1 | 1 | 1 |

合计 **21 次 / 8 分钟弯道**（≈ 每 23 秒一次）。最清楚的「反事实」事件：
- **段 7，t=451.3 s**：v=8 m/s、κ=-0.0117、**dev=-0.404 且仍在以 0.32/s 向外漂**、τ=0.78 → 若保持该速率，**1.86 s 后 |dev|=1（压线）**；驾驶员正好在这一刻打方向。
  轨迹：dev 2 s 前 -0.083 → 1 s 前 -0.404 → 接管时 -0.404（还在往外）。

### 20.3 车道位置分布在 ~0.8 处被截断（与「每次都被拉回」一致）
在控时 max|dev|：段 14 = **0.80**、段 25 = **0.87**、段 34 = 0.79、段 26 = 0.70、段 22 = 0.53；`|dev|≥0.85` 只有 1 帧。
⚠ 但这只是「一致」，不是「证明」：段 22 **零接管**却 763/763 外偏 → OP 在中等弯会停在一个 **外偏平台**（约 0.4–0.5），不是自己回到中心。

### 20.4 不依赖车道线的第二路证据：控制器自报「期望 vs 实际横向加速度」
用 `controlsState.lateralControlState.torqueState.desiredLateralAccel / actualLateralAccel`（20 Hz，**任何工况都有**），
定义 `outward = (a_des - a_act) × sign(κ)`：`> 0` = 朝弯外少给了（偏移会继续长大）。

| 段 | 弯道在控帧 | 外偏帧 | 外偏中位 m/s² | p90 | >0.5 占比 | 外偏 max |
|---|---|---|---|---|---|---|
| 14 | 1424 | 316 | **0.439** | 0.67 | 8.6% | 0.78 |
| 32 | 2991 | 817 | 0.152 | 0.454 | 1.9% | 0.71 |
| 7 | 2065 | 846 | 0.124 | 0.366 | 2.3% | 0.675 |
| 33 | 1749 | 557 | 0.034 | 0.263 | 0.4% | 0.57 |

按 `偏移 ≈ ½·Δa·t²`：持续外偏 0.5 m/s² 两秒 ⇒ 多漂 **1.0 m**；0.75 m/s² ⇒ **1.5 m（正是一条车道线）**。段 14 有 0.4% 的帧推算 2 s 内漂 >1.5 m。
**诚实边界**：外偏帧只占弯道帧的 12%–47%（不少段内偏更大），所以这**不能**证明「不拉就一定压线」；它证明的是——弯里反复出现朝外少给 0.4–0.8 m/s² 的窗口，
叠加 §19.4 的增益封顶（有效 1.30 vs 需求 2.20），这就是你反复需要拉回的方向性来源。

### 20.5 新增工具：`device/crosswatch.py`（反事实取证，只读不干预）
- 装到设备：`/data/openpilot/.dsh/crosswatch.py`；同时记两路信号，专门抓「驾驶员拉回的那一瞬间」：
  A. 车道线几何（有线时）：dev / 左右线 y / 概率；B. 控制器误差（永远有）：a_des、a_act、outward、τ、saturated；
  外加 v、κ_des/κ_act（=yawRate/v）、latActive、驾驶员打方向、转向灯。
- 事件判定：`t_cross = (1-|dev|) / |d(dev)/dt|`；向外漂移且 `t_cross < 1.5 s`、或驾驶员接管（在控时打方向 / 退控）→ 写一条事件（含前 1.5 s 轨迹）到 `events.jsonl`。
- 输出：`crosswatch-<UTC>.csv`（20 Hz）、`.events.jsonl`（事件）、`.live.jsonl`（每 5 s 汇总，可给 APP 读）。
- 已实测：设备上一口气跑 25 s 抓到 **500 帧（20 Hz 正常）**、车道线概率低时自动不输出 dev ✓。用法见 RUNBOOK §9。
