-- C3 控制台 · 服务端表结构（卡密/设备绑定/反馈/心跳统计）
-- 放进你现有的 renren-admin 数据库即可（MySQL 5.7+/8）

CREATE TABLE IF NOT EXISTS app_license (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  code         VARCHAR(64)  NOT NULL UNIQUE COMMENT '卡密',
  plan         VARCHAR(32)  DEFAULT 'pro' COMMENT '套餐名',
  features     VARCHAR(255) DEFAULT 'ai,routes,feedback' COMMENT '功能，逗号分隔',
  device_id    VARCHAR(64)  DEFAULT NULL COMMENT '绑定的设备号（一码一机）',
  bind_at      DATETIME     DEFAULT NULL,
  expires_at   DATETIME     DEFAULT NULL COMMENT '到期时间，NULL=永久',
  enabled      TINYINT      DEFAULT 1,
  note         VARCHAR(255) DEFAULT '',
  created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_heartbeat (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id    VARCHAR(64) NOT NULL,
  app_version  VARCHAR(32),
  os_version   VARCHAR(32),
  model        VARCHAR(64),
  display_mode VARCHAR(16),
  host_count   INT DEFAULT 0,
  feature      VARCHAR(64) COMMENT '最近用到的功能（可空）',
  ts           DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_dev (device_id, ts),
  INDEX idx_ts (ts)
);

CREATE TABLE IF NOT EXISTS app_feedback (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id    VARCHAR(64),
  app_version  VARCHAR(32),
  contact      VARCHAR(128),
  text         TEXT,
  image_path   VARCHAR(255) COMMENT '截图/附件的相对路径',
  log_path     VARCHAR(255) COMMENT '日志的相对路径',
  handled      TINYINT DEFAULT 0,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_dev (device_id), INDEX idx_ts (created_at)
);

-- 建议：先插几张测试卡密
-- INSERT INTO app_license(code, plan) VALUES ('C3-TEST-0001','pro'),('C3-TEST-0002','pro');

-- 赞赏登记（APP「赞赏」页用户回填；金额需 >20）
CREATE TABLE IF NOT EXISTS app_appreciate (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id   VARCHAR(64),
  app_version VARCHAR(32),
  amount      DECIMAL(10,2),
  contact     VARCHAR(255),
  handled     TINYINT(1) DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
