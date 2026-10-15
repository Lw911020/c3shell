# （可选后端）直接粘给 CloudBase 控制台 AI 助手的指令 —— 整段复制

> ⚠️ **2026-09-25 起：卡密已经不需要后端了**（改成**离线签名卡密**，见 `LICENSE-MINT.md`）。
> 这份指令现在只用于**可选的**「在线统计 + 问题反馈 + 赞赏登记」。配不通也**不影响卖卡** ✓
> 若腾讯云这套还是配不通，可换：**YesApi 果创云**（国内、注册即用、建表就有 REST）或一台自己的便宜服务器。

请在我的**当前云开发环境**里搭好一套「APP 卡密授权 + 在线统计 + 问题反馈 + 赞赏登记」后端，
全部用云开发资源，做完把「HTTP 访问服务的基础地址」和两条自测结果告我。
APP 端已经按下面的约定写好了，**请严格照做，不要改字段名**（改了就对接不上）。

## 一、要创建的东西

1. **数据库**：我的环境是**云开发 RDS MySQL** → 建 4 张表（DDL 见 **3.1**），并插入一条测试卡密 `C3-TEST-0001`
   - 用 MySQL 就照 3.1 建（字符集 utf8mb4）；万一环境里只有文档型数据库，就用集合，**字段名保持一样**
   - 连接注意：云函数要**开启私有网络并选 MySQL 的 VPC/子网**，数据库地址用**内网地址**（不是公网地址）
2. **云函数**：Node.js 18，函数名 `c3-license`，一个函数按请求路径分发 5 个接口
   - 依赖：**MySQL 用 `mysql2`**（PostgreSQL 用 `pg`；文档型数据库用 `@cloudbase/node-sdk`）
   - 环境变量：`MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USERNAME` / `MYSQL_PASSWORD` / `MYSQL_DATABASE`
     （**不会自动注入，要手填**：MySQL 控制台「连接信息」里抄**内网**地址；也可只给一条 `MYSQL_URL=mysql://user:pass@host:3306/db`）
   - 网络：云函数「配置 → 网络」**开启私有网络**，选 MySQL 所在的 **VPC + 子网**（否则 TCP 直连不通）
3. **HTTP 访问服务**：把 `/verify`、`/heartbeat`、`/feedback`、`/appreciate`、`/stats` 五条路径都指向 `c3-license`
   - 免鉴权（APP 直连，不带登录态）
   - 顺带加一条 `/` → 同一函数，返回一个**简单统计网页**（可选，方便用浏览器看人数）
4. 完成后告诉我：**HTTP 访问服务的基础地址**（形如 `https://xxxx.service.tcloudbase.com`）

## 二、接口约定（APP 已按这个写好）

### POST /verify —— 卡密校验 + 一码一机绑定
请求：`{"code":"C3-TEST-0001","device":"C3-3499EFE1917B48BA","version":"3.00.17","app":"c3shell"}`

处理顺序：
1. 查卡密：`code` 匹配且 `enabled=true`
   - 查不到 → `{"ok":false,"error":{"message":"卡密无效"}}`
   - `expires_at` 非空且已过期 → `{"ok":false,"error":{"message":"卡密已过期"}}`
2. 设备绑定：
   - `device_id` 为空 → 写入 `device_id` 与 `bind_at=NOW()`（首次绑定，成功）
   - `device_id` 等于请求的 device → 成功（同一台机器重复激活要成功，不要报错）
   - `device_id` 是别的设备 → `{"ok":false,"error":{"message":"卡密已绑定其它设备（如需换机请在后台解绑）"}}`
3. 成功统一返回：
   `{"ok":true,"plan":"pro","expiresAt":"2027-01-01","features":["ai","routes","feedback"]}`
   - `expiresAt` 没有有效期就返回空串 `""`
   - `features` 按卡密里的 `features` 字段（逗号分隔）拆成数组

