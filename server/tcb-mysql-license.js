/**
 * C3 控制台 · 云函数（云开发 RDS MySQL 版）★ 你现在这种环境用这个文件
 * 入口：index.js ← 本文件内容（注意入口是 exports.main）
 * 依赖：mysql2
 *
 * 云函数环境变量（**不会自动注入，要在「云函数 → 配置 → 环境变量」手填**；
 *   MYSQL_HOST / MYSQL_PORT / MYSQL_USERNAME(或 MYSQL_USER) / MYSQL_PASSWORD / MYSQL_DATABASE
 *   也可以只给一条连接串：MYSQL_URL=mysql://user:pass@host:3306/db
 *   MYSQL_SSL=1 → 启用 SSL（RDS 开了加密连接才需要）
 *
 * 前提（连不上先查这两条，见 DEPLOY-TCB.md 第 2.5 节）：
 *   ① 云函数「配置 → 网络」**开启私有网络**，选 MySQL 所在的 VPC 和子网（TCP 直连的前提）
 *   ② 主机必须用 **内网地址**（MySQL 控制台「连接信息」里的内网/VPC 地址），不是公网地址
 *   ③ 开了私有网络后云函数**公网出口可能不通** —— 本函数只用数据库，不需要公网出口 ✓
 *
 * 路径（HTTP 访问服务，都指向本函数）：/verify /heartbeat /feedback /appreciate /stats
 *   GET  /  → 一个极简统计网页（浏览器直接看人数）
 */
const mysql = require('mysql2/promise');
let pool = null;

function sslOpt() { return process.env.MYSQL_SSL === '1' ? { ssl: { rejectUnauthorized: false } } : {}; }

