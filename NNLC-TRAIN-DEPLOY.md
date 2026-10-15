# NNLC 训练 → 回灌 C3：地址速查 + 硬性清单

> 2026-09-27 建。来源标注：**【口述】** = 用户当天口述；**【实测】** = 当天在设备上跑出来的输出；**【推断】** = 由代码推得、未在实车上验证。

## 0. 设备地址速查 【口述】

| 场景 | 地址 | 连接器 host id | 备注 |
|---|---|---|---|
| **开车时（车载 WiFi）** | `192.168.0.66` | `c3` | 大多数时候是这个 |
| **在家** | `192.168.31.49` | `c3-lan` | 家里 Wi-Fi 网段 |
| 其他住处 / 别的地方 | 待报 | — | **换地方先问用户**，不要猜 |
| **其他地方（2026-09-27 实测）** | `10.190.129.66` | 未加入连接器 | 设备自己报 `wlan0 = 10.190.129.66/24`；开机 11 分钟 |
| **2026-09-27 晚（又换）** | `192.168.101.3` | 未加入连接器 | 设备自报 `wlan0 = 192.168.101.3/24`；同机 `comma-c5f64914`；**当前可达** |

- 私钥：`$DSH_HOME/ssh-connector/keys/id_ed25519`（= `named-keys/神牛`，2590 B，两把内容一致）。
- ⚠️ 连接器 `ssh-connector.json` 里 `defaultHostId` 目前是 `c3-lan`（家里那个）；**车上是 `c3`，要手切**。

## 1. 现状 【实测 2026-09-27】

- `build.json`：`release-c3` / `2025.002.000` / `release_notes = "BYD"` / **无 .git**。→ 当前是 **SP2025 BYD 口**，不是放飞版 CP。
- 活库：`/data/params/d_sp → /data/params/.tmp_8qAEBb`；`/data/params/d → d_tmp`（**只有 5 个键的老目录，别写错库**）。
- 横向相关现值：`NeuralNetworkLateralControl=0`（关）/ `BydUseNonLinearTorque=1` / `LateralRulePlannerEnabled=1` / `MadsSteeringMode=0` / `TorqueParamsOverrideEnabled=0`。
- 模型库 `sunnypilot/neural_network_data/neural_network_lateral_control/`：**114 个 json，无 BYD**；`torque_data/substitute.toml` 里也无 BYD 条目。
- 用设备自己的解析器跑 `get_nn_model_path(CarParams)`：

```
fingerprint: BYD_SONG_PRO_DMI_24   steerControlType: torque
-> (.../HYUNDAI_SONATA_HYBRID.json, 'HYUNDAI_SONATA_HYBRID', exact_match=False)
```

⇒ **现在就算把开关打开，NN 前馈用的是索纳塔混动的模型**（相似度 0.45，阈值 0.9），并置 `fuzzyFingerprint=True`。这就是为什么"打开会好一点"必须靠自训模型来兑现。

## 2. 自训模型要被 C3 真用上，必须满足（代码路径 【实测】）

1. **文件名 = 车架指纹**：`BYD_SONG_PRO_DMI_24.json`
   - `helpers.py::get_nn_model_path` 用 `SequenceMatcher` 比「文件名 stem ↔ carFingerprint」；同名 → 相似度 1.0 → `exact_match=True`，`fuzzyFingerprint=False`，直接命中。
2. **放到** `/data/openpilot/sunnypilot/neural_network_data/neural_network_lateral_control/`
3. **json 结构**（`nnlc/model.py::NNTorqueModel` 只认这些键）：
   - `input_size`（现有=18）、`output_size`（=1）、`input_mean` / `input_std`（18×1）
   - `input_vars`（特征名清单，现有顺序：`v_ego, lateral_accel, lateral_jerk, roll, lateral_accel_m03/m02/m01, lateral_accel_p03/p06/p10/p15, roll_m03/m02/m01, roll_p03/p06/p10/p15`）
   - `layers: [{dense_N_W, dense_N_b, activation}, ...]`；activation 支持 `identity` / `sigmoid`（json 里写 `σ` 也会被映射）
   - 可带 `model_test_loss` / `current_date_and_time`
   - ⚠️ `NNTorqueModel` 不校验 `input_vars`；**训练时的特征顺序必须和 `nnlc.py` 组装输入的顺序一致**（顺序错了不会报错，只会输出错的力矩）。
