# -*- coding: utf-8 -*-
# 生活流·她的宇宙服务（STEP-009 · LLM-03）
#
# 每日 00:45 遍历当日 ready 场景，每 scene 一次 LLM-03：
#   - 动态心理快照 worldview_snapshot（按 scene_id upsert）
#   - 静态观点 worldview_event（event_name UNIQUE，INSERT IGNORE 不覆盖首次版本）
#
# ⚠️ 设计文档冲突说明（core_attitude）：
#   steps.md STEP-009 要求校验 core_attitude ∈ {喜欢/排斥/矛盾/无感}，
#   但 prompt_spec P-03 的 JSON schema 未单独输出该字段，而将「核心态度」
#   融入 event_view 维度①。本实现采用兼容口径：
#     1) 若 LLM 输出含显式 core_attitude 键 → 直接枚举校验；
#     2) 否则回退到在 event_view 文本中检测四态度词之一。
#   该字段仅用于校验，worldview_event 表无对应列，不落库。（待确认）

import json
import logging
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.constants.life_feed_config import CONFIG_EMOTION_VOCAB, DEFAULT_EMOTION_VOCAB
from backend.database import async_session_maker
from backend.models.life_plan import LifePlan
from backend.models.worldview_event import WorldviewEvent
from backend.models.worldview_snapshot import WorldviewSnapshot
from backend.services.deepseek_llm_service import deepseek_llm_service
from backend.services.life_feed_config_service import get_life_feed_config
from backend.services.life_prompt_service import render_prompt

logger = logging.getLogger(__name__)

_SNAPSHOT_TIMEOUT = 45.0        # 单次 LLM-03 调用超时 45s（PRD 3.2）
_MAX_ATTEMPTS = 3               # 含首次，最多 3 次立即重试
_ATTITUDE_ENUM = ("喜欢", "排斥", "矛盾", "无感")
_EVENT_NAME_MIN_LEN = 10
_EVENT_VIEW_MIN_LEN = 100
_EVENT_VIEW_MAX_LEN = 200

_FENCE_HEAD = re.compile(r"^```[a-zA-Z]*\s*")
_FENCE_TAIL = re.compile(r"\s*```$")


class HerUniverseError(Exception):
    """她的宇宙快照/事件生成或校验失败（内容失败或最终失败）"""
    pass


def _strip_fence(text: str) -> str:
    s = (text or "").strip()
    s = _FENCE_HEAD.sub("", s)
    s = _FENCE_TAIL.sub("", s)
    return s.strip()


def _validate_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        raise HerUniverseError("snapshot 不是对象")
    out = {}
    for f in ("feeling_text", "emotion_value", "focus_tag", "worldview_trigger"):
        v = str(snapshot.get(f, "")).strip()
        if not v:
            raise HerUniverseError(f"snapshot.{f} 为空")
        out[f] = v
    return out


def _resolve_core_attitude(event: dict) -> str:
    """兼容取核心态度：显式字段优先，否则从 event_view 检测四态度词。"""
    explicit = str(event.get("core_attitude", "")).strip()
    if explicit:
        if explicit not in _ATTITUDE_ENUM:
            raise HerUniverseError(f"core_attitude 非法：{explicit}")
        return explicit
    view = str(event.get("event_view", ""))
    hit = [a for a in _ATTITUDE_ENUM if a in view]
    if not hit:
        raise HerUniverseError("event_view 未体现核心态度（喜欢/排斥/矛盾/无感）")
    return hit[0]


def _validate_event(event: dict) -> dict:
    if not isinstance(event, dict):
        raise HerUniverseError("worldview_event 不是对象")
    event_name = str(event.get("event_name", "")).strip()
    if len(event_name) < _EVENT_NAME_MIN_LEN:
        raise HerUniverseError(f"event_name 过短(<{_EVENT_NAME_MIN_LEN}字)：{event_name}")
    event_view = str(event.get("event_view", "")).strip()
    if len(event_view) < _EVENT_VIEW_MIN_LEN:
        raise HerUniverseError(f"event_view 过短(<{_EVENT_VIEW_MIN_LEN}字)")
    if len(event_view) > _EVENT_VIEW_MAX_LEN:
        # 上限按软约束处理：仅告警，不判失败（避免真实 LLM 略超即整条失败）
        logger.warning("[LLM-03] event_view 长度 %d 超过 %d（软约束，不失败）",
                       len(event_view), _EVENT_VIEW_MAX_LEN)
    _resolve_core_attitude(event)  # 校验核心态度（不落库）
    return {"event_name": event_name, "event_view": event_view}


