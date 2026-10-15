# C3 控制台 · 后端部署指引（卡密 / 设备绑定 / 反馈 / 在线统计）

> **首选路线**：腾讯云开发（TCB）——把 `server/AGENT-PROMPT.md` 整段粘给云开发控制台的 AI 助手即可。
> 这份是**备选**：你已经有一台服务器/现成后端时，照这里把 3 张表 + 一个 Controller 接进去 ✓

> 说明：AI 不能登录你的腾讯云控制台（需要你的登录态）。下面是**照着点**就能完成的两种方案。
> 客户端已写好，指向 /api/v1/app/license/verify（可在 APP「激活 / 授权」里改地址）。

---

## 方案 A（推荐 · 5 分钟）：放进你现有的 renren-admin

你已经有服务器 + 数据库，这是最省事的路。

1. **建表**：数据库里执行 schema.sql（3 张表：app_license / app_heartbeat / app_feedback）
2. **加测试卡密**：

        INSERT INTO app_license(code, plan) VALUES ('C3-TEST-0001','pro');

3. **放代码**：把 LicenseController.java 放进你的项目（如 com.renren.admin.modules.app），
   项目需要有 spring-boot-starter-jdbc（用了 JdbcTemplate）；renren-admin 自带。
4. **重启后端** → 验证：

        POST https://openpilottools.yuluoqc.xyz/renren-admin/api/v1/app/license/verify
        {"code":"C3-TEST-0001","device":"C3-XXXXXXXX","version":"2.119","app":"c3shell"}
        -> {"ok":true,"plan":"pro","expiresAt":"","features":["ai","routes","feedback"]}

5. **APP 里激活**：设置 →「激活 / 授权」→ 填 C3-TEST-0001 → 激活 ✓
6. **后台统计**：GET /api/v1/app/stats（日活 / 5 分钟在线 / 版本分布 / 功能使用 / 待处理反馈）

---

## 方案 B：腾讯云 SCF（云函数）

适合你不想动现有后台时。**注意：SCF 本身无状态，必须配一个数据库**（云数据库 MySQL 最省事）。

1. 腾讯云 → 云数据库 MySQL → 新建实例（最小规格即可）→ 执行 schema.sql
2. 腾讯云 → 云函数 SCF → 新建函数
   - 运行环境：Node.js 18
   - 创建方式：空白函数
3. **函数代码**：把 SCF-license.js 全文粘进去，入口填 index.main_handler
4. **依赖**：函数配置 → 依赖安装 → 添加 mysql2
5. **环境变量**：DB_HOST / DB_PORT / DB_USER / DB_PASS / DB_NAME
6. **触发器**：添加 API 网关 触发器
   - 路径：/license/verify、/heartbeat、/stats（可都指向同一函数）
   - API 网关里把方法鉴权设为「免鉴权」（APP 直连）
7. 复制 API 网关给出的完整 URL → 填进 APP「激活 / 授权 → 校验服务器」→ 保存 ✓

---

## 客户端还要我接的两件事（说一声就做）

| 功能 | 客户端要做的事 | 用到的接口 |
|---|---|---|
| 在线统计 | APP 每 5 分钟 POST 一次心跳（设备号/版本/系统/机型/显示模式/主机数/最近功能） | POST /heartbeat |
| 反馈上传 | 「问题反馈」把文字 + 截图 + 日志直接 POST 上去（现在先存到下载目录） | POST /feedback（multipart） |

> 心跳与反馈都要**用户可关**（软件设置里给开关），并说明"会匿名上报设备信息"，合规也省心。
