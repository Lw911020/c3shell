# C3 控制台（Android WebView 壳）

> **原始版（基线）= v2.48** ✓（2026-09-22 用户指定）：工作树就是 2.48 基线，原件另存
> `releases/c3shell-2.48-原始版.apk`；重建/校验/回滚见 `BASELINE.md`。

把设备上的 `dsh-ssh-connector` 独立服务装进一个可安装的 APP。

| 页签 | 地址 | 内容 |
|---|---|---|
| SSH 控制台 | `http://<host>:3081/` | xterm 终端 + SSH 会话（token 由服务端注入） |
| 转向诊断 | `http://<host>:3081/diag` | 调试窗口：转向/控制诊断 |

顶栏：`SSH 控制台` / `转向诊断` / `重载` / `设置`（主机+端口，记住到 SharedPreferences）/ `DSH`（拉起 DSH 应用）。

服务没在跑时不白屏，会显示一页带原因和启动命令的错误页。

## 构建

复用已有的通用构建器（javac → d8 → aapt2 link → 注入 dex → apksigner v1+v2+v3）：

```sh
python3 /storage/emulated/0/niw/apks/build_apk.py \
  /storage/emulated/0/openpilot/c3shell \
  /storage/emulated/0/openpilot/c3shell/c3shell.apk
```

> 注意：工具链 `~/.apktc` 必须按脚本方式单条命令注入 `LD_LIBRARY_PATH`，
> 直接跑 `java` 会报 `libandroid-shmem.so not found`。

## 安装

```sh
adb install -r /storage/emulated/0/openpilot/c3shell/c3shell.apk
```

包名 `com.padagent.c3shell`，minSdk 21 / target 34，cleartext 已放行（`usesCleartextTraffic`）。

## 依赖

连接器要先起来：

```sh
cd /storage/emulated/0/openpilot/dsh-ssh-connector
bash bin/restart-connector.sh      # 或 node bin/serve.mjs
```

## 源码

- `AndroidManifest.xml`
- `java/com/padagent/c3shell/MainActivity.java`（纯代码建 UI，无 res/）

## 实机安装记录（2026-09-20 20:02，MIUI）

无线调试：`adb connect 127.0.0.1:40725`（端口从 `127.0.0.1`/局域网 IP 扫描 `30000-49999` 得到；
本机 `/proc/net/tcp` 不可读、这个 adb build 的 `mdns:services` 不可用，所以只能扫端口）。

`adb install -r` 会被 MIUI 拦：`INSTALL_FAILED_USER_RESTRICTED: Install canceled by user`
（**增强防护**），必须走系统安装器：

```sh
adb push c3shell.apk /sdcard/Download/c3shell.apk
adb shell am start -a android.intent.action.VIEW -d file:///sdcard/Download/c3shell.apk \
  -t application/vnd.android.package-archive
# 1) ICP 备案提示 → 点「继续安装」
# 2) 增强防护提示 → 点右上角「⋮ → 单次安装授权」
# 3) 完成后重试 adb install -r 即可（授权已被记住）
```

⚠️ 那个页面上的「安装」大按钮在 y≈1153 处**是广告位**（红果免费短剧），别点错——
认准右上角 ⋮ 的单次授权，或安装完成后用 `pm list packages | grep c3shell` 核对。

实测结果：`com.padagent.c3shell` 装上并启动，两个页签都渲染，
SSH 控制台实连成功（`comma@comma-c5f64914:/data/openpilot$`）。截图见 `screenshots/`。

## 独立版（方案 C）：运行独立，**开发维护仍在平板**

目标与边界（2026-09-21 用户确认）：

- **运行时独立**：APK 自带 HTTP 服务 + JSch SSH + 内置页面，装到手机后不依赖平板、不需要 node/连接器/ssh 二进制。
- **开发与维护仍在平板**：源码、构建、发布、密钥与配置的"出厂预置"都在平板这台 DSH 工作区里做；
  手机只负责"安装 + 使用"，不改代码。

### 目录与命令

| 项 | 位置/命令 |
|---|---|
| 源码 | `/storage/emulated/0/openpilot/c3shell/`（`java/` `assets/` `AndroidManifest.xml`） |
| 一键构建发布 | `bash /storage/emulated/0/openpilot/c3shell/build.sh`（加版本号则先改版本：`bash build.sh 1.6`） |
| 产物 | `c3shell/releases/c3shell-<版本>.apk`，同时复制到平板 `/sdcard/Download/c3shell-<版本>.apk` |
| 构建器 | `/storage/emulated/0/niw/apks/build_apk.py`（javac→d8→aapt2→apksigner；已支持 `libs/*.jar` 与 `assets/`） |
| 依赖 | `libs/android.jar`（编译桩）、`libs/jsch.jar`（纯 Java SSH） |
| 远端工具 | `assets/remote/dsh_remote.py`（ls/read/write）、`assets/remote/params_dump.py`（参数 list/set），首次使用时由 APP 用 SFTP 自动推到设备 `/data/openpilot/.dsh/` |

### 更新一次的标准流程（全在平板上）

1. 改 `c3shell/` 下的源码或 `assets/`
2. `bash c3shell/build.sh <新版本号>`
3. 把 `/sdcard/Download/c3shell-<版本>.apk` 拷到手机安装（或用 adb 装到任意已连接设备）
4. （可选）我这边用 adb 直接在平板上装机自测：`adb install -r` + 查 `logcat -s C3ShellWeb`

### 已经跑通的能力（独立版）

`/api/ssh/state|hosts|key/named`（APP 本地存储）、`test|exec`、`term/open|input|stream`(SSE)、
`ls|read|write`、`params/all|set|apply` —— 均已实机验证（见上文各轮记录）。

## 独立版验收记录（2026-09-21 · 方案 C 收尾）

**正式版**：`releases/c3shell-1.7.apk`（365,642 字节）· 平板下载目录 `/sdcard/Download/c3shell-1.7.apk`

### 四片全部实机验证（平板连接器**停着**、纯 APP 自持）

| 片 | 验证方式 | 结果 |
|---|---|---|
| ① 内置服务 + 页面托管 | APP 自己 3081 托管；WebView 请求日志 | `/`200 `/diag`200；`__API__/__TOKEN__` 已替换 |
| ② SSH 连接/exec/终端 | JSch 直连 C3 设备 | 延迟 548ms；`APP_独立版_OK`；终端收到真实 shell 横幅（SSE） |
| ③ 文件/参数 | SFTP 自动推远端工具后执行 | 文件 77 项；参数 值279/说明209/默认238/分类207；写→读→还原 |
| ④ 采样/诊断 | 长连接 + SSE 具名事件 | 回放样本 39 字段、meta 含车型指纹；routes 80 条 18.1GB |
| 附加 | 辅助驾驶监听 / 本地语音 / 更新包 / AI 分析 | running=true；TTS 实测出声；更新包退出码0；本地规则 11 项偏离 |

### 冒烟门禁（v1.7）
```
embedded server on 127.0.0.1:3081 · 语音就绪 · 崩溃 0 条
/ /diag /api/ssh/{state,pkg,ai/config,voice/cues} 全 200
```

### 待用户侧确认
手机安装验收（清单：`ACCEPTANCE.md`，16 项）——APK 已生成，需在手机上装一次。
