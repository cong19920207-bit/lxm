# Admin Security Data

- 文档 ID：`contract-admin-security-data`
- 权威状态：`canonical`
- 功能范围：`admin-security-accounts`
- 必读依赖：`contract-shared-conventions`, `contract-shared-auth-rbac`
- 相关技术债：无

### 表名：login_log


| 字段名         | 类型         | 必填  | 默认值    | 说明                        |
| ----------- | ---------- | --- | ------ | ------------------------- |
| id          | Integer PK | 是   | 自增     |                           |
| user_id     | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`              |
| login_at    | DateTime   | 是   | -      |                           |
| time_period | String(20) | 是   | -      | morning / evening / other |
| created_at  | DateTime   | 是   | utcnow |                           |

### 表名：admin_users


| 字段名                   | 类型          | 必填  | 默认值    | 说明            |
| --------------------- | ----------- | --- | ------ | ------------- |
| id                    | Integer PK  | 是   | 自增     |               |
| username              | String(50)  | 是   | -      | 唯一索引（`unique=True`） |
| password_hash         | String(255) | 是   | -      |               |
| role                  | String(20)  | 是   | -      | super_admin / ops_admin / ai_trainer / tech_ops / observer（展示名“观察者”） |
| remark                | String(200) | 否   | NULL   |               |
| is_active             | Boolean     | 是   | True   | ORM `default=True` |
| is_locked             | Boolean     | 是   | False  | ORM `default=False` |
| login_fail_count      | Integer     | 是   | 0      |               |
| token_version         | Integer     | 是   | 0      | 后台账号级会话版本；数据库 `NOT NULL DEFAULT 0` |
| last_login_at         | DateTime    | 否   | NULL   |               |
| last_password_change_at | DateTime  | 否   | NULL   |               |
| created_at            | DateTime    | 是   | utcnow |               |
| created_by            | String(50)  | 否   | NULL   |               |

### 表名：admin_config


| 字段名        | 类型          | 必填  | 默认值    | 说明        |
| ---------- | ----------- | --- | ------ | --------- |
| id         | Integer PK  | 是   | 自增     |           |
| config_key | String(100) | 是   | -      | **非唯一**索引（`index=True`）；同一 key 多行见下 |
| config_value | Text      | 否   | NULL   | JSON 字符串等（`nullable=True`） |
| version    | Integer     | 是   | 1      | ORM `default=1` |
| draft_revision | Integer | 否 | NULL | 语音草稿乐观锁版本；v8a新增，旧行不回填 |
| is_active  | Boolean     | 是   | True   | ORM `default=True` |
| is_draft   | Boolean     | 是   | False  | ORM `default=False`；`comment`：True=草稿 / False=正式或历史 |
| updated_by | String(50)  | 否   | NULL   |           |
| updated_at | DateTime    | 是   | utcnow | `onupdate=utcnow` |

- **行语义与约束**：同一 `config_key` **允许且需要**多行并存——例如一条草稿（`is_draft=true`，`is_active=false`）、一条当前生效（`is_active=true`，`is_draft=false`）、多条历史版本（`is_active=false`，`is_draft=false`）。**禁止**对 `config_key` 单列建立 **UNIQUE**；否则 `PUT /api/admin/persona/draft`、`prompt` 草稿保存等会在 `INSERT` 草稿时触发 MySQL **1062**。新建库见 `scripts/schema_ddl.sql`；已错建唯一索引的库执行 **`scripts/migrate_admin_config_config_key_nonunique.sql`**（执行前用 `SHOW INDEX FROM admin_config` 核对索引名）。
- **运行时约定 key（节选，非表结构 DDL）**：除既有 `persona`、`fallback_reply` 等外，对话链路读取 **`step5_system_prompt`**（Step5 模块1 System 整段，缺省回退代码内 `SYSTEM_PROMPT_TEXT`）、**`step5_5_prompt_fragments`**（Step5.5 六段 JSON，缺省与 `step5_5_prompt_fragments.py` 内置默认合并）、**`step5_5_enabled`**（Step5.5 总开关，§2.7.1；`AdminConfigService.get_active_config`，Redis `active_config:step5_5_enabled`）；
  - 开关无库内生效行时视为关闭。管理端：侧栏 **「🗣️ 对话流 Prompt」** 分组内 **`prompt.html?tab=step5|step55`**（Step5 / Step5.5 可编辑）、**`step5-5-switch.html`**（总开关）；Step1.5 / Step3 / Step8 / Agent 任务指令另见只读页与 **`GET /api/admin/chat-prompt-view/*`**（2026-07-13）。

### 表名：admin_operation_logs


| 字段名                | 类型          | 必填  | 默认值    | 说明        |
| ------------------ | ----------- | --- | ------ | --------- |
| id                 | Integer PK  | 是   | 自增     |           |
| admin_user_id      | Integer     | 否   | NULL   | 可空（账号删除后仍保留日志，ORM `nullable=True`） |
| admin_username     | String(50)  | 是   | -      |           |
| module             | String(50)  | 是   | -      |           |
| action             | String(20)  | 是   | -      |           |
| target_description | String(500) | 否   | NULL   |           |
| before_value       | Text        | 否   | NULL   |           |
| after_value        | Text        | 否   | NULL   |           |
| ip_address         | String(50)  | 否   | NULL   |           |
| created_at         | DateTime    | 是   | utcnow |           |


---

<a id="voice-config-shared"></a>
### 语音配置共用表增量

`voice_call_config`、`voice_call_script`、`voice_call_master_switch`继续使用上面的admin_config，同key保留草稿/当前/历史多行，不加单列唯一约束。前两者草稿采用base_version与nullable draft_revision乐观锁；总开关使用独立版本发布。业务语义见[语音配置](../realtime-voice/data.md#configuration)，不新增平行配置表。
