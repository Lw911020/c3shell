package com.padagent.c3shell;

import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.Ringtone;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.IBinder;
import android.speech.tts.TextToSpeech;
import android.util.Log;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 语音提醒服务（2026-09-20）。
 *
 * 连接器（dsh-ssh-connector）把「该播什么」写进队列端点
 *   GET http://<host>:<port>/api/voice/next?since=<id>
 * 本服务每 3.5 秒轮询一次，用系统 TTS 播报新条目：
 *   - 对话完成  → 「对话已完成」
 *   - 需要选择  → 「需要你选择」
 * 只走回环地址、不需要 token（该端点仅绑在 127.0.0.1 时可用）。
 */
public class SpeechService extends Service {
    private static final String TAG = "C3ShellSpeech";
    private static final String PREFS = "c3shell";
    private static final long POLL_MS = 1500L;

    private static volatile boolean NUDGE = false;

    /** 入队后立即唤醒取队列线程 → 语音几乎无延迟 */
    public static void nudge() { NUDGE = true; }   // 兜底轮询（正常靠 nudge 立即唤醒）

    private TextToSpeech tts;
    private volatile boolean ttsReady = false;
    private volatile boolean toneFallback = false;
    private volatile boolean running = true;
    private final ArrayDeque<String> pending = new ArrayDeque<String>();
    private Thread poller;
    private static SpeechService INSTANCE;

    /** 语速/音调（2026-09-21 用户反馈：几个音色听起来一样 → 给可听见的调节） */
    public static String setRatePitch(String rateS, String pitchS) {
        SpeechService svc = INSTANCE;
        try {
            float r = Float.parseFloat(rateS), pi = Float.parseFloat(pitchS);
            if (r < 0.3f) r = 0.3f; if (r > 2.5f) r = 2.5f;
            if (pi < 0.3f) pi = 0.3f; if (pi > 2.5f) pi = 2.5f;
            if (svc != null && svc.tts != null) { svc.tts.setSpeechRate(r); svc.tts.setPitch(pi); }
            if (svc != null) svc.getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("ttsRate", String.valueOf(r)).putString("ttsPitch", String.valueOf(pi)).apply();
            return "{\"ok\":true,\"rate\":" + r + ",\"pitch\":" + pi + "}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t.getMessage())) + "\"}}";
        }
    }


    // ── 音色相关：一律走反射，编译桩里没有 Object ──
    private static java.util.Set<?> voicesOf(TextToSpeech t) {
        try { Object o = TextToSpeech.class.getMethod("getVoices").invoke(t); return (java.util.Set<?>) o; }
        catch (Throwable e) { return java.util.Collections.emptySet(); }
    }
    private static Object findVoice(TextToSpeech t, String name) {
        if (name == null || name.length() == 0) return null;
        for (Object v : voicesOf(t)) if (name.equals(vName(v))) return v;
        return null;
    }
    private static String vName(Object v) { return String.valueOf(call(v, "getName")); }
    private static String vLocale(Object v) { return String.valueOf(call(v, "getLocale")); }
    private static int vInt(Object v, String m) { Object o = call(v, m); return (o instanceof Integer) ? (Integer) o : 0; }
    private static Object call(Object o, String m) {
        try { return o.getClass().getMethod(m).invoke(o); } catch (Throwable e) { return null; }
    }
    private static boolean applyVoice(TextToSpeech t, Object voice) {
        try {
            Class<?> vc = Class.forName("Object");
            TextToSpeech.class.getMethod("setVoice", vc).invoke(t, voice);
            return true;
        } catch (Throwable e) { return false; }
    }
    private static String currentVoiceName(TextToSpeech t) {
        try { Object v = TextToSpeech.class.getMethod("getVoice").invoke(t); return v == null ? "" : vName(v); }
        catch (Throwable e) { return ""; }
    }