4. **上线三项**（【推断】，待实车验证）：`NeuralNetworkLateralControl=1`（写活库，别写 `d`）→ **重启 controlsd**（`CarParamsSP` 是启动时初始化的）→ 复查 `CarParamsSP.nnlc.model.name` 应为 `BYD_SONG_PRO_DMI_24` 且 `fuzzy=False`。

## 3. 自检 / 回灌前的校验（我可以在设备上只读跑）

- `NNTorqueModel(path)` 加载：`validate_layers()` 遇到未知 activation 直接抛错；
- `check_for_friction_override()`：内部 `evaluate([10.0, 0.0, 0.2]) < 0.1` 时置 `friction_override=True`（会改摩擦处理）——**新模型上线前先看这个值是 True 还是 False**；
- `get_nn_model_path(CarParams)` 复核命中名与 `exact_match`；
- 与旧模型（索纳塔）做同输入输出的对照，确认量级没跑偏。

## 4. 上线 A/B 与回滚

1. 备份：活库 `NeuralNetworkLateralControl` 现值 + 活库 dump（存工作区）；
2. 停车状态下部署新 json + 打开开关；
3. 只重启 controlsd（不整车）；
4. **低速固定路线**先跑，看 swaglog 的 nnlc 事件 + 手感；
5. 异常 → 开关写回 0（+ 删/换回旧 json）+ 重启 controlsd；
6. 不要在车流里做第一次试；`BydUseNonLinearTorque=1` 的非线性整形与 NN 前馈是**叠加**关系（§7.1 记过急转饱和风险）。

## 5. 待补

- [ ] 训练器是哪个（仓库 / 链接）——拿到后核对其输出格式与上面 schema 是否一致；
- [ ] 训练数据从 C3 怎么取（哪些 route 段、速度/路况覆盖要求、是否需特定标定路段）；
- [ ] 新模型名字/版本如何留档（建议文件名带日期另存一份，正式名用指纹）。


## 6. 训练器：基本确认是公开的 `amzoo/openpilot-nnlc-tools` 【实测 2026-09-27 读 README】

- 仓库：https://github.com/amzoo/openpilot-nnlc-tools （sunnypilot 社区 2026-02 前后整理的 NNLC 完整流水线）
- 流水线：**sync rlogs(SSH) → extract(--temporal) → score → prune → visualize 覆盖率 → interventions 分类剔除 → 训练(Julia) → deploy**
- 环境：Python 3.11+ · Julia 1.9+（CUDA/Metal GPU 更好，可 `--cpu`）· Docker 可选（**Mac 的 Metal 不能走 Docker GPU**）
- 部署说明：把训练产出的 json 拷进 `sunnypilot/neural_network_data/neural_network_lateral_control/`，**文件名 = 车架指纹** → 与本文 §2 我在设备上实测的一致（`BYD_SONG_PRO_DMI_24.json`）。

### 采集数据的硬约束（README「Driving Tips」）【实测】

- **采集时 NNLC 必须关着**（用原厂扭矩控制器跑），否则扭矩信号被已有模型污染 → 现在 `NeuralNetworkLateralControl=0` 正好，**采数据阶段别开**。
- 关掉打灯横向类设置（`BlinkerPauseLateralControl` 已是 0 ✓）。
- 目标量：**5–10 小时干净数据 / 20–30 条 route**；城市 5–15 m/s、郊区 15–25、高速 25–35；左右弯均衡；多种坡度；避免堵车/停车场/施工；干路面。
- 建议先跑 `score_routes` + `visualize_coverage`，红色格（<50 样本）要专门补跑。

### 车上数据家底（只读实测 2026-09-27）【实测】

- `/data/media/0/realdata`：**26 条 route**、1128 个段目录；`/data` 30G 用了 15G，余 14G。（2026-09-27 晚复查，又开了一段）
- 时间跨度：2025-07-02 → 2026-09-27 12:54（最近一段）。
- ⚠️ 条数够 ≠ 数据干净：2026-09-19 那条 route 接管率 50.2%（`dsh-ssh-connector/CONTROL16-c3.md`）——这类必须先过 score/prune 才能进训练。

## 7. 待确认（问用户）

