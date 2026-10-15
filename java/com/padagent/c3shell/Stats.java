package com.padagent.c3shell;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.UUID;

/**
 * 匿名心跳统计（2026-09-21 用户要求：后台监控使用人数/在线人数）。
 * 只上报：随机设备ID + APP版本 + Android版本 + 时间戳。不含任何个人信息。
 * 后端地址可配置（默认空 = 不上报），见 server/stats-server.py。
 */
public class Stats {
    private static final String PREFS = "c3shell";
    private static volatile boolean RUN = false;

    public static String url(Context c) {
        try { return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("statsUrl", ""); }
        catch (Throwable e) { return ""; }
    }
    public static boolean enabled(Context c) {
        try { return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("statsEnabled", true); }
        catch (Throwable e) { return true; }
    }
    public static String deviceId(Context c) {
        SharedPreferences sp = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String id = sp.getString("deviceId", "");
        if (id == null || id.length() == 0) {
            id = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
            sp.edit().putString("deviceId", id).apply();
        }
        return id;
    }
    public static String setUrl(Context c, String u) {
        c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("statsUrl", u == null ? "" : u.trim()).apply();
        return "{\"ok\":true,\"url\":\"" + Ssh.esc(url(c)) + "\"}";
    }
    public static String setEnabled(Context c, String v) {
        boolean on = !("0".equals(v) || "false".equalsIgnoreCase(v) || "off".equalsIgnoreCase(v) || "no".equalsIgnoreCase(v));   // 2026-09-21：兼容 "off"/"no"（原来只有 off 会被当成开启 ✗）
        c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("statsEnabled", on).commit();
        return "{\"ok\":true,\"enabled\":" + on + "}";
    }

    /** 上报一次；返回服务器响应（用于自检） */
    public static String beat(Context c) {
        String u = url(c);
        if (u == null || u.length() == 0) return "{\"ok\":false,\"error\":\"未配置统计地址\"}";
        HttpURLConnection conn = null;
        try {
            String body = "{\"id\":\"" + deviceId(c) + "\",\"ver\":\"" + Build0.ver(c) + "\",\"os\":\"Android "
                    + android.os.Build.VERSION.RELEASE + "\",\"ts\":" + (System.currentTimeMillis() / 1000) + "}";
            conn = (HttpURLConnection) new URL(u).openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(6000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            OutputStream os = conn.getOutputStream();
            os.write(body.getBytes("UTF-8"));
            os.close();
            int code = conn.getResponseCode();
            Logs.add("STATS", "beat code=" + code + " id=" + deviceId(c));
            return "{\"ok\":" + (code >= 200 && code < 300) + ",\"code\":" + code + "}";
        } catch (Throwable e) {
            Logs.add("STATS", "beat 失败: " + e);
            return "{\"ok\":false,\"error\":\"" + Ssh.esc(String.valueOf(e)) + "\"}";
        } finally {
            if (conn != null) try { conn.disconnect(); } catch (Throwable ignore) { }
        }
    }

    /** 启动后台心跳（每 10 分钟一次） */
    public static void start(final Context c) {
        if (RUN) return;
        RUN = true;
        Thread t = new Thread(new Runnable() {
            public void run() {
                while (true) {
                    try { if (enabled(c)) beat(c); } catch (Throwable ignore) { }
                    try { Thread.sleep(600000L); } catch (InterruptedException e) { return; }
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }

    static class Build0 {
        static String ver(Context c) {
            try { return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName; }
            catch (Throwable e) { return "?"; }
        }
    }
}
