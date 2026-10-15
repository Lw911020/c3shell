/**
 * 腾讯云 SCF 单文件版（Node.js 18）—— 如果你一定要用云函数
 * 依赖：mysql2（在 SCF 控制台"依赖安装"里加，或本地 npm i 后打包上传）
 * 环境变量：DB_HOST DB_PORT DB_USER DB_PASS DB_NAME
 * 触发：API 网关，路径 /verify /feedback /heartbeat /stats（或用一个 path 参数分发）
 *
 * 部署步骤（控制台）：
 *   1) 新建函数 → 运行环境 Node.js 18 → 空白函数
 *   2) 代码：粘贴本文件内容（入口 index.main_handler）
 *   3) 函数配置 → 依赖：安装 mysql2
 *   4) 环境变量：DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME
 *   5) 触发器 → API 网关 → 路径 /license/verify 等
 * 说明：也可以用"云开发数据库"，把下面的 q() 换成 TCB 查询即可
 */
const mysql = require('mysql2/promise');

let pool = null;
function db() {
  if (!pool) pool = mysql.createPool({
    host: process.env.DB_HOST, port: +(process.env.DB_PORT || 3306),
    user: process.env.DB_USER, password: process.env.DB_PASS, database: process.env.DB_NAME,
    waitForConnections: true, connectionLimit: 4
  });
  return pool;
}
const fail = (m) => ({ ok: false, error: { message: m } });
const str = (x) => (x == null ? '' : String(x).trim());

exports.main_handler = async (event, context) => {
  let body = {};
  try { body = event.body ? (typeof event.body === 'string' ? JSON.parse(event.body) : event.body) : (event.queryString || {}); }
  catch (e) { return { statusCode: 400, body: JSON.stringify(fail('bad json')) }; }
  const path = (event.path || '').toLowerCase();
  try {
    if (path.endsWith('/verify') || body.action === 'verify') {
      const code = str(body.code).toUpperCase(), device = str(body.device);
      if (code.length < 6 || device.length < 4) return ok(fail('参数不完整'));
      const [rows] = await db().query('SELECT * FROM app_license WHERE code=? AND enabled=1 LIMIT 1', [code]);
      if (!rows.length) return ok(fail('卡密无效'));
      const r = rows[0];
      if (r.expires_at && new Date(r.expires_at).getTime() < Date.now()) return ok(fail('卡密已过期'));
      if (!r.device_id) await db().query('UPDATE app_license SET device_id=?, bind_at=NOW() WHERE id=?', [device, r.id]);
      else if (r.device_id !== device) return ok(fail('卡密已绑定其它设备（如需换机请在后台解绑）'));
      return ok({ ok: true, plan: r.plan, expiresAt: r.expires_at ? new Date(r.expires_at).toISOString().slice(0, 10) : '',
                  features: str(r.features).split(',').filter(Boolean) });
    }
    if (path.endsWith('/heartbeat') || body.action === 'heartbeat') {
      await db().query('INSERT INTO app_heartbeat(device_id,app_version,os_version,model,display_mode,host_count,feature) VALUES(?,?,?,?,?,?,?)',
        [str(body.device), str(body.version), str(body.os), str(body.model), str(body.mode), +(body.hosts || 0), str(body.feature)]);
      return ok({ ok: true });
    }
    if (path.endsWith('/stats')) {
      const [[o]] = await db().query('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE ts > DATE_SUB(NOW(), INTERVAL 5 MINUTE)');
      const [[d]] = await db().query('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE DATE(ts)=CURDATE()');
      const [v] = await db().query('SELECT app_version v, COUNT(DISTINCT device_id) c FROM app_heartbeat GROUP BY v ORDER BY c DESC');
      const [f] = await db().query("SELECT feature f, COUNT(*) c FROM app_heartbeat WHERE feature<>'' GROUP BY f ORDER BY c DESC LIMIT 20");
      return ok({ ok: true, online5m: o.c, dau: d.c, versions: v, features: f });
    }
    return ok(fail('未知路径：' + path));
  } catch (e) {
    return ok(fail('服务器异常：' + (e && e.message ? e.message : e)));
  }
};
function ok(obj) { return { statusCode: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify(obj) }; }
