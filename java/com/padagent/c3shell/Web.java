package com.padagent.c3shell;

import android.content.Context;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.HashMap;
import java.util.Map;

/**
 * 内置 HTTP 服务（2026-09-20 方案 C）：APP 自己托管页面与 /api 接口，
 * 独立运行、不依赖平板上的 node 连接器。只绑 127.0.0.1（本机）。
 */
public class Web {
    public interface Api {
        String handle(String method, String path, String query, String body, Map<String, String> headers) throws Exception;
        /** 需要长连接（SSE）的接口在这里直接接管 socket；返回 true 表示已处理。 */
        boolean stream(Socket sock, String method, String path, String query, Map<String, String> headers) throws Exception;
    }

    private final Context ctx;
    private final int wantPort;
    private ServerSocket ss;
    private volatile boolean running = true;
    private Api api;
    public int port;

    /* 轮询汇总：不逐条写日志，但每 5 分钟或每 200 次给一行，方便看「到底在轮询什么」✓ */
    private static final java.util.concurrent.atomic.AtomicInteger QUIET_N = new java.util.concurrent.atomic.AtomicInteger();
    private static volatile long QUIET_MAX = 0, QUIET_T0 = System.currentTimeMillis();
    private static void quiet(long ms) {
        if (ms > QUIET_MAX) QUIET_MAX = ms;
        if (QUIET_N.incrementAndGet() >= 200 || System.currentTimeMillis() - QUIET_T0 > 300000L) flushQuiet();
    }
    /* 同一条请求连续重复（轮询/心跳那种）不再逐条写 ✓（2026-09-25 用户：日志别什么都写）*/
    private static String DUP_KEY = "";
    private static int DUP_N = 0;
    private static long DUP_T = 0;
    private static synchronized void logReq(String key, String line) {
        long now = System.currentTimeMillis();
        if (key.equals(DUP_KEY)) {
            DUP_N++;
            if (now - DUP_T > 300000L) { Logs.add("HTTP", "（同前 ×" + DUP_N + "，还在重复）"); DUP_N = 1; DUP_T = now; }
            return;
        }
        if (DUP_N > 1) Logs.add("HTTP", "（上一条相同请求共 " + DUP_N + " 次）");
        DUP_KEY = key; DUP_N = 1; DUP_T = now;
        Logs.add("HTTP", line);
    }
    private static synchronized void flushQuiet() {
        int n = QUIET_N.getAndSet(0);
        long mx = QUIET_MAX; QUIET_MAX = 0; QUIET_T0 = System.currentTimeMillis();
        if (n > 0) Logs.add("HTTP", "轮询 " + n + " 次（最慢 " + mx + "ms）");
    }

    public Web(Context c, int p) { ctx = c; wantPort = p; }

    public int start(Api a) throws IOException {
        api = a;
        ss = new ServerSocket();
        ss.setReuseAddress(true);
        ss.bind(new InetSocketAddress("127.0.0.1", wantPort));
        port = ss.getLocalPort();
        Thread t = new Thread(new Runnable() { public void run() { loop(); } });
        t.setDaemon(true);
        t.start();
        return port;
    }

    public void stop() {
        running = false;
        try { ss.close(); } catch (Throwable ignore) { }
    }

    private void loop() {
        while (running) {
            try {
                final Socket s = ss.accept();
                Thread th = new Thread(new Runnable() { public void run() { handle(s); } });
                th.setDaemon(true);
                th.start();
            } catch (Throwable e) {
                if (running) { try { Thread.sleep(50); } catch (Throwable ignore) { } }
            }
        }
    }

