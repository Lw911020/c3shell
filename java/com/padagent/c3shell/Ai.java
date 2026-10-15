package com.padagent.c3shell;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** AI 分析（2026-09-21 用户要求：连接 AI 分析数据并推荐参数修改）。
 *  设计要点：AI 端点是**可填任意 OpenAI 兼容地址**；没配也能用（页面侧本地规则引擎）。
 *  本类只做"代理转发"，避免 WebView 里的跨域/混合内容问题。 */
public class Ai {
    private final Context ctx;

    public Ai(Context c) { ctx = c; }

    private SharedPreferences p() { return ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE); }

    public String cfgJson() {
        return "{\"ok\":true,\"endpoint\":\"" + Ssh.esc(p().getString("aiEndpoint", ""))
                + "\",\"model\":\"" + Ssh.esc(p().getString("aiModel", ""))
                + "\",\"hasKey\":" + (p().getString("aiKey", "").length() > 0) + "}";
    }

    /** POST {prompt} → 转发到已配置的 OpenAI 兼容 /chat/completions，返回 {ok,text} */
    public String chat(String prompt) {
        String ep = p().getString("aiEndpoint", "").trim();
        String key = p().getString("aiKey", "").trim();
        String model = p().getString("aiModel", "").trim();
        if (ep.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"还没配置 AI 端点（设置里填 OpenAI 兼容地址）\"}}";
        if (ep.endsWith("/")) ep = ep.substring(0, ep.length() - 1);
        if (!ep.endsWith("/chat/completions")) ep = ep + "/chat/completions";
        HttpURLConnection c = null;
        try {
            URL u = new URL(ep);
            c = (HttpURLConnection) u.openConnection();
            c.setRequestMethod("POST");
            c.setConnectTimeout(8000);
            c.setReadTimeout(60000);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("User-Agent", "c3shell-app");
            if (key.length() > 0) c.setRequestProperty("Authorization", "Bearer " + key);
            String body = "{\"model\":\"" + Ssh.esc(model.length() > 0 ? model : "gpt-4o-mini")
                    + "\",\"messages\":[{\"role\":\"user\",\"content\":\"" + Ssh.esc(prompt) + "\"}],\"temperature\":0.2}";
            OutputStream os = c.getOutputStream();
            os.write(body.getBytes("UTF-8"));
            os.flush(); os.close();
            int code = c.getResponseCode();
            BufferedReader r = new BufferedReader(new InputStreamReader(
                    code >= 400 ? c.getErrorStream() : c.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line).append('\n');
            r.close();
            String txt = sb.toString();
            if (code >= 400) return "{\"ok\":false,\"error\":{\"message\":\"HTTP " + code + " " + Ssh.esc(txt.length() > 300 ? txt.substring(0, 300) : txt) + "\"}}";
            // 从 OpenAI 响应里抠出 content（够用即可）
            String content = txt;
            int i = txt.indexOf("\"content\":");
            if (i >= 0) {
                int q1 = txt.indexOf('"', i + 10);
                if (q1 >= 0) {
                    StringBuilder out = new StringBuilder();
                    for (int k = q1 + 1; k < txt.length(); k++) {
                        char ch = txt.charAt(k);
                        if (ch == '\\') { k++; if (k < txt.length()) out.append(txt.charAt(k)); continue; }
                        if (ch == '"') break;
                        out.append(ch);
                    }
                    content = out.toString();
                }
            }
            return "{\"ok\":true,\"text\":\"" + Ssh.esc(content) + "\"}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(String.valueOf(e.getMessage())) + "\"}}";
        } finally {
            if (c != null) try { c.disconnect(); } catch (Throwable ignore) { }
        }
    }

    /** 2026-10-03 用户要求：测试连接 —— 分步报告（GET /models + 最小对话），并给出可照做的原因 */
    public String test() {
        String ep = p().getString("aiEndpoint", "").trim();
        String key = p().getString("aiKey", "").trim();
        String model = p().getString("aiModel", "").trim();
        String Q = String.valueOf((char) 34);
        if (ep.length() == 0) return "{" + Q + "ok" + Q + ":false," + Q + "steps" + Q + ":[]," + Q + "error" + Q + ":{" + Q + "message" + Q + ":" + Q + "还没填 AI 网址（例如 https://api.deepseek.com/v1）" + Q + "}}";
        if (ep.endsWith("/")) ep = ep.substring(0, ep.length() - 1);
        String base = ep.endsWith("/chat/completions") ? ep.substring(0, ep.length() - 17) : ep;
        String uModels = base + "/models", uChat = base + "/chat/completions";
        long t1 = System.currentTimeMillis();
        String[] r1 = httpGet(uModels, key);
        long ms1 = System.currentTimeMillis() - t1;
        int c1 = codeOf(r1[0]);
        int mc = countOccurrences(r1[1], Q + "id" + Q);
        boolean mf = model.length() > 0 && r1[1].indexOf(model) >= 0;
        boolean h1 = looksHtml(r1[1]);
        String useModel = model.length() > 0 ? model : "gpt-4o-mini";
        long t2 = System.currentTimeMillis();
        String chatRes = chat("ping");                 // 走真正「问 AI」那条路，保证测的就是实际用的请求
        long ms2 = System.currentTimeMillis() - t2;
        String chatText = textOf(chatRes);
        boolean okChat = chatRes.indexOf(Q + "ok" + Q + ":true") >= 0;
        int c2 = okChat ? 200 : (chatText.length() > 0 ? 0 : 0);
        // 网址漏了 /v1 时自动再试一次，给一条能直接照做的提示
        String hint = "";
        if (!okChat && !base.endsWith("/v1")) {
            String[] rx = httpGet(base + "/v1/models", key);
            if (codeOf(rx[0]) == 200 && !looksHtml(rx[1]) && rx[1].indexOf(Q + "id" + Q) >= 0)
                hint = "建议把网址改成 " + base + "/v1（这个服务用 /v1 形式）";
        }
        if (hint.length() == 0 && !okChat && h1) hint = "返回的是网页不是接口 —— 网址大概率要带 /v1（例如 " + base + "/v1）";
        String steps = "{" + Q + "name" + Q + ":" + Q + "GET /models" + Q + "," + Q + "url" + Q + ":" + Q + Ssh.esc(uModels) + Q + "," + Q + "http" + Q + ":" + c1 + "," + Q + "ms" + Q + ":" + ms1
                + "," + Q + "models" + Q + ":" + mc + "," + Q + "modelFound" + Q + ":" + mf + "," + Q + "html" + Q + ":" + h1
                + "," + Q + "note" + Q + ":" + Q + Ssh.esc(shortMsg(r1[1], c1)) + Q + "},"
                + "{" + Q + "name" + Q + ":" + Q + "POST /chat/completions" + Q + "," + Q + "url" + Q + ":" + Q + Ssh.esc(uChat) + Q + "," + Q + "http" + Q + ":" + c2 + "," + Q + "ms" + Q + ":" + ms2
                + "," + Q + "note" + Q + ":" + Q + Ssh.esc(okChat ? ("模型 " + useModel + " 已答复：" + trimTo(textOf(chatRes), 60)) : trimTo(errMsgOf(chatRes), 200)) + Q + "}";
        String msg = okChat ? "" : stepError(c1, c2, base, h1);
        if (!okChat && hint.length() > 0) msg = msg.length() > 0 ? (msg + "；" + hint) : hint;
        String err = okChat ? "" : (Q + "error" + Q + ":{" + Q + "message" + Q + ":" + Q + Ssh.esc(msg) + Q + "},");
        return "{" + Q + "ok" + Q + ":" + okChat + "," + err + Q + "hint" + Q + ":" + Q + Ssh.esc(hint) + Q + "," + Q + "endpoint" + Q + ":" + Q + Ssh.esc(base) + Q + "," + Q + "model" + Q + ":" + Q + Ssh.esc(model) + Q + "," + Q + "steps" + Q + ":[" + steps + "]}";
    }

    private static String textOf(String chatJson) {
        int i = chatJson.indexOf("\"text\":\"");
        if (i < 0) return "";
        StringBuilder o = new StringBuilder();
        for (int k = i + 8; k < chatJson.length(); k++) {
            char ch = chatJson.charAt(k);
            if (ch == 92) { k++; if (k < chatJson.length()) o.append(chatJson.charAt(k)); continue; }
            if (ch == '"') break;
            o.append(ch);
        }
        return o.toString();
    }

    private static String errMsgOf(String chatJson) {
        int i = chatJson.indexOf("\"message\":\"");
        if (i < 0) return trimTo(chatJson, 200);
        StringBuilder o = new StringBuilder();
        for (int k = i + 11; k < chatJson.length(); k++) {
            char ch = chatJson.charAt(k);
            if (ch == 92) { k++; if (k < chatJson.length()) o.append(chatJson.charAt(k)); continue; }
            if (ch == '"') break;
            o.append(ch);
        }
        return trimTo(o.toString(), 200);
    }

    private static String trimTo(String s, int n) {
        if (s == null) return "";
        return s.length() > n ? s.substring(0, n) : s;
    }

    private static boolean looksHtml(String s) { return s != null && (s.indexOf("<html") >= 0 || s.indexOf("<!DOCTYPE") >= 0 || s.indexOf("<div") >= 0); }
    private static int codeOf(String s) { try { return Integer.parseInt(s); } catch (Throwable e) { return 0; } }

    private String[] httpGet(String url, String key) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod("GET");
            c.setConnectTimeout(6000);
            c.setReadTimeout(15000);
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("User-Agent", "c3shell-app");
            if (key.length() > 0) c.setRequestProperty("Authorization", "Bearer " + key);
            int code = c.getResponseCode();
            return new String[] { String.valueOf(code), readAll(code >= 400 ? c.getErrorStream() : c.getInputStream()) };
        } catch (Throwable e) {
            return new String[] { "0", String.valueOf(e.getMessage()) };
        } finally { if (c != null) try { c.disconnect(); } catch (Throwable ignore) { } }
    }

    private String[] httpChat(String base, String key, String model, String prompt) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(base + "/chat/completions").openConnection();
            c.setRequestMethod("POST");
            c.setConnectTimeout(6000);
            c.setReadTimeout(30000);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("User-Agent", "c3shell-app");
            if (key.length() > 0) c.setRequestProperty("Authorization", "Bearer " + key);
            String Q = String.valueOf((char) 34);
            String body = "{" + Q + "model" + Q + ":" + Q + Ssh.esc(model) + Q + "," + Q + "messages" + Q + ":[{" + Q + "role" + Q + ":" + Q + "user" + Q + "," + Q + "content" + Q + ":" + Q + Ssh.esc(prompt) + Q + "}]," + Q + "max_tokens" + Q + ":8}";
            OutputStream os = c.getOutputStream();
            os.write(body.getBytes("UTF-8"));
            os.flush(); os.close();
            int code = c.getResponseCode();
            return new String[] { String.valueOf(code), readAll(code >= 400 ? c.getErrorStream() : c.getInputStream()) };
        } catch (Throwable e) {
            return new String[] { "0", String.valueOf(e.getMessage()) };
        } finally { if (c != null) try { c.disconnect(); } catch (Throwable ignore) { } }
    }

    private static String readAll(java.io.InputStream in) {
        if (in == null) return "";
        try {
            BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
            StringBuilder sb = new StringBuilder(); String line;
            while ((line = r.readLine()) != null) sb.append(line).append(' ');
            r.close();
            return sb.toString();
        } catch (Throwable e) { return ""; }
    }

    private static int countOccurrences(String hay, String needle) {
        if (hay == null || needle.length() == 0) return 0;
        int n = 0, i = 0;
        while ((i = hay.indexOf(needle, i)) >= 0) { n++; i += needle.length(); }
        return n;
    }

    private static String shortMsg(String body, int code) {
        String t = body == null ? "" : body.trim();
        if (t.length() == 0) return code == 0 ? "连不上（网络/域名/证书？）" : ("HTTP " + code);
        if (t.length() > 160) t = t.substring(0, 160);
        return (code > 0 ? ("HTTP " + code + " ") : "") + t;
    }

    private static String stepError(int c1, int c2, String base, boolean html1) {
        if (html1) return "网址返回的是网页（不是 API）—— 地址要填到 /v1，例如 " + base + "/v1";
        if (c1 == 0) return "连不上 " + base + "（域名/网络/证书），或网址写法不对";
        if (c1 == 401 || c1 == 403) return "密钥无效或被拒（HTTP " + c1 + "）—— 检查 AI 密钥是否填对/过期";
        if (c1 == 404) return "网址不对（HTTP 404）—— 一般要填到 /v1 结尾，例如 https://api.deepseek.com/v1";
        if (c2 == 0) return "对话接口连不上（网络/证书）";
        if (c2 == 401 || c2 == 403) return "对话接口被拒（HTTP " + c2 + "）—— 密钥或模型名不对";
        if (c2 == 404) return "对话接口 404 —— 这个服务可能不是 OpenAI 兼容接口";
        if (c2 == 400) return "对话接口 400 —— 多半是模型名不对（去后台看该服务的模型列表）";
        if (c2 == 429) return "被限流/余额不足（HTTP 429）—— 去服务后台看额度";
        return "第一步 HTTP " + c1 + "，第二步 HTTP " + c2;
    }
}
