# 设备系统适配基线（CP = 当前基线 · SP2024 / SP2025 = 待适配）

> 建立：2026-09-24（v1）· v2：SP2025 实机采集 · v3：参数模块 v2 改造并真机验证 · v4：功能可用性实测 + env_dump· 维护：换系统时更新第 5 节矩阵
> 定位：c3shell 是「手机/平板端一体机外挂」，连的是**设备上的 openpilot 系统**。同一套 APP 要伺候三个大类系统（§1）。
> 本文件只干一件事：**把 CP 系统的实测事实钉死**，并把「换成 SP 时会不一样的地方」列成清单 —— 换系统后逐格填空，就知道 APP 哪几个文件要改。
> 深度出处：`dsh-ssh-connector/NOTES-c3.md`（设备档案）· `SYSTEM-c3.md`（系统总图）· `MASTER-c3.md`（总纲）· `c3shell/PROJECT-LOG.md`（逐轮实测）。
> 原则：**事实以设备为准，不凭记忆**；本文每条尽量带来源，没来源的标「待核实」。

## 0. 怎么用这份文件

| 时机 | 动作 |
|---|---|
| 换系统**前** | 读 §3（CP 事实）与 §4（APP 适配面），认出哪些实现是 CP 专属的 |
| 换系统**后** | 在设备上跑 `sh c3shell/tools/collect_env.sh`（只读），结果填进 §5 矩阵 → 得出要改的文件清单 |
| 每轮开工 | 先看 §6 的操作次序与 §7 红线，别把能用的东西弄坏 |

## 1. 三大类系统（2026-09-24 用户确认）

| 大类 | 展开 | 当前状态 | APP 适配状态 |
|---|---|---|---|
| OP | 官方 openpilot | 没装过 | 未适配 |
| **CP** | **CarrotPilot（胡萝卜）** | CP 基线（2026-09-24 前装在设备上） | **已适配**（v1.7 起全部能力） |
| **SP** | **SunnyPilot（阳光）** | **SP2025 已装（2025.002.000）· SP2024 待装** | **适配中（§4.5 已实测）** |

判定依据（设备实测，非推断）：

- `/data/params/d/GitBranch` = `CP-BYD放飞适配版0917Dev`（NOTES-c3.md § openpilot）
- 设备 8082 跑 `selfdrive.frogpilot.fleetmanager.fleet_manager`，页面自称 **CarrotPilot Fleet Manager Dashboard**（NOTES-c3.md § 设备自带的 Web 工具）
- 血统 = **FrogPilot + Carrot 混血**；`selfdrive/carrot/*` 可读可改（同上）
- ⚠️ 反例提醒：CP 里就有 `LongitudinalPlannerSP.update … # sunnypilot DEC`（CONTROL3-c3.md）→ **SP 的代码在 CP 里被借用了，SP 的差异不能照抄 CP 的结论**
- ✅ **2026-09-24 用户确认**：CP = CarrotPilot、SP = SunnyPilot（三大类 = 官方 OP / CP / SP）；**SP2024 与 SP2025 = SunnyPilot 的两个年份版本** → 同一套 APP 要分别适配，矩阵里各占一列。
- 预判：SP 两列的差异主要在「参数体系 / cereal 字段 / UI 布局 / 自带面板」，按 §5 逐格采集即可（不用猜）。

## 2. 三层视角：别把「系统特性」和「APP 布局」混在一起

| 层 | 是什么 | 换 CP→SP 会变吗 | 本文 |
|---|---|---|---|
| ① 设备端 openpilot（C3 盒子里的系统） | 文件路径、参数表、cereal 字段、进程/服务、UI 布局、自带 Web 面板 | **会变 —— 主要工作量在这** | §3 §4.1–4.3 |
| ② APP 自身界面（宿主上的 c3shell） | 顶栏/侧栏、页签、主题、字号、显示模式 | 不随 CP/SP 变 | §4.4 |
| ③ 宿主设备（装 APP 的机器） | Android 版本、WebView 版本、屏幕、TTS | 不随 CP/SP 变，但每换一台机器都要复验 | §4.4 |

## 3. CP 系统基线档案（设备端 · 全部实测）

### 3.1 系统与运行时
| 项 | CP 实测值 |
|---|---|
| 主机名 | comma-c5f64914 |
| 地址 / 端口 | 192.168.0.66:22（平板 wlan0 = 192.168.0.109，同网段） |
| 用户 / 密钥 | comma / 神牛密钥（catalog #4）；私钥 $DSH_HOME/ssh-connector/keys/id_ed25519 |
| 系统 | Ubuntu 24.04.3 LTS，内核 4.9.103 aarch64 |
| AGNOS | 12.8（/AGNOS 存在；launch_env.sh 里 AGNOS_VERSION=12.8） |
| 启动 | comma.service → tmux new-session -s comma -d /usr/comma/comma.sh |
| openpilot 的 python | /usr/local/venv/bin/python3（有 capnp + zstandard） |
| 系统 python | /usr/bin/python3 —— **没有** capnp/zstandard，别拿它跑分析 |
| 坑 | venv 的 bin/python3 是指向系统解释器的**符号链接** → 不能靠 realpath 判断「是否已在 venv 里」 |

