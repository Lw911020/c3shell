package com.padagent.c3shell;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Handler;
import android.os.IBinder;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.TextView;

/** 2026-09-23 v1.7 #2：全局桌面悬浮窗
 *  画中画小窗 → 点击放大 → 自由拖拽/缩放 → 10 秒无操作自动收回 ✓
 *  内容：先用 APP 自身的实时页（后续 #1 投屏做好后换成推流画面 ✓）
 *  兼容：compile stub 缺 API 常量 → 一律用字面量/反射，全部 try/catch 兜底 ✓ */
public class FloatWin extends Service {
    private WindowManager wm;
    private View root;
    private WindowManager.LayoutParams lp;
    private WebView web;
    /* 2026-09-24 R91（用户要求）：状态栏与右下角把手**平时隐藏**，点一下才出现，3.5 秒后自动收起 ✓
       这样平时悬浮窗就是干干净净一块画面（只有画面右上角的「C3 熄屏」）✓ */
    private TextView bar, close, grip;
    private final Runnable hideCtl = new Runnable() { public void run() { ctl(false); } };
    private int sw = 1080, sh = 1920;
    private boolean big = false;
    private final Handler H = new Handler();
    private Runnable shrink;
    // 2026-09-23 v1.7 #10：智能避让（前台应用在避让名单里 → 长期隐藏不弹回 ✓）
    private Runnable avoidLoop;
    // 2026-09-23 v1.7：状态暴露给 /api/float/status ✓
    public static volatile boolean RUNNING = false;
    private static FloatWin CUR = null;   // 当前窗口实例（多实例时只在销毁自己时清标志 ✓）
    public static volatile boolean HIDDEN = false;
    public static volatile boolean AVOIDED = false;
    public static volatile String LASTFG = "";
    private boolean hidden = false;
    private int diagN = 0;
    private String lastFg = "";
    private static final String[] AVOID_DEFAULT = { "autonavi", "baidu", "amap", "navi", "map",
        "360", "dvr", "dashcam", "camera", "reverse", "park", "adas", "xincheng", "byd.navi" };

    public IBinder onBind(Intent i) { return null; }

    public void onCreate() {
        super.onCreate();
        try {
            wm = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
            sw = getResources().getDisplayMetrics().widthPixels;
            sh = getResources().getDisplayMetrics().heightPixels;
            /* 2026-09-24 R95（用户思路）：**不再猜屏宽** ——
               MIUI 自由窗口下 APP 只能看到"虚拟显示"（实测 2350x1763，Resources.getSystem() 和
               DisplayManager 枚举出来也都一样 ✗），拿它算 x 必然把窗口推出屏幕右边 ✗。
               改成两招：① gravity 用 RIGHT → 由系统按**真实屏幕边缘**定位 ✓
                        ② 去掉 LAYOUT_NO_LIMITS → 系统会自动把窗口钳在屏内 ✓ */
            build();
            CUR = this;
            RUNNING = true;
            Logs.add("FLOAT", "悬浮窗已创建 " + sw + "x" + sh);
            startAvoid();   // 启动避让轮询
        } catch (Throwable t) {
            Logs.add("FLOAT", "创建失败: " + t);
            stopSelf();
        }
    }

    public void onDestroy() {
        try { if (shrink != null) H.removeCallbacks(shrink); } catch (Throwable ignore) { }
        try { if (avoidLoop != null) H.removeCallbacks(avoidLoop); } catch (Throwable ignore) { }
        try { H.removeCallbacks(hideCtl); } catch (Throwable ignore) { }
        try { if (root != null && wm != null) wm.removeView(root); } catch (Throwable ignore) { }
        if (CUR == this) { RUNNING = false; HIDDEN = false; AVOIDED = false; CUR = null; }
        Logs.add("FLOAT", "悬浮窗已销毁");
        super.onDestroy();
    }

    private int mint(int a, int b) { return a < b ? a : b; }
    /* 2026-09-24 R90（用户要求）：悬浮窗尺寸一律按 dp 算 ✓
       原来全写裸像素（状态栏 24px），本机密度 2.5 → 实际只有 9.6dp，细得像根线 ✗ */
    private int dp(int v) { try { return (int) (v * getResources().getDisplayMetrics().density + 0.5f); } catch (Throwable t) { return v; } }