- 电脑系统 + 有无 NVIDIA 显卡（决定 GPU 还是 `--cpu`）；
- 电脑与车机是否同一局域网（sync 脚本直连车机 IP，车上是 `192.168.0.66`）；
- 包是不是 amzoo 这个（拿链接/名字做版本核对）；
- 联网通道：网盘直链我下不了；走"电脑开 SSH"或"把关键小文件拷进工作区"。


## 8. 到"电脑"的通道（2026-09-27 讨论）

**结论：手机不能通过 USB 去读电脑。** USB 这个口子（MTP / ADB）方向是「电脑当主机、手机当设备」；DSH 跑在手机里，枚举不到电脑的盘。
实测本机：`sys.usb.config = adb`（当设备模式）、手机自带 adb 客户端 `1.0.41 / 35.0.2-android-tools`。

可行变通（按省事排序）：

1. **USB + HTTP（零服务安装）**：电脑有 adb → 手机开 USB 调试插上 → 电脑在训练器目录跑 `python -m http.server 8000` → 电脑执行 `adb reverse tcp:8000 tcp:8000` → 手机侧 `127.0.0.1:8000` 即可只读拉取该目录。
2. **USB 网络共享 + SSH**：手机开「USB 网络共享」→ 电脑拿到 `192.168.42.x`（手机 `192.168.42.129`）→ 电脑开 OpenSSH 服务器 → DSH 直接 ssh 过去（同 C3 的连法）。
3. **兜底**：把关键小文件（README/版本信息、任意一个导出模型 json 样例、训练脚本、数据 schema）拷到手机存储——总共几十 KB~几 MB，不需要整个安装包。
4. 若电脑与手机本来就在同一局域网，SSH/HTTP 直接走局域网，USB 都不用。

电脑侧待确认：系统（Windows/macOS/Linux）、有无 adb / 能否开 OpenSSH、有无 NVIDIA GPU（训练在哪台机器跑）。

## 9.1 日志体积实测（2026-09-27 晚，C3 `192.168.101.3`）

| 文件 | 数量 | 合计 |
|---|---|---|
| `qlog.zst`（cereal 数据，NNLC 特征从这里抽） | 1127 | **464 MB** |
| `rlog.zst`（原始 CAN） | 1127 | **10522 MB（10.3 GB）** |
| `qcamera.ts`（窄角相机） | 1126 | **2357 MB（2.3 GB）** |

- 每段目录：`/data/media/0/realdata/<route>--<hash>--<seg>/`，三个文件都在这一层（**glob 只有一层 `realdata/*/`**，别再写成两层）。
- 含义：**只要 qlog 的话 464 MB**，走手机中转很轻松；**要 rlog 就是 10 GB 级**。→ 取决于 `X:\nnlc` 的训练流程实际同步什么（待看）。
- 26 route / 1128 段；最新段 2026-09-27 12:54；`/data` 余 14 GB。

## 9. 进展 · 2026-09-27 晚（电竞酒店）

- 电脑：训练器在 `X:\nnlc`，**需要 C3 的日志**才能训练。
- 网络：电脑 IP 段 ≠ Wi-Fi 段 → 电脑**连不到 C3**；改用 **USB 把手机与电脑连起来**（手机当桥）。
- 手机侧实测：`sys.usb.config = adb`（当设备）；手机剩余 **168 GB**，够中转到手机再送电脑。
- 手机 → 电脑 的通道**还没建立**：`127.0.0.1:8000/8080/5000/9000` 全关。
  - 通道 A（电脑有 adb）：`adb reverse tcp:8000 tcp:8000` + 电脑在 `X:\nnlc` 跑 `python -m http.server 8000` → 手机侧 `127.0.0.1:8000` 可只读该目录。
  - 通道 B（电脑没 adb）：手机开「USB 网络共享」→ 电脑拿 `192.168.42.x` → 同跑 http.server（防火墙允许）→ 手机按该 IP 访问。
- ⚠️ **C3 当前不可达**（`10.190.129.66:22` 超时）：车/C3 关机或不在同网段 → **日志今晚拉不了**，等回到车上。
- 车上取日志两条路：
  1. 带笔记本上车 → 手机 USB 网络共享给笔记本 → 笔记本经手机 NAT 直达 C3，直接 rsync（最省事）；
  2. 我在车上把 C3 日志拉到手机 → 回酒店经 USB 送电脑（电脑加 `adb forward tcp:9000 tcp:9000`，手机起服务，电脑 `curl` 批量拉；或手机切 MTP 手动拖）。