    private void handle(Socket s) {
        try {
            // ★ 按「字节」读请求：Content-Length 是字节数，用 Reader 按字符读会在
            //   中文 body 时少读 → 关连接触发 RST（curl 表现为 http=000 / 响应被截断）
            java.io.InputStream raw = s.getInputStream();
            java.io.ByteArrayOutputStream hb = new java.io.ByteArrayOutputStream();
            int prev3 = -1, prev2 = -1, prev1 = -1, ch;
            while ((ch = raw.read()) >= 0) {
                hb.write(ch);
                if (prev3 == '\r' && prev2 == '\n' && prev1 == '\r' && ch == '\n') break;
                prev3 = prev2; prev2 = prev1; prev1 = ch;
            }
            String headText = new String(hb.toByteArray(), "UTF-8");
            String[] headLines = headText.split("\r\n");
            String line = headLines.length > 0 ? headLines[0] : "";
            String[] parts = line.split(" ");
            String method = parts.length > 0 ? parts[0] : "GET";
            String full = parts.length > 1 ? parts[1] : "/";
            Map<String, String> h = new HashMap<String, String>();
            for (int li = 1; li < headLines.length; li++) {
                String l2 = headLines[li];
                int ci = l2.indexOf(':');
                if (ci > 0) h.put(l2.substring(0, ci).trim().toLowerCase(), l2.substring(ci + 1).trim());
            }
            int cl = 0;
            try { cl = Integer.parseInt(h.containsKey("content-length") ? h.get("content-length") : "0"); } catch (Throwable ignore) { }
            String body = "";
            if (cl > 0) {
                byte[] bb = new byte[cl];
                int rd = 0;
                while (rd < cl) { int n = raw.read(bb, rd, cl - rd); if (n < 0) break; rd += n; }
                body = new String(bb, 0, rd, "UTF-8");
            }
            android.util.Log.i("C3ShellWeb", method + " " + full);
            String path = full, query = "";
            int qi = full.indexOf('?');
            if (qi >= 0) { path = full.substring(0, qi); query = full.substring(qi + 1); }

            if (path.startsWith("/api/")) {
                if (api != null) {
                    try { if (api.stream(s, method, path, query, h)) return; } catch (Throwable ignore) { }
                }
                String out;
                int code = 200;
                try {
                    long t0 = System.currentTimeMillis();
                    out = api != null ? api.handle(method, path, query, body, h) : "{\"ok\":false,\"error\":{\"message\":\"no api\"}}";
                    long ms = System.currentTimeMillis() - t0;
                    if (out == null) { out = "{\"ok\":false,\"error\":{\"message\":\"not found\"}}"; code = 404; }
                    /* 2026-09-25 用户要求「日志不要把什么东西都写上去」✓
                       轮询类 GET 成功 → 不逐条记（只计数，每 5 分钟汇总一行「轮询 N 次」）✓
                       只有「出错 / 慢（≥1500ms）/ POST（会改状态）/ 返回 ok:false」才逐条记 ✓ */
                    boolean isLogApi = "/api/log".equals(path) || "/api/log/clear".equals(path);   /* 别给日志本身再写日志 ✗ */
                    boolean quietReq = query != null && query.indexOf("quiet=1") >= 0;             /* 页面标了「这是轮询」→ 不写 ✓ */
                    /* 规则（2026-09-25 用户：日志别什么都写 ✓）：
                       逐条写的只有「出错的 / 慢的（≥1500ms）/ 真干了活的 POST（≥300ms）」；
                       纯轮询（成功的 GET、秒回的 POST）只计数，每 5 分钟汇总一行 ✓ */
                    boolean notable = !isLogApi && !quietReq && (code != 200
                                      || out.indexOf("\"ok\":false") >= 0
                                      || ms >= 1500
                                      || ("POST".equalsIgnoreCase(method) && ms >= 300));
                    if (isLogApi) { /* 跳过 */ }
                    else if (notable) logReq(method + " " + path + " " + out.length() + " " + code,
                                             (code == 200 ? "" : ("!" + code + " ")) + method + " " + path
                                             + " " + out.length() + "B " + ms + "ms");
                    else quiet(ms);
                } catch (Throwable e) {
                    code = 500;
                    out = "{\"ok\":false,\"error\":{\"message\":\"" + String.valueOf(e.getMessage()).replace("\"", "'") + "\"}}";
                }
                send(s, code, "application/json; charset=utf-8", out.getBytes("UTF-8"));
                return;
            }

            String name = (path.equals("/") || path.equals("/index.html")) ? "page.html" : path.substring(1);
            boolean wantDiag = name.equals("diag") || name.equals("diag.html");
            // 原始版（2.48）两页独立：/diag 直接给 diag.html ✗→✓（包内没有 diag.html 时才回退合并文档）
            if (wantDiag) name = (readAsset("diag.html") != null) ? "diag.html" : "page.html";
            byte[] data = readAsset(name);
            if (data == null) { send(s, 404, "text/plain; charset=utf-8", "not found".getBytes("UTF-8")); return; }
            String ct2 = ctype(name);
            if (ct2.startsWith("text/") || ct2.startsWith("application/javascript")) {
                // 页面里的占位符按连接器同样的约定替换（否则页面会去请求 /__API__/...）
                String ver = "";
                try { ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
                String title = wantDiag ? "诊断台" : "控制台";
                String t = new String(data, "UTF-8")
                        .replace("__API__", "/api/ssh")
                        .replace("__TOKEN__", "embedded")
                        .replace("__VENDOR__", "/vendor")     // xterm 等内置前端库
                        .replace("__TITLE__", title)
                        .replace("__APPVER__", ver)
                        .replace("__KEEP__", "null");
                data = t.getBytes("UTF-8");
            }
            send(s, 200, ct2, data);
        } catch (Throwable e) {
            android.util.Log.w("C3ShellWeb", "handle error: " + e);
            try { s.close(); } catch (Throwable ignore) { }
        }
    }

    private byte[] readAsset(String n) {
        try {
            InputStream is = Sec.open(ctx, n);
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int k;
            while ((k = is.read(buf)) > 0) bo.write(buf, 0, k);
            is.close();
            return bo.toByteArray();
        } catch (Throwable e) { return null; }
    }

    private static String ctype(String n) {
        if (n.endsWith(".css")) return "text/css; charset=utf-8";
        if (n.endsWith(".js")) return "text/javascript; charset=utf-8";
        if (n.endsWith(".html")) return "text/html; charset=utf-8";
        if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";     // 2026-09-24 R2b：封面/赞赏图给对 MIME ✓
        if (n.endsWith(".png")) return "image/png";
        if (n.endsWith(".webp")) return "image/webp";
        if (n.endsWith(".gif")) return "image/gif";
        return "application/octet-stream";
    }

    private static void send(Socket s, int code, String ct, byte[] body) throws IOException {
        String st = code == 200 ? "200 OK" : (code == 404 ? "404 Not Found" : "500 Internal Server Error");
                // 大响应自动 gzip（2026-09-21 优化：参数 1.37MB → 约 150KB，车机 WebView 74 也支持）
        byte[] out2 = body;
        String encHdr = "";
        if (false && body != null && body.length > 8192) {   // gzip 关闭（2026-09-21：疑似导致诊断页面板空白，先保正确性）
            try {
                java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                java.util.zip.GZIPOutputStream gz = new java.util.zip.GZIPOutputStream(bo, 8192);
                gz.write(body); gz.finish(); gz.close();
                byte[] z = bo.toByteArray();
                if (z.length < body.length) { out2 = z; encHdr = "Content-Encoding: gzip\r\n"; }
            } catch (Throwable ignore) { }
        }
String head = "HTTP/1.1 " + st + "\r\nContent-Type: " + ct + "\r\n" + encHdr + "Content-Length: " + out2.length +
                "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
        s.getOutputStream().write(head.getBytes("UTF-8"));
        s.getOutputStream().write(out2);
        s.getOutputStream().flush();
        s.close();
    }
}