### 3.2 openpilot 本体（换 SP 后这一整块都会变）
| 项 | CP 实测值 |
|---|---|
| 路径 | /data/openpilot |
| 分支 | Adapted_By_FangFei（方飞适配） |
| HEAD | 0e8c64d07d4e4c8efcd2a09750f36d1f21dfcff3 · 2026-08-18 · commit 信息仅 "init" |
| remote | **无**（纯本地 fork，没有上游可拉 → 升级只能整包刷） |
| 参数里的标识 | GitBranch = CP-BYD放飞适配版0917Dev |
| 血统 | FrogPilot + Carrot 混血 |
| **可读可改** | selfdrive/carrot/*（carrot_man/carrot_serv/carrot_functions/amap_navi/config/lane/web_interface）· selfdrive/frogpilot/fleetmanager/* · selfdrive/controls/lib/*.py |
| **混淆（PyArmor 8.5.9 pro，改不了内容）** | opendbc_repo/opendbc/car/byd/*（BYD 全系）· opendbc/can/dbc.py，共 11 个 .py |
| **编译（.so，改不了）** | latcontrol_torque_untils · longitudinal_untils · curve_extension_planner · lane_corridor_reference |
| 关键含义 | **横向控制的「行为」在 .so 里 → 算法改不了，只能调参 + 调标定** |

### 3.3 参数体系（APP 参数页的全部依据）
| 项 | CP 实测值 | 为什么重要 |
|---|---|---|
| 逻辑路径 | /data/params/d —— **是符号链接** → /data/params_cp/d | tar 备份只会存下链接本身（踩过）；SP 未必叫 params_cp |
| 数量 | **282** 个 | 参数页规模 / 缓存 / 对比基线 |
| fork 自定义参数族 | AutoNavi* · AutoFork* · AutoCurve* · AutoTurnControl · AutoEngage · AlphaLongitudinalEnabled · ActiveModelName … | 官方与 SP 里都没有 → 这些行在 SP 上会消失 |
| 默认值来源 | manager.py + carrot/config.py + nav_params.json + settings.cc | 见 §4.1 |

### 3.4 cereal 字段坑（fork 与上游不同 —— 采样/诊断最容易崩在这）
| 想要 | CP 的真实字段 |
|---|---|
| 转向命令 | carControl.actuators.steeringAngleDeg（**没有** actuators.steer） |
| 路径曲率 | carControl.currentCurvature / actuators.curvature |
| 车道线概率 | modelV2.laneLineProbs（扁平数组），不是 laneLines[].probability |
| 角速度 | carState.yawRate **不存在** → liveParameters.yawRateDEPRECATED |
| 横向加速度 | 自己算：vEgo × yawRate 或 vEgo² × curvature |
| carrot 专有 | carState.carrotCruise / logCarrot / leftLatDist / leftLongDist / gearStep / regenBraking / leftBlindspot |
| 字段存在但**恒 0**，不能用 | leftLatDist / rightLatDist / plannedTorque / feedbackTorque |
| ⚠️ 测量陷阱 | 停车保持时 actuators.accel = −2.0 而车静止 aEgo ≈ 0 → 必须过滤 vEgo > 0.5 或 standstill，否则得出「98% 欠刹」假象 |

### 3.5 设备端自带的 Web 面板（换 SP 后要重新点名）
| 端口 | 进程 | 是什么 |
|---|---|---|
| 8082 | selfdrive.frogpilot.fleetmanager.fleet_manager | CarrotPilot Fleet Manager Dashboard（行程/录像/导航/路线） |
| 8888 | selfdrive.carrot.lane | Lane Detect 车道检测面板 |
| 8088 | selfdrive.carrot.carrot_man | **CP 导航参数设置**（中文界面，源码 carrot/nav_params.html） |
| 7709 / 7710 | selfdrive.carrot.carrot_man | 非 HTTP，内部通信 |

### 3.6 设备端 UI 布局（APP 的投屏/触控直接照着它做的）
| 项 | CP 实测值 |
|---|---|
| 屏幕 | **2160x1080（2:1）** |
| 渲染栈 | UI 跑在 **weston** 上；hook 里 glReadPixels 读出 1080x2160 RGBA（竖屏物理帧缓冲） |
| 触摸量程 | X 0..1080 / Y 0..2160；逻辑映射用「方向 3」：面板 (px,py) → UI 逻辑 (2160−py, px) |
| 底部状态行 | `CP-BYD… 模型:CD210` —— APP 用**首行严格匹配**判断「投屏在不在跑」（notrunning 曾被误判成 running） |
| 右上角 | CARROT PILOT 徽标 |
| 右侧 | LD / CARL / SR / SO 一串 |
| 设备内置调试图表 | selfdrive/ui/carrot.cc 的 DrawPlot 共 **9** 个（APP 诊断页是它们的网页版） |
| 诊断用的权威信号 | lateralControlState.torqueState（控制器自己的信号，不是估算） |

### 3.7 设备侧被 APP 改过的东西（换系统 / 回滚必读）
| 项 | 内容 |
|---|---|
| 注入点 | /data/openpilot/system/manager/process_config.py 的 **ui 行**（env LD_PRELOAD=…）；备份 = process_config.py.dsh-bak |
| 钩子 | /data/openpilot/.dsh/uihook.so（源码 c3shell/device/uihook.c；hook eglSwapBuffers → glReadPixels → 写 /dev/shm/ui.rgb） |
| 采集开关 | 文件 /dev/shm/ui.cast.on（存在才采；删掉即停 → 关闭后零开销） |
| 触控 | /data/openpilot/.dsh/touchd（weston 用 libinput，**只认 MT 协议 B**，单点事件被静默丢弃） |
| 推送目录 | /data/openpilot/.dsh/（脚本 + so + 日志 + pid 都在这里） |
| 参数档案 | /data/openpilot/dsh-profiles/ |
| **完整回退** | ① cp process_config.py.dsh-bak → 原文件 ② rm -f .dsh/uihook.* 与 /dev/shm/ui.cast.on ③ systemctl restart comma |

## 4. APP 端对 CP 的假设（= 换 SP 时的适配面清单）

### 4.1 参数模块 —— 依赖最深，SP 必改
文件：`c3shell/assets/remote/params_dump.py`

| 适配点 | CP 里的位置 | SP 要确认什么 |
|---|---|---|
| 注册表 | /data/openpilot/common/params_keys.h | 路径还在不在；键表与 flags 格式是否一致 |
| 当前值 | /data/params/d（→ params_cp/d） | 目录是否还叫 params_cp |
| 默认值 | system/manager/manager.py（228 条） | SP 的默认值表在哪；manager_init 是否还写默认值 |
| 中文标题/说明 | selfdrive/ui/qt/offroad/settings.cc | SP 的 settings.cc 路径（常在 sunnypilot/ 下）；正则要重写 |
| 参数分类（设备自身分类） | settings.cc 的 togglesCarrot(id) + xxxToggles->setVisible(widgetIndex==N) + addItem | **CP 专有**：SP 是 sunnypilot 的 toggles 结构 → groups() / groupOrder 必须重写 |
| carrot 默认值 | selfdrive/carrot/config.py + nav_params.json | **CP 专有，SP 没有** → 这段必然失效，要能优雅降级（不能整页报错） |
| 写回 | 直接写 /data/params/d/Key | 目录名变了要跟着改 |

**✅ 2026-09-24 已实现并在真机验证（SP2025）**：`assets/remote/params_dump.py` 重写为 v2
（CP 老版备份 `params_dump.py.bak-cp-20260924`）

| 能力 | v2 做法 | SP2025 实测结果 |
|---|---|---|
| fork 识别 | 目录探测：有 selfdrive/carrot = CP；有 sunnypilot = SP | `fork=SP` ✓ |
| 参数活库 | 候选 `$PARAMS_DIR → /data/params/d_sp → /data/params/d`，取条目最多者（不再写死） | `paramDir=/data/params/d_sp` ✓ |
| 键集合 | 优先 common/params_keys.h；**没有就问运行时 `Params().all_keys()`** | `registrySource=runtime.all_keys`，**276 键** ✓ |
| 取值 | 兼容新旧 API；**SP2025 的 `get()` 返回原生类型（int/float/bool/datetime/dict）→ 统一归一成字符串**（不归一 json.dumps 会直接崩） | 276/276 取回，其中 128 个未设置 ✓ |
| 写回 | 优先 `Params().put()`，失败才回退直接写活库文件 | `set IsMetric=1` → `{"ok":true,"applied":1,"paramDir":"/data/params/d_sp"}` ✓ |
| 中文名/分组 | CP 读 settings.cc；SP 读 `layouts/settings/*.py`（字符串 × 注册表键求交）+ `translations/main_zh-CHS.ts` 映射 | 分组 **276/276 全覆盖**；中文名 11 条 ✓ |
| 兜底分组 | 设备端没覆盖的键按命名归类（Byd* → BYD、Sunnylink* → Sunnylink、其余 → 未分类） | 未分类 219 · SunnyPilot 18 · 设备 11 · BYD 9 · 开关 9 · Sunnylink 6 · 开发者 2 · 其它 2 |
| 版本信息 | 新增 `env.openpilot`（读 build.json） | 2025.002.000 · release-c3 · sunnypilot ✓ |

⚠️ 已知不足（诚实记录，别当成已完成）
- **SP2025 设备端设置界面只覆盖约 25 个参数**（其余由 SP 的 web(8765)/内部代码设置）→ 中文名只有 11 条、
  设备原生分组只有 25 条，剩下的靠命名兜底。要更全，得再挖 SP web 端的参数来源（下一步候选）。
- v2 的 CP 分支沿用旧逻辑，**没有在真 CP 设备上回归**（设备现在是 SP）→ 回刷 CP 时需复验。
- 改动只在源码里：**要在 APP 里生效必须重新构建 APK**（脚本打包在 assets 内）。

### 4.2 实时 / 采样 / 诊断 —— 依赖 cereal 字段名与路由格式
| 文件 | 依赖的 CP 事实 |
|---|---|
| assets/remote/live_stream.py | SUBSCRIBE = carState, carControl, selfdriveState, controlsState, lateralPlan …；字段名按 fork 写死 |
| assets/remote/drive_watch.py | SubMaster(['selfdriveState','deviceState']) + enabled |
| assets/remote/scan_routes.py | LogReader + **qlog.zst（zstd，不是 bz2）** + 目录命名 <8位>--<hex>--<segment> |
| 设备端 python | VENV_CANDIDATES = /usr/local/venv/bin/python3 或 /data/openpilot/.venv/bin/python3 |

SP 要确认：① 上面这些 service/字段是否都在；② 参数 key 与 cereal 字段差异（SP 有自己的 sunnypilot 字段，且 **actuators.steeringAngleDeg 这类差异可能又不一致**）；③ 路由目录与压缩格式是否变。

### 4.3 投屏 / 触控 —— 依赖设备端进程与渲染栈（风险最高）
| 适配点 | CP 实现 | SP 要确认 |
|---|---|---|
| 注入点 | process_config.py 的 ui 行 | 进程表结构是否一样；ui 的 cmdline 是否还是 ./ui |
| 钩子 | LD_PRELOAD uihook.so，hook eglSwapBuffers | SP 的 UI 是否仍走 GPU/EGL（换渲染栈则钩子失效） |
| 开关 / 数据 | /dev/shm/ui.cast.on、/dev/shm/ui.rgb | 路径是系统级，通常可沿用 |
| 触控 | touchd + MT 协议 B | 内核/输入栈变了要复验；「方向 3」映射复验 |
| 画面比例 | 2:1（2160x1080） | 设备分辨率若不同 → 尺寸档与 letterbox 重算 |

### 4.4 APP 自身布局（与 CP/SP 无关，但每换一次宿主设备都要复验）
| 项 | 现状 |
|---|---|
| 两套布局 | **手机/平板模式**：原生顶栏（一级）+ 网页头部 + 二级页签；**车机模式**：原生顶栏整行隐藏，网页左栏放「一级含二级」 |
| 切换 | 设置 → 界面 → 显示模式（手机/平板 · 车机 · 自动）；存 displayMode + localStorage c3layout；经 ?layout= URL 参数同步（不重建界面） |
| 主题 | 默认白底黑字 + 四季主题；原生外壳/顶栏/版本号跟随 |
| 字号 | 三档 |
| 已适配过的低版本宿主 | 车机 BYD DiLink3.0 · Android 10 (SDK 29) · arm64-v8a · 1920x1080 @240dpi · WebView Chromium 74 → 现代 CSS 静默失效：flex gap / color-mix / :is() / inset / aspect-ratio / backdrop-filter / :has() |
| 车机 TTS | 只有 com.byd.autovoice.tts 且无中文语音数据 → 车机无声（三条备选路线见 ROADMAP） |
| 本机平板 | 127.0.0.1 adb；窗口 ~400–540px |

## 4.5 SP2025 实测档案（2026-09-24 · 设备现装系统）

> 采集：连接器 exec 只读 + `tools/collect_env.sh`（设备留档 `/data/tmp/dsh-env-20260924T054958Z.txt`）
> 概况：**SunnyPilot 2025.002.000**（channel `release-c3`，git_origin sunnypilot/sunnypilot，build_style release，git_commit 全 0）
> ⚠️ 采集时设备刚重启（uptime 3 分钟），SP 的活参数库还叫 `.tmp_LTuZUL`（带 .tmp_ 前缀）→ **建议重启一次再复采确认它已定稿**。

| 项 | SP2025 实测值 | 对 APP 的影响 |
|---|---|---|
| 版本 | build.json：version **2025.002.000** · channel release-c3 · build_style release | 版本显示要读 build.json（CP 读 GitBranch 参数） |
| 代码来源 | **没有 .git**（release 整包解开，文件时间 08-28） | 一切 git 取值在 SP 上必然为空 → 必须降级 |
| 系统底座 | 与 CP 相同：Ubuntu 24.04.3 · 内核 4.9.103 · **AGNOS 12.8（没重刷）** | 系统层命令可原样复用 |
| 启动链 | /data/continue.sh → **/data/niuge_launcher（牛哥 launcher）** → launch_openpilot.sh；SP 用 sunnypilot/system/hardware/c3/launch_env.sh | 厂商 launcher 在链路里，改动要绕开它 |
| **参数活库** | **/data/params/d_sp → /data/params/.tmp_LTuZUL（276 键）**；/data/params/d → d_tmp **只有 5 项**（SshEnabled/AdbEnabled/Github*） | ⚠️ **最大坑**：APP 写死的 /data/params/d 在 SP 上只有 5 项 → 参数页会空 |
| 参数 API | `Params.get(k)` **不再接受 encoding 关键字**；`all_keys()` 返回 bytes 键（276） | 取值要写兼容；键表改用运行时 API |
| 注册表 | **没有 common/params_keys.h**；键表在 params_pyx.so 里，运行时暴露 `ParamKeyFlag / ParamKeyType` | registry() 从「解析头文件」改为「问运行时」 |
| 设置界面/中文名 | **没有 selfdrive/ui/qt/offroad/settings.cc**；改成 Python：**selfdrive/ui/layouts/settings/{settings.py,toggles.py}** + selfdrive/ui/sunnypilot/qt/offroad/settings/ | meta()/groups()（正则 settings.cc）整体作废，要重写解析 toggles.py |
| fork 目录 | sunnypilot ✅ · selfdrive/ui/sunnypilot ✅ · selfdrive/carrot ❌ · selfdrive/frogpilot ❌ | fork 判定：有 sunnypilot 无 carrot = SP |
| CP 残留 | process_config.py **干净**（无 LD_PRELOAD、无 .dsh-bak）；.dsh/ 只剩 drive_watch.py + mjpeg/touchd 的 pid/log（uihook.so 随安装消失）；/dev/shm 还留着 ui.cast.on 与 dsh-drivewatch.pid | 投屏钩子要在 SP 上重新注入；先清遗留 flag |
| 参数族 | 官方键 + SP 键（Sunnylink* · Alpha* · Blinker* · CustomAcc* · MapTargetVelocities · SpeedLimitOffset* · SmartCruiseControlVision）+ **BYD 厂商键**（BydFollowStockResume · BydHandsoffFix · BydStockAccelStartSpeed · BydStockEmergencyBrakePriority · BydUseNonLinearTorque · BydUseStockAccel） | CP 的 carrot/Auto* 族不存在；BYD 族是新增的一类 |
| cereal 服务 | 新增 SP 专有：carParamsSP · carStateSP · selfdriveStateSP · longitudinalPlanSP · liveMapDataSP · modelManagerSP · bookmarkButton · backupManagerSP · trafficLightState · driverMonitoringState；**carrot\* 全消失** | 采样/诊断的字段表要按 SP 重列 |
| 关键字段 | carControl.actuators.**steeringAngleDeg** ✅ · **currentCurvature** ✅ · **yawRateDEPRECATED** ✅（car.capnp 里都在） | 与 CP 同名 → 采样脚本主体可复用 |
| BYD 车码 | opendbc_repo/opendbc/car/byd/：values.py(9.7KB) · fingerprints.py · interface.py **可读**；carstate/carcontroller/bydcan/interface/fingerprints 是 **.so 编译产物**（不是 PyArmor） | 比 CP 略好，但仍改不了行为 |
| 服务端口 | **8765 = SP 自己的 websocket_server**（sunnypilot/web/）；CP 的 8082 / 8888 / 8088 全没了 | APP 里的引导/链接要改 |
| 数据 | /data/media/0/realdata 空（0 route，176K） | 录像/重放暂时无数据可用 |
| python | venv /usr/local/venv/bin/python3 3.12.3（capnp ✅ zstd ✅）· 系统 python 3.12.3（capnp ❌） | 与 CP 同构，脚本可复用 |
| 投屏/触控 | ui 进程仍是 **./ui**（PID 53107）；**钩子未装**（LD_PRELOAD 空、maps 无 uihook）；fb_size 取不到 → 分辨率待复测 | §4.3 的注入要在 SP 上重做 |

## 4.6 SP2025 功能可用性实测（2026-09-24 · 现场）

> 「先确认是哪个版本，再给对应功能」的落地入口 = 新增 `assets/remote/env_dump.py`（只读，单行 JSON）。
> 它给 APP 的一句话结论（设备实测原样）：
> `fork=SP · SunnyPilot · 2025.002.000 · release-c3 · hasGit=false · paramDir=/data/params/d_sp(148) · 服务 94 个 /
> 缺 lateralPlan · cast.ready=false · routes=0`

| 功能 | SP2025 现状 | 原因（实测） | 处理 |
|---|---|---|---|
| 参数（注册表/值/写回） | ✅ 可用 | v2 已按运行时 API + 活库 | 已改（`params_dump.py`） |
| 辅助驾驶监听 | ✅ 可用 | `drive_watch.py` 实测 `{"init":true,"en":0,"started":0}` | 无需改 |
| 运行曲线（实时采样） | 🔶 **已修好**（原来一启动就崩） | 2025 版**去掉了 lateralPlan 服务**（只剩 `lateralPlanDEPRECATED`）→ SubMaster 直接 KeyError | 已改（`live_stream.py`：按设备 SERVICE_LIST 动态过滤订阅表） |
| 曲线**当前无数据** | ⚠️ 不是 bug | 车没上电：`ign=0 / started=0`、**carState 4 秒 0 帧**（deviceState 有帧） | 上车点火后再看 |
| 重放 / 路线分析 | ❌ 无数据 | `/data/media/0/realdata` = 0 route | 需要先录一段 |
| 投屏 | ❌ **不可用**（用户反馈已复现） | `hookSo=false · lineHasPreload=false · injectedNow=false · frameFile=false` —— 钩子随安装没了，且 process_config 的 ui 行没注入 | 待做：在 SP 上重装钩子 |
| 触控 | ❌ 不可用 | `touchd=false` | 同投屏 |
| 版本/系统识别 | ✅ **新增** | `env_dump.py` 已实测输出上面那段 | 待接进 APP（Java API + 页面） |

