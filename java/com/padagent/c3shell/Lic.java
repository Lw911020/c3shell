package com.padagent.c3shell;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** 卡密激活 + 设备绑定 + 功能开关（2026-09-22 用户要求）
 *
 *  客户端只负责：存状态、发起校验、控制开关。真正的防破解必须在服务端 ✓
 *
 *  【服务端接口约定】（POST，JSON）
 *    请求 : {"code":"C3-XXXX-XXXX","device":"C3-1A2B3C4D5E6F7788","version":"2.118","app":"c3shell"}
 *    成功 : {"ok":true,"plan":"pro","expiresAt":"2027-01-01","features":["ai","routes","feedback"]}
 *    失败 : {"ok":false,"error":{"message":"卡密无效或已被绑定"}}
 *  设备绑定：服务端把 (code, device) 存起来；同一卡密换设备时返回失败 ✓
 *  未配置端点时退化为"本地记录"，便于先把流程跑通（不防破解，正式上线请务必接服务端）✓
 */
public class Lic {
    private final Context ctx;
    public Lic(Context c) { ctx = c; }
    private SharedPreferences p() { return ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE); }

    /** 2026-10-03：所有对外请求统一带 UA/Accept —— 实测 Cloudflare 会按 Java 默认 UA 返回 Error 1010 拦掉 */
    private static void ua(java.net.HttpURLConnection c) {
        try {
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("User-Agent", "c3shell-app");
        } catch (Throwable ignore) { }
    }

    public String deviceId() {
        /* 2026-09-25 用户问「换安装包 / 换手机车机还认不认」→ 把设备号做成**稳定**的 ✓
           以前是随机 UUID 存在偏好里 ✗：清数据、卸载重装就换号 → 老卡密对不上 ✗
           现在优先用系统 Android ID 的哈希（同一签名 + 同一台机器 → 重装 / 清数据都不变 ✓）；
           取不到（少数 ROM）才退回原来的随机号，保证永远有号可用 ✓ */
        String stable = stableId();
        if (stable != null && stable.length() > 0) {
            if (!stable.equals(p().getString("licDevice", ""))) p().edit().putString("licDevice", stable).commit();
            return stable;
        }
        String d = p().getString("licDevice", "");
        if (d == null || d.length() == 0) {
            d = "C3-" + java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase();
            p().edit().putString("licDevice", d).commit();
        }
        return d;
    }
    /* ═══ 2026-09-25 用户澄清：授权要绑 **C3 设备码**，不是手机/平板的 ✓ ═══
       理由：同一台 C3，可能用手机、也可能用车机（或换手机）→ 只要 C3 不变，卡就该一直能用 ✓
       设备号（本机 Android ID）现在只用于**在线统计**，不再参与授权 ✓ */
    public String c3() { return p().getString("licC3", ""); }
    public String setC3(String code) {
        String c = code == null ? "" : code.trim().toLowerCase();
        if (c.length() > 0) p().edit().putString("licC3", c).commit();
        return statusJson();
    }
    /** 卡里存的是 sha256("c3:" + 设备码) 的前 7 字节（和后端发卡脚本保持一致 ✓）*/
    private String c3Tag() {
        try {
            String c = c3();
            if (c == null || c.length() == 0) return null;
            return hex(sha256(("c3:" + c).getBytes("UTF-8")), 0, 7);
        } catch (Throwable t) { return null; }
    }

    /** 稳定设备号：Android ID 的哈希（只用于在线统计；授权不看它 ✓） */
    private String stableId() {
        try {
            String aid = android.provider.Settings.Secure.getString(
                    ctx.getContentResolver(), android.provider.Settings.Secure.ANDROID_ID);
            if (aid == null || aid.length() < 8) return null;
            byte[] h = sha256(("c3shell:" + aid).getBytes("UTF-8"));
            return "C3-" + hex(h, 0, 8).toUpperCase();
        } catch (Throwable t) { return null; }
    }
    /** 见过的最晚时间：卡密有效期用它比，**把系统时间往回调也没用** ✓（和体验版一个套路）*/
    private long trustedNow() {
        long now = System.currentTimeMillis();
        try {
            long seen = p().getLong("licSeen", 0);
            if (now > seen) { p().edit().putLong("licSeen", now).commit(); seen = now; }
            return seen > 0 ? seen : now;
        } catch (Throwable t) { return now; }
    }
    public String endpoint() {
        String e = p().getString("licEndpoint", "");
        return e == null ? "" : e;
        /* 2026-09-23 用户澄清：之前那个站点（openpilottools.yuluoqc.xyz）不是他的 ✗
           → 默认**不指向任何第三方**；等他自己的后端好了，在「激活/授权」里填地址即可 ✓
           未填地址时走"本地记录"（先把流程跑通，不防破解，正式上线要接自己的服务端 ✓） */
    }
    public String setEndpoint(String url) {
        p().edit().putString("licEndpoint", url == null ? "" : url.trim()).commit();
        return statusJson();
    }
    private static String mask(String c) {
        if (c == null || c.length() < 5) return c == null ? "" : c;
        return c.substring(0, 4) + "****" + c.substring(c.length() - 4);
    }
    public String statusJson() {
        /* 2026-09-25：activated 不再只看「有没有卡密」✗ —— 签名卡要**当场再验一遍**（设备/有效期）✓
           验不过就把原因（cardNote）一起给页面，用户自己就知道为什么显示未激活 ✓ */
        String code = p().getString("licCode", "");
        boolean on = code.length() > 0;
        String note = "";
        if (on && looksSigned(code)) {
            String res = inspectCard(code);
            on = res.indexOf("\"ok\":true") >= 0;
            if (!on) {
                int i = res.indexOf("\"message\":\"");
                if (i > 0) { int a = i + 11, b = res.indexOf('"', a); if (b > a) note = res.substring(a, b); }
            }
        }
        String feats = p().getString("licFeatures", "[\"ai\",\"routes\",\"feedback\"]");
        return "{\"ok\":true,\"activated\":" + on
             + ",\"code\":\"" + Ssh.esc(mask(code)) + "\""
             + ",\"plan\":\"" + Ssh.esc(p().getString("licPlan", "")) + "\""
             + ",\"expiresAt\":\"" + Ssh.esc(p().getString("licExpire", "")) + "\""
             + ",\"type\":\"" + Ssh.esc(p().getString("licType", "")) + "\""
             + (note.length() > 0 ? (",\"cardNote\":\"" + Ssh.esc(note) + "\"") : "")
             + ",\"device\":\"" + Ssh.esc(deviceId()) + "\""
             + ",\"c3\":\"" + Ssh.esc(c3()) + "\""
             + ",\"features\":" + feats
             + ",\"endpoint\":\"" + Ssh.esc(endpoint()) + "\"}";
    }
    public String clear() {
        p().edit().remove("licCode").remove("licPlan").remove("licExpire").remove("licType").commit();
        return statusJson();
    }
    /** 本地功能开关（用户自己的开关 ✓，与激活解耦） */
    public String setFeatures(String json) {
        p().edit().putString("licFeatures", json == null || json.length() == 0 ? "[]" : json).commit();
        return statusJson();
    }

    /** 开发者功能开关：哪些页签/入口显示（与激活解耦；没设过 = 全开，老用户不受影响） */
    public String setUiFeats(String json) {
        p().edit().putString("uiFeats", json == null || json.length() == 0 ? "[]" : json).commit();
        return statusJson();
    }
    public boolean uiFeatOn(String id) {
        String j = p().getString("uiFeats", "");
        if (j == null || j.length() == 0) return true;
        String qt = String.valueOf((char) 34);
        return j.indexOf(qt + id + qt) >= 0;
    }

    /** 远端功能开关（2026-10-03）：从服务器取这台设备该显示哪些功能；离线返回上次缓存 */
    public String remoteFeats() {
        String ep = endpoint();
        String cached = p().getString("rfeatsCache", "");
        String Q = String.valueOf((char) 34);
        String nl = String.valueOf((char) 10);
        if (ep.length() == 0) return "{" + Q + "ok" + Q + ":false," + Q + "error" + Q + ":{" + Q + "message" + Q + ":" + Q + "未配置校验服务器" + Q + "}," + Q + "cached" + Q + ":" + (cached.length() > 0 ? cached : "null") + "}";
        int i = ep.lastIndexOf('/');
        String base = i > 8 ? ep.substring(0, i) : ep;
        java.net.HttpURLConnection conn = null;
        try {
            conn = (java.net.HttpURLConnection) new java.net.URL(base + "/feat?device=" + java.net.URLEncoder.encode(deviceId(), "UTF-8")).openConnection();
            ua(conn);
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(15000);
            int rc = conn.getResponseCode();
            java.io.BufferedReader r = new java.io.BufferedReader(new java.io.InputStreamReader(rc >= 400 ? conn.getErrorStream() : conn.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder(); String line;
            while ((line = r.readLine()) != null) sb.append(line).append(nl);
            r.close();
            String txt = sb.toString().trim();
            if (rc < 400 && txt.indexOf(Q + "ok" + Q + ":true") >= 0) p().edit().putString("rfeatsCache", txt).commit();
            return txt;
        } catch (Throwable t) {
            return "{" + Q + "ok" + Q + ":false," + Q + "error" + Q + ":{" + Q + "message" + Q + ":" + Q + Ssh.esc(t.getClass().getSimpleName()) + Q + "}," + Q + "cached" + Q + ":" + (cached.length() > 0 ? cached : "null") + "}";
        } finally { try { if (conn != null) conn.disconnect(); } catch (Throwable ignore) { } }
    }

    /** 在线心跳（用户统计）：把已配置的校验地址里的 /verify 换成 /heartbeat 上报 ✓
     *  没配地址就静默跳过（不打扰用户 ✓） */
    public String heartbeat(String feature, int hostCount, String mode) {
        String ep = endpoint();
        if (ep.length() == 0) return "{\"ok\":true,\"skipped\":true,\"message\":\"未配置服务器，未上报\"}";
        String hb = ep.endsWith("/verify") ? (ep.substring(0, ep.length() - 7) + "/heartbeat") : ep;
        String ver = "?", os = "?";
        try { ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        try { os = android.os.Build.VERSION.RELEASE; } catch (Throwable ignore) { }
        String model = "";
        try { model = android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL; } catch (Throwable ignore) { }
        String body = "{\"device\":\"" + Ssh.esc(deviceId()) + "\",\"version\":\"" + Ssh.esc(ver)
                + "\",\"os\":\"" + Ssh.esc(os) + "\",\"model\":\"" + Ssh.esc(model)
                + "\",\"mode\":\"" + Ssh.esc(mode) + "\",\"hosts\":" + hostCount
                + ",\"feature\":\"" + Ssh.esc(feature) + "\"}";
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(hb).openConnection();
            ua(conn);
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(8000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            OutputStream os2 = conn.getOutputStream();
            os2.write(body.getBytes("UTF-8")); os2.flush(); os2.close();
            int rc = conn.getResponseCode();
            return rc < 400 ? "{\"ok\":true}" : "{\"ok\":false,\"error\":{\"message\":\"HTTP " + rc + "\"}}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(t.getClass().getSimpleName()) + "\"}}";
        } finally { try { if (conn != null) conn.disconnect(); } catch (Throwable ignore) { } }
    }

    public String activate(String code) {
        String c = code == null ? "" : code.trim().toUpperCase();
        if (c.length() < 6) return "{\"ok\":false,\"error\":{\"message\":\"卡密太短（至少 6 位）\"}}";
        /* 2026-09-24：长得像签名卡就**先离线验签**（不需要任何服务器）✓
           不是签名卡（比如 C3-TEST-0001）就照旧走「在线校验 / 本地记录」✓ */
        if (looksSigned(c)) return activateSigned(c);
        String ep = endpoint();
        String ver = "?";
        try { ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        String body = "{\"code\":\"" + Ssh.esc(c) + "\",\"device\":\"" + Ssh.esc(deviceId())
                + "\",\"version\":\"" + Ssh.esc(ver) + "\",\"app\":\"c3shell\"}";
        if (ep.length() == 0) {
            p().edit().putString("licCode", c).putString("licPlan", "local").putString("licExpire", "").commit();
            return "{\"ok\":true,\"local\":true,\"message\":\"未配置校验服务器，已在本机记录\",\"status\":" + statusJson() + "}";
        }
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(ep).openConnection();
            ua(conn);
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(15000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            OutputStream os = conn.getOutputStream();
            os.write(body.getBytes("UTF-8")); os.flush(); os.close();
            int rc = conn.getResponseCode();
            BufferedReader r = new BufferedReader(new InputStreamReader(
                    rc >= 400 ? conn.getErrorStream() : conn.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder(); String line;
            while ((line = r.readLine()) != null) sb.append(line).append('\n');
            r.close();
            String txt = sb.toString().trim();
            if (rc >= 400) return "{\"ok\":false,\"error\":{\"message\":\"服务器 HTTP " + rc + "：" + Ssh.esc(txt.length() > 200 ? txt.substring(0, 200) : txt) + "\"}}";
            boolean ok = txt.indexOf("\"ok\":true") >= 0 || txt.indexOf("\"ok\": true") >= 0;
            if (!ok) {
                String msg = "卡密无效或已被绑定";
                int i = txt.indexOf("message");
                if (i >= 0) { int a = txt.indexOf(':', i), b = txt.indexOf('"', a + 1), e2 = txt.indexOf('"', b + 1);
                    if (a > 0 && b > 0 && e2 > b) msg = txt.substring(b + 1, e2); }
                return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(msg) + "\"}}";
            }
            String plan = pick(txt, "plan"), exp = pick(txt, "expiresAt");
            p().edit().putString("licCode", c).putString("licPlan", plan).putString("licExpire", exp).commit();
            return "{\"ok\":true,\"plan\":\"" + Ssh.esc(plan) + "\",\"expiresAt\":\"" + Ssh.esc(exp) + "\",\"status\":" + statusJson() + "}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"连不上校验服务器：" + Ssh.esc(t.getClass().getSimpleName()) + "（可先填端点或用本地模式）\"}}";
        } finally {
            try { if (conn != null) conn.disconnect(); } catch (Throwable ignore) { }
        }
    }
    /* ===== 2026-09-24 上线那套（卡密 / 统计 / 反馈）都要用到的小工具 ===== */

    /** 同一台服务器上的兄弟端点：把 /verify 换成 /feedback、/stats ✓
     *  （未配置校验服务器时返回空串 → 调用方直接给「未配置」提示 ✓）*/
    private String sibling(String path) {
        String ep = endpoint();
        if (ep.length() == 0) return "";
        int i = ep.lastIndexOf('/');
        if (i > 8) ep = ep.substring(0, i);      /* 保留 https://主机:端口 这一段 ✓ */
        return ep + path;
    }
    /** 反馈里的联系方式（选填，存本机，跟着反馈一起发 ✓）*/
    public String setContact(String c) {
        p().edit().putString("licContact", c == null ? "" : c.trim()).commit();
        return statusJson();
    }
    /** 上报一条问题反馈：用户描述 + 完整日志 + 截图 base64（可选）✓
     *  端点是校验服务器同目录下的 /feedback（填 https://x/verify → 自动变 https://x/feedback ✓）*/
    public String feedback(String text, String logText, String imageB64) {
        String u = sibling("/feedback");
        if (u.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"未配置校验服务器（软件设置 → 激活 / 授权）\"}}";
        String ver = "?";
        try { ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        StringBuilder b = new StringBuilder();
        b.append("{\"device\":\"").append(Ssh.esc(deviceId()))
         .append("\",\"version\":\"").append(Ssh.esc(ver))
         .append("\",\"contact\":\"").append(Ssh.esc(p().getString("licContact", "")))
         .append("\",\"text\":\"").append(Ssh.esc(text == null ? "" : text))
         .append("\",\"logText\":\"").append(Ssh.esc(logText == null ? "" : logText))
         .append("\",\"imageB64\":\"").append(imageB64 == null ? "" : imageB64)   /* base64 里没有引号/反斜杠，不用转义 ✓ */
         .append("\"}");
        return postJson(u, b.toString(), 10000, 40000);
    }
    /** 赞赏登记（2026-09-24 用户要求）：把「已赞赏 + 金额（>20）」发到服务器。
     *  端点 = 校验服务器同目录下的 /appreciate（填 https://x/verify → 自动变 https://x/appreciate ✓）
     *  没配服务器时返回未配置提示，APP 侧会给用户相应说明 ✓ */
    public String appreciate(String amount) {
        String u = sibling("/appreciate");
        if (u.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"未配置校验服务器（软件设置 → 激活 / 授权 里填地址）\"}}";
        String ver = "?";
        try { ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        String body = "{\"device\":\"" + Ssh.esc(deviceId())
                + "\",\"version\":\"" + Ssh.esc(ver)
                + "\",\"amount\":\"" + Ssh.esc(amount == null ? "" : amount)
                + "\",\"contact\":\"" + Ssh.esc(p().getString("licContact", "")) + "\"}";
        return postJson(u, body, 8000, 15000);
    }

    /** 读后台统计（在线人数 / 累计设备 / 今日活跃）—— GET 兄弟端点 /stats ✓
     *  返回服务器原始 JSON，页面直接拿去显示 ✓ */
    public String stats() {
        String u = sibling("/stats");
        if (u.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"未配置校验服务器（软件设置 → 激活 / 授权）\"}}";
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(u).openConnection();
            ua(conn);
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(12000);
            return readAll(conn, "统计");
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"连不上统计服务器：" + Ssh.esc(t.getClass().getSimpleName()) + "\"}}";
        } finally { try { if (conn != null) conn.disconnect(); } catch (Throwable ignore) { } }
    }
    private static String readAll(HttpURLConnection conn, String what) throws Exception {
        int rc = conn.getResponseCode();
        BufferedReader r = new BufferedReader(new InputStreamReader(
                rc >= 400 ? conn.getErrorStream() : conn.getInputStream(), "UTF-8"));
        StringBuilder sb = new StringBuilder(); String line;
        while ((line = r.readLine()) != null) sb.append(line).append('\n');
        r.close();
        String t = sb.toString().trim();
        if (rc >= 400) return "{\"ok\":false,\"error\":{\"message\":\"服务器 HTTP " + rc + "：" + Ssh.esc(t.length() > 200 ? t.substring(0, 200) : t) + "\"}}";
        if (t.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(what) + "接口返回空\"}}";
        return t;
    }
    private static String postJson(String url, String body, int ct, int rt) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            ua(conn);
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(ct);
            conn.setReadTimeout(rt);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            OutputStream o = conn.getOutputStream();
            o.write(body.getBytes("UTF-8")); o.flush(); o.close();
            return readAll(conn, "上传");
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"上传失败：" + Ssh.esc(t.getClass().getSimpleName()) + "\"}}";
        } finally { try { if (conn != null) conn.disconnect(); } catch (Throwable ignore) { } }
    }
    /* ═══════════ 2026-09-24 离线签名卡密（不依赖任何服务器）═══════════
       为什么这么做：云后端一直配不通 → 干脆让卡密**自带签名**，APP 只内置公钥 ✓
       · 私钥只在发卡机（tools/license_mint.py），APK 里只有公钥 → 反编译也伪造不出卡 ✓
       · 一码一机：卡里签进了设备号摘要（7 字节）→ 别人拿到卡也用不了 ✓
       · 有效期也在卡里（自 2026-01-01 起的天数，0 = 永久）✓
       · 签名 = ECDSA P-256 / SHA-256；卡里存 64 字节定长 r||s，这里拼回 DER 给 java 验 ✓
       公钥指纹(SHA-256 前 8 字节) = abefcf506adb63e2（换密钥时记得同步改这行 ✗）*/
    private static final String PUBKEY_B64 =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEX9jTbmo1XogokbbM1cHzVv5G5anXD2m17/zw7Cs13Kpo2l/pFqjbA/i0gcn9Jl9L6oQp08hPmKxTo9kMrQtIVA==";
    private static final String B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    private static final String[] PLANS = {"pro", "basic", "trial", "internal"};
    private static final String[] FEATS = {"ai", "routes", "feedback"};

    /** 签名卡的长度特征：82 字节 → 132 个 Base32 字符（加前缀与分组横线 ≈ 150+ 字符）*/
    private static boolean looksSigned(String c) {
        if (c == null) return false;
        String s = c.trim().toUpperCase();
        if (!s.startsWith("C3-")) return false;
        int n = 0;
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) != '-') n++;
        return n >= 100;
    }
    private static byte[] b32d(String card) {
        StringBuilder bits = new StringBuilder();
        String s = card.toUpperCase();
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            int idx;
            if (ch == 'I' || ch == 'L') idx = 1;          /* Crockford：I/L→1、O→0、U→V ✓ */
            else if (ch == 'O') idx = 0;
            else if (ch == 'U') idx = 27;
            else idx = B32.indexOf(ch);
            if (idx < 0) continue;                        /* 横线、空格、换行一律跳过 ✓ */
            for (int b = 4; b >= 0; b--) bits.append(((idx >> b) & 1) == 1 ? '1' : '0');
        }
        int n = bits.length() / 8;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            int v = 0;
            for (int b = 0; b < 8; b++) v = (v << 1) | (bits.charAt(i * 8 + b) - '0');
            out[i] = (byte) v;
        }
        return out;
    }
    private static byte[] sha256(byte[] d) {
        try { return java.security.MessageDigest.getInstance("SHA-256").digest(d); }
        catch (Throwable t) { return new byte[32]; }
    }
    private static byte[] cat(byte[] a, byte[] b) {
        byte[] o = new byte[a.length + b.length];
        System.arraycopy(a, 0, o, 0, a.length);
        System.arraycopy(b, 0, o, a.length, b.length);
        return o;
    }
    private static String hex(byte[] d, int off, int len) {
        StringBuilder b = new StringBuilder();
        for (int i = off; i < off + len && i < d.length; i++) b.append(String.format("%02x", d[i] & 0xFF));
        return b.toString();
    }
    /** r||s（各 32 字节）→ ASN.1 DER（java 的 SHA256withECDSA 只吃 DER ✓）*/
    private static byte[] der(byte[] r, byte[] s) {
        byte[] ri = strip0(r), si = strip0(s);
        int lr = ri.length + ((ri[0] & 0x80) != 0 ? 1 : 0);
        int ls = si.length + ((si[0] & 0x80) != 0 ? 1 : 0);
        java.io.ByteArrayOutputStream o = new java.io.ByteArrayOutputStream();
        o.write(0x30); o.write(2 + lr + 2 + ls);
        o.write(0x02); o.write(lr); if ((ri[0] & 0x80) != 0) o.write(0x00); o.write(ri, 0, ri.length);
        o.write(0x02); o.write(ls); if ((si[0] & 0x80) != 0) o.write(0x00); o.write(si, 0, si.length);
        return o.toByteArray();
    }
    private static byte[] strip0(byte[] a) {
        int i = 0;
        while (i < a.length - 1 && a[i] == 0) i++;
        byte[] o = new byte[a.length - i];
        System.arraycopy(a, i, o, 0, o.length);
        return o;
    }

    /** 检查一张签名卡（不写状态）：返回 {"ok":true,…} 或 {"ok":false,"error":{…}} ✓ */
    public String inspectCard(String card) {
        try {
            String cs = card == null ? "" : card.trim().toUpperCase();
            if (cs.startsWith("C3-")) cs = cs.substring(3);      /* 前缀里的 C、3 也是 base32 字符 → 必须先剥 ✗ */
            else if (cs.startsWith("C3")) cs = cs.substring(2);
            byte[] raw = b32d(cs);
            if (raw.length < 82) return err("卡密长度不对（解出 " + raw.length + " 字节，应为 82）");
            byte[] pl = java.util.Arrays.copyOfRange(raw, 0, 16);
            byte[] r = java.util.Arrays.copyOfRange(raw, 16, 48);
            byte[] s = java.util.Arrays.copyOfRange(raw, 48, 80);
            byte[] chk = java.util.Arrays.copyOfRange(raw, 80, 82);
            byte[] mine = java.util.Arrays.copyOfRange(sha256(cat(pl, cat(r, s))), 0, 2);
            if (!java.util.Arrays.equals(mine, chk)) return err("校验位不对 → 卡密抄错/少字符了");
            int ver = (pl[0] >> 4) & 0x0F;
            if (ver != 1) return err("卡密版本不认识（v" + ver + "）");
            java.security.PublicKey pub = java.security.KeyFactory.getInstance("EC").generatePublic(
                new java.security.spec.X509EncodedKeySpec(android.util.Base64.decode(PUBKEY_B64, android.util.Base64.DEFAULT)));
            java.security.Signature sig = java.security.Signature.getInstance("SHA256withECDSA");
            sig.initVerify(pub); sig.update(pl);
            if (!sig.verify(der(r, s))) return err("签名无效：这张卡不是本机的发卡机签的（或被改过）");
            String tag = hex(pl, 9, 7);
            if (!tag.equals("00000000000000")) {
                String mineC3 = c3Tag();
                if (mineC3 == null) return err("还没读到「C3 设备码」：先连上 C3（点「读取」），或手动填一下 ✓");
                if (!tag.equals(mineC3)) return err("这张卡是给别的 C3 的（一码一台：卡里的摘要对不上当前这台 C3）");
            }
            int expDays = ((pl[4] & 0xFF) << 8) | (pl[5] & 0xFF);
            String expires = ""; long leftDays = -1;
            if (expDays > 0) {
                java.util.Calendar c = java.util.Calendar.getInstance(java.util.TimeZone.getTimeZone("UTC"));
                c.clear(); c.set(2026, 0, 1, 0, 0, 0);
                long expMs = c.getTimeInMillis() + expDays * 86400000L;
                java.text.SimpleDateFormat fmt = new java.text.SimpleDateFormat("yyyy-MM-dd");
                fmt.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
                expires = fmt.format(new java.util.Date(expMs));
                leftDays = (expMs - trustedNow()) / 86400000L;
                if (leftDays < 0) return err("这张卡已过期（" + expires + "）");
            }
            int planIdx = pl[2] & 0xFF;
            String plan = planIdx < PLANS.length ? PLANS[planIdx] : "pro";
            StringBuilder fs = new StringBuilder("[");
            for (int i = 0; i < FEATS.length; i++) if ((pl[1] & (1 << i)) != 0) {
                if (fs.length() > 1) fs.append(",");
                fs.append("\"").append(FEATS[i]).append("\"");
            }
            fs.append("]");
            int seq = ((pl[6] & 0xFF) << 16) | ((pl[7] & 0xFF) << 8) | (pl[8] & 0xFF);
            return "{\"ok\":true,\"type\":\"signed\",\"plan\":\"" + Ssh.esc(plan)
                 + "\",\"expiresAt\":\"" + Ssh.esc(expires) + "\",\"leftDays\":" + leftDays
                 + ",\"seq\":" + seq + ",\"bound\":" + (!tag.equals("00000000000000"))
                 + ",\"features\":" + fs + "}";
        } catch (Throwable t) {
            return err("卡密解析失败：" + t.getClass().getSimpleName());
        }
    }
    private static String err(String m) { return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(m) + "\"}}"; }

    /** 用签名卡激活（离线，不需要服务器）：验过就写本机状态 ✓ */
    public String activateSigned(String card) {
        String j = inspectCard(card);
        if (j.indexOf("\"ok\":true") < 0) return j;
        String plan = pick(j, "plan"), exp = pick(j, "expiresAt");
        String feats = j.substring(j.indexOf("\"features\":") + 11);
        feats = feats.substring(0, feats.lastIndexOf(']') + 1);
        String code = card.trim().toUpperCase();
        p().edit().putString("licCode", code).putString("licPlan", plan).putString("licExpire", exp)
             .putString("licFeatures", feats).putString("licType", "signed").commit();
        return "{\"ok\":true,\"type\":\"signed\",\"plan\":\"" + Ssh.esc(plan)
             + "\",\"expiresAt\":\"" + Ssh.esc(exp) + "\",\"message\":\"签名卡验证通过（离线，认的是这台 C3 ✓）\"}";
    }
    /** 现在这台机器是不是「已授权」？给体验版闸门用：有有效卡密 → 不再走体验倒计时 ✓
     *  · 签名卡：重新验一遍签 + 设备摘要 + 有效期（改系统时间也没用，日期是卡里的 ✓）
     *  · 老式卡（在线/本地记录）：只要本机记着就算已授权 ✓ */
    public boolean licensedNow() {
        String code = p().getString("licCode", "");
        if (code == null || code.length() == 0) return false;
        if (looksSigned(code)) return inspectCard(code).indexOf("\"ok\":true") >= 0;
        return true;
    }
    private static String pick(String json, String key) {
        try {
            int i = json.indexOf("\"" + key + "\"");
            if (i < 0) return "";
            int a = json.indexOf(':', i), b = json.indexOf('"', a + 1), e = json.indexOf('"', b + 1);
            return (a > 0 && b > 0 && e > b) ? json.substring(b + 1, e) : "";
        } catch (Throwable t) { return ""; }
    }
}
