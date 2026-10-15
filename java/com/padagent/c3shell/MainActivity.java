package com.padagent.c3shell;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * C3 控制台（纯 WebView 壳）。
 *
 * 只做一件事：把本机 dsh-ssh-connector 独立服务（默认 http://127.0.0.1:3081）
 * 的两个页面装进一个可安装的 APP：
 *   /      -> SSH 控制台
 *   /diag  -> 转向诊断（调试窗口）
 *
 * 页面里的 token 由 serve.mjs 在服务端注入，所以这里不需要带 token。
 * 服务没在跑时显示一页带原因与补救步骤的错误页（不是白屏）。
 */
public class MainActivity extends Activity {

    private static final String PREFS = "c3shell";
    private static final String K_HOST = "host";
    private static final String K_PORT = "port";
    private static final String DEFAULT_HOST = "127.0.0.1";
    private static final int DEFAULT_PORT = 3081;

    private static final String P_CONSOLE = "/";
    private static final String P_DIAG = "/diag";

    private static int C_BG = 0xFF0E1116;
    private static int C_BAR = 0xFF161B22;
    private static final int C_ACTIVE = 0xFF1F6FEB;
    private static final int C_IDLE = 0xFF232A34;
    /* 浅色外壳（白底黑字，2026-09-22）：未选中/普通按钮的浅底与深字 */
    private static final int C_IDLE_L = 0xFFF2F4F7;
    private static final int C_FG_L   = 0xFF1B1F24;
    private static final int C_DIM_L  = 0xFF525C6B;
    private static int C_FG = 0xFFE6EDF3;
    private static final int C_DIM = 0xFF8B949E;

    private WebView web;
    private Web embed;
    private static int EMBED_PORT = 0;
    private Api apiRef;
    private EditText termInput;
    private TextView termLbl;
    private View termBar;
    private SharedPreferences prefs;
    private Button bConsole;
    private String pendingQuery = "";    // load() 时附加到 URL 的查询（如 ui=1）
    private String pendingHash  = "";    // load() 时附加的锚点（如 #settings）
    private Button bDiag;
    private String page = P_CONSOLE;
    private String pendingUrl = "";
    private boolean failed = false;
    private View rootView;             // 最外层容器（它的底色也是"建得比 initChrome 早"的那批，需要重刷）
    private View topBarRow;            // 原生顶栏那一行（一级按钮 + 版本号），显示模式切换时整行显隐
    private View topBarInner;
    private TextView topTitle;          // 2026-09-24 R109：自建的矮标题条 ✓          // 顶栏里那排按钮的容器（buildBar 建的内层 LinearLayout，也要跟着外壳变色）

