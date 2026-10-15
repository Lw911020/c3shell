package com.padagent.c3shell;

import android.content.Context;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * 资产加密（2026-09-21 起；**2026-09-24 加固：密钥绑定本包签名证书**）。
 * 构建时把 html/js/css/py/keys/jpg 加密成 <名字>.enc，运行时透明解密。
 *
 * 密钥 = 固定基串(15B) + 本包签名证书 DER 的**尾部 9 字节**
 *   → 别人二次打包 / 换签名后钥匙就变了 → 资产全解不开（页面都出不来）✓
 * 说明：编译桩里没有 javax.crypto / java.security，故用自写 RC4 型流密码 + 明文校验和；
 *       它挡的是"随手解包抄改"，不是强密码学（这点如实写在 README）。
 */
public class Sec {

    private static byte[] gKey = null;

    private static byte[] base() {
        // 分段拼接，避免密钥以整串明文出现在 dex 里
        byte[] a = {0x43, 0x33, 0x53, 0x68};                 // C3Sh
        byte[] b = {0x65, 0x6c, 0x6c, 0x32, 0x30};           // ell20
        byte[] c = {0x32, 0x36, 0x2d, 0x50, 0x41, 0x44};     // 26-PAD
        byte[] k = new byte[a.length + b.length + c.length];
        System.arraycopy(a, 0, k, 0, a.length);
        System.arraycopy(b, 0, k, a.length, b.length);
        System.arraycopy(c, 0, k, a.length + b.length, c.length);
        return k;
    }

    private static synchronized byte[] key(Context ctx) throws IOException {
        if (gKey != null) return gKey;
        byte[] seed = Guard.assetsKeySeed(ctx);      // 取签名尾部（Guard 里统一读，便于校验）
        if (seed == null) throw new IOException("读不到本包签名，无法解密资产");
        byte[] b = base();
        byte[] k = new byte[b.length + seed.length];
        System.arraycopy(b, 0, k, 0, b.length);
        System.arraycopy(seed, 0, k, b.length, seed.length);
        gKey = k;
        return k;
    }

    private static byte[] ks(byte[] key, int n) {
        int[] S = new int[256];
        for (int i = 0; i < 256; i++) S[i] = i;
        int j = 0;
        for (int i = 0; i < 256; i++) {
            j = (j + S[i] + (key[i % key.length] & 0xFF)) & 255;
            int t = S[i]; S[i] = S[j]; S[j] = t;
        }
        byte[] out = new byte[n];
        int i2 = 0; j = 0;
        for (int x = 0; x < n; x++) {
            i2 = (i2 + 1) & 255;
            j = (j + S[i2]) & 255;
            int t = S[i2]; S[i2] = S[j]; S[j] = t;
            out[x] = (byte) (S[(S[i2] + S[j]) & 255]);
        }
        return out;
    }

    public static byte[] xcrypt(byte[] data, Context ctx) throws IOException {
        byte[] k = ks(key(ctx), data.length);
        byte[] o = new byte[data.length];
        for (int i = 0; i < data.length; i++) o[i] = (byte) (data[i] ^ k[i]);
        return o;
    }

    private static int be32(byte[] b, int o) {
        return ((b[o] & 0xFF) << 24) | ((b[o + 1] & 0xFF) << 16) | ((b[o + 2] & 0xFF) << 8) | (b[o + 3] & 0xFF);
    }

    /** 读资产：优先读 <name>.enc 并解密校验；不存在则回退明文 */
    public static InputStream open(Context ctx, String name) throws IOException {
        InputStream in;
        try {
            in = ctx.getAssets().open(name + ".enc");
        } catch (IOException e) {
            return ctx.getAssets().open(name);
        }
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
        in.close();
        byte[] all = bo.toByteArray();
        if (all.length < 12 || all[0] != 'C' || all[1] != '3' || all[2] != 'S' || all[3] != '1')
            throw new IOException("资产头无效：" + name);
        int len = be32(all, 4);
        if (len < 0 || all.length < 12 + len) throw new IOException("资产长度无效：" + name);
        byte[] body = new byte[len];
        System.arraycopy(all, 8, body, 0, len);
        byte[] plain = xcrypt(body, ctx);
        int sum = 0;
        for (int i = 0; i < plain.length; i++) sum = (sum + (plain[i] & 0xFF)) & 0xFFFFFFFF;
        if (sum != be32(all, 8 + len)) throw new IOException("资产校验失败（可能被改动）：" + name);
        return new ByteArrayInputStream(plain);
    }
}
