package com.padagent.c3shell;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

/** sh 更新包库（2026-09-21 用户要求：更新包保存/使用）。
 *  包体存在 APP 本机目录 packages/，名字+备注存 prefs；运行时用 SFTP 推到 C3 设备再执行。 */
public class Pkg {
    private final Context ctx;

    public Pkg(Context c) { ctx = c; }

    private SharedPreferences p() { return ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE); }
    private File dir() { File d = new File(ctx.getFilesDir(), "packages"); if (!d.exists()) d.mkdirs(); return d; }

    public static String safe(String n) {
        if (n == null) return "unnamed";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n.length() && b.length() < 48; i++) {
            char c = n.charAt(i);
            if (c == '/' || c == '\\' || c == ':' || c < 0x20) b.append('_'); else b.append(c);
        }
        return b.length() == 0 ? "unnamed" : b.toString();
    }

    public String json() {
        File[] fs = dir().listFiles();
        StringBuilder b = new StringBuilder("{\"ok\":true,\"packages\":[");
        boolean first = true;
        if (fs != null) {
            java.util.Arrays.sort(fs);
            for (File f : fs) {
                if (!f.isFile()) continue;
                if (!first) b.append(',');
                first = false;
                b.append("{\"name\":\"").append(Ssh.esc(f.getName())).append("\",\"size\":").append(f.length())
                 .append(",\"note\":\"").append(Ssh.esc(p().getString("pkg_" + f.getName(), ""))).append("\"}");
            }
        }
        return b.append("]}").toString();
    }

    public boolean save(String name, String b64, String note) {
        try {
            byte[] data = Base64.decode(b64, Base64.DEFAULT);
            File f = new File(dir(), safe(name).endsWith(".sh") ? safe(name) : safe(name) + ".sh");
            FileOutputStream o = new FileOutputStream(f);
            o.write(data);
            o.close();
            if (note != null) p().edit().putString("pkg_" + f.getName(), note).apply();
            return true;
        } catch (Throwable e) { return false; }
    }

    public void delete(String name) {
        try { new File(dir(), safe(name)).delete(); p().edit().remove("pkg_" + safe(name)).apply(); } catch (Throwable ignore) { }
    }

    public byte[] read(String name) {
        try {
            InputStream is = new java.io.FileInputStream(new File(dir(), safe(name)));
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[8192];
            int n;
            while ((n = is.read(b)) > 0) bo.write(b, 0, n);
            is.close();
            return bo.toByteArray();
        } catch (Throwable e) { return null; }
    }
}