    @Override
    protected void onCreate(Bundle savedInstanceState) {

        super.onCreate(savedInstanceState);
        // 2026-09-24 加固：签名校验（不符 → 提示并退出）+ 调试/注入痕迹提示；详见 Guard.java
        try { if (!Guard.check(this)) return; } catch (Throwable ignore) { }
        // 2026-09-24 体验版（用户要求）：过期 → 提示并退出；未开始/临近到期只提示 ✓
        // 正式版 TrialInfo.ON=false → 这一段完全不参与 ✓
        try { if (!Trial.gate(this)) return; } catch (Throwable ignore) { }
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(C_BG);
        rootView = root;                 // 2026-09-22：它也要跟着外壳重刷（否则让位处露出深色）

        // 工具条放进横向滚动容器：分屏/窄窗口下按钮仍可全部触达（2026-09-20 用户要求支持分屏）
        android.widget.HorizontalScrollView barScroll = new android.widget.HorizontalScrollView(this);
        barScroll.setHorizontalScrollBarEnabled(false);
        barScroll.setFillViewport(false);
        barScroll.addView(buildBar(), new android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT));
        LinearLayout topRow = new LinearLayout(this);
        topRow.setOrientation(LinearLayout.HORIZONTAL);
        topRow.setBackgroundColor(C_BAR);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(0, dp(56), 1f);
        topRow.addView(barScroll, slp);
        try {
            TextView tvv = new TextView(this);
            tvv.setText("v" + getPackageManager().getPackageInfo(getPackageName(), 0).versionName);
            tvv.setTextSize(14);                 // 用户反馈：版本号大一点
            tvv.setTextColor(themeLight() ? C_DIM_L : C_DIM);
            tvv.setGravity(85);                  // Gravity.BOTTOM|RIGHT → 下对齐贴右
            tvv.setPadding(dp(4), 0, dp(10), dp(4));
            topRow.addView(tvv, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT));
        } catch (Throwable ignore) { }
        topBarRow = topRow;                                        // 2026-09-22：显示模式要整行显隐
        root.addView(topRow, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(56)));


        /* 顶部标题（2026-09-21 用户要求居中）
           2026-09-24 R109（用户：APP 名称那一条太高了、太宽）：
           真因 —— 原生 ActionBar 的高度由系统主题决定（这台平板上实测 ≈68dp ✗），
           给它塞自定义视图只能改内容、改不了条本身的高度 ✗
           → 干脆**隐藏 ActionBar**，自己在最上面放一条更矮的标题条（40dp ✓），名字不变 ✓ */
        try {
            android.app.ActionBar ab = getActionBar();
            if (ab != null) {
                ab.setDisplayShowCustomEnabled(false);
                ab.setDisplayShowTitleEnabled(false);
                ab.hide();
            }
        } catch (Throwable ignore) { }
        try {
            topTitle = new TextView(this);
            topTitle.setText("C3 控制台");
            topTitle.setTextSize(15);
            topTitle.setTypeface(topTitle.getTypeface(), android.graphics.Typeface.BOLD);
            topTitle.setGravity(android.view.Gravity.CENTER);
            topTitle.setTextColor(C_FG);
            topTitle.setBackgroundColor(C_BAR);
            root.addView(topTitle, 0, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(40)));
        } catch (Throwable ignore) { }

        web = new WebView(this);
        web.setBackgroundColor(C_BG);
        web.setKeepScreenOn(true);
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);
        web.requestFocus(130);                       // View.FOCUS_DOWN：让输入框能拿到焦点
        getWindow().setSoftInputMode(16);            // SOFT_INPUT_ADJUST_RESIZE：键盘弹出时压缩内容而不是盖住
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        try { s.setCacheMode(2); } catch (Throwable ignore) { }   // 2=LOAD_NO_CACHE ✓ 2026-09-23 治"主题切换拿缓存旧样式" ✗
        try { web.clearCache(true); web.clearHistory(); } catch (Throwable ignore) { }
        try { Logs.add("BOOT", "MainActivity v" + getPackageManager().getPackageInfo(getPackageName(), 0).versionName + " 启动，已清 WebView 缓存"); } catch (Throwable ignore) { }
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(false);   // 不要"整页缩放适应"：否则 CSS 视口比设备宽，手机媒体查询不生效
        s.setSupportZoom(true); s.setBuiltInZoomControls(false);
        s.setBuiltInZoomControls(false);
        s.setSupportZoom(true);
        try {
            // API 19+；反射调用以免依赖较新的编译桩
            // 2026-09-24 加固：默认**关掉** WebView 远程调试（开着等于把解密后的页面送人；
            // 作者要看时把偏好 webdbg 置 true 即可 ✓）
            WebView.class.getMethod("setWebContentsDebuggingEnabled", boolean.class)
                    .invoke(null, Boolean.valueOf(Guard.webDebug(this)));
        } catch (Throwable ignore) {
            // 老系统没这个方法
        }
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, String url) {
                // 2026-09-22 方案A：网页切显示模式时会带 ?layout=car|tablet 重载 → 原生顶栏跟着显隐
                if (url != null && url.indexOf("c3shell://") < 0
                        && (url.indexOf("layout=car") >= 0 || url.indexOf("layout=tablet") >= 0 || url.indexOf("layout=auto") >= 0)) {
                    boolean isAuto = url.indexOf("layout=auto") >= 0;
                    String dm = isAuto ? "auto" : (url.indexOf("layout=car") >= 0 ? "car" : "tablet");
                    try { getSharedPreferences("c3shell", MODE_PRIVATE).edit().putString("displayMode", dm).commit(); } catch (Throwable ignore) { }
                    if (isAuto) {   // 自动：由原生算出 car/tablet 再重载（页面只认 car|tablet ✓）
                        lastCarMode = carMode();
                        applyModeToBar(lastCarMode ? "car" : "tablet");
                        load();
        try {   // FLOAT_AUTOSTART 记忆开关：自动开启悬浮窗 ✓
            if (getSharedPreferences("c3shell", MODE_PRIVATE).getBoolean("floatAuto", false)) {
                new android.os.Handler().postDelayed(new Runnable() { public void run() {
                    try { startService(new Intent(MainActivity.this, FloatWin.class));
                          Logs.add("FLOAT", "记忆开关：自动开启悬浮窗 ✓"); } catch (Throwable ignore) { }
                } }, 2500);
            }
        } catch (Throwable ignore) { }
                        toast("显示模式：自动（宽度 " + pageWidthDp() + "dp → " + (lastCarMode ? "车机" : "手机/平板") + "）");
                        return true;
                    }
                    lastCarMode = "car".equals(dm);
                    applyModeToBar(dm);
                    return false;              // 交给 WebView 正常加载（页面按 ?layout= 自己重排）
                }
                if (url != null && url.startsWith("c3shell://pick-key")) { startPickKey(); return true; }
                if (url != null && url.startsWith("c3shell://pick-pkg")) { startPickPkg(); return true; }
                if (url != null && url.startsWith("c3shell://pick-csv")) { startPickCsv(); return true; }
                if (url != null && url.startsWith("c3shell://save-dir")) { startPickSaveDir(); return true; }   // 2026-09-22 选导出目录   // 2026-09-22 参数页导入 CSV
                if (url != null && url.startsWith("c3shell://focus-term")) { focusTermInput(); return true; }
                if (url != null && url.startsWith("c3shell://theme")) { setChromeLight(url.indexOf("light=1") >= 0); return true; }
                if (url != null && url.startsWith("c3shell://float")) {   // v1.7 #2 桌面悬浮窗 ✓
                    boolean _on = url.indexOf("on=1") >= 0;
                    try { getSharedPreferences("c3shell", MODE_PRIVATE).edit().putBoolean("floatAuto", _on).commit(); } catch (Throwable ignore) { }  // FLOAT_MEM 记忆开关 ✓
                    boolean on = url.indexOf("on=1") >= 0;
                    if (on) {
                        if (!canOverlay()) {
                            toast("请先允许「显示在其他应用上层」，已为你打开设置 ✓");
                            openOverlaySettings();
                        } else {
                            startService(new Intent(MainActivity.this, FloatWin.class));
                            toast("悬浮窗已开启 ✓（按住顶部条拖动 / 点一下放大 / 右下角缩放 / 10 秒自动收回）");
                        }
                    } else {
                        stopService(new Intent(MainActivity.this, FloatWin.class));
                        toast("悬浮窗已关闭 ✓");
                    }
                    return true;
                }
                if (url != null && url.startsWith("c3shell://feedback")) { showFeedback(); return true; }   // 问题反馈 ✓
                if (url != null && url.startsWith("c3shell://sidecolor")) {   // 2026-09-22：页面左栏实际底色 → 让位处同色 ✓
                    try {
                        int i = url.indexOf("c=");
                        String hex = i >= 0 ? url.substring(i + 2).replaceAll("[^0-9a-fA-F]", "") : "";
                        if (hex.length() >= 6) {
                            int col = (int) Long.parseLong(hex.substring(0, 6), 16) | 0xFF000000;
                            int oldSide = sideColor();
                            getSharedPreferences("c3shell", MODE_PRIVATE).edit().putInt("sideColor", col).commit();
                            if (oldSide != col) {           // 主题变了 → 重算外壳颜色并整片重刷 ✓
                                initChrome();
                                applyChromeToViews();
                                try { paintTabs(); } catch (Throwable ignore) { }
                                Logs.add("UI", "sidecolor=" + hex + " dark=" + darkTheme()
                                        + " C_BAR=" + Integer.toHexString(C_BAR));
                            }
                            applyRootTint(carMode());
                        }
                    } catch (Throwable ignore) { }
                    return true;
                }
                if (url != null && url.startsWith("c3shell://displaymode")) {   // 2026-09-22 方案A：手机/平板 ↔ 车机
                    final String dm = (url.indexOf("mode=car") >= 0) ? "car" : "tablet";
                    try { getSharedPreferences("c3shell", MODE_PRIVATE).edit().putString("displayMode", dm).commit(); } catch (Throwable ignore) { }
                    Logs.add("UI", "显示模式 → " + dm + "（重建界面）");
                    try {
                        android.view.View c = findViewById(android.R.id.content);
                        c.postDelayed(new Runnable() { public void run() { try { recreate(); } catch (Throwable ignore) { } } }, 150);
                    } catch (Throwable ignore) { }
                    return true;
                }
                boolean needNonce = url == null || url.indexOf("?t=") >= 0;   // 一次性 nonce：只有真实点击才带
                if (needNonce && url != null && url.startsWith("c3shell://page")) {   // 一级菜单：切页面
                    // 2026-09-22 用户反馈"点击 AI 分析会闪一下"：同一页只是切页签 → 直接切，别整页重载 ✓
                    if (P_CONSOLE.equals(page) && url.indexOf("p=diag") < 0) {
                        String tab = url.indexOf("cast=1") >= 0 ? "cast" : (url.indexOf("ai=1") >= 0 ? "aian" : (url.indexOf("ui=1") >= 0 ? "uiset" : null));
                        if (tab != null && jsSwitchTab(tab)) return true;
                    }
                    page = (url.indexOf("p=diag") >= 0) ? P_DIAG : P_CONSOLE;
                    if (url.indexOf("ui=1") >= 0) { pendingQuery = "ui=1&tab=uiset"; pendingHash = ""; }   // 界面设置：用查询参数更稳 ✓
                    else if (url.indexOf("ai=1") >= 0) { pendingQuery = "tab=aian"; pendingHash = ""; }        // AI 分析 ✓
                    else if (url.indexOf("cast=1") >= 0) { pendingQuery = "tab=cast"; pendingHash = ""; }     // 投屏（车机左栏一级菜单）✓
                    else if (url.indexOf("pane=") >= 0) {                                                     // 2026-09-24 R103：参数设置 ✓
                        /* 一级菜单「参数设置」= 诊断页的"参数"页签（pane=params）✓
                           真因：这里原来只认 ui=1 / ai=1 / cast=1 ✗ → pane= 被丢掉 → 页面永远停在第一个页签 ✗ */
                        int pi = url.indexOf("pane=");
                        String pv = url.substring(pi + 5);
                        int cut = pv.length();
                        for (int ci = 0; ci < pv.length(); ci++) {
                            char ch = pv.charAt(ci);
                            if (ch == '&' || ch == '?' || ch == '#') { cut = ci; break; }
                        }
                        pendingQuery = "pane=" + pv.substring(0, cut);
                        pendingHash = "";
                    }
                    load(); return true;
                }
                if (needNonce && url != null && url.startsWith("c3shell://tools"))  { scanC3Devices(); return true; }   // 2026-09-22：设备查找 → 直接雷达扫描 ✓
                if (needNonce && url != null && url.startsWith("c3shell://reward")) { showReward();   return true; }
                if (url != null && url.startsWith("c3shell://uitab")) {     // 2026-10-05：页面页签 → 顶部菜单高亮
                    try {
                        int qi = url.indexOf("t=");
                        curTab = qi >= 0 ? url.substring(qi + 2).replaceAll("&.*$", "") : "";
                        paintTabs();
                    } catch (Throwable ignore) { }
                    return true;
                }
                if (needNonce && url != null && url.startsWith("c3shell://logs"))   { showLogs();     return true; }
                if (url != null && url.startsWith("c3shell://bar")) {
                    boolean on = url.indexOf("on=1") >= 0;
                    if (termBar != null) termBar.setVisibility(on ? View.VISIBLE : View.GONE);
                    return true;
                }
                return false;
            }
            @Override
            public void onPageFinished(WebView view, String url) {
                if (!failed) pendingUrl = "";
                /* ★ 2026-10-05 安全兜底：页面落地后如果不在投屏页，且设备端投屏可能还开着 → 停掉它。
                   起因（用户实测）：投屏编码一直编 1024×15fps，吃 C3 单核 60%+，
                   把 openpilot 拖出「进程间通信问题 / 立即接管控制 / locationd 临时错误」✗✗
                   （网页侧已用 sendBeacon 在跳转前发停止；这里兜住原生菜单等其它跳转路径 ✓）
                   例外：开着「悬浮小窗」要常驻看画面 → 不停 ✓ */
                try {
                    if (Api.CAST_ON && !FloatWin.RUNNING
                        && (url == null || url.indexOf("tab=cast") < 0)) {
                        final Api a = (apiRef != null) ? apiRef : (apiRef = new Api(MainActivity.this));   /* 匿名内部类里 this 不是 Activity ✗ */
                        new Thread(new Runnable() { public void run() {
                            try { a.handle("POST", "/api/cast/stop", "", null, null); } catch (Throwable ignore) { }
                        } }).start();
                    }
                } catch (Throwable ignore) { }
            }

            @Override
            public void onReceivedError(WebView view, int errorCode,
                                        String description, String failingUrl) {
                // 老 API 对任何资源失败都会回调，只认主文档那一次
                if (failingUrl != null && failingUrl.equals(pendingUrl)) {
                    failed = true;
                    showErrorPage(failingUrl, description, errorCode);
                }
            }
        });
        root.addView(web, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // 终端原生输入条（2026-09-21）：不依赖 WebView 的软键盘/xterm 隐藏输入框
        LinearLayout bar2 = new LinearLayout(this);
        bar2.setOrientation(LinearLayout.HORIZONTAL);
        bar2.setBackgroundColor(C_BAR);
        termBar = bar2;
        bar2.setPadding(dp(6), dp(4), dp(6), dp(4));
        termInput = new EditText(this);
        // 提示放在旁边的标签里（放进 EditText 的 hint 会被无障碍注入误当内容）
        TextView lbl = new TextView(this);
        termLbl = lbl;
        lbl.setText("输入");
        lbl.setTextSize(12);
        lbl.setTextColor(C_FG);            // 用户反馈：字太淡 → 用主文字色
        lbl.setPadding(dp(2), 0, dp(6), 0);
        bar2.addView(lbl);
        termInput.setTextSize(13);
        termInput.setSingleLine(true);
        try {   // 2026-09-22 用户要求：输入框要有"框"的样子 ✓
            android.graphics.drawable.GradientDrawable gd = new android.graphics.drawable.GradientDrawable();
            gd.setColor(0xFFFFFFFF); gd.setCornerRadius(dp(6)); gd.setStroke(dp(1), 0xFF9AA4B2);
            termInput.setBackground(gd);
        } catch (Throwable ignore) { }
        termInput.setImeOptions(5);                 // IME_ACTION_DONE（软键盘回车=发送）
        termInput.setOnKeyListener(new View.OnKeyListener() {
            public boolean onKey(View v, int code, android.view.KeyEvent e) {
                if (e != null && e.getAction() == android.view.KeyEvent.ACTION_DOWN && code == 66) {
                    sendTermText(termInput.getText().toString());
                    return true;
                }
                return false;
            }
        });
        termInput.setOnEditorActionListener(new TextView.OnEditorActionListener() {
            public boolean onEditorAction(TextView v, int actionId, android.view.KeyEvent e) {
                sendTermText(termInput.getText().toString() + "\n");   // 命令要带回车才会执行
                return true;
            }
        });
        termInput.setContentDescription("终端输入框");   // 便于无障碍精准定位
        termInput.setMinWidth(dp(110));
        termInput.setTextColor(C_FG);       // 输入框里的字也提亮
        termInput.setHintTextColor(C_FG);
        termInput.setTextSize(12);
        bar2.addView(termInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        /* 2026-10-05 用户反馈「终端输入框不支持粘贴复制吗」：车机上长按选「粘贴」不好按，
           直接给一个「粘贴」按钮 —— 把系统剪贴板内容插到光标处（不够就追加到末尾）✓ */
        Button pasteBtn = new Button(this);
        pasteBtn.setText("粘贴");
        pasteBtn.setTextSize(11);
        pasteBtn.setBackground(rounded(themeLight() ? C_IDLE_L : 0xFF1D222B, dp(12)));
        pasteBtn.setTextColor(themeLight() ? C_FG_L : C_FG);
        pasteBtn.setPadding(dp(10), dp(2), dp(10), dp(2));
        pasteBtn.setMinWidth(0); pasteBtn.setMinimumWidth(0);
        pasteBtn.setAllCaps(false);
        pasteBtn.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                try {
                    android.content.ClipboardManager cm =
                        (android.content.ClipboardManager) getSystemService(android.content.Context.CLIPBOARD_SERVICE);
                    if (cm == null || !cm.hasPrimaryClip()) return;
                    android.content.ClipData cd = cm.getPrimaryClip();
                    if (cd == null || cd.getItemCount() <= 0) return;
                    CharSequence t = cd.getItemAt(0).coerceToText(MainActivity.this);
                    if (t == null || t.length() == 0) return;
                    String cur = termInput.getText().toString();
                    int st = termInput.getSelectionStart();
                    if (st < 0 || st > cur.length()) st = cur.length();
                    termInput.setText(cur.substring(0, st) + t + cur.substring(st));
                    try { termInput.setSelection(Math.min(termInput.getText().length(), st + t.length())); } catch (Throwable ignore) { }
                } catch (Throwable ignore) { }
            }
        });
        bar2.addView(pasteBtn);
        Button sendBtn = new Button(this);
        sendBtn.setText("发送");
        sendBtn.setTextSize(11);
        sendBtn.setBackground(rounded(0xFF2F6FED, dp(12)));
        sendBtn.setTextColor(0xFFFFFFFF);
        sendBtn.setPadding(dp(8), dp(2), dp(8), dp(2));
        sendBtn.setMinWidth(0); sendBtn.setMinimumWidth(0);
        sendBtn.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { sendTermText(termInput.getText().toString() + "\n"); }
        });
        bar2.addView(sendBtn);
        String[][] extra = { {"↵", "\n"}, {"Tab", "\t"}, {"^C", "\u0003"} };
        boolean ltBar = themeLight();
        for (final String[] e2 : extra) {
            Button b = new Button(this);
            b.setText(e2[0]);
            b.setTextSize(12);
            // 2026-09-22 修（用户："发送后面那几个是黑的、字看不见、还被挤"）：
            // 原来写死深色底 0xFF1D222B + 文字色 C_FG（浅色外壳下 C_FG 是深色）→ 深底深字看不见 ✗
            b.setBackground(rounded(ltBar ? C_IDLE_L : 0xFF1D222B, dp(12)));
            b.setTextColor(ltBar ? C_FG_L : C_FG);
            b.setPadding(dp(12), dp(3), dp(12), dp(3));
            b.setMinWidth(dp(42)); b.setMinimumWidth(dp(42));     // 不再被挤压
            b.setAllCaps(false);
            b.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    if ("↵".equals(e2[0])) sendTermText(termInput.getText().toString() + "\n");
                    else sendTermText(e2[1]);
                }
            });
            bar2.addView(b);
        }
        termBar = bar2;
        bar2.setVisibility(View.GONE);      // 默认隐藏：只在「终端」页签显示
        root.addView(bar2, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // 内置 HTTP 服务（方案 C）：APP 自己托管页面，独立运行、不依赖平板
        // 优先固定 3081：手机上没有别的服务，页面/内置接口/语音服务三处地址就都统一了；
        // 若 3081 被占（例如平板上还跑着连接器），依次退让，最后才用随机端口。
        for (int tryPort : new int[] { 3081, 3082, 3083, 0 }) {
            try {
                embed = new Web(this, tryPort);
                apiRef = new Api(this);
                EMBED_PORT = embed.start(apiRef);
                break;
            } catch (Throwable ignore) {
                EMBED_PORT = 0;
            }
        }
        try {
            android.util.Log.i("C3ShellWeb", "embedded server on 127.0.0.1:" + EMBED_PORT);
            try { prefs.edit().putInt("localPort", EMBED_PORT).apply(); } catch (Throwable ignore) { }
        } catch (Throwable t) {
            EMBED_PORT = 0;   // 启动失败则退回"连外部连接器"模式
        }

        try { new Store(this).ensurePresetKeys(); } catch (Throwable ignore) { }

        Logs.init(this);
        // B7（2026-09-21）：会话标识 —— 主题切换等若触发重建，此值会变化（放在 Logs.init 之后，否则会被丢弃 ✗）
        Logs.add("UI", "onCreate session=" + java.util.UUID.randomUUID().toString().substring(0, 8));
        Stats.start(this);        // 匿名心跳（使用人数/在线人数统计）
        Logs.add("APP", "启动 v" + "1.72");
        initChrome();
        setContentView(root);
        applyChromeToViews();
        compactTopBar();   // 车机（宽屏）压缩顶部按钮，腾出内容高度
        hideTopBarWide();  // 车机：顶部菜单已进侧边栏 → 隐藏原生工具条

        // 2026-09-24 用户要求：改成「**每 5 次打开提示一次**赞赏」——
        // 原来只在首次打开弹一次（rewardShown），会和其他提示叠在一起；现在按打开次数计数，
        // 第 5/10/15… 次才提示一次（顺带去掉了原来那个「首次打开」弹窗 ✓）
        try {
            android.content.SharedPreferences sp0 = getSharedPreferences("c3shell", MODE_PRIVATE);
            int opens = sp0.getInt("appOpens", 0) + 1;
            sp0.edit().putInt("appOpens", opens).commit();
            if (opens % 5 == 0) {
                root.postDelayed(new Runnable() { public void run() { showReward(); } }, 1600);
            }
        } catch (Throwable ignore) { }
        load();
        // 2026-09-22 方案A：不再单独删原生版本号 —— 车机模式整行（含版本号）隐藏，
        // 手机/平板显示原生版本号；网页侧只在车机模式画 #sideVer，两边不会重复 ✓
        enableTls12();
        try { lastCarMode = carMode(); } catch (Throwable ignore) { }
        if (carMode()) { try { applyModeToBar("car"); } catch (Throwable ignore) { } }   // 含底部输入条左缩 ✓

        // 语音提醒服务（2026-09-20）：默认开，可在「设置」里关
        // 2026-09-21 还债：启动决策与失败原因**都写 APP 日志**（此前 catch 静默吞掉 ✗ → 语音长期不出声却无人知道）
        boolean voiceOn = prefs.getBoolean("voice", true);
        if (voiceOn) {
            try { startService(new Intent(this, SpeechService.class)); Logs.add("VOICE", "启动语音服务（voice=true）"); }
            catch (Throwable t) { Logs.add("VOICE", "启动语音服务失败: " + t); }
        } else {
            Logs.add("VOICE", "未启动语音服务（voice=false，可在设置里打开）");
        }
    }

    // ---------------------------------------------------------------- 顶栏

    private View buildBar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setBackgroundColor(C_BAR);
        topBarInner = bar;                 // 2026-09-22：它也是"建得比 initChrome 早"的那批，需要重刷
        bar.setPadding(dp(6), dp(5), dp(6), dp(5));

        bConsole = tab("SSH 控制台", P_CONSOLE);
        bDiag = tab("运行曲线", P_DIAG);   // 2026-09-24 R110（用户要求）：原名「转向诊断」改为「运行曲线」✓
        bar.addView(bConsole);
        bar.addView(bDiag);
        /* 2026-09-24 R103（用户要求）：参数从「转向诊断」的二级页签提升为一级菜单「参数设置」 ✓
           跳转用诊断页既有的 pane=params 深链机制 ✓（= 参数那个页签）*/
                /* 2026-09-24 R104（用户反馈：平板手机模式下菜单没改）：
           手机/平板的一级菜单 = 这条原生顶栏 → 「软件设置」也必须在这里有一级入口 ✓
           （原来它只以"控制台的二级页签"形式存在；R104 把二级里的重复项去掉后，平板上就没入口了 ✗）
           跳转用 tab=settings：页面里的 settings 页签按钮虽然被 CSS 隐藏，但 click() 依然生效 ✓ */
        final Lic _lic = new Lic(this);                  // 2026-10-03：原生一级菜单跟随「开发者功能开关」
        if (_lic.uiFeatOn("settings")) 
        if (_lic.uiFeatOn("cast")) 
                        if (_lic.uiFeatOn("uiset"))

