-- -*- coding: utf-8 -*-
-- 历史库 admin_config 缺 is_draft 时执行（与 backend.models.AdminConfig 对齐）
-- SQLAlchemy create_all 不会给已有表加列，需手动迁移后再跑 init_data.sql
--
-- 示例：
--   docker exec -i lxm_mysql mysql -ulxmt -p'你的密码' lxmfor < scripts/migrate_admin_config_add_is_draft.sql

SET NAMES utf8mb4;

ALTER TABLE admin_config
  ADD COLUMN is_draft TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'True=草稿版本, False=正式/历史版本'
    AFTER is_active;
