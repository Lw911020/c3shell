## 1. Java 原生层（界面外壳 + 服务端 + SSH）

| 文件 | 行数 | 关键成员（行号）|
|---|---|---|
| Ai.java | 84 | Ai()@17, p()@19, cfgJson()@21, chat()@29 |
| Api.java | 403 | Api()@16, q()@19, ov()@22, ov()@24, nz()@31, shqPair()@32, jstr()@35, jint()@63, sendToTerm()@74, qint()@86, q()@91, handle()@96 |
| Cues.java | 36 | Cues()@12, def()@14, get()@19, set()@24, json()@26 |
| Errs.java | 22 | zh()@5 |
| Logs.java | 74 | init()@22, add()@24, dump()@49, clear()@68, CTX@20 |
| MainActivity.java | 999 | onCreate()@70, shouldOverrideUrlLoading()@147, onPageFinished()@167, onReceivedError()@172, onKey()@208, onEditorAction()@217, onClick()@236, onClick()@249, buildBar()@317, onClick()@329, onClick()@332, onClick()@335, chromeLight()@342, tintText()@347 … |
| Pkg.java | 77 | Pkg()@16, p()@18, dir()@20, safe()@21, json()@31, save()@48, delete()@60, read()@64 |
| Sec.java | 86 | key()@16, ks()@28, xcrypt()@47, be32()@54 |
| SpeechService.java | 582 | nudge()@40, setRatePitch()@51, voicesOf()@67, findVoice()@71, vName()@76, vLocale()@77, vInt()@78, call()@79, applyVoice()@82, currentVoiceName()@89, voicesJson()@95, stream()@116, setStream()@121, params()@127 … |
| Ssh.java | 795 | Ssh()@29, host()@33, port()@34, user()@35, p()@36, resolveKey()@41, stateJson()@73, testJson()@82, execJson()@112, openTermJson()@165, lastTermId()@202, setLastTerm()@203, sendToTerm()@206, termTail()@246 … |
| Stats.java | 97 | url()@18, enabled()@23, deviceId()@27, setUrl()@36, setEnabled()@40, beat()@47, start()@75, run()@79, ver()@91 |
| Store.java | 212 | Store()@20, p()@22, parse()@30, hosts()@44, saveHosts()@60, hostById()@66, defaultHost()@73, upsertHost()@80, deleteHost()@89, setDefault()@95, hostsJson()@97, keysDir()@116, ASSET_OF()@126, ensurePresetKeys()@132 … |
| Voice.java | 57 | say()@17, nextJson()@28, stateJson()@41, id@10 |
| Web.java | 191 | Web()@33, stop()@47, loop()@52, handle()@65, readAsset()@149, ctype()@161, ss@29, api@31, port@32 |

## 2. 网页层：page.html 结构（每个 `<style>`/`<script>` 块的位置与用途）

