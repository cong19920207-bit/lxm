-- TD-015：conversation_log 增加送达态与 Q14 标记
-- MySQL 8：执行前备份。历史 user 行视为已成功闭环（C1）；assistant 行 delivery_status 保持 NULL。

ALTER TABLE conversation_log
  ADD COLUMN delivery_status VARCHAR(32) NULL COMMENT 'user: delivered/pending_llm/failed_timeout 等；assistant: NULL' AFTER sort_seq,
  ADD COLUMN skipped_in_prompt TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Q14 最旧条未进本轮 Prompt' AFTER delivery_status;

UPDATE conversation_log
SET delivery_status = 'delivered'
WHERE role = 'user' AND delivery_status IS NULL;

-- assistant 不参与送达态语义，保持 NULL（API A1 仍带键值为 null）