**投屏在 SP 上要做的三步**（结构已确认可复用：SP 的 `process_config.py` 第 130 行就是
`NativeProcess("ui", "selfdrive/ui", ["./ui"], always_run, ...)`，与 CP 同构）
1. 设备上重新编译 `uihook.so` + `touchd`（源码在 `c3shell/device/uihook.c`、`touchd.c`）并放进 `/data/openpilot/.dsh/`
2. 备份后在 ui 行加 `env LD_PRELOAD=/data/openpilot/.dsh/uihook.so`，然后重启 ui 进程让 manager 带钩子拉起
3. APP 侧投屏流程不变（`/dev/shm/ui.cast.on` 开关 + `mjpeg.py` 读 `ui.rgb` + `touchd` 注入）

## 4.7 投屏在 SP2025 上已恢复（2026-09-24 实测）

**结论：投屏已可用**（抓到的帧就是 C3 的真实界面，见 `_attic/verify-319/cast-frame.jpg`）。

### 根因（和 CP 上不一样，值得记住）

| 现象 | 真因 | 处理 |
|---|---|---|
| 钩子注入了、maps 里也有 uihook，但 `/dev/shm/ui.rgb` 一直不产出 | **SP2025 的 Qt5 是用 `eglGetProcAddress("eglSwapBuffers")` 拿 swap 指针的** → 老钩子只拦 PLT 调用，被绕过 ✗（CP 的 Qt 是直接调，所以老钩子在 CP 上好用） | 钩子 v4：同时拦 `eglSwapBuffers` / `eglSwapBuffersWithDamageKHR` / `...EXT`，并**接管 `eglGetProcAddress`** 把这三个名字指回自己 ✓ |
| 只 `kill ui` 进程，钩子不生效 | **manager 启动时就把 `process_config.py` 读进内存** → 改文件对它无感 | 必须 `sudo systemctl restart comma`（不是杀 ui）✓ |
| 重启后 APP 侧投屏起不来 | `.dsh/mjpeg.py` 随装系统没了，而 APP 从没发布过它 | `mjpeg.py` 已进 `assets/remote/`，`castJson` 启动前 `ensureRemote` 自动推 ✓ |

### 固化成工具（以后换系统/换设备直接跑）

    python3 tools/provision_cast.py verify      # 只读看状态
    python3 tools/provision_cast.py install     # 推源码 → 设备上 gcc 编译 → 备份+注入 → 重启 comma → 验证出帧
    python3 tools/provision_cast.py uninstall   # 用 .dsh-bak 还原 + 重启

本次 `verify` 输出（实测）：
```
当前状态: 钩子已注入=1  已加载=4  出帧文件=yes  采集开关=yes
资产: uihook.so=yes touchd=yes mjpeg.py=yes process_config 备份=yes
→ 投屏可用
```

### 现场要知道的三件事
- 采集开关是**文件** `/dev/shm/ui.cast.on`：在 = 采集，删掉 = 零开销（关掉后 `ui.rgb` 停止更新）
- 出帧格式：16 字节头（magic/宽/高/序号）+ RGBA；SP2025 实测 **1024x512（2:1）**，与 APP 的「适配/小/中/满宽」档位假设一致 ✓
- 钩子日志 `/dev/shm/uihook.log` 会记下 Qt 实际走的是哪个入口（换系统时先看它）

## 4.8 参数中文备注（2026-09-24 修完并实测 276/276）

**用户问**：参数设置里为什么都没有备注？

### 为什么原来没有
CP 上的备注来自设备端 `selfdrive/ui/qt/offroad/settings.cc`（作者在源码里写死了中文标题/说明）。
**SP2025 已经没有这个文件**（设置界面换成了 Python：`selfdrive/ui/layouts/settings/*.py`），
而它能覆盖的参数只有约 25 个 → 所以换到 SP 后整张表几乎没有备注。

### 怎么解决（两层来源）
1. **设备端能拿到什么就用什么**：settings.cc（CP/官方）或 layouts/settings/*.py + 中文 .ts（SP）—— 保持原逻辑，设备优先；
2. **随 APP 发布一份中文词库** `assets/remote/param-notes-zh.json`（**276 条，与设备实测键表 1:1 对齐**），
   设备端没有说明的键用它兜底。每条都带来源标签：
   - `【官方】` openpilot 原生语义（对照官方 params_keys.h 与字段含义）
   - `【SP】` SunnyPilot 功能（MADS · sunnylink · 限速辅助 · 自定义 ACC · 打灯暂停 · 绿灯提醒 …，对照官方文档/社区）
   - `【BYD】` 厂商私有（`Byd*` 共 9 条），**按名字推断并明确标注「推断」**，不装懂
   - `【内部】` 系统内部状态（Git*/Cache*/Offroad_* 等），一般不用手改
   - 动作型参数显式标危险：`DoReboot`→「重启设备(危险动作)」、`DoShutdown/DoUninstall/DoSoftReboot/BackupManager_*/ModelManager_ClearCache/LateralCalibrationCommand/ForcePowerDown/OnroadCycleRequested`

### 顺带挖出并修掉的两个真 bug（都很隐蔽）
| 现象 | 真因 | 修法 |
|---|---|---|
| 备注补上了，但经 APP 只出来 **149** 键（手工在设备上跑却是 276） | APP 是用 **系统 `python3`** 跑脚本的（`ch.setCommand("python3 " + path)`），系统 python **没有 capnp** → `Params().all_keys()` 拿不到 → 退化成「参数目录里存过的 149 个」 | 参数模块加**自我重入 venv**（`_reexec_with_venv()`，与 live_stream.py 同款）→ 不管谁调用都是 276 ✓ |
| 缓存导致「新功能看着没生效」 | APP 有 `params-cache.json`（车机 CPU 弱，缓存后秒开），但**缓存没有跟版本绑定**：升级后仍返回旧载荷（我实测被它骗了一轮：缓存里是 149 键无备注的旧数据） | 缓存加 `params-cache.ver`：版本不一致就当没缓存（首次升级后自动重读）✓ |

### 实测（走 APP 自己的接口，不是手工跑脚本）
```
升级到 3.00.25 后第一次取：cached=None → registry 276 | meta 276 | 备注 276
第二次取：cached=True ageMs=73 → registry 276 | meta 276
日志：cache written 60501B ver=3.00.25
抽查：驾驶风格/0 激进 1 标准 2 温和【官方】· MADS 总开关/模块化辅助驾驶【SP】· DoReboot/重启设备(危险动作)【官方】
```

### 还欠一步（安全）
动作型参数（DoReboot / DoShutdown / DoUninstall …）现在只是**标题上标了危险**，
参数页对它们还缺少「二次确认」——建议下一步在页面加：写入这些键前弹确认框（这是能一键把设备重启/卸载的开关）。

## 4.9 参数分层：默认只显示常用（2026-09-24）

**用户反馈**：太多无用参数了，可以隐藏。

### 做法：词库给每个键打一个 kind，页面按 kind 分层

| kind | 条数 | 默认 | 说明 |
|---|---|---|---|
| `user` | **124** | **显示** | 常用可调：开关 / 设备 / 软件 / SunnyPilot / BYD / Sunnylink / 常用可调 |
| `danger` | 11 | 显示（单独成组） | 动作型：`DoReboot / DoShutdown / DoSoftReboot / DoUninstall / DoConsole / ForcePowerDown / OnroadCycleRequested / BackupManager_* / ModelManager_ClearCache / LateralCalibrationCommand` —— 写入即执行，标题已标「(危险动作)」 |
| `internal` | **141** | **默认隐藏** | 内部状态：Git*/Cache*/Offroad_*/Live*/学习值/上传队列… 一般不用手改 |

- 页面：诊断台「参数」页工具条新增 **「只看常用」（默认勾选）** → 取消勾选就展开全部 276 项；
  实现 = `pkind()` + `renderParams` 里的过滤器 + 开关绑定（默认隐藏 internal）
- 分组重排：设备原生分组（开关 9 · 设备 1 · 软件 · 开发者 2 · SunnyPilot 16 · BYD 9 · Sunnylink 1）
  ＋ **常用可调 86** ＋ **动作型（危险）11** ＋ **内部状态（不用手改）141**（原来的「未分类 219」不再出现）

### 实测（走 APP 自己的接口 force）
```
registry 276 | meta 276
kind 分布: {user: 124, internal: 141, danger: 11}
默认可见(非内部): 135 | 默认隐藏: 141
分组分布: {常用可调: 86, 内部状态（不用手改）: 141, 动作型（危险）: 11, SunnyPilot: 16, 开关: 9, BYD: 9, 开发者: 2, 设备: 1, Sunnylink: 1}
```

### 还欠（安全）
动作型 11 项现在只是**标题标了危险 + 单独成组**，写入前仍缺**二次确认**（现在只有通用的「确定要写入吗」）。
建议下一步：对 `kind=danger` 的键，写入前弹更强的确认（红字 + 要求输入参数名）。

## 4.10 老镜像 SunnyPilot 0.9.8 档案与适配（2026-09-24 实测）

用户刷了老版本 SP，实测数据与踩坑如下。**同类设备/固件再遇到，照这份走。**

### 系统档案

| 项 | 值 |
|---|---|
| 版本 | SunnyPilot **0.9.8.0**（分支 sp098 · commit c0492e3b · 2025-06-10） |
| 底层 | **Ubuntu 20.04.6** · 内核 4.9.103+ |
| Python | **pyenv 3.11.4**（`/usr/local/pyenv/versions/3.11.4/bin/python3.11`）；系统 python3 是 3.8，且 `params_pyx.so` 报 `undefined symbol: Py_Version` → 用不了 |
| 代码布局 | **老布局**：SP 代码在 `selfdrive/sunnypilot/`（不是顶层 `sunnypilot/`）；无 `settings.cc`/`params_keys.h`/`layouts/settings`；BYD 车码是**可读 .py**（不是 .so） |
| 参数 | `/data/params/d → d_tmp`（133 个已设值）· 运行时注册表 **272 键** |
| 缺服务 | **没有 selfdriveState / lateralPlan**（老版接管状态在 `controlsState.enabled`） |
| SSH | `sshd_config: AuthorizedKeysFile /data/params/d/GithubSshKeys` —— **密钥就是这个参数文件**，刷机会丢，重新追加即可（已重装回连接器的密钥 ✓） |

### 本次做的适配（都已实测）

| # | 改动 | 文件 | 实测 |
|---|---|---|---|
| 1 | 解释器**动态解析**（运行时 manager 的 exe → pyenv → venv），不再写死 `/usr/local/venv` | 4 个远端脚本 + `Ssh.java`（CASTPY） | 系统 python3 启动 → 自动重入 pyenv，注册表 272 ✓ |
| 2 | fork 判定认三种布局（carrot / 顶层 sunnypilot / **selfdrive/sunnypilot** 或 build.json 源） | `params_dump.py` · `env_dump.py` | 徽标显示 SunnyPilot 0.9.8.0（原来会误判成官方 OP）✓ |
| 3 | 参数备注词库补**老系统 132 条**（含 `BYD*` 老命名、`EnableMads/NNFF/EnhancedScc/SpeedLimit*/AmapKey*` 等） → 词库 408 条 | `param-notes-zh.json` | 老系统 272/272 有备注 ✓ |
| 4 | `drive_watch.py` 支持老服务（无 selfdriveState 时退到 controlsState.enabled） | `drive_watch.py` | 不再 KeyError ✓ |
| 5 | 投屏钩子**重装**（`provision_cast.py install`），注入点与 SP2025 同构 | 设备侧 | `ui.rgb` 出帧 1024x512、maps 里 uihook 4 条、日志 `eglSwapBuffers`（老 Qt 直接调，走的经典路径）✓ |

### 两个坑（务必记住）

1. **触摸屏别多点**：`/usr/comma/comma.sh` 里有一条 —— 开机时 `touch_count > 4` 就判定「用户在要求恢复出厂」，直接进 `$RESET` 界面（实测日志 `launching system reset, got taps`）。
   本次就是这么进的 reset（不是重启造成的）。恢复方法：`pkill -x reset` → `comma.sh` 的循环会 `exec /data/continue.sh` → openpilot 立刻回来 ✓（不需要重刷）
2. **重启 comma 只影响 manager**，但要注意当前是不是 reset 流程 —— 先 `pgrep -af manager.py` 确认在跑 openpilot，再决定要不要重启。

