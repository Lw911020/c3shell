package com.padagent.c3shell;

/** 把 Java/网络英文异常翻成人话（2026-09-21 用户反馈：异常提示是英文）。 */
public class Errs {
    public static String zh(String msg) {
        if (msg == null || msg.length() == 0) return "未知错误";
        String m = msg;
        if (m.contains("Auth fail") || m.contains("auth fail")) return "认证失败：设备不接受这把密钥（换一把内置密钥，或用「从手机选择密钥…」导入你设备上已授权的私钥；用户名通常是 comma）";
        if (m.contains("Auth cancel")) return "认证被取消（设备可能不支持这种方式）";
        if (m.contains("Connection refused")) return "连接被拒绝：地址/端口不对，或设备没开 SSH";
        if (m.contains("No route to host")) return "网络不可达：和 C3 设备不在同一网络，或地址已变";
        if (m.contains("ConnectException")) return "连不上：请检查地址、端口、以及是否同一 Wi-Fi";
        if (m.contains("UnknownHost")) return "域名解析失败";
        if (m.contains("timeout") || m.contains("timed out")) return "连接超时（设备没响应）";
        if (m.contains("Socket closed")) return "连接被关闭";
        if (m.contains("invalid privatekey") || m.contains("invalid key") || m.contains("key is invalid")) return "私钥格式不对（可换一把，或改用 PPK 自动转换）";
        if (m.contains("Host key verification")) return "主机指纹校验失败";
        if (m.contains("Permission denied")) return "权限不足（设备拒绝了该操作）";
        return "操作失败：" + m;
    }
}