bar.addView(actionK("参数设置", "params", new View.OnClickListener() {
            public void onClick(View v) { curTab = "params"; paintTabs();  page = P_DIAG; pendingQuery = "pane=params"; pendingHash = ""; load(); }
        }));

if (_lic.uiFeatOn("cast")) bar.addView(actionK("投屏", "cast", new View.OnClickListener() {
            public void onClick(View v) { curTab = "cast"; paintTabs(); page = P_CONSOLE; pendingQuery = "tab=cast"; pendingHash = ""; load(); }
        }));

if (_lic.uiFeatOn("ai")) bar.addView(actionK("AI 分析", "ai", new View.OnClickListener() {
            public void onClick(View v) { curTab = "ai"; paintTabs(); page = P_CONSOLE; pendingQuery = "tab=aian"; pendingHash = ""; load(); }
        }));

if (_lic.uiFeatOn("settings")) bar.addView(actionK("软件设置", "settings", new View.OnClickListener() {
            public void onClick(View v) { curTab = "settings"; paintTabs();  page = P_CONSOLE; pendingQuery = "tab=settings"; pendingHash = ""; load(); }
        }));

if (_lic.uiFeatOn("uiset")) bar.addView(actionK("界面设置", "uiset", new View.OnClickListener() {
            public void onClick(View v) { curTab = "uiset"; paintTabs(); page = P_CONSOLE; pendingQuery = "ui=1&tab=uiset"; pendingHash = ""; load(); }
        }));

bar.addView(action("赞赏", new View.OnClickListener() {
            public void onClick(View v) { showReward(); }
        }));

