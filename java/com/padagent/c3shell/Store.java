package com.padagent.c3shell;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * APP 内置存储（方案 C）：主机配置 + 命名密钥 全部存在手机本地，
 * 不依赖平板上的连接器。
 *   - 主机：SharedPreferences "hosts"（每行一台，制表符分隔，简单可解析）
 *   - 密钥内容：getExternalFilesDir()/named-keys/<名字>（600 语义由沙盒保证）
 *   - 密钥中文名/备注：SharedPreferences "keymeta"
 */
public class Store {
    private final Context ctx;

    public Store(Context c) { ctx = c; }

    private SharedPreferences p() { return ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE); }

    // ── 主机 ─────────────────────────────────────────────────────────────
    public static class Host {
        public String id = "", label = "", host = "", user = "comma", key = "", note = "", mode = "ssh";
        public int port = 22;
        String line() { return id + "\t" + label + "\t" + host + "\t" + port + "\t" + user + "\t" + key + "\t" + note + "\t" + mode; }
        static Host parse(String l) {
            String[] f = l.split("\t", -1);
            Host h = new Host();
            if (f.length > 0) h.id = f[0];
            if (f.length > 1) h.label = f[1];
            if (f.length > 2) h.host = f[2];
            if (f.length > 3) { try { h.port = Integer.parseInt(f[3]); } catch (Throwable ignore) { } }
            if (f.length > 4) h.user = f[4];
            if (f.length > 5) h.key = f[5];
            if (f.length > 6) h.note = f[6];
            if (f.length > 7) h.mode = f[7];
            return h;
        }
    }

    public List<Host> hosts() {
        List<Host> out = new ArrayList<Host>();
        String all = p().getString("hosts", "");
        if (all.length() == 0) {
            // 首次运行给一台默认（可在界面改）
            Host h = new Host();
            h.id = "c3"; h.label = "C3 设备"; h.host = p().getString("host", "192.168.31.49");
            h.port = p().getInt("port", 22); h.user = p().getString("user", "comma");
            h.key = ""; h.mode = "ssh";
            out.add(h);
            return out;
        }
        for (String l : all.split("\n")) if (l.trim().length() > 0) out.add(Host.parse(l));
        return out;
    }

    private void saveHosts(List<Host> hs) {
        StringBuilder b = new StringBuilder();
        for (Host h : hs) b.append(h.line()).append('\n');
        // 2026-09-22 修（用户报"主机不能保存/新增"的真因）：apply() 是**异步落盘**，
        // 而 MIUI 很快杀进程 → 刚存的主机还没写盘就丢了 ✗。改成分步 commit()：写完即落盘 ✓
        p().edit().putString("hosts", b.toString()).commit();
    }

    public Host hostById(String id) {
        List<Host> hs = hosts();
        if (id == null || id.length() == 0) return defaultHost();
        for (Host h : hs) if (h.id.equals(id)) return h;
        return hs.isEmpty() ? null : hs.get(0);
    }

    public Host defaultHost() {
        List<Host> hs = hosts();
        String d = p().getString("defaultHostId", "");
        for (Host h : hs) if (h.id.equals(d)) return h;
        return hs.isEmpty() ? null : hs.get(0);
    }

    public void upsertHost(Host h) {
        List<Host> hs = hosts();
        boolean found = false;
        for (int i = 0; i < hs.size(); i++) if (hs.get(i).id.equals(h.id)) { hs.set(i, h); found = true; }
        if (!found) hs.add(h);
        saveHosts(hs);
        if (p().getString("defaultHostId", "").length() == 0) p().edit().putString("defaultHostId", h.id).commit();
    }

    public void deleteHost(String id) {
        List<Host> hs = hosts();
        for (int i = hs.size() - 1; i >= 0; i--) if (hs.get(i).id.equals(id)) hs.remove(i);
        saveHosts(hs);
    }

    public void setDefault(String id) { p().edit().putString("defaultHostId", id).commit(); }

    public String hostsJson() {
        List<Host> hs = hosts();
        String def = p().getString("defaultHostId", hs.isEmpty() ? null : hs.get(0).id);
        StringBuilder b = new StringBuilder("{\"ok\":true,\"embedded\":true,\"defaultHostId\":\"" + Ssh.esc(def) + "\",\"hosts\":[");
        for (int i = 0; i < hs.size(); i++) {
            Host h = hs.get(i);
            if (i > 0) b.append(',');
            b.append("{\"id\":\"").append(Ssh.esc(h.id)).append("\",\"label\":\"").append(Ssh.esc(h.label))
             .append("\",\"host\":\"").append(Ssh.esc(h.host)).append("\",\"port\":").append(h.port)
             .append(",\"user\":\"").append(Ssh.esc(h.user)).append("\",\"keyPath\":\"").append(Ssh.esc(h.key))
             .append("\",\"note\":\"").append(Ssh.esc(h.note)).append("\",\"mode\":\"").append(Ssh.esc(h.mode))
             .append("\",\"target\":\"").append(Ssh.esc(h.user + "@" + h.host + ":" + h.port)).append("\"}");
        }
        return b.append("]}").toString();
    }

    // ── 命名密钥 ─────────────────────────────────────────────────────────
    /** 密钥位目录：用**内部**私有目录（不依赖外部存储权限，重装升级都稳） */
    public File keysDir() {
        File dir = new File(ctx.getFilesDir(), "named-keys");
        if (!dir.exists()) dir.mkdirs();
        return dir;
    }

    /** 内置密钥位（随 APK 打包，首次运行自动铺开） */
    /* 2026-09-22 用户要求：把提供的全部密钥内置 ✓
       （其中 5 个是站点上的 PuTTY PPK，已用 tools/ppk2openssh 转成 OpenSSH，逐个指纹自检通过 ✓） */
    public static final String[] PRESET_KEYS = { "神牛", "雨落倾城",
            "斌哥密钥", "斌哥密钥2", "救援密钥", "门总新密钥", "门老板老密钥" };
    /* 2026-09-22：删掉重复的「老门新密钥」——实测它与站上「门总新密钥」**公钥完全相同**（同一把钥匙 ✓）；
       且没有任何主机的 key 指向它 ✓（两个主机都用"命名密钥"选择）。此处只清理这个历史遗留文件 ✓ */

    /** 资源名用 ASCII（aapt2 对中文资源名不可靠） */
    /** 2026-09-22：内置密钥的显示名与备注（用户反馈"老门新密钥重复了"——其实不是同一把，
     *  但名字太像 → 这里给每把配上说明，并标注本机旧档 ✓） */
    private static final String[][] PRESET_INFO = {
        { "神牛",        "神牛密钥",       "基础密钥之一 ✓" },
        { "雨落倾城",     "雨落倾城密钥",    "设备端密钥是 yuluoqingcheng 时选它 ✓" },
        { "斌哥密钥",     "斌哥密钥",       "设备用的斌哥密钥（ed25519；旧版 JSch 可能不支持 ✗）" },
        { "斌哥密钥2",    "斌哥密钥2",      "斌哥密钥2 ✓" },
        { "救援密钥",     "救援密钥",       "无法添加 SSH 用户名时用（不建议长期 ✓）" },
        { "门总新密钥",   "门总新密钥",      "设备端是 menwenliang 时选它 ✓" },
        { "门老板老密钥",  "门老板老密钥",    "设备端是 sadmenmenmen 时选它 ✓" }
    };

    private static String ASSET_OF(String name) {
        if ("神牛".equals(name)) return "k1";
        if ("雨落倾城".equals(name)) return "k2";
        if ("斌哥密钥".equals(name)) return "k4";
        if ("斌哥密钥2".equals(name)) return "k5";
        if ("救援密钥".equals(name)) return "k6";
        if ("门总新密钥".equals(name)) return "k7";
        if ("门老板老密钥".equals(name)) return "k8";
        return "k1";
    }

    public void ensurePresetKeys() {
        try {   // 2026-09-22 一次性清理：删掉与「门总新密钥」重复的历史遗留文件（实测同一把 ✓，无主机引用 ✓）
            java.io.File dup = new java.io.File(keysDir(), "老门新密钥");
            if (dup.exists()) dup.delete();
        } catch (Throwable ignore) { }
        for (String[] info : PRESET_INFO) {                  // 备注只填"空着的" ✓ 不覆盖用户自己写的 ✓
            try {
                if (keyMeta(info[0]).length() > 0) continue;
                p().edit().putString("keymeta_" + safe(info[0]), info[1] + "\u0001" + info[2]).commit();
            } catch (Throwable ignore) { }
        }
        File dir = keysDir();
        for (String name : PRESET_KEYS) {
            File f = new File(dir, name);
            if (f.exists() && f.length() > 0) continue;
            try {
                java.io.InputStream is = Sec.open(ctx, "keys/" + ASSET_OF(name));
                java.io.FileOutputStream o = new java.io.FileOutputStream(f);
                byte[] b = new byte[8192];
                int n;
                while ((n = is.read(b)) > 0) o.write(b, 0, n);
                is.close(); o.close();
            } catch (Throwable ignore) { }
        }
    }

    public File keyFile(String name) { return new File(keysDir(), safe(name)); }

    public static String safe(String n) {
        if (n == null) return "unnamed";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n.length() && b.length() < 64; i++) {
            char c = n.charAt(i);
            if (c == '/' || c == '\\' || c == ':' || c < 0x20) b.append('_'); else b.append(c);
        }
        return b.length() == 0 ? "unnamed" : b.toString();
    }

    public String keyMeta(String name) { return p().getString("keymeta_" + safe(name), ""); }

    public void setKeyMeta(String name, String display, String note) {
        p().edit().putString("keymeta_" + safe(name), display + "\u0001" + note).apply();
    }

    public String keysJson() {
        ensurePresetKeys();
        java.util.List<String> names = new java.util.ArrayList<String>();
        java.util.List<File> fs = new java.util.ArrayList<File>();
        for (String n : PRESET_KEYS) { File f = new File(keysDir(), n); fs.add(f); names.add(n); }
        File[] others = keysDir().listFiles();
        if (others != null) {
            java.util.Arrays.sort(others);
            for (File f : others) {
                if (f == null || !f.isFile() || f.getName().startsWith(".")) continue;
                if (java.util.Arrays.asList(PRESET_KEYS).contains(f.getName())) continue;
                fs.add(f); names.add(f.getName());
            }
        }
        StringBuilder b = new StringBuilder("{\"ok\":true,\"keys\":[");
        boolean first = true;
        if (fs != null) {
            // 保持「神牛/雨落倾城/老门新密钥」在前，不重新排序
            for (File f : fs) {
                if (f.isDirectory() || f.getName().startsWith(".")) continue;
                if (!first) b.append(',');
                first = false;
                String meta = keyMeta(f.getName());
                String disp = f.getName(), note = "";
                if (meta.length() > 0) { int i = meta.indexOf('\u0001'); disp = i > 0 ? meta.substring(0, i) : meta; note = i > 0 ? meta.substring(i + 1) : ""; }
                b.append("{\"key\":\"").append(Ssh.esc(f.getName())).append("\",\"name\":\"").append(Ssh.esc(disp))
                 .append("\",\"note\":\"").append(Ssh.esc(note)).append("\",\"path\":\"").append(Ssh.esc(f.getAbsolutePath()))
                 .append("\",\"size\":").append(f.length()).append("}");
            }
        }
        return b.append("]}").toString();
    }

    public boolean saveKey(String name, String content) {
        try {
            File f = keyFile(name);
            FileOutputStream o = new FileOutputStream(f);
            o.write(content.getBytes("UTF-8"));
            o.close();
            return true;
        } catch (Throwable e) { return false; }
    }

    public void deleteKey(String name) { try { keyFile(name).delete(); } catch (Throwable ignore) { } }
}
