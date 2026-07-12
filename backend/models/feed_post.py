# -*- coding: utf-8 -*-
# 生活流·朋友圈帖子表 feed_post 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# actual_publish_time 二选一定案（§0.5）：STEP-013 落库时留 NULL；
#   STEP-015 Feed 列表 API 命中 scheduled_publish_time<=NOW() AND is_visible=1 AND
#   actual_publish_time IS NULL 时，同步 UPDATE 一次为 NOW()。无独立定时任务。

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FeedPost(Base):
    """朋友圈内容表（v1.7 image_urls 平铺；v1.8 emotion 双路径；v1.9.4 base.png）"""

    __tablename__ = "feed_post"
    __table_args__ = (
        Index("idx_feed_post_scheduled_publish_time", "scheduled_publish_time"),
        Index("idx_feed_post_actual_publish_time", "actual_publish_time"),
        Index("idx_feed_post_scene_id", "scene_id"),
        Index("idx_feed_post_dedup_hash", "dedup_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    scene_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="关联场景 ID"
    )
    scheduled_publish_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment=(
            "计划发布时间；查询层通过 WHERE scheduled_publish_time <= NOW() "
            "AND is_visible = 1 控制对用户端可见性"
        ),
    )
    actual_publish_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="实际发布时间（首次到点查询由 STEP-015 懒惰写回 NOW()；§0.5 定案）",
    )
    # ENUM('generating','ready','failed')
    generation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="生成状态：generating / ready / failed"
    )

    content_text: Mapped[str] = mapped_column(Text, nullable=False, comment="文案内容")
    hashtags: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="话题标签数组（LLM-04 附带输出）"
    )
    image_urls: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            '图片 CDN 地址数组，平铺结构，按生成顺序排列，不分组'
            '（如 ["https://cdn.../a.webp"]）；域名为 CDN 加速域名，非 OSS 原始域名'
        ),
    )
    image_reference_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment=(
            "人物图生图基准图地址；本版本存储于服务器本地"
            "（/static/images/avatar/character-ref/base.png），非 OSS（v1.9.4）"
        ),
    )
    # ENUM('selfie','daily','scenery','emotion')
    image_type: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        comment=(
            "本条帖子整体图片类型（整条帖子抽签确定一个类型，所有图片走同一策略；"
            "daily/scenery/emotion 三类型对应三套独立 Prompt 模板 P-13a/b/c，v1.8）"
        ),
    )
    emotion: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment=(
            "情绪基调；双路径写入：快照 ready 时复制自 worldview_snapshot.emotion_value；"
            "快照缺失时由 LLM-04 从场景描述中判断并附带输出；取值优先取自 emotion_vocab 核心词表"
        ),
    )
    city: Mapped[str] = mapped_column(String(50), nullable=False, comment="拍摄城市，来源于场景 city 字段")
    season: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment=(
            "季节（春/夏/秋/冬）；LIFE001 落库时按 city+plan_date 计算写入；"
            "南半球白名单城市使用反向月份规则"
        ),
    )

    base_likes: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="默认虚拟点赞数（1–8），固定不变"
    )
    like_multiplier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=(
            "点赞放大倍率（1–3），固定不变；仅放大 base_likes，不放大 real_likes；"
            "展示点赞数 = base_likes × like_multiplier + real_likes"
        ),
    )
    real_likes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="真实用户点赞累计数；点赞 +1，取消点赞 -1"
    )

    # 评论展示假数（与点赞同公式）；历史帖迁移默认 0×1，新帖发帖时随机写入
    base_comments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="默认虚拟评论数（新帖 1–8），固定不变；历史帖默认 0",
    )
    comment_multiplier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment=(
            "评论放大倍率（新帖 1–3），固定不变；仅放大 base_comments；"
            "展示评论数 = base_comments × comment_multiplier + 真实可见评论条数"
        ),
    )

    is_visible: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        comment=(
            "管理员手动控制客户端可见性（0=隐藏/1=显示）；"
            "隐藏后历史互动数据保留，恢复展示后完整复原"
        ),
    )

    dedup_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment=(
            "内容去重哈希；基于 venue_type+category+city 三字段组合生成（MD5）；"
            "用于 7 天去重窗口查重（v1.8）"
        ),
    )

    # M2 STEP-026 新增：SSE 新帖广播去重标记（0=未广播/1=已广播）；
    # 每 30s 广播调度任务扫描 ready+visible+到点+未广播的帖子后置 1，防止同帖重复推送
    sse_broadcasted: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="SSE 新帖广播去重标记（0=未广播/1=已广播），STEP-026 使用",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
