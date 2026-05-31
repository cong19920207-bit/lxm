# -*- coding: utf-8 -*-
# 记忆业务逻辑：向量检索、CRUD 管理
#
# M1/M10/P10（长记忆第一套下线）：第一套「LLM 提取 + 去重合并」写入链已物理删除
# （extract_and_save / _deduplicate_and_save / _extract_memories_from_llm / _parse_memory_list）。
# 记忆统一由 Step6 异步管线写入。以下保留的检索/CRUD 方法标记 @deprecated，不再被调用，
# 仅保留函数体以备审计/回滚，请勿在新链路中引用。

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import MEMORY_TYPE_USER
from backend.database import async_session_maker
from backend.models.memory import Memory
from backend.services.embedding_service import embedding_service
from backend.services.vector_service import vector_service

logger = logging.getLogger(__name__)

# ============ 重要性评分关键词规则（仍由保留的 _calculate_importance 使用）============
IMPORTANCE_KEYWORDS: dict[int, list[str]] = {
    4: [
        "结婚", "离婚", "怀孕", "生孩子", "去世", "死亡", "毕业", "入学", "高考",
        "纪念日", "生日", "周年", "搬家", "移民", "辞职", "入职", "创业",
        "手术", "住院", "确诊", "车祸", "事故", "分手", "表白", "求婚",
    ],
    3: [
        "喜欢", "讨厌", "最爱", "不喜欢", "害怕", "过敏", "习惯", "每天都",
        "一直都", "从来不", "受不了", "忌口", "禁忌", "素食", "信仰",
        "专业是", "工作是", "职业是", "养了", "宠物", "家乡", "老家",
        "名字叫", "岁", "星座", "血型",
    ],
    2: [
        "最近", "今天", "昨天", "这周", "心情", "感觉", "有点", "压力",
        "累了", "开心", "难过", "焦虑", "生气", "失眠", "加班",
    ],
}


