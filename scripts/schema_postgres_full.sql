-- Full PostgreSQL schema for Knowledge Platform (test/dev).
-- Compatible with Postgres features used in the codebase: UUID, JSON, TEXT[], GIN FTS.
--
-- Optional database creation (run as a superuser):
--   CREATE DATABASE knowledge_platform;
--
-- Then connect to the database and run the DDL below.

BEGIN;

-- Core users/groups (ACL)
CREATE TABLE IF NOT EXISTS users (
  id            VARCHAR(255) PRIMARY KEY,
  email         VARCHAR(255) UNIQUE NOT NULL,
  display_name  VARCHAR(255),
  password_hash VARCHAR(255),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
  role          VARCHAR(50) NOT NULL DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS groups (
  id   VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS user_groups (
  user_id  VARCHAR(255) NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
  group_id VARCHAR(255) NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS user_group_overrides (
  user_id    VARCHAR(255) NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
  group_id   VARCHAR(255) NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  effect     VARCHAR(10)  NOT NULL DEFAULT 'deny',
  reason     TEXT,
  created_by VARCHAR(255),
  created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP    NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_user_group_overrides_group_id ON user_group_overrides (group_id);

-- Knowledge documents + chunks
CREATE TABLE IF NOT EXISTS documents (
  id           UUID PRIMARY KEY,
  source       VARCHAR(50)  NOT NULL,
  source_id    VARCHAR(255) NOT NULL,
  title        TEXT         NOT NULL,
  content      TEXT         NOT NULL,
  url          TEXT,
  author       VARCHAR(255),
  created_at   TIMESTAMP    NOT NULL,
  updated_at   TIMESTAMP    NOT NULL,
  metadata     JSON         NOT NULL DEFAULT '{}'::json,
  permissions  TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
  entities     TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
  workspace_id VARCHAR(255)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_source_source_id ON documents (source, source_id);
CREATE INDEX IF NOT EXISTS idx_documents_workspace_id ON documents (workspace_id);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents (source);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents (updated_at);

CREATE TABLE IF NOT EXISTS user_document_overrides (
  user_id    VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  effect     VARCHAR(10)  NOT NULL DEFAULT 'deny',
  reason     TEXT,
  created_by VARCHAR(255),
  created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP    NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, document_id)
);
CREATE INDEX IF NOT EXISTS idx_user_document_overrides_document_id ON user_document_overrides (document_id);

CREATE TABLE IF NOT EXISTS document_permissions (
  document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  group_id    VARCHAR(255) NOT NULL REFERENCES groups(id)   ON DELETE CASCADE,
  PRIMARY KEY (document_id, group_id)
);

CREATE TABLE IF NOT EXISTS chunks (
  id          UUID PRIMARY KEY,
  document_id UUID     NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  content     TEXT     NOT NULL,
  chunk_index INTEGER  NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING GIN (to_tsvector('simple', content));

-- Binary assets (images) + links to chunks
CREATE TABLE IF NOT EXISTS document_assets (
  id          UUID PRIMARY KEY,
  document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  source      VARCHAR(50) NOT NULL,
  source_ref  TEXT,
  kind        VARCHAR(20) NOT NULL DEFAULT 'image',
  filename    TEXT,
  mime_type   VARCHAR(100),
  bytes       INTEGER,
  sha256      VARCHAR(64),
  local_path  TEXT        NOT NULL,
  caption     TEXT,
  ocr_text    TEXT,
  width       INTEGER,
  height      INTEGER,
  meta        JSON        NOT NULL DEFAULT '{}'::json,
  created_at  TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_assets_document_id ON document_assets (document_id);
CREATE INDEX IF NOT EXISTS ix_document_assets_sha256 ON document_assets (sha256);
CREATE INDEX IF NOT EXISTS ix_document_assets_source ON document_assets (source);

CREATE TABLE IF NOT EXISTS chunk_assets (
  chunk_id UUID NOT NULL REFERENCES chunks(id)           ON DELETE CASCADE,
  asset_id UUID NOT NULL REFERENCES document_assets(id)  ON DELETE CASCADE,
  PRIMARY KEY (chunk_id, asset_id)
);
CREATE INDEX IF NOT EXISTS ix_chunk_assets_chunk_id ON chunk_assets (chunk_id);
CREATE INDEX IF NOT EXISTS ix_chunk_assets_asset_id ON chunk_assets (asset_id);

-- Graph edges between documents
CREATE TABLE IF NOT EXISTS document_links (
  id                 UUID PRIMARY KEY,
  source_document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  target_document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  kind               VARCHAR(20) NOT NULL DEFAULT 'explicit',
  relation           VARCHAR(50) NOT NULL DEFAULT 'references',
  weight             DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  evidence           TEXT,
  created_at         TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_links_source   ON document_links (source_document_id);
CREATE INDEX IF NOT EXISTS ix_document_links_target   ON document_links (target_document_id);
CREATE INDEX IF NOT EXISTS ix_document_links_kind     ON document_links (kind);
CREATE INDEX IF NOT EXISTS ix_document_links_relation ON document_links (relation);
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_links_tuple
  ON document_links (source_document_id, target_document_id, kind, relation);

-- Entities + relations
CREATE TABLE IF NOT EXISTS entities (
  id              UUID PRIMARY KEY,
  name            VARCHAR(255) NOT NULL,
  normalized_name VARCHAR(255),
  entity_type     VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities (name);
CREATE INDEX IF NOT EXISTS idx_entities_normalized_name ON entities (normalized_name);

CREATE TABLE IF NOT EXISTS entity_relations (
  id            UUID PRIMARY KEY,
  source_id     UUID REFERENCES entities(id),
  target_id     UUID REFERENCES entities(id),
  relation_type VARCHAR(100)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relations_triplet
  ON entity_relations (source_id, target_id, relation_type);

CREATE TABLE IF NOT EXISTS document_entities (
  document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  entity_id   UUID        NOT NULL REFERENCES entities(id)  ON DELETE CASCADE,
  entity_type VARCHAR(100) NOT NULL,
  PRIMARY KEY (document_id, entity_id)
);

CREATE TABLE IF NOT EXISTS entity_aliases (
  entity_id         UUID         NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  normalized_alias  VARCHAR(255) NOT NULL,
  alias_value       VARCHAR(255) NOT NULL,
  alias_type        VARCHAR(100) NOT NULL DEFAULT 'identity',
  alias_strength    INTEGER      NOT NULL DEFAULT 1,
  PRIMARY KEY (entity_id, normalized_alias)
);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_normalized_alias ON entity_aliases (normalized_alias);

-- Analytics / summaries
CREATE TABLE IF NOT EXISTS query_logs (
  id            UUID PRIMARY KEY,
  user_id       VARCHAR(255),
  query         TEXT NOT NULL,
  rewritten_query TEXT,
  result_count  INTEGER DEFAULT 0,
  created_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_query_logs_user_id ON query_logs (user_id);

CREATE TABLE IF NOT EXISTS document_summaries (
  document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  summary     TEXT NOT NULL
);

-- Drafting features
CREATE TABLE IF NOT EXISTS srs_drafts (
  id                 UUID PRIMARY KEY,
  title              TEXT NOT NULL,
  content            TEXT NOT NULL,
  source_document_ids JSON NOT NULL DEFAULT '[]'::json,
  source_snapshot    JSON NOT NULL DEFAULT '{}'::json,
  question           TEXT,
  answer             TEXT,
  created_by         VARCHAR(255),
  status             VARCHAR(30) NOT NULL DEFAULT 'draft',
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS doc_drafts (
  id                 UUID PRIMARY KEY,
  doc_type           VARCHAR(50) NOT NULL DEFAULT 'srs',
  title              TEXT NOT NULL,
  content            TEXT NOT NULL,
  source_document_ids JSON NOT NULL DEFAULT '[]'::json,
  source_snapshot    JSON NOT NULL DEFAULT '{}'::json,
  question           TEXT,
  answer             TEXT,
  created_by         VARCHAR(255),
  status             VARCHAR(30) NOT NULL DEFAULT 'draft',
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

-- AI task drafts (note: includes all columns added by runtime migrations)
CREATE TABLE IF NOT EXISTS ai_task_drafts (
  id                 UUID PRIMARY KEY,
  title              TEXT NOT NULL,
  description        TEXT,
  source_type        VARCHAR(50) NOT NULL,
  source_ref         TEXT,
  source_summary     TEXT,
  suggested_assignee VARCHAR(255),
  priority           VARCHAR(20) NOT NULL DEFAULT 'Medium',
  labels             TEXT[] DEFAULT ARRAY[]::TEXT[],
  status             VARCHAR(20) NOT NULL DEFAULT 'pending',
  triggered_by       VARCHAR(50) NOT NULL DEFAULT 'scheduler',
  created_by         VARCHAR(255),
  confirmed_by       VARCHAR(255),
  jira_key           VARCHAR(50),
  jira_project       VARCHAR(50) NOT NULL DEFAULT 'ECOS2025',
  scope_group_id     VARCHAR(255),
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  confirmed_at       TIMESTAMP,
  submitted_at       TIMESTAMP,
  -- Extended fields
  source_url         TEXT,
  source_meta        JSON NOT NULL DEFAULT '{}'::json,
  dedup_key          TEXT,
  evidence           JSON NOT NULL DEFAULT '[]'::json,
  suggested_fields   JSON NOT NULL DEFAULT '{}'::json,
  components         TEXT[] DEFAULT ARRAY[]::TEXT[],
  due_date           DATE,
  issue_type         VARCHAR(30) NOT NULL DEFAULT 'Task',
  epic_key           VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_dedup_key ON ai_task_drafts (dedup_key);
CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_scope_group_id ON ai_task_drafts (scope_group_id);

-- Connector configs / instances + sync logs
CREATE TABLE IF NOT EXISTS connector_configs (
  connector       VARCHAR(255) PRIMARY KEY,
  enabled         BOOLEAN NOT NULL DEFAULT TRUE,
  auto_sync       BOOLEAN NOT NULL DEFAULT FALSE,
  schedule_hour   INTEGER,
  schedule_minute INTEGER,
  schedule_tz     VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  selection       JSON NOT NULL DEFAULT '{}'::json,
  updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS connector_instances (
  id             UUID PRIMARY KEY,
  connector_type VARCHAR(50) NOT NULL,
  name           VARCHAR(255) NOT NULL,
  base_url       TEXT,
  auth_type      VARCHAR(50) NOT NULL DEFAULT 'token',
  username       VARCHAR(255),
  secret         TEXT,
  extra          JSON NOT NULL DEFAULT '{}'::json,
  created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_connector_instances_type ON connector_instances (connector_type);

CREATE TABLE IF NOT EXISTS sync_logs (
  id          BIGSERIAL PRIMARY KEY,
  connector   VARCHAR(255) NOT NULL,
  status      VARCHAR(20) NOT NULL DEFAULT 'running',
  started_at  TIMESTAMP,
  finished_at TIMESTAMP,
  last_sync_at TIMESTAMP,
  fetched     INTEGER DEFAULT 0,
  indexed     INTEGER DEFAULT 0,
  errors      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sync_logs_connector ON sync_logs (connector);
CREATE INDEX IF NOT EXISTS idx_sync_logs_last_sync_at ON sync_logs (last_sync_at);

-- ---------------------------------------------------------------------------
-- Seed: sys_admin application user (full quyền trong app)
--
-- App logic coi user là admin nếu:
-- - users.is_admin = true OR users.role = 'system_admin'
--
-- Cách 1 (khuyến nghị cho test): dùng pgcrypto để tạo bcrypt hash ngay trong SQL.
-- Lưu ý: cần quyền tạo extension. Nếu DB không cho phép, dùng Cách 2 bên dưới.
-- ---------------------------------------------------------------------------

-- Cách 1: tạo bcrypt hash bằng pgcrypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO users (id, email, display_name, password_hash, is_active, is_admin, role)
VALUES (
  'sys_admin',
  'sys_admin@example.com',
  'System Admin',
  crypt('ChangeMe123!', gen_salt('bf', 12)),
  TRUE,
  TRUE,
  'system_admin'
)
ON CONFLICT (id) DO UPDATE SET
  email         = EXCLUDED.email,
  display_name  = EXCLUDED.display_name,
  password_hash = EXCLUDED.password_hash,
  is_active     = TRUE,
  is_admin      = TRUE,
  role          = 'system_admin';

-- Option: add sys_admin vào tất cả groups hiện có (không bắt buộc vì admin bypass ACL).
INSERT INTO user_groups (user_id, group_id)
SELECT 'sys_admin', g.id
FROM groups g
ON CONFLICT DO NOTHING;

-- Cách 2 (nếu không tạo được pgcrypto):
-- 1) Tự tạo bcrypt hash ở máy local (ví dụ bằng Python bcrypt) rồi paste vào đây.
-- 2) Update lại users.password_hash:
-- UPDATE users
-- SET password_hash = '$2b$12$REPLACE_WITH_BCRYPT_HASH', is_admin = TRUE, role = 'system_admin'
-- WHERE id = 'sys_admin';

COMMIT;
