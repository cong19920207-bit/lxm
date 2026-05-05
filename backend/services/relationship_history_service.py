# -*- coding: utf-8 -*-
# 关系扩展字段变更历史服务（R-L1L3-05 append-only）

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.relationship_change_history import RelationshipChangeHistory

logger = logging.getLogger(__name__)


class RelationshipHistoryService:
    """关系扩展字段变更历史写入服务（append-only，仅 INSERT）"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append_history(
        self,
        relationship_id: int,
        user_id: int,
        field_name: str,
        old_value: Optional[str],
        new_value: str,
        trigger_source: str = "step6",
        round_id: Optional[str] = None,
    ) -> RelationshipChangeHistory:
        """写入一条变更历史记录（append-only，仅做 INSERT，不做 UPDATE 或 DELETE）"""
        record = RelationshipChangeHistory(
            relationship_id=relationship_id,
            user_id=user_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            trigger_source=trigger_source,
            round_id=round_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(record)
        await self.db.flush()
        logger.debug(
            "写入关系变更历史: relationship_id=%d, user_id=%d, field=%s, source=%s",
            relationship_id, user_id, field_name, trigger_source,
        )
        return record

    async def get_history_by_relationship(
        self,
        relationship_id: int,
        limit: int = 50,
    ) -> list[RelationshipChangeHistory]:
        """按 relationship_id 查询变更历史（按 created_at 升序）"""
        stmt = (
            select(RelationshipChangeHistory)
            .where(RelationshipChangeHistory.relationship_id == relationship_id)
            .order_by(RelationshipChangeHistory.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_history_by_user(
        self,
        user_id: int,
        limit: int = 50,
    ) -> list[RelationshipChangeHistory]:
        """按 user_id 查询变更历史（按 created_at 升序）"""
        stmt = (
            select(RelationshipChangeHistory)
            .where(RelationshipChangeHistory.user_id == user_id)
            .order_by(RelationshipChangeHistory.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