class HerUniverseService:
    """她的宇宙：LLM-03 快照 + 事件生成"""

    async def generate_for_scene(self, scene: dict, plan_date: date) -> tuple[dict, dict]:
        """
        对单个 scene 生成快照 + 事件。最多 3 次立即重试（含首次）。

        Returns:
            (snapshot_dict, event_dict)

        Raises:
            HerUniverseError: 3 次尝试均失败（超时/内容失败）
        """
        emotion_vocab = await get_life_feed_config(CONFIG_EMOTION_VOCAB, DEFAULT_EMOTION_VOCAB)
        if isinstance(emotion_vocab, list):
            emotion_vocab_str = "、".join(emotion_vocab)
        else:
            emotion_vocab_str = str(emotion_vocab)

        user_vars = {
            "time_range": scene.get("time_range", ""),
            "city": scene.get("city", ""),
            "category": scene.get("category", ""),
            "venue_type": scene.get("venue_type", ""),
            "description": scene.get("description", ""),
            "emotion_vocab": emotion_vocab_str,
        }
        system_prompt = await render_prompt("prompt_p03_system", {})
        user_prompt = await render_prompt("prompt_p03_user", user_vars)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        scene_id = scene.get("scene_id", "?")
        last_err: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                raw = await deepseek_llm_service.call_llm(
                    "llm_03", messages, timeout=_SNAPSHOT_TIMEOUT
                )
                data = json.loads(_strip_fence(raw))
                if not isinstance(data, dict):
                    raise HerUniverseError("输出顶层不是对象")
                snapshot = _validate_snapshot(data.get("snapshot"))
                event = _validate_event(data.get("worldview_event"))
                logger.info(
                    "[LLM-03] 单条成功 scene_id=%s 尝试=%d", scene_id, attempt
                )
                return snapshot, event
            except Exception as e:  # noqa: BLE001 — 超时/解析/校验统一按内容失败重试
                last_err = e
                logger.warning(
                    "[LLM-03] 单条中途失败 scene_id=%s 尝试=%d/%d 原因=%s",
                    scene_id, attempt, _MAX_ATTEMPTS, e,
                )

        raise HerUniverseError(
            f"scene_id={scene_id} 连续 {_MAX_ATTEMPTS} 次失败：{last_err}"
        )

    async def _upsert_snapshot(
        self, plan_date: date, scene_id: str, snapshot: dict | None, gen_status: str
    ) -> None:
        async with async_session_maker() as db:
            stmt = select(WorldviewSnapshot).where(
                WorldviewSnapshot.scene_id == scene_id,
                WorldviewSnapshot.plan_date == plan_date,
            )
            existing = (await db.execute(stmt)).scalars().first()
            data = snapshot or {}
            if existing:
                existing.feeling_text = data.get("feeling_text")
                existing.emotion_value = data.get("emotion_value")
                existing.focus_tag = data.get("focus_tag")
                existing.worldview_trigger = data.get("worldview_trigger")
                existing.gen_status = gen_status
            else:
                db.add(WorldviewSnapshot(
                    plan_date=plan_date,
                    scene_id=scene_id,
                    feeling_text=data.get("feeling_text"),
                    emotion_value=data.get("emotion_value"),
                    focus_tag=data.get("focus_tag"),
                    worldview_trigger=data.get("worldview_trigger"),
                    gen_status=gen_status,
                    created_at=datetime.utcnow(),
                ))
            await db.commit()

    async def _insert_event_if_absent(self, event: dict, source_scene_id: str) -> bool:
        """INSERT IGNORE 语义：event_name 已存在则跳过，返回 False；新增返回 True。"""
        async with async_session_maker() as db:
            stmt = select(WorldviewEvent.id).where(
                WorldviewEvent.event_name == event["event_name"]
            ).limit(1)
            if (await db.execute(stmt)).first() is not None:
                return False
            db.add(WorldviewEvent(
                event_name=event["event_name"],
                event_view=event["event_view"],
                source_scene_id=source_scene_id,
                created_at=datetime.utcnow(),
            ))
            try:
                await db.commit()
            except IntegrityError:
                # 并发下唯一键冲突：视为已存在，跳过
                await db.rollback()
                return False
            return True

    async def daily_her_universe_task(self, plan_date: date) -> dict:
        """
        主任务：遍历当日 ready 场景串行生成。单条失败不阻断其余。

        Returns:
            {"status": "skipped"/"done", "success": n, "failed": m, "events_new": k}
        """
        logger.info("[LLM-03] 任务触发 plan_date=%s", plan_date)
        async with async_session_maker() as db:
            life_plan = (await db.execute(
                select(LifePlan).where(LifePlan.plan_date == plan_date)
            )).scalars().first()

        if life_plan is None or life_plan.gen_status != "ready":
            logger.info("[LLM-03] 当日无 ready 生活计划，任务跳过 plan_date=%s", plan_date)
            return {"status": "skipped", "success": 0, "failed": 0, "events_new": 0}

        scenes = life_plan.scenes or []
        logger.info("[LLM-03] ready 场景数=%d plan_date=%s", len(scenes), plan_date)

        success, failed, events_new = 0, 0, 0
        for scene in scenes:
            scene_id = scene.get("scene_id", "?")
            logger.info("[LLM-03] 单条开始 scene_id=%s", scene_id)
            try:
                snapshot, event = await self.generate_for_scene(scene, plan_date)
            except HerUniverseError as e:
                logger.error("[LLM-03] 单条最终失败 scene_id=%s: %s", scene_id, e)
                await self._upsert_snapshot(plan_date, scene_id, None, "failed")
                failed += 1
                continue

            await self._upsert_snapshot(plan_date, scene_id, snapshot, "ready")
            inserted = await self._insert_event_if_absent(event, scene_id)
            events_new += 1 if inserted else 0
            logger.info(
                "[LLM-03] event 写入 event_name=%s 结果=%s",
                event["event_name"], "新增" if inserted else "跳过",
            )
            success += 1

        logger.info(
            "[LLM-03] 整体完成 plan_date=%s 成功=%d 失败=%d 新增事件=%d",
            plan_date, success, failed, events_new,
        )
        return {
            "status": "done", "success": success,
            "failed": failed, "events_new": events_new,
        }


# 全局单例
her_universe_service = HerUniverseService()