if (_lic.uiFeatOn("logs")) bar.addView(action("软件日志", new View.OnClickListener() {
            public void onClick(View v) { showLogs(); }
        }));

        return bar;
    }

    /** 原生外壳跟随网页主题（2026-09-21 用户反馈：白底主题下顶部仍是黑的）。
     *  网页切到「白底」时会通知 c3shell://theme?light=1 → 重建 Activity 用浅色外壳。 */
    private boolean chromeLight() {
        try { return getSharedPreferences("c3shell", MODE_PRIVATE).getBoolean("chromeLight", false); }
        catch (Throwable e) { return false; }
    }
    /** 递归给容器内所有文字上色（浅色外壳下标题要深色 ✓） */
    private void tintText(android.view.ViewGroup g, int color) {
        try {
            for (int i = 0; i < g.getChildCount(); i++) {
                android.view.View v = g.getChildAt(i);
                if (v instanceof TextView) ((TextView) v).setTextColor(color);
                else if (v instanceof android.view.ViewGroup) tintText((android.view.ViewGroup) v, color);
            }
        } catch (Throwable ignore) { }
    }

    /** 经典主题：白底黑字时原生外壳也变浅色（2026-09-21 用户要求 ✓；只改颜色，**绝不 recreate** ✓） */
    /** 2026-09-22 用户反馈："输入框白色跟选择的主题不搭" → 外壳（顶栏/底栏/输入条）改为跟随页面主题 ✓
     *  判断依据：页面报来的左栏底色亮度（getComputedStyle(nav.tabs) ✓，任何主题都精确 ✓） */
    private boolean darkTheme() {
        try {
            int c = sideColor();
            int r = (c >> 16) & 0xFF, g = (c >> 8) & 0xFF, b = c & 0xFF;
            return (0.299 * r + 0.587 * g + 0.114 * b) < 128;
        } catch (Throwable t) { return false; }
    }
    private boolean themeLight() {
        return !darkTheme();   // 白底 → 浅色外壳；季节主题 → 深色外壳 ✓
    }
    /** 主题色重刷（initChrome 之后调用 ✓）：底部输入栏等原生控件要按主题上色 ✗→✓ */
    private void applyChromeToViews() {
        // 2026-09-22 修：顶栏那一行是在 initChrome() 之前建的，底色拿到的是深色常量 → 白底外壳下留一条黑背景 ✗
        // 2026-09-22 修（用户："输入框左侧有一条黑的"）：这几处底色都是建在 initChrome 之前的深色 ✗
        // 2026-09-22 修（用户："底色跟其他对不上、有色差"）：这里原来刷 C_BG(#F4F6F9 偏灰) ✗，
        // 而输入条/网页背景是 C_BAR(纯白) → 让位处能看到色差。统一用 C_BAR ✓
        try { if (rootView != null) rootView.setBackgroundColor(carMode() ? sideColor() : C_BAR); } catch (Throwable ignore) { }
        try { if (web != null) web.setBackgroundColor(darkTheme() ? 0xFF0E1116 : C_BAR); } catch (Throwable ignore) { }
        try { getWindow().getDecorView().setBackgroundColor(darkTheme() ? 0xFF0E1116 : C_BAR); } catch (Throwable ignore) { }
        try { if (topBarRow != null) topBarRow.setBackgroundColor(C_BAR); } catch (Throwable ignore) { }
        try { if (topBarInner != null) topBarInner.setBackgroundColor(C_BAR); } catch (Throwable ignore) { }
        try { if (topBarRow instanceof android.view.ViewGroup) {
            android.view.ViewGroup g = (android.view.ViewGroup) topBarRow;
            for (int i = 0; i < g.getChildCount(); i++) g.getChildAt(i).setBackgroundColor(C_BAR);
        } } catch (Throwable ignore) { }
        try { if (termBar != null) termBar.setBackgroundColor(C_BAR); } catch (Throwable ignore) { }
        /* 2026-09-24 R108（用户：深色主题下顶部一级菜单按钮底色还是浅的）：
           顶栏按钮是**建栏时**按当时的主题上色的 ✗，只有 控制台/转向诊断 会被 paintTabs() 重刷 ✓
           → 主题一变，其余按钮仍是旧底色（深色主题里留一片浅色 ✗）→ 这里按当前主题整排重刷 ✓
           （随后调用方会再跑 paintTabs()，把选中的那个恢复成蓝底白字 ✓）*/
        try {
            boolean lt0 = themeLight();
            if (topBarInner instanceof android.view.ViewGroup) {
                android.view.ViewGroup g0 = (android.view.ViewGroup) topBarInner;
                for (int i0 = 0; i0 < g0.getChildCount(); i0++) {
                    android.view.View v0 = g0.getChildAt(i0);
                    if (v0 instanceof android.widget.Button) {
                        android.widget.Button b0 = (android.widget.Button) v0;
                        b0.setBackground(rounded(lt0 ? C_IDLE_L : 0xFF1D222B, dp(16)));
                        b0.setTextColor(lt0 ? C_FG_L : C_FG);
                    }
                }
            }
        } catch (Throwable ignore) { }
        try {
            if (topTitle != null) {
                topTitle.setBackgroundColor(C_BAR);
                topTitle.setTextColor(themeLight() ? C_FG_L : C_FG);
            }
        } catch (Throwable ignore) { }
        boolean lt = themeLight();
        try { if (termLbl != null) termLbl.setTextColor(lt ? 0xFF000000 : C_FG); } catch (Throwable ignore) { }   // 「输入」二字：浅色下纯黑 ✓
        try { if (termInput != null) {
            android.graphics.drawable.GradientDrawable gd = new android.graphics.drawable.GradientDrawable();
            gd.setColor(lt ? 0xFFFFFFFF : 0xFF11151B); gd.setCornerRadius(dp(6));
            gd.setStroke(dp(1), lt ? 0xFF9AA4B2 : 0xFF3A4353);
            termInput.setBackground(gd);
            termInput.setTextColor(lt ? 0xFF000000 : C_FG);
        } } catch (Throwable ignore) { }
        try {   // 「发送」保持蓝色主操作 ✓；回车/Tab/^C 三个按钮跟随主题 ✓
            if (termBar instanceof android.view.ViewGroup) {
                android.view.ViewGroup g = (android.view.ViewGroup) termBar;
                for (int i = 0; i < g.getChildCount(); i++) {
                    android.view.View v = g.getChildAt(i);
                    if (v instanceof android.widget.Button) {
                        android.widget.Button b = (android.widget.Button) v;
                        if (String.valueOf(b.getText()).indexOf("发送") >= 0) continue;
                        b.setBackground(rounded(lt ? C_IDLE_L : 0xFF1D222B, dp(12)));
                        b.setTextColor(lt ? C_FG_L : C_FG);
                    }
                }
            }
        } catch (Throwable ignore) { }
    }
    private void initChrome() {
        if (themeLight()) {                       // 经典白底：浅色外壳（顶栏/工具栏/底栏一并变浅 ✓）
            C_BG  = 0xFFF4F6F9;
            C_BAR = 0xFFFFFFFF;
            C_FG  = 0xFF1B1F24;
            try {
                getWindow().getDecorView().setSystemUiVisibility(8192);   // 状态栏图标转深色 ✓
                try { android.view.Window.class.getMethod("setStatusBarColor", int.class).invoke(getWindow(), C_BAR); } catch (Throwable ignore) { }
                try { android.view.Window.class.getMethod("setNavigationBarColor", int.class).invoke(getWindow(), C_BG); } catch (Throwable ignore) { }
            } catch (Throwable ignore) { }
            try { if (getActionBar() != null) { getActionBar().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(C_BAR)); } } catch (Throwable ignore) { }
            // ★ 白底上标题必须转深色（否则白字白底看不见 ✗ —— 用户此前就报过这个坑 ✓）
            // ★ 白底上标题必须转深色：直接遍历 ActionBar 视图树给所有文字上色（按 id 取名在某些 ROM 取不到 ✗）
            try {
                int abid = getResources().getIdentifier("action_bar", "id", "android");
                android.view.View ab = (abid != 0) ? findViewById(abid) : null;
                if (ab instanceof android.view.ViewGroup) tintText((android.view.ViewGroup) ab, C_FG);
                else { android.view.View t2 = findViewById(android.R.id.title); if (t2 instanceof TextView) ((TextView) t2).setTextColor(C_FG); }
            } catch (Throwable ignore) { }
            Logs.add("UI", "外壳=浅色（经典主题 ✓）");
        } else {                                  // 深色（默认）
            C_BG  = 0xFF0E1116;
            C_BAR = 0xFF161B22;
            C_FG  = 0xFFE6EDF3;
            try { getWindow().getDecorView().setSystemUiVisibility(0); } catch (Throwable ignore) { }
            Logs.add("UI", "外壳=深色");
        }
    }
    private void setChromeLight(final boolean light) {
        // 方案A：不再改原生外壳（仅记录，便于排查）
        Logs.add("UI", "网页主题=" + (light ? "白底" : "深色") + "（外壳固定深色）");
    }

    /** 车机（宽屏）：顶部菜单已进侧边栏 → 隐藏原生工具条（2026-09-21 用户要求） */
    private void hideTopBarWide() {
        try {
            if (!carMode()) return;
            android.view.ViewGroup root = (android.view.ViewGroup) findViewById(android.R.id.content);
            if (root == null) return;
            for (int i = 0; i < root.getChildCount(); i++) hideTopBarIn(root.getChildAt(i), 0);
            Logs.add("UI", "hideTopBarWide done");
        } catch (Throwable e) { Logs.add("UI", "hideTopBarWide 失败: " + e); }
    }
    /** 把某个 View 所在的"整行"（root 的直接子节点）隐藏起来 */
    private void hideWholeRow(android.view.View v) {
        try {
            android.view.ViewGroup root = (android.view.ViewGroup) findViewById(android.R.id.content);
            if (root == null) { v.setVisibility(android.view.View.GONE); return; }
            android.view.View child = v;
            while (child.getParent() != null && child.getParent() != root) {
                child = (android.view.View) child.getParent();
            }
            child.setVisibility(android.view.View.GONE);
        } catch (Throwable e) { v.setVisibility(android.view.View.GONE); }
    }

    /** 判断 root 子树里是否包含 target（用于避免误隐藏含 WebView 的容器） */
    private boolean containsView(android.view.View root, android.view.View target) {
        if (root == null || target == null) return false;
        if (root == target) return true;
        if (root instanceof android.view.ViewGroup) {
            android.view.ViewGroup g = (android.view.ViewGroup) root;
            for (int i = 0; i < g.getChildCount(); i++) if (containsView(g.getChildAt(i), target)) return true;
        }
        return false;
    }

    private void hideTopBarIn(android.view.View v, int depth) {
        if (depth > 12 || v == null) return;                      // 去掉浅层限制（之前 3 层，漏掉了顶栏里的版本号）
        if (v instanceof android.widget.HorizontalScrollView) {
            // 隐藏"整行容器"（工具条那一行，含版本号），但**必须确认它不含 WebView**（v2.30 误伤就是这么来的）
            android.view.View p = (android.view.View) v.getParent();
            if (p != null && !containsView(p, web)) { p.setVisibility(android.view.View.GONE); Logs.add("UI", "hideToolbarRow(整行)"); }
            else { v.setVisibility(android.view.View.GONE); Logs.add("UI", "hideToolbarRow(仅工具条)"); }
            return;
        }
        if (v instanceof TextView) {                              // 原生版本号（vX.Y）→ 隐藏
            String t = String.valueOf(((TextView) v).getText()).trim();
            if (t.matches("v?\\d+(\\.\\d+)+")) {
                try { android.view.ViewParent pp = v.getParent(); if (pp instanceof android.view.ViewGroup) ((android.view.ViewGroup) pp).removeView(v); } catch (Throwable ignore) { }
            }
        }
        if (v instanceof android.view.ViewGroup) {
            android.view.ViewGroup g = (android.view.ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) hideTopBarIn(g.getChildAt(i), depth + 1);
        }
    }

    /** 车机模式：底部原生输入条要让开左栏（网页左栏 142px + body padding-left 150px
     *  → 1 CSS px = 1dp，所以左内缩 150dp）✓ 2026-09-22 用户反馈"输入框会占用到侧边栏" */
    /** 2026-09-22 用户反馈："终端输入框覆盖了侧边栏，虽然看不见"
     *  真因：车机模式下底部输入条让位出来的那块（左侧 150dp）露出的是"根容器"底色 = 白 ✗，
     *  而页面左栏是 #F4F6F9 系 → 左下角看起来像被啃掉一角 ✓
     *  修法：车机模式下把根容器底色改成与页面左栏一致 ✓ */
    private static final int C_SIDEBAR_L = 0xFFF4F6F9;
    private int sideColor() {
        try { return getSharedPreferences("c3shell", MODE_PRIVATE).getInt("sideColor", C_SIDEBAR_L); }
        catch (Throwable t) { return C_SIDEBAR_L; }
    }
    private void applyRootTint(boolean car) {
        try { if (rootView != null) rootView.setBackgroundColor(car ? sideColor() : C_BAR); } catch (Throwable ignore) { }
    }

    private void applyTermBarInset(boolean car) {
        try {
            if (termBar == null) return;
            android.view.ViewGroup.LayoutParams lp = termBar.getLayoutParams();
            if (lp instanceof LinearLayout.LayoutParams) {
                ((LinearLayout.LayoutParams) lp).leftMargin = car ? dp(150) : 0;
                termBar.setLayoutParams(lp);
            }
        } catch (Throwable ignore) { }
    }

    /** 显示模式 → 原生顶栏整行显隐（2026-09-22 方案A；不重建 Activity） */
    private void applyModeToBar(String m) {
        try {
            if (topBarRow == null) return;
            boolean car = "car".equals(m);
            topBarRow.setVisibility(car ? View.GONE : View.VISIBLE);
            applyTermBarInset(car);           // 车机：底部输入条让开左栏 ✓
            applyRootTint(car);               // 车机：让位处的底色跟页面左栏一致 ✓
            Logs.add("UI", "顶栏" + (car ? "隐藏" : "显示") + "（显示模式=" + m + "）");
        } catch (Throwable ignore) { }
    }

    /** 自动模式阈值（dp）：平板半屏约 677dp → 手机/平板；整屏约 1363dp、车机 1920dp → 车机 ✓ */
    private static final int AUTO_CAR_MIN_DP = 900;
    private boolean lastCarMode = false;

    private int pageWidthDp() {
        try {
            android.util.DisplayMetrics m = getResources().getDisplayMetrics();
            return (int) (m.widthPixels / m.density);
        } catch (Throwable t) { return 0; }
    }

    /** 尺寸/方向变化：自动模式下重新判断，变了就切 + 重载页面（2026-09-22 用户要求） */
    @Override
    public void onConfigurationChanged(android.content.res.Configuration cfg) {
        super.onConfigurationChanged(cfg);
        try {
            if (!"auto".equals(getSharedPreferences("c3shell", MODE_PRIVATE).getString("displayMode", "auto"))) return;
            boolean car = carMode();
            if (car == lastCarMode) return;
            lastCarMode = car;
            applyModeToBar(car ? "car" : "tablet");
            load();
            toast(car ? "宽度够大 → 已自动切到车机模式" : "宽度较小 → 已自动切回手机/平板模式");
        } catch (Throwable ignore) { }
    }

    /** 显式显示模式（2026-09-21 还债 A4；2026-09-22 起支持 car/tablet/auto） */
    private boolean carMode() {
        /* 2026-09-22 方案A：手机/平板 = 一级菜单在原生顶栏（1.79 原始布局，网页只留二级页签）；
           车机 = 原生顶栏隐藏、一级/二级都在网页左栏。默认 tablet；车机在「设置→界面→显示模式」切一次即记住。
           不再按宽度猜 —— 平板 3408px 会被误判成车机（用户反馈过）。 */
        try {
            String dm = getSharedPreferences("c3shell", MODE_PRIVATE).getString("displayMode", "auto");
            if ("car".equals(dm)) return true;
            if (!"auto".equals(dm)) return false;
            return pageWidthDp() >= AUTO_CAR_MIN_DP;      // 2026-09-22 用户要求：自动模式 = 宽度超过阈值 → 车机模式 ✓
        } catch (Throwable ignore) { }
        return false;
    }

    /** B6 版本号单一来源（2026-09-21）：把原生顶栏里的版本号控件**从布局移除**（不再"藏"✗），
     *  版本只由页面侧栏 #sideVer 显示（来源＝manifest versionName，经 __APPVER__ 模板下发）。 */
    private void removeNativeVersion() {
        try {
            android.view.ViewGroup root = (android.view.ViewGroup) findViewById(android.R.id.content);
            if (root == null) return;
            removeVerIn(root, 0);
        } catch (Throwable e) { Logs.add("UI", "removeNativeVersion 失败: " + e); }
    }
    private void removeVerIn(android.view.View v, int depth) {
        if (depth > 12 || v == null) return;
        if (v instanceof TextView) {
            String t = String.valueOf(((TextView) v).getText()).trim();
            if (t.matches("v?\\d+(\\.\\d+)+")) {
                try {
                    android.view.ViewParent p = v.getParent();
                    if (p instanceof android.view.ViewGroup) ((android.view.ViewGroup) p).removeView(v);
                    Logs.add("UI", "removeNativeVer " + t);
                } catch (Throwable ignore) { }
                return;
            }
        }
        if (v instanceof android.view.ViewGroup) {
            android.view.ViewGroup g = (android.view.ViewGroup) v;
            for (int i = g.getChildCount() - 1; i >= 0; i--) removeVerIn(g.getChildAt(i), depth + 1);
        }
    }

    /** 车机（宽屏）：压缩顶部工具条按钮（2026-09-21 用户反馈顶部占位太多、字体太大） */
    private void compactTopBar() {
        try {
            if (!carMode()) return;
            android.view.ViewGroup root = (android.view.ViewGroup) findViewById(android.R.id.content);
            if (root == null) return;
            for (int i = 0; i < root.getChildCount(); i++) {
                android.view.View v = root.getChildAt(i);
                if (v instanceof android.view.ViewGroup) shrinkButtons((android.view.ViewGroup) v, 0);
                if (v instanceof android.view.ViewGroup) {                    // 顶栏容器里的版本号也要藏
                    android.view.ViewGroup g = (android.view.ViewGroup) v;
                    for (int j = 0; j < g.getChildCount(); j++) {
                        android.view.View c = g.getChildAt(j);
                        if (c instanceof TextView) {
                            String t2 = String.valueOf(((TextView) c).getText()).trim();
                            if (t2.matches("v\\d+(\\.\\d+)+")) { try { android.view.ViewParent pp2 = c.getParent(); if (pp2 instanceof android.view.ViewGroup) ((android.view.ViewGroup) pp2).removeView(c); } catch (Throwable ignore) { } }
                        }
                    }
                }
            }
        } catch (Throwable e) { Logs.add("UI", "compactTopBar 失败: " + e); }
    }
    private void shrinkButtons(android.view.ViewGroup g, int depth) {

        if (depth > 3) return;
        for (int i = 0; i < g.getChildCount(); i++) {
            android.view.View v = g.getChildAt(i);
            if (v instanceof Button) {
                ((Button) v).setTextSize(12);
                v.setPadding(dp(7), dp(2), dp(7), dp(2));
                android.view.ViewGroup.LayoutParams lp = v.getLayoutParams();
                if (lp != null) { lp.height = dp(32); v.setLayoutParams(lp); }
            } else if (v instanceof android.view.ViewGroup) {
                shrinkButtons((android.view.ViewGroup) v, depth + 1);
            }
        }
    }

    /** APP 内日志：直接看现场（请求/耗时/页面 JS 报错） */
    private void showLogs() {
        try {
            String t = Logs.dump(65536);
            android.widget.ScrollView sv = new android.widget.ScrollView(this);
            TextView tv = new TextView(this);
            tv.setTextSize(10.5f);
            tv.setTextIsSelectable(true);
            tv.setTypeface(android.graphics.Typeface.MONOSPACE);
            tv.setText(t.length() == 0 ? "（暂无日志）" : t);
            sv.addView(tv, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            new AlertDialog.Builder(this).setTitle("APP 日志（最近 64KB）").setView(sv)
                .setPositiveButton("关闭", null)
                .setNeutralButton("清空", new android.content.DialogInterface.OnClickListener() {
                    public void onClick(android.content.DialogInterface d, int w) { Logs.clear(); toast("日志已清空"); }
                }).show();
        } catch (Throwable e) { toast("日志读取失败：" + e); }
    }

    /** 关于 / 赞赏作者（2026-09-21 用户要求）
     *  2026-09-24 R98（用户要求）：加「软件介绍」+ 作者信息（松间叙白 / 微信 lwms1020，点击可复制）✓
     *  入口：原生顶栏「赞赏」/ 车机左栏「赞赏」/ diag 页 —— 都走 c3shell://reward → 这里 ✓ */
    private void showReward() {
        try {
            LinearLayout box = new LinearLayout(this);
            box.setOrientation(LinearLayout.VERTICAL);
            int pp = dp(14);
            box.setPadding(pp, pp, pp, dp(6));
            String ver = "";
            try { ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Throwable ignore) { }

            /* ① 软件介绍 */
            TextView intro = new TextView(this);
            intro.setText(introText(ver));
            intro.setTextSize(12.5f);
            intro.setTextColor(C_FG);
            intro.setLineSpacing(dp(2), 1f);
            box.addView(intro);

            /* ② 作者信息（点一下复制微信号 ✓） */
            TextView au = new TextView(this);
            au.setText("作者：松间叙白\n微信：lwms1020　（点这里复制）");
            au.setTextSize(15f);
            au.setTypeface(au.getTypeface(), android.graphics.Typeface.BOLD);
            au.setTextColor(C_FG);
            au.setPadding(0, dp(12), 0, dp(8));
            au.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    try {
                        android.content.ClipboardManager cm = (android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                        cm.setPrimaryClip(android.content.ClipData.newPlainText("微信号", "lwms1020"));
                        toast("微信号已复制：lwms1020");
                    } catch (Throwable e) { toast("微信号：lwms1020"); }
                }
            });
            box.addView(au);

            /* ③ 赞赏码（图挂了也不影响上面的信息 ✓） */
            try {
                android.graphics.Bitmap bm = android.graphics.BitmapFactory.decodeStream(Sec.open(this, "reward.jpg"));
                if (bm != null) {
                    TextView cap = new TextView(this);
                    cap.setText("觉得这个 APP 有用的话，可以赞赏一下作者 🙏\n（有问题或想要的功能也可以直接说，我会继续改）");
                    cap.setTextSize(13f);
                    cap.setTextColor(C_FG);
                    cap.setPadding(0, 0, 0, dp(8));
                    box.addView(cap);
                    android.widget.ImageView iv = new android.widget.ImageView(this);
                    iv.setImageBitmap(bm);
                    iv.setAdjustViewBounds(true);
                    iv.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
                    box.addView(iv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(300)));
                }
            } catch (Throwable ignore) { }

            /* ④ 我已赞赏（2026-09-24 用户要求）：填金额 → 联网登记给作者。
               2026-09-24 再改（用户要求）：① 输入框里**不再写「需 >20」**；
                                          ② **金额 >20 就先把弹窗关掉**，上报放后台做，结果只用轻提示 ✓ */
            final AlertDialog[] dlgBox = new AlertDialog[1];
            TextView tip2 = new TextView(this);
            tip2.setText("已经赞赏过？填一下金额，点「我已赞赏」告诉我一声 🙏");
            tip2.setTextSize(13f);
            tip2.setTextColor(C_FG);
            tip2.setPadding(0, dp(10), 0, dp(4));
            box.addView(tip2);
            LinearLayout amtRow = new LinearLayout(this);
            amtRow.setOrientation(LinearLayout.HORIZONTAL);
            final EditText amtIn = new EditText(this);
            amtIn.setHint("赞赏金额（元）");
            amtIn.setTextSize(14f);
            amtIn.setInputType(android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL);
            amtRow.addView(amtIn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            final Button amtBtn = new Button(this);
            amtBtn.setText("我已赞赏");
            amtRow.addView(amtBtn);
            box.addView(amtRow);
            amtBtn.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    String s = amtIn.getText() == null ? "" : amtIn.getText().toString().trim();
                    double vv = -1;
                    try { vv = Double.parseDouble(s); } catch (Throwable ignore) { }
                    if (vv <= 20) { toast("请输入大于 20 的赞赏金额 🙏"); return; }   // 规则保留，只是不再预先写在输入框里 ✓
                    final String amount = s;
                    /* 金额 >20 → **先把弹窗关掉**（服务器没配置也不会把人卡在弹窗里 ✗），上报放后台 ✓ */
                    if (dlgBox[0] != null) { try { dlgBox[0].dismiss(); } catch (Throwable ignore) { } }
                    new Thread(new Runnable() { public void run() {
                        final String r = new Lic(MainActivity.this).appreciate(amount);
                        boolean ok = r != null && r.indexOf("\"ok\":true") >= 0;
                        String em = "";
                        try {
                            int i2 = r.indexOf("\"message\":\"");
                            if (i2 >= 0) { int j2 = r.indexOf('"', i2 + 11); if (j2 > i2) em = r.substring(i2 + 11, j2); }
                        } catch (Throwable ignore) { }
                        final String msg = ok ? ("已记下：赞赏 " + amount + " 元，谢谢支持 🙏")
                                              : ("没发出去：" + (em.length() > 0 ? em : "服务器未响应"));
                        runOnUiThread(new Runnable() { public void run() { toast(msg); } });   // 只有轻提示，不再弹第二个窗 ✓
                    } }).start();
                }
            });

            android.widget.ScrollView sv = new android.widget.ScrollView(this);
            sv.addView(box);
            dlgBox[0] = new AlertDialog.Builder(this).setTitle("关于 c3shell · 赞赏作者").setView(sv)
                .setPositiveButton("关闭", null).create();
            dlgBox[0].show();
        } catch (Throwable e) { toast("打开失败：" + e.getClass().getSimpleName()); }
    }

    /** 软件介绍文本 */
    private String introText(String ver) {
        return "c3shell · 车机远程控制台　v" + ver + "\n" + "\n"
            + "在平板 / 手机上远程查看与控制 openpilot 车机（comma 3X / C3 等）。" + "\n" + "\n"
            + "主要功能：" + "\n"
            + "· 投屏：车机实时画面 + 悬浮小窗，可触控反控车机、熄屏 / 亮屏" + "\n"
            + "· 状态与参数：设备状态、参数表查看与下发、运行曲线" + "\n"
            + "· 终端 / 文件 / 实时曲线" + "\n"
            + "· AI 分析：扫描行车接管日志（qlog）出结论，也可交给 AI 深挖" + "\n"
            + "· 运维：常用脚本、备份、刷写；语音提醒（辅助驾驶状态变化时播报）" + "\n"
            + "· 连接：APP 内置 HTTP 服务 + SSH 直连车机（车机端脚本在 /data/openpilot/.dsh）"
            /* 2026-09-24 离线签名卡密：激活后这里显示「已激活」，体验倒计时自动失效 ✓ */
            + (TrialInfo.ON ? (Trial.licensed(this)
                ? ("\n" + "\n" + "【已激活】正式授权，不受体验期限制 ✓")
                : ("\n" + "\n" + "【体验版】剩余 " + Trial.leftText(this) + "　体验期 " + Trial.windowText() + " ✓")) : "");
    }
    /** 圆角背景（HyperOS 风：不再方正） */
    private android.graphics.drawable.GradientDrawable rounded(int color, float r) {
        android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(r);
        return g;
    }

    private String curTab = "";                 /* 2026-10-05：页面当前页签（用于顶部菜单高亮）*/

    /** 带"按下反馈"的背景（用户反馈：顶部菜单点了没反应，只有控制台/运行曲线有高亮） */
    private android.graphics.drawable.Drawable pressSel(int bg) {
        int press = themeLight() ? 0xFFD8E2F3 : 0xFF33405A;
        android.graphics.drawable.StateListDrawable d = new android.graphics.drawable.StateListDrawable();
        d.addState(new int[]{android.R.attr.state_pressed}, rounded(press, dp(16)));
        d.addState(new int[]{}, rounded(bg, dp(16)));
        return d;
    }

    private Button base(String text, int bg) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(12);
        b.setTextColor(themeLight() ? C_FG_L : C_FG);
        b.setBackground(pressSel(bg));
        b.setPadding(dp(14), dp(6), dp(14), dp(6));
        b.setMinWidth(0);
        b.setMinimumWidth(0);
        b.setAllCaps(false);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT);
        lp.rightMargin = dp(6);
        b.setLayoutParams(lp);
        return b;
    }

    private Button tab(String text, final String target) {
        final Button b = base(text, themeLight() ? C_IDLE_L : C_IDLE);
        b.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { switchTo(target); }
        });
        return b;
    }

    private static class KV { Button v; String k; KV(Button v, String k) { this.v = v; this.k = k; } }
    private final java.util.List<KV> barBtns = new java.util.ArrayList<KV>();

    private Button action(String text, View.OnClickListener l) {
        Button b = base(text, themeLight() ? C_IDLE_L : 0xFF1D222B);   // 浅色外壳下用浅底（原来是写死深底 → 黑块）
        b.setTextColor(themeLight() ? C_FG_L : C_FG);
        b.setOnClickListener(l);
        return b;
    }

    /** 记下按钮与页签 key 的对应（用于高亮；key 为空就是纯动作按钮，如赞赏/日志） */
    private Button actionK(String text, String key, View.OnClickListener l) {
        Button b = action(text, l);
        if (key != null && key.length() > 0) barBtns.add(new KV(b, key));
        return b;
    }

    private void paintTabs() {
        int idle = themeLight() ? C_IDLE_L : C_IDLE;
        /* 2026-09-24 R105（用户：手机/平板模式下一级菜单选中是蓝底黑字，看不清）：
           真因 —— base() 把文字设成近黑色（浅色主题 ✓），而这里只改了背景 ✗
           → 选中（蓝底）时文字仍是黑的 ✗。这里连文字颜色一起画：选中＝**白字** ✓ */
        int onFg  = 0xFFFFFFFF;                       /* 蓝底白字 ✓ */
        int offFg = themeLight() ? C_FG_L : C_FG;
        boolean actionOn = curTab != null && curTab.length() > 0 && !"hosts".equals(curTab) && !"charts".equals(curTab);
        if (bConsole != null) {
            boolean on = P_CONSOLE.equals(page) && !actionOn;
            bConsole.setBackground(rounded(on ? C_ACTIVE : idle, dp(16)));
            bConsole.setTextColor(on ? onFg : offFg);
        }
        if (bDiag != null) {
            boolean on = P_DIAG.equals(page) && !actionOn;
            bDiag.setBackground(rounded(on ? C_ACTIVE : idle, dp(16)));
            bDiag.setTextColor(on ? onFg : offFg);
        }
        /* 2026-10-05：一级菜单里那些"动作按钮"（投屏/AI 分析/软件设置/界面设置/参数设置）也跟随高亮 */
        for (int i = 0; i < barBtns.size(); i++) {
            Button b = barBtns.get(i).v;
            String k = barBtns.get(i).k;
            boolean on = k != null && k.length() > 0 && k.equals(curTab);      // 不再限定在控制台页 → 参数设置也能亮 ✓
            b.setBackground(pressSel(on ? C_ACTIVE : idle));
            b.setTextColor(on ? onFg : offFg);
        }
    }

    // ---------------------------------------------------------------- 加载

    private String baseUrl() {
        String host = prefs.getString(K_HOST, DEFAULT_HOST);
        int port = prefs.getInt(K_PORT, DEFAULT_PORT);
        if (EMBED_PORT > 0) return "http://127.0.0.1:" + EMBED_PORT;   // 独立模式：用 APP 内置服务
        return "http://" + host + ":" + port;
    }

    private void switchTo(String target) {
        page = target;
        curTab = "";                 // 2026-10-05：切页面（控制台/运行曲线）时清掉动作高亮，避免两个同时亮
        paintTabs();
        load();
    }

    private void load() {
        failed = false;
        paintTabs();
        // 2026-09-22 方案A：把显示模式与「在 APP 内」标记带给网页（网页据此决定要不要自建一级菜单）
        String _sep = page != null && page.indexOf('?') >= 0 ? "&" : "?";
        String _extra = (pendingQuery == null || pendingQuery.length() == 0) ? "" : ("&" + pendingQuery);
        String _hash = (pendingHash == null) ? "" : pendingHash;
        String _dm = "tablet";
        try { _dm = getSharedPreferences("c3shell", MODE_PRIVATE).getString("displayMode", "auto"); } catch (Throwable ignore) { }
        String _ver = "";
        try { _ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        pendingUrl = baseUrl() + page + _sep + "layout=" + (carMode() ? "car" : "tablet") + "&dm=" + _dm
                   + (lowEnd() ? "&low=1" : "") + "&v=" + _ver + "&inapp=1"
                   // 2026-09-24 体验版：把体验期起止带给页面（右上角 5 天倒计时）✓
                   + (TrialInfo.ON ? ("&trial=1&ts=" + TrialInfo.START + "&te=" + TrialInfo.END) : "")
                   + _extra + _hash;
        pendingQuery = ""; pendingHash = "";          // 用完即清，避免污染后续导航 ✓
        web.loadUrl(pendingUrl);
    }

    private void showErrorPage(String url, String description, int code) {
        StringBuilder h = new StringBuilder();
        h.append("<!DOCTYPE html><html><head><meta charset=\"utf-8\">")
         .append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
         .append("<style>body{margin:0;padding:22px;background:#0e1116;color:#e6edf3;")
         .append("font:14px/1.7 -apple-system,Roboto,sans-serif}h1{font-size:16px;margin:0 0 12px}")
         .append("code,pre{background:#161b22;border:1px solid #232a34;border-radius:6px;")
         .append("padding:2px 6px;color:#e8c400;font-size:12.5px}pre{padding:10px;overflow:auto}")
         .append(".k{color:#8b949e}.ok{color:#39d353}</style></head><body>")
         .append("<h1>连不上连接器服务</h1>")
         .append("<p class=\"k\">目标：</p><pre>").append(esc(url)).append("</pre>")
         .append("<p class=\"k\">原因：").append(esc(description))
         .append("（code ").append(code).append("）</p>")
         .append("<p>这个壳只负责显示，页面由设备上的 <code>dsh-ssh-connector</code> 独立服务提供。")
         .append("它现在没在监听，所以这里是空的。</p>")
         .append("<p><b>如果这是在手机上：</b>连接器跑在<b>平板</b>上，手机上的 127.0.0.1 是手机自己。")
         .append("点顶栏 <b>设置</b> → <b>自动查找连接器</b>（扫局域网），或手动把主机填成平板的 IP（例如 192.168.31.153）。</p>")
         .append("<p><b>如果这是在平板上（连接器本机）：</b></p><pre>cd /storage/emulated/0/openpilot/dsh-ssh-connector\n")
         .append("node bin/serve.mjs</pre>")
         .append("<p>起来之后点顶栏 <b>刷新</b> 即可；换了地址点 <b>设置</b>。</p>")
         .append("<p class=\"ok\">提示：也可以点顶栏 <b>DSH</b> 打开 DSH 应用，在它的终端里起服务。</p>")
         .append("</body></html>");
        web.loadDataWithBaseURL(null, h.toString(), "text/html", "utf-8", null);
    }

    private static String esc(String s) {
        if (s == null) return "";
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    // ---------------------------------------------------------------- 设置

    private void showSettings() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(8), dp(16), dp(4));

        TextView th = new TextView(this);
        th.setText("工具（连接与配置已移到页面里：主机页管地址/密钥，设置页管 AI·语音·界面）");
        th.setTextSize(12);
        th.setTextColor(C_DIM);
        box.addView(th);

        Button scanBtn = new Button(this);
        scanBtn.setText("扫描局域网找 C3 设备（SSH 22 端口）");
        scanBtn.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { scanC3Devices(); }
        });
        box.addView(scanBtn);


        String ver = "";
        try { ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Throwable ignore) { }
        TextView tv = new TextView(this);
        tv.setText("C3 控制台 v" + ver + "（独立版 · 内置 SSH）");
        tv.setTextSize(12);
        tv.setTextColor(C_DIM);
        box.addView(tv);

        new AlertDialog.Builder(this)
                .setTitle("设备查找")
                .setView(box)
                .setPositiveButton("关闭", null)
                .setNeutralButton("系统浏览器", new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface d, int w) { openExternal(); }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void openExternal() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(baseUrl() + page)));
        } catch (Throwable e) {
            toast("没有可用的浏览器");
        }
    }

    /** 扫局域网找连接器：本机所在 /24 网段逐个试 3081 端口（并行，约 3~6 秒）。 */
    private void findConnector() {
        toast("正在扫描局域网里的连接器…");
        new Thread(new Runnable() { public void run() {
            String found = null;
            try {
                java.util.List<String> pres = new java.util.ArrayList<String>();
                java.util.Enumeration<java.net.NetworkInterface> nis = java.net.NetworkInterface.getNetworkInterfaces();
                while (nis.hasMoreElements()) {
                    java.net.NetworkInterface ni = nis.nextElement();
                    if (ni == null || !ni.isUp() || ni.isLoopback()) continue;
                    java.util.Enumeration<java.net.InetAddress> as = ni.getInetAddresses();
                    while (as.hasMoreElements()) {
                        java.net.InetAddress a = as.nextElement();
                        if (!(a instanceof java.net.Inet4Address)) continue;
                        byte[] b = a.getAddress();
                        pres.add((b[0] & 0xff) + "." + (b[1] & 0xff) + "." + (b[2] & 0xff));
                    }
                }
                for (int pi = 0; pi < pres.size() && found == null; pi++) {
                    final String pre = pres.get(pi);
                    final java.util.concurrent.atomic.AtomicReference<String> hit =
                            new java.util.concurrent.atomic.AtomicReference<String>();
                    java.util.concurrent.ExecutorService ex = java.util.concurrent.Executors.newFixedThreadPool(32);
                    for (int i = 1; i <= 254 && hit.get() == null; i++) {
                        final String ip = pre + "." + i;
                        ex.submit(new Runnable() { public void run() {
                            if (hit.get() != null) return;
                            try {
                                java.net.Socket so = new java.net.Socket();
                                so.connect(new java.net.InetSocketAddress(ip, DEFAULT_PORT), 300);
                                so.close();
                                if (hit.get() == null) {
                                    java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL("http://" + ip + ":" + DEFAULT_PORT + "/api/voice/state").openConnection();
                                    c.setConnectTimeout(600); c.setReadTimeout(800);
                                    int code = c.getResponseCode();
                                    c.disconnect();
                                    if (code == 200 || code == 401) hit.compareAndSet(null, ip);
                                }
                            } catch (Throwable ignore) { }
                        } });
                    }
                    ex.shutdown();
                    try { ex.awaitTermination(6, java.util.concurrent.TimeUnit.SECONDS); } catch (Throwable ignore) { }
                    if (hit.get() != null) found = hit.get();
                }
            } catch (Throwable ignore) { }
            final String f = found;
            runOnUiThread(new Runnable() { public void run() {
                if (f != null) {
                    prefs.edit().putString(K_HOST, f).putInt(K_PORT, DEFAULT_PORT).apply();
                    toast("找到连接器：" + f + "，正在加载");
                    load();
                } else {
                    toast("没找到。请确认：手机与平板在同一 Wi-Fi，且平板上的连接器在运行");
                }
            } });
        } }).start();
    }

    private static final int REQ_PICK_KEY = 4711;
    private static final int REQ_PICK_CSV = 4718;   // 参数页「导入并写入」选 CSV
    private static final int REQ_PICK_DIR = 4719;   // 导出 CSV 的目录（系统目录选择器）
    private static final int REQ_PICK_PKG = 4712;
    private String pendingPkgNote = "";

    /** 点终端黑区 → 聚焦底部输入条并弹出键盘（让"点终端就能打字"成立） */
    private void focusTermInput() {
        try {
            termInput.requestFocus();
            android.view.inputmethod.InputMethodManager imm =
                (android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (imm != null) imm.showSoftInput(termInput, 0);
            toast("请在底部输入条打字，按「发送」或 ↵");
        } catch (Throwable t) { toast("聚焦输入条失败，请直接点底部输入框"); }
    }

    /** 选择 sh 更新包：系统文件管理器 → 存进 APP 的更新包库 */
    private void startPickPkg() {
        // 备注抓取需要 evaluateJavascript（编译桩里没有）→ 先跳过，选进来的包备注为空
        try {
            Intent i = new Intent("android.intent.action.OPEN_DOCUMENT");
            i.addCategory("android.intent.category.OPENABLE");
            i.setType("*/*");
            startActivityForResult(i, REQ_PICK_PKG);
        } catch (Throwable t) { toast("这台设备没有可用的文件管理器"); }
    }

    /** 2026-09-22：选「导出 CSV」的目录（系统目录选择器；授权持久化，之后一直用它） */
    private void startPickSaveDir() {
        try {
            Intent i = new Intent("android.intent.action.OPEN_DOCUMENT_TREE");
            startActivityForResult(i, REQ_PICK_DIR);
        } catch (Throwable t) { toast("这台设备不支持选择目录"); }
    }

    /** 2026-09-22：参数页「导入并写入」的 CSV 文件选择（WebView 里 <input type=file> 点不动 ✗ 改走原生） */
    private void startPickCsv() {
        try {
            Intent i = new Intent("android.intent.action.OPEN_DOCUMENT");
            i.addCategory("android.intent.category.OPENABLE");
            i.setType("*/*");
            startActivityForResult(i, REQ_PICK_CSV);
        } catch (Throwable t) { toast("这台设备没有可用的文件管理器"); }
    }

    /** 把原生输入条的内容送进终端会话（走 APP 内部通道，不经过页面） */
    private void sendTermText(String raw) {
        final String text = raw;
        try {
            if (apiRef == null) apiRef = new Api(this);
            apiRef.getClass();   // 保证已初始化
            new Thread(new Runnable() { public void run() {
                try {
                    java.lang.reflect.Method m = Api.class.getMethod("sendToTerm", String.class);
                    Object r = m.invoke(apiRef, text);
                    if (text != null && text.length() > 0 && !text.startsWith("\n") && !text.startsWith("\t")) {
                        runOnUiThread(new Runnable() { public void run() { termInput.setText(""); } });
                    }
                } catch (Throwable t) { android.util.Log.w("C3ShellTerm", "send failed: " + t); }
            } }).start();
        } catch (Throwable t) { android.util.Log.w("C3ShellTerm", "send err: " + t); }
    }

    /** 扫描局域网里开放 22 端口（SSH）的设备，选一个写进当前主机。 */
    /** 雷达扫描动画（2026-09-22 用户要求：点「查找」时要有雷达扫描的动效）
     *  用 Handler 每 33ms 推进角度（≈30fps）——不依赖 ValueAnimator ✓ */
    private class RadarView extends android.view.View {
        private float ang = 0f;
        private boolean running = false;
        private final android.os.Handler hd = new android.os.Handler();
        private final java.util.List<float[]> blips = new java.util.ArrayList<float[]>();
        private final Runnable tick = new Runnable() { public void run() {
            ang = (ang + 6f) % 360f; invalidate();
            if (running) hd.postDelayed(this, 33);
        } };
        public RadarView(android.content.Context c) { super(c); }
        public void start() { if (running) return; running = true; hd.post(tick); }
        public void stop()  { running = false; try { hd.removeCallbacks(tick); } catch (Throwable ignore) { } }
        public void addBlip() { blips.add(new float[]{ (float) (Math.random() * 360), (float) (0.25 + Math.random() * 0.7) }); invalidate(); }
        public void clearBlips() { blips.clear(); invalidate(); }
        protected void onDraw(android.graphics.Canvas cv) {
            try {
                int w = getWidth(), h = getHeight();
                float cx = w / 2f, cy = h / 2f, R = Math.min(w, h) / 2f - dp(6);
                if (R <= 0) return;
                android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
                p.setStyle(android.graphics.Paint.Style.STROKE); p.setStrokeWidth(dp(1));
                p.setColor(0x22000000);
                for (int i = 1; i <= 3; i++) cv.drawCircle(cx, cy, R * i / 3f, p);
                p.setColor(0x15000000);
                cv.drawLine(cx - R, cy, cx + R, cy, p); cv.drawLine(cx, cy - R, cx, cy + R, p);
                double a0 = Math.toRadians(ang);
                for (int t = 0; t < 12; t++) {
                    double a = a0 - t * 0.045;
                    android.graphics.Paint pp = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
                    pp.setStrokeWidth(dp(t == 0 ? 2 : 1));
                    pp.setColor(t == 0 ? 0xFF1F6FEB : (0x08000000 | ((0x33 - t * 3) << 24)));
                    cv.drawLine(cx, cy, cx + (float) (Math.cos(a) * R), cy + (float) (Math.sin(a) * R), pp);
                }
                for (int i = 0; i < blips.size(); i++) {
                    float[] b = blips.get(i);
                    double a = Math.toRadians(b[0]);
                    float x = cx + (float) (Math.cos(a) * R * b[1]), y = cy + (float) (Math.sin(a) * R * b[1]);
                    android.graphics.Paint bp = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
                    bp.setColor(0x331A7F37); cv.drawCircle(x, y, dp(6), bp);
                    bp.setColor(0xFF1A7F37); cv.drawCircle(x, y, dp(3), bp);
                }
            } catch (Throwable ignore) { }
        }
    }

    /** 扫描结果点一下 → 先问是否替换为当前 IP（2026-09-22 用户要求） */
    private void confirmReplaceHost(final String ip) {
        String cur = prefs.getString(K_HOST, "");
        new AlertDialog.Builder(this)
            .setTitle("替换当前 IP")
            .setMessage("把当前主机地址替换为：" + "\n\n" + ip + "\n\n原地址：" + (cur.length() > 0 ? cur : "（未设置）"))
            .setPositiveButton("替换", new DialogInterface.OnClickListener() {
                public void onClick(DialogInterface d, int w) {
                    // ① 写入主机地址（Store 默认主机 + prefs，双写 commit ✓）
                    Store st = new Store(MainActivity.this);
                    Store.Host h = st.defaultHost();
                    if (h == null) { h = new Store.Host(); h.id = "c3"; h.label = "C3 设备"; h.user = "comma"; }
                    h.host = ip; h.port = 22;
                    st.upsertHost(h); st.setDefault(h.id);
                    prefs.edit().putString(K_HOST, ip).putInt(K_PORT, 22).commit();
                    // ② 自动连一次（2026-09-22 用户要求）
                    toast("已把当前 IP 替换为 " + ip + "，正在测试连接…");
                    testHostAndJump(h);
                }
            })
            .setNegativeButton("取消", null)
            .show();
    }

    /* ================= 问题反馈（2026-09-22 用户要求：附图片或日志）=================
       无后端也能用：把「描述 + 最近日志 + 当前界面截图」打包写到系统「下载」目录，
       并可一键「分享文本」（微信/邮件直接发）。将来接后端时，把 saveFeedback 换成上传即可 ✓ */
    /** v1.7 #2：悬浮窗权限（API23+ 用反射，桩里可能没有 ✓）*/
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        try {
            String d = (intent == null || intent.getData() == null) ? null : intent.getData().toString();
            if (d != null && d.startsWith("c3shell://float")) FLOAT_NEWINTENT(d);
        } catch (Throwable ignore) { }
    }
    /** v1.7 #2：外部 am start 也能开关悬浮窗 ✓ */
    private void FLOAT_NEWINTENT(String url) {
        boolean on = url.indexOf("on=1") >= 0;
        try { Logs.add("FLOAT", "intent " + url + " on=" + on + " canOverlay=" + canOverlay()); } catch (Throwable ignore) { }
        if (on) {
            if (!canOverlay()) { toast("请先允许「显示在其他应用上层」✓"); openOverlaySettings(); }
            else { startService(new Intent(this, FloatWin.class)); toast("悬浮窗已开启 ✓"); }
        } else { stopService(new Intent(this, FloatWin.class)); toast("悬浮窗已关闭 ✓"); }
    }
    private boolean canOverlay() {
        try {
            if (android.os.Build.VERSION.SDK_INT < 23) return true;
            java.lang.reflect.Method m = android.provider.Settings.class.getMethod("canDrawOverlays", android.content.Context.class);
            Object r = m.invoke(null, this);
            return r instanceof Boolean && ((Boolean) r).booleanValue();
        } catch (Throwable t) { return true; }
    }
    private void openOverlaySettings() {
        try {
            Intent i = new Intent("android.settings.action.MANAGE_OVERLAY_PERMISSION");
            i.setData(android.net.Uri.parse("package:" + getPackageName()));
            startActivity(i);
        } catch (Throwable t) { toast("请到系统设置 → 应用 → 显示在其他应用上层 里允许本应用 ✓"); }
    }
    private void showFeedback() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(8), dp(16), dp(4));
        TextView th = new TextView(this);
        th.setText("说说遇到的问题。会自动附上：最近日志 + 当前界面截图 + 版本/主机/显示模式");
        th.setTextSize(12); th.setTextColor(C_DIM);
        box.addView(th);
        final EditText et = new EditText(this);
        et.setHint("例如：点开文件页会闪一下；连不上设备（用的是神牛密钥）…");
        et.setMinLines(3); et.setTextSize(13);
        box.addView(et);
        final Lic lic = new Lic(this);
        final boolean hasSrv = lic.endpoint().length() > 0;
        new AlertDialog.Builder(this)
            .setTitle("问题反馈")
            .setView(box)
            /* 2026-09-24：多了「上传到服务器」——发给自己的后端（软件设置 → 激活 / 授权 里填的地址 ✓）
               没配地址 / 上传失败也不慌，下面还有「保存反馈包」，功能不退化 ✓ */
            .setItems(new String[]{
                hasSrv ? "上传到服务器（推荐）" : "上传到服务器（还没配地址）",
                "保存反馈包到「下载」", "分享文本", "取消"
            }, new DialogInterface.OnClickListener() {
                public void onClick(DialogInterface d, int w) {
                    String t = et.getText().toString();
                    if (w == 0) {
                        if (hasSrv) uploadFeedback(t);
                        else toast("还没配校验服务器：软件设置 → 激活 / 授权 → 校验服务器 ✓");
                    } else if (w == 1) saveFeedback(t);
                    else if (w == 2) shareFeedbackText(t);
                }
            })
            .show();
    }

    /** 2026-09-24：把反馈直传到自己的服务器（描述 + 完整日志 + 当前截图）✓
     *  端点从「校验服务器」自动推：https://x/verify → https://x/feedback ✓；失败可改存「下载」✓ */
    private void uploadFeedback(String desc) {
        final Lic lic = new Lic(this);
        if (lic.endpoint().length() == 0) { toast("请先在「软件设置 → 激活 / 授权」里填校验服务器 ✓"); return; }
        toast("正在上传反馈…");
        final String text = feedbackText(desc);
        new Thread(new Runnable() {
            public void run() {
                String logs = "";
                try { logs = Logs.dump(200000); } catch (Throwable ignore) { }
                final String img = shotB64();
                final String r = lic.feedback(text, logs, img);
                final boolean ok = r != null && r.indexOf("\"ok\":true") >= 0;
                final boolean withShot = img.length() > 0;
                runOnUiThread(new Runnable() {
                    public void run() {
                        try {
                            new AlertDialog.Builder(MainActivity.this)
                                .setTitle(ok ? "反馈已上传 ✓" : "上传失败")
                                .setMessage(ok ? ("已收到，谢谢！\n附上了最近日志" + (withShot ? " + 当前截图" : "") + " ✓")
                                               : ("没传上去：\n" + r + "\n\n可以改用「保存反馈包」发给我 ✓"))
                                .setPositiveButton("好", null)
                                .setNeutralButton("改存到「下载」", new DialogInterface.OnClickListener() {
                                    public void onClick(DialogInterface d, int w) { saveFeedback(desc); }
                                })
                                .show();
                        } catch (Throwable t) { toast(ok ? "反馈已上传 ✓" : "上传失败"); }
                    }
                });
            }
        }).start();
    }
    /** 当前界面 → base64（JPEG 压缩，控制体积；失败返回空串 ✓）*/
    private String shotB64() {
        try {
            android.view.View rv = getWindow().getDecorView();
            android.graphics.Bitmap bm = android.graphics.Bitmap.createBitmap(rv.getWidth(), rv.getHeight(), android.graphics.Bitmap.Config.ARGB_8888);
            rv.draw(new android.graphics.Canvas(bm));
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            bm.compress(android.graphics.Bitmap.CompressFormat.JPEG, 70, bo);
            return "data:image/jpeg;base64," + android.util.Base64.encodeToString(bo.toByteArray(), android.util.Base64.NO_WRAP);
        } catch (Throwable t) { return ""; }
    }

    private String feedbackText(String desc) {
        StringBuilder b = new StringBuilder();
        b.append("=== C3 控制台 · 问题反馈 ===").append("\n");
        b.append("时间: ").append(new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new java.util.Date())).append("\n");
        try { b.append("版本: v").append(getPackageManager().getPackageInfo(getPackageName(), 0).versionName).append("\n"); } catch (Throwable ignore) { }
        b.append("显示模式: ").append(carMode() ? "车机" : "手机/平板").append(" 宽度 ").append(pageWidthDp()).append("dp\n");
        try {
            Store.Host h = new Store(this).defaultHost();
            if (h != null) b.append("主机: ").append(h.label).append(" ").append(h.host).append(":").append(h.port).append(" 用户=").append(h.user).append("\n");
        } catch (Throwable ignore) { }
        b.append("\n--- 用户描述 ---\n").append(desc == null ? "" : desc).append("\n");
        b.append("\n--- 最近日志（节选）---\n").append(Logs.dump(60000)).append("\n");
        return b.toString();
    }

    private void shareFeedbackText(String desc) {
        try {
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_SUBJECT, "C3 控制台 · 问题反馈");
            i.putExtra(Intent.EXTRA_TEXT, feedbackText(desc));
            startActivity(Intent.createChooser(i, "分享反馈"));
        } catch (Throwable t) { toast("没有可用的分享目标（可以先「保存反馈包」）"); }
    }

    private void saveFeedback(String desc) {
        String ts = new java.text.SimpleDateFormat("yyyyMMdd-HHmmss").format(new java.util.Date());
        String txt = feedbackText(desc);
        String p1 = null, p2 = null;
        try { p1 = saveToDownloads("c3-feedback-" + ts + ".txt", txt.getBytes("UTF-8"), "text/plain"); } catch (Throwable ignore) { }
        try {
            android.view.View rv = getWindow().getDecorView();
            android.graphics.Bitmap bm = android.graphics.Bitmap.createBitmap(rv.getWidth(), rv.getHeight(), android.graphics.Bitmap.Config.ARGB_8888);
            rv.draw(new android.graphics.Canvas(bm));
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            bm.compress(android.graphics.Bitmap.CompressFormat.PNG, 90, bo);
            p2 = saveToDownloads("c3-feedback-" + ts + ".png", bo.toByteArray(), "image/png");
        } catch (Throwable ignore) { }
        StringBuilder m = new StringBuilder("反馈已保存：");
        m.append("\n").append(p1 == null ? "（日志文件保存失败）" : p1);
        m.append("\n").append(p2 == null ? "（截图保存失败）" : p2);
        m.append("\n\n到「文件管理器 → 下载」把它们发给我即可 ✓");
        try {
            new AlertDialog.Builder(this).setTitle("已生成反馈包").setMessage(m.toString())
                .setPositiveButton("好", null).show();
        } catch (Throwable t) { toast("已保存到下载目录"); }
    }

    /** 写文件到系统「下载」目录（MediaStore，失败退到 APP 外部目录）——与 /save 同逻辑 ✓ */
    private String saveToDownloads(String name, byte[] bytes, String mime) {
        try {
            Class<?> dl = Class.forName("android.provider.MediaStore$Downloads");
            android.net.Uri ext = (android.net.Uri) dl.getField("EXTERNAL_CONTENT_URI").get(null);
            android.content.ContentValues cv = new android.content.ContentValues();
            cv.put("_display_name", name);
            cv.put("mime_type", mime);
            try { cv.put("relative_path", "Download/"); } catch (Throwable ignore) { }
            android.net.Uri item = getContentResolver().insert(ext, cv);
            if (item != null) {
                java.io.OutputStream os = getContentResolver().openOutputStream(item);
                os.write(bytes); os.flush(); os.close();
                return "下载/" + name;
            }
        } catch (Throwable ignore) { }
        try {
            java.io.File d = getExternalFilesDir(null);
            if (d == null) d = getFilesDir();
            java.io.File f = new java.io.File(d, name);
            java.io.FileOutputStream fo = new java.io.FileOutputStream(f);
            fo.write(bytes); fo.flush(); fo.close();
            return f.getAbsolutePath();
        } catch (Throwable t) { return null; }
    }

    /* 老安卓车机适配（2026-09-23）：minSdk 21->19；API<20 打开 TLS1.2；低配模式关动画 */
    private static void enableTls12() {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 20) return;
            javax.net.ssl.SSLContext sc = javax.net.ssl.SSLContext.getInstance("TLSv1.2");
            sc.init(null, null, null);
            javax.net.ssl.HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
        } catch (Throwable ignore) { }
    }
    private boolean lowEnd() {
        try {
            if (android.os.Build.VERSION.SDK_INT < 24) return true;
            android.app.ActivityManager am = (android.app.ActivityManager) getSystemService(ACTIVITY_SERVICE);
            if (am != null) {
                try {   // 编译桩没有 isLowRamDevice() → 反射 ✓
                    Object r = am.getClass().getMethod("isLowRamDevice").invoke(am);
                    if (r instanceof Boolean && ((Boolean) r).booleanValue()) return true;
                } catch (Throwable ignore) { }
            }
        } catch (Throwable ignore) { }
        return false;
    }

    /** 2026-09-22 用户要求：连接相关的英文提示翻成中文 ✓（原文附后面便于对照） */
    private static String cnSshMsg(String s0) {
        String s = s0 == null ? "" : s0;
        String[][] map = {
            {"Auth fail", "认证失败：密钥或用户名不对（换一个内置密钥试试）"},
            {"Auth cancel", "认证被取消"},
            {"invalid privatekey", "私钥格式不对：需要 OpenSSH 格式（PuTTY 的 .ppk 要先转换）"},
            {"Connection refused", "连接被拒：目标端口没开（检查端口/服务是否启动）"},
            {"Connection timed out", "连接超时：IP 不通或不在同一网络"},
            {"timed out", "连接超时：IP 不通或不在同一网络"},
            {"Network is unreachable", "网络不可达：检查 Wi-Fi 与 IP"},
            {"No route to host", "网络不可达：检查 Wi-Fi 与 IP"},
            {"UnknownHost", "地址解析失败：主机名/IP 可能写错了"},
            {"Host key verification", "加密协商失败：主机指纹或算法不匹配"},
            {"algorithm negotiation", "加密协商失败：主机指纹或算法不匹配"},
            {"No such file", "文件不存在：密钥路径写错了"},
            {"Permission denied", "没有权限：用户名或密钥不匹配"}
        };
        for (String[] m : map) if (s.indexOf(m[0]) >= 0) return m[1] + "（原文：" + (s.length() > 90 ? s.substring(0, 90) : s) + "）";
        return s.length() == 0 ? "未知错误" : s;
    }
    /** 从 testJson 返回里抽人话（成功时给主机名/内核） */
    private static String cnTestOk(String res, String ip) {
        try {
            int i = res.indexOf("Linux ");
            if (i >= 0) {
                String[] p = res.substring(i).split("[ \t]+");
                if (p.length >= 3) return "✓ 已连接：" + ip + " · 主机名 " + p[1] + " · 内核 " + p[2];
            }
        } catch (Throwable ignore) { }
        return "✓ 已连接：" + ip;
    }

    /** 2026-09-22 用户要求：替换 IP 后**自动连接**；失败则跳到 SSH 控制台（主机页）让用户改端口/用户/密钥 ✓ */
    private void testHostAndJump(final Store.Host h) {
        new Thread(new Runnable() { public void run() {
            String r = null, err = null;
            try { r = new Ssh(MainActivity.this).testJson(h.host, h.port, h.user, h.key, null); }
            catch (Throwable t) { err = t.getClass().getSimpleName(); }
            final String res = r, e2 = err;
            final boolean ok = res != null && res.indexOf("\"ok\":true") >= 0;
            runOnUiThread(new Runnable() { public void run() {
                if (ok) { toast(cnTestOk(res, h.host)); load(); return; }
                String why = cnSshMsg(res != null ? res : ("异常 " + e2));
                if (why.length() > 300) why = why.substring(0, 300) + "…";
                try {
                    new AlertDialog.Builder(MainActivity.this)
                        .setTitle("连接失败")
                        .setMessage("地址 " + h.host + " 已保存，但连不上。\n\n" + why
                                  + "\n\n可以到 SSH 控制台的「主机」页检查：端口 / 用户 / 密钥。")
                        .setPositiveButton("去 SSH 控制台", new DialogInterface.OnClickListener() {
                            public void onClick(DialogInterface d, int w) { gotoConsoleHost(); }
                        })
                        .setNegativeButton("稍后", null)
                        .show();
                } catch (Throwable t) { toast("连接失败（已保存地址）"); gotoConsoleHost(); }
            } });
        } }).start();
    }

    /** 反射调用页面自己的页签切换（编译桩没有 evaluateJavascript ✗）——避免整页重载导致的闪屏 ✓ */
    private boolean jsSwitchTab(String tab) {
        try {
            java.lang.reflect.Method m = web.getClass().getMethod("evaluateJavascript",
                    String.class, android.webkit.ValueCallback.class);
            m.invoke(web, "(function(){var b=document.querySelector('nav.tabs button[data-tab=\""
                    + tab + "\"]');if(b){b.click();var s=document.getElementById('nmMenu');return '1'}return '0'})()", null);
            return true;
        } catch (Throwable t) { return false; }
    }

    /** 跳到 SSH 控制台（该页默认是「主机」，含地址/端口/用户/密钥表单）✓ */
    private void gotoConsoleHost() {
        try { if (bConsole != null) { bConsole.performClick(); return; } } catch (Throwable ignore) { }
        try { page = P_CONSOLE; load(); } catch (Throwable ignore) { }
    }

    private void scanC3Devices() {
        // 点「查找」先弹雷达扫描动画 ✓；扫到的地址可点选 ✓；点后询问是否替换 ✓
        final RadarView radar = new RadarView(this);
        final TextView stat = new TextView(this);
        final LinearLayout listBox = new LinearLayout(this);
        listBox.setOrientation(LinearLayout.VERTICAL);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(10), dp(16), dp(4));
        box.addView(radar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(170)));
        stat.setText("正在扫描局域网（SSH 22 端口）…");
        stat.setTextSize(13); stat.setTextColor(C_DIM);
        stat.setPadding(0, dp(8), 0, dp(4));
        box.addView(stat);
        android.widget.ScrollView sv = new android.widget.ScrollView(this);
        sv.addView(listBox);
        box.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(170)));
        new AlertDialog.Builder(this).setTitle("设备查找").setView(box).setPositiveButton("关闭", null).show();
        radar.start();
        new Thread(new Runnable() { public void run() {
            try {
                java.util.List<String> pres = new java.util.ArrayList<String>();
                java.util.Enumeration<java.net.NetworkInterface> nis = java.net.NetworkInterface.getNetworkInterfaces();
                while (nis.hasMoreElements()) {
                    java.net.NetworkInterface ni = nis.nextElement();
                    if (ni == null || !ni.isUp() || ni.isLoopback()) continue;
                    java.util.Enumeration<java.net.InetAddress> as = ni.getInetAddresses();
                    while (as.hasMoreElements()) {
                        java.net.InetAddress a = as.nextElement();
                        if (!(a instanceof java.net.Inet4Address)) continue;
                        byte[] bb = a.getAddress();
                        pres.add((bb[0] & 0xff) + "." + (bb[1] & 0xff) + "." + (bb[2] & 0xff));
                    }
                }
                final java.util.List<String> hits = java.util.Collections.synchronizedList(new java.util.ArrayList<String>());
                for (int pi = 0; pi < pres.size() && hits.size() < 8; pi++) {
                    final String pre = pres.get(pi);
                    java.util.concurrent.ExecutorService ex = java.util.concurrent.Executors.newFixedThreadPool(32);
                    for (int i = 1; i <= 254; i++) {
                        final String ip = pre + "." + i;
                        ex.submit(new Runnable() { public void run() {
                            try {
                                java.net.Socket so = new java.net.Socket();
                                so.connect(new java.net.InetSocketAddress(ip, 22), 300);
                                so.close();
                                hits.add(ip);
                            } catch (Throwable ignore) { }
                        } });
                    }
                    ex.shutdown();
                    try { ex.awaitTermination(6, java.util.concurrent.TimeUnit.SECONDS); } catch (Throwable ignore) { }
                }
                java.util.Collections.sort(hits);
                runOnUiThread(new Runnable() { public void run() {
                    radar.stop();
                    if (hits.isEmpty()) {
                        stat.setText("没扫到开放 22 端口的设备（确认手机与 C3 在同一 Wi-Fi）");
                        toast("没扫到设备"); return;
                    }
                    stat.setText("找到 " + hits.size() + " 台设备 · 点一下地址即可替换当前 IP");
                    final String cur = prefs.getString(K_HOST, "");
                    for (final String ip : hits) {
                        Button b = new Button(MainActivity.this);
                        b.setText(ip + (ip.equals(cur) ? "　（当前）" : ""));
                        b.setAllCaps(false);
                        b.setOnClickListener(new View.OnClickListener() { public void onClick(View v) {
                            confirmReplaceHost(ip);
                        } });
                        listBox.addView(b, new LinearLayout.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
                        radar.addBlip();
                    }
                } });
            } catch (Throwable t) {
                runOnUiThread(new Runnable() { public void run() { toast("扫描失败：" + t.getClass().getSimpleName()); } });
            }
        } }).start();
    }

    /** 调起系统文件管理器选密钥（用户反馈：以前打不开文件管理器） */
    private void startPickKey() {
        try {
            Intent i = new Intent("android.intent.action.OPEN_DOCUMENT");
            i.addCategory("android.intent.category.OPENABLE");
            i.setType("*/*");
            startActivityForResult(i, REQ_PICK_KEY);
        } catch (Throwable t) {
            try {
                Intent i2 = new Intent("android.intent.action.GET_CONTENT");
                i2.setType("*/*");
                startActivityForResult(i2, REQ_PICK_KEY);
            } catch (Throwable t2) { toast("这台设备没有可用的文件管理器"); }
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_PICK_PKG) {
            if (res != RESULT_OK || data == null || data.getData() == null) { toast("已取消选择"); return; }
            android.net.Uri pu = data.getData();
            try {
                String nm = "update.sh";
                String seg = pu.getLastPathSegment();
                if (seg != null && seg.length() > 0) { int sl = seg.lastIndexOf('/'); nm = sl >= 0 ? seg.substring(sl + 1) : seg; }
                java.io.InputStream is = getContentResolver().openInputStream(pu);
                java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                byte[] b = new byte[8192];
                int n;
                while ((n = is.read(b)) > 0) bo.write(b, 0, n);
                is.close();
                String b64 = android.util.Base64.encodeToString(bo.toByteArray(), android.util.Base64.NO_WRAP);
                new Pkg(this).save(nm, b64, pendingPkgNote);
                toast("已加入更新包库：" + nm);
                load();
            } catch (Throwable t) { toast("导入失败：" + t.getClass().getSimpleName()); }
            return;
        }
        if (req == REQ_PICK_DIR) {
            if (res != RESULT_OK || data == null || data.getData() == null) { toast("已取消选择目录"); return; }
            android.net.Uri tu = data.getData();
            try {   // 编译桩没有 takePersistableUriPermission ✗ → 反射（这是"重启后仍能用该目录"的关键 ✓）
                java.lang.reflect.Method tm = getContentResolver().getClass()
                        .getMethod("takePersistableUriPermission", android.net.Uri.class, int.class);
                tm.invoke(getContentResolver(), tu,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            } catch (Throwable ignore) { }
            String seg = String.valueOf(tu.getLastPathSegment());
            String nm = seg;
            try { int c = seg.lastIndexOf(':'), sl = seg.lastIndexOf('/');
                  nm = seg.substring(Math.max(c, sl) + 1); } catch (Throwable ignore) { }
            if (nm == null || nm.length() == 0) nm = "所选目录";
            prefs.edit().putString("saveDirUri", tu.toString()).putString("saveDirName", nm).commit();
            toast("导出目录已设为：" + nm);
            final String fn = nm.replace("'", "");
            web.post(new Runnable() { public void run() {
                try {
                    java.lang.reflect.Method m = web.getClass().getMethod("evaluateJavascript",
                            String.class, android.webkit.ValueCallback.class);
                    m.invoke(web, "window.__saveDir && window.__saveDir('" + fn + "')", null);
                } catch (Throwable t) { }
            }});
            return;
        }
        if (req == REQ_PICK_CSV) {
            if (res != RESULT_OK || data == null || data.getData() == null) { toast("已取消选择"); return; }
            android.net.Uri cu = data.getData();
            try {
                String nm = "params.csv";
                String seg = cu.getLastPathSegment();
                if (seg != null && seg.length() > 0) { int sl = seg.lastIndexOf('/'); nm = sl >= 0 ? seg.substring(sl + 1) : seg; }
                java.io.InputStream is = getContentResolver().openInputStream(cu);
                java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                byte[] b = new byte[8192]; int n;
                while ((n = is.read(b)) > 0) bo.write(b, 0, n);
                is.close();
                final String b64 = android.util.Base64.encodeToString(bo.toByteArray(), android.util.Base64.NO_WRAP);
                final String fname = nm.replace("'", "");
                toast("已选：" + nm);
                // 回灌给页面（编译桩没有 evaluateJavascript ✗ → 反射调用 ✓）
                final MainActivity self = this;
                web.post(new Runnable() { public void run() {
                    try {
                        java.lang.reflect.Method m = web.getClass().getMethod("evaluateJavascript",
                                String.class, android.webkit.ValueCallback.class);
                        m.invoke(web, "window.__importCsv && window.__importCsv('" + b64 + "','" + fname + "')", null);
                    } catch (Throwable t) { toast("回灌页面失败：" + t.getClass().getSimpleName()); }
                }});
            } catch (Throwable t) { toast("导入失败：" + t.getClass().getSimpleName()); }
            return;
        }
        if (req != REQ_PICK_KEY) return;
        if (res != RESULT_OK || data == null || data.getData() == null) { toast("已取消选择密钥"); return; }
        android.net.Uri u = data.getData();
        try {
            String name = "本机导入密钥";
            String seg = u.getLastPathSegment();
            if (seg != null && seg.length() > 0) { int sl = seg.lastIndexOf('/'); name = sl >= 0 ? seg.substring(sl + 1) : seg; }
            java.io.InputStream is = getContentResolver().openInputStream(u);
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            byte[] b = new byte[8192];
            int n;
            while ((n = is.read(b)) > 0) bo.write(b, 0, n);
            is.close();
            Store st = new Store(this);
            java.io.File f = new java.io.File(st.keysDir(), Store.safe(name));
            java.io.FileOutputStream o = new java.io.FileOutputStream(f);
            o.write(bo.toByteArray());
            o.close();
            Store.Host h = st.defaultHost();
            if (h != null) { h.key = f.getAbsolutePath(); st.upsertHost(h); }
            toast("已导入密钥：" + f.getName() + "（已设为当前主机的私钥）");
            load();
        } catch (Throwable t) {
            toast("导入失败：" + t.getClass().getSimpleName() + " " + t.getMessage());
        }
    }

    /** 请求把本应用放到分屏（Android 7+ 的 LAUNCH_ADJACENT；失败就提示手动分屏）。 */
    private void splitScreen() {
        try {
            Intent i = new Intent(this, MainActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | 0x00001000 /* FLAG_ACTIVITY_LAUNCH_ADJACENT */);
            startActivity(i);
            toast("已请求分屏；若无反应请在最近任务里手动分屏");
        } catch (Throwable t) {
            toast("分屏请求失败：" + t.getClass().getSimpleName());
        }
    }

    private void openDsh() {
        try {
            Intent i = getPackageManager().getLaunchIntentForPackage("com.dsharnessmobile.shell");
            if (i == null) { toast("没找到 DSH 应用"); return; }
            startActivity(i);
        } catch (Throwable e) {
            toast("没找到 DSH 应用");
        }
    }

    // ---------------------------------------------------------------- 杂项

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && web != null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }
}