| 行号 | 类型 | 内容摘要 |
|---|---|---|
| 8 | script | <script>/* 第一帧消闪（2026-09-22）：在 load 之前同步设主题，避免"先黑后白" ✗ */ |
| 12 | script | <script>/* CLEAR-CARD-ORDER（2026-09-22）：清掉历史保存的卡片顺序 → 卡片位置固定 ✓ */ |
| 16 | style 开始 | <style> |
| 526 | style 开始 | <style id="diagCss"> |
| 691 | ★诊断容器 | <div id="diagHost" style="display:none"> |
| 726 | ★诊断页签 | 调试图表 |
| 727 | ★诊断页签 | 横向诊断 |
| 728 | ★诊断页签 | 参数 |
| 729 | ★诊断页签 | 设备/日志 |
| 800 | script | <script src="app/log.js"></script> |
| 801 | script | <script src="app/viewrouter.js"></script> |
| 802 | script | <script src="app/store.js"></script> |
| 803 | script | <script src="app/displaymode.js"></script> |
| 804 | script | <script src="app/base.js"></script> |
| 805 | script | <script> |
| 819 | script | <script> |
| 821 | script | if (!window.__TERM_PLAIN) { document.write('<script src="__VENDOR__/xterm.js"><\ |
| 823 | script | <script src="__VENDOR__/addon-fit.js"></script> |
| 824 | script | <script> |
| 1739 | script | <script src="/theme.js"></script> |
| 1740 | script | <script> |
| 1797 | script | <script src="app/ai.js"></script> |
| 1798 | script | <script> |
| 1846 | script | <script> |
| 1860 | script | <script> |
| 1899 | script | <script> |
| 1910 | script | <script> |
| 1956 | script | <script> |
| 1987 | script | <script> |
| 2003 | script | <script> |
| 2017 | script | <script> |
| 2021 | script | <script> |
| 2044 | script | <script> |
| 2076 | script | <script> |
| 2088 | script | <script src="app/termstatobserver.js"></script> |
| 2089 | script | <script> |
| 2136 | script | <script src="app/nav.js"></script> |
| 2137 | script | <script src="app/menu.js"></script> |
| 2138 | script | <script src="app/sideeditor.js"></script> |
| 2139 | script | <script src="app/fsfilterhook.js"></script> |
| 2140 | script | <script src="app/opsmovecards.js"></script> |
| 2141 | script | <script src="app/voicepush.js"></script> |
| 2142 | script | <script src="app/ai2.js"></script> |
| 2143 | script | <script src="app/statsinfo.js"></script> |
| 2144 | script | <script src="app/themerow.js"></script> |
| 2145 | style 开始 | <style> |
| 2150 | style 开始 | <style> |
| 2159 | style 开始 | <style> |
| 2165 | style 开始 | <style> |

## 3. 公共 JS 模块（assets/app/*.js）

| 模块 | 字节 | 首行注释（职责）| 全局入口 |
|---|---|---|---|
| ai.js | 4314 | AI 分析 —— 2026-09-22 整块重写（不再补丁 ✗）    职责：①扫描（本地规则）：拉取全部参数，列出与厂商默认不同的项 ②问 |  |
| ai2.js | 9459 | AI 分析（2026-09-22 **整块重写**：旧子菜单已删除 ✗，本模块自包含 ✓）    自建页签 + 自建面板 + 自接管点击（不 |  |
| base.js | 1627 | 公共层 base.js（2026-09-21 重构 A+B 第 2 步）    从 page.html 原样提取的共享工具函数；**仅在未定 |  |
| cache.js | 2919 | 公共层：只读缓存 + 加载提示（2026-09-21 重构 A+B 第 3 步）——原先只内联在 diag.html ✗ */ /* bus |  |
| diagpage.js | 57398 | 公共层模块：诊断页逻辑（2026-09-21 重构 A1b 第 1 步）    原为 diag.html 内 4 个内联 <script>  | __lazyLoad, onerror |
| dialog.js | 1501 | 公共层：确认弹窗 askConfirm（2026-09-21 重构 A+B）——原先两页各一份且 id 冲突(cfMsg/cfNo/cfYe | askConfirm |
| displaymode.js | 10865 | 公共层：显式显示模式（2026-09-21 还债 A4）    auto 在**客户端解析**成具体模式（car/tablet）→ CSS  | __TERM_PLAIN, __setUserMode |
| fsfilterhook.js | 1135 | 公共层模块：fsFilterHook（2026-09-21 重构 A3 —— 原为 page/diag 里的"追加式内联块" ✗） */ / |  |
| log.js | 856 | 公共层：统一错误记录（还债 B8，2026-09-21）    目标：任何被吞掉的异常都留下痕迹 → 便于"读日志"定位；热路径用限流避免刷 | cerr, cerrRl |
| menu.js | 9515 | 两级菜单（2026-09-21 重构 A2b + ③）：结构由 window.NAV 驱动 ✓    - 一级项固定来自配置（永不消失 ✓  | __menuRebuild |
| nav.js | 1000 | 导航配置（2026-09-21 重构 ③）：菜单结构的**唯一来源** ✓    - takesChildren：该一级项把"当前视图的页签 | NAV |
| opsmovecards.js | 2223 | 公共层模块：moveOpsCards（2026-09-21 重构 A3 收编） */ /* moveOpsCards（2026-09-21  |  |
| sideeditor.js | 4096 | 公共层模块：sideEditor（2026-09-21 重构 A3 收编） */ /* sideEditor v2（2026-09-21）： | __sePath |
| statsinfo.js | 2049 | B11（2026-09-21）：设置页显示"使用统计"状态并允许开关 —— 状态透明、由用户决定是否填后端 ✓ */ (function() |  |
| store.js | 1370 | 统一数据层客户端（2026-09-21 重构 ④）：一处读全部状态、一处合并写。    用法：Store.get() → {version, | Store |
| termstatobserver.js | 836 | 公共层模块：termStatObserver（2026-09-21 重构 A3 —— 原为 page/diag 里的"追加式内联块" ✗）  |  |
| themerow.js | 1981 | 经典主题入口（2026-09-21 用户要求）：设置→界面卡片里直接切「深色 / 白底」✓ */ (function(){   var NA |  |
| viewrouter.js | 2062 | 视图路由（2026-09-21 A1b 第 3 步）：单一文档内的 console / diag 视图切换    - /diag → 显示  | __diagLoaded |
| voicepush.js | 1583 | B9（2026-09-21）：语音包"生成并推送到车机"按钮（设置→语音卡片内） */ (function(){   function ui |  |

## 4. 生效路径（★这是"改了却没效果"的根因区）

| 我改的东西 | 实际生效链路 | 必须做什么才生效 |
|---|---|---|
| `assets/page.html`（含所有内联 `<style>`/`<script>`） | 构建时被 `Sec` **RC4 加密**成 `page.html.enc` 打进 APK → APP 运行时**解密**后交给 WebView | ①重新 build ②install ③**重启 APP**（WebView 缓存；已加 `Cache-Control: no-store` ✓） |
| `assets/theme.css` | 同上（加密进 APK）→ 页面用 `<link href="/theme.css">` 引用 | 同上（注意：**改了 theme.css 必须重新 build**，改源文件立刻看网页是看不到的 ✗） |
| `assets/app/*.js` | 同上（加密）→ 由 page.html 的 `<script src="app/xx.js">` 引入 | 同上 |
| `java/**/*.java` | javac → d8 → classes.dex → 打进 APK | ①重新 build ②install ③重启 APP |
| **原生控件**（顶栏/工具条/终端底部输入条/状态栏） | 由 `MainActivity.java` **代码创建** ✗**不在网页里** | 改 Java → build → install → 重启；**网页 CSS/JS 永远改不到它们** ✗ |
| **页面内元素**（侧栏/页签/面板/卡片/图表） | 由 `page.html` + `assets/app/*.js` 渲染 ✓ | 改网页资源 → build → install → 重启 |
| 主题（深色/白底） | 网页：`html[data-theme]`（localStorage/prefs ✓）；原生外壳：`MainActivity.initChrome()` 读 `prefs.theme` | 切主题后**原生外壳需重启 APP**；网页即时 ✓ |

## 5. 界面归属对照（用户可见元素 → 代码位置）

| 用户看到的 | 归属 | 代码位置 |
|---|---|---|
| 窗口标题「C3 控制台」 | **原生** | `MainActivity.initChrome()`（ActionBar 上色 ✓） |
| 状态栏/导航栏颜色 | **原生** | `MainActivity.initChrome()`（setStatusBarColor ✓） |
| 左侧栏（两级菜单、版本号右下） | **网页** | `assets/app/menu.js`（结构来自 `nav.js` ✓；版本 `#sideVer` ✓） |
| 顶行（SSH 控制台/主机选择/测试连接/辅助驾驶） | **网页** | `page.html` 的 header 段 |
| 控制台 5 个页签（主机/终端/文件/实时/运维） | **网页** | `page.html` `nav.tabs` + `menu.js` 搬进侧栏 |
| 终端**输出** | **网页** | `#termWrap/#term/#termText` + `termstatobserver.js` |
| 终端**底部输入条**（输入/发送/TAB） | **原生** ★ | `MainActivity.java`（`termInput` + `bar2` + `发送` ✓ 行 ~188-240） |
| 诊断 5 面板（调试图表/横向诊断/参数/设备日志/AI 分析） | **网页** | `page.html` `#diagHost` 内 `.pane#p1..#p5` + `diagpage.js` |
| AI 分析卡片 | **网页** | `#p5 > #aiCard`（逻辑 `assets/app/ai.js`） |
| 采样条（C3 诊断台/测试/开始采样/hz/时间窗） | **网页** | `page.html` `#diagHost .row1` + `diagpage.js` 的 showPane 判定 |
| 图表 | **网页** | `diagpage.js` 绘图 + `theme.css` 的 `--chartbg/--y/--g/--o/--r` |
| 语音（提示词/音色/生成/推送） | **网页 + 原生服务** | `page.html` 设置区 + `SpeechService.java` |


## 6. 已知坑（我踩过的，别再犯）

1. **标签配平**：往 `page.html` 追加 `<style>`/`</style>` 极易造成未闭合 ✗ → 全页空白 ✗。**规矩**：一律加进 `theme.css` 或**已有** `<style>` 块内部 ✓，改完必须核对 `<style>/<script>/<div>` 三对计数 ✓。
2. **改错层**：原生控件的样式**不能**用网页 CSS 改 ✗（终端底部输入条就是例子 ✓）。
3. **不重启看不到**：改资源后必须 build→install→**重启 APP** ✓（WebView 会缓存；已加 `no-store` ✓）。
4. **变量名写错**：`showPane(id)` 里我误写 `p` ✗ → ReferenceError → 面板不显示 ✗。
5. **车机 dump 不稳**：`uiautomator dump` 在车机偶发空返回 ✗ → 验证**首选截图** ✓，dump 仅辅助 ✓。
6. **一级项文本带前缀**：侧栏一级项显示为 `▾ 转向诊断` ✓ → 点击脚本必须用**包含匹配** ✓。
7. **apply()/commit()**：`SharedPreferences` 用 `apply()` 会在强杀后丢失 ✗ → 一律 `commit()` ✓。


## 7. 目录总览

| 路径 | 说明 |
|---|---|
| `java/com/padagent/c3shell/` | 原生层（Activity/服务/HTTP 服务端/SSH/加密/日志/统计/语音） |
| `assets/page.html` | **唯一网页文档**（控制台 + 诊断两视图同一文档 ✓） |
| `assets/theme.css` | 主题与全部**追加样式**（唯一允许加 CSS 的地方 ✓） |
| `assets/app/*.js` | 公共 JS 层（每个模块单一职责） |
| `assets/vendor/xterm.js` | 终端渲染库（仅现代内核加载 ✓；车机用纯文本渲染器 ✓） |
| `test/syntax.py` | 语法检查（JS 模块 + 内联块） |
| `test/techdebt.py` | 22 条技术债判据 |
| `test/e2e.py` | 端到端断言（平板/车机） |
| `test/contrast.py` | 浅色主题对比度审计（WCAG） |
| `test/codemap.py` | **本文件生成器**（改完代码重跑即可刷新地图 ✓） |
| `releases/` `CHANGELOG.md` `TECHDEBT.md` `ACCEPTANCE.md` | 交付物与文档 |