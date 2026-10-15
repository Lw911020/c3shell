p = "/storage/emulated/0/openpilot/c3shell/server/worker.js"
s = open(p).read()
def rep(old, new, must=1):
    global s
    n = s.count(old)
    assert n >= must, "锚点找不到: " + old[:60]
    s = s.replace(old, new)
    print("替换", n, "处:", old[:44].replace(chr(10), " "))

# 1) hist() 助手：每个设备一条时间线（在 kvAll 之后插入）
rep("""  } while (cursor);
  return out;
}""", """  } while (cursor);
  return out;
}

async function hist(env, dev, ev) {
  const ts = now();
  await env.CARDS.put("hist:" + dev + ":" + ts.replace(/[: ]/g, "-") + "-" + rnd(3), JSON.stringify(Object.assign({ ts: ts }, ev)));
}""")

# 2) verify 成功后记一条「激活」
rep("""  return [200, { ok: true, plan: card.plan || "", expiresAt: card.expiresAt || "" }];""",
"""  await hist(env, dev, { type: "verify", code: code, version: ver, plan: card.plan || "", expiresAt: card.expiresAt || "" });
  return [200, { ok: true, plan: card.plan || "", expiresAt: card.expiresAt || "" }];""")

# 3) 反馈记一条
rep("""  return [200, { ok: true, id: id }];""",
"""  await hist(env, dev, { type: "feedback", key: "fb:" + id, text: String(b.text || "").slice(0, 200) });
  return [200, { ok: true, id: id }];""")

# 4) 赞赏记一条
rep("""  await env.CARDS.put("ap:" + id, JSON.stringify({ ts: now(), device: b.device || "", version: b.version || "", amount: amt, contact: b.contact || "" }));""",
"""  await env.CARDS.put("ap:" + id, JSON.stringify({ ts: now(), device: b.device || "", version: b.version || "", amount: amt, contact: b.contact || "" }));
  await hist(env, String(b.device || "unknown"), { type: "appreciate", amount: amt });""")

# 5) 心跳：最多每 6 小时记一条时间线（省 KV 写入）
rep("""  await env.CARDS.put("dev:" + dev, JSON.stringify({ ts: now(), first: od.first || now(), feature: b.feature || "", hostCount: b.hostCount || 0, mode: b.mode || "", version: b.version || od.version || "", code: od.code || "", count: (od.count || 0) + 1 }));
  return [200, { ok: true }];
}""",
"""  const prevH = od.lastHist ? Date.parse(od.lastHist.replace(" ", "T") + "Z") : 0;
  const doH = !prevH || (Date.now() - prevH) > 6 * 3600000;
  await env.CARDS.put("dev:" + dev, JSON.stringify({ ts: now(), first: od.first || now(), feature: b.feature || "", hostCount: b.hostCount || 0, mode: b.mode || "", version: b.version || od.version || "", code: od.code || "", count: (od.count || 0) + 1, lastHist: doH ? now() : (od.lastHist || "") }));
  if (doH) await hist(env, dev, { type: "heartbeat", feature: b.feature || "", mode: b.mode || "" });
  return [200, { ok: true }];
}""")

# 6) act：新增续期（days=0 表示设为永久）
rep("""  if (doWhat === "delcard" && code) await env.CARDS.delete("card:" + code);""",
"""  if (doWhat === "renew" && code) {
    const raw = await env.CARDS.get("card:" + code);
    if (raw) {
      const c = JSON.parse(raw);
      const dstr = (form ? form.get("days") : u.searchParams.get("days")) || "365";
      const days = parseInt(dstr, 10);
      const baseMs = c.expiresAt && c.expiresAt > now() ? Date.parse(c.expiresAt.replace(" ", "T") + "Z") : Date.now();
      c.expiresAt = days > 0 ? new Date(baseMs + days * 86400000).toISOString().replace("T", " ").slice(0, 19) : "";
      c.renewed = now();
      await env.CARDS.put("card:" + code, JSON.stringify(c));
    }
  }
  if (doWhat === "delcard" && code) await env.CARDS.delete("card:" + code);""")

# 7) 设备详情页函数（插在 loginPage 之前）
rep("""function loginPage(err) {""",
"""async function devicePage(env, u) {
  const id = u.searchParams.get("id") || "";
  const keys = await kvAll(env, "hist:" + id + ":");
  const events = [];
  for (const k of keys) { const v = JSON.parse((await env.CARDS.get(k)) || "{}"); events.push(v); }
  events.sort((a, b) => String(b.ts || "").localeCompare(String(a.ts || "")));
  const dev = JSON.parse((await env.CARDS.get("dev:" + id)) || "{}");
  const bkeys = await kvAll(env, "bind:");
  const cards = [];
  for (const k of bkeys) { const p = k.split(":"); if (p[2] === id) { const raw = await env.CARDS.get("card:" + p[1]); if (raw) { const c = JSON.parse(raw); c._code = p[1]; cards.push(c); } } }
  const cut = new Date(Date.now() - 10 * 60000).toISOString().replace("T", " ").slice(0, 19);
  let b = "<header><h1>设备详情</h1><span class=sub>" + esc(id) + "</span><span style='flex:1'></span><a class='btn gray' href='../admin'>返回后台</a></header><div class=wrap>";
  b += "<div class=cards><div class=card><div class=k>状态</div><div class=v>" + ((dev.ts || "") >= cut ? "在线" : "离线") + "</div></div>" +
    "<div class=card><div class=k>心跳次数</div><div class=v>" + (dev.count || 0) + "</div></div>" +
    "<div class=card><div class=k>事件数</div><div class=v>" + events.length + "</div></div></div>";
  b += "<section><h2>基本信息</h2><table><tr><th>版本</th><td>" + esc(dev.version || "-") + "</td></tr><tr><th>首次</th><td>" + esc(dev.first || "-") + "</td></tr><tr><th>最近</th><td>" + esc(dev.ts || "-") + "</td></tr><tr><th>绑定卡密</th><td>" + esc(dev.code || "-") + "</td></tr></table></section>";
  b += "<section><h2>持有的卡密</h2>" + tbl(["卡密", "计划", "到期(UTC)", "台数", "创建"], cards.map(c => [esc(c._code), esc(c.plan || "-"), esc(c.expiresAt || "永久"), c.maxDevices || 1, esc(c.created || "-")])) + "</section>";
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

function loginPage(err) {""")

# 8) 后台路由：/admin/device
rep("""    if (seg === "data") return J((await stats(env))[1]);""",
"""    if (seg === "data") return J((await stats(env))[1]);
    if (seg === "device") return H(await devicePage(env, u), 200);""")

# 9) 卡密表加「续期」按钮（锚点避开反斜杠）
rep(""": "")];""",
"""": "") + " <form method=post action='admin/act' style='display:inline'><input type=hidden name=do value=renew><input type=hidden name=code value=" + code + "><input type=hidden name=tok value=" + esc(token) + "><input name=days value=365 size=3 style='width:56px'> <button class=btn style='padding:2px 8px;font-size:12px'>续期</button></form>"];""")

# 10) 设备表加「历史」链接
rep("""esc(d.ts || "-")])) + "</section>";""",
"""esc(d.ts || "-") + " <a class=btn href='admin/device?id=" + encodeURIComponent((d._key || "").slice(4)) + "'>历史</a>"])) + "</section>";""")

open(p, "w").write(s)
print("补丁全部完成")