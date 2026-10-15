package com.padagent.c3shell;

import android.content.Context;
import java.io.File;
import java.io.FileOutputStream;
import java.io.RandomAccessFile;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.Date;
import java.util.Locale;

/**
 * APP 内日志（2026-09-21 用户建议：出问题直接读日志，不要猜）。
 * 环形缓冲（内存 400 条）+ 落盘（filesDir/app.log，超过 256KB 截半），并提供 /api/log 读取。
 */
public class Logs {
    private static final int MAX = 400;
    private static final long MAX_FILE = 256 * 1024;
    private static final ArrayDeque<String> BUF = new ArrayDeque<String>();
    private static Context CTX;
    private static final SimpleDateFormat TS = new SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US);

    public static void init(Context c) { CTX = c.getApplicationContext(); }

    public static synchronized void add(String tag, String msg) {
        String line = TS.format(new Date()) + " [" + tag + "] " + (msg == null ? "" : msg);
        BUF.addLast(line);
        while (BUF.size() > MAX) BUF.removeFirst();
        try {
            if (CTX != null) {
                File f = new File(CTX.getFilesDir(), "app.log");
                FileOutputStream o = new FileOutputStream(f, true);
                o.write((line + "\n").getBytes("UTF-8"));
                o.close();
                if (f.length() > MAX_FILE) {              // 截半，留最近一半
                    RandomAccessFile r = new RandomAccessFile(f, "rw");
                    long keep = f.length() / 2;
                    byte[] b = new byte[(int) keep];
                    r.seek(f.length() - keep);
                    r.readFully(b);
                    r.setLength(0);
                    r.seek(0);
                    r.write(b);
                    r.close();
                }
            }
        } catch (Throwable ignore) { }
    }

    public static synchronized String dump(int tail) {
        StringBuilder b = new StringBuilder();
        try {
            File f = (CTX != null) ? new File(CTX.getFilesDir(), "app.log") : null;
            if (f != null && f.exists()) {
                RandomAccessFile r = new RandomAccessFile(f, "r");
                long len = f.length();
                long start = Math.max(0, len - Math.max(4096, tail));
                r.seek(start);
                byte[] buf = new byte[(int) (len - start)];
                r.readFully(buf);
                r.close();
                b.append(new String(buf, "UTF-8"));
            }
        } catch (Throwable ignore) { }
        if (b.length() == 0) { for (String s : BUF) b.append(s).append('\n'); }
        return b.toString();
    }

    public static synchronized void clear() {
        BUF.clear();
        try { if (CTX != null) new File(CTX.getFilesDir(), "app.log").delete(); } catch (Throwable ignore) { }
    }
}
