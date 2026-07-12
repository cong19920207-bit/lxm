# -*- coding: utf-8 -*-
"""STEP-001：生活流全量表 + users/relationship/agent_message 扩展

- 新增 8 张表：life_plan_outline / life_plan / worldview_snapshot / worldview_event /
  feed_post / feed_like / feed_comment（含 due_at） / agent_aware_queue
- 扩展：users.last_feed_entered_at
- 扩展：relationship.{like_aware_special_used_count, read_aware_special_used_count,
  has_ever_commented_feed}
- 变更：agent_message.trigger_type 由 String(10) → String(16)；应用层枚举新增
  LIKE_AWARE / READ_AWARE（供 M2 STEP-020/021 消费）
- 二选一定案（§0.5）：feed_comment.due_at DATETIME NULL 供 STEP-018 DB 轮询消费

Revision ID: v6a_step001_001
Revises: v5_covers_beijing_001
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision: str = "v6a_step001_001"
down_revision: Union[str, None] = "v5_covers_beijing_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─────────────────────────── users / relationship 扩展列 ───────────────────────────

_USERS_NEW_COLUMNS = [
    (
        "last_feed_entered_at",
        sa.DateTime(),
        None,
        "用户最近一次进入朋友圈页的时间；用于首页 [New] 徽标判定（NULL=从未进入）",
    ),
]

_RELATIONSHIP_NEW_COLUMNS = [
    (
        "like_aware_special_used_count",
        sa.Integer(),
        "0",
        "点赞 IM 特殊档已使用次数（入队成功 +1；与 like_aware_special_max_count 比较；可后台重置便于测试）",
    ),
    (
        "read_aware_special_used_count",
        sa.Integer(),
        "0",
        "已读 IM 特殊档已使用次数（入队成功 +1；与 read_aware_special_max_count 比较；可后台重置便于测试）",
    ),
    (
        "has_ever_commented_feed",
        sa.SmallInteger(),
        "0",
        "是否已发生过全局首次评论（用于评论 30s override；置 1 后不回退，便于测试重置）",
    ),
]


def _existing_columns(table_name: str) -> set[str]:
    """幂等辅助：返回目标表已有列集合；离线模式返回空集（不做检测）"""
    if context.is_offline_mode():
        return set()
    bind = op.get_bind()
    insp = inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def _existing_tables() -> set[str]:
    if context.is_offline_mode():
        return set()
    bind = op.get_bind()
    insp = inspect(bind)
    return set(insp.get_table_names())


# ─────────────────────────── upgrade ───────────────────────────


def upgrade() -> None:
    tables = _existing_tables()

    # 1) life_plan_outline
    if "life_plan_outline" not in tables:
        op.create_table(
            "life_plan_outline",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("week_start_date", sa.Date(), nullable=False, comment="所属自然周周一日期"),
            sa.Column("plan_date", sa.Date(), nullable=False, unique=True, comment="自然日日期"),
            sa.Column("city", sa.String(50), nullable=False, comment="当天所在城市"),
            sa.Column(
                "categories",
                sa.String(200),
                nullable=False,
                comment="当天内容分类，多个用\\n分隔；取值受后台 categories_vocab 固定枚举表约束（v1.8）",
            ),
            sa.Column(
                "gen_status",
                sa.String(16),
                nullable=False,
                comment="生成来源：auto=自动生成 / manual=人工补录",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_life_plan_outline_week_start_date", "life_plan_outline", ["week_start_date"])
        op.create_index("idx_life_plan_outline_plan_date", "life_plan_outline", ["plan_date"])

    # 2) life_plan
    if "life_plan" not in tables:
        op.create_table(
            "life_plan",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "plan_date",
                sa.Date(),
                nullable=False,
                unique=True,
                comment="计划日期，关联 life_plan_outline.plan_date",
            ),
            sa.Column(
                "scenes",
                sa.JSON(),
                nullable=False,
                comment="场景列表（scene_id/time_range/city/category/venue_type/description）；venue_type 自由发挥不受枚举约束",
            ),
            sa.Column(
                "gen_status",
                sa.String(16),
                nullable=False,
                comment="生成状态：generating / ready / failed",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_life_plan_plan_date", "life_plan", ["plan_date"])

    # 3) worldview_snapshot
    if "worldview_snapshot" not in tables:
        op.create_table(
            "worldview_snapshot",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_date", sa.Date(), nullable=False, comment="关联计划日期"),
            sa.Column("scene_id", sa.String(64), nullable=False, comment="关联场景 ID"),
            sa.Column("feeling_text", sa.Text(), nullable=True, comment="自然语言感受描述（A）"),
            sa.Column(
                "emotion_value",
                sa.String(50),
                nullable=True,
                comment="情绪值标签（B），优先取自 emotion_vocab 核心词表；LLM 可视场景生成更贴切的自由词",
            ),
            sa.Column("focus_tag", sa.String(100), nullable=True, comment="当前关注点（B）"),
            sa.Column(
                "worldview_trigger",
                sa.String(100),
                nullable=True,
                comment="触发的价值观标签（B），用于写入她的宇宙事件库 event_name",
            ),
            sa.Column(
                "gen_status",
                sa.String(16),
                nullable=False,
                comment="生成状态：generating / ready / failed",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_worldview_snapshot_plan_date", "worldview_snapshot", ["plan_date"])
        op.create_index("idx_worldview_snapshot_scene_id", "worldview_snapshot", ["scene_id"])

    # 4) worldview_event
    if "worldview_event" not in tables:
        op.create_table(
            "worldview_event",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "event_name",
                sa.String(200),
                nullable=False,
                unique=True,
                comment='话题名称（唯一键，描述性短语，如"在人多景区的感受与应对方式"）',
            ),
            sa.Column(
                "event_view",
                sa.Text(),
                nullable=False,
                comment="林小梦对该话题的固定看法（100-200字，含核心态度[喜欢/排斥/矛盾/无感]/典型场景/行为倾向）",
            ),
            sa.Column(
                "source_scene_id",
                sa.String(64),
                nullable=True,
                comment="首次触发生成的 scene_id，可溯源至来源场景",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                comment="首次写入时间，可用于后台按时间溯源",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_worldview_event_event_name", "worldview_event", ["event_name"])
        op.create_index("idx_worldview_event_source_scene_id", "worldview_event", ["source_scene_id"])

    # 5) feed_post（先建 feed_post，再建引用它的 feed_like / feed_comment / agent_aware_queue）
    if "feed_post" not in tables:
        op.create_table(
            "feed_post",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("scene_id", sa.String(64), nullable=True, comment="关联场景 ID"),
            sa.Column(
                "scheduled_publish_time",
                sa.DateTime(),
                nullable=False,
                comment="计划发布时间；查询层通过 WHERE scheduled_publish_time <= NOW() AND is_visible = 1 控制对用户端可见性",
            ),
            sa.Column(
                "actual_publish_time",
                sa.DateTime(),
                nullable=True,
                comment="实际发布时间（首次到点查询由 STEP-015 懒惰写回 NOW()；§0.5 定案）",
            ),
            sa.Column(
                "generation_status",
                sa.String(16),
                nullable=False,
                comment="生成状态：generating / ready / failed",
            ),
            sa.Column("content_text", sa.Text(), nullable=False, comment="文案内容"),
            sa.Column("hashtags", sa.JSON(), nullable=True, comment="话题标签数组（LLM-04 附带输出）"),
            sa.Column(
                "image_urls",
                sa.JSON(),
                nullable=True,
                comment='图片 CDN 地址数组，平铺结构，按生成顺序排列，不分组；域名为 CDN 加速域名，非 OSS 原始域名',
            ),
            sa.Column(
                "image_reference_url",
                sa.String(512),
                nullable=True,
                comment="人物图生图基准图地址；本版本存储于服务器本地（/static/images/avatar/character-ref/base.png），非 OSS（v1.9.4）",
            ),
            sa.Column(
                "image_type",
                sa.String(16),
                nullable=True,
                comment="本条帖子整体图片类型：selfie / daily / scenery / emotion（v1.8）",
            ),
            sa.Column(
                "emotion",
                sa.String(20),
                nullable=False,
                comment="情绪基调；双路径写入：快照 ready 时复制自 worldview_snapshot.emotion_value；快照缺失时由 LLM-04 附带输出",
            ),
            sa.Column("city", sa.String(50), nullable=False, comment="拍摄城市，来源于场景 city 字段"),
            sa.Column(
                "season",
                sa.String(20),
                nullable=False,
                comment="季节（春/夏/秋/冬）；LIFE001 落库时按 city+plan_date 计算；南半球白名单反向月份",
            ),
            sa.Column("base_likes", sa.Integer(), nullable=False, comment="默认虚拟点赞数（1–8），固定不变"),
            sa.Column(
                "like_multiplier",
                sa.Integer(),
                nullable=False,
                comment="点赞放大倍率（1–3），固定不变；展示点赞数 = base_likes × like_multiplier + real_likes",
            ),
            sa.Column(
                "real_likes",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="真实用户点赞累计数；点赞 +1，取消点赞 -1",
            ),
            sa.Column(
                "is_visible",
                sa.SmallInteger(),
                nullable=False,
                server_default="1",
                comment="管理员手动控制客户端可见性（0=隐藏/1=显示）；隐藏后历史互动数据保留",
            ),
            sa.Column(
                "dedup_hash",
                sa.String(64),
                nullable=False,
                comment="内容去重哈希；基于 venue_type+category+city 三字段组合生成（MD5）；7 天去重窗口",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_feed_post_scheduled_publish_time", "feed_post", ["scheduled_publish_time"])
        op.create_index("idx_feed_post_actual_publish_time", "feed_post", ["actual_publish_time"])
        op.create_index("idx_feed_post_scene_id", "feed_post", ["scene_id"])
        op.create_index("idx_feed_post_dedup_hash", "feed_post", ["dedup_hash"])

    # 6) feed_like
    if "feed_like" not in tables:
        op.create_table(
            "feed_like",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                comment="点赞用户 ID",
            ),
            sa.Column(
                "post_id",
                sa.Integer(),
                sa.ForeignKey("feed_post.id", ondelete="CASCADE"),
                nullable=False,
                comment="关联 feed_post.id",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "post_id", name="uk_feed_like_user_post"),
        )
        op.create_index("idx_feed_like_post_id", "feed_like", ["post_id"])

    # 7) feed_comment（含本次 due_at 字段，§0.5 二选一定案）
    if "feed_comment" not in tables:
        op.create_table(
            "feed_comment",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "post_id",
                sa.Integer(),
                sa.ForeignKey("feed_post.id", ondelete="CASCADE"),
                nullable=False,
                comment="关联朋友圈 feed_post.id",
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                comment="评论用户 ID",
            ),
            sa.Column("content", sa.Text(), nullable=False, comment="用户评论内容"),
            sa.Column(
                "lxm_reply",
                sa.Text(),
                nullable=True,
                comment="LXM 回复内容（由 LLM-05 生成，纯文本直接写入，无 JSON 包装，v1.8 明确）",
            ),
            sa.Column("lxm_reply_at", sa.DateTime(), nullable=True, comment="LXM 回复发出时间"),
            sa.Column(
                "lxm_reply_read_at",
                sa.DateTime(),
                nullable=True,
                comment="用户已读 LXM 回复时间（NULL=未读，计入首页角标）",
            ),
            sa.Column(
                "gen_status",
                sa.String(16),
                nullable=False,
                server_default="pending",
                comment="LXM 回复生成状态（LLM-05）：pending/generating/ready/failed",
            ),
            sa.Column(
                "due_at",
                sa.DateTime(),
                nullable=True,
                comment="LLM-05 计划回复时间；轮询消费用（STEP-018 每 30s 扫 due_at<=NOW() AND gen_status='pending'）",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_feed_comment_post_id", "feed_comment", ["post_id"])
        op.create_index("idx_feed_comment_user_id", "feed_comment", ["user_id"])
        op.create_index("idx_feed_comment_gen_status", "feed_comment", ["gen_status"])
        op.create_index(
            "idx_feed_comment_due_at_gen_status", "feed_comment", ["due_at", "gen_status"]
        )

    # 8) agent_aware_queue（M2 主用，M1 建表保留结构）
    if "agent_aware_queue" not in tables:
        op.create_table(
            "agent_aware_queue",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                comment="触发用户 ID",
            ),
            sa.Column(
                "trigger_type",
                sa.String(16),
                nullable=False,
                comment="触发类型：LIKE_AWARE / READ_AWARE",
            ),
            sa.Column(
                "post_id",
                sa.Integer(),
                sa.ForeignKey("feed_post.id", ondelete="CASCADE"),
                nullable=False,
                comment="关联 feed_post.id",
            ),
            sa.Column(
                "relationship_stage",
                sa.String(20),
                nullable=False,
                comment="入队时的关系阶段快照（stranger/friend/intimate/soulmate），阶段升级不重算",
            ),
            sa.Column(
                "due_at",
                sa.DateTime(),
                nullable=False,
                comment="计划发送时间，由触发时刻+对应延迟窗口计算得出",
            ),
            sa.Column(
                "status",
                sa.String(16),
                nullable=False,
                server_default="pending",
                comment="记录状态：pending / sent / failed",
            ),
            sa.Column(
                "agent_message_id",
                sa.Integer(),
                nullable=True,
                comment="生成成功后关联的 agent_message.id，便于后台联合查询展示",
            ),
            sa.Column(
                "fail_reason",
                sa.String(255),
                nullable=True,
                comment="失败原因，生成失败时记录",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                comment="触发/入队时间",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_agent_aware_queue_user_id", "agent_aware_queue", ["user_id"])
        op.create_index(
            "idx_agent_aware_queue_due_at_status", "agent_aware_queue", ["due_at", "status"]
        )
        op.create_index("idx_agent_aware_queue_post_id", "agent_aware_queue", ["post_id"])

    # 9) users 扩展列
    users_cols = _existing_columns("users")
    for col_name, col_type, default, comment in _USERS_NEW_COLUMNS:
        if col_name not in users_cols:
            op.add_column(
                "users",
                sa.Column(
                    col_name,
                    col_type,
                    nullable=True,
                    server_default=default,
                    comment=comment,
                ),
            )

    # 10) relationship 扩展列
    rel_cols = _existing_columns("relationship")
    for col_name, col_type, default, comment in _RELATIONSHIP_NEW_COLUMNS:
        if col_name not in rel_cols:
            op.add_column(
                "relationship",
                sa.Column(
                    col_name,
                    col_type,
                    nullable=False,
                    server_default=default,
                    comment=comment,
                ),
            )

    # 11) agent_message.trigger_type：String(10) → String(16)
    #     （幂等：若已是 >=16 或离线模式，仍执行 alter，MySQL 幂等友好）
    if not context.is_offline_mode():
        bind = op.get_bind()
        dialect = bind.dialect.name
        if dialect == "mysql":
            op.alter_column(
                "agent_message",
                "trigger_type",
                existing_type=sa.String(10),
                type_=sa.String(16),
                existing_nullable=False,
            )
        # 其他数据库（如 SQLite）VARCHAR 无长度约束，无需 alter


# ─────────────────────────── downgrade ───────────────────────────


def downgrade() -> None:
    # 顺序：先回滚 alter/add_column，再 drop 引用表，最后 drop 主表
    if not context.is_offline_mode():
        bind = op.get_bind()
        dialect = bind.dialect.name
        if dialect == "mysql":
            op.alter_column(
                "agent_message",
                "trigger_type",
                existing_type=sa.String(16),
                type_=sa.String(10),
                existing_nullable=False,
            )

    rel_cols = _existing_columns("relationship")
    for col_name, _, _, _ in reversed(_RELATIONSHIP_NEW_COLUMNS):
        if col_name in rel_cols:
            op.drop_column("relationship", col_name)

    users_cols = _existing_columns("users")
    for col_name, _, _, _ in reversed(_USERS_NEW_COLUMNS):
        if col_name in users_cols:
            op.drop_column("users", col_name)

    tables = _existing_tables()

    # 先 drop 引用表（含 FK），再 drop 被引用表
    for tname in [
        "agent_aware_queue",
        "feed_comment",
        "feed_like",
        "feed_post",
        "worldview_event",
        "worldview_snapshot",
        "life_plan",
        "life_plan_outline",
    ]:
        if tname in tables:
            op.drop_table(tname)
