# Alembic 数据库迁移

## 常用命令

在项目根目录（含 `alembic.ini`）执行：

```bash
# 升级到最新
alembic upgrade head

# 回退一个版本
alembic downgrade -1

# 若已通过 scripts/migrate_td016_round_id.sql 手工加列，避免重复 ADD：
alembic stamp td016_v2a_001
```

连接串与运行时一致：读取根目录 `.env` 的 `MYSQL_*`，经 `backend.config.get_mysql_sync_migration_url()`（**PyMySQL**）连接。

## PR 描述建议（迁移策略）

- **增量**：仅 `ADD` 可空 `round_id`，无数据回填；与 `scripts/migrate_td016_round_id.sql` 二选一或 Alembic 为准。
- **回滚**：`alembic downgrade -1` 或手工 `DROP COLUMN`（先 `emotion_log` 后 `conversation_log`）；再回滚依赖 `round_id` 的代码。
- **已用手工 SQL 的库**：使用 `alembic stamp td016_v2a_001` 对齐版本表，勿重复执行 `upgrade` 中的 ADD（本 revision 已做「列已存在则跳过」防护）。
- **TD-020 / V3-A**：新表 `user_short_term_emotion`，revision `**v3a_td020_001`**，依赖 `**td016_v2a_001**`；`alembic upgrade head` 即可；回滚 `alembic downgrade -1` 会删该表（见 `alembic/versions/v3a_td020_user_short_term_emotion.py`）。

