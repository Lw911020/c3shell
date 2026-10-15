# c3shell 架构与重构计划（A+B）

## 现状（2026-09-21 盘点）

```
APP（单进程）
├─ 原生外壳 MainActivity（ActionBar / 底部终端输入条 / 宽屏隐藏工具条）
├─ 进程内 HTTP 服务 Web.java（:3081，从 assets 解密下发）
│   ├─ page.html  控制台（主机/终端/文件/实时/运维/设置）   ← 独立文档
│   ├─ diag.html  转向诊断（调试图表/横向诊断/参数/设备日志）← 独立文档
│   ├─ theme.css / theme.js  共享样式与主题 ✓
│   └─ API：/api/ssh/*（Ssh.java→JSch）、/api/voice/*、/api/log、/term/*、/ls、/write…
└─ 数据：**无数据库**；filesDir/hosts.json · params-cache.json · app.log · SharedPreferences
```

**问题**：两个页面各自演化 → 跨页搬 UI 不可能（只能复制）✗；同一 bug 修两遍 ✗；
菜单/主题/请求缓存/文件列表等**重复实现** ✗。

## 目标（A+B）

```
assets/
  app/base.css      ← 公共样式（自 theme.css 拆出结构性部分）
  app/base.js       ← 公共层：api/get/post、toast、菜单(nestedMenu)、busyCache、el()、主题接口
  app/pages/console.html   ← 只留控制台内容
  app/pages/diag.html      ← 只留诊断内容（下一步：并入 console 成为页签）
Web.java 组装：base.css + base.js + 页面内容 → 一次下发（含 __APPVER__ 等模板变量）
```

- **A 合并为一个文档**：把 diag 的 4 个 pane 并进 console 作为页签（`#p1..#p4`）
- **B 抽公共层**：所有页面共用 `app/base.js`/`app/base.css`，页面文件只写自己的内容
- **C 数据层**：保持 JSON 文件（数据量不需要 DB），统一 `/api/store` 读写 + 内存缓存

## 实施步骤（每步：改一处 → 跑 test/e2e.py → 自测截图 → 通过再下一步；失败立即回退）

1. **建公共层骨架**：新增 `app/base.js`（先把两页**重复的函数**搬进来，页面内保留同名空壳，确保行为不变）
2. **切页面到公共层**：两页改为 `<script src="app/base.js">`，删掉各自重复实现；跑回归
3. **合并文档 A**：diag 的 pane 与脚本并入 console；`/diag` 路由改为"同文档 + 切页签"
4. **菜单统一**：nestedMenu 只保留一份；侧栏一级项与页面 pane 由同一份配置驱动
5. **数据层 C**：统一 `/api/store`（hosts/prefs/缓存），页面不再各自拼 JSON
6. **收尾**：`test/e2e.py` 增加"单文档 + 公共层"断言（两页不再有重复实现）

## 验证要点（每步必查）

- `test/e2e.py --build both`：21 项断言全绿
- 平板（无障碍）与车机（adb dump/tap）：菜单两级展开、来回切换、终端、参数分片、只读缓存
- 源码断言：`page.html`/`diag.html` **不再包含** nestedMenu/busyCache/api 的实现（只在 base.js 有）
