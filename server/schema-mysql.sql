-- C3 控制台 · RDS MySQL 建表（在 RDS 的 SQL 控制台 / phpMyAdmin 里整段执行，可重复执行 ✓）
-- 4 张表：卡密 / 心跳 / 反馈 / 赞赏；字符集统一 utf8mb4（中文和 emoji 都不会乱码）

CREATE TABLE IF NOT EXISTS app_license (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  plan VARCHAR(32) DEFAULT 'pro',
  features VARCHAR(255) DEFAULT 'ai,routes,feedback',
  device_id VARCHAR(64) NULL,
  bind_at DATETIME NULL,
  expires_at DATETIME NULL,
  enabled TINYINT(1) DEFAULT 1,
  note VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_heartbeat (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NOT NULL,
  app_version VARCHAR(32) NULL,
  os_version VARCHAR(32) NULL,
  model VARCHAR(64) NULL,
  display_mode VARCHAR(16) NULL,
  host_count INT DEFAULT 0,
  feature VARCHAR(64) NULL,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_hb_dev (device_id),
  KEY idx_hb_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_feedback (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NULL,
  app_version VARCHAR(32) NULL,
  contact VARCHAR(128) NULL,
  text TEXT NULL,
  image_url VARCHAR(255) NULL,
  image_b64 MEDIUMTEXT NULL,
  log_text MEDIUMTEXT NULL,
  handled TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_appreciate (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NULL,
  app_version VARCHAR(32) NULL,
  amount DECIMAL(10,2) NULL,
  contact VARCHAR(128) NULL,
  handled TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 一条测试卡密（已存在则跳过）
INSERT INTO app_license(code, plan, features, enabled, note) VALUES ('C3-TEST-0001', 'pro', 'ai,routes,feedback', 1, '测试')
  ON DUPLICATE KEY UPDATE code = code;

-- 自检：应看到 4 张表
SHOW TABLES LIKE 'app_%';
SELECT code, plan, device_id, enabled FROM app_license;
