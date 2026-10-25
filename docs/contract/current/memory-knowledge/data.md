# Memory Knowledge Data

> 提交范围说明：生产快照继续使用 `new_lxm_memory_long_collection`；本文 `local_test_collection` 仅代指历史本地隔离目标，不是可直接复制的部署配置。本地验收结果不代表生产验收。


- 文档 ID：`contract-memory-knowledge-data`
- 权威状态：`canonical`
- 功能范围：`memory-knowledge`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-017`, `TD-022`, `TD-023`, `TD-026`, `TD-027`, `TD-028`, `TD-029`

### 表名：memory


| 字段名                     | 类型          | 必填  | 默认值    | 说明                    |
| ----------------------- | ----------- | --- | ------ | --------------------- |
| id                      | Integer PK  | 是   | 自增     |                       |
| user_id                 | Integer FK(users.id, ON DELETE CASCADE) | 是   | -      | `index=True`          |
| content                 | Text        | 是   | -      |                       |
| importance_score        | Float       | 是   | -      |                       |
| source                  | String(20)  | 是   | -      | auto / manual / admin |
| dashvector_id           | String(100) | 否   | NULL   | 向量侧 ID（`index=True`） |
| is_deleted              | Boolean     | 是   | False  | 软删除                   |
| created_at              | DateTime    | 是   | utcnow |                       |
| updated_at              | DateTime    | 是   | utcnow | `onupdate=utcnow`     |
| expires_at              | DateTime    | 否   | NULL   | 过期时间                  |

- **运行时口径（TD-022 已清偿，表结构保留）**：长记忆第一套写入已下线，H5/Admin 列表改读 Step6 用户向量；`memory` 表仍在 ORM/库中，主链不再 `extract_and_save`。存量清理与表删除见 TD-022。

---

<a id="memory-implementation-boundary"></a>
### 本轮实现与环境边界

本节记载工作区已实现、在自有隔离环境验证的增量。2026-10-13本地Docker业务环境`local-docker:lxmfor`已完成S15并开放epoch2，运行于新库`local_test_collection`；旧库和旧隔离分区已退役且不复用名称。实际验证及版本见唯一STEP §3.39。M8 的 cg=0.18/user=0.15 是隔离评测候选，共享默认仍为0.1；内置 System 修复不覆盖合法 active/draft/显式 override。AC19/AC20 原失败和未齐质量对照按最新用户决定作为本阶段非阻断风险保留，不能据功能通过宣称质量全通过。最终 M8/GATE-D 与实际部署状态见唯一 STEP §3。

<a id="memory-control-types"></a>
### 控制表类型、物理默认与正文存储边界

记忆正文的权威源仍为向量当前文档；下列SQL表是提交、身份/代次、索引任务、使用保护、回填/清理和诊断控制，不是全文事实版本镜像。`ControlColumns`继承created_at/updated_at/revision；chat及future继承`Dates`，继承字段在各表只列一次。

类型别名按实际ORM：U64=BigInteger/MySQL BIGINT UNSIGNED，U32=Integer/MySQL INTEGER UNSIGNED；UUID=String(36)/MySQL CHAR(36) ascii/ascii_bin；DIGEST=LargeBinary(32)/BINARY(32)；INSTANT=DateTime/MySQL DATETIME(6)；ascii_string(n)=String(n)/MySQL VARCHAR(n) ascii/ascii_bin。memory_config的_time/_uuid/_digest等价对应；ref(target,name,later)为具名FK、ON DELETE RESTRICT，later只影响DDL use_alter。

各表列区分应用层 `default`、数据库 `server_default` 与本轮隔离MySQL物理DEFAULT；Python datetime.utcnow不会自动成为SQL CURRENT_TIMESTAMP。下表MySQL type/nullable/default/PK/index/FK/check来自只读真实schema（61表、23新增、零DDL/DML），ORM声明/继承来源逐列标明；环境是自有隔离，不能证明业务数据库已迁移。

`ExactJSONDocument`物理类型JSON(none_as_null=True)，实际SQL pending_payload等保存规范JSON**字符串标量**，Python取出再解为dict；不能把它声明为可用SQL JSONpath读对象的结构。合法业务input/候选正文按原快照语义保存，不以凭据字段名字猜测清洗正文。服务凭据从公开配置/错误/日志/维护/诊断投影剥离。完整控制语义见[API生命周期](api.md#memory-diagnostic-lifecycle)。

<a id="schema-memory_config_head"></a>
### 表名：memory_config_head

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| config_key | VARCHAR(100) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | primary_key | backend/models/memory_config.py:22 |
| active_admin_config_id | INTEGER | yes | — | — | — | — | backend/models/memory_config.py:23 |
| active_version | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_config.py:24 |
| revision | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_config.py:25 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_config.py:26 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "config_key"
    ],
    "name": null
  },
  "indexes": [],
  "unique_constraints": [],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_config_head_nonnegative",
      "sqltext": "((`active_version` >= 0) and (`revision` >= 0))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_config.py:22
config_key: Mapped[str] = mapped_column(String(100), primary_key=True)
# backend/models/memory_config.py:23
active_admin_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
# backend/models/memory_config.py:24
active_version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
# backend/models/memory_config.py:25
revision: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
# backend/models/memory_config.py:26
updated_at: Mapped[datetime] = mapped_column(_time, default=datetime.utcnow)
```

ORM表级约束来源：

```python
# backend/models/memory_config.py:18
__table_args__ = (
        CheckConstraint("active_version >= 0 AND revision >= 0", name="ck_memory_config_head_nonnegative"),
    )
```

