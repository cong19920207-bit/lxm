# -*- coding: utf-8 -*-
# 生活流后台管理 API：周大纲（STEP-006）+ 日生活计划/场景（STEP-008）
#
# 前缀 /api/admin（见 main.py include），权限 super_admin / ai_trainer；
# 所有写操作落 operation_log。settings 走 admin_config 草稿三卡点。

import json
import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_LIFE_CATEGORY_INVALID,
    ADMIN_ERR_LIFE_GENERATE_FAILED,
    ADMIN_ERR_LIFE_OUTLINE_ALREADY_EXISTS,
    ADMIN_ERR_LIFE_OUTLINE_EXISTS_ON_DATE,
    ADMIN_ERR_LIFE_OUTLINE_MISSING,
    ADMIN_ERR_LIFE_PARAM_INVALID,
    ADMIN_ERR_LIFE_PLAN_NOT_FOUND,
    ADMIN_ERR_LIFE_SCENE_NOT_FOUND,
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
)
from backend.constants.life_feed_config import (
    CONFIG_CATEGORIES_VOCAB,
    CONFIG_HOME_CITY,
    DEFAULT_CATEGORIES_VOCAB,
    DEFAULT_HOME_CITY,
)
from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.models.life_plan import LifePlan
from backend.models.life_plan_outline import LifePlanOutline
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.life_feed_config_service import get_life_feed_config
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_READ_ROLES = ("super_admin", "ai_trainer", "ops_admin", "observer")  # ops/observer 只读

# 生活节奏比例 config_key（10.1#4）
_CFG_RATIO_LOCAL = "life_ratio_local"
_CFG_RATIO_SHORT = "life_ratio_short_trip"
_CFG_RATIO_LONG = "life_ratio_long_trip"
_DEFAULT_RATIO = {"local": 70, "short_trip": 20, "long_trip": 10}


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


async def _categories_vocab() -> list[str]:
    vocab = await get_life_feed_config(CONFIG_CATEGORIES_VOCAB, DEFAULT_CATEGORIES_VOCAB)
    return vocab if isinstance(vocab, list) else DEFAULT_CATEGORIES_VOCAB


def _outline_to_dict(o: LifePlanOutline) -> dict:
    return {
        "id": o.id,
        "week_start_date": o.week_start_date.isoformat(),
        "plan_date": o.plan_date.isoformat(),
        "city": o.city,
        "categories": [c for c in (o.categories or "").split("\n") if c],
        "gen_status": o.gen_status,
    }


# ─────────────────────────── STEP-006 周大纲 ───────────────────────────

class OutlineCreateBody(BaseModel):
    plan_date: str
    city: str
    categories: list[str]


class OutlineUpdateBody(BaseModel):
    city: str
    categories: list[str]


class OutlineGenerateBody(BaseModel):
    week_start_date: str
    days_count: int | None = None


class SettingsBody(BaseModel):
    home_city: str
    life_ratio_local: int | None = None
    life_ratio_short_trip: int | None = None
    life_ratio_long_trip: int | None = None


