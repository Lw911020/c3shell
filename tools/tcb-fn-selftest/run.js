/**
 * 云函数自检（不需要真 MySQL）—— 用完就删的假驱动 + 16 项断言
 *
 * 用法（在仓库根目录跑）：
 *   env -u MYSQL_URL -u DATABASE_URL NODE_PATH=$PWD/c3shell/tools/tcb-fn-selftest/stub \
 *     node c3shell/tools/tcb-fn-selftest/run.js c3shell/server/tcb-mysql-license.js
 *
 * 它验证「路由 + SQL 拼装 + 字段名 + 缺配置降级」这些不看真库就能查的错；
 * 真正的连库仍要在云上跑一次（见 server/DEPLOY-TCB.md 第 2 节自检）。
 */
const fn = require(require('path').resolve(process.argv[2]));
const stub = require('mysql2/promise');
const T = [];
function chk(name, cond, extra) { T.push((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : '  <<< ' + JSON.stringify(extra))); }
async function call(p, body) {
  const r = await fn.main({ path: p, body: body ? JSON.stringify(body) : undefined });
  let j = null; try { j = JSON.parse(r.body); } catch (e) {}
  return { code: r.statusCode, ct: r.headers['content-type'] || '', raw: r.body, j: j };
}
(async () => {
  // ① 一个环境变量都没填 → 必须是中文可读提示（必须在建连接池之前测，池建好就缓存了）
  delete process.env.MYSQL_URL; delete process.env.DATABASE_URL; delete process.env.MYSQL_HOST; delete process.env.MYSQL_ADDRESS;
  const noconf = await call('/stats');
  chk('没填环境变量 → 中文提示', noconf.j.ok === false && /未配置数据库/.test(noconf.j.error.message), noconf.j);

  // ② 填上环境变量（假地址即可，驱动是 stub）
  process.env.MYSQL_HOST = 'mysql-internal.example';
  process.env.MYSQL_PORT = '3306';
  process.env.MYSQL_USERNAME = 'u';
  process.env.MYSQL_PASSWORD = 'p';
  process.env.MYSQL_DATABASE = 'c3app';

  const v = await call('/verify', { code: 'c3-test-0001', device: 'C3-TESTDEVICE001', version: '3.00.41' });
  chk('verify ok + plan/features', v.j && v.j.ok === true && v.j.plan === 'pro' && v.j.features.length === 3, v.j);
  const sel = stub.__calls.filter((c) => /FROM APP_LICENSE WHERE CODE/i.test(c[1]))[0];
  chk('verify 卡密转大写再查', sel && sel[2][0] === 'C3-TEST-0001', sel ? sel[2] : null);
  const upd = stub.__calls.filter((c) => /UPDATE APP_LICENSE SET DEVICE_ID/i.test(c[1]))[0];
  chk('首次激活写 device_id（一码一机）', !!upd && upd[2][0] === 'C3-TESTDEVICE001', upd ? upd[2] : null);
  chk('verify 参数不完整 → fail', (await call('/verify', { code: 'C3-TEST-0001', device: 'C3' })).j.ok === false);
  chk('heartbeat ok', (await call('/heartbeat', { device: 'C3-X', version: '3.00.41', os: 'Android 13', model: 'Pad', mode: 'tablet', hosts: 2, feature: '' })).j.ok === true);
  chk('feedback ok', (await call('/feedback', { device: 'C3-X', text: 'hi', imageB64: 'data:image/jpeg;base64,AAAA', logText: 'log' })).j.ok === true);
  const a1 = await call('/appreciate', { device: 'C3-X', amount: '10' });
  chk('appreciate 10 → 拒绝', a1.j.ok === false && /20/.test(a1.j.error.message), a1.j);
  const a2 = await call('/appreciate', { device: 'C3-X', amount: '50' });
  chk('appreciate 50 → ok,amount 数字', a2.j.ok === true && a2.j.amount === 50, a2.j);
  const s = await call('/stats');
  chk('stats 字段齐全', s.j && s.j.online5m === 7 && s.j.online30m === 7 && s.j.dau === 7 && s.j.devices === 7 &&
      s.j.licenseBound === 7 && s.j.licenseTotal === 7 && s.j.feedbackOpen === 7 && s.j.appreciateOpen === 7, s.j);
  chk('stats versions/features 是数组', Array.isArray(s.j.versions) && s.j.versions[0].v === '3.00.41' && Array.isArray(s.j.features));
  const root = await call('/');
  chk('GET / 返回 HTML 统计页', /html/.test(root.ct) && /在线统计/.test(root.raw || ''));
  chk('未知路径 → fail', (await call('/nope')).j.ok === false);
  const sqls = stub.__calls.map((c) => c[1]).join('\n');
  chk('全部 ? 占位符（MySQL 语法，不是 $1）', !/\$1/.test(sqls) && /VALUES\(\?/.test(sqls));
  chk('无 pg 专有函数（DATE_SUB/CURDATE）', /DATE_SUB\(NOW\(\), INTERVAL 5 MINUTE\)/.test(sqls) && /CURDATE\(\)/.test(sqls));
  const ins = stub.__calls.filter((c) => /INSERT INTO APP_FEEDBACK/i.test(c[1]))[0];
  chk('feedback 存纯 base64（去掉 data: 前缀）', ins && ins[2][5] === 'AAAA', ins ? ins[2] : null);

  console.log(T.join('\n'));
  const bad = T.filter((x) => x.indexOf('FAIL') === 0);
  console.log('---- ' + (T.length - bad.length) + '/' + T.length + ' 通过 ----');
  process.exit(bad.length ? 1 : 0);
})();
