package com.padagent.c3shell;

import android.content.Context;
import android.util.Base64;

import com.jcraft.jsch.ChannelExec;
import com.jcraft.jsch.ChannelShell;
import com.jcraft.jsch.JSch;
import com.jcraft.jsch.Session;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** SSH 引擎（方案 C 第②片）：纯 Java（JSch），不需要 ssh 二进制。
 *  支持：连接测试 / 单命令执行 / 交互式终端（含 SSE 输出流）。 */
public class Ssh {

    /** 交互类接口的连接超时（2026-09-21 用户反馈"参数页卡死"：原来 15~30s 等待太久，收到 8s） */
    static int TMO = 8000;
    private final Context ctx;
    private final Map<String, Term> terms = new HashMap<String, Term>();

    public Ssh(Context c) { ctx = c; }

    // ── 配置与密钥 ────────────────────────────────────────────────────────
    public String host() { return p().getString("host", "192.168.31.49"); }
    public int port() { return p().getInt("port", 22); }
    public String user() { return p().getString("user", "comma"); }
    private android.content.SharedPreferences p() {
        return ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE);
    }

    /** 找私钥：显式路径 → 外部私有目录 → 内部私有目录 → 命名密钥位。 */
    public String resolveKey(String given) {
        List<File> cands = new ArrayList<File>();
        if (given != null && given.length() > 0) {
            File f = new File(given);
            if (f.isAbsolute()) cands.add(f);
            File ext = ctx.getExternalFilesDir(null);
            if (ext != null) { cands.add(new File(ext, given)); cands.add(new File(new File(ext, "named-keys"), given)); }
            cands.add(new File(ctx.getFilesDir(), given));
            cands.add(new File(new File(ctx.getFilesDir(), "named-keys"), given));
        }
        File ext = ctx.getExternalFilesDir(null);
        if (ext != null) {
            cands.add(new File(ext, "id_ed25519"));
            cands.add(new File(new File(ext, "named-keys"), "神牛"));
            cands.add(new File(new File(ext, "named-keys"), "雨落倾城"));
        }
        cands.add(new File(ctx.getFilesDir(), "id_ed25519"));
        for (File f : cands) { if (f != null && f.isFile() && f.length() > 0) return f.getAbsolutePath(); }
        return null;
    }

    private Session connect(String host, int port, String user, String key, String pass, int timeoutMs) throws Exception {
        JSch jsch = new JSch();
        String k = resolveKey(key);
        if (k != null) jsch.addIdentity(k);
        Session s = jsch.getSession(user, host, port);
        s.setConfig("StrictHostKeyChecking", "no");
        s.setConfig("PreferredAuthentications", (k != null ? "publickey" : "") + (pass != null && pass.length() > 0 ? ",password" : ""));
        if (pass != null && pass.length() > 0) s.setPassword(pass);
        s.connect(timeoutMs);
        return s;
    }

    // ---------------- KEEP_REUSE：SSH 会话复用（v1.7 #9 连机提速）----------------
    /** 原来每条命令都新建 SSH 连接 → 建连 ~0.44s 占了 ~90% 耗时 ✗
     *  这里缓存一个会话反复用 ✓，命令耗时从 ~0.49s 降到 ~0.05s ✓ */
    private Session keepSess;
    private String keepSig;
    private final Object keepLock = new Object();


    // ── 2026-09-24 用户反馈「APP 界面切页/滚动卡、点菜单没反应」──────────────────
    //   真因：设备不在线时，页面每 5 秒轮询 /drive/status，每次都走一趟 TCP+SSH 握手（超时 8s）；
    //   5s < 8s → 请求互相叠加；浏览器同源只允许 6 条连接 → 点菜单发起的请求全在排队 ✗
    //   对策（三件一起）：① 先做 700ms TCP 预探测（离线时 <1s 就返回）
    //                    ② 失败后 8 秒内不再真连（负缓存）→ 轮询立刻得到"未连接"
    //                    ③ 同一时刻只允许一次真连（其它请求立即返回"正在连接"）✓
    private static final Object dialLock = new Object();
    private static volatile long failAt = 0L;
    private static volatile String failHost = null;
    private static volatile boolean dialing = false;
    private static final int FAIL_COOLDOWN_MS = 8000;

    /** 这台主机是不是"刚刚连不上"（页面据此秒回"未连接"，不再排队 ✓）*/
    public static boolean offlineRecently(String host) {
        return failHost != null && failHost.equals(host) && (System.currentTimeMillis() - failAt) < FAIL_COOLDOWN_MS;
    }

    private static void tcpPrecheck(String host, int port, int ms) throws Exception {
        java.net.Socket t = new java.net.Socket();
        try { t.connect(new java.net.InetSocketAddress(host, port), ms); }
        finally { try { t.close(); } catch (Throwable ignore) { } }
    }

    /** 所有真连都走这里：预探测 + 负缓存 + 单飞（force=true 表示用户手动点的「测试连接」）*/
    private Session dial(String host, int port, String user, String key, String pass, int timeoutMs, boolean force) throws Exception {
        if (!force && offlineRecently(host)) {
            long left = (FAIL_COOLDOWN_MS - (System.currentTimeMillis() - failAt)) / 1000 + 1;
            throw new Exception("设备未连接（" + left + " 秒后自动重试）");
        }
        synchronized (dialLock) {
            if (!force) {
                if (dialing) throw new Exception("正在连接设备…");
                if (offlineRecently(host)) throw new Exception("设备未连接（自动重试中）");
            }
            dialing = true;
            try {
                tcpPrecheck(host, port, 700);        // 离线时在这里就失败，不再拖满 8 秒 ✓
                Session s = connect(host, port, user, key, pass, timeoutMs);
                failHost = null; failAt = 0;
                return s;
            } catch (Exception e) {
                failHost = host; failAt = System.currentTimeMillis();
                throw e;
            } finally {
                dialing = false;
            }
        }
    }

    private Session reused(String host, int port, String user, String key, String pass, int timeoutMs) throws Exception {
        String sig = user + "@" + host + ":" + port + "#" + String.valueOf(key) + "#" + (pass != null);
        synchronized (keepLock) {
            if (keepSess != null && keepSess.isConnected() && sig.equals(keepSig)) return keepSess;
            if (keepSess != null) { try { keepSess.disconnect(); } catch (Throwable ignore) { } keepSess = null; }
            Session s = dial(host, port, user, key, pass, timeoutMs, false);
            try { s.setServerAliveInterval(15000); } catch (Throwable ignore) { }
            keepSess = s; keepSig = sig;
            return s;
        }
    }

    /** 复用模式下不主动断开 ✓（异常时丢弃缓存以便下次重连 ✓）*/
    private void dropKeep() {
        synchronized (keepLock) {
            if (keepSess != null) { try { keepSess.disconnect(); } catch (Throwable ignore) { } keepSess = null; keepSig = null; }
        }
    }

    public String stateJson() {
        return "{\"ok\":true,\"embedded\":true,\"defaultHostId\":\"c3\",\"hosts\":[{"
                + "\"id\":\"c3\",\"label\":\"C3 设备\",\"host\":\"" + esc(host()) + "\",\"port\":" + port()
                + ",\"user\":\"" + esc(user()) + "\",\"mode\":\"ssh\",\"target\":\"" + esc(user() + "@" + host() + ":" + port())
                + "\",\"keyPath\":\"" + esc(String.valueOf(resolveKey(null))) + "\"}]}";
    }

    /** 连接测试：连上并跑一条命令，返回 banner 与耗时。 */
    public String testJson(String host, int port, String user, String key, String pass) {
        long t0 = System.currentTimeMillis();
        Session s = null;
        try {
            s = dial(host, port, user, key, pass, TMO, true);   // 手动「测试连接」：绕过负缓存，但仍先 TCP 预探测 ✓
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand("echo ok; uname -a");
            InputStream in = ch.getInputStream();
            ch.connect();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            ch.disconnect();
            String out = bo.toString("UTF-8");
            List<String> banner = new ArrayList<String>();
            for (String line : out.split("\n")) if (line.trim().length() > 0) banner.add(line.trim());
            StringBuilder b = new StringBuilder();
            for (int i = 0; i < banner.size(); i++) { if (i > 0) b.append(','); b.append('"').append(esc(banner.get(i))).append('"'); }
            return "{\"ok\":true,\"result\":{\"ok\":true,\"code\":0,\"latencyMs\":" + (System.currentTimeMillis() - t0)
                    + ",\"banner\":[" + b + "],\"error\":null}}";
        } catch (Throwable e) {
            return "{\"ok\":true,\"result\":{\"ok\":false,\"code\":-1,\"latencyMs\":" + (System.currentTimeMillis() - t0)
                    + ",\"banner\":[],\"error\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}";
        } finally {
            // KEEP_REUSE2：共用会话不断开（坏了由 reused() 的 isConnected 自愈 ✓）
        }
    }


    /** 文件操作（2026-09-24）：文件页的「改名 / 删除 / 新建文件夹」在页面里走 /fs（APP 侧 = /api/ssh/fs）。
     *  独立版此前**只实现了 /ls，没有 fs** → 点了没反应（用户反馈「不能改文件名」✗）。 */
    public String fsOpJson(String op, String path, String to, String host, int port, String user, String key) {
        if (path == null || path.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"路径为空\"}}";
        String p = shq(path);
        String cmd;
        if ("rename".equals(op)) {
            if (to == null || to.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"新名称/路径为空\"}}";
            cmd = "test -e " + p + " || { echo __NOENT__; exit 0; }; mv -n " + p + " " + shq(to) + " && echo __OK__";
        } else if ("remove".equals(op)) {
            cmd = "rm -rf " + p + " && echo __OK__";
        } else if ("mkdir".equals(op)) {
            cmd = "mkdir -p " + p + " && echo __OK__";
        } else if ("copy".equals(op) || "move".equals(op)) {
            /* 2026-09-27 v3.00.71：文件页的「复制 / 移动」+ 粘贴 ✓
               to = 目标**完整路径**（页面算好 目录/名字）→ 对文件与目录都成立 ✓
               移动用 -n（不覆盖已有），复制用 -a（保留权限/时间，目录可递归 ✓） */
            if (to == null || to.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"目标路径为空\"}}";
            cmd = "test -e " + p + " || { echo __NOENT__; exit 0; }; "
                + ("copy".equals(op) ? "cp -a " : "mv -n ") + p + " " + shq(to) + " && echo __OK__";
        } else {
            return "{\"ok\":false,\"error\":{\"message\":\"不支持的操作\"}}";
        }
        String r = execJson(cmd, host, port, user, key);
        if (r != null && r.indexOf("__OK__") >= 0) return "{\"ok\":true}";
        if (r != null && r.indexOf("__NOENT__") >= 0) return "{\"ok\":false,\"error\":{\"message\":\"文件/目录不存在\"}}";
        return "{\"ok\":false,\"error\":{\"message\":\"操作失败（权限或路径问题）\"}}";
    }

    /** 设备 ⇄ 本机 文件传输（2026-09-27 v3.00.71）
     *  用户要求：文件页要能复制/移动，并且**可以选本机储存**。
     *  用 JSch 的 SFTP **流式**传（不走 base64 ✓）→ 几百 MB 的 qlog 也不会把内存顶爆 ✓
     *  dir="down"：设备 → 本机；dir="up"：本机 → 设备（先建本机父目录 ✓） */
    public String xferJson(String dir, String remote, String local, String host, int port, String user, String key) {
        if (remote == null || remote.length() == 0 || local == null || local.length() == 0)
            return "{\"ok\":false,\"error\":{\"message\":\"路径为空\"}}";
        long t0 = System.currentTimeMillis();
        Session s = null;
        try {
            java.io.File lf = new java.io.File(local);
            if ("up".equals(dir)) {
                if (!lf.isFile()) return "{\"ok\":false,\"error\":{\"message\":\"本机没有这个文件（或不是文件）：" + Ssh.esc(local) + "\"}}";
            } else if (lf.isDirectory()) {
                return "{\"ok\":false,\"error\":{\"message\":\"本机目标是个目录，请指定文件名\"}}";
            }
            s = session();
            com.jcraft.jsch.ChannelSftp sf = (com.jcraft.jsch.ChannelSftp) s.openChannel("sftp");
            sf.connect(8000);
            long n = 0;
            if ("up".equals(dir)) {
                java.io.InputStream is = new java.io.FileInputStream(lf);
                sf.put(is, remote);
                try { is.close(); } catch (Throwable ignore) { }
                n = lf.length();
            } else {
                java.io.File par = lf.getParentFile();
                if (par != null && !par.exists()) par.mkdirs();
                java.io.OutputStream os = new java.io.FileOutputStream(lf);
                sf.get(remote, os);
                try { os.flush(); os.close(); } catch (Throwable ignore) { }
                n = lf.length();
            }
            try { sf.disconnect(); } catch (Throwable ignore) { }
            return "{\"ok\":true,\"bytes\":" + n + ",\"ms\":" + (System.currentTimeMillis() - t0) + "}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}";
        } finally {
            // KEEP_REUSE2：共用会话不断开 ✓
        }
    }

    /** 单命令执行。 */
    public String execJson(String cmd, String host, int port, String user, String key) {
        final int LIMIT_EXEC = 200 * 1024;   // 单次 exec 返回上限（2026-09-21：1.46MB 曾把车机 WebView 渲染进程压死）
        Session s = null;
        boolean failed = false;   // 失败才丢弃复用会话 ✓
        try {
            s = reused(host, port, user, key, null, TMO);   // KEEP_REUSE ✓
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd);
            InputStream in = ch.getInputStream();
            InputStream er = ch.getErrStream();
            ch.connect();
            ByteArrayOutputStream o = new ByteArrayOutputStream(), e = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) { if (o.size() < LIMIT_EXEC) o.write(buf, 0, Math.min(n, LIMIT_EXEC - o.size())); }
            while (er.available() > 0 && (n = er.read(buf)) > 0) { if (e.size() < 8192) e.write(buf, 0, Math.min(n, 8192 - e.size())); }
            int code = ch.getExitStatus();
            ch.disconnect();
            return "{\"ok\":true,\"result\":{\"ok\":true,\"code\":" + code
                    + ",\"stdout\":\"" + esc(o.toString("UTF-8")) + "\",\"stderr\":\"" + esc(e.toString("UTF-8")) + "\"}}";
        } catch (Throwable ex) {
            failed = true;
            return "{\"ok\":true,\"result\":{\"ok\":false,\"code\":-1,\"stdout\":\"\",\"stderr\":\"" + esc(Errs.zh(String.valueOf(ex.getMessage()))) + "\"}}";
        } finally {
            if (s != null && failed) dropKeep();   // 成功则保留复用 ✓
        }
    }

    // ── 交互式终端 ────────────────────────────────────────────────────────
    static class Term {
        Session s; ChannelShell ch; OutputStream out;
        final ByteArrayOutputStream buf = new ByteArrayOutputStream();
        final List<Socket> subs = new ArrayList<Socket>();
        boolean closed;
        /** 滚动缓冲（最多 64KB）：供 /term/tail 轮询兜底用，SSE 消费不影响它 */
        final ByteArrayOutputStream tailBuf = new ByteArrayOutputStream();

        synchronized void push(byte[] b) {
            try { buf.write(b); } catch (Throwable ignore) { }
            try {
                tailBuf.write(b);
                if (tailBuf.size() > 65536) {                 // 超过 64KB 保留最后 48KB
                    byte[] all = tailBuf.toByteArray();
                    tailBuf.reset();
                    tailBuf.write(all, all.length - 49152, 49152);
                }
            } catch (Throwable ignore) { }
            int ok = 0, bad = 0;
            for (Socket so : new ArrayList<Socket>(subs)) {
                try { sendFrame(so.getOutputStream(), b); ok++; }   // 必须按 SSE 封帧（data: {"b64":…}），否则浏览器忽略
                catch (Throwable e) { bad++; subs.remove(so); }
            }
            android.util.Log.i("C3ShellTerm", "push " + b.length + "B subs=" + subs.size() + " ok=" + ok + " bad=" + bad);
        }
    }

    public String openTermJson(String host, int port, String user, String key, int cols, int rows) {
        // 幂等：已有活动会话就复用（用户反馈"每次重连都新开一个会话"，导致屏幕会话与发送目标错位）
        for (java.util.Map.Entry<String, Term> e : terms.entrySet()) {
            Term t = e.getValue();
            if (t != null && !t.closed) {
                lastTermId = e.getKey();
                android.util.Log.i("C3ShellTerm", "reuse session " + e.getKey());
                return "{\"ok\":true,\"sessionId\":\"" + e.getKey() + "\",\"cols\":" + cols + ",\"rows\":" + rows + ",\"reused\":true}";
            }
        }
        try {
            Session s = dial(host, port, user, key, null, TMO, false);
            ChannelShell ch = (ChannelShell) s.openChannel("shell");
            ch.setPtyType("xterm-256color", cols, rows, 0, 0);
            final InputStream in = ch.getInputStream();
            final OutputStream out = ch.getOutputStream();
            final Term t = new Term();
            t.s = s; t.ch = ch; t.out = out;
            ch.connect(10000);
            String id = "t" + System.currentTimeMillis();
            lastTermId = id;
            terms.put(id, t);
            Thread th = new Thread(new Runnable() { public void run() {
                byte[] b = new byte[8192];
                try { int n; while ((n = in.read(b)) > 0) t.push(java.util.Arrays.copyOf(b, n)); } catch (Throwable ignore) { }
                t.closed = true; t.push("\r\n[连接已断开]\r\n".getBytes());
            } });
            th.setDaemon(true); th.start();
            return "{\"ok\":true,\"sessionId\":\"" + id + "\",\"cols\":" + cols + ",\"rows\":" + rows + "}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}";
        }
    }

    /** 最近打开的终端会话（供 APP 原生输入条使用，页面不用参与） */
    private volatile String lastTermId;
    public String lastTermId() { return lastTermId; }
    public void setLastTerm(String id) { if (id != null && id.length() > 0) lastTermId = id; }

    /** 原生输入条：把文本送进终端（APP 底部那条输入框）。
     *  2026-09-24 改：**优先写 shell 的 stdin** —— 实测这套镜像写入有效（回显 57ms、输出还是流式的 ✓）。
     *  老实现是「另开一条 exec 连接、等命令跑完、再把结果整块塞进终端」：
     *  每次 400ms+（新建 SSH 握手），长命令（top/ls -R/编译）更是完全没有流式 ✗ —— 用户反馈「终端卡」就是它。
     *  只有没有活跃 shell 会话时才退回 exec，并且**复用会话**，不再每次握手。 */
    public String sendToTerm(String text) {
        String cmd = (text == null ? "" : text).replace("\r", "").replace("\n", "").trim();
        if (cmd.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"请输入命令\"}}";
        Term t = (lastTermId != null) ? terms.get(lastTermId) : null;
        if (t == null && !terms.isEmpty()) t = terms.values().iterator().next();
        if (t != null) {
            try {
                t.out.write((cmd + "\n").getBytes("UTF-8"));
                t.out.flush();
                android.util.Log.i("C3ShellTerm", "stdin-send " + cmd);
                return "{\"ok\":true,\"mode\":\"stdin\"}";
            } catch (Throwable ignore) { }
        }
        String out;
        try {
            Store.Host h = new Store(ctx).defaultHost();
            String host = h != null ? h.host : host();
            int port = h != null ? h.port : port();
            String user = h != null ? h.user : user();
            String key = h != null ? h.key : null;
            Session s = reused(host, port, user, key, null, TMO);   // 复用会话：别再握手 ✗
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd);
            InputStream in = ch.getInputStream();
            InputStream er = ch.getErrStream();
            ch.connect(8000);
            ByteArrayOutputStream o = new ByteArrayOutputStream(), e = new ByteArrayOutputStream();
            byte[] b = new byte[8192];
            int n;
            while ((n = in.read(b)) > 0) o.write(b, 0, n);
            while (er.available() > 0 && (n = er.read(b)) > 0) e.write(b, 0, n);
            ch.disconnect();
            out = o.toString("UTF-8") + e.toString("UTF-8");
            if (out.length() == 0) out = "(无输出)";
        } catch (Throwable t2) {
            out = "执行失败：" + Errs.zh(String.valueOf(t2.getMessage())) + "\r\n";
        }
        String echo = "\u001b[38;5;245m$ " + cmd + "\u001b[0m\r\n" + out + (out.endsWith("\n") ? "" : "\r\n");
        byte[] data = echo.getBytes();
        int k = 0;
        for (Term tt : terms.values()) { try { tt.push(data); k++; } catch (Throwable ignore) { } }
        android.util.Log.i("C3ShellTerm", "exec-send cmd=" + cmd + " -> pushed to " + k + " session(s), out=" + out.length() + "B");
        return "{\"ok\":true,\"sent\":" + k + ",\"sessions\":" + terms.size() + ",\"outBytes\":" + out.length() + "}";
    }

    /** 终端内容轮询兜底（2026-09-21：老 WebView 上 SSE 不可用时用 XHR 拉） */
    public String termTail(String id, String since) {
        try {
            if (id == null || id.length() == 0) id = lastTermId;
            Term t = (id == null) ? null : terms.get(id);
            if (t == null) return "{\"ok\":false,\"error\":{\"message\":\"会话不存在\"}}";
            byte[] all;
            synchronized (t) { all = t.tailBuf.toByteArray(); }
            int from = 0;
            try { from = Integer.parseInt(since); } catch (Throwable ignore) { }
            if (from < 0 || from > all.length) from = 0;
            String txt = new String(all, from, all.length - from, "UTF-8");
            return "{\"ok\":true,\"text\":\"" + esc(txt) + "\",\"next\":" + all.length + "}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(e)) + "\"}}";
        }
    }

    public String inputJson(String id, String b64) {
        Term t = terms.get(id);
        if (t == null) return "{\"ok\":false,\"error\":{\"message\":\"unknown session\"}}";
        try { t.out.write(Base64.decode(b64, Base64.DEFAULT)); t.out.flush(); return "{\"ok\":true}"; }
        catch (Throwable e) { return "{\"ok\":false,\"error\":{\"message\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}"; }
    }

    public void closeTerm(String id) {
        Term t = terms.remove(id);
        if (t != null) { try { t.ch.disconnect(); } catch (Throwable ignore) { } try { t.s.disconnect(); } catch (Throwable ignore) { } }
    }

    /** SSE：先把 backlog 用 data: 发出去，之后每次有新输出就发一帧（含心跳）。 */
    public boolean termStream(Socket sock, String id) throws Exception {
        final Term t = terms.get(id);
        if (t == null) return false;
        OutputStream o = sock.getOutputStream();
        String head = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\n"
                + "Cache-Control: no-cache, no-store\r\nConnection: keep-alive\r\n\r\n";
        o.write(head.getBytes("UTF-8"));
        byte[] back;
        synchronized (t) {
            // 单查看者：新流接入时踢掉旧订阅者（旧 socket 写入不报错但页面收不到，2026-09-21 实测）
            for (Socket old : new java.util.ArrayList<Socket>(t.subs)) { try { old.close(); } catch (Throwable ignore) { } }
            t.subs.clear();
            back = t.buf.toByteArray(); t.buf.reset(); t.subs.add(sock);
        }
        android.util.Log.i("C3ShellTerm", "stream attach id=" + id + " backlog=" + back.length + " subs=" + t.subs.size());
        if (back.length > 0) sendFrame(o, back);
        int idle = 0;
        while (!t.closed) {
            Thread.sleep(200);
            synchronized (t) { }
            idle++;
            if (idle % 75 == 0) { try { o.write(": ping\n\n".getBytes("UTF-8")); o.flush(); } catch (Throwable ignore) { break; } }
        }
        // 断开时把剩余输出发完
        synchronized (t) { back = t.buf.toByteArray(); t.buf.reset(); t.subs.remove(sock); }
        if (back.length > 0) sendFrame(o, back);
        try { o.flush(); sock.close(); } catch (Throwable ignore) { }
        return true;
    }

    private static void sendFrame(OutputStream o, byte[] data) throws Exception {
        String b64 = Base64.encodeToString(data, Base64.NO_WRAP);
        o.write(("data: {\"b64\":\"" + b64 + "\"}\n\n").getBytes("UTF-8"));
        o.flush();
    }

    // ── 远端脚本：内置在 assets 里，首次用 SFTP 推上去，之后按大小变化重传 ──
    private static final String REMOTE_DIR = "/data/openpilot/.dsh";

    private Session session() throws Exception {
        Store.Host h = new Store(ctx).defaultHost();
        String host = h != null ? h.host : host();
        int port = h != null ? h.port : port();
        String user = h != null ? h.user : user();
        String key = h != null ? h.key : null;
        return reused(host, port, user, key, null, TMO);   // KEEP_REUSE2：数据路径共用会话 ✓
    }

    private byte[] asset(String name) {
        try {
            java.io.InputStream is = Sec.open(ctx, name);
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[8192];
            int n;
            while ((n = is.read(b)) > 0) bo.write(b, 0, n);
            is.close();
            return bo.toByteArray();
        } catch (Throwable e) { return null; }
    }

    /** 确保远端脚本存在且是最新的；返回远端路径（失败返回 null）。 */
    public String ensureRemote(Session s, String assetName, String remoteName) {
        try {
            byte[] want = asset("remote/" + assetName);
            if (want == null) return null;
            String path = REMOTE_DIR + "/" + remoteName;
            com.jcraft.jsch.ChannelSftp sftp = (com.jcraft.jsch.ChannelSftp) s.openChannel("sftp");
            sftp.connect(8000);
            boolean need = true;
            try {
                com.jcraft.jsch.SftpATTRS a = sftp.lstat(path);
                if (a.getSize() == want.length) need = false;
            } catch (Throwable ignore) { }
            if (need) {
                try { sftp.mkdir(REMOTE_DIR); } catch (Throwable ignore) { }
                sftp.put(new java.io.ByteArrayInputStream(want), path);
            }
            sftp.disconnect();
            return path;
        } catch (Throwable e) { return null; }
    }

    /** 跑远端 python 小工具，返回它的 stdout（JSON 文本）。 */
    /** 2026-09-24 R100：远端调用**失败自动重试** ✓
     *  起因：诊断台偶发「重放路线获取失败」。实测 APP 日志里 /routes 有时返回 40~43 字节的
     *  {"ok":false,…} 且耗时 8~16 秒 —— 就是 openChannel(8000) 超时 ✗
     *  （车机忙时最容易中：路线扫描会把 C3 CPU 打到 90%+；共用会话被占用时同理）
     *  这类失败是**瞬时**的，重试一两次基本都能过 ✓ */
    private String runRemote(String assetName, String remoteName, String args, String stdinB64) {
        String r = runRemoteOnce(assetName, remoteName, args, stdinB64);
        for (int i = 0; i < 2 && remoteErr(r); i++) {
            try { Thread.sleep(400L * (i + 1)); } catch (Throwable ignore) { }
            r = runRemoteOnce(assetName, remoteName, args, stdinB64);
        }
        return r;
    }
    private static boolean remoteErr(String r) {
        if (r == null) return true;
        String t = r.trim();
        return t.length() == 0 || t.startsWith("{\"ok\":false");
    }

    private String runRemoteOnce(String assetName, String remoteName, String args, String stdinB64) {
        Session s = null;
        try {
            s = session();
            String path = ensureRemote(s, assetName, remoteName);
            if (path == null) return "{\"ok\":false,\"error\":{\"message\":\"上传远端脚本失败\"}}";
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand("python3 " + path + " " + args);
            java.io.OutputStream cin = ch.getOutputStream();
            InputStream in = ch.getInputStream();
            ch.connect(8000);
            if (stdinB64 != null) { cin.write(stdinB64.getBytes("UTF-8")); cin.flush(); }
            try { cin.close(); } catch (Throwable ignore) { }
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[16384];
            int n;
            while ((n = in.read(b)) > 0) bo.write(b, 0, n);
            ch.disconnect();
            String out = bo.toString("UTF-8").trim();
            return out.length() > 0 ? out : "{\"ok\":false,\"error\":{\"message\":\"远端无输出\"}}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}";
        } finally {
            // KEEP_REUSE2：共用会话不断开（坏了由 reused() 的 isConnected 自愈 ✓）
        }
    }

    private static String shq(String v) {
        if (v == null) return "''";
        return "'" + v.replace("'", "'\\''") + "'";
    }

    public String lsJson(String path) { return runRemote("dsh_remote.py", "dsh_remote.py", "ls " + shq(path == null ? "/data/openpilot" : path), null); }
    public String readJson(String path) { return runRemote("dsh_remote.py", "dsh_remote.py", "read " + shq(path), null); }
    public String writeJson(String path, String b64) { return runRemote("dsh_remote.py", "dsh_remote.py", "write " + shq(path), b64); }
    /** 截断超长字符串值（2026-09-21 日志定位）：
     *  LiveTorqueParameters 这一个二进制值就 283,058 字符 → 整个载荷 1.26MB，
     *  车机 Chromium74 光 JSON.parse + 渲染就冻结数秒（表现：参数页打不开/卡死）。
     *  截断后载荷降到几十 KB，页面秒开；被截断的值标注原长度。 */
    public static String trimLongStrings(String json, int max) {
        if (json == null) return null;
        StringBuilder o = new StringBuilder(json.length());
        int i = 0, n = json.length();
        while (i < n) {
            char c = json.charAt(i);
            if (c != '"') { o.append(c); i++; continue; }
            int j = i + 1; boolean esc = false; int lit = 0;
            while (j < n) {
                char d = json.charAt(j);
                if (esc) { esc = false; lit++; j++; continue; }
                if (d == '\\') { esc = true; j++; continue; }
                if (d == '"') break;
                lit++; j++;
            }
            if (lit > max) {
                // 整段替换为干净字符串：绝不保留原内容，避免切断 unicode 转义序列（v1.74 的教训）
                o.append("\"\u2026\uff08\u539f\u503c ").append(lit).append(" \u5b57\u7b26\uff0c\u53ef\u80fd\u662f\u4e8c\u8fdb\u5236/\u957f\u5217\u8868\uff0c\u5df2\u7701\u7565\uff09\"");
            } else {
                o.append(json, i, Math.min(j + 1, n));
            }
            i = j + (j < n ? 1 : 0);
        }
        return o.toString();
    }

    /** 参数：带磁盘缓存（车机 CPU 弱、远端 dump 要数秒~30s；缓存后秒开）。force=true 强制重读 */
    public String paramsAllJson() { return paramsAllJson(false); }
    public String paramsAllJson(boolean force) {
        java.io.File cf = new java.io.File(ctx.getFilesDir(), "params-cache.json");
        /* 2026-09-24：缓存必须跟 APP 版本绑定 —— 否则升级后（例如参数脚本换了）页面还在吃旧缓存。
           本人就被这个坑骗过一轮：缓存里是「149 键 / 无备注」的旧数据，看着像新功能没生效 ✗。
           版本不一致 = 当没缓存 ✓ */
        java.io.File vf = new java.io.File(ctx.getFilesDir(), "params-cache.ver");
        String pkgVer = "";
        try { pkgVer = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        boolean verOk = false;
        try {
            if (vf.exists()) {
                byte[] vb = new byte[(int) vf.length()];
                java.io.FileInputStream vin = new java.io.FileInputStream(vf);
                int vo = 0, vn; while (vo < vb.length && (vn = vin.read(vb, vo, vb.length - vo)) > 0) vo += vn;
                vin.close();
                verOk = pkgVer.equals(new String(vb, "UTF-8").trim());
            }
        } catch (Throwable ignore) { }
        if (!force && verOk && cf.exists() && cf.length() > 1000) {
            try {
                byte[] b = new byte[(int) cf.length()];
                java.io.FileInputStream in = new java.io.FileInputStream(cf);
                int off = 0, n; while (off < b.length && (n = in.read(b, off, b.length - off)) > 0) off += n;
                in.close();
                String cached = new String(b, "UTF-8");
                long age = System.currentTimeMillis() - cf.lastModified();
                int k = cached.indexOf(',');
                if ((cached.startsWith("{\"ok\":true") || cached.startsWith("{\"ok\": true")) && k > 0) {
                    android.util.Log.i("C3ShellParams", "cache hit age=" + (age / 1000) + "s");
                    // 缓存也要截断（旧缓存是未截断的大载荷）
                    return "{\"ok\":true,\"cached\":true,\"ageMs\":" + age + ",\"_cacheControl\":\"max-age=30\"" + trimLongStrings(cached.substring(k), 400);
                }
            } catch (Throwable ignore) { }
        }
        String r = paramsAllLive();
        if (r != null) r = trimLongStrings(r, 400);   // ★ 截断超长值
        try {
            boolean good = r != null && (r.indexOf("\"ok\":true") >= 0 || r.indexOf("\"ok\": true") >= 0)
                    && (r.indexOf("\"ok\":false") < 0 && r.indexOf("\"ok\": false") < 0);
            if (good) {
                java.io.FileOutputStream o = new java.io.FileOutputStream(cf);
                o.write(r.getBytes("UTF-8")); o.close();
                try {   // 记下这份缓存是哪个 APP 版本写的
                    java.io.FileOutputStream vo2 = new java.io.FileOutputStream(vf);
                    vo2.write(pkgVer.getBytes("UTF-8")); vo2.close();
                } catch (Throwable ignore) { }
                android.util.Log.i("C3ShellParams", "cache written " + cf.length() + "B ver=" + pkgVer);
            }
        } catch (Throwable ignore) { }
        return r;
    }

    private String paramsAllLive() {
        // 页面的参数功能会直接 exec `python3 /data/openpilot/dsh-params.py …`，
        // 独立版里也放一份到那个路径，保证页面流程可用。
        try {
            Session s2 = session();
            ensureRemote(s2, "params_dump.py", "params_dump.py");
            // 2026-09-24：中文备注词库随 APP 发布（设备端 settings.cc 在 SP 上已不存在）
            ensureRemote(s2, "param-notes-zh.json", "param-notes-zh.json");
            ensureRemoteAt(s2, "params_dump.py", "/data/openpilot/dsh-params.py");
            s2.disconnect();
        } catch (Throwable ignore) { }
        return runRemote("params_dump.py", "params_dump.py", "", null);
    }

    /** 把 asset 上传到指定远端绝对路径（大小一致则跳过）。 */
    public void ensureRemoteAt(Session s3, String assetName, String remotePath) {
        try {
            byte[] want = asset("remote/" + assetName);
            if (want == null) return;
            com.jcraft.jsch.ChannelSftp sftp = (com.jcraft.jsch.ChannelSftp) s3.openChannel("sftp");
            sftp.connect(8000);
            boolean need = true;
            try { if (sftp.lstat(remotePath).getSize() == want.length) need = false; } catch (Throwable ignore) { }
            if (need) sftp.put(new java.io.ByteArrayInputStream(want), remotePath);
            sftp.disconnect();
        } catch (Throwable ignore) { }
    }
    public String paramsSetJson(String pairs) { return runRemote("params_dump.py", "params_dump.py", "set " + pairs, null); }

    /** SP 适配（2026-09-24）：连上设备先问「你是哪个系统 + 能力如何」，APP 据此开关功能。
     *  设备侧 env_dump.py 只读探测（fork / 版本 / 参数库 / 服务 / 投屏钩子 / 路线）。 */
    public String envJson() {
        return runRemote("env_dump.py", "env_dump.py", "", null);
    }

    // ── 实时采样（第④片）：跑设备侧 live_stream.py，按行解析 JSON，
    //    通过 SSE 具名事件（sample / exit）推给诊断页 ──
    static class Live {
        Session s; ChannelExec ch;
        final java.util.List<String> samples = new java.util.ArrayList<String>();
        final java.util.List<Socket> subs = new java.util.ArrayList<Socket>();
        volatile boolean closed;
        volatile String stopReason;
        volatile String meta = "{}";
        final java.util.List<String> notes = new java.util.ArrayList<String>();
        synchronized void add(String sampleJson) {
            samples.add(sampleJson);
            while (samples.size() > 900) samples.remove(0);
            for (Socket so : new java.util.ArrayList<Socket>(subs)) {
                try { writeEvent(so.getOutputStream(), "sample", sampleJson); }
                catch (Throwable e) { subs.remove(so); }
            }
        }
    }
    private final java.util.Map<String, Live> lives = new java.util.HashMap<String, Live>();

    public String liveStart(String replay, int hz, boolean fast, int seconds) {
        try {
            Session s = session();
            String script = ensureRemote(s, "live_stream.py", "live_stream.py");
            if (script == null) return "{\"ok\":false,\"error\":{\"message\":\"上传采样脚本失败\"}}";
            StringBuilder cmd = new StringBuilder("python3 -u " + script);   // -u：采样是长流，必须无缓冲，否则管道里看不到样本
            if (replay != null && replay.length() > 0) cmd.append(" --replay ").append(shq(replay));
            else cmd.append(" --live");        // ★ 不指定回放时是实时模式（少了它脚本会直接退出）
            if (hz > 0) cmd.append(" --hz ").append(hz);
            if (fast) cmd.append(" --fast");
            if (seconds > 0) cmd.append(" --seconds ").append(seconds);
            final Live L = new Live(); L.s = s;
            final ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd.toString() + " 2>&1");   // 采样脚本的报错也要能看到（否则被 stderr 吞掉）
            final InputStream in = ch.getInputStream();
            ch.connect(8000);
            L.ch = ch;
            final String id = "l" + System.currentTimeMillis();
            lives.put(id, L);
            Thread th = new Thread(new Runnable() { public void run() {
                try {
                    java.io.BufferedReader r = new java.io.BufferedReader(new java.io.InputStreamReader(in, "UTF-8"));
                    String line;
                    while ((line = r.readLine()) != null) {
                        line = line.trim();
                        if (line.length() == 0) continue;
                        if (line.charAt(0) == '{') {
                            if (line.indexOf("\"meta\"") >= 0) L.meta = line; else L.add(line);
                        } else {
                            L.notes.add(line);                       // 非 JSON 行（含错误信息）留痕
                            if (L.notes.size() > 40) L.notes.remove(0);
                        }
                    }
                } catch (Throwable ignore) { }
                L.closed = true;
                if (L.stopReason == null) L.stopReason = "process-exit";
                if (!"api-stop".equals(L.stopReason)) { try { voice.say(cues().get("sampleEnd"), "live-end"); } catch (Throwable ignore) { } }
                for (Socket so : new java.util.ArrayList<Socket>(L.subs)) {
                    try { writeEvent(so.getOutputStream(), "exit", "{\"reason\":\"" + L.stopReason + "\"}"); } catch (Throwable ignore) { }
                }
            } });
            th.setDaemon(true);
            th.start();
            return "{\"ok\":true,\"session\":{\"id\":\"" + id + "\",\"replay\":\"" + esc(replay) + "\",\"hz\":" + hz + "}}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}";
        }
    }

    public String liveStatus() {
        StringBuilder b = new StringBuilder("{\"ok\":true,\"sessions\":[");
        boolean first = true;
        for (java.util.Map.Entry<String, Live> e : lives.entrySet()) {
            Live L = e.getValue();
            if (!first) b.append(',');
            first = false;
            b.append("{\"id\":\"").append(e.getKey()).append("\",\"running\":").append(!L.closed)
             .append(",\"samples\":").append(L.samples.size())
             .append(",\"stopReason\":").append(L.stopReason == null ? "null" : ("\"" + L.stopReason + "\""))
             .append(",\"notes\":\"").append(esc(joinNotes(L))).append("\"}");
        }
        return b.append("]}").toString();
    }

    private static String joinNotes(Live L) {
        StringBuilder b = new StringBuilder();
        for (String n : L.notes) { if (b.length() > 0) b.append(" | "); b.append(n); }
        return b.length() > 400 ? b.substring(b.length() - 400) : b.toString();
    }

    public String liveStop(String id) {
        Live L = lives.get(id);
        if (L == null) return "{\"ok\":false,\"error\":{\"message\":\"unknown live session\"}}";
        L.stopReason = "api-stop";
        try { L.ch.disconnect(); } catch (Throwable ignore) { }
        try { L.s.disconnect(); } catch (Throwable ignore) { }
        L.closed = true;
        return "{\"ok\":true}";
    }

    /** SSE：首帧 backlog+meta，随后 sample 事件，结束时 exit 事件。 */
    public boolean liveStream(Socket sock, String id) throws Exception {
        final Live L = lives.get(id);
        if (L == null) return false;
        OutputStream o = sock.getOutputStream();
        o.write(("HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\n"
                + "Cache-Control: no-cache, no-store\r\nConnection: keep-alive\r\n\r\n").getBytes("UTF-8"));
        String head;
        synchronized (L) {
            StringBuilder b = new StringBuilder("{\"backlog\":[");
            for (int i = 0; i < L.samples.size(); i++) { if (i > 0) b.append(','); b.append(L.samples.get(i)); }
            b.append("],\"meta\":").append(L.meta.length() > 1 ? L.meta : "{}").append('}');
            head = b.toString();
            L.subs.add(sock);
        }
        writeEvent(o, "head", head);
        int idle = 0;
        while (!L.closed) {
            Thread.sleep(200);
            if (++idle % 75 == 0) { try { o.write(": ping\n\n".getBytes("UTF-8")); o.flush(); } catch (Throwable ignore) { break; } }
        }
        try { writeEvent(o, "exit", "{\"reason\":\"" + L.stopReason + "\"}"); } catch (Throwable ignore) { }
        synchronized (L) { L.subs.remove(sock); }
        try { o.flush(); sock.close(); } catch (Throwable ignore) { }
        return true;
    }

    static void writeEvent(OutputStream o, String evt, String dataJson) throws Exception {
        o.write(("event: " + evt + "\ndata: " + dataJson + "\n\n").getBytes("UTF-8"));
        o.flush();
    }

    /** 2026-09-22 用户要求：接入路线数据（qlog）——复用连接器的 scan_routes.py
     *  真读 qlog（10Hz，比 rlog 小 15 倍）：分类每段（驻车/手动/已接管/干预混合）+ 汇总每 route */
    public String routesScanJson(String root, int limit, boolean segments) {
        String r = (root == null || root.length() == 0) ? "/data/media/0/realdata" : root;
        String args = "--root " + shq(r) + (limit != 0 ? (" --limit " + limit) : "") + (segments ? " --segments" : "");   // R77：负数=最近 N 天 ✓
        String out = runRemote("scan_routes.py", "dsh-scan-routes.py", args, null);
        // 脚本可能先打日志/进度，JSON 在最后一行 → 取出来 ✓
        try {
            String[] L = out.split("\n");
            for (int i = L.length - 1; i >= 0; i--) {
                String t = L[i].trim();
                if (t.startsWith("{") && t.endsWith("}")) return t;
            }
        } catch (Throwable ignore) { }
        return out;
    }

    /* 2026-09-22 用户要求：AI 分析要进度条 / 预计时间要准 / 分析中能切页面
       → 扫描改为**后台跑**（nohup 脱离会话），页面轮询进度与结果 ✓ */
    private static final String SCAN_PROG = REMOTE_DIR + "/scan-progress.json";
    private static final String SCAN_RES  = REMOTE_DIR + "/scan-result.json";

    public String routesScanStart(String root, int limit) {
        Session s = null;
        try {
            s = session();
            String path = ensureRemote(s, "scan_routes.py", "dsh-scan-routes.py");
            if (path == null) return "{\"ok\":false,\"error\":{\"message\":\"上传扫描脚本失败\"}}";
            String r = (root == null || root.length() == 0) ? "/data/media/0/realdata" : root;
            // 2026-09-24 R77：负数 = 最近 N 天（脚本支持）—— 原来只传 >0，导致"最近 1/3 天"选了没用 ✗
            // 2026-09-24 R82：**不能删 progress** —— 脚本要靠它读出上一轮的 pid 把重复进程杀掉 ✓
            //   两个扫描同时写同一个进度文件 = 进度条前后跳 ✗；只删旧结果 ✓
            String cmd = "rm -f " + SCAN_RES + "; "
                    + "nohup python3 " + path + " --root " + shq(r) + (limit != 0 ? (" --limit " + limit) : "")
                    + " --progress " + SCAN_PROG + " --out " + SCAN_RES
                    + " > " + REMOTE_DIR + "/scan.log 2>&1 & echo started";
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd);
            InputStream in = ch.getInputStream();
            ch.connect(8000);
            byte[] b = new byte[512];
            while (in.read(b) > 0) { }
            ch.disconnect();
            return "{\"ok\":true,\"progress\":{\"pct\":0,\"scanned\":0}}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t)) + "\"}}";
        }
    }


    /** 2026-09-24：各镜像的 python 不一样，且**不能只用 readlink -f /proc/<pid>/exe**：
     *  它会把 venv 的符号链接解析成系统 python（没有 numpy/capnp）✗ —— 投屏服务会直接起不来
     *  （实测报 ModuleNotFoundError: numpy）。所以：优先挑一个**真能 import numpy** 的解释器 ✓ */
    private static final String CASTPY =
            "PY=$(for p in $(pgrep -f manager.py | head -3); do tr '\\0' '\\n' < /proc/$p/cmdline | head -1; done | grep python | head -1); "
          + "if [ ! -x \"$PY\" ] || ! \"$PY\" -c 'import numpy' 2>/dev/null; then PY=/usr/local/venv/bin/python3; fi; "
          + "if [ ! -x \"$PY\" ] || ! \"$PY\" -c 'import numpy' 2>/dev/null; then PY=$(ls /usr/local/pyenv/versions/*/bin/python3 2>/dev/null | tail -1); fi; "
          + "if [ ! -x \"$PY\" ]; then PY=python3; fi; ";
    /** 一键装/卸投屏钩子（2026-09-24）：源码由 APP 推过去，设备侧 cast_provision.py 完成
     *  「编译 → 备份+注入 process_config.py → 重启 manager → 验证出帧」。
     *  这样换系统/换设备都不用懂这些，用户在投屏页点一下即可 ✓ */
    public String castProvision(String action) {
        try {
            Session s = session();
            ensureRemote(s, "uihook.c", "uihook.c");
            ensureRemote(s, "touchd.c", "touchd.c");
            ensureRemote(s, "mjpeg.py", "mjpeg.py");
        } catch (Throwable ignore) { }
        String a = (action == null || action.length() == 0) ? "install" : action;
        return runRemote("cast_provision.py", "cast_provision.py", a, null);
    }

    /** v1.7 #1：投屏 MJPEG 服务的 启动/停止/状态（照 routesScanStart 的存活模式 ✓）
     *  注意：pkill 用 [m]jpeg 写法，避免匹配到本命令自身的 cmdline（自杀 ✗）*/
    public String castJson(String action) {
        Session s = null;
        try {
            s = session();
            String py  = "/data/openpilot/.dsh/mjpeg.py";
            String log = "/data/openpilot/.dsh/mjpeg.log";
            String pidf = "/data/openpilot/.dsh/mjpeg.pid";
            String cmd;
            if ("stop".equals(action)) {
                // 用 PID 文件停止：命令行里只有数字，绝不会匹配到自己 ✓
                cmd = "rm -f /dev/shm/ui.cast.on; kill $(cat " + pidf + " 2>/dev/null) 2>/dev/null; rm -f " + pidf + "; echo stopped";
            } else if ("status".equals(action)) {
                cmd = "P=$(cat " + pidf + " 2>/dev/null); if [ -n \"$P\" ] && kill -0 $P 2>/dev/null; then echo running:$P; elif curl -s --max-time 2 http://127.0.0.1:8090/stat >/dev/null 2>&1; then echo running:port; else echo notrunning; fi"
                    + "; echo @; curl -s --max-time 3 http://127.0.0.1:8090/stat 2>/dev/null; echo @; tail -2 " + log + " 2>/dev/null";
            } else {
                // 2026-09-24：**只在 start 时**推 mjpeg.py —— 页面每隔几秒轮询 status，
                // 放在方法开头会「把刚在设备上改好的脚本覆盖回旧版」（实测踩过 ✗）
                try { ensureRemote(s, "mjpeg.py", "mjpeg.py"); } catch (Throwable ignore) { }
                // 与 routesScanStart 完全同构：rm; nohup <prog> … > log 2>&1 & echo started（+ 记 PID ✓）
                // 2026-09-24：先杀旧的再起。**不能用 pkill -f \"mjpeg.py\"** —— 本条命令自己的 cmdline 里也有 mjpeg.py，
                // pkill 会把这个 shell 一起杀掉 → 后面的 nohup 还没执行就被 Terminated（实测踩过 ✗）
                // 改法：① 按 PID 文件杀 ② 兜底 pgrep 逐个杀但**跳过自己 $$**（模式写成 mjpeg[.]py，它不匹配自身字面量）
                //       ③ 再等端口真的空出来（最多 4s）才起，避免 Address already in use
                String killOld = "P=$(cat " + pidf + " 2>/dev/null); [ -n \"$P\" ] && kill $P 2>/dev/null; "
                  + "for p in $(pgrep -f 'mjpeg[.]py' 2>/dev/null); do [ \"$p\" = \"$$\" ] && continue; kill $p 2>/dev/null; done; "
                  + "sleep 1; for i in 1 2 3 4 5 6 7 8; do curl -s -m 1 -o /dev/null http://127.0.0.1:8090/stat || break; sleep 0.5; done; "
                  + "rm -f " + pidf + "; ";
                cmd = CASTPY + "touch /dev/shm/ui.cast.on; " + killOld + "TP=$(cat /data/openpilot/.dsh/touchd.pid 2>/dev/null); if [ -z \"$TP\" ] || ! kill -0 $TP 2>/dev/null; then nohup /data/openpilot/.dsh/touchd 8091 > /data/openpilot/.dsh/touchd.log 2>&1 & echo $! > /data/openpilot/.dsh/touchd.pid; fi; echo \"$PY\" > /data/openpilot/.dsh/mjpeg.pypath 2>/dev/null; nohup $PY " + py + " 8090 15 1024 58 ui > " + log + " 2>&1 & echo $! > " + pidf + "; echo started";
            }
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd);
            InputStream in = ch.getInputStream();
            ch.connect(8000);
            byte[] b = new byte[512];
            int n;
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            while ((n = in.read(b)) > 0) bo.write(b, 0, n);
            ch.disconnect();
            String out = bo.toString("UTF-8").trim();
            return "{\"ok\":true,\"action\":\"" + esc(action) + "\",\"out\":\"" + esc(out) + "\"}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t)) + "\"}}";
        }
    }

    public String routesScanStatus() {
        Session s = null;
        try {
            s = session();
            String cmd = "echo @P; cat " + SCAN_PROG + " 2>/dev/null; echo; echo @R; head -c 500000 " + SCAN_RES + " 2>/dev/null; echo; echo @E";
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd);
            InputStream in = ch.getInputStream();
            ch.connect(8000);
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[16384]; int n;
            while ((n = in.read(b)) > 0) bo.write(b, 0, n);
            ch.disconnect();
            String out = bo.toString("UTF-8");
            String prog = between(out, "@P", "@R").trim();
            String res  = between(out, "@R", "@E").trim();
            String pj = (prog.startsWith("{") ? prog : "null");
            String rj = "null";
            try {
                String[] L = res.split("\n");
                for (int i = L.length - 1; i >= 0; i--) { String t = L[i].trim();
                    if (t.startsWith("{") && t.endsWith("}")) { rj = t; break; } }
            } catch (Throwable ignore) { }
            return "{\"ok\":true,\"progress\":" + pj + ",\"result\":" + rj + "}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t)) + "\"}}";
        }
    }

    private static String between(String s, String a, String b) {
        try {
            int i = s.indexOf(a); if (i < 0) return "";
            i += a.length();
            int j = s.indexOf(b, i); if (j < 0) j = s.length();
            return s.substring(i, j);
        } catch (Throwable t) { return ""; }
    }

    public String routesJson(String root) {
        return runRemote("dsh_remote.py", "dsh_remote.py", "routes " + shq(root == null || root.length() == 0 ? "/data/media/0/realdata" : root), null);
    }

    // ── 辅助驾驶状态（第⑤轮）：长连接监听 selfdriveState/deviceState，
    //    变化时更新状态并投一条本地语音 ──
    public final Voice voice = new Voice();
    public Cues cues() { return new Cues(ctx); }
    private volatile boolean driveWanted = false;
    private volatile boolean driveRunning = false;
    private volatile Boolean lastEn = null;      // null = 还没观测到
    private volatile Boolean lastStarted = null;
    private volatile long lastEventAt = 0;
    private volatile int driveRestarts = 0;
    private volatile String driveError = null;
    private volatile long driveSince = 0;
    private java.util.concurrent.atomic.AtomicInteger driveGen = new java.util.concurrent.atomic.AtomicInteger(0);

    public String driveStatusJson() {
        return "{\"ok\":true,\"enabled\":" + driveWanted + ",\"running\":" + driveRunning
                + ",\"hostId\":\"c3\",\"lastEn\":" + (lastEn == null ? "null" : (lastEn.booleanValue() ? "1" : "0"))
                + ",\"lastStarted\":" + (lastStarted == null ? "null" : (lastStarted.booleanValue() ? "1" : "0"))
                + ",\"lastEventAt\":" + (lastEventAt == 0 ? "null" : lastEventAt)
                + ",\"restarts\":" + driveRestarts
                + ",\"lastError\":" + (driveError == null ? "null" : ("\"" + esc(driveError) + "\""))
                + ",\"since\":" + (driveSince == 0 ? "null" : driveSince) + "}";
    }

    /** 保证监听在跑（页面一查状态就自动开，免手动开关）。 */
    public void ensureDriveWatch() {
        if (!driveWanted) { driveWanted = true; startDriveThread(driveGen.incrementAndGet()); }
    }

    public String driveWatch(boolean on) {
        if (!on) { driveWanted = false; driveRunning = false; driveGen.incrementAndGet(); return driveStatusJson(); }
        driveWanted = true;
        startDriveThread(driveGen.incrementAndGet());
        return driveStatusJson();
    }

    private void startDriveThread(final int gen) {
        Thread t = new Thread(new Runnable() { public void run() {
            while (driveWanted && gen == driveGen.get()) {
                Session s = null;
                try {
                    s = session();
                    String script = ensureRemote(s, "drive_watch.py", "drive_watch.py");
                    if (script == null) throw new Exception("上传 drive_watch.py 失败");
                    ChannelExec ch = (ChannelExec) s.openChannel("exec");
                    ch.setCommand("P=$(cat /dev/shm/dsh-drivewatch.pid 2>/dev/null); [ -n \"$P\" ] && kill -9 $P 2>/dev/null; sleep 1; "
                            + "sh -c 'echo $$ > /dev/shm/dsh-drivewatch.pid; exec python3 -u " + script + " 2>&1'");
                    final InputStream in = ch.getInputStream();
                    ch.connect(8000);
                    driveRunning = true; driveSince = System.currentTimeMillis(); driveError = null;
                    connCue(true);
                    java.io.BufferedReader r = new java.io.BufferedReader(new java.io.InputStreamReader(in, "UTF-8"));
                    String line;
                    while ((line = r.readLine()) != null) {
                        if (!driveWanted || gen != driveGen.get()) break;
                        line = line.trim();
                        if (line.length() == 0 || line.charAt(0) != '{') continue;
                        handleDriveLine(line);
                    }
                } catch (Throwable e) {
                    driveError = String.valueOf(e.getMessage());
                    connCue(false);
                } finally {
                    driveRunning = false;
            // KEEP_REUSE2：共用会话不断开（坏了由 reused() 的 isConnected 自愈 ✓）
                }
                if (driveWanted && gen == driveGen.get()) {
                    driveRestarts++;
                    // 设备离线时别 3 秒一次空转：负缓存命中就退到 10 秒 ✓
                    boolean off = failHost != null;
                    try { Thread.sleep(off ? 10000 : 3000); } catch (Throwable ignore) { }
                }
            }
        } });
        t.setDaemon(true);
        t.start();
    }

    private volatile Boolean lastConnState = null;
    private volatile long lastConnCueAt = 0;

    /** 连接状态跳变时投语音（2026-09-21 用户反馈：连上/断开都没提示）。
     *  只在"状态变化"时播，且 5 秒节流，避免断线重连时反复播报。 */
    private void connCue(boolean ok) {
        long now = System.currentTimeMillis();
        if (lastConnState != null && lastConnState.booleanValue() == ok) return;
        if (now - lastConnCueAt < 5000) return;
        lastConnState = Boolean.valueOf(ok);
        lastConnCueAt = now;
        try {
            Cues c = cues();
            String text = c.get(ok ? "connected" : "disconnected");
            voice.say(text, ok ? "conn-up" : "conn-down");
            Logs.add("VOICE", "入队语音：\"" + text + "\"");   // 打印真实文案（此前写死了旧句子）
        } catch (Throwable e) {
            Logs.add("VOICE", "入队失败: " + e);
        }
    }

    /** 收到一行 drive_watch 的输出：更新状态，并在"变化"时投语音。 */
    private void handleDriveLine(String line) {
        Boolean en = boolField(line, "en");
        Boolean started = boolField(line, "started");
        lastEventAt = System.currentTimeMillis();
        if (en != null) {
            if (lastEn != null && lastEn.booleanValue() != en.booleanValue()) {
                Cues c = cues();
                voice.say(en.booleanValue() ? c.get("driveOn") : c.get("driveOff"), "drive-change");
            }
            lastEn = en;
        }
        if (started != null) lastStarted = started;
    }

    private static Boolean boolField(String json, String key) {
        int i = json.indexOf("\"" + key + "\"");
        if (i < 0) return null;
        int c = json.indexOf(':', i);
        if (c < 0) return null;
        String rest = json.substring(c + 1).trim();
        if (rest.startsWith("true")) return Boolean.TRUE;
        if (rest.startsWith("false")) return Boolean.FALSE;
        if (rest.startsWith("1")) return Boolean.TRUE;
        if (rest.startsWith("0")) return Boolean.FALSE;
        return null;
    }

    /** 把本机更新包推到设备并执行（cd <dir> && sh <file>）。 */
    public String runPkg(String name, String remoteDir, String extraArgs) {
        Session s = null;
        try {
            byte[] data = new Pkg(ctx).read(name);
            if (data == null) return "{\"ok\":false,\"error\":{\"message\":\"本机没有这个更新包\"}}";
            s = session();
            String dir = (remoteDir == null || remoteDir.length() == 0) ? "/data/openpilot" : remoteDir;
            String remote = "/tmp/" + Pkg.safe(name);
            com.jcraft.jsch.ChannelSftp sftp = (com.jcraft.jsch.ChannelSftp) s.openChannel("sftp");
            sftp.connect(8000);
            sftp.put(new java.io.ByteArrayInputStream(data), remote);
            sftp.disconnect();
            String cmd = "cd " + shq(dir) + " && sh " + remote + (extraArgs == null || extraArgs.length() == 0 ? "" : (" " + extraArgs));
            ChannelExec ch = (ChannelExec) s.openChannel("exec");
            ch.setCommand(cmd + " 2>&1");
            InputStream in = ch.getInputStream();
            ch.connect(8000);
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[16384];
            int n;
            while ((n = in.read(b)) > 0) bo.write(b, 0, n);
            for (int w = 0; w < 40 && !ch.isClosed(); w++) { try { Thread.sleep(100); } catch (Throwable ignore) { } }
            int code = ch.getExitStatus();
            ch.disconnect();
            String out = bo.toString("UTF-8");
            return "{\"ok\":true,\"code\":" + code + ",\"cmd\":\"" + esc(cmd) + "\",\"output\":\"" + esc(out.length() > 4000 ? out.substring(out.length() - 4000) : out) + "\"}";
        } catch (Throwable e) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(Errs.zh(String.valueOf(e.getMessage()))) + "\"}}";
        } finally {
            // KEEP_REUSE2：共用会话不断开（坏了由 reused() 的 isConnected 自愈 ✓）
        }
    }

    public static String esc(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c == '\n') b.append("\\n");
            else if (c == '\r') b.append("\\r");
            else if (c == '\t') b.append("\\t");
            else if (c < 0x20) b.append(' ');
            else b.append(c);
        }
        return b.toString();
    }
}
