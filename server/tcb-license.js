/**
 * C3 控制台 · 腾讯云「云开发 TCB」云函数（一个函数管全部接口）
 *
 * 接口（HTTP 访问服务，路径都指向本函数）：
 *   POST /verify     卡密校验 + 设备绑定（一码一机）
 *   POST /heartbeat  在线心跳（用户统计）
 *   POST /feedback   问题反馈（文字 + 截图base64 + 日志文本 → 截图转存云存储）
 *   POST /appreciate 赞赏登记（用户在「赞赏」页回填金额，需 >20）
 *   GET  /stats      统计（5分钟在线 / 日活 / 版本分布 / 功能使用 / 待处理反馈）
 *
 * 集合（数据库里建这 3 个，权限都设为「所有用户不可读写」——函数用管理端SDK绕过规则，最安全）：
 *   app_license    { code, plan, features, device_id, bind_at, expires_at, enabled, note, created_at }
 *   app_heartbeat  { device_id, app_version, os_version, model, display_mode, host_count, feature, ts }
 *   app_feedback   { device_id, app_version, contact, text, image_file_id, log_text, handled, created_at }
 *   app_appreciate { device_id, app_version, amount, contact, handled, created_at }
 *
 * 依赖：@cloudbase/node-sdk（云函数依赖安装里加，或用下面的 package.json）
 */
const tcb = require('@cloudbase/node-sdk');
const app = tcb.init({ env: tcb.SYMBOL_CURRENT_ENV });
const db = app.database();
const _ = db.command;
const $ = db.command.aggregate;   // 聚合操作用（/stats 里分组版本分布）

const ok = (o) => ({ statusCode: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify(o) });
const fail = (m) => ok({ ok: false, error: { message: m } });
const str = (x) => (x == null ? '' : String(x).trim());

exports.main = async (event, context) => {
  let body = {};
  const path = String(event.path || event.rawPath || '').toLowerCase();
  try {
    if (event.body) {
      const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
      body = typeof raw === 'string' ? JSON.parse(raw) : raw;
    } else body = event.queryString || {};
  } catch (e) { body = {}; }

  try {
    /* ---------- 卡密校验 + 设备绑定 ---------- */
    if (path.endsWith('/verify')) {
      const code = str(body.code).toUpperCase(), device = str(body.device);
      if (code.length < 6 || device.length < 4) return fail('参数不完整');
      const r = await db.collection('app_license').where({ code: code, enabled: true }).limit(1).get();
      if (!r.data || !r.data.length) return fail('卡密无效');
      const it = r.data[0];
      if (it.expires_at && new Date(it.expires_at).getTime() < Date.now()) return fail('卡密已过期');
      if (!it.device_id) {
        await db.collection('app_license').doc(it._id).update({ device_id: device, bind_at: new Date() });
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
      await db.collection('app_heartbeat').add({
        device_id: str(body.device), app_version: str(body.version), os_version: str(body.os),
        model: str(body.model), display_mode: str(body.mode),
        host_count: Number(body.hosts || 0), feature: str(body.feature), ts: new Date()
      });
      return ok({ ok: true });
    }

    /* ---------- 问题反馈（截图走云存储，日志存文本） ---------- */
    if (path.endsWith('/feedback')) {
      const dev = str(body.device);
      /* APP 发的是 data:image/jpeg;base64,xxx（imageB64）；兼容老的 shotB64 字段，前缀要去掉 */
      const shot = str(body.imageB64 || body.shotB64).replace(/^data:[^,]*,/, '');
      let fileId = '', b64 = '';
      if (shot.length > 100) {
        try {
          const up = await app.uploadFile({
            cloudPath: 'feedback/' + Date.now() + '-' + (dev.slice(-8) || 'dev') + '.jpg',
            fileContent: Buffer.from(shot, 'base64')
          });
          fileId = up.fileID || '';
        } catch (e) { b64 = shot.slice(0, 1500000); }   /* 没配云存储就退回存 base64 */
      }
      await db.collection('app_feedback').add({
        device_id: dev, app_version: str(body.version), contact: str(body.contact),
        text: str(body.text).slice(0, 8000), image_file_id: fileId, image_b64: b64,
        log_text: str(body.logText).slice(0, 200000), handled: false, created_at: new Date()
      });
      return ok({ ok: true, image: fileId });
    }

    /* ---------- 统计 ---------- */
    if (path.endsWith('/appreciate')) {
      const amt = Number(String(body.amount || '').replace(/[^0-9.]/g, ''));
      if (!(amt > 20)) return fail('赞赏金额需大于 20');
      await db.collection('app_appreciate').add({
        device_id: str(body.device), app_version: str(body.version),
        amount: amt, contact: str(body.contact), handled: false, created_at: new Date()
      });
      return ok({ ok: true, amount: amt });
    }

    if (path.endsWith('/stats')) {
      const since5 = new Date(Date.now() - 5 * 60 * 1000);
      const since30 = new Date(Date.now() - 30 * 60 * 1000);
      const dayStart = new Date(); dayStart.setHours(0, 0, 0, 0);
      const online = await db.collection('app_heartbeat').where({ ts: _.gte(since5) }).count();
      const dau = await db.collection('app_heartbeat').where({ ts: _.gte(dayStart) }).count();
      const all = await db.collection('app_heartbeat').count();
      const on30 = await db.collection('app_heartbeat').where({ ts: _.gte(since30) }).count();
      const open = await db.collection('app_feedback').where({ handled: false }).count();
      const appr = await db.collection('app_appreciate').where({ handled: false }).count();
      const bound = await db.collection('app_license').where({ device_id: _.neq('') }).count();
      const total = await db.collection('app_license').count();
      const vers = await db.collection('app_heartbeat').aggregate()
        .group({ _id: '$app_version', c: $.sum(1) }).sort({ c: -1 }).limit(20).end();
      return ok({
        ok: true,
        online5m: online.total, online30m: on30.total, dau: dau.total, heartbeats: all.total,
        feedbackOpen: open.total, appreciateOpen: appr.total,
        licenseBound: bound.total, licenseTotal: total.total,
        versions: (vers.list || []).map((x) => ({ v: x._id, c: x.c }))
      });
    }

    return fail('未知路径：' + path);
  } catch (e) {
    return fail('服务器异常：' + (e && e.message ? e.message : e));
  }
};