### 实测汇总（走 APP 自己的接口）
```
env: fork=SP SunnyPilot（阳光） | version=0.9.8.0 | caps={params:true, live:true, replay:false, cast:true}
cast: 全部子项 true（uiProcess/lineHasPreload/hookSo/injectedNow/touchd/frameFile/ready）
params: registry 272 | values 272 | 备注 272/272 | 默认可见 231 / 隐藏 177
```


### 4.10.1 老系统投屏「服务起不来」的两个真因（2026-09-24 修完）

| 现象 | 真因 | 修法 |
|---|---|---|
| 钩子明明在出帧，APP 里投屏却没画面 | 投屏服务 `mjpeg.py` 用 `cv2(OpenCV)` 编码 JPEG，**老镜像的 pyenv 里没有 cv2**（PIL 10.2 / numpy 有）→ 服务一启动就 `ModuleNotFoundError: cv2` 死掉 ✗ | `mjpeg.py` 加 **PIL 兜底**（`to_bgr/fit_width/encode_jpg` 三个助手：有 cv2 用 cv2，没有就 numpy+PIL）✓ |
| 我在设备上刚改好的脚本，过几秒又变回旧版 | 我把「推 mjpeg.py」放在了 APP 的 `castJson()` 开头，而**页面每隔几秒轮询 `/api/cast/status`** → 每次都把它自带的旧脚本覆盖回设备 ✗（很隐蔽：改完看着生效，一转眼又坏） | 推送**只在 start 时**做（status/stop 不推）✓ |

实测（走 APP 接口）：`/api/cast/start` → `running:124857` · `src=ui` → 抓到 1200x600 JPEG，画面就是设备真实界面 **SunnyPilot 0.9.8.0_c0492e3b 中文 UI** ✓

> 帧里还看到设备端两条告警：**「NVMe 固态硬盘未被挂载」** 与 **「设备注册失败」**。
> 前者很可能就是这台设备 `realdata` 为空、没路线数据的原因（没挂载就没录像）—— 需要在设备侧处理。


### 4.10.2 投屏触控「点不动」的三个原因（2026-09-24 修完）

| 现象 | 真因 | 修法 |
|---|---|---|
| 画面能看，点上去没反应 | 投屏页的触控**默认是关的**：要先点「**启用反控**」并确认（`RUN` 默认 false）。这个状态原来**不持久化** → 换系统/重装后又回到关闭 ✗ | 按设备记住（`c3tcon:<host>`），下次自动恢复并提示「反控已恢复开启」✓ |
| 启用了反控还是点不准/没反应 | **方向**不同系统不一样：CP 实测 **3**，这套老 SP 0.9.8 实测 **2**。而方向原存在**全局 key** 里 → 换系统会把上一套的方向带过来 ✗ | 方向按设备存（`c3castdir3:<host>`），并且**不再继承全局旧值**（默认 2）✓ |
| 触控彻底没反应 | 老镜像没有 `touch.py`（被刷掉），而页面在 `/ping` 探测失败时会回退到那条老路径 ✗ | touchd 已提供 `/ping`（实测 ok）→ 永远走快路径；touchd 也已重装 ✓ |

实测（直接打设备 8091）：
```
dir3 → tap(929,1577) → 帧没变 ✗
dir2 → tap(151,583)  → 帧变了 ★ 正确（一下把关告警关掉，露出设备主页）
```

**使用者要做的**（换系统后只需一次，之后按设备记住）：
1. 投屏页点「**启用反控**」→ 确认；
2. 点一下画面，若无反应就在「方向」里换 1/2/3/4 —— 
   本机（老 SP 0.9.8）正确值是 **2**，CP 是 **3**；
3. 悬浮窗里的画面**不用**点反控开关，方向同样按设备记忆 ✓


## 4.11 文件页「改名 / 删除 / 新建文件夹」在独立版失效（2026-09-24 修完）

**用户问**：不能修改文件内的文件名称吗？

**真因**：页面文件页的这三个按钮走 `POST /fs`，而 APP 把模板里的 `__API__` 替换成了 `/api/ssh`（`Web.java:136`），
所以实际请求的是 `/api/ssh/fs`。但独立版**只实现了 `/api/ssh/ls`（列目录），没有 `/fs`** → 点「改名/删除/新建文件夹」都拿不到结果（静默失败）✗。
（连接器那份是实现了 `/fs` 的，所以浏览器版一直好使。）

**修法**：
- `Ssh.fsOpJson(op,path,to,…)`：rename=`mv -n` · remove=`rm -rf` · mkdir=`mkdir -p`（返回 `{"ok":true}` / 带原因的失败）
- `Api.java` 新增 `/api/ssh/fs` 路由（紧跟 `/api/ssh/ls` 之后）

**实测（走 APP 接口）**：
```
造文件 → ok；op=rename → {"ok":true}，列表里 _renamed_ok.txt 在、旧名没了 ✓
op=mkdir → ok；op=remove → ok（目录/文件都删掉）✓
```


## 4.12 终端「卡」的真因：原生输入条每次新建 SSH 连接（2026-09-24 修完）

**用户反馈**：这个版本的终端怎么这么卡。

### 实测（先量再改）

| 路径 | 改前 | 说明 |
|---|---|---|
| xterm 打字（页面里直接敲） | 写入 3ms · **回显 57ms** ✓ | 本来就没问题 |
| **APP 底部原生输入条** | **429ms/次** ✗ | 真凶 |
| 设备 shell 启动开销 | 0.10 秒 | 不是它的锅 |
| 投屏钩子开销 | 开关 ON/OFF 只差 0.3%（load 0.87） | 也不是它的锅（我一开始怀疑过） |

**真因**：原生输入条走 `sendToTerm()`，老实现是「**另开一条 exec 连接 → 等命令跑完 → 把回声+输出整块塞进终端**」：
每次都要重新 SSH 握手（这套老镜像约 400ms），而且**长命令完全没有流式**（top / ls -R / 编译时只能干等）✗。
之所以这么写，是因为注释说「实测 JSch shell 通道写入不生效（设备无回显）」—— 但这套镜像**其实生效**（57ms 就回显了）✓。

**修法**：`sendToTerm()` 改成**优先写 shell 的 stdin**（和 xterm 打字同一条路），
只有没有活跃会话时才退回 exec，并且**复用会话**（`reused()`，不再握手）。

### 改后实测
```
原生输入条：429ms → **2~3ms**（{"ok":true,"mode":"stdin"}）
命令输出**流式**进终端（连发 3 条，终端里都看得到）✓
```


## 4.13 回到 CP（CarrotPilot 0.9.9）· 两个关键教训（2026-09-24）

系统又换回 CP，实测档案：

| 项 | 值 |
|---|---|
| 版本 | **Carrot2-v9 (2025-09-21)** · build.json 版本 **0.9.9**（commit 47f5a171） |
| 底层 | Ubuntu 24.04.2 · 内核 4.9.103 |
| 布局 | `selfdrive/carrot` + `selfdrive/frogpilot` ✓ · **有 `common/params_keys.h` 与 `selfdrive/ui/qt/offroad/settings.cc`**（即最初适配的那套布局） |
| Python | manager 用 `/usr/bin/python3.12`，**capnp 来自 `/usr/local/venv`** |
| 参数 | 注册表 `params_keys.h` **294 键**；运行时 `all_keys()` **373 键**（carrot 额外加的键不在头文件里） |

### 教训 1：找解释器**不能只看 /proc/<pid>/exe**

`readlink -f /proc/<pid>/exe` 会**把符号链接解析掉**：`/usr/local/venv/bin/python3` → `/usr/bin/python3.12`（没有 capnp）✗
→ 后果：`cereal.services` 导入失败，`caps.live` 变 false、12 个服务全报「缺失」（看着像设备不支持，其实是选错解释器）✗
修法（5 个远端脚本统一）：① 读进程 **cmdline 的 argv[0]**（venv 路径只出现在这）② 固定位置 + pyenv；
③ **逐个试 `import capnp`**，选第一个真能用的 ✓。实测：`services total 92 · missing []` ✓

### 教训 2：Carrot 的 build.json 源**也是 sunnypilot**

所以「源里有 sunnypilot 就当 SP」会把 CP 误报成 `CP+SP` ✗。改成：目录证据优先，
只有在**没有** carrot/frogpilot 目录时才用 build.json 源当 SP 线索 ✓（现在显示 `CP · CarrotPilot（胡萝卜）`）

### 本次实际结果
```
env: fork=CP CarrotPilot（胡萝卜） · version 0.9.9 · services.missing=[] · caps={params:true, live:true, replay:false, cast:true}
cast: 全部子项 true（钩子重装并出帧 1024x512 ✓）
params: registry 294 | values 373 | 键合计 373 | **有备注 373/373（100%）**
metaSource: settings.cc + 内置词库(561) / 分层
```

> 词库现在 **561 条**，三套系统全部 0 缺失：CP 294 · SP2025 276 · 老 SP 0.9.8 272 ✓


## 4.14 换一个系统就要重新适配吗？（2026-09-24 结论 + 一键安装）

**用户问**：每个版本都要自适应，换个版本就出问题吗？

### 之前每次出问题，都是同一类原因：APP 里写死了假设

| 假设 | CP 0.9.9 | SP2025 | 老 SP 0.9.8 | 现在的做法 |
|---|---|---|---|---|
| 解释器在 `/usr/local/venv` | 部分（还靠 venv 提供 capnp） | ✓ | ✗ pyenv 3.11.4 | 探测 cmdline + **逐个验 capnp** ✓ |
| 参数表在 `params_keys.h` | ✓ 294 键 | ✗ 没有 | ✗ 没有 | 有就读，没有问运行时 `all_keys()` ✓ |
| 参数库在 `/data/params/d` | ✓ | ✗ 在 `d_sp` | ✓ | 自动选条目最多的活库 ✓ |
| 中文说明在 `settings.cc` | ✓ | ✗ 改 Python | ✗ 没有 | 设备端优先 + **561 条词库兜底**（三套系统 0 缺失）✓ |
| Qt 直接调 `eglSwapBuffers` | ✓ | ✗ 走 `eglGetProcAddress` | ✓ | 两种都拦 ✓ |
| 有 `cv2` | ✓ | ✓ | ✗ 只有 PIL | 无 cv2 用 numpy+PIL ✓ |
| 有 `selfdriveState` 服务 | ✓ | ✓ | ✗ 只有 `controlsState` | 动态挑服务 ✓ |
| 顶层 `sunnypilot/` = SP | —— | ✓ | ✗ 在 `selfdrive/sunnypilot` | 多信号判定（目录优先）✓ |

**结论**：这些现在全部是「探测 + 优雅降级」，不再是假设。缺什么就少那个功能，不会整页崩。
所以**换版本基本不再需要人肉适配**。

### 唯一剩下的：投屏钩子要「每台设备装一次」—— 现在 APP 里一键装

投屏靠改设备端 ui 进程（LD_PRELOAD 钩子），必须一次性：编译 → 改 `process_config.py` → 重启 manager。
已在三套系统验证注入点写法一致（`NativeProcess("ui", "selfdrive/ui", ["./ui"], always_run…)`），gcc 也都有 ✓。

新增（v3.00.33）：
- 设备侧 `assets/remote/cast_provision.py`（install/uninstall/verify，**幂等**）
- APP 路由 `/api/cast/provision`（自动把 `uihook.c/touchd.c/mjpeg.py` 推过去再执行）
- 投屏页：检测到没装钩子时显示 **「一键安装投屏能力」** 按钮，点了 APP 自己装（约 1 分钟，重启一次设备），装完自动刷新状态 ✓

实测（CP，已装）：
```
verify  → {"uiProcess":true,"preload":true,"loaded":true,"frames":true,"frame":"1024x512#5","ok":true}
install → 3 秒返回：["编译 rc=0", "注入: 已存在，跳过", "钩子已在运行，无需重启"]（幂等，不折腾设备）✓
```

### 未来什么情况还需要人
1. 某个 fork 把 ui 进程那行写法改了 → 脚本会**明确报「找不到 ui 行」**（不是静默失败），加个 pattern 即可；
2. 全新参数（词库没收录）→ 只显示键名，不显示备注；可用 APP 的「AI 分析」问，或补进词库；
3. 服务改名 → 动态过滤，少几条曲线，不会崩。


## 4.15 「放飞自我版」CP 实测（2026-09-24）· 一键装 + 又一个 python 陷阱

