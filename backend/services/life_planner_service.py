# -*- coding: utf-8 -*-
# 生活流·Life Planner 服务（STEP-005 起）
#
# STEP-005：LLM-01 周大纲生成 generate_week_outline + 当月生活比例软约束统计。

import calendar
import json
import logging
import re
from datetime import date, datetime, timedelta

from sqlalchemy import select

from backend.constants.life_feed_config import (
    CONFIG_CATEGORIES_VOCAB,
    CONFIG_HOME_CITY,
    CONFIG_LXM_DISLIKES,
    CONFIG_LXM_LIKES,
    DEFAULT_CATEGORIES_VOCAB,
    DEFAULT_HOME_CITY,
    DEFAULT_LXM_DISLIKES,
    DEFAULT_LXM_LIKES,
)
from backend.database import async_session_maker
from backend.models.life_plan import LifePlan
from backend.models.life_plan_outline import LifePlanOutline
from backend.services.deepseek_llm_service import deepseek_llm_service
from backend.services.life_feed_config_service import get_life_feed_config
from backend.services.life_prompt_service import render_prompt

logger = logging.getLogger(__name__)

# 剥离 LLM 输出可能包裹的 markdown 代码块围栏（```json ... ```）
_MARKDOWN_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")

_DATE_FMT = "%Y-%m-%d"

# 日场景约束
_SCENE_MIN_COUNT = 2
_SCENE_MAX_COUNT = 5
_SCENE_TIME_START_MIN = 6 * 60   # 06:00
_SCENE_TIME_END_MAX = 20 * 60    # 20:00
_SCENE_DESC_MIN_LEN = 200
_TIME_RANGE_PATTERN = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")


class LifePlannerError(Exception):
    """周大纲/日场景生成或校验失败"""
    pass


class SceneValidationError(Exception):
    """日场景校验失败（内部使用，转化为 gen_status='failed'）"""
    pass


def _parse_hhmm(hh: str, mm: str) -> int:
    h, m = int(hh), int(mm)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise SceneValidationError(f"非法时间 {hh}:{mm}")
    return h * 60 + m


def _strip_markdown_fence(text: str) -> str:
    """去掉首尾 markdown 代码块围栏，返回纯 JSON 文本。"""
    if not text:
        return ""
    stripped = text.strip()
    # 去开头 ```json / ``` ，去结尾 ```
    stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _parse_llm_json(raw: str) -> dict:
    """剥离 markdown 后解析 JSON；失败抛 LifePlannerError。"""
    text = _strip_markdown_fence(raw)
    if not text:
        raise LifePlannerError("LLM 返回空文本")
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise LifePlannerError(f"LLM 输出 JSON 解析失败: {e}") from e
    if not isinstance(data, dict):
        raise LifePlannerError("LLM 输出顶层不是对象")
    return data


def _month_bounds(d: date) -> tuple[date, date]:
    """返回 d 所在自然月的首日与末日。"""
    first = d.replace(day=1)
    last_day = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=last_day)
    return first, last


def _classify_month_days(rows: list[LifePlanOutline], home_city: str) -> dict:
    """
    统计当月本地 / 短途 / 长途天数（软约束参考值，PRD 2.2.4）。

    分类口径（PRD 未给出「短途 vs 长途」精确算法，此处采用可辩护默认，
    如需调整仅改本函数）：
      - 本地：city == home_city
      - 非本地：按日期连续分组为「行程」；单天行程 → 短途；连续 ≥2 天 → 长途
        （契合「长途须含出发-途中-返回」的多日特征）。
    """
    local = 0
    away_runs: list[int] = []
    current_run = 0
    prev_date: date | None = None

    for row in sorted(rows, key=lambda r: r.plan_date):
        is_away = row.city != home_city
        if not is_away:
            if current_run:
                away_runs.append(current_run)
                current_run = 0
            local += 1
            prev_date = row.plan_date
            continue
        # 非本地：判断是否与上一非本地日连续
        if current_run and prev_date is not None and (row.plan_date - prev_date).days == 1:
            current_run += 1
        else:
            if current_run:
                away_runs.append(current_run)
            current_run = 1
        prev_date = row.plan_date

    if current_run:
        away_runs.append(current_run)

    short_days = sum(r for r in away_runs if r == 1)
    long_days = sum(r for r in away_runs if r >= 2)
    return {"local": local, "short": short_days, "long": long_days}


