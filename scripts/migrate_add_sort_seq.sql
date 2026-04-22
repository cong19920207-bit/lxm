-- 迁移脚本：为统一时间线功能添加 sort_seq 字段和 user_timeline_seq 表
-- 执行顺序：1. 本 SQL  2. python -m scripts.backfill_sort_seq

-- 1. conversation_log 加 sort_seq
ALTER TABLE conversation_log ADD COLUMN sort_seq BIGINT NOT NULL DEFAULT 0;
CREATE INDEX ix_conversation_log_sort_seq ON conversation_log (sort_seq);

-- 2. agent_message 加 sort_seq
ALTER TABLE agent_message ADD COLUMN sort_seq BIGINT NOT NULL DEFAULT 0;
CREATE INDEX ix_agent_message_sort_seq ON agent_message (sort_seq);

-- 3. 新建 user_timeline_seq 序列表
CREATE TABLE IF NOT EXISTS user_timeline_seq (
    user_id INTEGER NOT NULL,
    next_seq BIGINT NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