**待问**：X 盘是移动硬盘还是内置盘；电脑有无 adb / Python / Node。

## 10. 训练器真实身份（2026-09-27 实锤：从 exe 里挖出来的）【实测】

文件（手机侧）：`/sdcard/Download/nnlc/`
- `NNLC_Trainer-1.0.5-windows-x64.exe`（60.6 MB）＝ **PyInstaller 打包的 Windows GUI（Python 3.11 + tkinter）**
- `NNLC_Julia_Runtime-windows-x64-v1.zip`（502 MB）+ 解包后的 `NNLC_Runtime/`（julia 1.10.11 + depot）
- 来源：`windows_runtime.json` 里 `release_url = https://github.com/samhzx/nnlc`（tag `julia-runtime-v1`）

### 内含流水线（符号/字符串实证）
- Python：`nnlc_gui` · `nnlc_runtime` · `nnlc_auto_train` · `nnlc_tools.{extract_lateral_data, extract_rlog_worker, score_routes, prune_routes, visualize_model, visualize_coverage, streaming_data, steering_classifier, ...}`
- Julia：`training/latmodel_temporal.jl`（**主模型 = 与 sunnypilot 生产 NNLC 一致**）· `latmodel.jl` · `latmodel_temporal_steer_angle.jl` · `latmodel_NeuralPDE.jl` · `install_packages.jl`
- CLI 示例（exe 内帮助文本）：`python nnlc_auto_train.py --data ./data --car BYD_TANG_DMI_24`、`--min-score 40`、`--skip-deploy`、`--streaming --batch-size=4096`

### 硬性要求（它的 training/README.md 原文）
1. **输入 = rlogs**（它找 `rlog.zst` / `rlog.bz2` 段目录；qlog 不在它的名单里）
2. `extract_lateral_data --temporal` → CSV（18 维：v_ego · desired_lateral_accel · friction_input · roll · torque_output + 时序列 −0.3/−0.2/−0.1/+0.3/+0.6/+1.0/+1.5）
3. 输出 JSON = `NNTorqueModel` 格式（input_size/output_size/input_mean/input_std/layers/input_vars）→ 放
   `sunnypilot/neural_network_data/neural_network_lateral_control/` → **与本文 §2 在 C3 上实测的加载器完全一致** ✓
4. **训练固定 CPU**（不需要 NVIDIA 显卡 ✓）；小数据集 1000 epoch ≈ 8 秒；大数据用「CPU 流式低内存模式」
5. ⚠ 一键流程**建议预留 ≥100 GB 磁盘**（中间 CSV 很大；流式只省内存不省磁盘）
6. 车名 `--car` 必须 = 车架指纹 → 你要填 **`BYD_SONG_PRO_DMI_24`**（填错 → C3 加载时退化成索纳塔模型，§1 已实测）

### 数据体积（C3 实测 2026-09-27）
| 范围 | rlog 体积 |
|---|---|
| 全部 25 条 route / 1127 段 | **10.3 GB** |
| 最新 5 条 | 3.25 GB |
| 最新 10 条 | 8.53 GB |
| 单条最大的 `0000000f`（437 段） | 4.3 GB |
| 今天那条 `00000018`（278 段） | 2.6 GB |

### 搬运路径（现在可行）
```
C3 (192.168.101.3) --我 SSH--> 手机 /sdcard/Download/c3rlogs/ --你 adb pull--> 电脑 X:\...
```
（电脑已装 adb；不需要把私钥放到电脑上 ✓）

## 11. C3 → 手机 搬运：踩过的坑（2026-09-27 晚）

症状：三版脚本都"跑完了"但只落了 10 个文件。**两个真因**：
1. `ls -d dir/` 的输出带尾斜杠 → `n=${d##*/}` 取到**空字符串** → 传给远端 tar 的文件清单是空的（tar 空清单**退出码 0**，所以看起来"成功"✗）
   → 改成 `n=$(basename "$d")`