用户把原版 BYD 适配 CP 换成了**放飞自我版**。全程只用了两条命令：`snap` / `diff`，和 APP 里的「一键安装投屏能力」。

### 前后差异（快照 diff，客观数据）

| 项 | 原版 | 放飞版 |
|---|---|---|
| 注册表键数 | 294 | **364** |
| 运行时键数 | 373 | 375 |
| 有值的键 | 189 | **261** |
| 新增 | —— | **86**（`AutoFork*/AutoDoFork*/AutoCurveSpeed*H/AutoUpRoadLimit*/ContinuousLaneChange*/CurveSpeedAlgo/LowSpeedTorqueAmp*/WdCamSw*/SupportedCars_*`…） |
| 消失 | —— | 84（上一版的 SP 风格键，如 `EnableMads/HideVEgoUi/HandsOnWheelMonitoring`…） |
| 值变化 | —— | 58 |

快照与 diff 工具：`tools/cp_params_snapshot.py snap|diff`（走 APP 接口，输出新增/消失/值变化 + **新键里词库没备注的清单**）✓

### 备注：放飞版的 settings.cc 自带很好的中文说明
实测多条参数的说明比我的词库还细（例：`AutoDoForkBlinkerDist` →「L 进匝道打灯距离偏移(15m)」+ 一段解释；`CurveSpeedAlgo` →「弯道预瞄速度控制模式：0 传统 / 1 预测 / 2 智能」）。
设备端优先的规则让它们自动生效 ✓；新键里词库没收录的 84 条我补进了词库（**645 条**），最终 **375 键 375 备注（100%）** ✓

### 投屏：更新把注入冲掉了 → APP 里点一下就装回来

实测（真实场景，不是模拟）：
```
POST /api/cast/provision {"action":"install"}   耗时 66 秒
steps: ["编译 uihook.so/touchd: rc=0", "注入: OK（原文件已备份为 process_config.py.dsh-bak）", "重启 comma: 已下发"]
结果: {"uiProcess":true,"preload":true,"loaded":true} ✓
```

### 顺带修掉的第三个 python 陷阱（Java 侧）

投屏服务起来后报 `ModuleNotFoundError: No module named numpy` —— 原因和脚本里那条一样：
Java 的 `CASTPY` 也用 `readlink -f /proc/<pid>/exe` 解析解释器 → venv 符号链接被解析成系统 python（没 numpy）✗。
修法：改成**优先挑一个真能 `import numpy` 的解释器**（cmdline → venv → pyenv → python3 逐个验）✓。
> 教训：**只要哪里用 readlink -f /proc/pid/exe 找 python，那里就会踩坑** —— 脚本侧和 Java 侧各踩了一次。

### 本轮结果
```
env: fork=CP · 0.9.9 · caps={params:true, live:true, replay:false, cast:true} · services.missing=[]
cast: 全部子项 true；起服务 → running:54199 · src=ui；抓到 JPEG 59,931 字节 ✓
params: registry 364 | 键合计 375 | 有备注 375/375 | metaSource=settings.cc + 内置词库(645)
```

## 4.16 「赞赏」提醒与登记（2026-09-24 新增，客户端 3.00.40）

用户要的三件事：① 每 5 次打开「关于/赞赏」页才提示一次（原来第一次就弹，太吵）；②
提示里带「我已赞赏」按钮，自己填金额；③ 填完**联网发给作者**，并且**不要再弹下一个窗**。

### 改法
- `MainActivity.onCreate`：`SharedPreferences` 里 `appOpens` 自增，只有 `opens % 5 == 0` 才走
  `showReward()`；旧的「首次打开必弹」逻辑（`rewardShown`）删掉 ✓
- `showReward()` 第 ④ 块：金额输入框（提示语「赞赏金额（元，需 >20）」）+「我已赞赏」按钮
  - 校验：`vv > 20`，否则 Toast「请输入大于 20 的赞赏金额」并**不关窗**
  - 通过：后台线程上报 → 成功 Toast「已记下：赞赏 XX 元，谢谢！」，**关掉当前弹窗，不再出后续提示** ✓
- `Lic.appreciate(amount)`：POST `<基础地址>/appreciate`，body `{device,version,amount,contact}`，
  8s 连接 / 15s 读取超时；未填服务器地址时走统一降级提示「未配置校验服务器（软件设置 → 激活 / 授权 里填地址）」
- 服务端：`tcb-license.js`（文档型）/ `tcb-sql-license.js`（PostgreSQL）都加了 `/appreciate`，
  金额 `Number()` 后**必须 > 20** 才落库，否则 `{"ok":false,"error":{"message":"赞赏金额需大于 20"}}`；
  集合 / 表名 `app_appreciate`；`/stats` 多返回一个 `appreciateOpen`

### 实测
```
GET  /api/ssh/license {"action":"appreciate","amount":"50"}
  → {"ok":false,"error":{"message":"未配置校验服务器（软件设置 → 激活 / 授权 里填地址）"}}   ✓ 降级正确
dex 内含 appOpens / appreciate / 「我已赞赏」/「赞赏金额（元，需 >20）」/「已记下：赞赏」/「请输入大于 20」 ✓
设备号 C3-3499EFE1917B48BA（上报时自带，无需用户填）
```

> 注意：后台还没部署（地址没填）时，三个联网功能（激活 / 反馈 / 赞赏）都是同一句降级提示，
> 不算 bug。部署见 `server/DEPLOY-TCB.md`（手动）或把 `server/AGENT-PROMPT.md` 整段粘给云开发控制台的 AI 助手。
## 4.17 后端落地：用户的云开发环境是 **RDS MySQL**（2026-09-24）

原来 `server/` 里只有两套实现：文档型（`tcb-license.js`）+ PostgreSQL（`tcb-sql-license.js`）。
用户回「云数据库 RDS MySQL」→ 补第三套 MySQL 版：

- `server/tcb-mysql-license.js` ★：`mysql2` 连接池、`?` 占位符、`DATE_SUB(NOW(), INTERVAL 5 MINUTE)` / `CURDATE()`；
  `GET /` 直接出 HTML 统计页；一个环境变量都没填时给**中文提示**（不是英文堆栈）
- `server/schema-mysql.sql`：4 张表 utf8mb4（`app_license` / `app_heartbeat` / `app_feedback` / `app_appreciate`），可重复执行
- `server/tcb-package-mysql.json`：依赖只写 `mysql2`
- 连接三件事（已写进 `DEPLOY-TCB.md` 第 2 节）：① 云函数**开启私有网络**、选 MySQL 的 VPC + 子网；
  ② **环境变量手填**（`MYSQL_*` 不会自动注入，主机必须用**内网地址**）；③ RDS 白名单 / 安全组放通

### 顺手修掉的真 bug：反馈截图从来没上传成功过

APP 发的是 `imageB64 = "data:image/jpeg;base64,…"`（带 data URL 前缀），而两套老实现都在读 `body.shotB64`
（字段名不对 → 永远取不到）；就算字段名对了，`Buffer.from("data:image/jpeg;base64," + …)` 也会把
`dataimagejpegbase64` 当成 base64 解出**垃圾字节**（Node 解码会跳过 `:` `/` `;` `,`，但字母是合法 base64 字符）✗。
现在三套统一：`imageB64 || shotB64` + `replace(/^data:[^,]*,/, '')`；文档型优先传云存储，失败回退存 base64 ✓。

### 自检（不用真库）

`c3shell/tools/tcb-fn-selftest/`：假 `mysql2` 桩 + 16 项断言（路由 / 占位符语法 / 字段名 / data 前缀 / 缺配置降级）：
```
env -u MYSQL_URL -u DATABASE_URL NODE_PATH=$PWD/c3shell/tools/tcb-fn-selftest/stub \
  node c3shell/tools/tcb-fn-selftest/run.js c3shell/server/tcb-mysql-license.js
→ 16/16 通过
```
> 真连库还得在云上跑一次 `SELECT 1`：报「未配置数据库…」= 环境变量没填；报 ETIMEDOUT / ECONNREFUSED = VPC / 白名单没开。
## 4.18 第二台设备：比亚迪 DiLink 车机（2026-09-24 更新到 3.00.41）

用户原话「现在已经上车，车机又可以连接了 → 把它更新到最新版本」——这里「车机」**不是** C3 设备，
而是**车上的比亚迪 DiLink 中控大屏**（另一台 Android 机器，装的是同一个 c3shell APP）。

### 怎么找到它 / 怎么装
- 平板扫 `192.168.0.0/24` 的 `5555` 端口找到它：`adb connect 192.168.0.100:5555`
  （`adb devices -l` 报 `product:DiLink3.0 model:DiLink3_0_For_BYD_AUTO`，Android 10，1920×1080）
- `adb -s 192.168.0.100:5555 install -r releases/c3shell-3.00.41.apk` → 签名一致，直接覆盖，**不丢配置** ✓
- 启动：`am start -n com.padagent.c3shell/.MainActivity`，截图确认车机模式正常、左下角 `v3.00.41` ✓
  （截图存 `_attic/verify-headunit-3.00.41.png`）

### 和 C3 设备的对应关系（易混）
| | 平板（DSH 主机） | 车机（DiLink 大屏） | C3 设备 |
|---|---|---|---|
| 地址 | 192.168.0.109 | 192.168.0.100 | 192.168.0.66（车机上配的）/ 192.168.31.49（家里） |
| APP 内置服务端口 | **3082**（3081 被 DSH 连接器占了） | **3081**（车机上没跑 DSH 连接器） | — |
| 主机条目 | c3(192.168.31.49) + host2(192.168.0.66) | 只有一条 c3(192.168.0.66) | — |

> 车机上取 APP 状态（不用打开界面）：`adb -s 192.168.0.100:5555 shell "curl -s -H 'x-dsh-ssh-token: embedded' http://127.0.0.1:3081/api/ssh/hosts"`

### 本轮发现：C3 设备当时不在车上那个网里
- 车机上 `ip neigh` → `192.168.0.66 dev wlan0 INCOMPLETE`（ARP 都解析不到 = 设备不在这个网）
- 平板扫全 `192.168.0.0/24` 的 22/8022 等端口：只有路由器（192.168.0.1）和车机（192.168.0.100），**没有 C3**
- 所以车机页面显示「●设备已断开」是**如实反映**，不是 APP 的 bug —— 等 C3 开机 / 连上同一个 Wi-Fi 即可
## 4.19 投屏「延迟太厉害」的真根因：撞上半截帧白等 100ms（2026-09-24 修完，6.4 → 19.7 fps）

用户问「是又有通道堵塞了吗？」—— **不是通道，也不是网络**，证据：
- 平板→C3 `ping` 30 包 0 丢、RTT 平均 **13ms**；C3 在 5GHz（AP `wei_WiFi`，PHY 866.5 Mb/s）
- 平板直连拉流 **1.4 MB/s** 毫无压力；`/stat` 显示 8090 只有 **1 个客户端（车机）**，不存在抢通道

真因在设备侧 `mjpeg.py`（10 秒探针）：
```
源 ui.rgb 更新 178 帧（17.8 fps） → 实际只出 64 帧（6.4 fps）
**短读 67 次**（131 次读里一半是半截帧）→ 旧代码 time.sleep(0.1); continue
→ 67 × 100ms ≈ 6.7 秒白等，正好吃掉 2/3 的时间 ✗
```
钩子写 `/dev/shm/ui.rgb` 是「先写 16 字节头、再写 1.5MB 身体」，读侧在写的过程中读到的是**半截文件**。

### 修法（mjpeg **v5.1**）
1. **seqlock 读法**：`os.pread(fd,16,0)` 读头 → 读体 → **再读头比对**；头变了或体不完整就**立刻重读**（微秒级），不再睡 100ms ✓
2. **每个客户端只发新帧**（旧版固定 1/FPS 重发同一张 → 车机 WebView 反复解码重复帧，解码跟不上就排队 = 延迟越积越大）
3. 新帧就绪用 `threading.Condition` **立即通知**（省掉最多一个 1/FPS 的等待）
4. 客户端 socket 开 `TCP_NODELAY`；`/stat` 多给 `sent=` / `enc=` / `torn=`

### APP 侧同步改的三处
- 默认起流参数 `8090 20 1200 62` → **`8090 25 1024 58`**（源本来就是 1024 宽，放大到 1200 纯烧 CPU）
- 画质档「低/中/高」= 800×450 Q45 / **1024×600 Q58** / 1280×720 Q68；档位命令改用**真实解释器**（起流时把 `$PY` 写进 `mjpeg.pypath`）——换系统后不会再因为写死 `/usr/local/venv/bin/python3` 而切档失败
- 「开始投屏」**先 `pkill [m]jpeg.py` 再起**（原来不杀旧的 → 8090 被占 `Address already in use`，改了参数/画质不生效）

