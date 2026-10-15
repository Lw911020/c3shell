package com.padagent.c3shell;

import android.content.Context;
import java.util.Map;

/**
 * 内置 API（方案 C 第①片）：先把页面需要的接口用占位实现兜住，
 * 让 APP 能独立托管页面；SSH 相关实现（第②片）在这里逐个替换为真实现。
 */
public class Api implements Web.Api {
    /** 2026-10-05：设备端投屏是否可能还在跑（供"离开投屏页就停"的兜底判断 ✓） */
    public static volatile boolean CAST_ON = false;
    private final Context ctx;
    private final Ssh ssh;
    private final Store store;
    private final Pkg pkg;
    private final Ai ai;
    private final Local local;   // 2026-09-27 v3.00.71：本机（手机/平板）储存

    public Api(Context c) { ctx = c; ssh = new Ssh(c); store = new Store(c); pkg = new Pkg(c); ai = new Ai(c); local = new Local(c); }
    /** JSON 字符串转义（本地助手，2026-09-21 统一数据层用） */
    private static String q(String v) {
        return String.valueOf(v).replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static String ov(String body, String query, String key) { return ov(body, query, key, null); }
    private static String ov(String body, String query, String key, String def) {
        String v = jstr(body, key);
        if (v != null && v.length() > 0) return v;
        v = q(query, key);
        if (v != null && v.length() > 0) return v;
        return def;
    }
    private static String nz(String v, String def) { return (v == null || v.length() == 0) ? def : v; }

    /** 取 body 里对象字段的原始 JSON（如 values:{...}）——不引 JSON 库，靠括号配平 ✓ */
    private static String jobj(String body, String key) {
        try {
            int i = body.indexOf("\"" + key + "\"");
            if (i < 0) return null;
            int c = body.indexOf(':', i);
            int b = body.indexOf('{', c);
            if (b < 0) return null;
            int d = 0;
            for (int j = b; j < body.length(); j++) {
                char ch = body.charAt(j);
                if (ch == '{') d++;
                else if (ch == '}') { d--; if (d == 0) return body.substring(b, j + 1); }
            }
        } catch (Throwable ignore) { }
        return null;
    }

    /** 数一个 JSON 对象的顶层键值对个数（≈参数项数；只用于显示 ✓） */
    private static int jobjCount(String obj) {
        if (obj == null) return 0;
        int d = 0, n = 0;
        for (int i = 0; i < obj.length(); i++) {
            char c = obj.charAt(i);
            if (c == '{' || c == '[') d++;
            else if (c == '}' || c == ']') d--;
            else if (c == ':' && d == 1) n++;
        }
        return n;
    }

    /** 把档案顺手镜像一份到 C3 设备（best-effort：失败不影响主流程，也不阻塞响应） */
    private void mirrorProfiles(final String slot, final String json) {
        new Thread(new Runnable() { public void run() {
            try {
                Store.Host d = store.defaultHost();
                String b64 = android.util.Base64.encodeToString(json.getBytes("UTF-8"), android.util.Base64.NO_WRAP);
                String cmd = "mkdir -p /data/openpilot/dsh-profiles && echo " + b64
                           + " | base64 -d > /data/openpilot/dsh-profiles/" + slot + ".json";
                ssh.execJson(cmd, d == null ? null : d.host, d == null ? 22 : d.port,
                             d == null ? null : d.user, d == null ? null : d.key);
            } catch (Throwable ignore) { }
        }}).start();
    }
    static String shqPair(String v) { return "'" + (v == null ? "" : v.replace("'", "'\\''")) + "'"; }

    /* 2026-09-25 用户澄清：卡密要绑 **C3 设备码**（不是手机/平板的）✓
       → 同一台 C3，手机、车机都能用 ✓；换 C3 才需要换卡 ✓
       取法（多个来源依次兜底，只要有一个稳定就行）：
         Params 里的 DongleId → /persist/comma/dongle_id → hostname 去掉 comma- 前缀 → SoC 序列号 ✓
       输出统一带 "C3ID:" 前缀，方便在有杂音的输出里精确截取 ✓ */
    private String c3Query() {
        try {
            Store.Host d = store.defaultHost();
            /* 2026-10-05：**刷机后没在 comma 注册的 C3，DongleId 就是占位串 "UnregisteredDevice"** ✗
               （这台的实测值就是它）→ 必须跳过，否则所有未注册机器都拿到同一个"设备码"，一张卡到处用 ✗
               跳过之后依次用 hostname / SoC 序列号兜底 ✓ */
            String cmd = "D=$(cat /data/params/d/DongleId 2>/dev/null | tr -d '\\r\\n'); "
                       + "[ \"$D\" = UnregisteredDevice ] && D=; "
                       + "[ -n \"$D\" ] || D=$(cat /persist/comma/dongle_id 2>/dev/null | tr -d '\\r\\n'); "
                       + "[ \"$D\" = UnregisteredDevice ] && D=; "
                       + "[ -n \"$D\" ] || D=$(hostname 2>/dev/null | sed 's/^comma-//'); "
                       + "[ -n \"$D\" ] || D=$(cat /sys/devices/soc0/serial_number 2>/dev/null | tr -d '\\r\\n'); "
                       + "echo C3ID:$D";
            String res = ssh.execJson(cmd, d == null ? null : d.host, d == null ? 22 : d.port,
                                      d == null ? null : d.user, d == null ? null : d.key);
            /* 2026-10-05 修（用户报「激活授权里读取 C3 设备码失败，明明已联机」）：
               execJson 返回的是 {"ok":true,"result":{...,"stdout":"…"}} —— 字段叫 **stdout**，
               这里原来写成 jstr(res,"out") → 永远取不到 → 直接判「没读到」✗（连上了也读不出）
               → 实测：/api/ssh/exec 同样命令能拿到 stdout，证明链路没问题，就是这个字段名 ✗ */
            String out = jstr(res, "stdout");
            if (out == null) return "";
            int i = out.indexOf("C3ID:");
            if (i < 0) return "";
            String v = out.substring(i + 5).trim();
            int nl = v.indexOf('\n');
            if (nl > 0) v = v.substring(0, nl);
            v = v.replace("\r", "").replace("\n", "").trim();
            if (v.length() == 0 || v.equals("$D")) return "";
            if (v.equalsIgnoreCase("UnregisteredDevice")) return "";    // 兜底：占位串不算设备码 ✓
            return v;
        } catch (Throwable t) { return ""; }
    }

    // 极简 JSON 取值（这套 android.jar 没有 org.json）
    static String jstr(String body, String key) {
        if (body == null) return null;
        String pat = "\"" + key + "\"";
        int i = body.indexOf(pat);
        if (i < 0) return null;
        int c = body.indexOf(':', i + pat.length());
        if (c < 0) return null;
        // 2026-09-24 R81（真根因）：值必须以**引号**开头才算字符串 ✓
        //   原来直接取"冒号后第一个引号" → 对 {"limit":-1,"hostId":"c3"} 会把 hostId 当 limit 的值 ✗
        //   → parseInt("hostId") 失败 → 回落默认值 6 → "选最近 1 天还是扫 6 条" 的真根因 ✗✗
        //   （R79 的负数分支因此根本没被执行到；R79 保留，数字解析仍靠它 ✓）
        int p = c + 1; while (p < body.length() && " \t".indexOf(body.charAt(p)) >= 0) p++;
        if (p >= body.length() || body.charAt(p) != '"') return null;
        int q1 = p;
        StringBuilder sb = new StringBuilder();
        for (int k = q1 + 1; k < body.length(); k++) {
            char ch = body.charAt(k);
            if (ch == '\\') {
                k++;
                if (k < body.length()) {
                    char nx = body.charAt(k);
                    if (nx == 'n') sb.append('\n');
                    else if (nx == 't') sb.append('\t');
                    else if (nx == 'r') sb.append('\r');
                    else sb.append(nx);
                }
                continue;
            }
            if (ch == '"') break;
            sb.append(ch);
        }
        return sb.toString();
    }
    static int jint(String body, String key, int def) {
        String v = jstr(body, key);
        if (v == null) {
            try {
                int i = body == null ? -1 : body.indexOf("\"" + key + "\"");
                // 2026-09-24 R79：**负数也要认**！原来只扫数字 → "-1" 解析成空串抛异常 → 回落默认值 ✗
                //   （这就是"选最近 1 天却按 limit=6 扫"的根因）
                if (i >= 0) { int c = body.indexOf(':', i); if (c >= 0) {
                    int j = c + 1; while (j < body.length() && " \t".indexOf(body.charAt(j)) >= 0) j++;
                    int e = j; if (e < body.length() && (body.charAt(e) == '-' || body.charAt(e) == '+')) e++;
                    int d0 = e; while (e < body.length() && Character.isDigit(body.charAt(e))) e++;
                    if (e > d0) return Integer.parseInt(body.substring(j, e));
                } }
            } catch (Throwable ignore) { }
            return def;
        }
        try { return Integer.parseInt(v); } catch (Throwable e) { return def; }
    }

    public String sendToTerm(String text) { return ssh.sendToTerm(text); }

    public boolean stream(java.net.Socket sock, String method, String path, String query, Map<String, String> headers) throws Exception {
        if (path.equals("/api/ssh/term/stream")) {
            return ssh.termStream(sock, q(query, "sessionId"));
        }
        if (path.equals("/api/ssh/live/stream")) {
            return ssh.liveStream(sock, q(query, "sessionId"));
        }
        return false;
    }
    private static int qint(String query, String k, int def) {
        String v = q(query, k);
        if (v == null) return def;
        try { return Integer.parseInt(v.trim()); } catch (Throwable e) { return def; }
    }
    private static String q(String query, String k) {
        if (query == null) return null;
        for (String kv : query.split("&")) { int i = kv.indexOf('='); if (i > 0 && kv.substring(0, i).equals(k)) { try { return java.net.URLDecoder.decode(kv.substring(i + 1), "UTF-8"); } catch (Throwable e) { return kv.substring(i + 1); } } }
        return null;
    }

    public String handle(String method, String path, String query, String body, Map<String, String> headers) {
        /* 2026-10-05：页面的 api()/c3api() 会**自动加 /api/ssh 前缀** —— 页面里若写的是
           「已经带前缀的路径」（如 /api/ssh/exec）或「不带 /api/ssh 的模块路径」（如 /cast/provision），
           真实请求就变成 /api/ssh/ssh/exec、/api/ssh/cast/provision → 全部落进末尾的
           「APP 内置版还没实现该接口」兜底，0ms 失败 ✗（用户报的「投屏能力安装失败」正是此坑）。
           这里把两类错位地址统一掰回来：① 重复前缀去掉一层 ② cast/float 归到 /api/ 下。
           页面侧也已改成直连，双保险（老页面/连接器页面/第三方调用同样受益）✓ */
        if (path != null) {
            if (path.startsWith("/api/ssh/ssh/")) path = "/api/ssh/" + path.substring(13);
            else if (path.startsWith("/api/ssh/cast/") || path.startsWith("/api/ssh/float/")) path = "/api/" + path.substring(9);
        }
        if (path.equals("/api/ssh/state")) {
            return store.hostsJson();          // 主机配置存在 APP 本地（手机存储）
        }
        if (path.equals("/api/ssh/hosts")) {
            String action = jstr(body, "action");
            if ("delete".equals(action)) { store.deleteHost(jstr(body, "id")); return store.hostsJson(); }
            if ("default".equals(action)) { store.setDefault(jstr(body, "id")); return store.hostsJson(); }
            // 2026-09-22：纯 GET（没有 action）就是"列出主机" —— 必须在下面的 upsert 校验之前返回，
            // 否则空 body 会被"地址必填"拦掉（2.56 踩过这个坑：GET /hosts 直接报 bad_host ✗）
            if (action == null || action.length() == 0) return store.hostsJson();
            String hs = body == null ? "" : body;
            // 2026-09-22 修：原来写死 "\"host\":{" —— 只要 JSON 里冒号/大括号之间有一个空格就找不到，
            // 于是整串 body 被当成字段源，jstr 把 "id" 的值当成了地址 ✗。改为容错扫描（允许空白）。
            int hi = hs.indexOf("\"host\"");
            if (hi >= 0) {
                int c2 = hs.indexOf(':', hi + 6);
                if (c2 >= 0) { int b2 = hs.indexOf('{', c2 + 1);
                    if (b2 >= 0) hs = hs.substring(b2 + 1); }
            }
            Store.Host h = new Store.Host();
            h.id = nz(jstr(hs, "id"), "host" + (store.hosts().size() + 1));
            h.label = nz(jstr(hs, "label"), h.id);
            h.host = nz(jstr(hs, "host"), "");
            h.port = jint(hs, "port", 22);
            h.user = nz(jstr(hs, "user"), "comma");
            h.key = nz(jstr(hs, "keyPath"), "");
            h.note = nz(jstr(hs, "note"), "");
            h.mode = nz(jstr(hs, "mode"), "ssh");
            if (h.host == null || h.host.length() == 0) {     // 2026-09-22：地址必填（此前空地址也能存进去 ✗）
                return "{\"ok\":false,\"error\":{\"code\":\"bad_host\",\"message\":\"地址必填（保存主机需要地址）\"}}";
            }
            store.upsertHost(h);
            return store.hostsJson();
        }
        if (path.equals("/api/ssh/key")) {
            // 页面用它列密钥信息（独立版：返回内置密钥位目录 + 列表）
            return "{\"ok\":true,\"path\":\"" + Ssh.esc(store.keysDir().getAbsolutePath()) + "\",\"exists\":true,\"named\":" + store.keysJson() + "}";
        }
        if (path.equals("/api/ssh/key/named")) {
            String action = jstr(body, "action");
            if ("meta".equals(action)) { store.setKeyMeta(nz(jstr(body, "key"), jstr(body, "name")), nz(jstr(body, "name"), ""), nz(jstr(body, "note"), "")); return store.keysJson(); }
            if ("delete".equals(action)) { store.deleteKey(nz(jstr(body, "name"), jstr(body, "key"))); return store.keysJson(); }
            String nm = jstr(body, "name"), ct = jstr(body, "content");
            if (nm != null && ct != null && ct.length() > 0) { store.saveKey(nm, ct); return store.keysJson(); }
            return store.keysJson();
        }
        if (path.equals("/api/ssh/license")) {
            Lic lic = new Lic(ctx);
            String action = jstr(body, "action");
            if ("activate".equals(action)) return lic.activate(jstr(body, "code"));
            if ("clear".equals(action)) return lic.clear();
            if ("endpoint".equals(action)) return lic.setEndpoint(jstr(body, "endpoint"));
            if ("features".equals(action)) return lic.setFeatures(jstr(body, "features"));
            if ("uifeats".equals(action)) return lic.setUiFeats(jstr(body, "features"));   // 2026-10-03：开发者功能开关（界面显示哪些页签/入口）
            if ("heartbeat".equals(action)) return lic.heartbeat(nz(jstr(body, "feature"), ""), jint(body, "hosts", 0), nz(jstr(body, "mode"), ""));
            /* 2026-09-24 上线三件套：看统计 / 上传反馈 / 存联系方式 ✓ */
            if ("rfeats".equals(action)) return lic.remoteFeats();   // 2026-10-03：远端功能开关（服务器下发）
            if ("stats".equals(action)) return lic.stats();
            if ("contact".equals(action)) return lic.setContact(jstr(body, "contact"));
            if ("feedback".equals(action)) return lic.feedback(jstr(body, "text"), jstr(body, "logText"), jstr(body, "imageB64"));
            if ("appreciate".equals(action)) return lic.appreciate(jstr(body, "amount"));   // 2026-09-24：赞赏登记（>20）
            /* 2026-09-24 离线签名卡密：只看不写（核对卡密用，激活走 activate ✓） */
            if ("inspect".equals(action)) return lic.inspectCard(jstr(body, "card"));
            /* C3 设备码：现场读 / 手动填（读不到时也能让买家自己填 ✓）*/
            if ("c3code".equals(action)) {
                String c3 = c3Query();
                if (c3.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"没读到 C3 设备码：先确认能连上 C3（「测试连接」），或手动填一下 ✓\"}}";
                lic.setC3(c3);
                return lic.statusJson();
            }
            if ("c3set".equals(action)) return lic.setC3(jstr(body, "c3"));
            return lic.statusJson();
        }
        if (path.equals("/api/ssh/test")) {
            // 2026-09-24 R2：按页面"选中的主机"测试（此前只认默认主机 → 手动保存/切换的主机永远测不到 ✗）
            Store.Host d = store.hostById(jstr(body, "hostId")); return ssh.testJson(ov(body, query, "host", d == null ? null : d.host), qint(query, "port", jint(body, "port", d == null ? 22 : d.port)), ov(body, query, "user", d == null ? null : d.user), nz(jstr(body, "key"), d == null ? null : d.key), jstr(body, "password"));
        }
        if (path.equals("/api/ssh/exec")) {
            String cmd = jstr(body, "command");
            if (cmd == null) return "{\"ok\":false,\"error\":{\"message\":\"command required\"}}";
            Store.Host d2 = store.hostById(jstr(body, "hostId")); return ssh.execJson(cmd, ov(body, query, "host", d2 == null ? null : d2.host), qint(query, "port", jint(body, "port", d2 == null ? 22 : d2.port)), ov(body, query, "user", d2 == null ? null : d2.user), nz(jstr(body, "key"), d2 == null ? null : d2.key));
        }
        if (path.equals("/api/ssh/term/open")) {
            Store.Host d3 = store.hostById(jstr(body, "hostId")); return ssh.openTermJson(ov(body, query, "host", d3 == null ? null : d3.host), qint(query, "port", jint(body, "port", d3 == null ? 22 : d3.port)), ov(body, query, "user", d3 == null ? null : d3.user), nz(jstr(body, "key"), d3 == null ? null : d3.key), jint(body, "cols", 120), jint(body, "rows", 34));
        }
        if (path.equals("/api/ssh/term/current")) {
            ssh.setLastTerm(jstr(body, "sessionId"));
            return "{\"ok\":true,\"current\":\"" + ssh.lastTermId() + "\"}";
        }
        if (path.equals("/api/ssh/term/tail")) return ssh.termTail(q(query, "sessionId"), q(query, "since"));
        if (path.equals("/api/ssh/term/send")) {
            return ssh.sendToTerm(jstr(body, "text"));
        }
        if (path.equals("/api/ssh/term/input")) {
            return ssh.inputJson(jstr(body, "sessionId"), jstr(body, "data"));
        }
        if (path.equals("/api/ssh/term/close")) {
            ssh.closeTerm(jstr(body, "sessionId"));
            return "{\"ok\":true}";
        }
        if (path.equals("/api/ssh/ls")) {
            return ssh.lsJson(q(query, "path"));
        }
        if (path.equals("/api/ssh/fs")) {   // 2026-09-24：文件页的改名/删除/新建文件夹（独立版此前没实现 ✗）
            Store.Host df = store.hostById(jstr(body, "hostId"));
            return ssh.fsOpJson(jstr(body, "op"), jstr(body, "path"), jstr(body, "to"),
                    ov(body, query, "host", df == null ? null : df.host),
                    qint(query, "port", jint(body, "port", df == null ? 22 : df.port)),
                    ov(body, query, "user", df == null ? null : df.user),
                    nz(jstr(body, "key"), df == null ? null : df.key));
        }
        if (path.equals("/api/ssh/read")) {
            return ssh.readJson(q(query, "path"));
        }
        /* ---------- 本机储存 + 设备⇄本机 传输（2026-09-27 v3.00.71，用户要求）----------
           需求：控制台「文件」页要有**复制 / 移动**，并且**可以选本机储存** ✓
           本机侧只用 java.io.File（编译桩里都有 ✓）；设备⇄本机走 JSch SFTP 流式（不走 base64 ✓） */
        /* 2026-09-27 v3.00.74：页面的 api() 会自动加前缀 /api/ssh —— 实测报错就是 `/api/ssh/local/ls` ✗
           → **两个路径都接受**（/api/local/* 与 /api/ssh/local/*），免得再踩一次 ✓ */
        if (path.equals("/api/local/roots") || path.equals("/api/ssh/local/roots")) return local.rootsJson();
        if (path.equals("/api/local/ls") || path.equals("/api/ssh/local/ls")) return local.listJson(q(query, "path"));
        if (path.equals("/api/local/op") || path.equals("/api/ssh/local/op")) return local.opJson(jstr(body, "op"), jstr(body, "path"), jstr(body, "to"));
        if (path.equals("/api/local/grant") || path.equals("/api/ssh/local/grant")) {
            // 「所有文件访问」设置页（Android 11+ 才能全盘读写 /storage/emulated/0 ✓）
            try {
                android.content.Intent i = new android.content.Intent("android.settings.MANAGE_APP_ALL_FILES_ACCESS_PERMISSION");
                i.setData(android.net.Uri.parse("package:" + ctx.getPackageName()));
                i.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(i);
                return "{\"ok\":true}";
            } catch (Throwable t1) {
                try {
                    android.content.Intent i2 = new android.content.Intent("android.settings.MANAGE_ALL_FILES_ACCESS_PERMISSION");
                    i2.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
                    ctx.startActivity(i2);
                    return "{\"ok\":true}";
                } catch (Throwable t2) {
                    return "{\"ok\":false,\"error\":{\"message\":\"这台设备没有该设置页；请到 系统设置 → 应用 → 特殊权限 里给本应用「所有文件访问」\"}}";
                }
            }
        }
        if (path.equals("/api/xfer") || path.equals("/api/ssh/xfer")) {
            Store.Host df = store.hostById(jstr(body, "hostId"));
            return ssh.xferJson(jstr(body, "dir"), jstr(body, "remote"), jstr(body, "local"),
                    ov(body, query, "host", df == null ? null : df.host),
                    qint(query, "port", jint(body, "port", df == null ? 22 : df.port)),
                    ov(body, query, "user", df == null ? null : df.user),
                    nz(jstr(body, "key"), df == null ? null : df.key));
        }
        if (path.equals("/api/ssh/savedir")) {
            String dn = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE).getString("saveDirName", "");
            return "{\"ok\":true,\"dir\":\"" + q(dn.length() > 0 ? dn : "下载（默认）") + "\"}";
        }
        if (path.equals("/api/ssh/save")) {
            // 2026-09-22：页面「导出 CSV / 快照 CSV」走这里。
            // 原来只有连接器实现了 /save ✗ → APP 里点了退回浏览器下载、而 WebView 下载被拦 → 看着"没反应" ✗
            String name = nz(jstr(body, "filename"), "export-" + System.currentTimeMillis() + ".csv");
            name = name.replaceAll("[\\\\/:*?\"<>|]", "_");
            if (name.length() > 120) name = name.substring(name.length() - 120);
            String text = nz(jstr(body, "text"), "");
            byte[] bytes;
            try { bytes = ("\uFEFF" + text).getBytes("UTF-8"); }   // BOM：Excel 打开中文表头不乱码
            catch (Throwable t) { bytes = text.getBytes(); }
            String where = null;
            // ① 用户自选的导出目录（系统目录选择器给的 tree URI；DocumentsContract 在编译桩里没有 → 反射）
            try {
                String tree = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE).getString("saveDirUri", "");
                if (tree != null && tree.length() > 0) {
                    Class<?> dc = Class.forName("android.provider.DocumentsContract");
                    java.lang.reflect.Method m = dc.getMethod("createDocument",
                            android.content.ContentResolver.class, android.net.Uri.class, String.class, String.class);
                    android.net.Uri doc = (android.net.Uri) m.invoke(null, ctx.getContentResolver(),
                            android.net.Uri.parse(tree), "text/csv", name);
                    if (doc != null) {
                        java.io.OutputStream os = ctx.getContentResolver().openOutputStream(doc);
                        os.write(bytes); os.flush(); os.close();
                        String dn = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE).getString("saveDirName", "所选目录");
                        where = dn + "/" + name;
                    }
                }
            } catch (Throwable ignore) { }
            // ② 没设自选目录（或失败）→ 系统「下载」目录
            if (where == null) try {
                Class<?> dl = Class.forName("android.provider.MediaStore$Downloads");
                android.net.Uri ext = (android.net.Uri) dl.getField("EXTERNAL_CONTENT_URI").get(null);
                android.content.ContentValues cv = new android.content.ContentValues();
                cv.put("_display_name", name);
                cv.put("mime_type", "text/csv");
                try { cv.put("relative_path", "Download/"); } catch (Throwable ignore) { }
                android.net.Uri item = ctx.getContentResolver().insert(ext, cv);
                if (item != null) {
                    java.io.OutputStream os = ctx.getContentResolver().openOutputStream(item);
                    os.write(bytes); os.flush(); os.close();
                    where = "下载/" + name;
                }
            } catch (Throwable ignore) { }
            if (where == null) {   // ③ 退路：APP 外部目录
                try {
                    java.io.File d = ctx.getExternalFilesDir(null);
                    if (d == null) d = ctx.getFilesDir();
                    java.io.File f = new java.io.File(d, name);
                    java.io.FileOutputStream fo = new java.io.FileOutputStream(f);
                    fo.write(bytes); fo.flush(); fo.close();
                    where = f.getAbsolutePath();
                } catch (Throwable t) {
                    return "{\"ok\":false,\"error\":{\"message\":\"" + q(String.valueOf(t)) + "\"}}";
                }
            }
            return "{\"ok\":true,\"path\":\"" + q(where) + "\",\"bytes\":" + bytes.length + "}";
        }
        if (path.equals("/api/ssh/write")) {
            return ssh.writeJson(jstr(body, "path"), jstr(body, "b64"));
        }
        if (path.equals("/api/ssh/profiles")) {
            // 2026-09-22：参数档案（A–H/Z）。APP 原来没实现 ✗ → 页面「保存」只写本地缓存、"存到机器"必失败
            // 存储：SharedPreferences 每档一个 key（不用 JSON 库 ✓）；同时 best-effort 镜像到 C3 设备 ✓
            android.content.SharedPreferences sp = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE);
            String[] SLOTS = { "A", "B", "C", "D", "E", "F", "G", "H", "Z" };
            if (!"POST".equalsIgnoreCase(method)) {
                StringBuilder sb = new StringBuilder();
                for (String sl : SLOTS) {
                    String rec = sp.getString("prof:" + sl, null);
                    if (rec == null || rec.length() == 0) continue;
                    if (sb.length() > 0) sb.append(",");
                    sb.append("\"").append(sl).append("\":").append(rec);
                }
                return "{\"ok\":true,\"file\":\"APP 内置存档（随 APP，卸载会丢）\",\"remoteDir\":\"/data/openpilot/dsh-profiles\","
                     + "\"profiles\":{" + sb.toString() + "}}";
            }
            String slot = nz(jstr(body, "slot"), "");
            if (slot.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"slot required\"}}";
            if ("delete".equalsIgnoreCase(nz(jstr(body, "action"), "save"))) {
                sp.edit().remove("prof:" + slot).commit();
                mirrorProfiles(slot, "{\"deleted\":true}");
                return "{\"ok\":true,\"slot\":\"" + q(slot) + "\"}";
            }
            String values = jobj(body, "values"); if (values == null) values = "{}";
            String note = nz(jstr(body, "note"), "");
            int count = jobjCount(values);              // 2026-09-22：自己数，避免客户端 jint 解析不到 ✓
            if (count == 0) count = jint(body, "count", 0);
            String t = new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss").format(new java.util.Date());
            String rec = "{\"t\":\"" + q(t) + "\",\"note\":\"" + q(note) + "\",\"count\":" + count + ",\"p\":" + values + "}";
            sp.edit().putString("prof:" + slot, rec).commit();
            mirrorProfiles(slot, rec);
            return "{\"ok\":true,\"slot\":\"" + q(slot) + "\",\"count\":" + count + ",\"note\":\"" + q(note) + "\"}";
        }
        if (path.equals("/api/ssh/env")) return ssh.envJson();   // SP 适配：系统版本 + 能力探测（2026-09-24）
        if (path.equals("/api/ssh/params/all")) {
            return ssh.paramsAllJson("1".equals(q(query, "force")));
        }
        if (path.equals("/api/ssh/params/apply")) {
            // 页面「应用」传 { values: {K:V,…} } → 拼成 set 的 K=V（整对交给 shell 引号）
            StringBuilder pairs = new StringBuilder();
            if (body != null) {
                int vi = body.indexOf("\"values\"");
                String vs = vi >= 0 ? body.substring(vi + 8) : body;
                int br = vs.indexOf('{');
                if (br >= 0) vs = vs.substring(br + 1);
                int p2 = 0;
                while (true) {
                    int q1 = vs.indexOf('"', p2);
                    if (q1 < 0) break;
                    int q2 = vs.indexOf('"', q1 + 1);
                    if (q2 < 0) break;
                    int c = vs.indexOf(':', q2);
                    if (c < 0) break;
                    int v1 = vs.indexOf('"', c + 1);
                    if (v1 < 0) break;
                    int v2 = vs.indexOf('"', v1 + 1);
                    if (v2 < 0) break;
                    String k = vs.substring(q1 + 1, q2);
                    String v = vs.substring(v1 + 1, v2);
                    if (k.length() > 0 && !k.equals("values")) {
                        if (pairs.length() > 0) pairs.append(' ');
                        pairs.append(shqPair(k + "=" + v));
                    }
                    p2 = v2 + 1;
                }
            }
            return ssh.paramsSetJson(pairs.toString());
        }
        if (path.equals("/api/ssh/params/set")) {
            String pairs = jstr(body, "pairs");
            return ssh.paramsSetJson(pairs == null ? "" : pairs);
        }
        if (path.equals("/api/ssh/live/start")) {
            boolean fast = body != null && body.indexOf("\"fast\":true") >= 0;
            return ssh.liveStart(nz(jstr(body, "replay"), ""), jint(body, "hz", 10), fast, jint(body, "seconds", 0));
        }
        if (path.equals("/api/ssh/live/status")) {
            return ssh.liveStatus();
        }
        if (path.equals("/api/ssh/live/stop")) {
            return ssh.liveStop(jstr(body, "sessionId"));
        }
        if (path.equals("/api/ssh/routes/scan/start")) {
            int lim = jint(body, "limit", 6);
            Logs.add("AI", "scan/start body=" + (body == null ? "null" : body.substring(0, Math.min(120, body.length()))) + " => lim=" + lim);
            return ssh.routesScanStart(nz(jstr(body, "root"), "/data/media/0/realdata"), lim);
        }
        if (path.equals("/api/ssh/routes/scan/status")) {
            return ssh.routesScanStatus();
        }
        if (path.equals("/api/ssh/routes/scan")) {
            // 2026-09-22：qlog 分诊扫描（limit 默认 6 条最新，够快；0 = 全扫）
            int lim = jint(body, "limit", 6);
            boolean seg = body != null && body.indexOf("\"segments\":true") >= 0;
            String root = nz(jstr(body, "root"), "/data/media/0/realdata");
            return ssh.routesScanJson(root, lim, seg);
        }
        if (path.equals("/api/cast/provision")) return ssh.castProvision(jstr(body, "action"));   // 2026-09-24：一键装投屏钩子
        /* 2026-10-05 安全：投屏编码会吃 C3 单核 60%+，实测把 openpilot 拖出「进程间通信问题/立即接管控制」✗
           这里只记"可能还在跑"的状态，供 MainActivity 在离开投屏页时做兜底停（避免每次翻页都白跑一趟 SSH）✓ */
        if (path.equals("/api/cast/start")) { CAST_ON = true;  return ssh.castJson("start"); }    // v1.7 #1 投屏 ✓
        if (path.equals("/api/cast/stop"))  { CAST_ON = false; return ssh.castJson("stop"); }
        if (path.equals("/api/cast/status")) return ssh.castJson("status");
        if (path.equals("/api/float/start")) {   // v1.7 #2 可靠控制 ✓
            try { ctx.startService(new android.content.Intent(ctx, FloatWin.class)); } catch (Throwable t) { }
            return "{\"ok\":true,\"running\":" + FloatWin.RUNNING + "}";
        }
        if (path.equals("/api/float/stop")) {
            try { ctx.stopService(new android.content.Intent(ctx, FloatWin.class)); } catch (Throwable t) { }
            return "{\"ok\":true}";
        }
        if (path.equals("/api/float/status")) {   // 状态：跑没跑 / 是否避让 / 前台是谁 / 辅助功能通不通 ✓
            return "{\"ok\":true,\"running\":" + FloatWin.RUNNING + ",\"hidden\":" + FloatWin.HIDDEN
                 + ",\"avoided\":" + FloatWin.AVOIDED + ",\"a11y\":" + FloatA11y.connected
                 + ",\"fg\":\"" + FloatWin.LASTFG + "\",\"a11yInfo\":\"" + FloatA11y.INFO + "\"}";
        }
        if (path.equals("/api/ssh/routes")) {
            return ssh.routesJson(q(query, "root"));
        }
        if (path.equals("/api/ssh/prefs")) {
            android.content.SharedPreferences sp = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE);
            if (method.equals("POST")) {
                String v = jstr(body, "voice");
                if (v != null) {
                    boolean on = !"off".equals(v);
                    sp.edit().putBoolean("voice", on).commit();
                    try {
                        if (on) ctx.startService(new android.content.Intent(ctx, SpeechService.class));
                        else ctx.stopService(new android.content.Intent(ctx, SpeechService.class));
                    } catch (Throwable ignore) { }
                }
                String dm = jstr(body, "displayMode");        // 2026-09-21 还债 A4：显式显示模式
                if (dm != null) sp.edit().putString("displayMode", dm).commit();
                String tk = jstr(body, "token");
                if (tk != null) sp.edit().putString("token", tk).commit();
                String thp = jstr(body, "theme");
                if (thp != null && thp.length() > 0) sp.edit().putString("theme", thp).commit();   // 经典主题（外壳也跟随 ✓）
            }
            return "{\"ok\":true,\"theme\":\"" + q(String.valueOf(sp.getString("theme", "light"))) + "\",\"displayMode\":\"" + String.valueOf(sp.getString("displayMode", "auto")) + "\",\"voice\":" + sp.getBoolean("voice", true)
                    + ",\"token\":\"" + Ssh.esc(sp.getString("token", "")) + "\"}";
        }
        if (path.equals("/api/ssh/ai/config")) {
            if (method.equals("POST")) {
                android.content.SharedPreferences sp = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE);
                if (jstr(body, "endpoint") != null) sp.edit().putString("aiEndpoint", jstr(body, "endpoint")).apply();
                if (jstr(body, "model") != null) sp.edit().putString("aiModel", jstr(body, "model")).apply();
                if (jstr(body, "key") != null) sp.edit().putString("aiKey", jstr(body, "key")).apply();
            }
            return ai.cfgJson();
        }
        if (path.equals("/api/ssh/ai/chat")) {
            return ai.chat(jstr(body, "prompt"));
        }
        if (path.equals("/api/ssh/ai/test")) {      // 2026-10-03：测试 AI 连接是否畅通
            return ai.test();
        }
        if (path.equals("/api/ssh/pkg")) {
            String action = jstr(body, "action");
            if ("delete".equals(action)) { pkg.delete(nz(jstr(body, "name"), "")); return pkg.json(); }
            if ("save".equals(action) || jstr(body, "b64") != null) {
                boolean ok = pkg.save(nz(jstr(body, "name"), "update.sh"), jstr(body, "b64"), jstr(body, "note"));
                return ok ? pkg.json() : "{\"ok\":false,\"error\":{\"message\":\"保存失败\"}}";
            }
            return pkg.json();
        }
        if (path.equals("/api/ssh/pkg/run")) {
            return ssh.runPkg(nz(jstr(body, "name"), ""), nz(jstr(body, "dir"), "/data/openpilot"), nz(jstr(body, "args"), ""));
        }
        if (path.equals("/api/ssh/drive/status")) {
            ssh.ensureDriveWatch();          // 自动开始监听（用户反馈：驾驶状态不显示）
            return ssh.driveStatusJson();
        }
        if (path.equals("/api/ssh/drive/watch")) {
            boolean on = body == null || body.indexOf("\"enabled\":false") < 0;
            return ssh.driveWatch(on);
        }
        if (path.equals("/api/ssh/voice/cues")) {
            String key = jstr(body, "key"), text = jstr(body, "text");
            if (key != null && key.length() > 0 && method.equals("POST")) { ssh.cues().set(key, text == null ? "" : text); }
            return ssh.cues().json();
        }
        if (path.equals("/api/ssh/voice/voices")) {
            return SpeechService.voicesJson();
        }
        if (path.equals("/api/ssh/voice/settings")) {
            return SpeechService.setRatePitch(nz(jstr(body, "rate"), "1"), nz(jstr(body, "pitch"), "1"));
        }
        if (path.equals("/api/ssh/voice/voice")) {
            return SpeechService.setVoice(jstr(body, "name"));
        }
        // 语音诊断（2026-09-21 车机上语音排查）
        // APP 内日志（2026-09-21）：出问题直接读现场，别猜
        // 2026-09-24 R68：页面把文本写进系统「下载」目录（体检报告下载 ✓）
        if (path.equals("/api/save")) {
            String name = jstr(body, "name");
            if (name == null || name.length() == 0) name = "c3-report-" + System.currentTimeMillis() + ".txt";
            String text = jstr(body, "text");
            if (text == null) return "{\"ok\":false,\"error\":{\"message\":\"text 必填\"}}";
            String saved = null;
            try {
                byte[] bytes = text.getBytes("UTF-8");
                try {
                    Class<?> dl = Class.forName("android.provider.MediaStore$Downloads");
                    android.net.Uri ext = (android.net.Uri) dl.getField("EXTERNAL_CONTENT_URI").get(null);
                    android.content.ContentValues cv = new android.content.ContentValues();
                    cv.put("_display_name", name);
                    cv.put("mime_type", "text/plain");
                    try { cv.put("relative_path", "Download/"); } catch (Throwable ignore) { }
                    android.net.Uri item = ctx.getContentResolver().insert(ext, cv);
                    if (item != null) {
                        java.io.OutputStream os = ctx.getContentResolver().openOutputStream(item);
                        os.write(bytes); os.flush(); os.close();
                        saved = "下载/" + name;
                    }
                } catch (Throwable ignore) { }
                if (saved == null) {
                    java.io.File d = ctx.getExternalFilesDir(null);
                    if (d == null) d = ctx.getFilesDir();
                    java.io.File f = new java.io.File(d, name);
                    java.io.FileOutputStream fo = new java.io.FileOutputStream(f);
                    fo.write(bytes); fo.flush(); fo.close();
                    saved = f.getAbsolutePath();
                }
            } catch (Throwable e) { return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(String.valueOf(e.getMessage())) + "\"}}"; }
            Logs.add("SAVE", "报告已写入 " + saved);
            return "{\"ok\":true,\"path\":\"" + Ssh.esc(saved) + "\"}";
        }
        if (path.equals("/api/log")) {
            if ("POST".equalsIgnoreCase(method)) { Logs.add("JS", jstr(body, "msg") + " @" + jstr(body, "where")); }
            String txt = Logs.dump(65536);
            return "{\"ok\":true,\"log\":\"" + Ssh.esc(txt) + "\"}";
        }
        /* 2026-09-25：页面「自更新」的版本指纹 —— 比拿日志文件长度当指纹准得多 ✓
           （装了新包 → 这里返回的版本号就变了 → 页面自己重载，不用手点刷新 ✓）*/
        if (path.equals("/api/ver")) {
            String v = "?"; int c = 0;
            try {
                android.content.pm.PackageInfo pi = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0);
                v = pi.versionName; c = pi.versionCode;
            } catch (Throwable ignore) { }
            return "{\"ok\":true,\"ver\":\"" + q(v) + "\",\"code\":" + c + "}";
        }
        // 统计配置与自检（2026-09-21）
        if (path.equals("/api/stats")) {
            if ("POST".equalsIgnoreCase(method)) {
                if (body != null && body.indexOf("\"url\"") >= 0) Stats.setUrl(ctx, jstr(body, "url"));
                if (body != null && body.indexOf("\"enabled\"") >= 0) Stats.setEnabled(ctx, jstr(body, "enabled"));
            }
            return "{\"ok\":true,\"url\":\"" + Ssh.esc(Stats.url(ctx)) + "\",\"enabled\":" + Stats.enabled(ctx)
                 + ",\"deviceId\":\"" + Stats.deviceId(ctx) + "\"}";
        }
        if (path.equals("/api/stats/beat")) return Stats.beat(ctx);
        if (path.equals("/api/log/clear")) { Logs.clear(); return "{\"ok\":true}"; }
        // ── 统一数据层（2026-09-21 重构 ④）：一处读全部状态、一处合并写 ──
        if (path.equals("/api/store")) {
            android.content.SharedPreferences sp = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE);
            if (method.equals("POST")) {
                String v = jstr(body, "voice");
                if (v != null) sp.edit().putBoolean("voice", !"off".equals(v)).commit();
                String dm = jstr(body, "displayMode");
                if (dm != null) sp.edit().putString("displayMode", dm).commit();
                String tk = jstr(body, "token");
                if (tk != null) sp.edit().putString("token", tk).commit();
                String th = jstr(body, "theme");      // 经典主题（白底黑字）
                if (th != null && th.length() > 0) sp.edit().putString("theme", th).commit();
                String nm = jstr(body, "nativeKeys");
                if (nm != null) sp.edit().putString("nativeKeys", nm).commit();
            }
            String ver = "";
            try { ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
            return "{\"ok\":true,\"store\":{\"version\":\"" + q(ver) + "\""
                 + ",\"voice\":" + sp.getBoolean("voice", true)
                 + ",\"displayMode\":\"" + String.valueOf(sp.getString("displayMode", "auto")) + "\""
                 + ",\"token\":\"" + q(String.valueOf(sp.getString("token", ""))) + "\""
                 + ",\"nativeKeys\":\"" + q(String.valueOf(sp.getString("nativeKeys", ""))) + "\"}}";
        }
        if (path.equals("/api/voice/diag")) return SpeechService.diag();
        if (path.equals("/api/voice/say")) return SpeechService.sayLocal(q(query, "text"));   // 2026-09-23 本机播报（投屏状态）✓
        if (path.equals("/api/voice/render")) return (body != null && body.indexOf("\"key\"") >= 0) ? SpeechService.renderItems(body) : SpeechService.renderCues();
        if (path.equals("/api/voice/cue")) return SpeechService.cueB64(q(query, "key"));
        // B9（2026-09-21）：语音包"生成 + 推送"一体化
        if (path.equals("/api/voice/import")) {                       // 收包端（车机侧）
            String k = jstr(body, "key"), b = jstr(body, "b64");
            if (k == null || b == null || k.length() == 0 || b.length() < 64) return "{\"ok\":false,\"error\":{\"message\":\"缺少 key/b64\"}}";
            try {
                byte[] data = android.util.Base64.decode(b, android.util.Base64.DEFAULT);
                java.io.FileOutputStream fo = new java.io.FileOutputStream(new java.io.File(ctx.getFilesDir(), k + ".wav"));
                fo.write(data); fo.close();
                Logs.add("VOICE", "导入语音包 " + k + " " + data.length + "B");
                return "{\"ok\":true,\"key\":\"" + q(k) + "\",\"bytes\":" + data.length + "}";
            } catch (Throwable e) { return "{\"ok\":false,\"error\":{\"message\":\"写入失败: " + q(String.valueOf(e.getMessage())) + "\"}}"; }
        }
        if (path.equals("/api/voice/push")) {                          // 推送端（平板侧，服务器到服务器 → 无 CORS ✗✓）
            String host = jstr(body, "host"); if (host == null || host.length() == 0) host = "192.168.0.100";
            int port = 3081;
            try { port = Integer.parseInt(String.valueOf(jstr(body, "port"))); } catch (Throwable ignore) { }
            String[] keys = { "connected", "disconnected", "driveOn", "driveOff", "sampleEnd" };
            // 不再整包 renderCues()（会截断已存在的好文件 ✗）——由 cueBytes 按需临时渲染 ✓
            StringBuilder items = new StringBuilder();
            int okn = 0;
            for (int i = 0; i < keys.length; i++) {
                String k = keys[i];
                byte[] data = SpeechService.cueBytes(k);
                String one;
                if (data == null) one = "{\"key\":\"" + q(k) + "\",\"ok\":false,\"error\":\"本机无该音频\",\"debug\":\"" + q(SpeechService.cueDebug(k)) + "\"}";
                else {
                    try {
                        java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL("http://" + host + ":" + port + "/api/voice/import").openConnection();
                        c.setRequestMethod("POST"); c.setDoOutput(true);
                        c.setConnectTimeout(6000); c.setReadTimeout(25000);
                        c.setRequestProperty("Content-Type", "application/json");
                        String payload = "{\"key\":\"" + q(k) + "\",\"b64\":\"" + android.util.Base64.encodeToString(data, android.util.Base64.NO_WRAP) + "\"}";
                        java.io.OutputStream os = c.getOutputStream(); os.write(payload.getBytes("UTF-8")); os.close();
                        int code = c.getResponseCode();
                        if (code == 200) okn++;
                        one = "{\"key\":\"" + q(k) + "\",\"ok\":" + (code == 200) + ",\"bytes\":" + data.length + ",\"code\":" + code + "}";
                    } catch (Throwable e) { one = "{\"key\":\"" + q(k) + "\",\"ok\":false,\"error\":\"" + q(String.valueOf(e.getMessage())) + "\"}"; }
                }
                if (items.length() > 0) items.append(",");
                items.append(one);
            }
            Logs.add("VOICE", "推送语音包 → " + host + ":" + port + " 成功 " + okn + "/" + keys.length);
            return "{\"ok\":true,\"host\":\"" + q(host) + "\",\"port\":" + port + ",\"okCount\":" + okn + ",\"total\":" + keys.length + ",\"items\":[" + items + "]}";
        }
        if (path.equals("/api/voice/stream")) return SpeechService.setStream(jstr(body, "stream"));
        if (path.equals("/api/ssh/voice/say")) {
            String t = jstr(body, "text");
            if (t != null && t.length() > 0) ssh.voice.say(t, "manual-test");
            return "{\"ok\":true}";
        }
        if (path.equals("/api/ssh/voice/test")) {
            String text = jstr(body, "text");
            ssh.voice.say(text == null ? "语音测试" : text, "manual-test");
            return "{\"ok\":true}";
        }
        if (path.startsWith("/api/voice/")) {
            if (path.equals("/api/voice/state")) return ssh.voice.stateJson();
            int since = 0;
            String sv = q(query, "since");
            if (sv != null) { try { since = Integer.parseInt(sv.trim()); } catch (Throwable ignore) { } }
            return ssh.voice.nextJson(since);
        }
        // 独立版没有的功能：返回"空但成功"，避免页面显示「读取失败」
        if (path.equals("/api/ssh/jobs")) return "{\"ok\":true,\"jobs\":[]}";
        if (path.equals("/api/ssh/checkpoints")) return "{\"ok\":true,\"checkpoints\":[]}";
        if (path.equals("/api/ssh/key/catalog")) return "{\"ok\":true,\"catalog\":[]}";
        if (path.equals("/api/ssh/fs/list")) return ssh.lsJson(q(query, "path"));
        if (path.startsWith("/api/ssh/")) {
            return "{\"ok\":false,\"error\":{\"code\":\"embedded-todo\",\"message\":\"APP 内置版还没实现该接口：" + path + "\"}}";
        }
        return null;
    }
}