    /** 供内置 API 调用：列出系统 TTS 的音色 */
    public static String voicesJson() {
        SpeechService svc = INSTANCE;
        try {
            StringBuilder b = new StringBuilder("{\"ok\":true,\"voices\":[");
            if (svc != null && svc.tts != null) {
                boolean first = true;
                for (Object v : voicesOf(svc.tts)) {
                    if (!first) b.append(',');
                    first = false;
                    b.append("{\"name\":\"").append(esc(vName(v))).append("\",\"locale\":\"")
                     .append(esc(vLocale(v))).append("\",\"quality\":").append(vInt(v, "getQuality"))
                     .append(",\"latency\":").append(vInt(v, "getLatency")).append('}');
                }
            }
            return b.append("],\"current\":\"").append(esc(currentVoice())).append("\",\"rate\":" + rate() + ",\"pitch\":" + pitch() + "}").toString();
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t.getMessage())) + "\"},\"voices\":[]}";
        }
    }

    /** 播报通道：0=通话 3=媒体 5=通知（2026-09-21 车机上语音没声 → 允许切换） */
    public static String stream() {
        SpeechService s = INSTANCE;
        try { return s != null ? s.getSharedPreferences(PREFS, MODE_PRIVATE).getString("ttsStream", "3") : "3"; }
        catch (Throwable e) { return "3"; }
    }
    public static String setStream(String v) {
        int n = 3; try { n = Integer.parseInt(v); } catch (Throwable ignore) { }
        SpeechService s = INSTANCE;
        try { if (s != null) s.getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("ttsStream", String.valueOf(n)).apply(); } catch (Throwable ignore) { }
        return "{\"ok\":true,\"stream\":" + n + "}";
    }
    private static java.util.HashMap<String, String> params() {
        // 编译桩里只声明了旧签名 speak(CharSequence,int,HashMap)；真机上等价（stream 参数）
        java.util.HashMap<String, String> m = new java.util.HashMap<String, String>();
        try { m.put("stream", stream()); } catch (Throwable ignore) { }
        return m;
    }
    /** 本机 TTS 诊断：车机上用来判"为什么没声音"（无引擎？无中文音色？通道不对？） */
    public static String diag() {
        boolean ready = false; int n = 0, zh = 0; String eng = "", err = "";
        SpeechService s = INSTANCE;
        try {
            if (s != null && s.tts != null) {
                ready = true;
                try { eng = String.valueOf(TextToSpeech.class.getMethod("getDefaultEngine").invoke(s.tts)); } catch (Throwable ignore) { }
                java.util.Set<?> vs = voicesOf(s.tts);
                if (vs != null) {
                    n = vs.size();
                    for (Object v : vs) { String nm = vName(v); if (nm != null && nm.toLowerCase().indexOf("zh") >= 0) zh++; }
                }
                if (n == 0) err = "引擎已就绪但音色列表为空（本机可能没装中文语音数据）";
            } else err = "TTS 未初始化：本机可能没有语音引擎（车机常见）";
        } catch (Throwable t) { err = String.valueOf(t.getMessage()); }
        return "{\"ok\":true,\"serviceRunning\":" + (INSTANCE != null) + ",\"ready\":" + ready + ",\"engine\":\"" + esc(eng) + "\",\"voices\":" + n
             + ",\"zhVoices\":" + zh + ",\"voice\":\"" + esc(currentVoice()) + "\",\"stream\":" + stream()
             + ",\"rate\":\"" + rate() + "\",\"pitch\":\"" + pitch() + "\",\"lastError\":\"" + esc(err) + "\"}";
    }

    private static String rate() { SpeechService s = INSTANCE; try { return String.valueOf(s != null ? s.getSharedPreferences(PREFS, MODE_PRIVATE).getString("ttsRate", "1") : "1"); } catch (Throwable e) { return "1"; } }
    private static String pitch() { SpeechService s = INSTANCE; try { return String.valueOf(s != null ? s.getSharedPreferences(PREFS, MODE_PRIVATE).getString("ttsPitch", "1") : "1"); } catch (Throwable e) { return "1"; } }

    public static String currentVoice() {
        SpeechService svc = INSTANCE;
        try { if (svc != null && svc.tts != null) return currentVoiceName(svc.tts); } catch (Throwable ignore) { }
        return "";
    }

    /** 切换音色（持久化 + 立即生效 + 试听） */
    public static String setVoice(String name) {
        SpeechService svc = INSTANCE;
        if (svc == null || svc.tts == null) return "{\"ok\":false,\"error\":{\"message\":\"TTS 未就绪\"}}";
        try {
            if (name != null && name.length() > 0) {
                Object target = findVoice(svc.tts, name);
                if (target != null) applyVoice(svc.tts, target);
            }
            svc.getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("ttsVoice", name == null ? "" : name).apply();
            return "{\"ok\":true,\"current\":\"" + esc(currentVoice()) + "\"}";
        } catch (Throwable t) {
            return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t.getMessage())) + "\"}}";
        }
    }

    /** 取预生成音频（base64），供把音频打进 APK 用 */
    /** 取某提示音的文案（与 renderCues 同一来源 ✓） */
    private static String cueText(String key) {
        try {
            SpeechService svc = INSTANCE;
            if (svc == null) return null;
            android.content.SharedPreferences p = svc.getSharedPreferences(PREFS, MODE_PRIVATE);
            String[] keys = { "connected", "disconnected", "driveOn", "driveOff", "sampleEnd" };
            String[] defs = { "设备已连接", "连接已断开", "辅助驾驶已开启", "辅助驾驶已关闭", "采样已结束" };
            for (int i = 0; i < keys.length; i++) if (keys[i].equals(key)) return p.getString("cue_" + key, defs[i]);
        } catch (Throwable e) { }
        return null;
    }
    private static byte[] readAll(java.io.File f) {
        try {
            byte[] b = new byte[(int) f.length()];
            java.io.FileInputStream in = new java.io.FileInputStream(f);
            int off = 0, n;
            while (off < b.length && (n = in.read(b, off, b.length - off)) > 0) off += n;
            in.close();
            return b;
        } catch (Throwable e) { return null; }
    }

    /** 诊断：返回"目录/文件名/存在/长度"，用于定位推送失败原因 ✓ */
    /** 2026-09-23：页面/浮窗请求本地播报（投屏连接/重连/停止、避让…）✓ */
    public static String sayLocal(String text) {
        if (text == null || text.length() == 0) return "{\"ok\":false,\"error\":{\"message\":\"empty\"}}";
        String t = text.length() > 120 ? text.substring(0, 120) : text;
        SpeechService s = INSTANCE;
        if (s == null) return "{\"ok\":false,\"error\":{\"message\":\"语音服务未启动（软件设置里开启语音提醒即可）\"}}";
        try { s.speak(t); } catch (Throwable e) { return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(e)) + "\"}}"; }
        return "{\"ok\":true,\"said\":\"" + esc(t) + "\"}";
    }

    public static String cueDebug(String key) {
        try {
            java.io.File dir = (INSTANCE != null) ? INSTANCE.getFilesDir() : null;
            if (dir == null) return "INSTANCE=null";
            java.io.File f = new java.io.File(dir, key + ".wav");
            return "dir=" + dir.getAbsolutePath() + " f=" + f.getName() + " exists=" + f.exists() + " len=" + f.length();
        } catch (Throwable e) { return "err=" + e; }
    }

    /** 原始音频字节（B9 推送用）：没有就先用本机 TTS 渲染 ✓ */
    public static byte[] cueBytes(String key) {
        try {
            java.io.File dir = (INSTANCE != null) ? INSTANCE.getFilesDir() : null;
            if (dir == null) return null;
            java.io.File f = new java.io.File(dir, key + ".wav");
            if (!f.exists() || f.length() < 512) {
                // ★ 不再整包 renderCues()（那会把已存在的好文件截成 0 字节 ✗）
                //   改为：按该 key 的提示词渲染到**临时文件**，校验大小后再用 ✓
                String text = cueText(key);
                java.io.File tmp = new java.io.File(INSTANCE.getCacheDir(), "push_" + key + ".wav");
                try { if (tmp.exists()) tmp.delete(); } catch (Throwable ignore) { }
                if (text != null && text.length() > 0 && INSTANCE.tts != null) synth(INSTANCE.tts, text, tmp.getAbsolutePath(), key);
                if (tmp.exists() && tmp.length() >= 512) return readAll(tmp);
                return null;
            }
            byte[] b = new byte[(int) f.length()];
            java.io.FileInputStream in = new java.io.FileInputStream(f);
            int off = 0, n;
            while (off < b.length && (n = in.read(b, off, b.length - off)) > 0) off += n;
            in.close();
            return b;
        } catch (Throwable e) { return null; }
    }

    public static String cueB64(String key) {
        SpeechService svc = INSTANCE;
        try {
            String path = svc.getFilesDir().getAbsolutePath() + "/" + key + ".wav";
            java.io.File f = new java.io.File(path);
            if (!f.exists()) return "{\"ok\":false,\"error\":{\"message\":\"还没生成：\" + key}}";
            java.io.FileInputStream in = new java.io.FileInputStream(f);
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            byte[] b = new byte[8192]; int n;
            while ((n = in.read(b)) > 0) bo.write(b, 0, n);
            in.close();
            return "{\"ok\":true,\"size\":" + bo.size() + ",\"b64\":\""
                 + android.util.Base64.encodeToString(bo.toByteArray(), android.util.Base64.NO_WRAP) + "\"}";
        } catch (Throwable t) { return "{\"ok\":false,\"error\":{\"message\":\"" + esc(String.valueOf(t)) + "\"}}"; }
    }

    private static String esc(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20) b.append(' ');
            else b.append(c);
        }
        return b.toString();
    }

    @Override
    public void onCreate() {
        super.onCreate();
        INSTANCE = this;
        Log.i(TAG, "service created");
        initTts(0);                                   // ★ 独立方法 + 失败重试（还债：失败不再被吞）
        running = true;
        poller = new Thread(new Runnable() { public void run() { loop(); } }, "c3-voice-poll");
        poller.setDaemon(true);
        poller.start();
    }

    /** 初始化 TTS。Android 上启动过早常见 onInit=ERROR → 记录到 APP 日志并重试（最多 3 次/间隔 3 秒）。 */
    private void initTts(final int attempt) {
        try { Logs.add("VOICE", "TTS 初始化尝试 #" + attempt); } catch (Throwable ignore) { }
        try {
            tts = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
                public void onInit(int status) {
                    try { Logs.add("VOICE", "TTS onInit status=" + status + (status == TextToSpeech.SUCCESS ? " 成功" : " 失败")); } catch (Throwable ignore) { }
                    if (status == TextToSpeech.SUCCESS) {
                        int r = tts.setLanguage(Locale.CHINA);
                        ttsReady = true;
                        toneFallback = false;
                        Log.i(TAG, "tts ready, setLanguage=" + r);
                        try {
                            String vn = getSharedPreferences(PREFS, MODE_PRIVATE).getString("ttsVoice", "");
                            if (vn != null && vn.length() > 0 && !voicesOf(tts).isEmpty()) {
                                Object tv = findVoice(tts, vn);
                                if (tv != null && applyVoice(tts, tv)) Log.i(TAG, "voice restored: " + vn);
                            }
                        } catch (Throwable ignore) { }
                        try {
                            String rs = getSharedPreferences(PREFS, MODE_PRIVATE).getString("ttsRate", "");
                            String ps = getSharedPreferences(PREFS, MODE_PRIVATE).getString("ttsPitch", "");
                            if (rs.length() > 0) tts.setSpeechRate(Float.parseFloat(rs));
                            if (ps.length() > 0) tts.setPitch(Float.parseFloat(ps));
                        } catch (Throwable ignore) { }
                        flushOne();
                    } else {
                        Log.w(TAG, "tts init failed status=" + status);
                        toneFallback = true;                                  // 先保底能听见
                        flushOne();
                        if (attempt < 3) {
                            try {
                                new android.os.Handler(getMainLooper()).postDelayed(new Runnable() {
                                    public void run() { try { initTts(attempt + 1); } catch (Throwable ignore) { } }
                                }, 3000);
                            } catch (Throwable ignore) { }
                        }
                    }
                }
            });
        } catch (Throwable e) {
            try { Logs.add("VOICE", "TTS 构造失败: " + e); } catch (Throwable ignore) { }
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            String say = intent.getStringExtra("say");
            if (say != null && say.length() > 0) speak(say);
        }
        return START_STICKY;
    }

    private void loop() {
        while (running) {
            try { pollOnce(); } catch (Throwable t) { Log.w(TAG, "poll: " + t); }
            // ★ 可被 nudge 立即唤醒（2026-09-21 用户反馈：接管/退出语音有延迟）
            for (long w = 0; w < POLL_MS; w += 100) {
                if (NUDGE) { NUDGE = false; break; }
                try { Thread.sleep(100); } catch (InterruptedException e) { return; }
            }
        }
    }

    private void pollOnce() throws Exception {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        int lp = prefs.getInt("localPort", 0);
        String host = lp > 0 ? "127.0.0.1" : prefs.getString("host", "127.0.0.1");
        int port = lp > 0 ? lp : prefs.getInt("port", 3081);
        if (host == null || host.length() == 0) host = "127.0.0.1";
        long since = prefs.getLong("voiceSeen", 0L);
        String tok = prefs.getString("token", "");
        String q = "/api/voice/next?since=" + since + ((tok != null && tok.length() > 0) ? ("&token=" + tok) : "");
        URL u = new URL("http://" + host + ":" + port + q);
        HttpURLConnection c = (HttpURLConnection) u.openConnection();
        c.setConnectTimeout(4000);
        c.setReadTimeout(6000);
        try {
            int code = c.getResponseCode();
            if (code != 200) { Log.i(TAG, "http " + code); return; }
            StringBuilder sb = new StringBuilder();
            BufferedReader br = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
            String line;
            while ((line = br.readLine()) != null) sb.append(line);
            br.close();
            String body = sb.toString();
            List<String> texts = extractTexts(body);
            for (int i = 0; i < texts.size(); i++) speak(texts.get(i));
            long last = extractLong(body, "last");
            if (last > since) prefs.edit().putLong("voiceSeen", last).apply();
        } finally {
            try { c.disconnect(); } catch (Throwable ignore) { }
        }
    }

    /** 播报音频包：优先"生成语音包"产出的 filesDir/<key>.wav，其次内置 assets/voice/<key>.wav */
    private static final String[][] CUES = {
        {"connected", "设备已连接"}, {"disconnected", "连接已断开"},
        {"driveOn", "辅助驾驶已开启"}, {"driveOff", "辅助驾驶已关闭"},
        {"sampleEnd", "采样已结束"}
    };
    private static android.media.MediaPlayer CUE_MP;
    private static java.util.HashMap<String, String> CUE_MAP;

    private static void loadCueMap(android.content.Context c) {
        if (CUE_MAP != null) return;
        CUE_MAP = new java.util.HashMap<String, String>();
        for (String[] x : CUES) CUE_MAP.put(x[1], x[0]);
        try {
            java.io.BufferedReader r = new java.io.BufferedReader(new java.io.InputStreamReader(
                    new java.io.FileInputStream(c.getFilesDir().getAbsolutePath() + "/voice-map.txt"), "UTF-8"));
            String line;
            while ((line = r.readLine()) != null) {
                int t = line.indexOf('\t');
                if (t > 0) CUE_MAP.put(line.substring(t + 1), line.substring(0, t));
            }
            r.close();
        } catch (Throwable ignore) { }
    }

    private boolean playCueAudio(String text) {
        loadCueMap(this);
        String key = CUE_MAP.get(text);
        if (key == null) return false;
        java.io.File local = new java.io.File(getFilesDir(), key + ".wav");
        java.io.File tmp = new java.io.File(getCacheDir(), "cue_" + key + ".wav");
        try {
            if (!local.exists() || local.length() < 512) {
                // ★ 每次都从包内资源重新拷贝（2026-09-21 修复"语音提示没改变"）：
                //   以前缓存存在就复用 → APK 换了新录音，车机还在放旧缓存
                java.io.InputStream in = getAssets().open("voice/" + key + ".wav");
                java.io.FileOutputStream out = new java.io.FileOutputStream(tmp);
                byte[] b = new byte[8192]; int n;
                while ((n = in.read(b)) > 0) out.write(b, 0, n);
                in.close(); out.close();
                local = tmp;
            }
            if (CUE_MP != null) { try { CUE_MP.release(); } catch (Throwable ignore) { } CUE_MP = null; }
            CUE_MP = new android.media.MediaPlayer();
            CUE_MP.setDataSource(local.getAbsolutePath());
            CUE_MP.prepare(); CUE_MP.start();
            Log.i(TAG, "play cue audio " + local.getAbsolutePath() + " (" + local.length() + "B)");
            return true;
        } catch (Throwable t) {
            Log.i(TAG, "cue audio 失败 key=" + key + " err=" + t);
            return false;
        }
    }

    private static int synth(TextToSpeech t, String text, String path, String key) {
        java.io.File f = new java.io.File(path);
        try {
            java.lang.reflect.Method m = TextToSpeech.class.getMethod("synthesizeToFile",
                    CharSequence.class, android.os.Bundle.class, java.io.File.class, String.class);
            android.os.Bundle bun = new android.os.Bundle();
            try { bun.putInt("stream", Integer.parseInt(stream())); } catch (Throwable ignore) { }
            return (Integer) m.invoke(t, text, bun, f, key);
        } catch (Throwable t1) {
            try {
                java.lang.reflect.Method m2 = TextToSpeech.class.getMethod("synthesizeToFile",
                        String.class, java.util.HashMap.class, String.class);
                return (Integer) m2.invoke(t, text, params(), path);
            } catch (Throwable t2) { return -1; }
        }
    }

    private static String jsonStr(String s, int from) {
        try {
            int a = s.indexOf('"', from); if (a < 0) return null;
            StringBuilder b = new StringBuilder();
            for (int i = a + 1; i < s.length(); i++) {
                char c = s.charAt(i);
                if (c == '\\') { i++; if (i < s.length()) b.append(s.charAt(i)); continue; }
                if (c == '"') return b.toString();
                b.append(c);
            }
        } catch (Throwable ignore) { }
        return null;
    }

    /** 生成语音包：按页面传来的当前提示词列表生成（自定义文本也能出声） */
    public static String renderItems(String body) {
        SpeechService svc = INSTANCE;
        if (svc == null || svc.tts == null) return "{\"ok\":false,\"error\":{\"message\":\"TTS 未就绪\"}}";
        StringBuilder b = new StringBuilder("{\"ok\":true,\"items\":[");
        StringBuilder map = new StringBuilder();
        int i = 0, ok = 0, n = 0;
        while (true) {
            int k = body.indexOf("\"key\":", i); if (k < 0) break;
            int t = body.indexOf("\"text\":", k); if (t < 0) break;
            String kk = jsonStr(body, k + 6), tt = jsonStr(body, t + 7);
            i = t + 7;
            if (kk == null || tt == null) continue;
            String path = svc.getFilesDir().getAbsolutePath() + "/" + kk + ".wav";
            int r = synth(svc.tts, tt, path, kk);
            if (n > 0) b.append(',');
            b.append("{\"key\":\"").append(kk).append("\",\"r\":").append(r).append("}");
            n++;
            if (r == 0) { ok++; map.append(kk).append('\t').append(tt).append('\n'); }
        }
        try {
            java.io.FileOutputStream o = new java.io.FileOutputStream(svc.getFilesDir().getAbsolutePath() + "/voice-map.txt");
            o.write(map.toString().getBytes("UTF-8")); o.close();
            CUE_MAP = null;
        } catch (Throwable ignore) { }
        b.append("],\"okCount\":").append(ok).append(",\"total\":").append(n).append("}");
        return b.toString();
    }

    /** 兼容旧调用：用内置默认语句生成 */
    public static String renderCues() {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < CUES.length; i++) {
            if (i > 0) b.append(',');
            b.append("{\"key\":\"").append(CUES[i][0]).append("\",\"text\":\"").append(esc(CUES[i][1])).append("\"}");
        }
        return renderItems("{\"items\":[" + b + "]}");
    }

    private void speak(String text) {
        if (playCueAudio(text)) return;
        if (text == null || text.trim().length() == 0) return;
        Log.i(TAG, "speak: " + text);
        synchronized (pending) {
            pending.addLast(text.trim());
        }
        flushOne();
    }

    private void flushOne() {
        if (!ttsReady && !toneFallback) return;
        String t;
        synchronized (pending) { t = pending.pollFirst(); }
        if (t == null) return;
        if (ttsReady) {
            try { tts.speak(t, TextToSpeech.QUEUE_ADD, params()); Log.i(TAG, "tts speak queued stream=" + stream()); return; }
            catch (Throwable e) { Log.w(TAG, "speak failed: " + e); }
        }
        playTone();
    }

    /** 系统默认通知音（TTS 不可用时的兜底，保证"有声音"）。 */
    private void playTone() {
        try {
            Uri u = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
            Ringtone r = RingtoneManager.getRingtone(this, u);
            if (r != null) { r.play(); Log.i(TAG, "tone played"); }
        } catch (Throwable e) { Log.w(TAG, "tone failed: " + e); }
    }

    @Override
    public void onDestroy() {
        INSTANCE = null;
        running = false;
        try { if (tts != null) { tts.stop(); tts.shutdown(); } } catch (Throwable ignore) { }
        super.onDestroy();
        Log.i(TAG, "service destroyed");
    }

    /** 极简取 "last":N（这套精简 android.jar 没有 org.json，所以自带小解析）。 */
    private static long extractLong(String s, String key) {
        int i = s.indexOf("\"" + key + "\":");
        if (i < 0) return -1;
        i += key.length() + 3;
        int j = i;
        while (j < s.length() && (Character.isDigit(s.charAt(j)) || s.charAt(j) == '-')) j++;
        try { return Long.parseLong(s.substring(i, j)); } catch (Throwable e) { return -1; }
    }

    /** 取所有 text 字段（含引号/反斜杠/换行/unicode 反转义）。 */
    private static List<String> extractTexts(String s) {
        List<String> out = new ArrayList<String>();
        int i = 0;
        while (true) {
            int k = s.indexOf("\"text\":\"", i);
            if (k < 0) break;
            int p = k + 8;
            StringBuilder sb = new StringBuilder();
            boolean esc = false;
            while (p < s.length()) {
                char ch = s.charAt(p);
                if (esc) {
                    if (ch == 'n') sb.append('\n');
                    else if (ch == 't') sb.append('\t');
                    else if (ch == 'u' && p + 4 < s.length()) {
                        try { sb.append((char) Integer.parseInt(s.substring(p + 1, p + 5), 16)); } catch (Throwable ignore) { }
                        p += 4;
                    } else sb.append(ch);
                    esc = false;
                } else if (ch == '\\') esc = true;
                else if (ch == '"') break;
                else sb.append(ch);
                p++;
            }
            out.add(sb.toString());
            i = p + 1;
        }
        return out;
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