### POST /heartbeat —— 在线心跳（统计人数用）
请求：`{"device":"C3-…","version":"3.00.17","os":"Android 13","model":"Xiaomi Pad","mode":"tablet","hosts":2,"feature":""}`
处理：插入 `app_heartbeat` 一行 → 返回 `{"ok":true}`

### POST /feedback —— 问题反馈（带日志和截图）
请求：`{"device":"C3-…","version":"3.00.17","contact":"","text":"用户描述","imageB64":"data:image/jpeg;base64,…","logText":"最近日志"}`
处理：插入 `app_feedback` 一行：
- `text` 截 8000 字符、`logText` 截 200000 字符
- 截图二选一必须落库：**能存云存储**就把 fileID 写进 `image_url`；不方便就直接把 base64 存进 `image_b64`（截 1500000 字符）
- 返回 `{"ok":true}`

### POST /appreciate —— 赞赏登记（APP 赞赏页用户自己回填）
请求：`{"device":"C3-…","version":"3.00.40","amount":"50","contact":""}`
处理：
- `amount` 转成数字，**必须大于 20**，否则返回 `{"ok":false,"error":{"message":"赞赏金额需大于 20"}}`
- 通过则插入 `app_appreciate` 一行 → 返回 `{"ok":true,"amount":50}`

### GET /stats —— 后台看数（浏览器和 APP 都会调）
返回：
```
{"ok":true,
 "online5m": 5 分钟内出现过的去重 device 数,
 "online30m": 30 分钟内去重 device 数,
 "dau": 今天（设备本地时区按 UTC+8 算）出现过的去重 device 数,
 "devices": app_heartbeat 里去重 device 总数,
 "licenseBound": app_license 里 device_id 非空的行数,
 "licenseTotal": app_license 总行数,
 "feedbackOpen": app_feedback 里 handled=false 的行数,
 "appreciateOpen": app_appreciate 里 handled=false 的行数,
 "versions": [{"v":"3.00.17","c":设备数}],
 "features": [{"f":"功能名","c":次数}]}
```

## 三、DDL 与初始数据

### 3.1 RDS MySQL（★ 我的环境是这种，先做这个）

```sql
-- 4 张表：卡密 / 心跳 / 反馈 / 赞赏；字符集统一 utf8mb4（中文和 emoji 都不会乱码）

CREATE TABLE IF NOT EXISTS app_license (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  plan VARCHAR(32) DEFAULT 'pro',
  features VARCHAR(255) DEFAULT 'ai,routes,feedback',
  device_id VARCHAR(64) NULL,
  bind_at DATETIME NULL,
  expires_at DATETIME NULL,
  enabled TINYINT(1) DEFAULT 1,
  note VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_heartbeat (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NOT NULL,
  app_version VARCHAR(32) NULL,
  os_version VARCHAR(32) NULL,
  model VARCHAR(64) NULL,
  display_mode VARCHAR(16) NULL,
  host_count INT DEFAULT 0,
  feature VARCHAR(64) NULL,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_hb_dev (device_id),
  KEY idx_hb_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_feedback (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NULL,
  app_version VARCHAR(32) NULL,
  contact VARCHAR(128) NULL,
  text TEXT NULL,
  image_url VARCHAR(255) NULL,
  image_b64 MEDIUMTEXT NULL,
  log_text MEDIUMTEXT NULL,
  handled TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_appreciate (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NULL,
  app_version VARCHAR(32) NULL,
  amount DECIMAL(10,2) NULL,
  contact VARCHAR(128) NULL,
  handled TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 一条测试卡密（已存在则跳过）
INSERT INTO app_license(code, plan, features, enabled, note) VALUES ('C3-TEST-0001', 'pro', 'ai,routes,feedback', 1, '测试')
  ON DUPLICATE KEY UPDATE code = code;

-- 自检：应看到 4 张表
SHOW TABLES LIKE 'app_%';
SELECT code, plan, device_id, enabled FROM app_license;```