class LifePlannerService:
    """Life Planner：周大纲 + 日场景生成"""

    async def _get_month_stats(self, ref_date: date, home_city: str) -> dict:
        """读取 ref_date 所在自然月已落库大纲，统计本地/短途/长途天数。"""
        first, last = _month_bounds(ref_date)
        async with async_session_maker() as db:
            stmt = select(LifePlanOutline).where(
                LifePlanOutline.plan_date >= first,
                LifePlanOutline.plan_date <= last,
            )
            result = await db.execute(stmt)
            rows = list(result.scalars().all())
        return _classify_month_days(rows, home_city)

    async def _week_already_generated(self, week_start_date: date) -> bool:
        """按自然日落库计数：该周只要有 ≥1 天落库即视为已生成（PRD 2.2.5）。"""
        async with async_session_maker() as db:
            stmt = select(LifePlanOutline.id).where(
                LifePlanOutline.week_start_date == week_start_date
            ).limit(1)
            result = await db.execute(stmt)
            return result.first() is not None

    def _validate_outline(
        self, data: dict, days_count: int, plan_start_date: date, vocab: list[str]
    ) -> list[dict]:
        """校验 LLM 输出的 days 数组；失败抛 LifePlannerError。返回规范化 days。"""
        days = data.get("days")
        if not isinstance(days, list):
            raise LifePlannerError("输出缺少 days 数组")
        if len(days) != days_count:
            raise LifePlannerError(f"days 条数 {len(days)} 与 days_count {days_count} 不符")

        vocab_set = set(vocab)
        normalized: list[dict] = []
        for i, item in enumerate(days):
            if not isinstance(item, dict):
                raise LifePlannerError(f"days[{i}] 不是对象")
            date_str = str(item.get("date", "")).strip()
            city = str(item.get("city", "")).strip()
            categories = str(item.get("categories", "")).strip()
            try:
                parsed_date = datetime.strptime(date_str, _DATE_FMT).date()
            except ValueError as e:
                raise LifePlannerError(f"days[{i}].date 非法: {date_str}") from e
            if not city:
                raise LifePlannerError(f"days[{i}].city 为空")
            if not categories:
                raise LifePlannerError(f"days[{i}].categories 为空")
            cat_items = [c.strip() for c in categories.split("\n") if c.strip()]
            if not cat_items:
                raise LifePlannerError(f"days[{i}].categories 拆分后为空")
            for c in cat_items:
                if c not in vocab_set:
                    raise LifePlannerError(f"days[{i}] 分类「{c}」不在 categories_vocab 内")
            normalized.append({
                "date": parsed_date,
                "city": city,
                "categories": "\n".join(cat_items),
            })

        # 日期应自 plan_start_date 起连续递增
        for offset, item in enumerate(normalized):
            expected = plan_start_date + timedelta(days=offset)
            if item["date"] != expected:
                raise LifePlannerError(
                    f"days[{offset}].date {item['date']} 与期望 {expected} 不符"
                )
        return normalized

    async def generate_week_outline(
        self,
        days_count: int,
        week_start_date: date,
        is_manual: bool = False,
        plan_start_date: date | None = None,
    ) -> dict:
        """
        生成一周（或剩余若干自然日）大纲并落库 life_plan_outline。

        Args:
            days_count: 生成的自然日数量（常规周日触发为 7）
            week_start_date: 所属自然周周一日期
            is_manual: True=后台手动补录（gen_status='manual'）；False=自动（'auto'）
            plan_start_date: 起始生成日；None 时默认 = week_start_date（自动整周）

        Returns:
            {"status": "success"/"skipped", "days": n, "week_start_date": "..."}

        Raises:
            LifePlannerError: LLM 调用/解析/校验失败（视为技术失败，由上层触发重试）
        """
        plan_start_date = plan_start_date or week_start_date
        week_end_date = week_start_date + timedelta(days=6)

        # 已生成判定（幂等 + 23:30 重试跳过）
        if await self._week_already_generated(week_start_date):
            logger.info(
                "[LLM-01] 周大纲已存在，跳过 week_start_date=%s", week_start_date
            )
            return {"status": "skipped", "week_start_date": week_start_date.isoformat()}

        home_city = await get_life_feed_config(CONFIG_HOME_CITY, DEFAULT_HOME_CITY)
        vocab = await get_life_feed_config(CONFIG_CATEGORIES_VOCAB, DEFAULT_CATEGORIES_VOCAB)
        if not isinstance(vocab, list):
            vocab = DEFAULT_CATEGORIES_VOCAB
        month_stats = await self._get_month_stats(plan_start_date, home_city)

        variables = {
            "plan_start_date": plan_start_date.isoformat(),
            "days_count": days_count,
            "week_start_date": week_start_date.isoformat(),
            "week_end_date": week_end_date.isoformat(),
            "home_city": home_city,
            "current_month": plan_start_date.strftime("%Y-%m"),
            "month_local_days": month_stats["local"],
            "month_short_trip_days": month_stats["short"],
            "month_long_trip_days": month_stats["long"],
            "categories_vocab": ", ".join(vocab),
        }

        logger.info(
            "[LLM-01] 触发周大纲生成 week_start_date=%s days_count=%d manual=%s",
            week_start_date, days_count, is_manual,
        )

        system_prompt = await render_prompt("prompt_p01_system", variables)
        user_prompt = await render_prompt("prompt_p01_user", variables)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw = await deepseek_llm_service.call_llm("llm_01", messages)
        data = _parse_llm_json(raw)
        normalized = self._validate_outline(data, days_count, plan_start_date, vocab)

        gen_status = "manual" if is_manual else "auto"
        now = datetime.utcnow()
        async with async_session_maker() as db:
            for item in normalized:
                db.add(LifePlanOutline(
                    week_start_date=week_start_date,
                    plan_date=item["date"],
                    city=item["city"],
                    categories=item["categories"],
                    gen_status=gen_status,
                    created_at=now,
                    updated_at=now,
                ))
            await db.commit()

        logger.info(
            "[LLM-01] 周大纲生成成功 week_start_date=%s 落库 %d 天",
            week_start_date, len(normalized),
        )
        return {
            "status": "success",
            "days": len(normalized),
            "week_start_date": week_start_date.isoformat(),
        }

    # ──────────────────── STEP-007 · LLM-02 日场景 ────────────────────

    def _validate_scenes(
        self, data: dict, plan_date: date, outline_city: str, outline_categories: list[str]
    ) -> list[dict]:
        """校验并规范化 scenes；违规抛 SceneValidationError。返回带规范 scene_id 的列表。"""
        scenes = data.get("scenes")
        if not isinstance(scenes, list):
            raise SceneValidationError("输出缺少 scenes 数组")
        if not (_SCENE_MIN_COUNT <= len(scenes) <= _SCENE_MAX_COUNT):
            raise SceneValidationError(f"场景数 {len(scenes)} 不在 [2,5] 内")

        cat_set = set(outline_categories)
        normalized: list[dict] = []
        for i, sc in enumerate(scenes):
            if not isinstance(sc, dict):
                raise SceneValidationError(f"scenes[{i}] 不是对象")
            time_range = str(sc.get("time_range", "")).strip()
            m = _TIME_RANGE_PATTERN.match(time_range)
            if not m:
                raise SceneValidationError(f"scenes[{i}].time_range 格式非法: {time_range}")
            start_min = _parse_hhmm(m.group(1), m.group(2))
            end_min = _parse_hhmm(m.group(3), m.group(4))
            if start_min >= end_min:
                raise SceneValidationError(f"scenes[{i}].time_range 起止顺序非法")
            if start_min < _SCENE_TIME_START_MIN or end_min > _SCENE_TIME_END_MAX:
                raise SceneValidationError(f"scenes[{i}].time_range 超出 06:00-20:00")

            city = str(sc.get("city", "")).strip()
            if city != outline_city:
                raise SceneValidationError(
                    f"scenes[{i}].city「{city}」与大纲「{outline_city}」不符"
                )
            category = str(sc.get("category", "")).strip()
            if category not in cat_set:
                raise SceneValidationError(f"scenes[{i}].category「{category}」不在当日分类内")
            venue_type = str(sc.get("venue_type", "")).strip()
            if not venue_type:
                raise SceneValidationError(f"scenes[{i}].venue_type 为空")
            description = str(sc.get("description", "")).strip()
            if len(description) < _SCENE_DESC_MIN_LEN:
                raise SceneValidationError(
                    f"scenes[{i}].description 长度 {len(description)} < {_SCENE_DESC_MIN_LEN}"
                )

            # scene_id 规则（§0.5 定案）：scene_{plan_date}_{seq:03d}
            scene_id = f"scene_{plan_date.isoformat()}_{i + 1:03d}"
            normalized.append({
                "scene_id": scene_id,
                "time_range": time_range,
                "city": city,
                "category": category,
                "venue_type": venue_type,
                "description": description,
            })
        return normalized

    async def _get_outline(self, plan_date: date) -> LifePlanOutline | None:
        async with async_session_maker() as db:
            stmt = select(LifePlanOutline).where(LifePlanOutline.plan_date == plan_date)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def _upsert_life_plan(self, plan_date: date, scenes: list, gen_status: str) -> None:
        """按 plan_date 幂等写入 life_plan（存在则更新 scenes/gen_status）。"""
        async with async_session_maker() as db:
            stmt = select(LifePlan).where(LifePlan.plan_date == plan_date)
            existing = (await db.execute(stmt)).scalars().first()
            if existing:
                existing.scenes = scenes
                existing.gen_status = gen_status
            else:
                db.add(LifePlan(
                    plan_date=plan_date, scenes=scenes,
                    gen_status=gen_status, created_at=datetime.utcnow(),
                ))
            await db.commit()

    async def generate_daily_scenes(self, plan_date: date) -> dict:
        """
        为 plan_date 生成 2~5 个日场景并落库 life_plan（LLM-02）。

        Returns:
            {"status": "ready"/"failed"/"skipped_no_outline"/"skipped_ready", ...}
            —— 校验/生成失败落 gen_status='failed'（供 00:30 重试），不抛异常。
        """
        outline = await self._get_outline(plan_date)
        if outline is None:
            logger.info("[LLM-02] 无大纲，跳过 plan_date=%s", plan_date)
            return {"status": "skipped_no_outline", "plan_date": plan_date.isoformat()}

        async with async_session_maker() as db:
            existing = (await db.execute(
                select(LifePlan).where(LifePlan.plan_date == plan_date)
            )).scalars().first()
            if existing and existing.gen_status == "ready":
                logger.info("[LLM-02] 当日场景已 ready，跳过 plan_date=%s", plan_date)
                return {"status": "skipped_ready", "plan_date": plan_date.isoformat()}

        outline_categories = [c.strip() for c in outline.categories.split("\n") if c.strip()]
        lxm_likes = await get_life_feed_config(CONFIG_LXM_LIKES, DEFAULT_LXM_LIKES)
        lxm_dislikes = await get_life_feed_config(CONFIG_LXM_DISLIKES, DEFAULT_LXM_DISLIKES)

        variables = {
            "plan_date": plan_date.isoformat(),
            "outline_city": outline.city,
            "outline_categories": outline.categories,
            "lxm_likes": lxm_likes,
            "lxm_dislikes": lxm_dislikes,
        }

        logger.info("[LLM-02] 触发日场景生成 plan_date=%s", plan_date)
        try:
            system_prompt = await render_prompt("prompt_p02_system", variables)
            user_prompt = await render_prompt("prompt_p02_user", variables)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            raw = await deepseek_llm_service.call_llm("llm_02", messages)
            data = _parse_llm_json(raw)
            normalized = self._validate_scenes(
                data, plan_date, outline.city, outline_categories
            )
        except (LifePlannerError, SceneValidationError) as e:
            logger.warning("[LLM-02] 日场景生成失败 plan_date=%s: %s", plan_date, e)
            await self._upsert_life_plan(plan_date, [], "failed")
            return {"status": "failed", "plan_date": plan_date.isoformat(), "reason": str(e)}
        except Exception as e:
            logger.error(
                "[LLM-02] 日场景生成异常 plan_date=%s: %s", plan_date, e, exc_info=True
            )
            await self._upsert_life_plan(plan_date, [], "failed")
            return {"status": "failed", "plan_date": plan_date.isoformat(), "reason": str(e)}

        await self._upsert_life_plan(plan_date, normalized, "ready")
        logger.info(
            "[LLM-02] 日场景生成成功 plan_date=%s 场景数=%d", plan_date, len(normalized)
        )
        return {"status": "ready", "plan_date": plan_date.isoformat(), "scenes": len(normalized)}


# 全局单例
life_planner_service = LifePlannerService()
