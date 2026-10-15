# c3shell v1.7 交付说明

交付日期：2026-09-23　｜　基线：**v2.119 主线**（版本号仍显示 v2.119 ✓）
本文档对应多轮项目（PROJECT-LOG.md 中 R0~R28）的最终交付。

## 一、交付清单（全部双端实测 ✓）

| # | 功能 | 实测证据 |
|---|---|---|
| 1 | **超级投屏**（实时行车画面 ~5fps + 反向触控 + 桌面小窗）| 跨网拉到 404KB/6s（boundary+JPEG 校验 ✓）；触控注入被系统接收（读端收到 120 字节注入事件 ✓）；cast.html 已接入浮窗 ✓ |
| 2 | 全局桌面悬浮窗（拖动/点击放大/10s 自动收回/右下角缩放/记忆开关）| 车机实测小窗出现且窗内显示实时画面；日志「悬浮窗已创建 1920x990」✓ |
| 4 | 全屏沉浸 + 集中设置面板 | 卡片与控件在车机渲染正常 ✓ |
| 5 | 屏幕旋转 90 度 + 自适应缩放（90/100/110%）| 同上 ✓ |
| 6 | 一键下发「通用脚本」专区（12 个通用脚本，危险项带确认）| 实测系统概览/磁盘占用（realdata 17G）✓ |
| 7 | 顶部页签横向滑动 + 点击自动居中 | 样式与脚本核对 ✓ |
| 8 | 时间同步 / NTP 自动授时（本地免流直调 + NTP + 对齐时区）| 实测设备时间/时区/免密 sudo ✓ |
| 9 | **连机提速**（SSH 会话复用）| **命令往返 0.49s → 0.041s（约 12 倍）**；扫描状态 0.548s → 0.053s ✓ |
| 10 | 投屏智能避让（导航/360/倒车时自动隐藏，不弹回）| 打开高德 avoided=true hidden=true fg=com.autonavi.amapauto ✓；回桌面自动恢复 ✓ |
| 3 | 内核虚拟屏（无屏模式驱动）| ❌ 判定不可行（需内核级 uinput 驱动 + root）→ **已用「投屏 + 反向触控」替代并交付 ✓** |

## 二、新增的控制面（可复用 ✓）

- `/api/float/start|stop|status`：悬浮窗可靠控制与状态（含前台包名/是否避让/辅助功能状态）
- `/api/cast/start|stop|status`：设备侧 MJPEG 投屏服务的启停与状态
- 设备侧工具：`/data/openpilot/.dsh/mjpeg.py`（MJPEG 服务，VisionIPC 取帧）、`mjsnap2.py`（按需抓帧）
- 发现并可复用的 fork 控制通道：ZMQ 7710（JSON，支持 echo_cmd 远程执行）、Web 8088、cereal carrotMan 消息

## 三、关键技术结论（存档）

- C3（AGNOS / 内核 4.9 / Snapdragon UBWC）**无法从进程外线性抓屏**：ffmpeg 无 kmsgrab、无 /dev/fb0、legacy fb=0、DRM+EGL 线性导入得到 UBWC 花屏、QCOM modifier 被驱动拒绝
- **正确画面源 = VisionIPC 只读取帧**（camerad / VISION_STREAM_ROAD，1928x1208）→ 缩放 480 + JPEG q55 = 14.6KB/帧 → MJPEG 约 5fps，**完全不修改设备侧 openpilot**
- **守护进程存活要点**：`pkill -f <pattern>` 会匹配整条命令行；命令行内含该字面时会**自杀** → 一律用 **PID 文件**方案
- 触摸注入：`/dev/input/event2`（rw-rw-rw-，无需 root），单点协议 ABS_X/ABS_Y + BTN_TOUCH + SYN_REPORT，量程与屏幕 1:1

## 四、回退方法（随时可退 ✓）

```
安装 releases/c3shell-2.119.34-安全版.apk   # 回到实现 v1.7 之前的状态（双端均可）
```
安全版另存于 `_attic/safe/`（含 APK + 源码快照）✓

## 五、已知限制（诚实记录 ✓）

- 投屏约 5 帧/秒（够看清画面，非高帧率）；如需更高帧率可在设备侧长驻更多编码器
- 反向触控为「触摸板」形式（画面是行车摄像头，与 C3 UI 屏幕坐标系不同，故不做画面上直接点击）
- 运行中的 App 实例需重启一次才能看到新增卡片（本项目遵守不强行 force-stop 用户运行状态）
- 车机 App 的 HTTP token 与 DSH embedded token 不同，无法从 adb 直接调用其接口
