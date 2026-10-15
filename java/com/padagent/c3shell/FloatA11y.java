package com.padagent.c3shell;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;

/** 2026-09-23 v1.7 #10：前台应用检测（国产车机 ROM 上 UsageStats 常被限制 ✗，辅助功能最可靠 ✓）
 *  只读窗口状态事件里的包名，不读取任何窗口内容 ✓ */
public class FloatA11y extends AccessibilityService {
    public static volatile String lastPkg = "";
    public static volatile long lastAt = 0;
    public static volatile boolean connected = false;
    private static int pollErr = 0;
    public static volatile String INFO = "未开始";

    protected void onServiceConnected() {
        connected = true;
        startPoll();   // 主动轮询活动窗口 ✓
        // 服务信息完全由 res/xml/a11y.xml 声明（canRetrieveWindowContent + flagRetrieveInteractiveWindows ✓）
        try { Logs.add("FLOAT", "辅助功能服务已连接（前台检测可用 ✓）"); } catch (Throwable ignore) { }
    }

    /** 主动查询活动窗口（比等 onAccessibilityEvent 可靠 ✓ 全反射实现，桩里没有这些类也能编译 ✓）*/
    private void pollWindows() {
        try {
            int nWin = 0, nAct = 0; String err = "";
            java.lang.reflect.Method mw = getClass().getMethod("getWindows");
            Object list = mw.invoke(this);
            if (list instanceof java.util.List) {
                java.util.List<?> ws = (java.util.List<?>) list;
                nWin = ws.size();
                for (Object w : ws) {
                    try {
                        java.lang.reflect.Method ma = w.getClass().getMethod("isActive");
                        Object act = ma.invoke(w);
                        boolean active = (act instanceof Boolean) && ((Boolean) act).booleanValue();
                        if (!active) continue;
                        nAct++;
                        java.lang.reflect.Method mr = w.getClass().getMethod("getRoot");
                        Object r = mr.invoke(w);
                        if (r == null) continue;
                        java.lang.reflect.Method mp = r.getClass().getMethod("getPackageName");
                        Object pk = mp.invoke(r);
                        if (pk != null && String.valueOf(pk).length() > 0) {
                            lastPkg = String.valueOf(pk);
                            lastAt = System.currentTimeMillis();
                        }
                    } catch (Throwable ignore) { }
                }
            }
            INFO = "win=" + nWin + " act=" + nAct + " pkg=" + lastPkg + (err.length() > 0 ? (" err=" + err) : "");
        } catch (Throwable t) {
            INFO = "异常: " + t;
        }
    }

    private void startPoll() {
        try {
            final android.os.Handler h = new android.os.Handler();
            h.postDelayed(new Runnable() {
                public void run() {
                    pollWindows();
                    try { h.postDelayed(this, 900); } catch (Throwable ignore) { }
                }
            }, 900);
        } catch (Throwable ignore) { }
    }
    public void onAccessibilityEvent(AccessibilityEvent e) {
        try {
            if (e == null) return;
            int t = e.getEventType();
            if (t == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
                CharSequence p = e.getPackageName();
                if (p != null && p.length() > 0) { lastPkg = String.valueOf(p); lastAt = System.currentTimeMillis(); }
            }
        } catch (Throwable ignore) { }
    }
    public void onInterrupt() { }
}