### 实测（车机 WebView 连着时）
```
修前: 6.4 fps（源 17.8）· 单帧编码 20ms · 客户端只拿到 5.1 fps
修后: 19.7 fps（贴着源）· 单帧编码 24-55ms · 客户端 17.1 fps · torn 计数在涨但每次重读只有微秒
```
> 结论：**投屏不需要更多带宽，需要别在读半截帧时傻等** —— 同理，以后凡是「读另一个进程正在写的文件」，都要按 seqlock 处理。
### 补丁：3.00.43 引入的「自己把自己杀了」坑（3.00.44 修）

为了让「开始投屏」先杀掉旧实例（原来不杀 → 8090 被占 `Address already in use`，改了参数不生效），
我在 start 命令里加了 `pkill -f "[m]jpeg.py"` —— 结果**整条命令被 Terminated，投屏服务彻底没了**。

原因：`pkill -f` 匹配的是**整条 cmdline**，而这条 start 命令自己的 cmdline 里就写着
`nohup $PY /data/openpilot/.dsh/mjpeg.py 8090 …` → `[m]jpeg` 那个「不匹配自身」的小技巧只挡住了
pkill 自己，**没挡住执行它的那个 shell**（shell 的 cmdline 里有真正的 `mjpeg.py`）✗

改法（三条一起，3 次连点实测 ps 恒为 1、0 次 traceback）：
1. 按 PID 文件杀：`P=$(cat mjpeg.pid); [ -n "$P" ] && kill $P`
2. 兜底扫 `pgrep -f 'mjpeg[.]py'` 逐个杀，但 **`[ "$p" = "$$" ] && continue` 跳过自己**
   （模式写成 `mjpeg[.]py`：字面量里没有真正的点，正则匹配不到它自己）
3. 再 `curl /stat` 轮询等端口真空出来（最多 4s）才起 —— 不再赌 `sleep 1` 够不够

> 教训升级版：**凡是「用 pkill 的模式」杀掉自己命令行里出现过的名字，都要先想清楚会不会杀掉执行者自己。**

### 补丁 2：还是「开久一点就有延迟」→ 改用**客户端拉帧**（3.00.45 ~ 3.00.51）

用户继续报「一开始没有延迟，开久一点就有延迟」。这次量到了直接证据：
```
stat:  frames=6885  sent=6765        → 积压 120 帧 ≈ 6 秒（15~20fps 时）
ss  :  192.168.0.66:8090 → 车机    Send-Q = 1,166,003 字节   ← 内核发送缓冲还堆着 1.1MB
```
即：**MJPEG 是"服务器推"** —— 车机 WebView 解码只要比 C3 产出慢一点点，每秒差几帧，
跑几分钟就是几秒延迟，而且只会越来越大 ✗（跟带宽/通道完全无关）。

### 修法：客户端**拉最新帧**（不是服务器推）
- `mjpeg.py v5.2/5.3` 新增 `GET /frame.jpg`：只回**当前这一帧**（`Cache-Control: no-store`）
- 必须加 `Access-Control-Allow-Origin: *`：页面用 `fetch().blob()` 跨源取图，**没有这个头 WebView 直接判失败**
  （踩过：表现成"拉帧失败自动退回 MJPEG"，查了半天）
- `protocol_version` 改 **HTTP/1.1**（带 Content-Length 才能复用连接；HTTP/1.0 每帧新建连接 = 每秒 15 个 TIME_WAIT ✗）
- 没人看就不采集：`clients > 0` 或最近 3 秒有人拉过 `/frame.jpg`
- 页面侧（`page.html` 投屏页 + `cast.html` 浮窗）改成 **15fps 拉帧循环**：解码慢就自动跳帧 → **延迟恒定** ✓
  - 连续失败退回 MJPEG，但**服务重启那一两秒不算**（要连续 8 秒没有成功帧才退回），且**30 秒后自动切回拉帧** ✓
  - 早期版本「失败一次就把禁用标记写进 localStorage」= 灾难：装 3.00.45/46 时设备端还没 `/frame`，
    标记被写死 → 之后永远走 MJPEG ✗ → 现在只在本次会话内退回，并在启动时清掉脏标记 ✓
- 默认参数 `8090 15 1024 58 ui`（15fps / 1024×600 / 画质 58）

### 实测（车机投屏页开着，连着看 2 分钟）
```
18:17:46  pulls=771    age=0.01  clients=0
18:18:11  pulls=1020   age=0.06  clients=0   ← 稳定 ~10~16 次/秒
18:18:37  pulls=1285   age=0.06  clients=0   ← age 不涨 = 延迟不累积 ✓
```
> 注：`运行曲线 / 实时` 打开时设备 load 能到 **11.8**（`live_stream.py --hz 10` 占掉一个核），
> 会让 C3 出帧变慢（拉帧就跳帧、看着"不够顺"），但**不会**再把延迟越堆越大 ✓
> 想更顺：关掉那两个页，或把画质切「低（800×450）」。
## 4.20 APP 加固：混淆 + 资源绑签名 + 关调试口（2026-09-24，3.00.52 / 3.00.53）

用户要求「把 APP 加密一下，避免轻易破解」。原有基础已经不错：资源本来就是流密码加密（`Sec.java` + 构建时 `_enc`）、
APK 用 PKCS12 正式密钥签名（v1+v2+v3）、`allowBackup=false`。这一轮补上四件事：

| 措施 | 做法 | 效果 |
|---|---|---|
| **代码混淆** | `d8` → **R8**（`build_apk.py` 直接调 d8.jar 里的 R8）+ `proguard-rules.pro` | 类/方法/字段名全重命名（实测 dex 里 `com.padagent.c3shell.Ssh` 出现 0 次；日志里变成 `com.padagent.c3shell.a.a(...)`），反编译读不动 |
| **资源绑签名** | 资产密钥 = 固定基串(15B) + **签名证书 DER 尾部 9 字节**（构建时 keytool 导出，运行时 `PackageManager` 取自己签名） | 二次打包 / 换签名 → 钥匙不对 → **所有 `.enc` 解不开**，页面都出不来；`Guard` 还会弹「包被改过」并退出 |
| **关调试入口** | WebView `setWebContentsDebuggingEnabled` 默认 **false**（作者要看时把偏好 `webdbg` 置 true） | chrome://inspect 拿不到解密后的页面 |
| **反调试提示** | `Guard.hazard()`：debugger / debuggable / frida / xposed / substrate（读 `/proc/self/maps`） | 只 Toast 提示，不误伤正常使用 |

### 踩过的坑（下次别再踩）
- R8 需要 **java.\* 的库类**，而我们这份 `android.jar` 只有 `android.*`（连 `java/lang/Object` 都没有）→
  用 Python 把 JDK 的 `jmods/java.base.jmod` 里 `classes/**` 抽出来打成 `~/.apktc/build/libjava.jar`（7556 个类）喂给 R8 ✓
  （**绝不能** `export LD_LIBRARY_PATH` 去跑 jimage/jar：会劫持宿主 shell 的动态库，`bin/mkdir`、`bin/ls` 全起不来 ✗）
- 只混淆、**不裁剪**（`-dontshrink -dontoptimize`）：程序里有多处对**框架类**的反射
  （`DocumentsContract` / `MediaStore$Downloads` / `UsageEvents` / `WebView.evaluateJavascript`），裁剪容易误伤 → 先求稳 ✓
- `-keep` 清单：manifest 组件（`MainActivity` / `SpeechService` / `FloatWin` / `FloatA11y`）+ **`com.jcraft.jsch.**`**
  （JSch 的密码学实现是按类名反射加载的，整包必须留）
- 资源读口只有一处 `Sec.open(ctx, name)`（`Web.readAsset` / `Ssh.asset` / `Store` 都走它）→ 加解密对上层透明；
  这轮顺手把 `.json`（参数词库）和 `.c`（设备端钩子源码）也纳入加密，并清掉 `__pycache__` / `*.bak*` / `*.pyc` 杂物
- R8 默认**不写**映射表 → 在临时规则里加 `-printmapping`，产物旁边留 `releases/c3shell-<ver>-mapping.txt`（解混淆线上堆栈用）

### 验证
```
离线：APK 内证书尾部 9 字节 = BuildInfo.CERT_TAIL = 构建时用的值（fc4d370642bdfbb4dc）
      用这把钥匙解 assets/page.html.enc → 校验和通过、开头就是 <!doctype html> ✓
线上：平板装 3.00.53 → 页面 200 / 299,024 字节（= 运行时按自己签名解密成功 ✓）
      logcat 无异常；混淆生效（方法名已成 com.padagent.c3shell.a.a(...)）
```
> 老实说：客户端加固只能**抬高门槛**，不是不可破 —— 真正算钱的卡密校验本来就在服务器侧 ✓
> 待办：车机（DiLink）当时已断电离线，它装的还是 **3.00.51（未加固）**，等它上线我再刷成 3.00.53。
## 4.21 「切页/滚动卡、点菜单没反应」的真因与修法（2026-09-24，3.00.55）

用户反馈：**APP 界面切页/滚动卡、点一些菜单没反应**（并猜"是不是一直在自动连接主机？"——猜对了）。

### 真因（两条叠在一起）
1. **设备离线时，SSH 请求把浏览器连接池占满**：页面每 **5 秒**轮询 `/api/ssh/drive/status`，
   而每次连接超时是 **8 秒** —— 5 < 8 → 请求互相叠加；浏览器同源只允许 **6 条**连接，
   点菜单时发起的请求全在排队 → 「点了没反应」✗（截图里那些 `连接中…` 就是这个症状）
2. **每 1.2 秒扫一遍终端 DOM**：`stat()` 用 `querySelectorAll(".xterm-rows > div")` 逐行取 textContent 拼字符串，
   终端行数一多就是实打实的 UI 线程开销 → 滚动/切页掉帧 ✗

### 修法
**A. SSH 侧三件套（`Ssh.dial()`，所有真连都走它）**
1. 先做 **700ms TCP 预探测**（设备离线时 <1s 就返回，不再拖满 8 秒）
2. 失败后 **8 秒负缓存**：这段时间内所有请求立刻得到「设备未连接（N 秒后自动重试）」✓
3. **单飞**：同一时刻只允许一次真连，其它请求立即返回「正在连接设备…」（不再堆叠）✓
   （手动点的「测试连接」`force=true` 会绕过负缓存，但同样先预探测）

**B. 页面侧**
- `/drive/status` 轮询改成**自适应**：成功 5 秒，失败退到 15 秒（不再 5<8 叠加）
- `stat()`：只在**终端页**、3 秒一次（原来 1.2 秒、无条件、全量扫）
- 另两处终端相关定时器（每 3 秒）也加了「只在终端页」判断

### 实测（平板，设备离线——正是用户遇到的场景）
```
接口耗时: /api/ssh/hosts          2.5 ms
          /api/ssh/drive/status   3.3~4.0 ms   ← 修前是 8 秒超时 ✗
4 个并发 SSH 请求（模拟连点菜单）: 31 ms 总耗时   ← 修前会各等 8 秒并把连接池占满
滚动后 gfxinfo:  Janky 0.79%  (90th 7ms / 99th 17ms)
          修前:  Janky 5.62%  (90th 38ms / 99th 85ms)
```

> 顺带说明：这不是加固带来的 —— 加固前后冷启动 156ms vs 149ms、静置 CPU 3% vs 4%（噪声范围）✓
> 真因是"设备不在线时把 8 秒超时压在 5 秒轮询上"这个老问题，离线场景才暴露。
## 5. 适配矩阵（CP 已定稿 · SP2025 已实测 · SP2024 待装）

> SP2024 还没装过 → 该列留空；装完直接跑 `sh tools/collect_env.sh` 填。

