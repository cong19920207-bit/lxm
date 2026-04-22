-- TD-016 / V2-A：为 conversation_log、emotion_log 增加可空 round_id（UUID 文本，36 字符）
-- MySQL 8：执行前备份。旧行保持 NULL；写入 round_id 见后续 V2-B。
-- 部署顺序：先执行本脚本（DDL），再发布含 ORM 的应用代码。
-- 推荐优先使用 Alembic：项目根执行 `alembic upgrade head`（revision td016_v2a_001），与本脚本二选一；已执行本脚本时请 `alembic stamp td016_v2a_001`。
--
-- 【PR 描述摘要】
-- 1. 增量迁移：仅 ADD 可空列，无数据回填；与 Alembic 二选一之「同等方案」（仓库惯例为 scripts/migrate_*.sql）。
-- 2. 回滚：先 DROP emotion_log.round_id，再 DROP conversation_log.round_id；并回滚含 ORM 字段的代码提交。
-- 3. 未改 chat.py 打包/防抖/限流；emotion_log.conversation_id 仍挂首条 user（现网语义保留）。

ALTER TABLE conversation_log
  ADD COLUMN round_id VARCHAR(36) NULL COMMENT 'TD-016：一轮多 user+assistant 共享 UUID' AFTER skipped_in_prompt;

ALTER TABLE emotion_log
  ADD COLUMN round_id VARCHAR(36) NULL COMMENT 'TD-016：与本轮 conversation_log 相同 round_id' AFTER conversation_id;

-- ========== downgrade（回滚时手工执行；先 emotion_log 后 conversation_log）==========
-- ALTER TABLE emotion_log DROP COLUMN round_id;
-- ALTER TABLE conversation_log DROP COLUMN round_id;
