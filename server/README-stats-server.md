# c3shell 使用统计后端（部署指南）

## 它统计什么
只统计：**随机设备ID、APP 版本、Android 版本、心跳时间**。不采集任何个人信息、不采集车辆数据。
APP 每 10 分钟发一次心跳；**5 分钟内有心跳算在线**。

## 部署（任意一台有公网 IP 的机器，1 分钟）
```bash
# 1) 上传这一个文件即可（零依赖，Python3 标准库）
scp server/stats-server.py root@你的服务器:/opt/

# 2) 常驻运行（systemd）
cat >/etc/systemd/system/c3shell-stats.service <<'SVC'
[Unit]
Description=c3shell stats
[Service]
ExecStart=/usr/bin/python3 /opt/stats-server.py 8099
Restart=always
[Install]
WantedBy=multi-user.target
SVC
systemctl enable --now c3shell-stats

# 3) 放行端口（示例：ufw）
ufw allow 8099/tcp
```

## 看统计
浏览器打开 `http://你的服务器:8099/` → **总设备数 / 在线(5分钟) / 10分钟 / 24小时活跃 + 设备列表**
（或 `GET /stats` 取 JSON）

## 让 APP 上报
在 APP 所在设备执行一次配置（或让我用 adb 配置）：
```bash
curl -X POST -H 'content-type: application/json' \
     -d '{"url":"http://你的服务器:8099/beat","enabled":true}' \
     http://127.0.0.1:3081/api/stats
```
自检：`curl http://127.0.0.1:3081/api/stats/beat`（返回 code=200 即通）

## 关闭统计
`curl -X POST -d '{"enabled":false}' http://127.0.0.1:3081/api/stats`
