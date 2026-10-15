package com.padagent.c3shell;

/**
 * 体验版（2026-09-24 用户要求）：倒计时体验期，**当前 3 天 = 72 小时**（2026-09-25 08:00 → 2026-09-28 08:00 北京时间）。
 * 天数与起止时间都由构建写进 TrialInfo（改构建参数就跟着变），本类不写死 ✓
 * 起止时间由构建时生成（TrialInfo.java），正式版里 TrialInfo.ON=false，本类完全不参与 ✓
 *
 *   · 过期  → 不可取消的弹窗提示 + 退出（想继续用找作者要正式版）
 *   · 未开始 → 正常用，提示「体验期 X 开始」
 *   · 最后 24 小时 → 每天提醒一次
 *   · 防改表：记住「见过的最晚时间」，把系统时间往回调**不会**延长体验期 ✓
 */
public final class Trial {

    private static final String P = "c3shell";
    private static long gSeen = 0;

    /** 可信当前时间 = max(系统时间, 见过的最晚时间)；改表回退不会变小 ✓ */
    public static long trustedNow(android.content.Context c) {
        long now = System.currentTimeMillis();
        try {
            android.content.SharedPreferences sp = c.getSharedPreferences(P, android.content.Context.MODE_PRIVATE);
            long seen = sp.getLong("trialSeen", 0);
            if (now > seen) { sp.edit().putLong("trialSeen", now).apply(); seen = now; }
            gSeen = seen;
        } catch (Throwable e) { gSeen = now; }
        return gSeen > 0 ? gSeen : now;
    }

    public static boolean on() { return TrialInfo.ON; }

    public static boolean beforeStart(android.content.Context c) {
        return on() && trustedNow(c) < TrialInfo.START;
    }

    public static boolean expired(android.content.Context c) {
        if (licensed(c)) return false;               /* 2026-09-24：已激活 → 体验期不再限制 ✓ */
        return on() && trustedNow(c) > TrialInfo.END;
    }

    /** 已激活（有有效卡密）就不走体验倒计时 —— 用户买卡后不用换包 ✓ */
    public static boolean licensed(android.content.Context c) {
        try { return new Lic(c).licensedNow(); } catch (Throwable e) { return false; }
    }

    public static long leftMs(android.content.Context c) {
        long t = trustedNow(c);
        if (t < TrialInfo.START) return TrialInfo.END - TrialInfo.START;   // 还没开始：显示完整时长
        return Math.max(0, TrialInfo.END - t);
    }

    /** 「3 天 4 小时」/「5 小时 20 分」/「18 分」 */
    public static String leftText(android.content.Context c) {
        long ms = leftMs(c);
        long d = ms / 86400000L, h = (ms % 86400000L) / 3600000L, mi = (ms % 3600000L) / 60000L;
        if (d > 0) return d + " 天 " + h + " 小时";
        if (h > 0) return h + " 小时 " + mi + " 分";
        return mi + " 分";
    }

    /** 体验期共几天（由 START/END 算出，改构建参数自动跟着变 ✓）*/
    public static int days() { return (int) ((TrialInfo.END - TrialInfo.START) / 86400000L); }

    public static String windowText() {
        return fmt(TrialInfo.START) + " → " + fmt(TrialInfo.END);
    }

    public static String fmt(long ms) {
        java.text.SimpleDateFormat f = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm");
        return f.format(new java.util.Date(ms));
    }

    /** 启动闸门：过期 → 提示并退出（false）；其它情况返回 true（可继续）✓ */
    public static boolean gate(final android.app.Activity a) {
        if (!on()) return true;
        if (licensed(a)) return true;                /* 已激活：直接放行，不弹到期/提醒 ✓ */
        try {
            if (expired(a)) {
                new android.app.AlertDialog.Builder(a)
                    .setTitle("体验期已结束")
                    .setMessage("这个包的 " + days() + " 天体验期（" + windowText() + "）已经结束。\n\n"
                              + "想继续使用请联系作者：微信 lwms1020（备注 C3 控制台）✓")
                    .setCancelable(false)
                    .setPositiveButton("退出", new android.content.DialogInterface.OnClickListener() {
                        public void onClick(android.content.DialogInterface d, int w) { a.finish(); }
                    })
                    .show();
                return false;
            }
            if (beforeStart(a)) {
                toast(a, "体验版：体验期 " + fmt(TrialInfo.START) + " 开始，共 " + days() + " 天");
            } else if (leftMs(a) < 86400000L) {          // 最后 24 小时：每天只提醒一次 ✓
                android.content.SharedPreferences sp = a.getSharedPreferences(P, android.content.Context.MODE_PRIVATE);
                String day = new java.text.SimpleDateFormat("yyyyMMdd").format(new java.util.Date());
                if (!day.equals(sp.getString("trialWarnDay", ""))) {
                    sp.edit().putString("trialWarnDay", day).apply();
                    new android.app.AlertDialog.Builder(a)
                        .setTitle("体验版快到期了")
                        .setMessage("剩余 " + leftText(a) + "（" + fmt(TrialInfo.END) + " 结束）。\n\n"
                                  + "要正式版请联系作者：微信 lwms1020 ✓")
                        .setPositiveButton("知道了", null)
                        .show();
                }
            }
        } catch (Throwable e) { }
        return true;
    }

    private static void toast(android.app.Activity a, String m) {
        try { android.widget.Toast.makeText(a, m, android.widget.Toast.LENGTH_LONG).show(); } catch (Throwable e) { }
    }

    private Trial() { }
}