2. `ssh ... 2>&1 | tar -xf -` 把 **ssh 的 known_hosts 警告混进了 tar 流** → 本地 tar 报 "This does not look like a tar archive" ✗
   → ssh 加 `-o LogLevel=ERROR`，且**绝不**把 ssh 的 stderr 并进管道（用 `2>/dev/null`）

另外实测：**C3 ↔ 手机 Wi-Fi 只有约 0.5 MB/s**（读 8.1 MB 花了 17.8 s）；本机写盘不是瓶颈（2.2 GB/s）→
今天那条 2.6 GB 约 1.5 h，全量 10.8 GB 约 6–8 h。想快可考虑让手机连 C3 自己的 Hotspot（C3 上 `nmcli` 里有 Hotspot 配置，当前未启用）
脚本：`c3rlogs-prior18.sh`（只搬今天那条，分块 tar + 重试）/ `c3rlogs-pull.sh`（全量 rsync）· 日志同名 .log
## 12. 今天那条 route 已搬到手机（2026-09-27 23:45 完成）【实测】
- 结果：`/sdcard/Download/c3rlogs/` = **278 段**（全为 `00000018--7b266847e8--*`），**278 rlog + 278 qlog**，无缺件，**2.7 GB**
- 零碎目录（之前几次尝试留下的其他 route，约 850 个）**已按用户要求清掉**；续搬全量时这 ~0.9 GB 会重新拉一遍（约 10 分钟）
- 电脑侧动作：`adb pull /sdcard/Download/c3rlogs X:\nnlc\data`
- 训练器：数据目录 = 那个 `c3rlogs`；**车名必须填 `BYD_SONG_PRO_DMI_24`**；先用它跑通「rlogs → CSV → 模型 JSON」链路，再搬其余 24 条 route（约 8 GB）重训
## 13. 续搬其余 24 条 route（2026-09-27 23:54 开始）
- 脚本 `c3rlogs-rest.sh`（日志同名 .log）：分块 tar 每块 40 段 + 块级断点 `c3rlogs-chunks.done` + 每块最多重试 5 次 ✓
- 待搬 **850 段**（1128 − 今天那条 278）；实测约 2 MB/s → 估计 **1 小时左右**
- ⚠ **同一个"尾斜杠"坑第三次踩**：`ls -d dir/` 的输出带尾斜杠 → ① `${d##*/}` 取空 ② `sed 's|.*/||'` 也会取空 ✗
  → 正确写法：`ls -d */ | sed 's|/$||'`（先剥尾斜杠），且清单为空时直接报错退出（别再"跑完却啥也没搬"）
## 14. 第一版自训 NNLC 模型：已训练 + 已校验 + 已部署（2026-09-28 00:0x）【实测】

### 训练结果（用户电脑跑的一键流程；日志：`/sdcard/Download/nnlc/训练日志.txt`）
- 数据：`X:\nnlc\c3rlogs` 里 **278 个 rlog**（就是今天那条 route 00000018）；CSV **773,219 行**（530 MB，已拷到平板 `nnlc/training_input/BYD_SONG_PRO_DMI_24.csv`）
- 训练：**750 epoch 早停**（15 次无改善），最终 Loss **0.005526**，**Test loss (MSE) 0.006860**（阈值 < 0.05 → 合格）
- 结构：**18 → 7 → 13 → 3 → 1**（4 层）；模型 **4,575 B**；总耗时 758.9 s
- 产出（电脑）：`X:\nnlc\训练结果\BYD_SONG_PRO_DMI_24.json`；（平板副本）`nnlc/training_input/training_results/BYD_SONG_PRO_DMI_24/`（含 json/bson/训练曲线 png+pdf/log）

### 上线前校验（在 C3 上跑，只读）
1. 用 **C3 自己的 `NNTorqueModel` 加载** ✓：input_size=18 / output_size=1 / mean·std 各 18 / 4 层 activation `[σ, σ, identity, identity]`（σ 会被 loader 映射成 sigmoid ✓）
2. **`friction_override = False`** ✓（不会额外叠加摩擦补偿）
3. **输入顺序与 C3 上 `nnlc.py` 的 `nn_input` 逐项一致** ✓
   `nnlc.py`：`[vEgo, _desired_lateral_accel, friction_input, roll] + past_lateral_accels_desired(3) + future_planned_lateral_accels(4) + past_rolls(3) + future_rolls(4)`
   模型 `input_vars`：`v_ego, desired_lateral_accel, friction_input, roll, desired_lateral_accel_tm03/tm02/tm01, _tp03/tp06/tp10/tp15, roll_tm03/tm02/tm01, roll_tp03/tp06/tp10/tp15` ✓
