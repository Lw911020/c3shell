/**
 * C3 控制台 · 云函数（云开发 SQL 型 / PostgreSQL 版）
 * 依赖：pg（云函数依赖安装里加 pg）
 * 环境变量：PG_URL（云开发 → PostgreSQL 管理 里的连接串，形如
 *   postgresql://user:pass@host:5432/db?sslmode=require）
 *
 * 路径（HTTP 访问服务，都指向本函数）：/verify /heartbeat /feedback /appreciate /stats
 */
const { Pool } = require('pg');
let pool = null;
function db() {
  if (!pool) pool = new Pool({ connectionString: process.env.PG_URL, max: 4, ssl: { rejectUnauthorized: false } });
  return pool;
}
const ok = (o) => ({ statusCode: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify(o) });
const fail = (m) => ok({ ok: false, error: { message: m } });
const str = (x) => (x == null ? '' : String(x).trim());

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
    if (path.endsWith('/verify')) {
      const code = str(body.code).toUpperCase(), device = str(body.device);
      if (code.length < 6 || device.length < 4) return fail('参数不完整');
      const r = await db().query('SELECT * FROM app_license WHERE code=$1 AND enabled=TRUE LIMIT 1', [code]);
      if (!r.rows.length) return fail('卡密无效');
      const it = r.rows[0];
      if (it.expires_at && new Date(it.expires_at).getTime() < Date.now()) return fail('卡密已过期');
      if (!it.device_id) await db().query('UPDATE app_license SET device_id=$1, bind_at=NOW() WHERE id=$2', [device, it.id]);
      else if (it.device_id !== device) return fail('卡密已绑定其它设备（如需换机请在后台解绑）');
      return ok({
        ok: true, plan: it.plan || 'pro',
        expiresAt: it.expires_at ? new Date(it.expires_at).toISOString().slice(0, 10) : '',
        features: str(it.features || 'ai,routes,feedback').split(',').filter(Boolean)
      });
    }

    if (path.endsWith('/heartbeat')) {
      await db().query('INSERT INTO app_heartbeat(device_id,app_version,os_version,model,display_mode,host_count,feature) VALUES($1,$2,$3,$4,$5,$6,$7)',
        [str(body.device), str(body.version), str(body.os), str(body.model), str(body.mode), Number(body.hosts || 0), str(body.feature)]);
      return ok({ ok: true });
    }

    if (path.endsWith('/feedback')) {
      /* APP 发的是 data:image/jpeg;base64,xxx（imageB64）；兼容老的 shotB64 字段，前缀要去掉 */
      const shot = str(body.imageB64 || body.shotB64).replace(/^data:[^,]*,/, '');
      await db().query('INSERT INTO app_feedback(device_id,app_version,contact,text,image_url,image_b64,log_text) VALUES($1,$2,$3,$4,$5,$6,$7)',
        [str(body.device), str(body.version), str(body.contact), str(body.text).slice(0, 8000),
         str(body.imageUrl || ''), shot.slice(0, 1500000), str(body.logText).slice(0, 200000)]);
      return ok({ ok: true });
    }

    if (path.endsWith('/appreciate')) {
      const amt = Number(String(body.amount || '').replace(/[^0-9.]/g, ''));
      if (!(amt > 20)) return fail('赞赏金额需大于 20');
      await db().query('INSERT INTO app_appreciate(device_id,app_version,amount,contact) VALUES($1,$2,$3,$4)',
        [str(body.device), str(body.version), amt, str(body.contact)]);
      return ok({ ok: true, amount: amt });
    }

    if (path.endsWith('/stats')) {
      const online = await db().query('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE ts > NOW() - INTERVAL \'5 minutes\'');
      const on30  = await db().query('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE ts > NOW() - INTERVAL \'30 minutes\'');
      const dau    = await db().query('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat WHERE ts::date = CURRENT_DATE');
      const devs   = await db().query('SELECT COUNT(DISTINCT device_id) c FROM app_heartbeat');
      const open   = await db().query('SELECT COUNT(*) c FROM app_feedback WHERE handled=FALSE');
      const appr   = await db().query('SELECT COUNT(*) c FROM app_appreciate WHERE handled=FALSE');
      const bound  = await db().query('SELECT COUNT(*) c FROM app_license WHERE device_id IS NOT NULL');
      const total  = await db().query('SELECT COUNT(*) c FROM app_license');
      const vers   = await db().query('SELECT app_version v, COUNT(DISTINCT device_id) c FROM app_heartbeat GROUP BY 1 ORDER BY 2 DESC LIMIT 20');
      const feats  = await db().query("SELECT feature f, COUNT(*) c FROM app_heartbeat WHERE feature <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 20");
      return ok({ ok: true, online5m: +online.rows[0].c, online30m: +on30.rows[0].c, dau: +dau.rows[0].c, devices: +devs.rows[0].c,
                  feedbackOpen: +open.rows[0].c, appreciateOpen: +appr.rows[0].c,
                  licenseBound: +bound.rows[0].c, licenseTotal: +total.rows[0].c,
                  versions: vers.rows, features: feats.rows });
    }

    return fail('未知路径：' + path);
  } catch (e) {
    return fail('服务器异常：' + (e && e.message ? e.message : e));
  }
};