    /* 2026-09-24 R95（用户要求）：**长按拖动**浮窗 —— 不用先点出状态栏 ✓
       用 onInterceptTouchEvent：只有"长按成立"后才拦截；平时的点/划照常给网页（反控不受影响 ✓）*/
    private class DragBox extends FrameLayout {
        private float dx = 0, dy = 0;
        private boolean dragging = false, armed = false;
        private final Runnable fire = new Runnable() { public void run() {
            armed = false; dragging = true; poke();   /* 长按成立 → 进入拖动 + 露出控制条 ✓ */
        } };
        DragBox(Context c) { super(c); }
        public boolean onInterceptTouchEvent(MotionEvent e) {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    dx = e.getRawX(); dy = e.getRawY(); dragging = false; armed = true;
                    H.removeCallbacks(fire); H.postDelayed(fire, 450);
                    return false;
                case MotionEvent.ACTION_MOVE:
                    if (armed) {
                        if (Math.abs(e.getRawX() - dx) > 14 || Math.abs(e.getRawY() - dy) > 14) {
                            armed = false; H.removeCallbacks(fire);   /* 划动 → 不是长按，交给网页 ✓ */
                        }
                        return false;
                    }
                    return dragging;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    H.removeCallbacks(fire); armed = false;
                    boolean was = dragging; dragging = false;
                    return was;
            }
            return false;
        }
        public boolean onTouchEvent(MotionEvent e) {
            if (!dragging) return false;
            if (e.getActionMasked() == MotionEvent.ACTION_MOVE) {
                lp.x -= (int) (e.getRawX() - dx);    /* 向右拖 → 距右边更近 ✓（gravity=RIGHT）*/
                lp.y += (int) (e.getRawY() - dy);
                dx = e.getRawX(); dy = e.getRawY();
                lp.x = Math.max(0, lp.x);            /* 不许跑出右边；左边由系统钳制 ✓ */
                lp.y = Math.max(0, Math.min(sh - dp(60), lp.y));
                apply();
            }
            return true;
        }
    }

    private void build() {
        FrameLayout box = new DragBox(this);
        /* 2026-09-24 R90（用户要求）：四个角做圆角 ✓
           关键：光给背景圆角不够 —— 里面的 WebView（投屏画面）是方块，四角会把圆角盖掉 ✗
           所以再加 setClipToOutline(true)：让整棵子视图都按圆角裁剪 ✓（API21+，用反射兼容 stub ✓） */
        final int CORNER = dp(16);
        try {
            android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
            g.setColor(0xEE10141A);
            g.setCornerRadius(CORNER);
            box.setBackground(g);
        } catch (Throwable t) {
            box.setBackgroundColor(0xEE10141A);
        }
        try {
            java.lang.reflect.Method m = View.class.getMethod("setClipToOutline", boolean.class);
            m.invoke(box, Boolean.TRUE);
        } catch (Throwable ignore) { }

        web = new WebView(this);
        try {
            web.getSettings().setJavaScriptEnabled(true);
            /* 2026-09-24 R97（用户报「熄屏/亮屏按钮没用」的真因之一）：
               浮窗这个 WebView 原来**没关缓存**（主页那边有关 ✓，这里漏了 ✗）
               → 改了 cast.html 之后浮窗还在跑旧页面，按新逻辑改的按钮自然不生效 ✗
               现在：LOAD_NO_CACHE + clearCache + URL 带版本号做 cache-busting ✓ */
            try { web.getSettings().setCacheMode(2); } catch (Throwable ignore) { }   // 2=LOAD_NO_CACHE
            try { web.clearCache(true); } catch (Throwable ignore) { }
            String ver = "";
            try { ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Throwable ignore) { }
            web.setBackgroundColor(0x00000000);
            web.loadUrl(appBase() + "/cast.html?mini=1&v=" + ver);   // v1.7 #1 浮窗显示投屏；2026-09-24 改用 APP 真实端口（退让后 3081 可能是别人的服务）✓
        } catch (Throwable ignore) { }
        FrameLayout.LayoutParams fw = new FrameLayout.LayoutParams(-1, -1);
        fw.setMargins(dp(2), dp(36), dp(2), dp(2));
        box.addView(web, fw);

        // 顶部细条：拖动 + 双击放大/收回 + 关闭
        bar = new TextView(this);
        bar.setText("C3 画面 · 拖动/点按放大");
        bar.setTextSize(12f);
        bar.setTextColor(Color.parseColor("#9EC1FF"));
        bar.setGravity(android.view.Gravity.CENTER_VERTICAL | android.view.Gravity.LEFT);
        bar.setPadding(dp(12), 0, dp(58), 0);   /* 右边留出关闭键的位置（否则字会压到 ✕ 下面 ✗）*/
        bar.setBackgroundColor(0x33FFFFFF);
        FrameLayout.LayoutParams fb = new FrameLayout.LayoutParams(-1, dp(34));
        box.addView(bar, fb);

        close = new TextView(this);
        close.setText(" ✕ ");
        close.setTextSize(15f);
        close.setTextColor(Color.parseColor("#FFB4B4"));
        close.setGravity(android.view.Gravity.CENTER);
        FrameLayout.LayoutParams fc = new FrameLayout.LayoutParams(dp(56), dp(34), android.view.Gravity.RIGHT | android.view.Gravity.TOP);
        box.addView(close, fc);
        close.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { stopSelf(); }
        });

        // 右下角缩放把手
        grip = new TextView(this);
        grip.setText("◢");
        grip.setTextSize(16f);
        grip.setTextColor(Color.parseColor("#9EC1FF"));
        grip.setGravity(android.view.Gravity.CENTER);
        grip.setBackgroundColor(0x33FFFFFF);
        FrameLayout.LayoutParams fg = new FrameLayout.LayoutParams(dp(48), dp(48), android.view.Gravity.RIGHT | android.view.Gravity.BOTTOM);
        box.addView(grip, fg);

        root = box;   /* 长按拖动 / 点按反控 都由 DragBox 分流 ✓ */

        int type;
        try { type = (android.os.Build.VERSION.SDK_INT >= 26) ? 2038 : 2002; } catch (Throwable t) { type = 2002; }
        lp = new WindowManager.LayoutParams();
        lp.type = type;
        /* 2026-09-24 R95：去掉 LAYOUT_NO_LIMITS —— 让系统把窗口钳在屏内（以前允许拖出屏外 ✗）*/
        lp.flags = 0x00000008 /*NOT_FOCUSABLE：不抢焦点*/ | 0x00000200 /*NOT_TOUCH_MODAL*/;
        lp.format = -3;   // PixelFormat.TRANSLUCENT
        lp.gravity = android.view.Gravity.TOP | android.view.Gravity.RIGHT;   /* 锚右边缘 ✓ */
        setSize(false);
        lp.x = dp(12);      /* 距右边 12dp —— 由系统按真实屏边缘算，不用知道屏宽 ✓ */
        lp.y = dp(48);

        wm.addView(root, lp);
        ctl(false);   /* 2026-09-24 R91：平时隐藏状态栏与把手 ✓ */

        // 2026-09-24 R95：顶栏不再负责拖动（长按整窗即可拖 ✓），只保留"点一下放大/收回"
        final float[] st = new float[4];
        bar.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { toggleBig(); poke(); }
        });

        // 缩放（右下把手）
        grip.setOnTouchListener(new View.OnTouchListener() {
            public boolean onTouch(View v, MotionEvent e) {
                if (e.getAction() == MotionEvent.ACTION_DOWN) { st[0] = e.getRawX(); st[1] = e.getRawY(); st[2] = lp.width; st[3] = lp.height; return true; }
                if (e.getAction() == MotionEvent.ACTION_MOVE) {
                    int w = (int) (st[2] + (e.getRawX() - st[0]));
                    int h = (int) (st[3] + (e.getRawY() - st[1]));
                    lp.width = Math.max(240, Math.min(sw, w));
                    lp.height = Math.max(180, Math.min(sh, h));
                    apply(); return true;
                }
                return false;
            }
        });

        scheduleShrink();
    }

    /** 读避让名单（内置关键词 + 用户自定义，逗号分隔 ✓）*/
    private String avoidList() {
        String u = "";
        try { u = getSharedPreferences("c3shell", MODE_PRIVATE).getString("floatAvoid", ""); } catch (Throwable ignore) { }
        return u == null ? "" : u;
    }
    /** 当前前台应用包名（UsageStats ✓ 需 GET_USAGE_STATS 授权；失败返回空）*/
    private String foregroundPkg() {
        // 优先：辅助功能（最可靠 ✓）；5 秒内有事件就直接用 ✓
        try {
            if (FloatA11y.lastPkg != null && FloatA11y.lastPkg.length() > 0
                    && (System.currentTimeMillis() - FloatA11y.lastAt) < 5000) return FloatA11y.lastPkg;
        } catch (Throwable ignore) { }
        try {
            Object usm = getSystemService("usagestats");
            if (usm == null) return "";
            long now = System.currentTimeMillis();
            java.lang.reflect.Method q = usm.getClass().getMethod("queryEvents", long.class, long.class);
            Object events = q.invoke(usm, now - 6L*3600L*1000L, now);   // 2026-09-23 修复：15 秒窗口内常常没有前台事件 → 包名为空 ✗，放宽到 6 小时 ✓
            if (events == null) return "";
            /* 2026-09-23 修复（车机日志实证）：UsageEvents.getEvents(long,long) 是隐藏 API，
               Android 10 上反射必抛 NoSuchMethodException → 智能避让一直失效 ✗
               改用公开的 hasNextEvent()/getNextEvent(UsageEvents.Event) ✓ */
            Class<?> evCls = Class.forName("android.app.usage.UsageEvents$Event");
            java.lang.reflect.Method hasNext = events.getClass().getMethod("hasNextEvent");
            java.lang.reflect.Method nextEv  = events.getClass().getMethod("getNextEvent", evCls);
            Object ev = evCls.newInstance();
            java.lang.reflect.Method gt = evCls.getMethod("getEventType");
            java.lang.reflect.Method gp = evCls.getMethod("getPackageName");
            String last = "";
            int guard = 0;
            while (((Boolean) hasNext.invoke(events)).booleanValue() && ++guard < 4000) {
                nextEv.invoke(events, ev);
                if (((Integer) gt.invoke(ev)).intValue() == 1 /*MOVE_TO_FOREGROUND*/) {
                    Object pk = gp.invoke(ev);
                    if (pk != null) last = String.valueOf(pk);
                }
            }
            return last;
        } catch (Throwable t) { try { Logs.add("FLOAT", "前台检测失败: " + t); } catch (Throwable ignore) { } return ""; }  // DIAG_FG
    }
    private boolean inAvoid(String pkg) {
        if (pkg == null || pkg.length() == 0) return false;
        String low = pkg.toLowerCase();
        for (String k : AVOID_DEFAULT) if (low.indexOf(k) >= 0) return true;
        String u = avoidList().toLowerCase();
        if (u.length() > 0) {
            String[] parts = u.split(",");
            for (String x : parts) {
                String k = x.trim();
                if (k.length() > 0 && low.indexOf(k) >= 0) return true;
            }
        }
        return false;
    }
    private void setHidden(boolean h) {
        try {
            if (h == hidden) return;
            hidden = h; HIDDEN = h;
            if (h) { try { wm.removeView(root); } catch (Throwable ignore) { } }
            else { try { wm.addView(root, lp); } catch (Throwable ignore) { } }
            Logs.add("FLOAT", h ? "避让：已隐藏悬浮窗（前台=" + lastFg + "）" : "避让结束：恢复显示悬浮窗");
        } catch (Throwable ignore) { }
    }
    private void startAvoid() {
        try {
            if (avoidLoop != null) H.removeCallbacks(avoidLoop);
            avoidLoop = new Runnable() {
                public void run() {
                    try {
                        String pkg = foregroundPkg();
                        try { if (diagN < 8) { diagN++; Logs.add("FLOAT", "前台检测#" + diagN + " = '" + pkg + "' avoid=" + inAvoid(pkg)); } } catch (Throwable ignore) { }
                        if (pkg != null && pkg.length() > 0 && !pkg.equals(lastFg)) {
                            lastFg = pkg; LASTFG = pkg;
                            boolean avoid = inAvoid(pkg); AVOIDED = avoid;
                            setHidden(avoid);
                            if (!avoid && !hidden) { scheduleShrink(); }
                        }
                    } catch (Throwable ignore) { }
                    H.postDelayed(this, 900);
                }
            };
            H.postDelayed(avoidLoop, 1500);
        } catch (Throwable ignore) { }
    }

    /** 露出控制条/把手（并在 3.5 秒无操作后自动收起 ✓）*/
    private void poke() {
        try {
            ctl(true);
            H.removeCallbacks(hideCtl);
            H.postDelayed(hideCtl, 3500);
        } catch (Throwable ignore) { }
    }

    /** 显示/隐藏：原生状态栏 + 关闭键 + 右下把手；画面边距同步让位 ✓
       注意：网页右上角那个「C3 熄屏」按钮要跟着反着来，否则会和 ✕ 重叠 ✗ */
    private void ctl(boolean show) {
        try {
            int v = show ? View.VISIBLE : View.GONE;
            if (bar != null) bar.setVisibility(v);
            if (close != null) close.setVisibility(v);
            if (grip != null) grip.setVisibility(v);
            if (web != null) {
                try {
                    FrameLayout.LayoutParams p = (FrameLayout.LayoutParams) web.getLayoutParams();
                    p.topMargin = show ? dp(36) : 0;
                    web.setLayoutParams(p);
                } catch (Throwable ignore) { }
                /* 编译桩（libs/android.jar）里没有 evaluateJavascript → 按本文件既有风格走反射 ✓ */
                try {
                    Class<?> vc = Class.forName("android.webkit.ValueCallback");
                    java.lang.reflect.Method ej = WebView.class.getMethod("evaluateJavascript", String.class, vc);
                    ej.invoke(web, "try{document.getElementById('topbar').style.display='" + (show ? "none" : "flex") + "';}catch(e){}", null);
                } catch (Throwable ignore) { }
            }
        } catch (Throwable ignore) { }
    }

    private void setSize(boolean bigMode) {
        big = bigMode;
        if (big) { lp.width = (int) (sw * 0.72); lp.height = (int) (sh * 0.72); }
        /* 2026-09-24 用户要求：默认尺寸翻倍（原来 min(0.34*屏, 560x460) → 现在 min(0.68*屏, 1120x920)）✓ */
        else { lp.width = mint((int) (sw * 0.68), 1120); lp.height = mint((int) (sh * 0.68), 920); }
    }

    private void apply() {
        try { wm.updateViewLayout(root, lp); } catch (Throwable ignore) { }
    }

    private void toggleBig() {
        setSize(!big);
        if (big) {
            lp.x = (sw - lp.width) / 2;
            lp.y = (sh - lp.height) / 2;
        }
        apply();
        scheduleShrink();
    }

    /** 10 秒无操作 → 自动收回小窗（保障行车安全 ✓）*/
    private void scheduleShrink() {
        try {
            if (shrink != null) H.removeCallbacks(shrink);
            shrink = new Runnable() { public void run() {
                if (big) { setSize(false); apply(); }
            } };
            H.postDelayed(shrink, 10000);
        } catch (Throwable ignore) { }
    }
    /** 2026-09-24 修「悬浮窗黑屏」根因：
        APP 的页面服务端口会**退让**（3081 被连接器占用时依次用 3082/3083/随机，
        见 MainActivity 启动内嵌服务那段），而这里原来写死 http://127.0.0.1:3081/cast.html
        → 浮窗加载到**别人的**话页面（404）= 黑屏 ✗。
        现在：先读 APP 自己存的 localPort，再依次试 3081~3083，
        并且**实测 /cast.html 是不是 200** 才采用，避免再认错服务 ✓ */
    private String appBase() {
        int p = 0;
        try { p = getSharedPreferences("c3shell", MODE_PRIVATE).getInt("localPort", 0); } catch (Throwable ignore) { }
        int[] cands = new int[] { p, 3081, 3082, 3083 };
        for (int c : cands) {
            if (c <= 0) continue;
            if (probeCast(c)) return "http://127.0.0.1:" + c;
        }
        return "http://127.0.0.1:" + (p > 0 ? p : 3081);
    }

    /** 探这个端口是不是「APP 自己的页面服务」（能给出 cast.html 才算 ✓） */
    private boolean probeCast(int port) {
        java.net.Socket sk = null;
        try {
            sk = new java.net.Socket();
            sk.connect(new java.net.InetSocketAddress("127.0.0.1", port), 300);
            sk.setSoTimeout(900);
            sk.getOutputStream().write(("GET /cast.html HTTP/1.0" + CH_CRLF + "Host: 127.0.0.1" + CH_CRLF + CH_CRLF).getBytes("UTF-8"));
            sk.getOutputStream().flush();
            byte[] b = new byte[64];
            int n = sk.getInputStream().read(b);
            if (n <= 0) return false;
            String head = new String(b, 0, n, "UTF-8");
            return head.indexOf("200") > 0 && head.indexOf("404") < 0;
        } catch (Throwable t) {
            return false;
        } finally {
            try { if (sk != null) sk.close(); } catch (Throwable ignore) { }
        }
    }

    private static final String CH_CRLF = String.valueOf((char) 13) + String.valueOf((char) 10);
}