| # | 项 | CP（历史基线） | SP2024 | **SP2025（2026-09-24 实测）** | APP 要改的地方 |
|---|---|---|---|---|---|
| 1 | 系统 / 内核 / AGNOS | 24.04.3 · 4.9.103 · AGNOS 12.8 | 待填 | **同 CP**（AGNOS 没重刷） | 无需改 |
| 2 | openpilot 路径 | /data/openpilot | 待填 | **同** | 无需改 |
| 3 | 分支 / HEAD / GitBranch | Adapted_By_FangFei · CP-BYD放飞适配版0917Dev | 待填 | **无 .git**；build.json = 2025.002.000 release-c3；GitBranch=release-c3 | 版本/信息改读 build.json |
| 4 | remote（能否增量更新） | 无 | 待填 | **无 .git**（release 整包） | git 类功能要降级 |
| 5 | 参数目录 | /data/params/d → params_cp/d | 待填 | **活库 d_sp → .tmp_LTuZUL**；d → d_tmp 仅 5 项 | **params_dump.py 解析活库** ⚠️ |
| 6 | 参数总数 | 282 | 待填 | **276**（all_keys） | 规模 / 缓存 |
| 7 | 注册表文件 | common/params_keys.h | 待填 | **该文件不存在**；运行时暴露 ParamKeyFlag/ParamKeyType | registry() 改用运行时 API |
| 8 | 默认值表位置 | manager.py + carrot/config.py + nav_params.json | 待填 | manager.py ✅；carrot 两个 ❌ | defaults() 去掉 carrot 段 |
| 9 | 中文标题/说明 | selfdrive/ui/qt/offroad/settings.cc | 待填 | **无此文件**；改为 layouts/settings/toggles.py + sunnypilot settings/ | meta() 重写 |
| 10 | 参数分组结构 | togglesCarrot + widgetIndex | 待填 | toggles.py（Python 结构，待解析） | groups() / groupOrder 重写 |
| 11 | fork 专有参数族 | AutoNavi/AutoFork/AutoCurve/carrot* | 待填 | Sunnylink* · Alpha* · Blinker* · CustomAcc* · MapTargetVelocities · SpeedLimitOffset* + **Byd\*** | 参数页分类 |
| 12 | cereal 差异 | 见 §3.4 | 待填 | 关键字段同名 ✅；carrot* 消失；新增 *SP 服务 | live_stream 字段表 |
| 13 | 设备端 Web 面板 | 8082 / 8888 / 8088 | 待填 | **8765**（SP websocket_server） | 引导 / 链接 |
| 14 | UI 渲染栈 | weston + GL（eglSwapBuffers） | 待填 | ui 仍是 ./ui；渲染栈待复测 | 投屏 |
| 15 | 屏幕分辨率与比例 | 2160x1080（2:1） | 待填 | 待复测（fb_size 取不到） | 投屏尺寸档 |
| 16 | ui 进程 / process_config | ./ui + LD_PRELOAD 注入点 | 待填 | ./ui 在跑；process_config.py **干净**（无注入、无 .dsh-bak） | 投屏注入要重装 |
| 17 | 混淆范围 | opendbc/car/byd/* PyArmor（11 .py） | 待填 | **不再 PyArmor**；BYD 改 .so 编译（values/fingerprints/interface 可读） | 可改边界略宽 |
| 18 | .so 清单 | 4 个（latcontrol/longitudinal/curve/lane_corridor） | 待填 | services · params_pyx · controlsd · plannerd · vision · pandad_api_impl · transformations · libthneed · byd/*.so | 可改边界 |
| 19 | TTS / 语音 | 平板 TTS 可用；车机 BYD 引擎无中文数据 | 待填 | 待复验（宿主侧没变，预计无影响） | 语音模块 |
| 20 | 宿主设备（型号/Android/WebView） | 平板 + 车机 BYD DiLink3.0 | 待填 | 宿主未变（平板 192.168.31.153） | §4.4 |

**SP 适配清单（进度）**
1. ✅ 参数活库解析 + 注册表改运行时 API + 取值归一 + 写回 `Params.put()`（v2 已真机验证）
2. ✅ 版本/信息读 build.json（v2 已带 `env.openpilot`）
3. 🔶 中文名与分组：设备端能拿到的都拿了（分组 276/276、中文名 11）；更全要挖 SP web(8765)
4. ⏳ cereal 字段表按 *SP 服务重列（`carStateSP / selfdriveStateSP / longitudinalPlanSP / liveMapDataSP …`）
5. ✅ **投屏钩子已在 SP 上装好并出帧**（§4.7；工具 `tools/provision_cast.py`）；触控 touchd 已编译并在 8091 监听，实点验证待做
6. ✅ **重新构建 APK**（3.00.19 → 3.00.25 连续迭代）
8. ✅ **参数中文备注 276/276**（§4.8）：随包发布词库 + venv 重入 + 缓存版本绑定
11. ✅ **参数分层/默认隐藏内部状态**（§4.9）：常用 124 / 危险 11 / 内部 141，页面「只看常用」开关
12. ⏳ 动作型参数写入前的强化确认（红字 + 输参数名）
9. ⏳ 动作型参数（DoReboot/DoShutdown/DoUninstall…）写入前的二次确认（页面）
13. ✅ **老镜像 SP 0.9.8 全套适配**（§4.10）：解释器动态解析 / fork 判定 / 词库 408 条 / drive_watch 回退 / 投屏重装 / 装机验证
10. ⏳ 车机（BYD DiLink）装最新 APK：代码是共用的（悬浮窗尺寸无车机分支），只差装机 —— 车机当前不在同一网络
6b. 原第 6 条：**v3.00.19 / versionCode 507**（`releases/c3shell-3.00.19.apk`，已装平板并核对 versionName）
7. ✅ **版本识别接进 APP**（2026-09-24）：新增 `/api/ssh/env`（Java）+ 顶部设备徽标 + 能力门禁（页面）
   - 实机验证：连上后徽标显示 **`SunnyPilot（阳光） 2025.002.000`**，旁为「设备已连接」（截图 `_attic/verify-319/app-319.png`）
   - 门禁行为：`caps.cast=false` 时「开始投屏」置灰 + 投屏卡片顶部黄条说明缺什么；曲线页顶部提示缺的服务
   - 探测失败一律静默降级（认不出系统时功能照旧）

## 6. 换系统的操作次序（避免把能用的东西弄坏）
1. 平板侧先做**配置快照**（DSH undo_snapshot）；设备侧先在 APP 里存参数档案（A–H/Z）+ 检查点
2. 记下当前能用的安装包 `releases/c3shell-<当前版本>.apk`（回退锚点）
3. 刷 SP **前**先把 §3.7 的设备侧改动完整回退（cp .dsh-bak → 原文件；rm 钩子；restart comma）—— 别把 CP 的钩子留在 SP 上
4. 刷完先跑 collect_env.sh（只读），再装 APP 连一次；这一步**只验两件事**：连得上 + 能读参数
5. 参数对比：把 CP 的 282 项档案与 SP 的新注册表做 diff（多 / 少 / 改名）→ 决定参数页要改什么
6. 投屏 / 触控**放最后**（要改设备端 process_config.py，风险最高，且必须可一键回退）
7. 每步留证据（截图 / 接口返回 / 日志），失败立即回退，不带着坏状态往下走

## 7. 红线
- 不自动重启设备：刷机引导只引导，重启必须用户点确认
- 不在设备上乱点系统 UI（误触屏保/应用中心会把用户界面搞乱）
- 改 process_config.py 前必须备份（.dsh-bak），改完必须能一键回退
- 混淆 / 编译产物（BYD 目录、4 个 .so）：APP 不依赖其内部实现做功能
- 事实以设备为准；本文没写来源的结论，动手前先核实

## 8. 本次 SP 适配的回退锚点（2026-09-24 建立）

改代码/改设备前先把「现在能用的一版」钉住了，任何时候都能退回来：

| 项 | 位置 / 值 |
|---|---|
| 改造前 APP 版本 | **v3.00.18（versionCode 506）** |
| DSH 配置快照 | `undo_snapshot` 手工快照 **20260924-140530-cf0f**（`undo_list` 可见，可 `undo_restore mode=id` 还原） |
| 源码整树归档 | `_attic/rollback-20260924-140530/src-before-spadapt.tar.gz`（45MB，不含 releases/_attic） |
| APK 锚点 | `_attic/rollback-20260924-140530/c3shell-before-spadapt.apk`（= 改造前的 c3shell.apk） |
| 设备端状态 | `_attic/rollback-20260924-140530/device/`：process_config.py · build.json · env_dump.json · dsh_ls.txt · params_ls.txt · services.txt |
| CP 参数脚本原件 | `assets/remote/params_dump.py.bak-cp-20260924` |

怎么退：
- 退源码：`tar -xzf _attic/rollback-20260924-140530/src-before-spadapt.tar.gz -C c3shell/`
- 退 APP：`adb install -r _attic/rollback-20260924-140530/c3shell-before-spadapt.apk`
- 退设备端改动（投屏钩子那种）：`cp _attic/rollback-.../device/process_config.py /data/openpilot/system/manager/process_config.py` + 重启 ui
- 退 DSH 配置：`undo_restore mode=id snapshot_id=20260924-140530-cf0f`

## 4.22 界面显示模式**默认「自动」**（2026-09-24，3.00.57）

用户要求：「界面显示模式默认为自动」。

原先的问题：**代码里的默认值是 `tablet`，不是 `auto`** —— 三处读取都写成 `getString("displayMode","tablet")`，
所以首次安装/没设置过时永远进「手机/平板」布局，「自动」必须手点一次才生效 ✗。

改动（三处 Java + 一处页面）：
| 位置 | 原来 | 现在 |
|---|---|---|
| `MainActivity.load()`（下发给网页的 `dm=`）| `"tablet"` | **`"auto"`** |
| `MainActivity.carMode()`（真正决定车机/平板布局）| `"tablet"` | **`"auto"`** |
| `MainActivity.onConfigurationChanged()`（旋转/尺寸变化重判）| `"tablet"` | **`"auto"`** |
| `page.html` 选中态 `markChoices()` | `c3dm\|\|c3layout\|\|"tablet"` | **`c3dm\|\|"auto"`** |

自动规则（未动）：`pageWidthDp() >= AUTO_CAR_MIN_DP(900)` → 车机模式（左栏菜单），否则手机/平板布局。
界面设置里三个按钮 `手机/平板 · 车机 · 自动` 照旧，点了会记住 ✓

实测（平板 v3.00.57）：
```
改前 prefs: displayMode=tablet     → 顶栏布局
设为 auto 后: displayMode=auto      → 界面设置里「自动」高亮 ✓
平板 2272px / density 400 = 909dp  ≥ 900dp  → 自动判定为「车机模式（左栏菜单）」✓（按规则，符合预期）
```
> 注意：平板是 909dp，**正好压在 900dp 阈值上面 9dp**，所以自动模式下它会进「车机」布局（左栏菜单）。
> 想让它保持顶栏布局：界面设置 →「手机/平板」点一次即可（会记住）；
> 或者把 `AUTO_CAR_MIN_DP` 提到 1200（只有真车机 1920dp 才进车机模式）—— 一句话我就改 ✓
### 4.22.1 赞赏弹窗底部改版（2026-09-24，3.00.58）

用户要求：「赞赏页面把最下面的内容修改一下，赞赏大于20可以关闭弹窗，不用在输入框显示需＞20」

| 改动 | 原来 | 现在 |
|---|---|---|
| 输入框提示 | `赞赏金额（元，需 >20）` | **`赞赏金额（元）`**（不再预先写规则）|
| 提示行 | `已经赞赏过？填一下金额（需大于 20 元），点「我已赞赏」告诉我一声 🙏` | `已经赞赏过？填一下金额，点「我已赞赏」告诉我一声 🙏` |
| 点「我已赞赏」 | 等后台上报**成功**才关弹窗（服务器没配 → 弹窗关不掉 ✗）| **金额 >20 先把弹窗关掉**，上报放后台，结果只用一条轻提示 ✓ |
| 校验 | 金额 ≤20 → Toast「请输入大于 20 的赞赏金额 🙏」 | 不变（规则保留，只是不再写在输入框里）|

验证：`classes.dex` 字节级比对 —— 3.00.57 有 `赞赏金额（元，需 >20）`、`需大于 20 元`；
3.00.58 两者都为 0，新增 `赞赏金额（元）`，校验文案 `请输入大于 20 的赞赏金额` 仍在 ✓
## 4.23 体验版：**3 天倒计时**（72 小时，2026-09-24，构建开关）

用户要求：「增加一个体验版本，…倒计时…开始定为 2026.9.25 早上8点，有效期72」→ 后明确**改为 3 天**。
最终口径：**体验期 2026-09-25 08:00 → 2026-09-28 08:00（3 天 = 72 小时）** ✓
（天数由 `START/END` 算出，改 `C3_TRIAL_END` 即可变；代码/文案里不再写死天数 ✓）

### 怎么打包
```bash
bash c3shell/build.sh 3.00.60 trial      # 体验版 → releases/c3shell-3.00.60-体验版.apk
bash c3shell/build.sh 3.00.61            # 正式版（同一份代码，TrialInfo.ON=false，体验逻辑完全不参与）
# 想改体验期（不用改代码）：
C3_TRIAL=1 C3_TRIAL_START="2026-09-25 08:00:00" C3_TRIAL_END="2026-09-28 08:00:00" python3 c3shell/build_apk.py c3shell out.apk
```

### 实现（四处）
| 位置 | 作用 |
|---|---|
| `build_apk.py` → 生成 `TrialInfo.java` | 把 `ON / START / END / LABEL` 写进代码（默认 **2026-09-25 08:00 → 2026-09-28 08:00** 北京时间 = 3 天；可用环境变量覆盖）|
| `Trial.java` | ① 过期 → **不可取消弹窗 + 退出**；② 未开始 → 提示「体验期 X 开始」，照常用；③ 最后 24 小时 → 每天提醒一次；④ **防改表**：记住「见过的最晚时间」，把系统时间往回调**不会**延长体验期 |
| `MainActivity` | 启动闸门 `Trial.gate()`；页面 URL 带 `&trial=1&ts=&te=`；「关于」弹窗末尾显示【体验版】剩余 X 天 Y 小时 |
| `page.html` | 右上角常驻小红条：未开始「体验期 9月25日 08:00 开始」／进行中「体验版 · 剩余 4 天 03 小时（到 …）」／已结束「体验期已结束」（每 20 秒刷新）|

### 实测（平板 v3.00.60）
```
体验版（ON=true，3 天窗口，v3.00.61）：
  启动轻提示 → 「体验版：体验期 2026-09-25 08:00 开始，共 3 天」✓（实拍 _attic/v-trial3d-toast.png）
  右上角红条 → 「体验期 9月25日 08:00 开始」✓（当时 09-24 23:01，未开始）
  「关于」弹窗 → 【体验版】剩余 3 天 0 小时　体验期 2026-09-25 08:00 → 2026-09-28 08:00 ✓
  页面资源（加密态）解密核对：trialChip 出现 3 次 ✓；TrialInfo START/END = 1790294400000 / 1790726400000 ✓
过期态（临时把 END 设为 09-24 20:00 重打一版）：
  启动即弹「体验期已结束」+「退出」按钮，页面完全不加载 ✓（实测截图 `_attic/v-trial-expired.png`）
正式版（ON=false）：
  冷启动 156 ms，logcat 无任何「体验版」字样 ✓（平板最终装的是这一版）
```
> 提醒：体验版**只能抬高门槛**（改系统时间也被 maxSeen 挡住；真要破还是能破——它面向的是普通试用者）✓
## 4.24 「投屏能力一直在检查中」+ 投屏没画面（2026-09-26，3.00.63）

用户报：车机上「投屏能力：检查中…」一直转、投屏没画面。实测两个独立问题叠在一起：

### 问题 1：设备换成 **SunnyPilot 2025.002** 后投屏钩子没了（真没画面的原因）
设备 2026-09-26 01:08 换了系统（`/data/params/d_sp`、build.json origin=sunnypilot），换系统会清掉：
`uihook.so`、`process_config.py` 里的 `LD_PRELOAD` 注入、`touchd`、`/dev/shm/ui.rgb` —— 实测全都没有 ✓
所以 mjpeg 服务在跑但 `frames=0`，而且**车机那边已经堆了 80 条僵尸 MJPEG 连接**（页面不停重连）✗

修法（就是投屏页那个「一键安装投屏能力」在设备上做的事，我直接走脚本做了）：
```
推送 cast_provision.py / uihook.c / touchd.c / mjpeg.py →
/usr/local/venv/bin/python3 cast_provision.py install   （33 秒）
结果: {"preload":true,"loaded":true,"frames":true,"frame":"1024x512#61","ok":true}
实测: ui.rgb 39 帧/2 秒（≈19 fps）· mjpeg frames 增长 · 8090 连接从 80 掉到 1 ✓
另: touchd 没在跑 → 手动起了一次，8091 /ping → ok（反控可用）✓
```

### 问题 2：页面永远停在「投屏能力：检查中…」（UI 逻辑 bug）
`dshEnvLoad()` 原来**只在「连接测试成功」那一刻**被调用（`setStatus(ok)` 那条线）。
如果页面在"设备已连接"的状态下加载，就没有那次跳变 → 能力探测从不执行 → 那行字永远停在「检查中…」✗
（页面里也没有超时/失败态，用户只能干等。）

修法：
- 新增 `dshEnvKick()`：**打开页面就主动探一次**（1.5s / 4s 各一次）、失败自动重试最多 8 次（每 5 秒）、
  仍失败 → 那行变成「检查失败 + 重试按钮」（状态一定收敛，不再让用户干等）✓
- 另外每 60 秒复查一次 ✓
- **钩子没装时不再挂画面流**：自动接入前先看 `caps.cast`，为 false 就提示「投屏能力未安装」并直接返回
  （这条同时治住了那 80 条僵尸连接 ✓）

### 实测（车机 v3.00.63）
```
投屏能力：已就绪 ✓（SunnyPilot（阳光）；点画面反控前先按「启用反控」）
投屏中 · 6.0 fps · 21.1ms/帧   ← 画面是活的（SunnyPilot 自己的 UI）
设备侧: pulls 864 → 911（5 秒 47 次）· age 0.04~0.06 · clients 0 · 8090 连接 1 条 ✓
env 探测: caps={"params":true,"live":true,"replay":true,"cast":true} · cast.ready=true ✓
```

> 教训：**换系统 = 投屏钩子必然丢**（这是设计上的必然，不是 bug）。APP 已经能一键装回来 ✓
> 但「检查中…」这种没有终态的 UI 是设计缺陷 —— 任何异步探测都必须有超时 + 失败态 + 重试 ✓
### 4.24.1 为什么「设备重启」会让车机锁 **LKAS 故障**（2026-09-26 实测查清）

用户问：为什么设备重启之后，车机也得跟着重启才能用（LKAS 故障）？

### 实测结论：这是**车自己锁的**，不是 APP/设备算出来的
```
实时信号（venv python + cereal 读 carState）:
  carState: vEgo=0.00  gearShifter=drive  steerFaultTemporary=False  steerFaultPermanent=True
  selfdriveState: enabled=False state=disabled
```
链路（都在设备源码里能查到）：
```
车机 EPS 锁故障 → 车端口报 steerFaultPermanent=True（来自 CAN，不是 openpilot 判断的）
  → selfdrive/car/car_specific.py:213  if CS.steerFaultPermanent: events.add(EventName.steerUnavailable)
  → selfdrive/selfdrived/events.py:781  EventName.steerUnavailable → 「LKAS 故障：请重启车辆以启用」
```
**为什么只能重启车辆**：故障锁在**车的 EPS 模块**里（永久故障/DTC），openpilot 只是把它报出来；
重启 APP、重启设备、重启 openpilot 都改不了车里的锁 —— 只有**点火循环（熄火→等 10 秒→重新上电）**才清 ✓

**为什么"设备重启"会触发**：BYD 这套 LKAS 是**上电时握手**的。设备（或 openpilot 的 comma.service）在车辆通电/行驶中
重启 → 握手中断、LKAS 心跳消失 → 车机 EPS 锁故障。所以：**车辆通电时不要重启设备/openpilot** ✗

### 本次是谁触发的（如实记录）
2026-09-26 09:19 我给设备装投屏钩子（`cast_provision.py install` → `systemctl restart comma`），
当时车辆是通电的 → 09:22 车机上就出现了这条 LKAS 故障 ✓ 是我这步操作触发的。

### 已做的防护（3.00.64）
- 「一键安装投屏能力」现在**先弹确认**：说明会重启一次、车在通电/行驶时可能锁 LKAS 故障、建议熄火后再装 ✓
- 「重启设备」「重启 openpilot」的确认框里也加了同一句风险提示 ✓
- 投屏卡片未安装提示里常驻一行「⚠ 装之前请确认车辆已熄火」✓

> 待办（可选）：装之前用 `carState`（档位/车速/点火）**自动判断**车辆是否在通电，只在有风险时警告 ——
> 现在的做法是无条件提醒（宁可多说一句，也不要用户又踩一次）✓
### 8.1 最新锚点：**3.00.56**（2026-09-24 22:35 保存，用户要求「版本保存」）

| 项 | 位置 / 值 |
|---|---|
| 当前版本 | **v3.00.56（versionCode 546）** |
| 源码整树归档 | `_attic/rollback-20260924-223509/src-3.00.56.tar.gz`（**506 个文件 / 32.3 MB**；不含 `releases/`、`_attic/`、构建产物）|
| APK 锚点 | `_attic/rollback-20260924-223509/c3shell-3.00.56.apk`（sha256 见同目录 `MANIFEST.txt`）|
| 混淆映射表 | `.../c3shell-3.00.56-mapping.txt`（线上堆栈出乱码时用它解）|
| 加固前留存 | `.../c3shell-3.00.51-未加固·留存.apk` |
| DSH 配置快照 | 手工快照 **20260924-223515-5f92**（`undo_list` 可见）|

这一版包含：系统版本自适应 · 投屏（**拉帧** + 一键安装）· 参数词库/分层 · 文件页改名删除 · 终端提速 ·
赞赏提醒 · **R8 混淆 + 资源绑签名加固** · **离线快回（界面不再卡）**。

怎么退：
- 退源码：`tar -xzf _attic/rollback-20260924-223509/src-3.00.56.tar.gz -C c3shell/`
- 退 APP（平板）：`adb -s 127.0.0.1:<无线调试端口> install -r _attic/rollback-20260924-223509/c3shell-3.00.56.apk`
- 退 APP（车机）：`adb -s 192.168.0.100:5555 install -r _attic/rollback-20260924-223509/c3shell-3.00.56.apk`
- 退到未加固版：`adb install -r _attic/rollback-20260924-223509/c3shell-3.00.51-未加固·留存.apk`
- 退 DSH 配置：`undo_restore mode=id snapshot_id=20260924-223515-5f92`

> 注：设备（C3）当时离线，所以这次**没有**存设备端状态（`process_config.py` 等）——
> 设备端的东西都在 `assets/remote/` 里，投屏钩子随时可用投屏页「一键安装投屏能力」重装 ✓
### 4.7.1 悬浮窗黑屏（2026-09-24 修完并实机验证）

**用户反馈**：投屏能用、触控没问题，但**悬浮窗没有画面**；顺带要求默认尺寸翻倍。

| 问题 | 真因（实测） | 修法 |
|---|---|---|
| 悬浮窗黑屏 | APP 的页面服务端口会**退让**（`MainActivity` 里依次试 3081→3082→3083→随机，注释里就写着「平板上还跑着连接器」的情形）。本机实测 APP 落在 **3082**，而 `FloatWin` 里 `cast.html` 的地址**写死 127.0.0.1:3081** → 浮窗 WebView 加载到的是**连接器**的页面（`/cast.html` → 404）= 黑屏 ✗ | 新增 `appBase()`：先读 APP 自己存的 `localPort`，再依次试 3081~3083，并**实测 `/cast.html` 返回 200** 才采用（防止再认错服务）✓ |
| （顺带）换网/多主机时浮窗没画面 | `cast.html` 取的是 `hosts[0]` 而不是**默认主机** → 列表第一个是连不上的热点地址时就黑屏 ✗ | 改成：`defaultHostId` 优先 + 逐个候选探测（一个连不上自动试下一个）+ 自动拉起设备侧投屏服务 ✓ |
| 默认尺寸太小 | 原来 `min(0.34×屏, 560×460)` | 翻倍成 `min(0.68×屏, 1120×920)` ✓ |

**实机验证（2026-09-24，v3.00.22）**
- 用 APP 自己的接口起服务与浮窗：`POST /api/cast/start` → `running src=ui frames=5 ms=34.3`；`POST /api/float/start` → `running:true`
- 系统窗口表里浮窗 `contentSize=920x1120`（旋转显示空间）= 旧默认 560x460 的**整整两倍** ✓
- 截图 `_attic/float-322.png`：浮窗里就是 C3 的 SunnyPilot 界面，右下角提示「来自 C3 设备 ✓」✓

**教训（写进流程）**：APP 自己也是个 HTTP 服务，**任何指回自己的地方都不能写死端口**。
平板上连接器占 3081 是正常情形，APP 会退让到 3082/3083 —— 写死 3081 的代码会静默指到别人身上（这种 bug 只在「两个服务同时活着」时出现，最难查）。