<a id="schema-memory_config_publish"></a>
### 表名：memory_config_publish

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| id | BIGINT | no | — | — | — | primary_key | backend/models/memory_config.py:43 |
| publish_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_config.py:44 |
| admin_id | INTEGER | no | — | — | — | — | backend/models/memory_config.py:45 |
| source_entry | VARCHAR(64) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | — | backend/models/memory_config.py:46 |
| canonical_key | VARCHAR(100) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | index | backend/models/memory_config.py:47 |
| request_digest | BINARY(32) | no | — | — | — | — | backend/models/memory_config.py:48 |
| validated_digest | BINARY(32) | yes | — | — | — | — | backend/models/memory_config.py:49 |
| expected_head_revision | BIGINT | yes | — | — | — | — | backend/models/memory_config.py:50 |
| commit_state | VARCHAR(16) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | — | backend/models/memory_config.py:51 |
| committed_admin_config_id | INTEGER | yes | — | — | — | — | backend/models/memory_config.py:52 |
| committed_version | BIGINT | yes | — | — | — | — | backend/models/memory_config.py:53 |
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_config.py:54 |
| observed_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_config.py:55 |
| committed_at | DATETIME | yes | — | — | — | — | backend/models/memory_config.py:56 |
| terminal_at | DATETIME | yes | — | — | — | — | backend/models/memory_config.py:57 |
| receipt_until | DATETIME | yes | — | — | — | — | backend/models/memory_config.py:58 |
| tombstone_until | DATETIME | yes | — | — | — | — | backend/models/memory_config.py:59 |
| reason | VARCHAR(64) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_config.py:60 |
| record_revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_config.py:61 |
| lease_owner | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_config.py:62 |
| lease_version | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_config.py:63 |
| lease_until | DATETIME | yes | — | — | — | — | backend/models/memory_config.py:64 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_config_publish_canonical_key",
      "column_names": [
        "canonical_key"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_config_publish_actor_id",
      "column_names": [
        "admin_id",
        "publish_id"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_config_publish_actor_id",
      "column_names": [
        "admin_id",
        "publish_id"
      ],
      "duplicates_index": "uq_memory_config_publish_actor_id"
    }
  ],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_config_publish_commit",
      "sqltext": "(((`commit_state` = _utf8mb4'committed') and (`committed_admin_config_id` is not null) and (`committed_version` is not null)) or ((`commit_state` <> _utf8mb4'committed') and (`committed_admin_config_id` is null) and (`committed_version` is null)))"
    },
    {
      "name": "ck_memory_config_publish_revision",
      "sqltext": "((`record_revision` >= 1) and (`lease_version` >= 0))"
    },
    {
      "name": "ck_memory_config_publish_state",
      "sqltext": "(`commit_state` in (_utf8mb4'accepted',_utf8mb4'validating',_utf8mb4'committed',_utf8mb4'rejected',_utf8mb4'unknown'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_config.py:43
id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
# backend/models/memory_config.py:44
publish_id: Mapped[str] = mapped_column(_uuid)
# backend/models/memory_config.py:45
admin_id: Mapped[int] = mapped_column(Integer)
# backend/models/memory_config.py:46
source_entry: Mapped[str] = mapped_column(String(64))
# backend/models/memory_config.py:47
canonical_key: Mapped[str] = mapped_column(String(100), index=True)
# backend/models/memory_config.py:48
request_digest: Mapped[bytes] = mapped_column(_digest)
# backend/models/memory_config.py:49
validated_digest: Mapped[bytes | None] = mapped_column(_digest, nullable=True)
# backend/models/memory_config.py:50
expected_head_revision: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
# backend/models/memory_config.py:51
commit_state: Mapped[str] = mapped_column(String(16))
# backend/models/memory_config.py:52
committed_admin_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
# backend/models/memory_config.py:53
committed_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
# backend/models/memory_config.py:54
created_at: Mapped[datetime] = mapped_column(_time, default=datetime.utcnow)
# backend/models/memory_config.py:55
observed_at: Mapped[datetime] = mapped_column(_time, default=datetime.utcnow)
# backend/models/memory_config.py:56
committed_at: Mapped[datetime | None] = mapped_column(_time, nullable=True)
# backend/models/memory_config.py:57
terminal_at: Mapped[datetime | None] = mapped_column(_time, nullable=True)
# backend/models/memory_config.py:58
receipt_until: Mapped[datetime | None] = mapped_column(_time, nullable=True)
# backend/models/memory_config.py:59
tombstone_until: Mapped[datetime | None] = mapped_column(_time, nullable=True)
# backend/models/memory_config.py:60
reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
# backend/models/memory_config.py:61
record_revision: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
# backend/models/memory_config.py:62
lease_owner: Mapped[str | None] = mapped_column(_uuid, nullable=True)
# backend/models/memory_config.py:63
lease_version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
# backend/models/memory_config.py:64
lease_until: Mapped[datetime | None] = mapped_column(_time, nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_config.py:31
__table_args__ = (
        UniqueConstraint("admin_id", "publish_id", name="uq_memory_config_publish_actor_id"),
        CheckConstraint("commit_state IN ('accepted','validating','committed','rejected','unknown')",
                        name="ck_memory_config_publish_state"),
        CheckConstraint("record_revision >= 1 AND lease_version >= 0",
                        name="ck_memory_config_publish_revision"),
        CheckConstraint("(commit_state = 'committed' AND committed_admin_config_id IS NOT NULL "
                        "AND committed_version IS NOT NULL) OR (commit_state <> 'committed' "
                        "AND committed_admin_config_id IS NULL AND committed_version IS NULL)",
                        name="ck_memory_config_publish_commit"),
    )
```

<a id="schema-memory_runtime_fence"></a>
### 表名：memory_runtime_fence

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| environment_id | VARCHAR(64) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | primary_key | backend/models/memory_control.py:37 |
| target_epoch | BIGINT | no | — | — | — | — | backend/models/memory_control.py:38 |
| target_fingerprint | BINARY(32) | no | — | — | — | — | backend/models/memory_control.py:39 |
| mode | VARCHAR(16) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:40 |
| reset_run_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:42 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "environment_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "fk_memory_fence_reset",
      "column_names": [
        "reset_run_id"
      ],
      "unique": false
    }
  ],
  "unique_constraints": [],
  "foreign_keys": [
    {
      "name": "fk_memory_fence_reset",
      "constrained_columns": [
        "reset_run_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_reset_run",
      "referred_columns": [
        "run_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    }
  ],
  "check_constraints": [
    {
      "name": "ck_memory_fence_mode",
      "sqltext": "(`mode` in (_ascii'maintenance',_ascii'active'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_control.py:37
environment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
# backend/models/memory_control.py:38
target_epoch: Mapped[int] = mapped_column(U64)
# backend/models/memory_control.py:39
target_fingerprint: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_control.py:40
mode: Mapped[str] = mapped_column(ascii_string(16))
# backend/models/memory_control.py:42
reset_run_id: Mapped[str | None] = mapped_column(UUID, ref("memory_reset_run.run_id", "fk_memory_fence_reset", later=True), nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_control.py:36
__table_args__ = (CheckConstraint("mode IN ('maintenance','active')", name="ck_memory_fence_mode"),)
```

<a id="schema-memory_identity"></a>
### 表名：memory_identity

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| id | BIGINT | no | — | — | — | primary_key | backend/models/memory_control.py:56 |
| target_epoch | BIGINT | no | — | — | — | — | backend/models/memory_control.py:57 |
| target_fingerprint | BINARY(32) | no | — | — | — | — | backend/models/memory_control.py:58 |
| partition_name | VARCHAR(64) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:59 |
| doc_id | VARCHAR(64) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:60 |
| memory_type | VARCHAR(32) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | — | backend/models/memory_control.py:61 |
| owner_user_id | BIGINT | no | — | — | — | — | backend/models/memory_control.py:62 |
| generation | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_control.py:63 |
| allocated_generation | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_control.py:64 |
| body_hash | BINARY(32) | yes | — | — | — | — | backend/models/memory_control.py:65 |
| source_state | VARCHAR(24) COLLATE "ascii_bin" | no | "unknown" | — | — | — | backend/models/memory_control.py:66 |
| index_state | VARCHAR(24) COLLATE "ascii_bin" | no | "not_ready" | — | — | — | backend/models/memory_control.py:67 |
| encoder_version | VARCHAR(128) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_control.py:68 |
| current_operation_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:69 |
| inflight_operation_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:70 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_identity_states_id",
      "column_names": [
        "source_state",
        "index_state",
        "id"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_identity_target_doc",
      "column_names": [
        "target_fingerprint",
        "partition_name",
        "doc_id"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_identity_target_doc",
      "column_names": [
        "target_fingerprint",
        "partition_name",
        "doc_id"
      ],
      "duplicates_index": "uq_memory_identity_target_doc"
    }
  ],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_identity_generation",
      "sqltext": "((`generation` >= 0) and (`allocated_generation` >= `generation`))"
    },
    {
      "name": "ck_memory_identity_index",
      "sqltext": "(`index_state` in (_ascii'not_ready',_ascii'ready',_ascii'repairing',_ascii'manual',_ascii'deleted'))"
    },
    {
      "name": "ck_memory_identity_owner",
      "sqltext": "(((`memory_type` in (_utf8mb4'character_global',_utf8mb4'character_knowledge')) and (`owner_user_id` = 0)) or ((`memory_type` in (_utf8mb4'user',_utf8mb4'character_private')) and (`owner_user_id` > 0)))"
    },
    {
      "name": "ck_memory_identity_source",
      "sqltext": "(`source_state` in (_ascii'unknown',_ascii'live',_ascii'deleted'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_control.py:56
id: Mapped[int] = mapped_column(U64.with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
# backend/models/memory_control.py:57
target_epoch: Mapped[int] = mapped_column(U64)
# backend/models/memory_control.py:58
target_fingerprint: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_control.py:59
partition_name: Mapped[str] = mapped_column(ascii_string(64))
# backend/models/memory_control.py:60
doc_id: Mapped[str] = mapped_column(ascii_string(64))
# backend/models/memory_control.py:61
memory_type: Mapped[str] = mapped_column(String(32))
# backend/models/memory_control.py:62
owner_user_id: Mapped[int] = mapped_column(BigInteger)
# backend/models/memory_control.py:63
generation: Mapped[int] = mapped_column(U64, default=0, server_default="0")
# backend/models/memory_control.py:64
allocated_generation: Mapped[int] = mapped_column(U64, default=0, server_default="0")
# backend/models/memory_control.py:65
body_hash: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
# backend/models/memory_control.py:66
source_state: Mapped[str] = mapped_column(ascii_string(24), default="unknown")
# backend/models/memory_control.py:67
index_state: Mapped[str] = mapped_column(ascii_string(24), default="not_ready")
# backend/models/memory_control.py:68
encoder_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
# backend/models/memory_control.py:69
current_operation_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_control.py:70
inflight_operation_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_control.py:47
__table_args__ = (
        UniqueConstraint("target_fingerprint", "partition_name", "doc_id", name="uq_memory_identity_target_doc"),
        Index("ix_memory_identity_states_id", "source_state", "index_state", "id"),
        CheckConstraint("source_state IN ('unknown','live','deleted')", name="ck_memory_identity_source"),
        CheckConstraint("index_state IN ('not_ready','ready','repairing','manual','deleted')", name="ck_memory_identity_index"),
        CheckConstraint("generation >= 0 AND allocated_generation >= generation", name="ck_memory_identity_generation"),
        CheckConstraint("(memory_type IN ('character_global','character_knowledge') AND owner_user_id = 0) OR "
                        "(memory_type IN ('user','character_private') AND owner_user_id > 0)", name="ck_memory_identity_owner"),
    )
```

<a id="schema-memory_operation"></a>
### 表名：memory_operation

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| operation_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_control.py:91 |
| identity_id | BIGINT | yes | — | — | — | — | backend/models/memory_control.py:92 |
| generation | BIGINT | yes | — | — | — | — | backend/models/memory_control.py:93 |
| parent_operation_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:94 |
| task_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:95 |
| round_no | INTEGER | yes | — | — | — | — | backend/models/memory_control.py:96 |
| attempt | INTEGER | yes | — | — | — | — | backend/models/memory_control.py:97 |
| source_generation_key | BINARY(32) | yes | — | — | — | — | backend/models/memory_control.py:98 |
| operation_kind | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:99 |
| owner_actor_type | VARCHAR(16) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:100 |
| owner_actor_id | BIGINT | no | — | — | — | — | backend/models/memory_control.py:101 |
| client_request_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:102 |
| idempotency_hash | BINARY(32) | yes | — | — | — | — | backend/models/memory_control.py:103 |
| request_hash | BINARY(32) | no | — | — | — | — | backend/models/memory_control.py:104 |
| target_epoch | BIGINT | no | — | — | — | — | backend/models/memory_control.py:105 |
| source_result | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:106 |
| index_result | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:107 |
| dispatch_state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:108 |
| pending_payload | JSON | yes | — | — | — | — | backend/models/memory_control.py:109 |
| payload_hash | BINARY(32) | yes | — | — | — | — | backend/models/memory_control.py:110 |
| remote_tag | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:111 |
| worker_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:112 |
| worker_epoch | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_control.py:113 |
| lease_until | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:114 |
| dispatched_at | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:115 |
| reconcile_until | DATETIME | no | — | — | — | — | backend/models/memory_control.py:116 |
| terminal_at | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:117 |
| receipt_summary | JSON | yes | — | — | — | — | backend/models/memory_control.py:118 |
| receipt_until | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:119 |
| tombstone_until | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:120 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "operation_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "fk_memory_operation_identity",
      "column_names": [
        "identity_id"
      ],
      "unique": false
    },
    {
      "name": "ix_memory_operation_dispatch_lease",
      "column_names": [
        "dispatch_state",
        "lease_until"
      ],
      "unique": false
    },
    {
      "name": "ix_memory_operation_source_reconcile",
      "column_names": [
        "source_result",
        "reconcile_until"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_operation_actor_request",
      "column_names": [
        "owner_actor_type",
        "owner_actor_id",
        "idempotency_hash"
      ],
      "unique": true,
      "type": "UNIQUE"
    },
    {
      "name": "uq_memory_operation_parent_identity",
      "column_names": [
        "parent_operation_id",
        "identity_id"
      ],
      "unique": true,
      "type": "UNIQUE"
    },
    {
      "name": "uq_memory_operation_source_generation",
      "column_names": [
        "source_generation_key"
      ],
      "unique": true,
      "type": "UNIQUE"
    },
    {
      "name": "uq_memory_operation_task_attempt",
      "column_names": [
        "task_id",
        "round_no",
        "attempt"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_operation_actor_request",
      "column_names": [
        "owner_actor_type",
        "owner_actor_id",
        "idempotency_hash"
      ],
      "duplicates_index": "uq_memory_operation_actor_request"
    },
    {
      "name": "uq_memory_operation_parent_identity",
      "column_names": [
        "parent_operation_id",
        "identity_id"
      ],
      "duplicates_index": "uq_memory_operation_parent_identity"
    },
    {
      "name": "uq_memory_operation_source_generation",
      "column_names": [
        "source_generation_key"
      ],
      "duplicates_index": "uq_memory_operation_source_generation"
    },
    {
      "name": "uq_memory_operation_task_attempt",
      "column_names": [
        "task_id",
        "round_no",
        "attempt"
      ],
      "duplicates_index": "uq_memory_operation_task_attempt"
    }
  ],
  "foreign_keys": [
    {
      "name": "fk_memory_operation_identity",
      "constrained_columns": [
        "identity_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_identity",
      "referred_columns": [
        "id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    },
    {
      "name": "fk_memory_operation_parent",
      "constrained_columns": [
        "parent_operation_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_operation",
      "referred_columns": [
        "operation_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    },
    {
      "name": "fk_memory_operation_task",
      "constrained_columns": [
        "task_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_index_task",
      "referred_columns": [
        "task_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    }
  ],
  "check_constraints": [
    {
      "name": "ck_memory_operation_dispatch",
      "sqltext": "(`dispatch_state` in (_ascii'prepared',_ascii'claimed',_ascii'dispatching',_ascii'confirmed',_ascii'unknown',_ascii'not_sent',_ascii'superseded'))"
    },
    {
      "name": "ck_memory_operation_generation_key",
      "sqltext": "(((`operation_kind` in (_ascii'create',_ascii'update',_ascii'delete')) and (`source_generation_key` is not null)) or ((`operation_kind` not in (_ascii'create',_ascii'update',_ascii'delete')) and (`source_generation_key` is null)))"
    },
    {
      "name": "ck_memory_operation_identity",
      "sqltext": "((`operation_kind` = _ascii'batch') or ((`identity_id` is not null) and (`generation` is not null)))"
    },
    {
      "name": "ck_memory_operation_index",
      "sqltext": "(`index_result` in (_ascii'pending',_ascii'ready',_ascii'failed',_ascii'unknown',_ascii'manual',_ascii'not_required',_ascii'superseded'))"
    },
    {
      "name": "ck_memory_operation_index_attempt",
      "sqltext": "((`operation_kind` <> _ascii'index') or ((`task_id` is not null) and (`round_no` is not null) and (`attempt` is not null) and (`attempt` >= 1)))"
    },
    {
      "name": "ck_memory_operation_kind",
      "sqltext": "(`operation_kind` in (_ascii'create',_ascii'update',_ascii'delete',_ascii'index',_ascii'retry',_ascii'baseline',_ascii'batch'))"
    },
    {
      "name": "ck_memory_operation_source",
      "sqltext": "(`source_result` in (_ascii'pending',_ascii'confirmed',_ascii'failed',_ascii'unknown',_ascii'superseded'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_control.py:91
operation_id: Mapped[str] = mapped_column(UUID, primary_key=True)
# backend/models/memory_control.py:92
identity_id: Mapped[int | None] = mapped_column(U64, ref("memory_identity.id", "fk_memory_operation_identity"), nullable=True)
# backend/models/memory_control.py:93
generation: Mapped[int | None] = mapped_column(U64, nullable=True)
# backend/models/memory_control.py:94
parent_operation_id: Mapped[str | None] = mapped_column(UUID, ref("memory_operation.operation_id", "fk_memory_operation_parent"), nullable=True)
# backend/models/memory_control.py:95
task_id: Mapped[str | None] = mapped_column(UUID, ref("memory_index_task.task_id", "fk_memory_operation_task", later=True), nullable=True)
# backend/models/memory_control.py:96
round_no: Mapped[int | None] = mapped_column(U32, nullable=True)
# backend/models/memory_control.py:97
attempt: Mapped[int | None] = mapped_column(U32, nullable=True)
# backend/models/memory_control.py:98
source_generation_key: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
# backend/models/memory_control.py:99
operation_kind: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:100
owner_actor_type: Mapped[str] = mapped_column(ascii_string(16))
# backend/models/memory_control.py:101
owner_actor_id: Mapped[int] = mapped_column(BigInteger)
# backend/models/memory_control.py:102
client_request_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_control.py:103
idempotency_hash: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
# backend/models/memory_control.py:104
request_hash: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_control.py:105
target_epoch: Mapped[int] = mapped_column(U64)
# backend/models/memory_control.py:106
source_result: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:107
index_result: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:108
dispatch_state: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:109
pending_payload: Mapped[dict | None] = mapped_column(ExactJSONDocument(), nullable=True)
# backend/models/memory_control.py:110
payload_hash: Mapped[bytes | None] = mapped_column(DIGEST, nullable=True)
# backend/models/memory_control.py:111
remote_tag: Mapped[str] = mapped_column(UUID)
# backend/models/memory_control.py:112
worker_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_control.py:113
worker_epoch: Mapped[int] = mapped_column(U64, default=0, server_default="0")
# backend/models/memory_control.py:114
lease_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:115
dispatched_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:116
reconcile_until: Mapped[datetime] = mapped_column(INSTANT)
# backend/models/memory_control.py:117
terminal_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:118
receipt_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
# backend/models/memory_control.py:119
receipt_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:120
tombstone_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_control.py:75
__table_args__ = (
        UniqueConstraint("source_generation_key", name="uq_memory_operation_source_generation"),
        UniqueConstraint("task_id", "round_no", "attempt", name="uq_memory_operation_task_attempt"),
        UniqueConstraint("parent_operation_id", "identity_id", name="uq_memory_operation_parent_identity"),
        UniqueConstraint("owner_actor_type", "owner_actor_id", "idempotency_hash", name="uq_memory_operation_actor_request"),
        Index("ix_memory_operation_dispatch_lease", "dispatch_state", "lease_until"),
        Index("ix_memory_operation_source_reconcile", "source_result", "reconcile_until"),
        CheckConstraint("operation_kind IN ('create','update','delete','index','retry','baseline','batch')", name="ck_memory_operation_kind"),
        CheckConstraint("operation_kind = 'batch' OR (identity_id IS NOT NULL AND generation IS NOT NULL)", name="ck_memory_operation_identity"),
        CheckConstraint("source_result IN ('pending','confirmed','failed','unknown','superseded')", name="ck_memory_operation_source"),
        CheckConstraint("index_result IN ('pending','ready','failed','unknown','manual','not_required','superseded')", name="ck_memory_operation_index"),
        CheckConstraint("dispatch_state IN ('prepared','claimed','dispatching','confirmed','unknown','not_sent','superseded')", name="ck_memory_operation_dispatch"),
        CheckConstraint("operation_kind <> 'index' OR (task_id IS NOT NULL AND round_no IS NOT NULL AND attempt IS NOT NULL AND attempt >= 1)", name="ck_memory_operation_index_attempt"),
        CheckConstraint("(operation_kind IN ('create','update','delete') AND source_generation_key IS NOT NULL) OR "
                        "(operation_kind NOT IN ('create','update','delete') AND source_generation_key IS NULL)", name="ck_memory_operation_generation_key"),
    )
```

<a id="schema-memory_index_task"></a>
### 表名：memory_index_task

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| task_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_control.py:130 |
| identity_id | BIGINT | no | — | — | — | — | backend/models/memory_control.py:131 |
| operation_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:132 |
| generation | BIGINT | no | — | — | — | — | backend/models/memory_control.py:133 |
| encoder_version | VARCHAR(128) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | — | backend/models/memory_control.py:134 |
| body_hash | BINARY(32) | no | — | — | — | — | backend/models/memory_control.py:135 |
| state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:136 |
| round_no | INTEGER | no | 0 | "0" | '0' | — | backend/models/memory_control.py:137 |
| attempt | INTEGER | no | 0 | "0" | '0' | — | backend/models/memory_control.py:138 |
| round_started_at | DATETIME | no | — | — | — | — | backend/models/memory_control.py:139 |
| round_deadline_at | DATETIME | no | — | — | — | — | backend/models/memory_control.py:140 |
| next_attempt_at | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:141 |
| worker_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_control.py:142 |
| worker_epoch | BIGINT | no | 0 | "0" | '0' | — | backend/models/memory_control.py:143 |
| lease_until | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:144 |
| error_code | VARCHAR(64) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_control.py:145 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "task_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "fk_memory_index_task_source",
      "column_names": [
        "operation_id"
      ],
      "unique": false
    },
    {
      "name": "ix_memory_index_task_due",
      "column_names": [
        "state",
        "next_attempt_at",
        "task_id"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_index_task_generation_encoder",
      "column_names": [
        "identity_id",
        "generation",
        "encoder_version"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_index_task_generation_encoder",
      "column_names": [
        "identity_id",
        "generation",
        "encoder_version"
      ],
      "duplicates_index": "uq_memory_index_task_generation_encoder"
    }
  ],
  "foreign_keys": [
    {
      "name": "fk_memory_index_task_identity",
      "constrained_columns": [
        "identity_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_identity",
      "referred_columns": [
        "id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    },
    {
      "name": "fk_memory_index_task_source",
      "constrained_columns": [
        "operation_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_operation",
      "referred_columns": [
        "operation_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    }
  ],
  "check_constraints": [
    {
      "name": "ck_memory_index_task_state",
      "sqltext": "(`state` in (_ascii'pending',_ascii'running',_ascii'retry_wait',_ascii'manual',_ascii'completed',_ascii'superseded'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_control.py:130
task_id: Mapped[str] = mapped_column(UUID, primary_key=True)
# backend/models/memory_control.py:131
identity_id: Mapped[int] = mapped_column(U64, ref("memory_identity.id", "fk_memory_index_task_identity"))
# backend/models/memory_control.py:132
operation_id: Mapped[str] = mapped_column(UUID, ref("memory_operation.operation_id", "fk_memory_index_task_source"))
# backend/models/memory_control.py:133
generation: Mapped[int] = mapped_column(U64)
# backend/models/memory_control.py:134
encoder_version: Mapped[str] = mapped_column(String(128))
# backend/models/memory_control.py:135
body_hash: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_control.py:136
state: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:137
round_no: Mapped[int] = mapped_column(U32, default=0, server_default="0")
# backend/models/memory_control.py:138
attempt: Mapped[int] = mapped_column(U32, default=0, server_default="0")
# backend/models/memory_control.py:139
round_started_at: Mapped[datetime] = mapped_column(INSTANT)
# backend/models/memory_control.py:140
round_deadline_at: Mapped[datetime] = mapped_column(INSTANT)
# backend/models/memory_control.py:141
next_attempt_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:142
worker_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_control.py:143
worker_epoch: Mapped[int] = mapped_column(U64, default=0, server_default="0")
# backend/models/memory_control.py:144
lease_until: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:145
error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_control.py:125
__table_args__ = (
        UniqueConstraint("identity_id", "generation", "encoder_version", name="uq_memory_index_task_generation_encoder"),
        Index("ix_memory_index_task_due", "state", "next_attempt_at", "task_id"),
        CheckConstraint("state IN ('pending','running','retry_wait','manual','completed','superseded')", name="ck_memory_index_task_state"),
    )
```

<a id="schema-memory_use_claim"></a>
### 表名：memory_use_claim

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| claim_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_control.py:154 |
| request_hash | BINARY(32) | no | — | — | — | — | backend/models/memory_control.py:155 |
| consumer_kind | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:156 |
| execution_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:157 |
| target_epoch | BIGINT | no | — | — | — | — | backend/models/memory_control.py:158 |
| owner_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:159 |
| state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:160 |
| created_deadline_at | DATETIME | no | — | — | — | — | backend/models/memory_control.py:161 |
| handoff_at | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:162 |
| closed_at | DATETIME | yes | — | — | — | — | backend/models/memory_control.py:163 |
| error_code | VARCHAR(64) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_control.py:164 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "claim_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "uq_memory_use_claim_execution",
      "column_names": [
        "consumer_kind",
        "execution_id"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_use_claim_execution",
      "column_names": [
        "consumer_kind",
        "execution_id"
      ],
      "duplicates_index": "uq_memory_use_claim_execution"
    }
  ],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_use_claim_state",
      "sqltext": "(`state` in (_utf8mb4'reserved',_utf8mb4'dispatching',_utf8mb4'handed_off',_utf8mb4'aborted',_utf8mb4'unknown'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_control.py:154
claim_id: Mapped[str] = mapped_column(UUID, primary_key=True)
# backend/models/memory_control.py:155
request_hash: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_control.py:156
consumer_kind: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:157
execution_id: Mapped[str] = mapped_column(UUID)
# backend/models/memory_control.py:158
target_epoch: Mapped[int] = mapped_column(U64)
# backend/models/memory_control.py:159
owner_id: Mapped[str] = mapped_column(UUID)
# backend/models/memory_control.py:160
state: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_control.py:161
created_deadline_at: Mapped[datetime] = mapped_column(INSTANT)
# backend/models/memory_control.py:162
handoff_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:163
closed_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_control.py:164
error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_control.py:150
__table_args__ = (
        UniqueConstraint("consumer_kind", "execution_id", name="uq_memory_use_claim_execution"),
        CheckConstraint("state IN ('reserved','dispatching','handed_off','aborted','unknown')", name="ck_memory_use_claim_state"),
    )
```

<a id="schema-memory_use_item"></a>
### 表名：memory_use_item

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| claim_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_control.py:170 |
| identity_id | BIGINT | no | — | — | — | primary_key | backend/models/memory_control.py:171 |
| generation | BIGINT | no | — | — | — | — | backend/models/memory_control.py:172 |
| body_hash | BINARY(32) | no | — | — | — | — | backend/models/memory_control.py:173 |
| route | VARCHAR(4) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_control.py:174 |
| ordinal | INTEGER | no | — | — | — | — | backend/models/memory_control.py:175 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "claim_id",
      "identity_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_use_item_identity_claim",
      "column_names": [
        "identity_id",
        "claim_id"
      ],
      "unique": false
    }
  ],
  "unique_constraints": [],
  "foreign_keys": [
    {
      "name": "fk_memory_use_item_claim",
      "constrained_columns": [
        "claim_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_use_claim",
      "referred_columns": [
        "claim_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    },
    {
      "name": "fk_memory_use_item_identity",
      "constrained_columns": [
        "identity_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_identity",
      "referred_columns": [
        "id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    }
  ],
  "check_constraints": []
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_control.py:170
claim_id: Mapped[str] = mapped_column(UUID, ref("memory_use_claim.claim_id", "fk_memory_use_item_claim"), primary_key=True)
# backend/models/memory_control.py:171
identity_id: Mapped[int] = mapped_column(U64, ref("memory_identity.id", "fk_memory_use_item_identity"), primary_key=True)
# backend/models/memory_control.py:172
generation: Mapped[int] = mapped_column(U64)
# backend/models/memory_control.py:173
body_hash: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_control.py:174
route: Mapped[str] = mapped_column(ascii_string(4))
# backend/models/memory_control.py:175
ordinal: Mapped[int] = mapped_column(U32)
```

ORM表级约束来源：

```python
# backend/models/memory_control.py:169
__table_args__ = (Index("ix_memory_use_item_identity_claim", "identity_id", "claim_id"),)
```

<a id="schema-memory_maintenance_event"></a>
### 表名：memory_maintenance_event

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| id | BIGINT | no | — | — | — | primary_key | backend/models/memory_maintenance.py:19 |
| event_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | unique | backend/models/memory_maintenance.py:20 |
| record_kind | VARCHAR(16) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | — | backend/models/memory_maintenance.py:21 |
| task_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_maintenance.py:22 |
| run_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_maintenance.py:23 |
| operation_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_maintenance.py:24 |
| identity_id | BIGINT | yes | — | — | — | — | backend/models/memory_maintenance.py:25 |
| generation | BIGINT | yes | — | — | — | — | backend/models/memory_maintenance.py:26 |
| event_type | VARCHAR(32) COLLATE "utf8mb4_unicode_ci" | no | — | — | — | — | backend/models/memory_maintenance.py:27 |
| source_state | VARCHAR(16) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_maintenance.py:28 |
| index_state | VARCHAR(24) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_maintenance.py:29 |
| maintenance_state | VARCHAR(24) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_maintenance.py:30 |
| attempt_number | INTEGER | yes | — | — | — | — | backend/models/memory_maintenance.py:31 |
| started_at | DATETIME | yes | — | — | — | — | backend/models/memory_maintenance.py:32 |
| ended_at | DATETIME | yes | — | — | — | — | backend/models/memory_maintenance.py:33 |
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_maintenance.py:34 |
| controlled_reason | VARCHAR(64) COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_maintenance.py:35 |
| details | JSON | yes | — | — | — | — | backend/models/memory_maintenance.py:36 |
| display_deleted_at | DATETIME | yes | — | — | — | — | backend/models/memory_maintenance.py:37 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_event_run_created",
      "column_names": [
        "run_id",
        "created_at",
        "id"
      ],
      "unique": false
    },
    {
      "name": "ix_memory_event_task_created",
      "column_names": [
        "task_id",
        "created_at",
        "id"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_event_id",
      "column_names": [
        "event_id"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_event_id",
      "column_names": [
        "event_id"
      ],
      "duplicates_index": "uq_memory_event_id"
    }
  ],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_event_kind",
      "sqltext": "(`record_kind` in (_utf8mb4'task',_utf8mb4'backfill'))"
    },
    {
      "name": "ck_memory_event_origin",
      "sqltext": "((`task_id` is not null) or (`run_id` is not null))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_maintenance.py:19
id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), 'sqlite'), primary_key=True, autoincrement=True)
# backend/models/memory_maintenance.py:20
event_id: Mapped[str] = mapped_column(UUID, unique=True)
# backend/models/memory_maintenance.py:21
record_kind: Mapped[str] = mapped_column(ascii_string(16))
# backend/models/memory_maintenance.py:22
task_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_maintenance.py:23
run_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_maintenance.py:24
operation_id: Mapped[str | None] = mapped_column(UUID, nullable=True)
# backend/models/memory_maintenance.py:25
identity_id: Mapped[int | None] = mapped_column(U64, nullable=True)
# backend/models/memory_maintenance.py:26
generation: Mapped[int | None] = mapped_column(U64, nullable=True)
# backend/models/memory_maintenance.py:27
event_type: Mapped[str] = mapped_column(ascii_string(32))
# backend/models/memory_maintenance.py:28
source_state: Mapped[str | None] = mapped_column(ascii_string(16), nullable=True)
# backend/models/memory_maintenance.py:29
index_state: Mapped[str | None] = mapped_column(ascii_string(24), nullable=True)
# backend/models/memory_maintenance.py:30
maintenance_state: Mapped[str | None] = mapped_column(ascii_string(24), nullable=True)
# backend/models/memory_maintenance.py:31
attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
# backend/models/memory_maintenance.py:32
started_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_maintenance.py:33
ended_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
# backend/models/memory_maintenance.py:34
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_maintenance.py:35
controlled_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
# backend/models/memory_maintenance.py:36
details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
# backend/models/memory_maintenance.py:37
display_deleted_at: Mapped[datetime | None] = mapped_column(INSTANT, nullable=True)
```

ORM表级约束来源：

```python
# backend/models/memory_maintenance.py:13
__table_args__ = (
        CheckConstraint("record_kind IN ('task','backfill')", name='ck_memory_event_kind'),
        CheckConstraint('task_id IS NOT NULL OR run_id IS NOT NULL', name='ck_memory_event_origin'),
        Index('ix_memory_event_task_created', 'task_id', 'created_at', 'id'),
        Index('ix_memory_event_run_created', 'run_id', 'created_at', 'id'),
    )
```

<a id="schema-memory_reset_run"></a>
### 表名：memory_reset_run

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| run_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_backfill.py:16 |
| environment_id | VARCHAR(64) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:17 |
| reset_key | VARCHAR(16) COLLATE "ascii_bin" | no | 'S15' | — | — | — | backend/models/memory_backfill.py:18 |
| manifest_hash | BINARY(32) | no | — | — | — | — | backend/models/memory_backfill.py:19 |
| protocol_version | VARCHAR(32) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:20 |
| target_epoch | BIGINT | no | — | — | — | — | backend/models/memory_backfill.py:21 |
| target_fingerprint | BINARY(32) | no | — | — | — | — | backend/models/memory_backfill.py:22 |
| t0 | DATETIME | yes | — | — | — | — | backend/models/memory_backfill.py:23 |
| phase | VARCHAR(32) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:24 |
| state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:25 |
| baseline_digest | BINARY(32) | yes | — | — | — | — | backend/models/memory_backfill.py:26 |
| completed_at | DATETIME | yes | — | — | — | — | backend/models/memory_backfill.py:27 |
| opened_at | DATETIME | yes | — | — | — | — | backend/models/memory_backfill.py:28 |
| operator_id | BIGINT | no | — | — | — | — | backend/models/memory_backfill.py:29 |
| last_error_code | VARCHAR(64) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_backfill.py:30 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "run_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "uq_memory_reset_environment_key",
      "column_names": [
        "environment_id",
        "reset_key"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_reset_environment_key",
      "column_names": [
        "environment_id",
        "reset_key"
      ],
      "duplicates_index": "uq_memory_reset_environment_key"
    }
  ],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_reset_key",
      "sqltext": "(`reset_key` = _utf8mb4'S15')"
    },
    {
      "name": "ck_memory_reset_state",
      "sqltext": "(`state` in (_utf8mb4'planned',_utf8mb4'maintenance',_utf8mb4'running',_utf8mb4'unknown',_utf8mb4'failed',_utf8mb4'completed',_utf8mb4'opened'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_backfill.py:16
run_id: Mapped[str] = mapped_column(UUID,primary_key=True)
# backend/models/memory_backfill.py:17
environment_id: Mapped[str] = mapped_column(ascii_string(64))
# backend/models/memory_backfill.py:18
reset_key: Mapped[str] = mapped_column(ascii_string(16),default='S15')
# backend/models/memory_backfill.py:19
manifest_hash: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:20
protocol_version: Mapped[str] = mapped_column(ascii_string(32))
# backend/models/memory_backfill.py:21
target_epoch: Mapped[int] = mapped_column(U64)
# backend/models/memory_backfill.py:22
target_fingerprint: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:23
t0: Mapped[datetime | None] = mapped_column(INSTANT)
# backend/models/memory_backfill.py:24
phase: Mapped[str] = mapped_column(ascii_string(32))
# backend/models/memory_backfill.py:25
state: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_backfill.py:26
baseline_digest: Mapped[bytes | None] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:27
completed_at: Mapped[datetime | None] = mapped_column(INSTANT)
# backend/models/memory_backfill.py:28
opened_at: Mapped[datetime | None] = mapped_column(INSTANT)
# backend/models/memory_backfill.py:29
operator_id: Mapped[int] = mapped_column(U64)
# backend/models/memory_backfill.py:30
last_error_code: Mapped[str | None] = mapped_column(ascii_string(64))
```

ORM表级约束来源：

```python
# backend/models/memory_backfill.py:13
__table_args__ = (UniqueConstraint('environment_id','reset_key',name='uq_memory_reset_environment_key'),
        CheckConstraint("reset_key = 'S15'",name='ck_memory_reset_key'),
        CheckConstraint("state IN ('planned','maintenance','running','unknown','failed','completed','opened')",name='ck_memory_reset_state'))
```

<a id="schema-memory_reset_item"></a>
### 表名：memory_reset_item

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| run_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_backfill.py:36 |
| kind | VARCHAR(16) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_backfill.py:37 |
| resource_key | VARCHAR(191) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_backfill.py:38 |
| state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:39 |
| fixed_scope | JSON | no | — | — | — | — | backend/models/memory_backfill.py:40 |
| cursor | JSON | yes | — | — | — | — | backend/models/memory_backfill.py:41 |
| before_count | BIGINT | yes | — | — | — | — | backend/models/memory_backfill.py:42 |
| after_count | BIGINT | yes | — | — | — | — | backend/models/memory_backfill.py:43 |
| preserve_digest_before | BINARY(32) | yes | — | — | — | — | backend/models/memory_backfill.py:44 |
| preserve_digest_after | BINARY(32) | yes | — | — | — | — | backend/models/memory_backfill.py:45 |
| result_digest | BINARY(32) | yes | — | — | — | — | backend/models/memory_backfill.py:46 |
| error_code | VARCHAR(64) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_backfill.py:47 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "run_id",
      "kind",
      "resource_key"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_reset_item_state",
      "column_names": [
        "state",
        "run_id"
      ],
      "unique": false
    }
  ],
  "unique_constraints": [],
  "foreign_keys": [
    {
      "name": "fk_memory_reset_item_run",
      "constrained_columns": [
        "run_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_reset_run",
      "referred_columns": [
        "run_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    }
  ],
  "check_constraints": [
    {
      "name": "ck_memory_reset_item_kind",
      "sqltext": "(`kind` in (_ascii'phase',_ascii'resource'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_backfill.py:36
run_id: Mapped[str] = mapped_column(UUID,ref('memory_reset_run.run_id','fk_memory_reset_item_run'),primary_key=True)
# backend/models/memory_backfill.py:37
kind: Mapped[str] = mapped_column(ascii_string(16),primary_key=True)
# backend/models/memory_backfill.py:38
resource_key: Mapped[str] = mapped_column(ascii_string(191),primary_key=True)
# backend/models/memory_backfill.py:39
state: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_backfill.py:40
fixed_scope: Mapped[dict] = mapped_column(JSON)
# backend/models/memory_backfill.py:41
cursor: Mapped[dict | None] = mapped_column(JSON)
# backend/models/memory_backfill.py:42
before_count: Mapped[int | None] = mapped_column(U64)
# backend/models/memory_backfill.py:43
after_count: Mapped[int | None] = mapped_column(U64)
# backend/models/memory_backfill.py:44
preserve_digest_before: Mapped[bytes | None] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:45
preserve_digest_after: Mapped[bytes | None] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:46
result_digest: Mapped[bytes | None] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:47
error_code: Mapped[str | None] = mapped_column(ascii_string(64))
```

ORM表级约束来源：

```python
# backend/models/memory_backfill.py:35
__table_args__ = (CheckConstraint("kind IN ('phase','resource')",name='ck_memory_reset_item_kind'),Index('ix_memory_reset_item_state','state','run_id'))
```

<a id="schema-memory_backfill_run"></a>
### 表名：memory_backfill_run

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| run_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_backfill.py:56 |
| mode | VARCHAR(16) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:57 |
| execution_state | VARCHAR(24) COLLATE "ascii_bin" | no | 'pending' | — | — | — | backend/models/memory_backfill.py:58 |
| stage | VARCHAR(16) COLLATE "ascii_bin" | no | 'scan' | — | — | — | backend/models/memory_backfill.py:59 |
| source_scope | JSON | no | — | — | — | — | backend/models/memory_backfill.py:60 |
| frozen_versions | JSON | no | — | — | — | — | backend/models/memory_backfill.py:61 |
| scope_digest | BINARY(32) | no | — | — | — | — | backend/models/memory_backfill.py:62 |
| baseline | JSON | no | — | — | — | — | backend/models/memory_backfill.py:63 |
| high_water | JSON | yes | — | — | — | — | backend/models/memory_backfill.py:64 |
| checkpoint_summary | JSON | yes | — | — | — | — | backend/models/memory_backfill.py:65 |
| cutoff | JSON | yes | — | — | — | — | backend/models/memory_backfill.py:66 |
| scanned_records | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_backfill.py:67 |
| unique_source_ids | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_backfill.py:68 |
| attempt_count | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_backfill.py:69 |
| total_known | TINYINT | no | False | '0' | '0' | — | backend/models/memory_backfill.py:70 |
| total_source_ids | BIGINT | yes | — | — | — | — | backend/models/memory_backfill.py:71 |
| source_class_counts | JSON | no | dict | — | — | — | backend/models/memory_backfill.py:72 |
| reconcile_counts | JSON | no | dict | — | — | — | backend/models/memory_backfill.py:73 |
| unresolved_count | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_backfill.py:74 |
| report_complete | TINYINT | no | False | '0' | '0' | — | backend/models/memory_backfill.py:75 |
| started_at | DATETIME | yes | — | — | — | — | backend/models/memory_backfill.py:76 |
| ended_at | DATETIME | yes | — | — | — | — | backend/models/memory_backfill.py:77 |
| lease_owner | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_backfill.py:78 |
| lease_version | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_backfill.py:79 |
| lease_until | DATETIME | yes | — | — | — | — | backend/models/memory_backfill.py:80 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "run_id"
    ],
    "name": null
  },
  "indexes": [],
  "unique_constraints": [],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_backfill_counts",
      "sqltext": "((`scanned_records` >= 0) and (`unique_source_ids` >= 0) and (`attempt_count` >= 0) and (`unresolved_count` >= 0))"
    },
    {
      "name": "ck_memory_backfill_mode",
      "sqltext": "(`mode` in (_utf8mb4'isolated',_utf8mb4'actual'))"
    },
    {
      "name": "ck_memory_backfill_stage",
      "sqltext": "(`stage` in (_utf8mb4'scan',_utf8mb4'index',_utf8mb4'reconcile',_utf8mb4'catchup'))"
    },
    {
      "name": "ck_memory_backfill_state",
      "sqltext": "(`execution_state` in (_utf8mb4'pending',_utf8mb4'running',_utf8mb4'interrupted',_utf8mb4'manual_required',_utf8mb4'completed'))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_backfill.py:56
run_id: Mapped[str] = mapped_column(UUID,primary_key=True)
# backend/models/memory_backfill.py:57
mode: Mapped[str] = mapped_column(ascii_string(16))
# backend/models/memory_backfill.py:58
execution_state: Mapped[str] = mapped_column(ascii_string(24),default='pending')
# backend/models/memory_backfill.py:59
stage: Mapped[str] = mapped_column(ascii_string(16),default='scan')
# backend/models/memory_backfill.py:60
source_scope: Mapped[dict] = mapped_column(JSON)
# backend/models/memory_backfill.py:61
frozen_versions: Mapped[dict] = mapped_column(JSON)
# backend/models/memory_backfill.py:62
scope_digest: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:63
baseline: Mapped[dict] = mapped_column(JSON)
# backend/models/memory_backfill.py:64
high_water: Mapped[dict | None] = mapped_column(JSON)
# backend/models/memory_backfill.py:65
checkpoint_summary: Mapped[dict | None] = mapped_column(JSON)
# backend/models/memory_backfill.py:66
cutoff: Mapped[dict | None] = mapped_column(JSON)
# backend/models/memory_backfill.py:67
scanned_records: Mapped[int] = mapped_column(U64,default=0,server_default='0')
# backend/models/memory_backfill.py:68
unique_source_ids: Mapped[int] = mapped_column(U64,default=0,server_default='0')
# backend/models/memory_backfill.py:69
attempt_count: Mapped[int] = mapped_column(U64,default=0,server_default='0')
# backend/models/memory_backfill.py:70
total_known: Mapped[bool] = mapped_column(Boolean,default=False,server_default='0')
# backend/models/memory_backfill.py:71
total_source_ids: Mapped[int | None] = mapped_column(U64)
# backend/models/memory_backfill.py:72
source_class_counts: Mapped[dict] = mapped_column(JSON,default=dict)
# backend/models/memory_backfill.py:73
reconcile_counts: Mapped[dict] = mapped_column(JSON,default=dict)
# backend/models/memory_backfill.py:74
unresolved_count: Mapped[int] = mapped_column(U64,default=0,server_default='0')
# backend/models/memory_backfill.py:75
report_complete: Mapped[bool] = mapped_column(Boolean,default=False,server_default='0')
# backend/models/memory_backfill.py:76
started_at: Mapped[datetime | None] = mapped_column(INSTANT)
# backend/models/memory_backfill.py:77
ended_at: Mapped[datetime | None] = mapped_column(INSTANT)
# backend/models/memory_backfill.py:78
lease_owner: Mapped[str | None] = mapped_column(UUID)
# backend/models/memory_backfill.py:79
lease_version: Mapped[int] = mapped_column(U64,default=0,server_default='0')
# backend/models/memory_backfill.py:80
lease_until: Mapped[datetime | None] = mapped_column(INSTANT)
```

ORM表级约束来源：

```python
# backend/models/memory_backfill.py:52
__table_args__ = (CheckConstraint("mode IN ('isolated','actual')",name='ck_memory_backfill_mode'),
        CheckConstraint("execution_state IN ('pending','running','interrupted','manual_required','completed')",name='ck_memory_backfill_state'),
        CheckConstraint("stage IN ('scan','index','reconcile','catchup')",name='ck_memory_backfill_stage'),
        CheckConstraint('scanned_records >= 0 AND unique_source_ids >= 0 AND attempt_count >= 0 AND unresolved_count >= 0',name='ck_memory_backfill_counts'))
```

<a id="schema-memory_backfill_item"></a>
### 表名：memory_backfill_item

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| created_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:29 |
| updated_at | DATETIME | no | datetime.utcnow | — | — | — | backend/models/memory_control.py:30 |
| revision | BIGINT | no | 1 | "1" | '1' | — | backend/models/memory_control.py:31 |
| id | BIGINT | no | — | — | — | primary_key | backend/models/memory_backfill.py:87 |
| run_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:88 |
| item_seq | BIGINT | no | — | — | — | — | backend/models/memory_backfill.py:89 |
| identity_id | BIGINT | yes | — | — | — | — | backend/models/memory_backfill.py:90 |
| identity_key | JSON | no | — | — | — | — | backend/models/memory_backfill.py:91 |
| identity_digest | BINARY(32) | no | — | — | — | — | backend/models/memory_backfill.py:92 |
| source_class | VARCHAR(32) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:93 |
| current_generation | BIGINT | yes | — | — | — | — | backend/models/memory_backfill.py:94 |
| content_digest | BINARY(32) | yes | — | — | — | — | backend/models/memory_backfill.py:95 |
| index_result | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:96 |
| reconcile_state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_backfill.py:97 |
| task_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_backfill.py:98 |
| attempt_count | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_backfill.py:99 |
| observed_at | DATETIME | no | — | — | — | — | backend/models/memory_backfill.py:100 |
| reason | VARCHAR(64) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_backfill.py:101 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_backfill_item_run",
      "column_names": [
        "run_id",
        "item_seq"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_backfill_item_identity",
      "column_names": [
        "run_id",
        "identity_digest"
      ],
      "unique": true,
      "type": "UNIQUE"
    },
    {
      "name": "uq_memory_backfill_item_seq",
      "column_names": [
        "run_id",
        "item_seq"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_backfill_item_identity",
      "column_names": [
        "run_id",
        "identity_digest"
      ],
      "duplicates_index": "uq_memory_backfill_item_identity"
    },
    {
      "name": "uq_memory_backfill_item_seq",
      "column_names": [
        "run_id",
        "item_seq"
      ],
      "duplicates_index": "uq_memory_backfill_item_seq"
    }
  ],
  "foreign_keys": [
    {
      "name": "fk_memory_backfill_item_run",
      "constrained_columns": [
        "run_id"
      ],
      "referred_schema": null,
      "referred_table": "memory_backfill_run",
      "referred_columns": [
        "run_id"
      ],
      "options": {
        "ondelete": "RESTRICT"
      }
    }
  ],
  "check_constraints": []
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_control.py:29
created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
# backend/models/memory_control.py:30
updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)
# backend/models/memory_control.py:31
revision: Mapped[int] = mapped_column(U64, default=1, server_default="1")
# backend/models/memory_backfill.py:87
id: Mapped[int] = mapped_column(U64.with_variant(Integer,'sqlite'),primary_key=True,autoincrement=True)
# backend/models/memory_backfill.py:88
run_id: Mapped[str] = mapped_column(UUID,ref('memory_backfill_run.run_id','fk_memory_backfill_item_run'))
# backend/models/memory_backfill.py:89
item_seq: Mapped[int] = mapped_column(U64)
# backend/models/memory_backfill.py:90
identity_id: Mapped[int | None] = mapped_column(U64)
# backend/models/memory_backfill.py:91
identity_key: Mapped[dict] = mapped_column(JSON)
# backend/models/memory_backfill.py:92
identity_digest: Mapped[bytes] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:93
source_class: Mapped[str] = mapped_column(ascii_string(32))
# backend/models/memory_backfill.py:94
current_generation: Mapped[int | None] = mapped_column(U64)
# backend/models/memory_backfill.py:95
content_digest: Mapped[bytes | None] = mapped_column(DIGEST)
# backend/models/memory_backfill.py:96
index_result: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_backfill.py:97
reconcile_state: Mapped[str] = mapped_column(ascii_string(24))
# backend/models/memory_backfill.py:98
task_id: Mapped[str | None] = mapped_column(UUID)
# backend/models/memory_backfill.py:99
attempt_count: Mapped[int] = mapped_column(U64,default=0,server_default='0')
# backend/models/memory_backfill.py:100
observed_at: Mapped[datetime] = mapped_column(INSTANT)
# backend/models/memory_backfill.py:101
reason: Mapped[str | None] = mapped_column(ascii_string(64))
```

ORM表级约束来源：

```python
# backend/models/memory_backfill.py:85
__table_args__ = (UniqueConstraint('run_id','item_seq',name='uq_memory_backfill_item_seq'),
        UniqueConstraint('run_id','identity_digest',name='uq_memory_backfill_item_identity'),Index('ix_memory_backfill_item_run','run_id','item_seq'))
```

<a id="schema-memory_diagnostic_run"></a>
### 表名：memory_diagnostic_run

| 字段 | 实际MySQL类型 | NULL | 应用default | ORM server_default | 实际SQL DEFAULT | PK/index/unique | 源声明位置 |
|---|---|---|---|---|---|---|---|
| run_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | primary_key | backend/models/memory_diagnostic.py:17 |
| admin_id | INTEGER | no | — | — | — | — | backend/models/memory_diagnostic.py:18 |
| user_id | INTEGER | yes | — | — | — | — | backend/models/memory_diagnostic.py:19 |
| environment_id | VARCHAR(64) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_diagnostic.py:20 |
| request_id | CHAR(36) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_diagnostic.py:21 |
| request_digest | BINARY(32) | no | — | — | — | — | backend/models/memory_diagnostic.py:22 |
| source | VARCHAR(8) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_diagnostic.py:23 |
| parent_run_id | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_diagnostic.py:24 |
| input_text | TEXT COLLATE "utf8mb4_unicode_ci" | yes | — | — | — | — | backend/models/memory_diagnostic.py:25 |
| execution_state | VARCHAR(24) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_diagnostic.py:26 |
| history_state | VARCHAR(16) COLLATE "ascii_bin" | no | — | — | — | — | backend/models/memory_diagnostic.py:27 |
| result_revision | BIGINT | no | 1 | '1' | '1' | — | backend/models/memory_diagnostic.py:28 |
| created_at | DATETIME | no | — | — | — | — | backend/models/memory_diagnostic.py:29 |
| observed_at | DATETIME | no | — | — | — | — | backend/models/memory_diagnostic.py:30 |
| deadline_at | DATETIME | no | — | — | — | — | backend/models/memory_diagnostic.py:31 |
| persist_deadline_at | DATETIME | no | — | — | — | — | backend/models/memory_diagnostic.py:32 |
| started_at | DATETIME | yes | — | — | — | — | backend/models/memory_diagnostic.py:33 |
| finished_at | DATETIME | yes | — | — | — | — | backend/models/memory_diagnostic.py:34 |
| terminal_at | DATETIME | yes | — | — | — | — | backend/models/memory_diagnostic.py:35 |
| stage | VARCHAR(32) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_diagnostic.py:36 |
| controlled_reason | VARCHAR(64) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_diagnostic.py:37 |
| frozen_versions | JSON | yes | — | — | — | — | backend/models/memory_diagnostic.py:38 |
| context_sources | JSON | yes | — | — | — | — | backend/models/memory_diagnostic.py:39 |
| candidate_snapshots | JSON | yes | — | — | — | — | backend/models/memory_diagnostic.py:40 |
| selection_result | JSON | yes | — | — | — | — | backend/models/memory_diagnostic.py:41 |
| metrics | JSON | yes | — | — | — | — | backend/models/memory_diagnostic.py:42 |
| snapshot_available | TINYINT | no | False | '0' | '0' | — | backend/models/memory_diagnostic.py:43 |
| lease_owner | CHAR(36) COLLATE "ascii_bin" | yes | — | — | — | — | backend/models/memory_diagnostic.py:44 |
| lease_version | BIGINT | no | 0 | '0' | '0' | — | backend/models/memory_diagnostic.py:45 |
| lease_until | DATETIME | yes | — | — | — | — | backend/models/memory_diagnostic.py:46 |
| deleted_at | DATETIME | yes | — | — | — | — | backend/models/memory_diagnostic.py:47 |
| tombstone_until | DATETIME | yes | — | — | — | — | backend/models/memory_diagnostic.py:48 |

表级实际约束（PK、索引及unique、FK/ondelete、check）：

```json
{
  "primary_key": {
    "constrained_columns": [
      "run_id"
    ],
    "name": null
  },
  "indexes": [
    {
      "name": "ix_memory_diagnostic_active",
      "column_names": [
        "environment_id",
        "execution_state",
        "deadline_at"
      ],
      "unique": false
    },
    {
      "name": "ix_memory_diagnostic_user_created",
      "column_names": [
        "user_id",
        "created_at",
        "run_id"
      ],
      "unique": false
    },
    {
      "name": "uq_memory_diagnostic_request",
      "column_names": [
        "admin_id",
        "request_id"
      ],
      "unique": true,
      "type": "UNIQUE"
    }
  ],
  "unique_constraints": [
    {
      "name": "uq_memory_diagnostic_request",
      "column_names": [
        "admin_id",
        "request_id"
      ],
      "duplicates_index": "uq_memory_diagnostic_request"
    }
  ],
  "foreign_keys": [],
  "check_constraints": [
    {
      "name": "ck_memory_diagnostic_execution",
      "sqltext": "(`execution_state` in (_ascii'accepted',_ascii'running',_ascii'completed',_ascii'degraded',_ascii'failed',_ascii'budget_blocked',_ascii'interrupted',_ascii'manual_required'))"
    },
    {
      "name": "ck_memory_diagnostic_history",
      "sqltext": "(`history_state` in (_ascii'pending',_ascii'saved',_ascii'failed',_ascii'unknown',_ascii'deleted'))"
    },
    {
      "name": "ck_memory_diagnostic_revision",
      "sqltext": "(`result_revision` >= 1)"
    },
    {
      "name": "ck_memory_diagnostic_source",
      "sqltext": "((`source` is null) or (`source` in (_ascii'main',_ascii'openapi',_ascii'step8')))"
    }
  ]
}
```

完整ORM列声明（含默认、onupdate、autoincrement及FK参数；继承只列一次）：

```python
# backend/models/memory_diagnostic.py:17
run_id: Mapped[str]=mapped_column(UUID,primary_key=True)
# backend/models/memory_diagnostic.py:18
admin_id: Mapped[int]=mapped_column(Integer)
# backend/models/memory_diagnostic.py:19
user_id: Mapped[int|None]=mapped_column(Integer)
# backend/models/memory_diagnostic.py:20
environment_id: Mapped[str]=mapped_column(ascii_string(64))
# backend/models/memory_diagnostic.py:21
request_id: Mapped[str]=mapped_column(UUID)
# backend/models/memory_diagnostic.py:22
request_digest: Mapped[bytes]=mapped_column(DIGEST)
# backend/models/memory_diagnostic.py:23
source: Mapped[str|None]=mapped_column(ascii_string(8))
# backend/models/memory_diagnostic.py:24
parent_run_id: Mapped[str|None]=mapped_column(UUID)
# backend/models/memory_diagnostic.py:25
input_text: Mapped[str|None]=mapped_column(Text)
# backend/models/memory_diagnostic.py:26
execution_state: Mapped[str]=mapped_column(ascii_string(24))
# backend/models/memory_diagnostic.py:27
history_state: Mapped[str]=mapped_column(ascii_string(16))
# backend/models/memory_diagnostic.py:28
result_revision: Mapped[int]=mapped_column(U64,default=1,server_default='1')
# backend/models/memory_diagnostic.py:29
created_at: Mapped[datetime]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:30
observed_at: Mapped[datetime]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:31
deadline_at: Mapped[datetime]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:32
persist_deadline_at: Mapped[datetime]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:33
started_at: Mapped[datetime|None]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:34
finished_at: Mapped[datetime|None]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:35
terminal_at: Mapped[datetime|None]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:36
stage: Mapped[str|None]=mapped_column(ascii_string(32))
# backend/models/memory_diagnostic.py:37
controlled_reason: Mapped[str|None]=mapped_column(ascii_string(64))
# backend/models/memory_diagnostic.py:38
frozen_versions: Mapped[dict|None]=mapped_column(JSON)
# backend/models/memory_diagnostic.py:39
context_sources: Mapped[dict|None]=mapped_column(JSON)
# backend/models/memory_diagnostic.py:40
candidate_snapshots: Mapped[list|None]=mapped_column(JSON)
# backend/models/memory_diagnostic.py:41
selection_result: Mapped[dict|None]=mapped_column(JSON)
# backend/models/memory_diagnostic.py:42
metrics: Mapped[dict|None]=mapped_column(JSON)
# backend/models/memory_diagnostic.py:43
snapshot_available: Mapped[bool]=mapped_column(Boolean,default=False,server_default='0')
# backend/models/memory_diagnostic.py:44
lease_owner: Mapped[str|None]=mapped_column(UUID)
# backend/models/memory_diagnostic.py:45
lease_version: Mapped[int]=mapped_column(U64,default=0,server_default='0')
# backend/models/memory_diagnostic.py:46
lease_until: Mapped[datetime|None]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:47
deleted_at: Mapped[datetime|None]=mapped_column(INSTANT)
# backend/models/memory_diagnostic.py:48
tombstone_until: Mapped[datetime|None]=mapped_column(INSTANT)
```

ORM表级约束来源：

```python
# backend/models/memory_diagnostic.py:10
__table_args__=(UniqueConstraint('admin_id','request_id',name='uq_memory_diagnostic_request'),
        Index('ix_memory_diagnostic_user_created','user_id','created_at','run_id'),
        Index('ix_memory_diagnostic_active','environment_id','execution_state','deadline_at'),
        CheckConstraint("source IS NULL OR source IN ('main','openapi','step8')",name='ck_memory_diagnostic_source'),
        CheckConstraint("execution_state IN ('accepted','running','completed','degraded','failed','budget_blocked','interrupted','manual_required')",name='ck_memory_diagnostic_execution'),
        CheckConstraint("history_state IN ('pending','saved','failed','unknown','deleted')",name='ck_memory_diagnostic_history'),
        CheckConstraint('result_revision >= 1',name='ck_memory_diagnostic_revision'))
```

<a id="memory-control-retention"></a>
### 控制引用、快照与清理边界

identity按环境/目标epoch/type/user/doc身份唯一、generation严格单调，source_state/index_state分离；operation完整intent与tag/readback是源确认锚点；pending_payload只是未决恢复负载，不构成事实版本历史。task按原代/hash/encoder排它、完成不能由无来源索引猜测。use_claim/use_item在最后校验和发模型之间保护当前正文，unknown发送不按TTL释放。索引详细无正文回执7天、墓碑30天、未决不回收；诊断history永久保存，合法手删仅清快照并保30天幂等/审计锚点。008未完成run/item仍保护task/event引用。

诊断run的两种状态、120+30秒/lease和同actor/request唯一摘要、永久历史/手删与去凭据投影见[只读诊断](api.md#memory-diagnostic-lifecycle)；不得把控表保留期当正文历史自动清理。backfill/reset范围、checkpoint、完成提交unknown及独立open见[工具契约](api.md#memory-maintenance-and-backfill)；最终SDK地址兼容见[SDK工厂](api.md#memory-sdk-endpoint-compat)。本轮不声明业务schema迁移、S15清理或开放。

<a id="memory-runtime-structures"></a>
### 冻结配置、候选和Prompt DTO

`EffectiveMemoryConfig`一次冻结snapshot_id、retrieval、prompt、providers/versions、reply_model、target_fingerprint/可选target_epoch、encoder_version与profiles；secret handle不用于公开响应。`Candidate`不可变绑定route/identity_id/partition/doc_id/generation/body_hash/value/type/owner/key、有效通道来源/原分/名次、route_rank/rerank_score/order_method/trust_state。`Removal`只受控reason/stage/identity；`RouteResult`分dense/bm25/rerank状态与空因；`RetrievalResult`含config_snapshot_id/queries/routes/rewrite_deadline/retrieval_deadline。

`PromptBuildResult/SelectedEntry`、官方counter与保留初始/最终选择见[Prompt选入](api.md#memory-prompt-selection)；MemoryUseClaim.request_hash BINARY(32)只绑定可信user/owner/epoch/fingerprint、原deadline和原序candidate身份/代/hash/route/ordinal，UseItem只存最终选中项，重复原请求恢复裁剪结果，不锁被剔除项。MemoryUseGuard reserve/begin_handoff/handoff与原owner停止见同一API定义，源在途排除、同代confirmed源的index在途可dense使用。

迁移链v8h→v9a_memory_config_publication_001→v9b_memory_control_001→v9c_memory_maintenance_001；v9d回填/reset及voice cleared_run/fence FK，v9g_memory_diagnostic_001接v9f_future_consumption_001。应用create_all排除迁移管理表；隔离迁移证据与实际业务迁移分开记录；本地`lxmfor`已在2026-10-13迁至v9g，见STEP §3.39。actual activation必须匹配已完成S15记录；只有显式allow_isolated且isolated:环境可使用无reset证明fence，不造清理证据。

<a id="s15-vector-cursor"></a>
### memory_reset_item.cursor 的向量回执命名空间

既有 JSON 列增加逻辑 `vector_receipt`，无物理迁移。绑定字段为 `protocol=s15-vector-receipt-v1`、`run_id/resource_key/target_digest/revision/origin`；origin 为 `registered_dispatch` 或只读 `legacy_read`。原 receipt 仅含 `protocol=dashvector-delete-sync-v1/operation=delete_all/code/request_id/mode=sync/outcome`，code 为严格有界整数，outcome 为 request_completed 或 failed。既有未知行不得追补原 ACK。

独立 evidence 复用相同绑定，加 `kind/operation/source/evidence_digest/request_id`；kind=request_completed 时 source=provider_request_status，kind=target_retired 时 source=independent_target_isolation，并须 late_delete_isolated=true。字段校验不认证事实，认证由内部只读验证器负责。postcheck 仅留固定 state 及合法 U64 count；供应商正文、错误和凭据不进入该命名空间。并发核实必须锁定原 run/item，迟到 unknown 不覆盖 confirmed；不改 manifest 或 fixed_scope。行为见[向量回执契约](api.md#s15-vector-receipt)。

<a id="mysql-revision-ledger"></a>
### 本地 MySQL 迁移版本记录

从原 v8h 库通过 Alembic 升级时，v9a 先将已有 `alembic_version.version_num` 从小于128字符的 VARCHAR 扩为128，避免33字符的 revision 在业务DDL提交后无法记录；不改 revision 身份、业务字段或已有配置。无版本表的直接隔离迁移调用保持可用，SQLite不执行该MySQL专用变更。真实CLI升级、再次进入及保留行验证见本轮STEP §3。
