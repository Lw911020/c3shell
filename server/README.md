# c3shell 后台（你自己的服务器）

## 1. 它对接的是什么
APP 里 `java/com/padagent/c3shell/Lic.java` 已经内建"一台服务器 + 兄弟端点"的约定：

| 用途 | 方法 | 路径（相对你填的端点） | 请求体 | 期望响应 |
|---|---|---|---|---|
| 激活/校验 | POST | 你填的那个 URL（看 `/verify`） | `{"code","device","version","app"}` | `{"ok":true,"plan":"1y","expiresAt":"2027-10-02 14:08:09"}` |
| 反馈 | POST | `/feedback` | `{"device","version","contact","text","logText","imageB64"}` | `{"ok":true}` |
| 赞赏登记 | POST | `/appreciate` | `{"device","version","amount","contact"}` | `{"ok":true}` |
| 心跳 | POST | `/heartbeat` | `{"device","feature","hostCount","mode"}` | `{"ok":true}` |
| 统计 | GET | `/stats` | — | `{"ok":true,"online":N,"devices":N,"today":N,...}` |

失败一律 `{"ok":false,"error":{"message":"给用户看的原因"}}`（APP 会把 message 直接显示）。  
端点是**自动推**的（`Lic.java:218 sibling()`）：在 APP「软件设置 → 激活 / 授权」里填
`https://qwen.jiangdl.icu/verify`，其余的 `/feedback`、`/appreciate`、`/stats` 会自动变成同主机同目录。

## 2. 部署（阿里云）
```bash
# 1) 放上去（backend.py 单文件，只依赖 python3 标准库）
scp backend.py root@你的服务器:/opt/c3shell/
ssh root@你的服务器
mkdir -p /opt/c3shell && cd /opt/c3shell

# 2) 起服务（8080 只监听本机，外面由 nginx 做 TLS）
python3 backend.py serve --port 8080 --db /opt/c3shell/backend.db --data /opt/c3shell/data --token <管理口令>

# 3) 发卡
python3 backend.py mint --plan 1y --days 365 --count 10 --db /opt/c3shell/backend.db
python3 backend.py list --db /opt/c3shell/backend.db
python3 backend.py bind --code C3-XXXX --device <设备ID>   # 换机解绑
```

systemd（推荐，进程挂了自动起）：
```ini
[Unit]
Description=c3shell backend
After=network.target
[Service]
WorkingDirectory=/opt/c3shell
ExecStart=/usr/bin/python3 /opt/c3shell/backend.py serve --port 8080 --db /opt/c3shell/backend.db --data /opt/c3shell/data --token <管理口令>
Restart=always
[Install]
WantedBy=multi-user.target
```

nginx 反代（**注意：若你站点前面有"访问验证"页面，必须把这些路径放行**）：
```nginx
server {
  listen 443 ssl;
  server_name qwen.jiangdl.icu;
  client_max_body_size 16m;          # 反馈带截图 base64，默认 1m 会 413
  location ~ ^/(verify|activate|feedback|appreciate|heartbeat|stats)$ {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_read_timeout 60s;
  }
  location /admin { proxy_pass http://127.0.0.1:8080; }   # 后台页：/admin?token=<口令>
  # 其它路径保持你原来的站点（Qwen 工作台等）
}
```

## 3. 后台页
浏览器打开 `https://qwen.jiangdl.icu/admin?token=<管理口令>`：在线/累计设备/今日活跃、卡密台账、绑定情况、反馈（含日志与截图文件路径）、赞赏台账，60 秒自动刷新。

## 4. 已经本机实测通过的项（2026-10）
- `/health`、`POST /verify`（有效卡→plan+expiresAt；坏卡→"卡密无效"；换设备→"已绑定其它设备"）、`POST /appreciate`、`POST /feedback`（日志落盘）、`GET /stats`、`/admin?token=`

## 5. 安全与兜底（重要）
- **离线签名卡优先**：APP 里 `activateSigned()` + `tools/license_mint.py` 可以不联网验证（车机经常没网）。在线卡密适合"换机/退款/统计"，两者可并存。
- APP 里的 `endpoint` 为空时走"本地记录"（不防破解）——正式上线要填上你的地址。
- 卡密支持 `max_devices`（默认 1 台），防一台卡到处传。
- `logText` 最大约 200 KB、截图 base64 可达数 MB：已限制单请求 12 MB，建议 nginx 也配 `limit_req` 防刷。

## 6. 只有域名、没有服务器？—— 用 Cloudflare Worker（0 元 / 免备案 / 自带 HTTPS）

`worker.js` 就是同一套接口的 Cloudflare Workers 版本（KV 存卡密/绑定/反馈/赞赏，含后台页与发卡接口）。
适合"只买了一个域名、不想租服务器"的情况。

1. Cloudflare 控制台 → **Workers & Pages → Create Worker**（名字如 `c3shell-api`）→ 把 `worker.js` 全文粘进去 → Deploy。
2. **Storage → KV → Create namespace**（如 `c3shell`）→ 回到 Worker 的 **Settings → Variables**：
   - KV Namespace 绑定：变量名 **`CARDS`** → 选刚建的命名空间；
   - 环境变量/密钥：**`TOKEN`** = 你的管理口令。
3. **Settings → Domains & Routes → Add custom domain**：`api.jiangdl.icu`（Cloudflare 自动签发证书，无需备案）。
   也可以用默认的 `https://c3shell-api.<你的账号>.workers.dev`。
4. APP「软件设置 → 激活 / 授权」里填：`https://api.jiangdl.icu/verify`（兄弟端点自动推出）。
5. 发卡：`curl -X POST "https://api.jiangdl.icu/mint?token=<管理口令>" -H "Content-Type: application/json" -d "{\"plan\":\"1y\",\"days\":365,\"count\":10}"`
6. 后台页：`https://api.jiangdl.icu/admin?token=<管理口令>`（卡密 / 绑定 / 设备心跳 / 反馈 / 赞赏）。

> ⚠️ **不要**把 Worker 挂到 `qwen.jiangdl.icu` 的根路径上——那个域名现在是你买/在用的 AI 面板（"Qwen 工作台"），
> 它的 `/verify`、`/stats` 被自己的验证页占着。请用**新子域**（如 `api.jiangdl.icu`）或 Worker 路由的 `/c3/*`。
> Worker 只看 URL 的最后一段，所以 `/c3/verify`、`/c3/feedback` 都能正常工作。