4. **已部署**到 `/data/openpilot/sunnypilot/neural_network_data/neural_network_lateral_control/BYD_SONG_PRO_DMI_24.json` ✓
5. 用设备自己的 `get_nn_model_path` 复核：**`resolved = BYD_SONG_PRO_DMI_24`、`exact_match=True`、非 MOCK** ✓（不会再退化成索纳塔模型）

### 还差最后一步（需用户点头）
- 打开开关：`NeuralNetworkLateralControl=1`（写活库 `d_sp`）→ 重启 controlsd → 复查 `CarParamsSP.nnlc.model.name`
- **停车时做**；回滚 = 写回 0 + 重启 controlsd（原值 0 已记录）
- 这版只用今天一条 route 训练（覆盖窄）→ 先当"链路验证版"；全量 route 搬完再重训"正式版"
## 15. 第1版 vs 第2版 模型对比（2026-09-28 06:39 第2次训练完成）【实测】

| 项 | 第1次（只有今天那条） | 第2次（全量 1127 段） |
|---|---|---|
| 过滤后训练行数 | 749,337 | **2,513,759**（3.36×） |
| 结构 | 7x18→13x7→3x13→1x3 | 同 |
| epoch | 750（早停） | 750（早停） |
| 训练集最终 Loss | 0.005526 | 0.010207（数据多且难，正常） |
| **Test loss (MSE)** | 0.006860 | **0.004755（↓30.7%）** ✓ |
| 模型 JSON | 4,575 B | 4,553 B |
| **friction_override** | False | **True** ⚠（loader 自动置位 → 运行时额外叠加摩擦补偿） |
| 输入顺序 | 一致 ✓ | 一致 ✓ |

- 目录：第1次 `nnlc/training_input/training_results/BYD_SONG_PRO_DMI_24/` · 第2次 `nnlc/第二次/BYD_SONG_PRO_DMI_24/`（含 json/bson/`_log.txt`/`.training.png`/`-a.png`/`-b.png`+pdf）
- 我在 C3 上用 `NNTorqueModel` 加载第2版 ✓，并用**节点手写前向**与 C3 的 `evaluate` 交叉验证：同一输入都给 **0.6695** ✓
- 同输入扫描（vEgo=15、稳态转弯）：第2版前馈力矩整体**低 10–35%**（0.5 m/s²: 0.309→0.195；1.5: 0.830→0.670；3.0: 1.158→1.057）→ 主观会**偏软**，靠 PID 补
- 结论：第2版是正式版候选（泛化更好）；上线前只需把第1版备份、把第2版放进模型目录
## 16. 已换上第2版模型（2026-09-28 22:56）【实测】
- 现装：`BYD_SONG_PRO_DMI_24.json`（4,553 B，`model_test_loss=0.004754955`，date `2026-09-28_06-39-12`）= **第2版** ✓
- 备份：`/data/openpilot/.dsh/nnlc-staging/BYD_SONG_PRO_DMI_24.v1-live.json.bak`（4,575 B，第1版）
- 四道校验全过：`NNTorqueModel` 加载 ✓ · `friction_override=True`（第2版特征）✓ · 输入顺序一致 ✓ · `get_nn_model_path` → `BYD_SONG_PRO_DMI_24` / `exact_match=True` / 非 MOCK ✓
- 模型目录 115 个 json = 114 原厂 + BYD ✓；开关 `NeuralNetworkLateralControl=1` ✓
- 当时车辆状态：`IsOnroad=0 / IsOffroad=1`（只有 `./ui` 在跑）→ **下次通电自动加载第2版**，无需重启 controlsd
- 回滚：`cp .../nnlc-staging/BYD_SONG_PRO_DMI_24.v1-live.json.bak <模型目录>/BYD_SONG_PRO_DMI_24.json`；临时关闭：参数写 0；两者都需重启 controlsd（或断电重启）
- 试车关注：① 第2版前馈比第1版低 10–35% → 可能偏软 ② 第2版多了摩擦补偿（friction_override=True）→ 低速小误差时更实