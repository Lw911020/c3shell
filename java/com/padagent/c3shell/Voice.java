package com.padagent.c3shell;

import java.util.ArrayList;
import java.util.List;

/** APP 本地语音队列（独立版）：APP 自己产生提示（连接断开、辅助驾驶开/关…），
 *  SpeechService 轮询 /api/voice/next 取走并 TTS 播报。 */
public class Voice {
    public static class Item {
        public int id; public String text; public String why; public long ts = System.currentTimeMillis();
    }
    private final List<Item> items = new ArrayList<Item>();
    // ★ id 用"秒级时间戳"起步：APP 重启后队列是新的，而 SpeechService 里存着上次的 since。
    //   若 id 从 1 重新开始，since 会永远大于新 id → 新消息再也播不出来（2026-09-21 实测踩到）。
    private int seq = (int) (System.currentTimeMillis() / 1000);
    private static final int MAX = 200;

    public synchronized int say(String text, String why) {
        Item it = new Item();
        it.id = ++seq;
        it.text = text;
        it.why = why == null ? "app" : why;
        items.add(it);
        while (items.size() > MAX) items.remove(0);
        try { SpeechService.nudge(); } catch (Throwable ignore) { }   // 入队即唤醒播放线程
        return it.id;
    }

    public synchronized String nextJson(int since) {
        StringBuilder b = new StringBuilder("{\"ok\":true,\"items\":[");
        boolean first = true;
        for (Item it : items) {
            if (it.id <= since) continue;
            if (!first) b.append(',');
            first = false;
            b.append("{\"id\":").append(it.id).append(",\"ts\":").append(it.ts)
             .append(",\"why\":\"").append(Ssh.esc(it.why)).append("\",\"text\":\"").append(Ssh.esc(it.text)).append("\"}");
        }
        return b.append("],\"last\":").append(seq).append('}').toString();
    }

    public synchronized String stateJson() {
        int last = seq;
        int count = items.size();
        StringBuilder tail = new StringBuilder("[");
        int from = Math.max(0, items.size() - 5);
        for (int i = from; i < items.size(); i++) {
            if (i > from) tail.append(',');
            Item it = items.get(i);
            tail.append("{\"id\":").append(it.id).append(",\"ts\":").append(it.ts)
                .append(",\"why\":\"").append(Ssh.esc(it.why)).append("\",\"text\":\"").append(Ssh.esc(it.text)).append("\"}");
        }
        tail.append(']');   // 补上数组闭合（否则 state JSON 不合法）
        return "{\"ok\":true,\"last\":" + last + ",\"count\":" + count + ",\"watching\":true,\"tail\":" + tail + "}";
    }
}
