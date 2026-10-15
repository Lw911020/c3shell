# 把 c3shell 后台部署到 Cloudflare（两条路，任选一条）

你看到的报错 **「此上传程序暂不支持需要构建过程的项目…请改用 wrangler deploy」** 是因为走了 **Workers 的「上传」入口**：
那个入口只接受**已经打包好的产物**，看到单个 JS 源码就以为还需要构建。我们这个后台是**单文件、零依赖**，本来就不需要构建，
所以请走下面任意一条（都不用 npm、不用构建）。

## 路线 A：控制台「Edit code」（推荐，约 2 分钟）

1. 控制台 → **Workers & Pages → Create application → Create Worker** → 起名 `c3shell-api` → **Deploy**（先部署默认的 Hello World）。
2. 进入该 Worker → 右上 **Edit code**（旧界面叫 Quick edit，图标 `</>`）→ 编辑器里**全选删除** → 粘贴 `worker.js` 全文 → **Deploy**。
   - 若编辑器不接受模块语法（报 export default 之类），改用 **`worker-legacy.js`**：功能完全一样，只是服务线程旧格式，任何版本的控制台都吃。
3. **建 KV**：Storage & Databases → **KV** → Create namespace（如 `c3shell`）。
   回到 Worker → **Settings → Bindings（Variables and Secrets）**：
   - 加 **KV Namespace** 绑定：Variable name = `CARDS` → 选刚建的命名空间；
   - 加变量/密钥：`TOKEN` = 接口口令（`/mint` 用，同时是登录 Cookie 的签名密钥）、`ADMIN_USER` = 登录名（默认 admin）、`ADMIN_PASS` = 登录密码。
   改完**再 Deploy 一次**让绑定生效。
4. Worker → **Settings → Domains & Routes → Add → Custom domain**：`api.jiangdl.icu`（证书自动签发，**不需要备案**）。
5. APP「软件设置 → 激活 / 授权」填：`https://api.jiangdl.icu/verify`
6. 发卡与后台：
```bash
curl -X POST "https://api.jiangdl.icu/mint?token=<TOKEN>" -H "Content-Type: application/json" -d '{"plan":"1y","days":365,"count":10}'
# 后台页：浏览器打开  https://api.jiangdl.icu/admin?token=<TOKEN>
```

## 路线 B：wrangler（有电脑 + Node 时）

```bash
npm i -g wrangler
wrangler login
mkdir c3shell-api && cd c3shell-api      # 把 worker.js 与 wrangler.toml 放进来
wrangler kv namespace create CARDS       # 输出里记下 id，填进 wrangler.toml 的 kv_namespaces.id
wrangler secret put TOKEN                # 输入管理口令
wrangler deploy
```
部署后会给出 `https://c3shell-api.<账号>.workers.dev/verify`，需要自定义域名就在控制台 Add custom domain。

## 自检（三条命令）

```bash
curl -s https://api.jiangdl.icu/health
curl -s -X POST https://api.jiangdl.icu/verify -H "Content-Type: application/json" -d '{"code":"C3-NOPE","device":"TESTSN"}'
curl -s https://api.jiangdl.icu/stats
```
第 1 条应回 `{"ok":true,"service":"c3shell-worker",...}`；第 2 条应回 `{"ok":false,"error":{"message":"卡密无效"}}`（说明路由与 KV 都通了）。

## 常见坑

- **别挂到 `qwen.jiangdl.icu` 根路径**（那是你的 AI 面板，`/verify`、`/stats` 被它的验证页占着）；用新子域 `api.jiangdl.icu`。
  另：Worker 只看 URL **最后一段**，所以挂在 `/c3/verify`、`/c3/feedback` 下也照常工作。
- 加了 KV/变量后**忘了重新 Deploy** → `/verify` 会 500（CARDS 未定义）。
- 免费额度：KV 每天 10 万读取 / 1000 次写入，按你这个用量完全够。
- 想把卡密做成“离线签名卡”（不联网也能验），用 `tools/license_mint.py` + APP 里的 `activateSigned()`，两者可以并存。
