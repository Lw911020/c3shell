package com.padagent.c3shell;

import android.content.Context;
import android.content.SharedPreferences;

/** 语音提示词（可自定义，存本机）。2026-09-21 用户要求。 */
public class Cues {
    public static final String[] KEYS = { "connected", "disconnected", "driveOn", "driveOff", "sampleEnd" };
    public static final String[] DEF = { "设备已连接", "连接已断开", "辅助驾驶已开启", "辅助驾驶已关闭", "采样已结束" };

    private final SharedPreferences p;

    public Cues(Context c) { p = c.getSharedPreferences("c3shell", Context.MODE_PRIVATE); }

    private static String def(String k) {
        for (int i = 0; i < KEYS.length; i++) if (KEYS[i].equals(k)) return DEF[i];
        return k;
    }

    public String get(String k) {
        String v = p.getString("cue_" + k, null);
        return (v == null || v.length() == 0) ? def(k) : v;
    }

    public void set(String k, String v) { p.edit().putString("cue_" + k, v == null ? "" : v).apply(); }

    public String json() {
        StringBuilder b = new StringBuilder("{\"ok\":true,\"cues\":[");
        for (int i = 0; i < KEYS.length; i++) {
            if (i > 0) b.append(',');
            b.append("{\"key\":\"").append(KEYS[i]).append("\",\"text\":\"").append(Ssh.esc(get(KEYS[i]))).append("\"}");
        }
        return b.append("]}").toString();
    }
}