function optsFromUrl(u) {
  const p = new URL(u);
  const o = {
    host: p.hostname,
    port: Number(p.port || 3306),
    user: decodeURIComponent(p.username || 'root'),
    password: decodeURIComponent(p.password || '')
  };
  const d = decodeURIComponent((p.pathname || '').replace(/^\//, ''));
  if (d) o.database = d;
  const ssm = (p.searchParams.get('sslmode') || p.searchParams.get('ssl') || '').toLowerCase();
  if (ssm && ssm !== 'disable' && ssm !== 'false' && ssm !== '0') o.ssl = { rejectUnauthorized: false };
  return o;
}

function db() {
  if (pool) return pool;
  const url = process.env.MYSQL_URL || process.env.DATABASE_URL || '';
  if (!url && !(process.env.MYSQL_HOST || process.env.MYSQL_ADDRESS)) {
    throw new Error('未配置数据库：请在云函数「配置 → 环境变量」填 MYSQL_HOST / MYSQL_PORT / MYSQL_USERNAME / MYSQL_PASSWORD / MYSQL_DATABASE（或一条 MYSQL_URL）');
  }
  const base = url ? optsFromUrl(url) : {
    host: process.env.MYSQL_HOST || process.env.MYSQL_ADDRESS || '127.0.0.1',
    port: Number(process.env.MYSQL_PORT || 3306),
    user: process.env.MYSQL_USERNAME || process.env.MYSQL_USER || 'root',
    password: process.env.MYSQL_PASSWORD || process.env.MYSQL_PASSWD || '',
    database: process.env.MYSQL_DATABASE || process.env.MYSQL_DB || ''
  };
  pool = mysql.createPool(Object.assign({ connectionLimit: 4, charset: 'utf8mb4', waitForConnections: true }, base, sslOpt()));
  return pool;
}

const ok = (o) => ({ statusCode: 200, headers: { 'content-type': 'application/json; charset=utf-8' }, body: JSON.stringify(o) });
const fail = (m) => ok({ ok: false, error: { message: m } });
const str = (x) => (x == null ? '' : String(x).trim());
const num = (x) => Number(x || 0);

async function statsData() {
  const q = (sql) => db().query(sql);
  const [[on5]] = await q('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE ts > DATE_SUB(NOW(), INTERVAL 5 MINUTE)');
  const [[on30]] = await q('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE ts > DATE_SUB(NOW(), INTERVAL 30 MINUTE)');
  const [[dau]] = await q('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE DATE(ts) = CURDATE()');
  const [[devs]] = await q('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat');
  const [[open]] = await q('SELECT COUNT(*) c FROM app_feedback WHERE handled = 0');
  const [[appr]] = await q('SELECT COUNT(*) c FROM app_appreciate WHERE handled = 0');
  const [[bound]] = await q("SELECT COUNT(*) c FROM app_license WHERE device_id IS NOT NULL AND device_id <> ''");
  const [[total]] = await q('SELECT COUNT(*) c FROM app_license');
  const [vers] = await q('SELECT app_version v, COUNT(DISTINCT device_id) c FROM app_heartbeat GROUP BY app_version ORDER BY c DESC LIMIT 20');
  const [feats] = await q("SELECT feature f, COUNT(*) c FROM app_heartbeat WHERE feature <> '' GROUP BY feature ORDER BY c DESC LIMIT 20");
  return {
    ok: true,
    online5m: num(on5.c), online30m: num(on30.c), dau: num(dau.c), devices: num(devs.c),
    licenseBound: num(bound.c), licenseTotal: num(total.c),
    feedbackOpen: num(open.c), appreciateOpen: num(appr.c),
    versions: vers.map((r) => ({ v: str(r.v), c: num(r.c) })),
    features: feats.map((r) => ({ f: str(r.f), c: num(r.c) }))
  };
}

function statsHtml(s) {
  const row = (k, v) => '<tr><td>' + k + '</td><td align="right"><b>' + v + '</b></td></tr>';
  return '<!doctype html><meta charset="utf-8"><title>C3 控制台 · 在线统计</title>' +
    '<style>body{font:14px/1.7 system-ui,sans-serif;margin:24px;color:#222}table{border-collapse:collapse;min-width:320px}' +
    'td{border-bottom:1px solid #eee;padding:6px 10px}h2{margin:0 0 12px}</style>' +
    '<h2>C3 控制台 · 在线统计</h2><table>' +
    row('5 分钟在线', s.online5m) + row('30 分钟在线', s.online30m) + row('今日活跃（DAU）', s.dau) +
    row('累计设备', s.devices) + row('已绑卡密', s.licenseBound + ' / ' + s.licenseTotal) +
    row('待处理反馈', s.feedbackOpen) + row('待看赞赏', s.appreciateOpen) +
    '</table><p style="color:#888">更新时间：' + new Date().toLocaleString('zh-CN') + '</p>';
}

exports.main = async (event) => {
  const path = String(event.path || event.rawPath || '').toLowerCase();
  let body = {};
  try {
    if (event.body) {
      const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
      body = typeof raw === 'string' ? JSON.parse(raw) : raw;
    } else body = event.queryString || {};
  } catch (e) { body = {}; }

  try {
    /* ---------- 卡密校验 + 一码一机绑定 ---------- */
    if (path.endsWith('/verify')) {
      const code = str(body.code).toUpperCase(), device = str(body.device);
      if (code.length < 6 || device.length < 4) return fail('参数不完整');
      const [rows] = await db().execute('SELECT * FROM app_license WHERE code = ? AND enabled = 1 LIMIT 1', [code]);
      if (!rows.length) return fail('卡密无效');
      const it = rows[0];
      if (it.expires_at && new Date(it.expires_at).getTime() < Date.now()) return fail('卡密已过期');
      if (!it.device_id) {
        await db().execute('UPDATE app_license SET device_id = ?, bind_at = NOW() WHERE id = ?', [device, it.id]);
      } else if (it.device_id !== device) {
        return fail('卡密已绑定其它设备（如需换机请在后台解绑）');
      }
      return ok({
        ok: true, plan: str(it.plan) || 'pro',
        expiresAt: it.expires_at ? new Date(it.expires_at).toISOString().slice(0, 10) : '',
        features: str(it.features || 'ai,routes,feedback').split(',').filter(Boolean)
      });
    }

    /* ---------- 在线心跳 ---------- */
    if (path.endsWith('/heartbeat')) {
      await db().execute(
        'INSERT INTO app_heartbeat(device_id,app_version,os_version,model,display_mode,host_count,feature) VALUES(?,?,?,?,?,?,?)',
        [str(body.device), str(body.version), str(body.os), str(body.model), str(body.mode), num(body.hosts), str(body.feature)]);
      return ok({ ok: true });
    }

    /* ---------- 问题反馈（截图 base64 直存 image_b64） ---------- */
    if (path.endsWith('/feedback')) {
      /* APP 发的是 data:image/jpeg;base64,xxx（imageB64）；兼容老的 shotB64 字段，前缀要去掉 */
      const shot = str(body.imageB64 || body.shotB64).replace(/^data:[^,]*,/, '');
      await db().execute(
        'INSERT INTO app_feedback(device_id,app_version,contact,text,image_url,image_b64,log_text) VALUES(?,?,?,?,?,?,?)',
        [str(body.device), str(body.version), str(body.contact), str(body.text).slice(0, 8000),
         str(body.imageUrl || ''), shot.slice(0, 1500000), str(body.logText).slice(0, 200000)]);
      return ok({ ok: true });
    }

    /* ---------- 赞赏登记（金额需 > 20） ---------- */
    if (path.endsWith('/appreciate')) {
      const amt = Number(String(body.amount || '').replace(/[^0-9.]/g, ''));
      if (!(amt > 20)) return fail('赞赏金额需大于 20');
      await db().execute('INSERT INTO app_appreciate(device_id,app_version,amount,contact) VALUES(?,?,?,?)',
        [str(body.device), str(body.version), amt, str(body.contact)]);
      return ok({ ok: true, amount: amt });
    }

    /* ---------- 统计 ---------- */
    if (path.endsWith('/stats')) return ok(await statsData());
    if (path === '' || path === '/') {
      const s = await statsData();
      return { statusCode: 200, headers: { 'content-type': 'text/html; charset=utf-8' }, body: statsHtml(s) };
    }

    return fail('未知路径：' + path);
  } catch (e) {
    return fail('服务器异常：' + (e && e.message ? e.message : e));
  }
};
