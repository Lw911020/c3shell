#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码地图生成器：扫描本项目，输出每个模块的职责/定位/生效路径。
用法：python3 test/codemap.py            # 打印摘要
      python3 test/codemap.py --full     # 同时写出 CODEMAP.md（完整版）"""
import os, re, sys, json
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p):
    try: return open(os.path.join(SRC,p),encoding='utf-8',errors='replace').read()
    except Exception: return ''
def lines(p): return rd(p).count('\n')+1
out=[]
def w(s=''): out.append(s)

# ── 1. Java 层：类/方法/关键字段（带行号）──
w('## 1. Java 原生层（界面外壳 + 服务端 + SSH）')
w('')
w('| 文件 | 行数 | 关键成员（行号）|')
w('|---|---|---|')
jdir='java/com/padagent/c3shell'
for f in sorted(os.listdir(os.path.join(SRC,jdir))):
    if not f.endswith('.java'): continue
    s=rd(os.path.join(jdir,f)); n=lines(os.path.join(jdir,f))
    syms=[]
    for m in re.finditer(r'^\s*(?:public|private|protected|static)[^\n{;=]*?(\w+)\s*\([^)]*\)\s*\{', s, re.M):
        ln=s[:m.start()].count('\n')+1
        syms.append('%s()@%d' % (m.group(1), ln))
    for m in re.finditer(r'^\s*(?:private|public|protected)\s+(?:static\s+)?[\w<>\[\].]+\s+(\w+)\s*;', s, re.M):
        ln=s[:m.start()].count('\n')+1
        syms.append('%s@%d' % (m.group(1), ln))
    w('| %s | %d | %s |' % (f, n, ', '.join(syms[:14]) + (' …' if len(syms)>14 else '')))
w('')

# ── 2. 网页层：page.html 的 style/script 块（带行号）──
w('## 2. 网页层：page.html 结构（每个 `<style>`/`<script>` 块的位置与用途）')
s=rd('assets/page.html'); L=s.split('\n')
w('')
w('| 行号 | 类型 | 内容摘要 |')
w('|---|---|---|')
for i,l in enumerate(L,1):
    if re.search(r'<style\b', l) or re.search(r'^<style', l.strip()):
        w('| %d | style 开始 | %s |' % (i, l.strip()[:70]))
    if '<script' in l:
        w('| %d | script | %s |' % (i, l.strip()[:80]))
    if 'id="diagHost"' in l: w('| %d | ★诊断容器 | %s |' % (i, l.strip()[:70]))
    if re.search(r'data-p="p\d"', l): w('| %d | ★诊断页签 | %s |' % (i, re.sub(r'<[^>]+>','',l).strip()[:40]))
    if 'id="aiCard"' in l: w('| %d | ★AI 卡片 | %s |' % (i, l.strip()[:60]))
w('')

# ── 3. JS 模块：职责与入口 ──
w('## 3. 公共 JS 模块（assets/app/*.js）')
w('')
w('| 模块 | 字节 | 首行注释（职责）| 全局入口 |')
w('|---|---|---|---|')
d='assets/app'
for f in sorted(os.listdir(os.path.join(SRC,d))):
    if not f.endswith('.js'): continue
    src=rd(os.path.join(d,f))
    first=''
    m=re.search(r'/\*(.{0,110})', src, re.S)
    if m: first=m.group(1).replace('\n',' ').strip()
    gs=re.findall(r'window\.(\w+)\s*=', src)
    w('| %s | %d | %s | %s |' % (f, os.path.getsize(os.path.join(SRC,d,f)), first[:70], ', '.join(sorted(set(gs))[:6])))
w('')