### 3.2 PostgreSQL（环境里是 PG 才用）

```sql
CREATE TABLE IF NOT EXISTS app_license (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(64) UNIQUE NOT NULL,
  plan VARCHAR(32) DEFAULT 'pro',
  features VARCHAR(255) DEFAULT 'ai,routes,feedback',
  device_id VARCHAR(64), bind_at TIMESTAMP, expires_at TIMESTAMP,
  enabled BOOLEAN DEFAULT TRUE, note VARCHAR(255) DEFAULT '',
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS app_heartbeat (
  id BIGSERIAL PRIMARY KEY,
  device_id VARCHAR(64) NOT NULL, app_version VARCHAR(32), os_version VARCHAR(32),
  model VARCHAR(64), display_mode VARCHAR(16), host_count INT DEFAULT 0,
  feature VARCHAR(64), ts TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hb_dev ON app_heartbeat(device_id);
CREATE INDEX IF NOT EXISTS idx_hb_ts  ON app_heartbeat(ts);
CREATE TABLE IF NOT EXISTS app_feedback (
  id BIGSERIAL PRIMARY KEY,
  device_id VARCHAR(64), app_version VARCHAR(32), contact VARCHAR(128),
  text TEXT, image_url VARCHAR(255), image_b64 TEXT, log_text TEXT,
  handled BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS app_appreciate (
  id BIGSERIAL PRIMARY KEY,
  device_id VARCHAR(64), app_version VARCHAR(32), amount DECIMAL(10,2),
  contact VARCHAR(128), handled BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW()
);
INSERT INTO app_license(code, plan) VALUES ('C3-TEST-0001','pro')
  ON CONFLICT (code) DO NOTHING;
```

## 四、后台怎么用（请把这几个操作写成一段说明留给我）

1. **发一张新卡密**：INSERT 一行（给我一条现成的 SQL 模板，code 形如 `C3-XXXX-XXXX-XXXX`）
2. **解绑换机**：把某张卡密的 `device_id`/`bind_at` 置空
3. **停用/续期**：`enabled=false` / 改 `expires_at`
4. **看人数**：浏览器打开 `<基础地址>/stats`
5. **处理反馈**：把 `app_feedback.handled` 改成 true
6. **看赞赏**：`SELECT device_id,amount,contact,created_at FROM app_appreciate ORDER BY id DESC;`（处理完把 `handled` 改 true）

## 五、验收自测（请务必跑一遍并把两次结果贴给我）

1. 用测试卡密激活：
   `POST /verify` body `{"code":"C3-TEST-0001","device":"C3-TESTDEVICE001","version":"3.00.17","app":"c3shell"}`
   → 期望 `ok=true`、`plan=pro`
2. 换一台设备用同一个卡密再调一次：
   body 里 device 换成 `C3-TESTDEVICE002`
   → 期望 `ok=false`，message = 「卡密已绑定其它设备（如需换机请在后台解绑）」
3. `POST /heartbeat` 一次（body 用上面那条）→ 期望 `{"ok":true}`，
   然后 `GET /stats` 里 `online5m` 应该 ≥ 1
4. `POST /feedback` 一次（text 随便写一句）→ 期望 `{"ok":true}`，`GET /stats` 里 `feedbackOpen` ≥ 1
5. `POST /appreciate` 两次：先 body `{"device":"C3-TESTDEVICE001","amount":"10"}` → 期望 `ok=false`（金额需大于 20）；
   再 body 换成 `"amount":"50"` → 期望 `{"ok":true,"amount":50}`，`GET /stats` 里 `appreciateOpen` = 1

## 六、完成后回给我的三样东西

1. HTTP 访问服务基础地址（`https://….service.tcloudbase.com`）
2. 上面第 1、2 条自测的**原始返回**
3. 一段「发卡 / 解绑 / 看数 / 处理反馈 / 看赞赏」的操作说明
