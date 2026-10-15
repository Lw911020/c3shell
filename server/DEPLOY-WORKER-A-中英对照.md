# 路线 A：控制台 Edit code 部署（中英对照 / Bilingual）

> 不要走「上传 / Upload」入口——它只接受打包好的产物，会报 "此上传程序暂不支持需要构建过程的项目…请改用 wrangler deploy"。
> Do NOT use the "Upload" entry — it only accepts a pre-built bundle and shows "This upload tool does not yet support projects that require a build step… please use wrangler deploy".

## 一、逐步操作（Step by step）

| # | 中文操作 | English / 控制台原文按钮 |
|---|---|---|
| 1 | 打开 Cloudflare 控制台 → 左侧「Workers 和 Pages」→「创建应用程序」→「创建 Worker」→ 名字填 `c3shell-api` → 点「部署」 | Dashboard → **Workers & Pages** → **Create application** → **Create Worker** → name `c3shell-api` → **Deploy** |
| 2 | 进入刚建的 Worker → 右上角「编辑代码」(`</>`) → 编辑器里**全选删除** → 粘贴 `worker.js` 全文 → 点「部署」 | Open the Worker → **Edit code** (`</>`) → select all & delete → paste the whole `worker.js` → **Deploy** |
| 2b | 若编辑器不接受模块语法（报 `export default` 之类）→ 改粘贴 **`worker-legacy.js`**，功能完全一样 | If the editor rejects module syntax (complains about `export default`) → paste **`worker-legacy.js`** instead (identical features) |
| 3 | 左侧「存储和数据库」→「KV」→「创建命名空间」→ 名字随意（如 `c3shell`） | **Storage & Databases** → **KV** → **Create namespace** → any name (e.g. `c3shell`) |
| 4 | 回到 Worker →「设置」→「绑定」（变量和密钥）→「添加绑定」→ 选 **KV 命名空间** → 变量名填 `CARDS` → 选中刚建的空间 → 保存 | Worker → **Settings** → **Bindings** (Variables and Secrets) → **Add binding** → **KV namespace** → Variable name `CARDS` → pick the namespace → **Save** |
| 5 | 同一页「添加变量」→ 名称 `TOKEN` → 值 = 你的管理口令 → 类型建议选「密钥/加密」→ 保存 | Same page → **Add variable** → name `TOKEN` → value = your admin password → choose **Secret/Encrypt** → **Save** |
| 6 | **再点一次「部署」**（改了绑定/变量必须重新部署才生效） | Click **Deploy** once more (bindings/vars only apply after a new deploy) |
| 7 | 「设置」→「域和路由」→「添加」→「自定义域」→ 填 `api.jiangdl.icu` → 添加（证书自动签发，无需备案） | **Settings** → **Domains & Routes** → **Add** → **Custom domain** → `api.jiangdl.icu` → **Add domain** (cert auto-issued, no ICP filing needed) |
| 8 | APP 里：「软件设置」→「激活 / 授权」→ 填 `https://api.jiangdl.icu/verify` | In the APP: **Settings** → **Activation / License** → enter `https://api.jiangdl.icu/verify` |

## 二、发卡与看后台（Mint / Admin）

```bash
# 发 10 张一年期卡密 / issue 10 one-year cards
curl -X POST "https://api.jiangdl.icu/mint?token=<TOKEN>" -H "Content-Type: application/json" -d '{"plan":"1y","days":365,"count":10}'

# 后台页 / admin page
https://api.jiangdl.icu/admin?token=<TOKEN>
```

## 三、部署自检（Self-check，成了才说明路由 + KV 都通）

```bash
curl -s https://api.jiangdl.icu/health
curl -s -X POST https://api.jiangdl.icu/verify -H "Content-Type: application/json" -d '{"code":"C3-NOPE","device":"TESTSN"}'
curl -s https://api.jiangdl.icu/stats
```

| 命令 | 期望输出（中文含义） | Expected (English) |
|---|---|---|
| `/health` | `{"ok":true,"service":"c3shell-worker",...}` = 服务活着 | service is alive |
| `POST /verify` | `{"ok":false,"error":{"message":"卡密无效"}}` = 路由与 KV 都通了 | routing + KV both work |
| `/stats` | `{"ok":true,"online":0,...}` = 统计正常 | stats works |

## 四、按钮中英对照表（Console glossary）

| 中文 | English |
|---|---|
| 创建工作程序 / 创建应用程序 | Create application |
| 创建 Worker | Create Worker |
| 部署 | Deploy |
| 编辑代码 | Edit code |
| 快速编辑 | Quick edit |
| 存储和数据库 | Storage & Databases |
| KV 命名空间 | KV namespace |
| 设置 | Settings |
| 变量和密钥 / 绑定 | Variables and Secrets / Bindings |
| 添加绑定 | Add binding |
| 添加变量 | Add variable |
| 密钥（加密） | Secret (Encrypt) |
| 域和路由 | Domains & Routes |
| 自定义域 | Custom domain |
| 保存 / 保存并部署 | Save / Save and Deploy |
| 日志（实时） | Logs (Live) |

## 五、常见报错对照（Error → 处理）

| 报错原文 | 含义 / 处理 |
|---|---|
| 此上传程序暂不支持需要构建过程的项目…请改用 wrangler deploy | 你用了「上传」入口。改走本文件路线 A（Edit code），或用 wrangler |
| `CARDS is not defined` / 500 | KV 绑定没生效：加完绑定后**必须再 Deploy 一次** |
| `/admin` 返回「需要口令」 | 地址少了 `?token=` 或 TOKEN 没设 |
| 404 `no such path: xxx` | 路径最后一段不是 verify/feedback/appreciate/heartbeat/stats/admin/mint；注意 Worker 只看最后一段 |
| 浏览器打开域名是「Qwen 工作台 · 访问验证」 | 你打开的是 `qwen.jiangdl.icu`（你的 AI 面板）。后台要用 `api.jiangdl.icu` |