# ── 4. 生效路径（改了怎么才会生效）──
w('## 4. 生效路径（★这是"改了却没效果"的根因区）')
w('')
w('''| 我改的东西 | 实际生效链路 | 必须做什么才生效 |
|---|---|---|
| `assets/page.html`（含所有内联 `<style>`/`<script>`） | 构建时被 `Sec` **RC4 加密**成 `page.html.enc` 打进 APK → APP 运行时**解密**后交给 WebView | ①重新 build ②install ③**重启 APP**（WebView 缓存；已加 `Cache-Control: no-store` ✓） |
| `assets/theme.css` | 同上（加密进 APK）→ 页面用 `<link href="/theme.css">` 引用 | 同上（注意：**改了 theme.css 必须重新 build**，改源文件立刻看网页是看不到的 ✗） |
| `assets/app/*.js` | 同上（加密）→ 由 page.html 的 `<script src="app/xx.js">` 引入 | 同上 |
| `java/**/*.java` | javac → d8 → classes.dex → 打进 APK | ①重新 build ②install ③重启 APP |
| **原生控件**（顶栏/工具条/终端底部输入条/状态栏） | 由 `MainActivity.java` **代码创建** ✗**不在网页里** | 改 Java → build → install → 重启；**网页 CSS/JS 永远改不到它们** ✗ |
| **页面内元素**（侧栏/页签/面板/卡片/图表） | 由 `page.html` + `assets/app/*.js` 渲染 ✓ | 改网页资源 → build → install → 重启 |
| 主题（深色/白底） | 网页：`html[data-theme]`（localStorage/prefs ✓）；原生外壳：`MainActivity.initChrome()` 读 `prefs.theme` | 切主题后**原生外壳需重启 APP**；网页即时 ✓ |
''')

# ── 5. 界面归属对照（谁归原生、谁归网页）──
w('## 5. 界面归属对照（用户可见元素 → 代码位置）')
w('')
w('''| 用户看到的 | 归属 | 代码位置 |
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
''')
w('')
w('## 6. 已知坑（我踩过的，别再犯）')
w('''
1. **标签配平**：往 `page.html` 追加 `<style>`/`</style>` 极易造成未闭合 ✗ → 全页空白 ✗。**规矩**：一律加进 `theme.css` 或**已有** `<style>` 块内部 ✓，改完必须核对 `<style>/<script>/<div>` 三对计数 ✓。
2. **改错层**：原生控件的样式**不能**用网页 CSS 改 ✗（终端底部输入条就是例子 ✓）。
3. **不重启看不到**：改资源后必须 build→install→**重启 APP** ✓（WebView 会缓存；已加 `no-store` ✓）。
4. **变量名写错**：`showPane(id)` 里我误写 `p` ✗ → ReferenceError → 面板不显示 ✗。
5. **车机 dump 不稳**：`uiautomator dump` 在车机偶发空返回 ✗ → 验证**首选截图** ✓，dump 仅辅助 ✓。
6. **一级项文本带前缀**：侧栏一级项显示为 `▾ 转向诊断` ✓ → 点击脚本必须用**包含匹配** ✓。
7. **apply()/commit()**：`SharedPreferences` 用 `apply()` 会在强杀后丢失 ✗ → 一律 `commit()` ✓。
''')
w('')
w('## 7. 目录总览')
w('')
w('| 路径 | 说明 |')
w('|---|---|')
w('| `java/com/padagent/c3shell/` | 原生层（Activity/服务/HTTP 服务端/SSH/加密/日志/统计/语音） |')
w('| `assets/page.html` | **唯一网页文档**（控制台 + 诊断两视图同一文档 ✓） |')
w('| `assets/theme.css` | 主题与全部**追加样式**（唯一允许加 CSS 的地方 ✓） |')
w('| `assets/app/*.js` | 公共 JS 层（每个模块单一职责） |')
w('| `assets/vendor/xterm.js` | 终端渲染库（仅现代内核加载 ✓；车机用纯文本渲染器 ✓） |')
w('| `test/syntax.py` | 语法检查（JS 模块 + 内联块） |')
w('| `test/techdebt.py` | 22 条技术债判据 |')
w('| `test/e2e.py` | 端到端断言（平板/车机） |')
w('| `test/contrast.py` | 浅色主题对比度审计（WCAG） |')
w('| `test/codemap.py` | **本文件生成器**（改完代码重跑即可刷新地图 ✓） |')
w('| `releases/` `CHANGELOG.md` `TECHDEBT.md` `ACCEPTANCE.md` | 交付物与文档 |')

doc='\n'.join(out)
open(os.path.join(SRC,'CODEMAP.md'),'w',encoding='utf-8').write(doc)
print('  ✓ CODEMAP.md 已生成（%d 字符）' % len(doc))
print('  Java 文件 %d 个 · JS 模块 %d 个 · page.html %d 行' % (
  len([f for f in os.listdir(os.path.join(SRC,jdir)) if f.endswith('.java')]),
  len([f for f in os.listdir(os.path.join(SRC,d)) if f.endswith('.js')]), len(L)))
