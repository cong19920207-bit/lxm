"""Read-only previews and revision-checked administration of the query router."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend import config as environment
from backend import constants as codes
from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.schemas.common import ApiResponse
from backend.services import memory_config_publication as publication
from backend.services import memory_router_config as configs
from backend.services.memory_admin_common import page_data
from backend.services.memory_config_schema import MemoryQueryRouterConfig, ROUTER_KEY, ROUTER_PROMPT_MAX_CHARS, ROUTER_CONFIG_MAX_BYTES
from backend.services.memory_query_router import FIXED_RULES, RouterProvider
from backend.utils.admin_auth import require_role
from .vector_config import _server_time

router = APIRouter(prefix="/prompt/memory-router")
read = require_role("super_admin", "ai_trainer", "observer")
write = require_role("super_admin", "ai_trainer")
Revision = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,18})$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: Revision


class DraftCommand(Command):
    draft_digest: Digest | None


class SaveDraft(DraftCommand):
    config: MemoryQueryRouterConfig


class PublishCommand(Command):
    publish_id: str


class PublishDraft(PublishCommand):
    draft_digest: Digest


class Rollback(PublishCommand):
    version: Revision
    version_digest: Digest | None = None


async def response(operation):
    try:
        return ApiResponse.ok(data={**await operation, "server_time": _server_time()})
    except publication.PublicationError as exc:
        return ApiResponse.fail(exc.code, message=exc.reason)
    except (SQLAlchemyError, TimeoutError):
        return ApiResponse.fail(codes.ADMIN_ERR_MEMORY_UNAVAILABLE, message="config_dependency_unreadable")
    except ValueError:
        return ApiResponse.fail(codes.ADMIN_ERR_MEMORY_INVALID, message="router_config_invalid")


@router.get("")
async def get_active(db=Depends(get_db), actor=read):
    async def preview():
        result = await configs.active(db)
        config = MemoryQueryRouterConfig.model_validate(result["config"])
        provider = RouterProvider.from_config(config, environment.get_volc_model())
        result.update(effective_model=provider.model, effective_provider=config.provider_name,
                      thinking_enabled=config.thinking_enabled, credential_configured=bool(provider.credential.reveal().strip()),
                      fixed_rules=FIXED_RULES, output_schema={"need_memory_query": "boolean"},
                      history_round_limit=30, history_timezone="Asia/Shanghai", prompt_max_chars=ROUTER_PROMPT_MAX_CHARS,
                      config_max_bytes=ROUTER_CONFIG_MAX_BYTES)
        return result
    return await response(preview())


@router.get("/draft")
async def get_draft(db=Depends(get_db), actor=read):
    async def view():
        current = await configs.active(db)
        return {**configs.project_draft(await configs.draft_row(db)), "revision": current["revision"]}
    return await response(view())


@router.put("/draft")
async def save_draft(body: SaveDraft, db=Depends(get_db), actor=write):
    return await response(configs.edit_draft(db, actor, body, body.config.model_dump(exclude_unset=True)))


@router.delete("/draft")
async def discard_draft(body: DraftCommand, db=Depends(get_db), actor=write):
    return await response(configs.edit_draft(db, actor, body))


@router.get("/history")
async def history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db=Depends(get_db), actor=read):
    async def listing():
        query = configs.history_query()
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await db.scalars(query.order_by(AdminConfig.version.desc()).offset((page-1)*page_size).limit(page_size))
        items = [{k: v for k, v in configs.version_view(row).items() if k != "config"} for row in rows]
        return {**page_data(items, total, page, page_size), "items": items}
    return await response(listing())


@router.get("/history/{version}")
async def version_detail(version: int, db=Depends(get_db), actor=read):
    async def view():
        row = await db.scalar(configs.history_query().where(AdminConfig.version == version))
        if row is None:
            raise publication.PublicationError(codes.ADMIN_ERR_MEMORY_NOT_FOUND, "router_version_unavailable")
        return configs.version_view(row)
    return await response(view())


async def publish(db, actor, operation, body):
    try:
        command = body.model_dump(exclude={"publish_id"})
        command["operation"] = operation
        identity = publication.get_or_create_publish_id(body.publish_id)
        result = await publication.publish(db, ROUTER_KEY, command, actor.id, identity,
            lambda _, candidate: configs.validated(candidate), locked_candidate=configs.locked_candidate,
            source_entry=f"/api/admin/prompt/memory-router/{operation}")
        result["server_time"] = _server_time()
        if result["commit_state"] == "committed":
            return ApiResponse.ok(data=result)
        code = {"publication_revision_conflict": codes.ADMIN_ERR_MEMORY_REVISION_CONFLICT,
                "router_version_unavailable": codes.ADMIN_ERR_MEMORY_NOT_FOUND,
                "config_record_unreadable": codes.ADMIN_ERR_MEMORY_UNAVAILABLE}.get(result.get("reason"))
        code = code or {"expired": codes.ADMIN_ERR_MEMORY_EXPIRED,
                        "rejected": codes.ADMIN_ERR_MEMORY_INVALID}.get(result["commit_state"], codes.ADMIN_ERR_MEMORY_COMMIT_UNKNOWN)
        return ApiResponse.fail(code, message=result.get("reason") or "publication_unconfirmed", data=result)
    except publication.PublicationError as exc:
        if exc.reason == "publication_id_outside_window":
            return ApiResponse.fail(exc.code, message=exc.reason, data={
                "publish_id": body.publish_id, "admission_state": "not_admitted", "server_time": _server_time()})
        return ApiResponse.fail(exc.code, message=exc.reason)


@router.post("/publish")
async def publish_draft(body: PublishDraft, db=Depends(get_db), actor=write):
    return await publish(db, actor, "publish", body)


@router.post("/disable")
async def disable(body: PublishCommand, db=Depends(get_db), actor=write):
    return await publish(db, actor, "disable", body)


@router.post("/rollback")
async def rollback(body: Rollback, db=Depends(get_db), actor=write):
    return await publish(db, actor, "rollback", body)
