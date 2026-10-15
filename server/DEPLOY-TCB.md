# 云开发 TCB 部署步骤（照这个点，约 10 分钟）

> **首选不是手点这页**：把 `server/AGENT-PROMPT.md` 整段粘给「云开发控制台的 AI 助手」，让它替你建（约 10 分钟）。
> 这份留作**手动兜底**：AI 助手不灵、或你想自己看清每一步时照着点 ✓

> 一个云函数管全部接口：/verify（卡密+设备绑定）/heartbeat（统计）/feedback（反馈）/appreciate（赞赏登记）/stats（后台看数）

## 1. 创建环境
云开发控制台 → 新建环境 → 名称随意（如 c3app）→ 套餐选**免费** ✓

## 2. 数据库（**RDS MySQL** ★ 你的环境走这条）
> 云开发控制台 → 数据库 / MySQL → 进 RDS 实例的 **SQL 控制台**，把 `schema-mysql.sql` 整段粘进去执行
> （建 4 张表 + 一条测试卡密 `C3-TEST-0001`，可重复执行；字符集 utf8mb4，中文/emoji 不乱码）

> **然后让云函数能连上它**（TCP 直连，连不上 90% 是下面三条没做）：
> 1. 云函数 → 配置 → **网络**：**开启私有网络**，选 MySQL 所在的 **VPC + 子网**（同地域）
> 2. 云函数 → 配置 → **环境变量**：`MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USERNAME` / `MYSQL_PASSWORD` / `MYSQL_DATABASE`
>    —— **不会自动注入，要手填**：从 MySQL 控制台「连接信息」抄，**主机一定用内网地址**（不是公网地址）
>    （也可以只给一条 `MYSQL_URL=mysql://user:pass@内网地址:3306/库名`）
> 3. RDS 的白名单 / 安全组：放通云函数所在网段
>
> 自检：函数里 `SELECT 1` 通了再往下；报「未配置数据库…」就是第 2 步没填，报 `ETIMEDOUT/ECONNREFUSED` 基本是第 1 或 3 步

## 2b. 文档型数据库（**只有云数据库、没有 RDS** 才走这条）
建 4 个集合（数据库 → 集合管理 → 新建）
| 集合名 | 用途 | 权限 |
|---|---|---|
| app_license | 卡密 + 绑定设备 | **所有用户不可读写**（函数用管理端 SDK，能绕规则，最安全）|
| app_heartbeat | 在线心跳（统计） | 所有用户不可读写 |
| app_feedback | 问题反馈 | 所有用户不可读写 |
| app_appreciate | 赞赏登记（金额 > 20） | 所有用户不可读写 |

### 先塞一条测试卡密（数据库 → app_license → 添加记录）
    {"code":"C3-TEST-0001","plan":"pro","features":"ai,routes,feedback","enabled":true,"note":"测试"}

## 4. 建云函数（云函数 → 新建）
- 函数名：c3-license
- 运行环境：Node.js 18（有 16 也行）
- 代码文件：
  - **RDS MySQL**：index.js ← `tcb-mysql-license.js`，package.json ← `tcb-package-mysql.json`（依赖 `mysql2`）
  - 文档型数据库：index.js ← `tcb-license.js`，package.json ← `tcb-package.json`
  - （两种都是 **入口 exports.main** ✓）
- 依赖安装：保存后在「依赖」里点一次在线安装（或本地 npm i 后一起打包上传）
- 改完代码想先验一遍（不用连真库）：在仓库根目录跑
  `env -u MYSQL_URL -u DATABASE_URL NODE_PATH=$PWD/c3shell/tools/tcb-fn-selftest/stub node c3shell/tools/tcb-fn-selftest/run.js c3shell/server/tcb-mysql-license.js` → 应 16/16 通过

## 5. 开 HTTP 访问（云开发 → HTTP 访问服务 / 云接入）
添加 5 条路径，**都指向 c3-license**：
    /verify    /heartbeat    /feedback    /appreciate    /stats
（方式不限；APP 会用 POST /verify、POST /heartbeat、POST /feedback、POST /appreciate）

拿到基础地址形如： https://<环境ID>.service.tcloudbase.com

## 6. APP 里填地址
设置 → 激活 / 授权 → 校验服务器： https://<环境ID>.service.tcloudbase.com/verify  → 保存
→ 输入 C3-TEST-0001 → 激活 → 应显示「已激活（pro）」

## 7. 看数据
- 统计：浏览器打开 https://<环境ID>.service.tcloudbase.com/stats
- 明细：
  - **RDS MySQL**：RDS 的 SQL 控制台里 `SELECT * FROM app_appreciate ORDER BY id DESC;`（反馈 `app_feedback`、心跳 `app_heartbeat` 同理）
  - 文档型：云开发控制台 → 数据库 → app_heartbeat / app_feedback / app_appreciate（截图存在云存储 ✓）

---

## 客户端现状
- 卡密校验 ✓ 已接（填地址即可）
- 在线心跳 ✓ 已接（每 5 分钟一次；「激活 / 授权」里有开关，可关 ✓ 只上报设备号/版本/系统/机型/显示模式/主机数）
- 问题反馈上传 ⏳ 待接（云函数已支持：text + shotB64 + logText；接好后「问题反馈」会直接上传 ✓）
- 赞赏登记 ✓ 已接（「赞赏」页填 > 20 的金额 → 点「我已赞赏」→ 上报 device/version/amount/contact；未填地址时提示「未配置校验服务器」）
