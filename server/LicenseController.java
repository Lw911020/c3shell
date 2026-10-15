package com.renren.admin.modules.app;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import javax.servlet.http.HttpServletRequest;
import java.io.File;
import java.text.SimpleDateFormat;
import java.util.*;

/**
 * C3 控制台 服务端接口（卡密校验 / 设备绑定 / 问题反馈 / 在线心跳）
 *
 * 放进 renren-admin（或任意 Spring Boot 项目）即可，路径约定与 APP 端一致：
 *   POST /api/v1/app/license/verify   {"code","device","version","app"}
 *       成功 {"ok":true,"plan","expiresAt","features":[...]}
 *       失败 {"ok":false,"error":{"message":"…"}}
 *   POST /api/v1/app/feedback         multipart：text, contact, device, version, image?, log?
 *   POST /api/v1/app/heartbeat        {"device","version","os","model","mode","hosts","feature"}
 *   后台统计：GET /api/v1/app/stats    → 日活/在线/版本分布/功能使用
 *
 * 说明：这里用最朴素的 JdbcTemplate 写法（方便直接跑）；表结构见 schema.sql。
 *      Spring Boot 默认已带 Jackson；若你的项目用 FastJSON，把 Map 返回换成你自己的封装即可。
 */
@RestController
@RequestMapping("/api/v1/app")
public class LicenseController {

    private final org.springframework.jdbc.core.JdbcTemplate jdbc;
    public LicenseController(org.springframework.jdbc.core.JdbcTemplate jdbc) { this.jdbc = jdbc; }

    private static String s(Object o) { return o == null ? "" : String.valueOf(o).trim(); }

    /** 卡密校验 + 设备绑定（一码一机） */
    @PostMapping("/license/verify")
    public Map<String, Object> verify(@RequestBody Map<String, Object> body) {
        String code = s(body.get("code")).toUpperCase();
        String device = s(body.get("device"));
        Map<String, Object> out = new LinkedHashMap<>();
        try {
            if (code.length() < 6 || device.length() < 4) return fail("参数不完整");
            List<Map<String, Object>> rows = jdbc.queryForList(
                    "SELECT * FROM app_license WHERE code=? AND enabled=1 LIMIT 1", code);
            if (rows.isEmpty()) return fail("卡密无效");
            Map<String, Object> r = rows.get(0);
            String bound = s(r.get("device_id"));
            Object exp = r.get("expires_at");
            if (exp != null) {
                Date d = (Date) exp;
                if (d.getTime() < System.currentTimeMillis()) return fail("卡密已过期");
            }
            if (bound.length() == 0) {                       // 首次：绑定这台设备
                jdbc.update("UPDATE app_license SET device_id=?, bind_at=NOW() WHERE id=?", device, r.get("id"));
            } else if (!bound.equals(device)) {              // 已绑别的设备：拒绝（可在后台解绑）
                return fail("卡密已绑定其它设备（如需换机请在后台解绑）");
            }
            out.put("ok", true);
            out.put("plan", s(r.get("plan")));
            out.put("expiresAt", exp == null ? "" : new SimpleDateFormat("yyyy-MM-dd").format((Date) exp));
            out.put("features", Arrays.asList(s(r.get("features")).split(",")));
            return out;
        } catch (Exception e) {
            return fail("服务器异常：" + e.getClass().getSimpleName());
        }
    }

    /** 问题反馈（文字 + 可选截图/日志） */
    @PostMapping("/feedback")
    public Map<String, Object> feedback(@RequestParam Map<String, String> p,
                                        @RequestParam(value = "image", required = false) MultipartFile image,
                                        @RequestParam(value = "log", required = false) MultipartFile log) {
        try {
            String dev = s(p.get("device")), ts = new SimpleDateFormat("yyyyMMdd-HHmmss").format(new Date());
            String dir = "/data/c3-feedback/" + ts + "_" + (dev.length() > 12 ? dev.substring(dev.length() - 8) : dev);
            String ip = null, lp = null;
            File d = new File(dir); d.mkdirs();
            if (image != null && !image.isEmpty()) { File f = new File(d, "shot.png"); image.transferTo(f); ip = f.getAbsolutePath(); }
            if (log != null && !log.isEmpty())     { File f = new File(d, "app.log");  log.transferTo(f);  lp = f.getAbsolutePath(); }
            jdbc.update("INSERT INTO app_feedback(device_id,app_version,contact,text,image_path,log_path) VALUES(?,?,?,?,?,?)",
                    dev, s(p.get("version")), s(p.get("contact")), s(p.get("text")), ip, lp);
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true); out.put("saved", dir);
            return out;
        } catch (Exception e) {
            return fail("反馈保存失败：" + e.getClass().getSimpleName());
        }
    }

    /** 在线心跳（用户统计用） */
    @PostMapping("/heartbeat")
    public Map<String, Object> heartbeat(@RequestBody Map<String, Object> body, HttpServletRequest req) {
        try {
            jdbc.update("INSERT INTO app_heartbeat(device_id,app_version,os_version,model,display_mode,host_count,feature) VALUES(?,?,?,?,?,?,?)",
                    s(body.get("device")), s(body.get("version")), s(body.get("os")), s(body.get("model")),
                    s(body.get("mode")), body.get("hosts") == null ? 0 : Integer.parseInt(s(body.get("hosts"))),
                    s(body.get("feature")));
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            return out;
        } catch (Exception e) { return fail("心跳失败"); }
    }

    /** 后台统计（简单版：日活 / 近 5 分钟在线 / 版本分布 / 功能使用） */
    @GetMapping("/stats")
    public Map<String, Object> stats() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("online5m", jdbc.queryForObject("SELECT COUNT(DISTINCT device_id) FROM app_heartbeat WHERE ts > DATE_SUB(NOW(), INTERVAL 5 MINUTE)", Integer.class));
        out.put("dau", jdbc.queryForObject("SELECT COUNT(DISTINCT device_id) FROM app_heartbeat WHERE DATE(ts)=CURDATE()", Integer.class));
        out.put("devices", jdbc.queryForObject("SELECT COUNT(DISTINCT device_id) FROM app_heartbeat", Integer.class));
        out.put("versions", jdbc.queryForList("SELECT app_version v, COUNT(DISTINCT device_id) c FROM app_heartbeat GROUP BY v ORDER BY c DESC"));
        out.put("features", jdbc.queryForList("SELECT feature f, COUNT(*) c FROM app_heartbeat WHERE feature<>'' GROUP BY f ORDER BY c DESC LIMIT 20"));
        out.put("feedbackOpen", jdbc.queryForObject("SELECT COUNT(*) FROM app_feedback WHERE handled=0", Integer.class));
        out.put("licenseBound", jdbc.queryForObject("SELECT COUNT(*) FROM app_license WHERE device_id IS NOT NULL", Integer.class));
        return out;
    }

    private Map<String, Object> fail(String msg) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("message", msg);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", false); out.put("error", e);
        return out;
    }
}
