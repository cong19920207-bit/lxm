-- -*- coding: utf-8 -*-
-- admin_config：去掉 config_key 上的 UNIQUE，改为普通索引
--
-- 背景：`admin_config_service.save_draft` 会在已有「生效/历史」行时 INSERT 草稿行，
-- 同一 `config_key` 允许多行（is_draft=1 草稿 + is_draft=0 的生效与历史）。
-- 若库中存在 UNIQUE(config_key) 或唯一索引 `ix_admin_config_config_key`，会触发
-- MySQL 1062 Duplicate entry，导致人格/Prompt 等「保存草稿」500。
--
-- 执行前建议：`SHOW INDEX FROM admin_config;` / `SHOW CREATE TABLE admin_config;`
-- 确认唯一索引名；若名称不是 `ix_admin_config_config_key`，请改下方 DROP 语句。
--
-- Docker 示例（库名/账号按 .env，以下为 compose 默认值）：
--   docker exec -i lxm_mysql mysql -ulxm -p'lxm123456' lxm < scripts/migrate_admin_config_config_key_nonunique.sql

SET NAMES utf8mb4;

-- 删除错误的唯一索引（名称以实际库为准）
ALTER TABLE admin_config DROP INDEX ix_admin_config_config_key;

-- 重建为「非唯一」索引，便于按 config_key 查询
CREATE INDEX ix_admin_config_config_key ON admin_config (config_key);
