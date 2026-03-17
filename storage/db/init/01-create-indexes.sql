-- Tối ưu cho hàm `get_by_source` trong Ingestion Pipeline
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);

-- Tối ưu cho hàm đếm (Count) và truy vấn Task Drafts
CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_status ON ai_task_drafts(status);
CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_source_type ON ai_task_drafts(source_type);

-- Tối ưu cho việc kiểm tra quyền (Permissions)
CREATE INDEX IF NOT EXISTS idx_user_groups_user_id ON user_groups(user_id);