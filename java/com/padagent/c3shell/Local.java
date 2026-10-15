package com.padagent.c3shell;

import android.content.Context;
import java.io.File;

/**
 * 本机（手机 / 平板）文件操作 —— 2026-09-27 v3.00.71
 *
 * 用户要求：控制台「文件」页要有**复制 / 移动**功能，并且**可以选本机储存**。
 * 设计取舍（都是踩过的坑）：
 *  · 只用 java.io.File —— 编译桩 android.jar 里 DocumentsContract 那套没有 ✗（项目里已有的 SAF 代码全靠反射）
 *  · 候选根：/storage/emulated/0（全盘，需「所有文件访问」）· Download · APP 外部目录（永远可写 ✓）
 *  · 读不到的目录**不抛异常**，返回 ok:false + 人话提示（并引导去授权）✓
 */
public class Local {
    private final Context ctx;
    public Local(Context c) { ctx = c; }

    public static String appDir(Context c) {
        try { File d = c.getExternalFilesDir(null); if (d != null) return d.getAbsolutePath(); } catch (Throwable ignore) { }
        try { return c.getFilesDir().getAbsolutePath(); } catch (Throwable ignore) { }
        return "/data/local/tmp";
    }

    public static String defRoot(Context c) {
        try {
            File d = new File("/storage/emulated/0/Download");
            if (d.isDirectory() && d.canRead() && d.canWrite()) return d.getAbsolutePath();
            File s = new File("/storage/emulated/0");
            if (s.isDirectory() && s.canRead()) return s.getAbsolutePath();
        } catch (Throwable ignore) { }
        return appDir(c);
    }

    private static String err(String m) {
        return "{\"ok\":false,\"error\":{\"message\":\"" + Ssh.esc(m) + "\"}}";
    }

    /** 候选根目录 + 能不能读写（页面用它给「本机储存」快捷入口 ✓） */
    public String rootsJson() {
        String[] cands = { "/storage/emulated/0", "/storage/emulated/0/Download", "/storage/emulated/0/Documents", appDir(ctx), "/sdcard" };
        StringBuilder b = new StringBuilder();
        for (String p : cands) {
            File f = new File(p);
            boolean isDir = false, r = false, w = false;
            try { isDir = f.isDirectory(); r = f.canRead(); w = f.canWrite(); } catch (Throwable ignore) { }
            if (!isDir) continue;
            if (b.length() > 0) b.append(',');
            b.append("{\"path\":\"").append(Ssh.esc(p)).append("\",\"readable\":").append(r).append(",\"writable\":").append(w).append('}');
        }
        return "{\"ok\":true,\"def\":\"" + Ssh.esc(defRoot(ctx)) + "\",\"app\":\"" + Ssh.esc(appDir(ctx)) + "\",\"roots\":[" + b + "]}";
    }

    public String listJson(String path) {
        if (path == null || path.length() == 0) path = defRoot(ctx);
        File d = new File(path);
        if (!d.exists()) return err("目录不存在：" + path);
        if (!d.isDirectory()) return err("不是目录：" + path);
        File[] fs = null;
        try { fs = d.listFiles(); } catch (Throwable ignore) { }
        if (fs == null) return err("读不到这个目录（没有存储权限？点「授权本机存储」）");
        StringBuilder b = new StringBuilder();
        int n = 0;
        for (File f : fs) {
            boolean dir = false, link = false, r = false;
            long size = 0, mt = 0;
            try { dir = f.isDirectory(); link = isLink(f); r = f.canRead(); size = f.length(); mt = f.lastModified(); } catch (Throwable ignore) { }
            if (!dir && !r) continue;
            if (b.length() > 0) b.append(',');
            b.append("{\"name\":\"").append(Ssh.esc(f.getName())).append("\",\"dir\":").append(dir)
             .append(",\"link\":").append(link).append(",\"size\":").append(size).append(",\"mtime\":").append(mt).append('}');
            n++;
            if (n > 4000) break;
        }
        return "{\"ok\":true,\"path\":\"" + Ssh.esc(d.getAbsolutePath()) + "\",\"entries\":[" + b + "]}";
    }

    private static boolean isLink(File f) {
        try {
            Class<?> c = Class.forName("android.system.Os");
            Object st = c.getMethod("lstat", String.class).invoke(null, f.getAbsolutePath());
            Object mode = st.getClass().getField("st_mode").get(st);
            return (((Number) mode).intValue() & 0170000) == 0120000;   // S_IFLNK
        } catch (Throwable ignore) { }
        try { return !f.getCanonicalPath().equals(f.getAbsolutePath()); } catch (Throwable ignore) { }
        return false;
    }

    /** op: mkdir | rename | remove | copy | move */
    public String opJson(String op, String path, String to) {
        if (path == null || path.length() == 0) return err("路径为空");
        if (op == null) return err("缺少 op");
        File src = new File(path);
        if (!src.exists()) return err("不存在：" + path);
        try {
            if ("mkdir".equals(op)) {
                if (src.exists()) return "{\"ok\":true}";
                return src.mkdirs() ? "{\"ok\":true}" : err("新建失败（没有写权限？）");
            }
            if ("remove".equals(op)) return rm(src) ? "{\"ok\":true}" : err("删除失败");
            if (to == null || to.length() == 0) return err("目标路径为空");
            File dst = new File(to);
            if ("rename".equals(op)) return src.renameTo(dst) ? "{\"ok\":true}" : err("改名失败");
            if ("copy".equals(op)) return cp(src, dst) ? "{\"ok\":true}" : err("复制失败");
            if ("move".equals(op)) {
                if (src.renameTo(dst)) return "{\"ok\":true}";
                if (cp(src, dst)) { if (!rm(src)) return err("已复制但源删除失败"); return "{\"ok\":true}"; }
                return err("移动失败");
            }
            return err("不支持的操作：" + op);
        } catch (Throwable e) {
            return err("操作失败：" + e.getMessage());
        }
    }

    private static boolean rm(File f) {
        try {
            if (f.isDirectory()) {
                File[] kids = f.listFiles();
                if (kids != null) for (File k : kids) if (!rm(k)) return false;
            }
            return f.delete();
        } catch (Throwable ignore) { return false; }
    }

    private static boolean cp(File src, File dst) {
        try {
            if (src.isDirectory()) {
                if (!dst.exists() && !dst.mkdirs()) return false;
                File[] kids = src.listFiles();
                if (kids != null) for (File k : kids) if (!cp(k, new File(dst, k.getName()))) return false;
                return true;
            }
            File par = dst.getParentFile();
            if (par != null && !par.exists() && !par.mkdirs()) return false;
            java.io.InputStream is = new java.io.FileInputStream(src);
            java.io.OutputStream os = new java.io.FileOutputStream(dst);
            byte[] buf = new byte[65536];
            int n;
            while ((n = is.read(buf)) > 0) os.write(buf, 0, n);
            try { is.close(); } catch (Throwable ignore) { }
            try { os.flush(); os.close(); } catch (Throwable ignore) { }
            return true;
        } catch (Throwable ignore) { return false; }
    }
}