class MemoryService:
    """记忆业务服务：检索、增删改查（第一套写入链已下线，以下方法均 @deprecated 保留）。"""

    # ================================================================
    #  search_relevant_memories —— 记忆检索 [自定义 @deprecated 保留]
    # ================================================================

    async def search_relevant_memories(
        self,
        user_id: int,
        query_text: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        [自定义 @deprecated 保留] 记忆检索（第一套链路，已停用，召回侧改走向量检索）：
        1. 生成 query embedding
        2. DashVector 检索 Top K
        3. 交叉验证 MySQL（过滤已删除 / 已过期）
        4. 返回格式化结果
        """
        try:
            query_embedding = await embedding_service.get_embedding(query_text)
            if not query_embedding:
                logger.warning("查询文本 embedding 生成失败")
                return []

            dv_results = await vector_service.search(
                query_embedding=query_embedding,
                memory_type=MEMORY_TYPE_USER,
                user_id=user_id,
                top_k=top_k,
                threshold=0.7,
            )
            if not dv_results:
                return []

            # 提取 memory_id 列表，批量校验 MySQL
            id_map: dict[int, dict] = {}
            for item in dv_results:
                mid = self._extract_memory_id(item.get("id", ""))
                if mid is not None:
                    id_map[mid] = item

            if not id_map:
                return [
                    {"content": r.get("content", ""), "score": r.get("score", 0.0)}
                    for r in dv_results
                ]

            now = datetime.utcnow()
            async with async_session_maker() as db:
                stmt = select(Memory).where(
                    and_(
                        Memory.id.in_(list(id_map.keys())),
                        Memory.is_deleted == False,  # noqa: E712
                        or_(Memory.expires_at.is_(None), Memory.expires_at > now),
                    )
                )
                result = await db.execute(stmt)
                valid_memories = {m.id: m for m in result.scalars().all()}

            valid_results = []
            for mid, dv_item in id_map.items():
                if mid in valid_memories:
                    valid_results.append({
                        "content": valid_memories[mid].content,
                        "score": dv_item.get("score", 0.0),
                    })

            return valid_results

        except Exception as e:
            logger.error("记忆检索失败 user_id=%d: %s", user_id, str(e))
            return []

    # ================================================================
    #  3. get_user_memories —— 分页查询
    # ================================================================

    async def get_user_memories(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """[自定义 @deprecated 保留] 分页获取用户所有记忆（第一套链路，已停用）。"""
        async with async_session_maker() as db:
            base_filter = and_(
                Memory.user_id == user_id,
                Memory.is_deleted == False,  # noqa: E712
            )

            # 总数
            count_stmt = select(func.count()).select_from(Memory).where(base_filter)
            total = (await db.execute(count_stmt)).scalar() or 0

            # 分页列表
            offset = (page - 1) * page_size
            list_stmt = (
                select(Memory)
                .where(base_filter)
                .order_by(Memory.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            rows = (await db.execute(list_stmt)).scalars().all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "list": [self._memory_to_dict(m) for m in rows],
            }

    # ================================================================
    #  4. update_memory —— 更新记忆
    # ================================================================

    async def update_memory(
        self,
        memory_id: int,
        user_id: int,
        new_content: str,
    ) -> bool:
        """[自定义 @deprecated 保留] 更新记忆（第一套链路，已停用）。"""
        async with async_session_maker() as db:
            memory = await self._get_valid_memory(db, memory_id, user_id)
            if not memory:
                return False

            memory.content = new_content
            memory.updated_at = datetime.utcnow()
            await db.commit()

            # 异步更新向量（失败不影响 MySQL 数据）
            try:
                embedding = await embedding_service.get_embedding(new_content)
                if embedding:
                    await vector_service.upsert(
                        memory_id=memory.id,
                        embedding=embedding,
                        metadata={
                            "user_id": user_id,
                            "content": new_content,
                            "importance_score": memory.importance_score,
                            "created_at": memory.created_at.isoformat(),
                        },
                        memory_type=MEMORY_TYPE_USER,
                    )
            except Exception as e:
                logger.error("更新记忆向量失败 memory_id=%d: %s", memory_id, str(e))

            return True

    # ================================================================
    #  5. delete_memory —— 删除记忆
    # ================================================================

    async def delete_memory(self, memory_id: int, user_id: int) -> bool:
        """[自定义 @deprecated 保留] 删除记忆（第一套链路，已停用）。"""
        async with async_session_maker() as db:
            memory = await self._get_valid_memory(db, memory_id, user_id)
            if not memory:
                return False

            memory.is_deleted = True
            memory.updated_at = datetime.utcnow()
            await db.commit()

            if memory.dashvector_id:
                try:
                    await vector_service.delete(memory.dashvector_id)
                except Exception as e:
                    logger.error(
                        "删除记忆向量失败 memory_id=%d: %s", memory_id, str(e)
                    )

            return True

    # ================================================================
    #  手动添加记忆
    # ================================================================

    async def add_memory_manual(self, user_id: int, content: str) -> dict:
        """[自定义 @deprecated 保留] 手动添加记忆（第一套链路，已停用）。"""
        score = self._calculate_importance(content)
        if score < 2:
            score = 2  # 手动添加最低给 2 分

        async with async_session_maker() as db:
            memory = Memory(
                user_id=user_id,
                content=content,
                importance_score=score,
                source="manual",
                expires_at=self._calc_expires_at(score),
            )
            db.add(memory)
            await db.flush()

            # 写入 DashVector
            try:
                embedding = await embedding_service.get_embedding(content)
                if embedding:
                    dashvector_id = await vector_service.upsert(
                        memory_id=memory.id,
                        embedding=embedding,
                        metadata={
                            "user_id": user_id,
                            "content": content,
                            "importance_score": score,
                            "created_at": memory.created_at.isoformat(),
                        },
                        memory_type=MEMORY_TYPE_USER,
                    )
                    memory.dashvector_id = dashvector_id
            except Exception as e:
                logger.error("手动添加记忆写入向量失败: %s", str(e))

            await db.commit()

            return self._memory_to_dict(memory)

    # ================================================================
    #  内部方法
    # ================================================================
    # 注：第一套提取链路的私有方法（_extract_memories_from_llm / _parse_memory_list /
    #     _deduplicate_and_save）已随 extract_and_save 一并物理删除（P10）。
    #     _calculate_importance / _calc_expires_at 因仍被保留的 add_memory_manual 引用而保留。

    @staticmethod
    def _calculate_importance(content: str) -> int:
        """通过关键词匹配计算记忆重要性评分（4/3/2/1）"""
        for score in (4, 3, 2):
            for kw in IMPORTANCE_KEYWORDS.get(score, []):
                if kw in content:
                    return score
        return 1

    @staticmethod
    def _calc_expires_at(score: int) -> datetime | None:
        """根据重要性评分计算过期时间：>= 4 永不过期，其余 180 天"""
        if score >= 4:
            return None
        return datetime.utcnow() + timedelta(days=180)

    @staticmethod
    def _extract_memory_id(dashvector_id: str) -> int | None:
        """从 dashvector_id（格式 mem_{id}）中提取 memory_id"""
        if dashvector_id.startswith("mem_"):
            try:
                return int(dashvector_id[4:])
            except ValueError:
                return None
        return None

    @staticmethod
    async def _get_valid_memory(
        db: AsyncSession, memory_id: int, user_id: int
    ) -> Memory | None:
        """查询未删除的指定记忆"""
        stmt = select(Memory).where(
            and_(
                Memory.id == memory_id,
                Memory.user_id == user_id,
                Memory.is_deleted == False,  # noqa: E712
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _memory_to_dict(m: Memory) -> dict:
        """Memory ORM 对象转前端友好的 dict"""
        return {
            "id": m.id,
            "content": m.content,
            "importance_score": m.importance_score,
            "source": m.source,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        }


# 全局单例
memory_service = MemoryService()
