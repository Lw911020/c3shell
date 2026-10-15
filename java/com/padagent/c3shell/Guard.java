package com.padagent.c3shell;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Debug;
import android.widget.Toast;

/**
 * 加固（2026-09-24 用户要求「把 APP 加密一下，避免轻易破解」）：
 *   ① 签名校验：与构建时写入的证书指纹比对 —— 二次打包/重签名 → 直接退出（资产本来就解不开）
 *   ② 反调试 / 反注入：debugger、debuggable、frida/xposed/substrate 痕迹 → 仅提示（不误伤正常使用）
 *   ③ WebView 调试开关收口：默认关（作者要看时把偏好 webdbg 置 true）
 * 说明：客户端防破解只能"抬高门槛"，真正算钱的校验（卡密）本来就在服务器侧 ✓
 */
public final class Guard {

    private static byte[] gDer = null;
    private static boolean gRead = false;

    private static synchronized byte[] der(Context ctx) {
        if (gRead) return gDer;
        gRead = true;
        try {
            PackageManager pm = ctx.getPackageManager();
            // 64 = GET_SIGNATURES（API 28+ 已废弃但依然返回结果）；不写常量名以免依赖新 SDK 桩
            PackageInfo pi = pm.getPackageInfo(ctx.getPackageName(), 64);
            if (pi != null && pi.signatures != null && pi.signatures.length > 0) {
                gDer = pi.signatures[0].toByteArray();
            }
        } catch (Throwable e) {
            gDer = null;
        }
        return gDer;
    }

    /** 资产密钥里的"签名部分"：证书 DER 尾部 9 字节（构建时取的是同一份 DER）*/
    static byte[] assetsKeySeed(Context ctx) {
        byte[] d = der(ctx);
        if (d == null || d.length < 9) return null;
        byte[] t = new byte[9];
        System.arraycopy(d, d.length - 9, t, 0, 9);
        return t;
    }

    private static String hex(byte[] b) {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < b.length; i++) {
            s.append(Character.forDigit((b[i] >> 4) & 15, 16)).append(Character.forDigit(b[i] & 15, 16));
        }
        return s.toString();
    }

    /** true = 签名与构建时不一致（被改过 / 二次打包）*/
    static boolean tampered(Context ctx) {
        byte[] t = assetsKeySeed(ctx);
        if (t == null) return true;                     // 读不到也按异常处理（资产同样解不开）
        return !hex(t).equalsIgnoreCase(BuildInfo.CERT_TAIL);
    }

    /** 调试器 / 注入框架痕迹（只提示）*/
    static String hazard(Context ctx) {
        StringBuilder s = new StringBuilder();
        try { if (Debug.isDebuggerConnected()) s.append("调试器 "); } catch (Throwable e) { }
        try { if ((ctx.getApplicationInfo().flags & 2) != 0) s.append("debuggable "); } catch (Throwable e) { }
        try {
            java.io.BufferedReader r = new java.io.BufferedReader(
                    new java.io.InputStreamReader(new java.io.FileInputStream("/proc/self/maps")));
            String ln; int n = 0;
            while ((ln = r.readLine()) != null && n++ < 4000) {
                String l = ln.toLowerCase();
                if (l.indexOf("frida") >= 0 || l.indexOf("xposed") >= 0
                        || l.indexOf("substrate") >= 0 || l.indexOf("lsposed") >= 0) {
                    s.append(l.indexOf("frida") >= 0 ? "frida " : "xposed ");
                    break;
                }
            }
            r.close();
        } catch (Throwable e) { }
        return s.toString().trim();
    }

    /** WebView 远程调试（chrome://inspect）默认关 —— 开着等于把解密后的页面送到别人手里 */
    static boolean webDebug(Context ctx) {
        try { return ctx.getSharedPreferences("c3shell", 0).getBoolean("webdbg", false); } catch (Throwable e) { return false; }
    }

    /** 启动自检：签名不符 → 提示并退出；有调试/注入 → 只提示 */
    public static boolean check(final Activity a) {
        try {
            if (tampered(a)) {
                new AlertDialog.Builder(a)
                    .setTitle("包被改过，不能使用")
                    .setMessage("本应用的签名与发布版不一致（被二次打包或重新签名）。\n\n"
                              + "内置资源是按签名加密的，改包后无法正常工作。")
                    .setCancelable(false)
                    .setPositiveButton("退出", new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface d, int w) { a.finish(); }
                    })
                    .show();
                return false;
            }
            String hz = hazard(a);
            if (hz.length() > 0) Toast.makeText(a, "检测到 " + hz + "（仅提示，不影响使用）", Toast.LENGTH_LONG).show();
        } catch (Throwable e) { }
        return true;
    }
}
