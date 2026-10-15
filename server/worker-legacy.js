// c3shell 后台 · Cloudflare Worker 版 v2（带登录页 + 美化界面）
// 绑定：KV 命名空间 -> 变量名 CARDS
// 密钥：TOKEN（接口校验口令/会话签名）、ADMIN_USER（登录名，默认 admin）、ADMIN_PASS（登录密码）
// 访问：GET /admin  ->  登录页；登录后进入后台（Cookie 会话，7 天）
//      也可直接用 /admin?token=<TOKEN> 免登录进入（兼容旧用法）
// 接口（与 APP 的 Lic.java 对应）：POST /verify /feedback /appreciate /heartbeat ; GET /stats
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type, Authorization", "Access-Control-Allow-Methods": "GET, POST, OPTIONS" };
const J = (o, code) => new Response(JSON.stringify(o), { status: code || 200, headers: Object.assign({ "Content-Type": "application/json; charset=utf-8" }, CORS) });
const css = ["*{box-sizing:border-box}", "body{margin:0;background:#f5f6f8;color:#1f2430;font:14px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,Microsoft YaHei,sans-serif}", "a{color:#2b6cb0;text-decoration:none}", "header{background:linear-gradient(135deg,#1f2937,#374151);color:#fff;padding:18px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}", "header h1{font-size:18px;margin:0;font-weight:600}", ".sub{opacity:.7;font-size:12px}", ".wrap{max-width:1180px;margin:0 auto;padding:18px}", ".cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:18px}", ".card{background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(16,24,40,.08)}", ".card .k{font-size:12px;color:#6b7280}", ".card .v{font-size:24px;font-weight:700;margin-top:4px}", "section{background:#fff;border-radius:12px;padding:14px 16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(16,24,40,.08)}", "section h2{font-size:15px;margin:0 0 10px;display:flex;align-items:center;gap:8px}", ".btn{display:inline-block;background:#2b6cb0;color:#fff;border:0;border-radius:8px;padding:7px 12px;font-size:13px;cursor:pointer}", ".btn.gray{background:#6b7280}", ".btn.red{background:#dc2626}", ".btn.small{padding:3px 8px;font-size:12px;border-radius:6px}", "input,select{border:1px solid #d1d5db;border-radius:8px;padding:6px 9px;font-size:13px;margin-right:6px}", "table{width:100%;border-collapse:collapse;font-size:13px}", "th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #eef0f3;vertical-align:top}", "th{background:#f9fafb;color:#6b7280;font-weight:600;position:sticky;top:0}", "tr:hover td{background:#fafbfc}", ".chip{display:inline-block;background:#e8f0fb;color:#1d4ed8;border-radius:999px;padding:1px 8px;font-size:12px;margin:1px 2px}", ".chip.g{background:#e7f7ee;color:#067647}", ".chip.r{background:#fdeaea;color:#b42318}", ".chip.y{background:#fdf6e3;color:#a16207}", ".muted{color:#6b7280}", ".mono{font-family:ui-monospace,Menlo,Consolas,monospace}", ".tw{max-height:340px;overflow:auto;border:1px solid #eef0f3;border-radius:8px}", "details summary{cursor:pointer;color:#2b6cb0}", ".login{max-width:380px;margin:8vh auto;background:#fff;border-radius:14px;padding:26px;box-shadow:0 6px 24px rgba(16,24,40,.12)}", ".login h1{font-size:18px;margin:0 0 4px}", ".login p{color:#6b7280;font-size:13px;margin:0 0 18px}", ".login input{width:100%;margin:0 0 10px;padding:10px 12px}", ".login .btn{width:100%;padding:10px}", ".err{background:#fdeaea;color:#b42318;border-radius:8px;padding:8px 10px;font-size:13px;margin-bottom:12px}", "footer{text-align:center;color:#9aa3af;font-size:12px;padding:10px 0 30px}"].join("");
const H = (html, code, extra) => new Response(html, { status: code || 200, headers: Object.assign({ "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" }, CORS, extra || {}) });
const now = () => new Date().toISOString().replace("T", " ").slice(0, 19);
const today = () => now().slice(0, 10);
function rnd(n) { const s = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; let o = ""; for (let i = 0; i < n; i++) o += s[Math.floor(Math.random() * s.length)]; return o; }
function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/'/g, "&#39;").replace(/"/g, "&quot;"); }
const enc = new TextEncoder();
async function hmacHex(key, data) {
  const k = await crypto.subtle.importKey("raw", enc.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", k, enc.encode(data));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
}
async function sessMake(env, user) {
  const exp = Date.now() + 7 * 86400000;
  const payload = user + "." + exp;
  return payload + "." + await hmacHex(TOKEN || "c3key", payload);
}
async function sessUser(env, req) {
  const raw = cookieOf(req, "c3sess");
  if (!raw) return "";
  const p = raw.split(".");
  if (p.length !== 3) return "";
  if (!(Number(p[1]) > Date.now())) return "";
  const want = await hmacHex(TOKEN || "c3key", p[0] + "." + p[1]);
  return p[2] === want ? p[0] : "";
}
function cookieOf(req, name) {
  const c = req.headers.get("Cookie") || "";
  for (const part of c.split(";")) { const kv = part.trim().split("="); if (kv[0] === name) return decodeURIComponent(kv[1] || ""); }
  return "";
}
async function kvAll(env, prefix, cap) {
  const out = []; let cursor = undefined;
  do {
    const l = await CARDS.list({ prefix: prefix || undefined, cursor: cursor, limit: 1000 });
    for (const k of l.keys) { out.push(k.name); if (cap && out.length >= cap) return out; }
    cursor = l.list_complete ? undefined : l.cursor;
  } while (cursor);
  return out;
}

const FEAT_IDS = ["cast", "term", "files", "live", "ops", "settings", "uiset", "ai", "routes", "feedback", "logs"];

/** 远端功能开关：feat:<设备> 优先；否则 feat:__default；都没有 = ["*"] 不限制（老用户不受影响） */
async function featGet(env, dev) {
  const mine = JSON.parse((await CARDS.get("feat:" + dev)) || "null");
  const def = JSON.parse((await CARDS.get("feat:__default")) || "null");
  const list = mine && mine.features ? mine.features : (def && def.features ? def.features : ["*"]);
  return { ok: true, device: dev, features: list, source: mine ? "device" : (def ? "default" : "all"),
           updated: (mine && mine.updated) || (def && def.updated) || "" };
}
async function featSet(env, dev, list, note) {
  const key = "feat:" + (dev || "__default");
  await CARDS.put(key, JSON.stringify({ features: list, updated: now(), note: note || "" }));
  return { ok: true, device: dev || "__default", features: list };
}

async function hist(env, dev, ev) {
  const ts = now();
  await CARDS.put("hist:" + dev + ":" + ts.replace(/[: ]/g, "-") + "-" + rnd(3), JSON.stringify(Object.assign({ ts: ts }, ev)));
}

async function verify(env, b) {
  const code = String(b.code || "").trim().toUpperCase();
  const dev = String(b.device || "").trim();
  const ver = String(b.version || "");
  if (code.length < 6) return [400, { ok: false, error: { message: "卡密太短（至少 6 位）" } }];
  if (!dev) return [400, { ok: false, error: { message: "缺少设备标识" } }];
  const raw = await CARDS.get("card:" + code);
  if (!raw) return [400, { ok: false, error: { message: "卡密无效" } }];
  const card = JSON.parse(raw);
  if (card.expiresAt && card.expiresAt < now()) return [400, { ok: false, error: { message: "卡密已过期（" + card.expiresAt + " UTC）" } }];
  const keys = await kvAll(env, "bind:" + code + ":");
  const devs = keys.map(k => k.slice(("bind:" + code + ":").length));
  const max = card.maxDevices || 1;
  if (devs.indexOf(dev) < 0 && devs.length >= max) return [400, { ok: false, error: { message: "该卡密已绑定其它设备（后台可解绑换机）" } }];
  await CARDS.put("bind:" + code + ":" + dev, JSON.stringify({ ts: now(), version: ver }));
  const old = await CARDS.get("dev:" + dev);
  const od = old ? JSON.parse(old) : {};
  await CARDS.put("dev:" + dev, JSON.stringify({ ts: now(), first: od.first || now(), feature: "license", version: ver, code: code, count: (od.count || 0) + 1 }));
  await hist(env, dev, { type: "verify", code: code, version: ver, plan: card.plan || "", expiresAt: card.expiresAt || "" });
  return [200, { ok: true, plan: card.plan || "", expiresAt: card.expiresAt || "" }];
}

async function feedback(env, b) {
  const dev = String(b.device || "unknown");
  const id = now().replace(/[: ]/g, "-") + "-" + rnd(4);
  await CARDS.put("fb:" + id, JSON.stringify({ ts: now(), device: dev, version: b.version || "", contact: b.contact || "",
    text: String(b.text || "").slice(0, 4000), logTail: String(b.logText || "").slice(-8000), imgB64: String(b.imageB64 || "").slice(0, 300000) }));
  const old = await CARDS.get("dev:" + dev);
  const od = old ? JSON.parse(old) : {};
  await CARDS.put("dev:" + dev, JSON.stringify({ ts: now(), first: od.first || now(), feature: "feedback", version: b.version || "", count: (od.count || 0) + 1 }));
  await hist(env, dev, { type: "feedback", key: "fb:" + id, text: String(b.text || "").slice(0, 200) });
  return [200, { ok: true, id: id }];
}

async function appreciate(env, b) {
  const id = now().replace(/[: ]/g, "-") + "-" + rnd(4);
  const amt = parseFloat(String(b.amount || "0").replace(/[^0-9.]/g, "")) || 0;
  await CARDS.put("ap:" + id, JSON.stringify({ ts: now(), device: b.device || "", version: b.version || "", amount: amt, contact: b.contact || "" }));
  await hist(env, String(b.device || "unknown"), { type: "appreciate", amount: amt });
  return [200, { ok: true }];
}

async function heartbeat(env, b) {
  const dev = String(b.device || "").trim();
  if (!dev) return [400, { ok: false, error: { message: "缺少设备标识" } }];
  const old = await CARDS.get("dev:" + dev);
  const od = old ? JSON.parse(old) : {};
  const prevH = od.lastHist ? Date.parse(od.lastHist.replace(" ", "T") + "Z") : 0;
  const doH = !prevH || (Date.now() - prevH) > 6 * 3600000;
  await CARDS.put("dev:" + dev, JSON.stringify({ ts: now(), first: od.first || now(), feature: b.feature || "", hostCount: b.hostCount || 0, mode: b.mode || "", version: b.version || od.version || "", code: od.code || "", count: (od.count || 0) + 1, lastHist: doH ? now() : (od.lastHist || "") }));
  if (doH) await hist(env, dev, { type: "heartbeat", feature: b.feature || "", mode: b.mode || "" });
  return [200, { ok: true }];
}

async function mint(env, b) {
  const count = Math.min(parseInt(b.count || "1", 10) || 1, 100);
  const days = parseInt(b.days || "365", 10);
  const plan = String(b.plan || "1y");
  const max = parseInt(b.maxDevices || "1", 10) || 1;
  const exp = days > 0 ? new Date(Date.now() + days * 86400000).toISOString().replace("T", " ").slice(0, 19) : "";
  const codes = [];
  for (let i = 0; i < count; i++) {
    const code = "C3-" + rnd(12);
    await CARDS.put("card:" + code, JSON.stringify({ plan: plan, expiresAt: exp, maxDevices: max, created: now() }));
    codes.push(code);
  }
  return [200, { ok: true, plan: plan, expiresAt: exp, codes: codes }];
}

async function gather(env) {
  const all = await kvAll(env, "", 4000);
  const g = { cards: [], binds: [], devs: [], fbs: [], aps: [] };
  for (const key of all) {
    const v = JSON.parse((await CARDS.get(key)) || "{}");
    v._key = key;
    if (key === "feat:__default") g.defFeat = v;
    else if (key.startsWith("card:")) g.cards.push(v);
    else if (key.startsWith("bind:")) g.binds.push(v);
    else if (key.startsWith("dev:")) g.devs.push(v);
    else if (key.startsWith("fb:")) g.fbs.push(v);
    else if (key.startsWith("ap:")) g.aps.push(v);
  }
  const byTs = (a, b) => String(b.ts || "").localeCompare(String(a.ts || ""));
  g.cards.sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")));
  g.devs.sort(byTs); g.fbs.sort(byTs); g.aps.sort(byTs); g.binds.sort(byTs);
  return g;
}

async function stats(env) {
  const g = await gather(env);
  const cut = new Date(Date.now() - 10 * 60000).toISOString().replace("T", " ").slice(0, 19);
  const used = new Set(g.binds.map(b => (b._key || "").split(":")[1]));
  return [200, { ok: true, online: g.devs.filter(d => (d.ts || "") >= cut).length, devices: g.devs.length,
    today: g.devs.filter(d => (d.ts || "").slice(0, 10) === today()).length, cards: g.cards.length, cardsUsed: used.size,
    feedback: g.fbs.length, appreciate: g.aps.length,
    appreciateAmount: Math.round(g.aps.reduce((s, a) => s + (Number(a.amount) || 0), 0) * 100) / 100, serverTime: now() }];
}

async function devicePage(env, u) {
  const id = u.searchParams.get("id") || "";
  const keys = await kvAll(env, "hist:" + id + ":");
  const events = [];
  for (const k of keys) { const v = JSON.parse((await CARDS.get(k)) || "{}"); events.push(v); }
  events.sort((a, b) => String(b.ts || "").localeCompare(String(a.ts || "")));
  const dev = JSON.parse((await CARDS.get("dev:" + id)) || "{}");
  const bkeys = await kvAll(env, "bind:");
  const cards = [];
  for (const k of bkeys) { const p = k.split(":"); if (p[2] === id) { const raw = await CARDS.get("card:" + p[1]); if (raw) { const c = JSON.parse(raw); c._code = p[1]; cards.push(c); } } }
  const cut = new Date(Date.now() - 10 * 60000).toISOString().replace("T", " ").slice(0, 19);
  const rfeat = await featGet(env, id);
  let b = "<header><h1>设备详情</h1><span class=sub>" + esc(id) + "</span><span style='flex:1'></span><a class='btn gray' href='../admin'>返回后台</a></header><div class=wrap>";
  b += "<div class=cards><div class=card><div class=k>状态</div><div class=v>" + ((dev.ts || "") >= cut ? "在线" : "离线") + "</div></div>" +
    "<div class=card><div class=k>心跳次数</div><div class=v>" + (dev.count || 0) + "</div></div>" +
    "<div class=card><div class=k>事件数</div><div class=v>" + events.length + "</div></div></div>";
  b += "<section><h2>基本信息</h2><table><tr><th>版本</th><td>" + esc(dev.version || "-") + "</td></tr><tr><th>首次</th><td>" + esc(dev.first || "-") + "</td></tr><tr><th>最近</th><td>" + esc(dev.ts || "-") + "</td></tr><tr><th>绑定卡密</th><td>" + esc(dev.code || "-") + "</td></tr></table></section>";
  b += "<section><h2>持有的卡密</h2>" + tbl(["卡密", "计划", "到期(UTC)", "台数", "创建"], cards.map(c => [esc(c._code), esc(c.plan || "-"), esc(c.expiresAt || "永久"), c.maxDevices || 1, esc(c.created || "-")])) + "</section>";
  b += "<section><h2>功能开关（远端控制这台设备）</h2><p class=muted>当前生效：" + esc((rfeat.features || []).join(" / ")) + "（来源 " + esc(rfeat.source) + "，" + esc(rfeat.updated || "-") + "）</p>" + featForm(id, rfeat.features || []) + "</section>";
  b += "<section><h2>事件时间线（激活 / 反馈 / 赞赏 / 心跳）</h2>" + tbl(["时间", "类型", "细节"], events.slice(0, 500).map(e => {
    let d = "";
    if (e.type === "verify") d = "激活 " + (e.plan || "") + " · 到期 " + (e.expiresAt || "永久") + " · " + (e.code || "");
    else if (e.type === "feedback") d = "反馈：" + (e.text || "");
    else if (e.type === "appreciate") d = "赞赏 ￥" + (e.amount || 0);
    else d = "心跳 " + (e.feature || "") + " " + (e.mode || "");
    return [esc(e.ts || "-"), "<span class=chip>" + esc(e.type || "") + "</span>", esc(d)];
  })) + "</section></div>";
  return shell("设备 " + id, b);
}

function featForm(dev, cur) {
  const has = (id) => cur.indexOf(id) >= 0 || cur.indexOf("*") >= 0;
  let h = "<form method=post action=admin/act><input type=hidden name=do value=feats><input type=hidden name=device value='" + esc(dev) + "'>";
  for (const id of FEAT_IDS) h += "<label class=note style='display:inline-flex;align-items:center;gap:4px;margin:2px 10px 2px 0'><input type=checkbox name=features value='" + id + "'" + (has(id) ? " checked" : "") + "> " + id + "</label>";
  h += "<button class=btn>保存开关</button> <span class=muted>勾掉 = 远程禁用；什么都不勾 = 该设备只剩「主机」；全勾 = 不限制</span></form>";
  return h;
}

function loginPage(err) {
  return "<!DOCTYPE html><html lang=zh><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\"><title>c3shell 后台登录</title><style>" + css + "</style></head><body>" +
    "<form class=login method=post action=admin/login>" +
    "<h1>c3shell 后台</h1><p>请登录后查看卡密 / 设备 / 反馈 / 赞赏</p>" +
    (err ? "<div class=err>" + esc(err) + "</div>" : "") +
    "<input name=user placeholder=用户名 autocomplete=username required>" +
    "<input name=pass type=password placeholder=密码 autocomplete=current-password required>" +
    "<button class=btn type=submit>登录</button>" +
    "<p style=\"margin-top:14px\" class=muted>用 ADMIN_USER / ADMIN_PASS 设置账号密码；<br>也可访问 /admin?token=TOKEN 免登录进入</p>" +
    "</form></body></html>";
}

function shell(title, body) {
  return "<!DOCTYPE html><html lang=zh><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\"><title>" + esc(title) + "</title><style>" + css + "</style></head><body>" + body + "<footer>c3shell backend · Cloudflare Worker</footer></body></html>";
}

function tbl(cols, rows, empty) {
  if (!rows.length) return "<p class=muted>" + esc(empty || "暂无数据") + "</p>";
  let h = "<div class=tw><table><tr>" + cols.map(c => "<th>" + c + "</th>").join("") + "</tr>";
  for (const r of rows) h += "<tr>" + r.map(c => "<td>" + c + "</td>").join("") + "</tr>";
  return h + "</table></div>";
}

function dash(env, u, g, notice) {
  const cut = new Date(Date.now() - 10 * 60000).toISOString().replace("T", " ").slice(0, 19);
  const used = new Set(g.binds.map(b => (b._key || "").split(":")[1]));
  const online = g.devs.filter(d => (d.ts || "") >= cut).length;
  const sum = Math.round(g.aps.reduce((s, a) => s + (Number(a.amount) || 0), 0) * 100) / 100;
  const card = (k, v) => "<div class=card><div class=k>" + k + "</div><div class=v>" + v + "</div></div>";
  const token = u.searchParams.get("token") || "";
  const defFeats = JSON.parse((g.defFeat && g.defFeat.features) ? JSON.stringify(g.defFeat.features) : "null") || ["*"];
  const q = token ? "&token=" + encodeURIComponent(token) : "";
  const base = u.pathname.replace(/[^/]*$/, "");
  let body = "<header><h1>c3shell 后台</h1><span class=sub>服务器时间 " + now() + " UTC · 会话 7 天</span><span style=\"flex:1\"></span>" +
    "<a class=btn gray href=\"admin" + (token ? "?token=" + encodeURIComponent(token) : "") + "\">刷新</a> " +
    "<a class=btn gray href=\"admin/logout\">退出</a></header><div class=wrap>";
  if (notice) body += "<div class=err style=\"background:#e7f7ee;color:#067647\">" + esc(notice) + "</div>";
  body += "<div class=cards>" + card("在线（10 分钟）", online) + card("累计设备", g.devs.length) +
    card("今日活跃", g.devs.filter(d => (d.ts || "").slice(0, 10) === today()).length) +
    card("卡密总数", g.cards.length) + card("已使用卡密", used.size) + card("反馈", g.fbs.length) +
    card("赞赏笔数", g.aps.length) + card("赞赏合计", "￥" + sum) + "</div>";
  body += "<section><h2>默认功能开关（所有设备 · 服务器下发）</h2><p class=muted>设备没有单独设置时，就用这里的默认；什么都没设 = 不限制（全开）</p>" + featForm("__default", defFeats) + "</section>";
  body += "<section><h2>发卡</h2><form method=post action=\"admin/act\">" +
    "<input type=hidden name=do value=mint><input type=hidden name=tok value=\"" + esc(token) + "\">" +
    "计划 <input name=plan value=1y size=4> 天数 <input name=days value=365 size=5> 数量 <input name=count value=10 size=3> 每卡台数 <input name=maxDevices value=1 size=2> " +
    "<button class=btn type=submit>生成卡密</button></form>";
  if (g.cards.length) body += "<p class=mono style=\"margin-top:8px\">最近生成的卡密（点复制）：<br>" +
    g.cards.slice(0, 20).map(c => "<span class=chip onclick=\"navigator.clipboard.writeText('" + c._key.slice(5) + "')\">" + c._key.slice(5) + "</span>").join("") + "</p>";
  body += "</section>";
  body += "<section><h2>设备（" + g.devs.length + "）</h2> <a class=btn href='admin/export?type=devices'>导出 CSV</a>" + tbl(["设备ID", "状态", "绑定卡密", "版本", "次数", "首次", "最近"],
    g.devs.slice(0, 300).map(d => ["<span class=mono>" + esc((d._key || "").slice(4)) + "</span>",
      ((d.ts || "") >= cut ? "<span class=\"chip g\">在线</span>" : "<span class=\"chip\">离线</span>"),
      "<span class=\"chip y\">" + esc(d.code || "-") + "</span>", esc(d.version || "-"), d.count || 1, esc(d.first || "-"), esc(d.ts || "-") + " <a class=btn href='admin/device?id=" + encodeURIComponent((d._key || "").slice(4)) + "'>历史</a>"])) + "</section>";
  body += "<section><h2>卡密（" + g.cards.length + "）</h2> <a class=btn href='admin/export?type=cards'>导出 CSV</a>" + tbl(["卡密", "计划", "到期(UTC)", "台数", "已绑", "创建", "操作"],
    g.cards.slice(0, 300).map(c => {
      const code = (c._key || "").slice(5);
      const binds = g.binds.filter(b => (b._key || "").indexOf("bind:" + code + ":") === 0);
      const exp = c.expiresAt && c.expiresAt < now() ? "<span class=\"chip r\">已过期</span> " + esc(c.expiresAt) : esc(c.expiresAt || "永久");
      return ["<span class=mono>" + esc(code) + "</span>", esc(c.plan || "-"), exp, c.maxDevices || 1, binds.length, esc(c.created || "-"),
        "<a class=\"btn small red\" href=\"admin/act?do=delcard&code=" + encodeURIComponent(code) + q + "\" onclick=\"return confirm('确认删除该卡密？')\">删除</a>" +
        (binds.length ? " <a class=\"btn small gray\" href=\"admin/act?do=unbind&code=" + encodeURIComponent(code) + q + "\" onclick=\"return confirm('解绑该卡密的所有设备？')\">解绑</a>" : "") + " <form method=post action='admin/act' style='display:inline'><input type=hidden name=do value=renew><input type=hidden name=code value=" + code + "><input type=hidden name=tok value=" + esc(token) + "><input name=days value=365 size=3 style='width:56px'> <button class=btn style='padding:2px 8px;font-size:12px'>续期</button></form>"];
    })) + "</section>";
  body += "<section><h2>绑定关系（" + g.binds.length + "）</h2> <a class=btn href='admin/export?type=bind'>导出 CSV</a>" + tbl(["卡密", "设备", "版本", "最近"],
    g.binds.slice(0, 300).map(b => { const p = (b._key || "").split(":"); return [esc(p[1]), "<span class=mono>" + esc(p[2]) + "</span>", esc(b.version || "-"), esc(b.ts || "-")]; })) + "</section>";
  body += "<section><h2>反馈（" + g.fbs.length + "）</h2> <a class=btn href='admin/export?type=fb'>导出 CSV</a>";
  if (!g.fbs.length) body += "<p class=muted>暂无反馈</p>";
  for (const f of g.fbs.slice(0, 100)) {
    body += "<details><summary>" + esc(f.ts) + " · " + esc((f.device || "").slice(0, 12)) + " · " + esc(f.text || "") .slice(0, 60) + "</summary>" +
      "<p>" + esc(f.text || "") + "</p><p class=muted>版本 " + esc(f.version || "-") + " · 联系 " + esc(f.contact || "-") + "</p>" +
      (f.imgB64 ? "<p><img src=\"" + base + "admin/img?key=" + encodeURIComponent(f._key) + q + "\" style=\"max-width:320px;border-radius:8px\"></p>" : "") +
      "<pre class=mono style=\"white-space:pre-wrap;background:#f9fafb;padding:8px;border-radius:8px\">" + esc(f.logTail || "") + "</pre></details>";
  }
  body += "</section>";
  body += "<section><h2>赞赏（" + g.aps.length + " 笔 · 合计 ￥" + sum + "）</h2> <a class=btn href='admin/export?type=ap'>导出 CSV</a>" + tbl(["时间", "设备", "金额", "版本", "联系"],
    g.aps.slice(0, 300).map(a => [esc(a.ts), "<span class=mono>" + esc(a.device || "-") + "</span>", "￥" + (a.amount || 0), esc(a.version || "-"), esc(a.contact || "-")])) + "</section>";
  body += "<p class=muted>页面每 60 秒自动刷新（正在输入时不刷新）。数据来自 KV，最多显示各表前 300 行。</p></div>";
  body += "<script>" +
    "setTimeout(function(){var a=document.activeElement;if(!a||(a.tagName!=='INPUT'&&a.tagName!=='TEXTAREA'))location.reload();},60000);" +
    "</script>";
  return shell("c3shell 后台", body);
}

async function act(env, u, req, form) {
  const doWhat = (form ? form.get("do") : u.searchParams.get("do")) || "";
  const tok = (form ? form.get("tok") : u.searchParams.get("token")) || "";
  const code = ((form ? form.get("code") : u.searchParams.get("code")) || "").toUpperCase();
  const qs = tok ? "?token=" + encodeURIComponent(tok) : "";
  if (doWhat === "mint") {
    const r = await mint(env, { count: form.get("count"), days: form.get("days"), plan: form.get("plan"), maxDevices: form.get("maxDevices") });
    const codes = (r[1].codes || []).join("  ");
    return new Response(null, { status: 303, headers: Object.assign({ Location: "../admin" + qs + (qs ? "&" : "?") + "minted=" + encodeURIComponent(codes) }, CORS) });
  }
  if (doWhat === "feats") {
    const dv = (form ? form.get("device") : u.searchParams.get("device")) || "__default";
    const list = form ? form.getAll("features").map(String) : [];
    await featSet(env, dv, list, (form ? form.get("note") : "") || "");
  }
  if (doWhat === "renew" && code) {
    const raw = await CARDS.get("card:" + code);
    if (raw) {
      const c = JSON.parse(raw);
      const dstr = (form ? form.get("days") : u.searchParams.get("days")) || "365";
      const days = parseInt(dstr, 10);
      const baseMs = c.expiresAt && c.expiresAt > now() ? Date.parse(c.expiresAt.replace(" ", "T") + "Z") : Date.now();
      c.expiresAt = days > 0 ? new Date(baseMs + days * 86400000).toISOString().replace("T", " ").slice(0, 19) : "";
      c.renewed = now();
      await CARDS.put("card:" + code, JSON.stringify(c));
    }
  }
  if (doWhat === "delcard" && code) await CARDS.delete("card:" + code);
  if (doWhat === "unbind" && code) { const ks = await kvAll(env, "bind:" + code + ":"); for (const k of ks) await CARDS.delete(k); }
  if (doWhat === "deldev") await CARDS.delete("dev:" + (u.searchParams.get("device") || ""));
  if (doWhat === "delfb") await CARDS.delete(u.searchParams.get("key") || "");
  return new Response(null, { status: 303, headers: Object.assign({ Location: "../admin" + qs }, CORS) });
}

async function exportCsv(env, u) {
  const g = await gather(env);
  const type = u.searchParams.get("type") || "cards";
  let rows = [];
  if (type === "cards") { rows.push(["code", "plan", "expiresAt", "maxDevices", "created"]); for (const c of g.cards) rows.push([(c._key || "").slice(5), c.plan || "", c.expiresAt || "", c.maxDevices || 1, c.created || ""]); }
  else if (type === "devices") { rows.push(["device", "code", "version", "first", "last", "count"]); for (const d of g.devs) rows.push([(d._key || "").slice(4), d.code || "", d.version || "", d.first || "", d.ts || "", d.count || 1]); }
  else if (type === "fb") { rows.push(["ts", "device", "version", "contact", "text"]); for (const f of g.fbs) rows.push([f.ts || "", f.device || "", f.version || "", f.contact || "", String(f.text || "").replace(/[",]/g, " ")]); }
  else if (type === "ap") { rows.push(["ts", "device", "amount", "version", "contact"]); for (const a of g.aps) rows.push([a.ts || "", a.device || "", a.amount || 0, a.version || "", a.contact || ""]); }
  const csv = rows.map(r => r.map(x => "\"" + String(x).replace(/"/g, "\"\"") + "\"").join(",")).join("\n");
  return new Response(csv, { status: 200, headers: Object.assign({ "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": "attachment; filename=" + type + "-" + today() + ".csv" }, CORS) });
}

async function adminImg(env, u) {
  const key = u.searchParams.get("key") || "";
  const raw = key ? await CARDS.get(key) : null;
  if (!raw) return new Response("no image", { status: 404 });
  const b64 = (JSON.parse(raw).imgB64 || "").split(",").pop();
  if (!b64) return new Response("no image", { status: 404 });
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  return new Response(bin, { status: 200, headers: { "Content-Type": "image/jpeg", "Cache-Control": "private, max-age=600" } });
}

async function adminArea(req, env, u, seg, prev) {
  const user = await sessUser(env, req);
  const tok = u.searchParams.get("token") || "";
  const tokOk = !!(TOKEN && tok === TOKEN);
  const authed = !!user || tokOk;
  if (prev === "admin") {
    if (seg === "login") {
      if (req.method !== "POST") return H(loginPage(""), 200);
      let form = null;
      try { form = await req.formData(); } catch (e) { form = new FormData(); }
      const okUser = String(form.get("user") || "") === String(ADMIN_USER || "admin");
      const okPass = String(form.get("pass") || "") === String(ADMIN_PASS || "");
      if (!ADMIN_PASS) return H(loginPage("服务器还没设置 ADMIN_PASS（请在 Worker 变量里添加）"), 200);
      if (!(okUser && okPass)) return H(loginPage("用户名或密码不对"), 401);
      const s = await sessMake(env, String(ADMIN_USER || "admin"));
      return new Response(null, { status: 303, headers: Object.assign({ Location: "../admin", "Set-Cookie": "c3sess=" + s + "; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800" }, CORS) });
    }
    if (seg === "logout") return new Response(null, { status: 303, headers: Object.assign({ Location: "../admin", "Set-Cookie": "c3sess=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0" }, CORS) });
    if (!authed) return H(loginPage(""), 200);
    if (seg === "act" && req.method === "POST") { let f = null; try { f = await req.formData(); } catch (e) { f = new FormData(); } return act(env, u, req, f); }
    if (seg === "act") return act(env, u, req, null);
    if (seg === "export") return exportCsv(env, u);
    if (seg === "img") return adminImg(env, u);
    if (seg === "data") return J((await stats(env))[1]);
    if (seg === "device") return H(await devicePage(env, u), 200);
  }
  if (seg === "admin") {
    if (!authed) return H(loginPage(""), 200);
    const g = await gather(env);
    const minted = u.searchParams.get("minted") || "";
    return H(dash(env, u, g, minted ? "已生成卡密：" + minted : ""), 200);
  }
  return null;
}

async function handle(req) {
    const u = new URL(req.url);
    const path = u.pathname.replace(/[/]+$/, "");
    const parts = path.split("/").filter(Boolean);
    const seg = parts.length ? parts[parts.length - 1] : "";
    const prev = parts.length > 1 ? parts[parts.length - 2] : "";
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const adm = await adminArea(req, env, u, seg, prev);
    if (adm) return adm;
    let b = {};
    if (req.method === "POST") { try { b = await req.json(); } catch (e) { b = {}; } }
    let r;
    switch (seg) {
      case "verify": case "activate": r = await verify(env, b); break;
      case "feedback": r = await feedback(env, b); break;
      case "appreciate": r = await appreciate(env, b); break;
      case "heartbeat": r = await heartbeat(env, b); break;
      case "stats": r = await stats(env); break;
      case "feat": {
        const dv = String(b.device || u.searchParams.get("device") || "");
        if (req.method === "GET") {
          if (!dv) return J({ ok: false, error: { message: "缺少 device" } }, 400);
          r = [200, await featGet(env, dv)];
        } else {
          if (!TOKEN || u.searchParams.get("token") !== TOKEN) return J({ ok: false, error: { message: "需要 token" } }, 403);
          r = [200, await featSet(env, dv || "__default", Array.isArray(b.features) ? b.features : [], b.note)];
        }
        break;
      }
      case "mint":
        if (!TOKEN || u.searchParams.get("token") !== TOKEN) return J({ ok: false, error: { message: "需要 token" } }, 403);
        r = await mint(env, b); break;
      case "": case "health": return J({ ok: true, service: "c3shell-worker", version: "v2", time: now() });
      default: r = [404, { ok: false, error: { message: "no such path: " + seg } }];
    }
    return J(r[1], r[0]);
}

addEventListener("fetch", function (event) { event.respondWith(handle(event.request)); });
