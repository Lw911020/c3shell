-- C3 控制台 · 表结构（PostgreSQL 版，对应云开发 SQL 型数据库）
-- 用法：云开发控制台 → PostgreSQL 管理 → SQL 查询/执行窗口 → 整段粘贴执行
--       （或本地用连接串 psql 执行也行）

CREATE TABLE IF NOT EXISTS app_license (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(64) UNIQUE NOT NULL,
  plan        VARCHAR(32) DEFAULT 'pro',
  features    VARCHAR(255) DEFAULT 'ai,routes,feedback',
  device_id   VARCHAR(64),
  bind_at     TIMESTAMP,
  expires_at  TIMESTAMP,
  enabled     BOOLEAN DEFAULT TRUE,
  note        VARCHAR(255) DEFAULT '',
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app_heartbeat (
  id          BIGSERIAL PRIMARY KEY,
  device_id   VARCHAR(64) NOT NULL,
  app_version VARCHAR(32),
  os_version  VARCHAR(32),
  model       VARCHAR(64),
  display_mode VARCHAR(16),
  host_count  INT DEFAULT 0,
  feature     VARCHAR(64),
  ts          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hb_dev ON app_heartbeat(device_id);
CREATE INDEX IF NOT EXISTS idx_hb_ts  ON app_heartbeat(ts);

CREATE TABLE IF NOT EXISTS app_feedback (
  id          BIGSERIAL PRIMARY KEY,
  device_id   VARCHAR(64),
  app_version VARCHAR(32),
  contact     VARCHAR(128),
  text        TEXT,
  image_url   VARCHAR(255),
  log_text    TEXT,
  handled     BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW()
);

-- 测试卡密
INSERT INTO app_license(code, plan) VALUES ('C3-TEST-0001','pro')
  ON CONFLICT (code) DO NOTHING;

-- 赞赏登记（APP「赞赏」页用户回填；金额需 >20）
CREATE TABLE IF NOT EXISTS app_appreciate (
  id          BIGSERIAL PRIMARY KEY,
  device_id   TEXT,
  app_version TEXT,
  amount      NUMERIC(10,2),
  contact     TEXT,
  handled     BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