@router.get("/life-plan/outline", dependencies=[require_role(*_READ_ROLES)])
async def get_outline(
    week_start_date: str | None = Query(None),
    plan_date: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查询某周大纲（7 天）或单日。"""
    if plan_date:
        d = _parse_date(plan_date)
        if d is None:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
        row = (await db.execute(
            select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
        return ApiResponse.ok(data=_outline_to_dict(row) if row else None)

    if week_start_date:
        d = _parse_date(week_start_date)
        if d is None:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
        rows = (await db.execute(
            select(LifePlanOutline)
            .where(LifePlanOutline.week_start_date == d)
            .order_by(LifePlanOutline.plan_date.asc()))).scalars().all()
        return ApiResponse.ok(data=[_outline_to_dict(r) for r in rows])

    return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="需提供 week_start_date 或 plan_date")


@router.post("/life-plan/outline", dependencies=[require_role(*_ALLOWED_ROLES)])
async def create_outline(
    body: OutlineCreateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """新增单日大纲条目；已存在返回错误。"""
    d = _parse_date(body.plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
    vocab = await _categories_vocab()
    if not body.categories or any(c not in vocab for c in body.categories):
        return ApiResponse.fail(ADMIN_ERR_LIFE_CATEGORY_INVALID)

    exists = (await db.execute(
        select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
    if exists:
        return ApiResponse.fail(ADMIN_ERR_LIFE_OUTLINE_EXISTS_ON_DATE)

    # week_start_date = 该日所在自然周周一
    week_start = d - timedelta(days=d.weekday())
    row = LifePlanOutline(
        week_start_date=week_start, plan_date=d, city=body.city,
        categories="\n".join(body.categories), gen_status="manual")
    db.add(row)
    await db.flush()
    await log_operation(db, admin_user, "life_plan", "create_outline",
                        f"新增周大纲单日 {body.plan_date}", after_value=body.city, request=request)
    await db.commit()
    return ApiResponse.ok(data=_outline_to_dict(row))


@router.put("/life-plan/outline/{plan_date}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_outline(
    plan_date: str,
    body: OutlineUpdateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑单日大纲。"""
    d = _parse_date(plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
    vocab = await _categories_vocab()
    if not body.categories or any(c not in vocab for c in body.categories):
        return ApiResponse.fail(ADMIN_ERR_LIFE_CATEGORY_INVALID)

    row = (await db.execute(
        select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PLAN_NOT_FOUND)
    before = f"{row.city}|{row.categories}"
    row.city = body.city
    row.categories = "\n".join(body.categories)
    await log_operation(db, admin_user, "life_plan", "update_outline",
                        f"编辑周大纲单日 {plan_date}", before_value=before,
                        after_value=f"{body.city}|{','.join(body.categories)}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_outline_to_dict(row))


@router.delete("/life-plan/outline/{plan_date}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_outline(
    plan_date: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除单日大纲。"""
    d = _parse_date(plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
    row = (await db.execute(
        select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PLAN_NOT_FOUND)
    await db.delete(row)
    await log_operation(db, admin_user, "life_plan", "delete_outline",
                        f"删除周大纲单日 {plan_date}", before_value=row.city, request=request)
    await db.commit()
    return ApiResponse.ok(data={"deleted": plan_date})


@router.post("/life-plan/outline/generate", dependencies=[require_role(*_ALLOWED_ROLES)])
async def generate_outline(
    body: OutlineGenerateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """一键生成剩余自然日大纲（仅当今天及以后剩余日零落库时可用）。"""
    week_start = _parse_date(body.week_start_date)
    if week_start is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)

    today = date.today()
    week_end = week_start + timedelta(days=6)
    plan_start = max(week_start, today)  # 今天及以后
    if plan_start > week_end:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="该周已结束")

    # 剩余自然日已有 ≥1 天落库 → 409
    existing = (await db.execute(
        select(LifePlanOutline).where(
            LifePlanOutline.plan_date >= plan_start,
            LifePlanOutline.plan_date <= week_end))).scalars().first()
    if existing:
        return ApiResponse.fail(ADMIN_ERR_LIFE_OUTLINE_ALREADY_EXISTS)

    days_count = body.days_count or ((week_end - plan_start).days + 1)
    from backend.services.life_planner_service import life_planner_service
    try:
        result = await life_planner_service.generate_week_outline(
            days_count=days_count, week_start_date=week_start,
            is_manual=True, plan_start_date=plan_start)
    except Exception as e:
        logger.error("[后台][生活计划] 一键生成失败: %s", e, exc_info=True)
        return ApiResponse.fail(ADMIN_ERR_LIFE_GENERATE_FAILED)

    await log_operation(db, admin_user, "life_plan", "generate_outline",
                        f"一键生成大纲 week={body.week_start_date} days={days_count}",
                        after_value=json.dumps(result, ensure_ascii=False), request=request)
    await db.commit()
    return ApiResponse.ok(data=result)


@router.get("/life-plan/settings", dependencies=[require_role(*_READ_ROLES)])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """读取 home_city + 生活节奏比例（本地/短途/长途）。"""
    home_city = await get_life_feed_config(CONFIG_HOME_CITY, DEFAULT_HOME_CITY)
    local = await get_life_feed_config(_CFG_RATIO_LOCAL, _DEFAULT_RATIO["local"])
    short = await get_life_feed_config(_CFG_RATIO_SHORT, _DEFAULT_RATIO["short_trip"])
    long = await get_life_feed_config(_CFG_RATIO_LONG, _DEFAULT_RATIO["long_trip"])
    return ApiResponse.ok(data={
        "home_city": home_city,
        "life_ratio_local": local,
        "life_ratio_short_trip": short,
        "life_ratio_long_trip": long,
    })


@router.put("/life-plan/settings", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_settings(
    body: SettingsBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """写入 home_city + 生活节奏比例（走 admin_config 草稿；发布由发布接口三卡点完成）。"""
    if not body.home_city or not body.home_city.strip():
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="home_city 不能为空")

    # 各项分别存草稿（config_key 粒度独立）
    saved = []
    pairs = [
        (CONFIG_HOME_CITY, body.home_city.strip()),
        (_CFG_RATIO_LOCAL, body.life_ratio_local),
        (_CFG_RATIO_SHORT, body.life_ratio_short_trip),
        (_CFG_RATIO_LONG, body.life_ratio_long_trip),
    ]
    for key, val in pairs:
        if val is None:
            continue
        await admin_config_service.save_draft(
            db=db, config_key=key,
            config_value=json.dumps(val, ensure_ascii=False),
            updated_by=admin_user.username)
        saved.append(key)

    await log_operation(db, admin_user, "life_plan", "update_settings",
                        f"保存生活计划设置草稿 {saved}", after_value=body.home_city, request=request)
    await db.commit()
    return ApiResponse.ok(data={"draft_saved": saved})


# ─────────────────────────── STEP-008 日生活计划/场景 ───────────────────────────

class SceneBody(BaseModel):
    time_range: str
    city: str
    category: str
    venue_type: str
    description: str


def _plan_to_dict(p: LifePlan) -> dict:
    return {
        "id": p.id,
        "plan_date": p.plan_date.isoformat(),
        "scenes": p.scenes or [],
        "gen_status": p.gen_status,
    }


def _next_scene_id(plan_date: date, scenes: list) -> str:
    max_seq = 0
    prefix = f"scene_{plan_date.isoformat()}_"
    for s in scenes:
        sid = str(s.get("scene_id", ""))
        if sid.startswith(prefix):
            try:
                max_seq = max(max_seq, int(sid[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{max_seq + 1:03d}"


@router.get("/life-plan/daily", dependencies=[require_role(*_READ_ROLES)])
async def get_daily(
    plan_date: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查询某日 life_plan 或范围查询（分页）。"""
    if plan_date:
        d = _parse_date(plan_date)
        if d is None:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
        row = (await db.execute(
            select(LifePlan).where(LifePlan.plan_date == d))).scalars().first()
        if row is None:
            return ApiResponse.fail(ADMIN_ERR_LIFE_PLAN_NOT_FOUND)
        return ApiResponse.ok(data=_plan_to_dict(row))

    ds, de = _parse_date(start or ""), _parse_date(end or "")
    if ds is None or de is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
    rows = (await db.execute(
        select(LifePlan)
        .where(LifePlan.plan_date >= ds, LifePlan.plan_date <= de)
        .order_by(LifePlan.plan_date.desc())
        .offset((page - 1) * size).limit(size))).scalars().all()
    return ApiResponse.ok(data={"list": [_plan_to_dict(r) for r in rows], "page": page, "size": size})


@router.post("/life-plan/daily/{plan_date}/generate", dependencies=[require_role(*_ALLOWED_ROLES)])
async def generate_daily(
    plan_date: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """手动触发 LLM-02 生成日场景；outline 缺失返回错误。"""
    d = _parse_date(plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
    outline = (await db.execute(
        select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
    if outline is None:
        return ApiResponse.fail(ADMIN_ERR_LIFE_OUTLINE_MISSING)

    from backend.services.life_planner_service import life_planner_service
    try:
        result = await life_planner_service.generate_daily_scenes(d)
    except Exception as e:
        logger.error("[后台][生活计划] 手动生成日场景失败: %s", e, exc_info=True)
        return ApiResponse.fail(ADMIN_ERR_LIFE_GENERATE_FAILED)

    await log_operation(db, admin_user, "life_plan", "generate_daily",
                        f"手动生成日场景 {plan_date}",
                        after_value=json.dumps(result, ensure_ascii=False)[:500], request=request)
    await db.commit()
    return ApiResponse.ok(data=result)


@router.post("/life-plan/daily/{plan_date}/scenes", dependencies=[require_role(*_ALLOWED_ROLES)])
async def add_scene(
    plan_date: str,
    body: SceneBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """手动新增一条 scene（10.1#8）；追加至 ≥2 条且原为 failed 时自动升级 ready。"""
    d = _parse_date(plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)

    outline = (await db.execute(
        select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
    if outline is None:
        return ApiResponse.fail(ADMIN_ERR_LIFE_OUTLINE_MISSING)
    outline_cats = [c for c in (outline.categories or "").split("\n") if c]
    if body.category not in outline_cats:
        return ApiResponse.fail(ADMIN_ERR_LIFE_CATEGORY_INVALID)

    plan = (await db.execute(
        select(LifePlan).where(LifePlan.plan_date == d))).scalars().first()
    scenes = list(plan.scenes) if (plan and plan.scenes) else []
    new_scene = {
        "scene_id": _next_scene_id(d, scenes),
        "time_range": body.time_range,
        "city": body.city,
        "category": body.category,
        "venue_type": body.venue_type,
        "description": body.description,
    }
    scenes.append(new_scene)

    if plan is None:
        plan = LifePlan(plan_date=d, scenes=scenes,
                        gen_status="ready" if len(scenes) >= 2 else "failed")
        db.add(plan)
    else:
        if plan.gen_status == "failed" and len(scenes) >= 2:
            plan.gen_status = "ready"
        plan.scenes = scenes
    await db.flush()
    await log_operation(db, admin_user, "life_plan", "add_scene",
                        f"手动新增场景 {plan_date} {new_scene['scene_id']}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_plan_to_dict(plan))


@router.put("/life-plan/daily/{plan_date}/scenes/{scene_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_scene(
    plan_date: str,
    scene_id: str,
    body: SceneBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑单条 scene（category 须 ∈ 当日大纲；city 不强制；不主动降级 gen_status）。"""
    d = _parse_date(plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)

    # 确认点 7-B：编辑与新增一致，校验 category ∈ 当日大纲 categories
    outline = (await db.execute(
        select(LifePlanOutline).where(LifePlanOutline.plan_date == d))).scalars().first()
    if outline is None:
        return ApiResponse.fail(ADMIN_ERR_LIFE_OUTLINE_MISSING)
    outline_cats = [c for c in (outline.categories or "").split("\n") if c]
    if body.category not in outline_cats:
        return ApiResponse.fail(ADMIN_ERR_LIFE_CATEGORY_INVALID)

    plan = (await db.execute(
        select(LifePlan).where(LifePlan.plan_date == d))).scalars().first()
    if plan is None or not plan.scenes:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PLAN_NOT_FOUND)

    scenes = list(plan.scenes)
    idx = next((i for i, s in enumerate(scenes) if str(s.get("scene_id")) == scene_id), -1)
    if idx < 0:
        return ApiResponse.fail(ADMIN_ERR_LIFE_SCENE_NOT_FOUND)
    scenes[idx] = {
        "scene_id": scene_id,
        "time_range": body.time_range,
        "city": body.city,
        "category": body.category,
        "venue_type": body.venue_type,
        "description": body.description,
    }
    plan.scenes = scenes
    await db.flush()
    await log_operation(db, admin_user, "life_plan", "update_scene",
                        f"编辑场景 {plan_date} {scene_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_plan_to_dict(plan))


@router.delete("/life-plan/daily/{plan_date}/scenes/{scene_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_scene(
    plan_date: str,
    scene_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除单条 scene（不主动降级 gen_status）。"""
    d = _parse_date(plan_date)
    if d is None:
        return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
    plan = (await db.execute(
        select(LifePlan).where(LifePlan.plan_date == d))).scalars().first()
    if plan is None or not plan.scenes:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PLAN_NOT_FOUND)
    scenes = [s for s in plan.scenes if str(s.get("scene_id")) != scene_id]
    if len(scenes) == len(plan.scenes):
        return ApiResponse.fail(ADMIN_ERR_LIFE_SCENE_NOT_FOUND)
    plan.scenes = scenes
    await db.flush()
    await log_operation(db, admin_user, "life_plan", "delete_scene",
                        f"删除场景 {plan_date} {scene_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_plan_to_dict(plan))
