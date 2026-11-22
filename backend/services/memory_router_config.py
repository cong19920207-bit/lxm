"""Router configuration uses the existing publication head and durable receipts."""
import hashlib
import json

from sqlalchemy import select

from backend import config as environment
from backend import constants as codes
from backend.models.admin_config import AdminConfig
from backend.services import memory_config_publication as publications
from backend.services.memory_config_schema import DEFAULT_ROUTER, ROUTER_KEY, MemoryQueryRouterConfig
from backend.services.memory_query_router import RouterProvider
from backend.utils.admin_auth import log_operation


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def validated(value):
    # Preserve the exact stored fields used for legacy digests and size checks.
    return MemoryQueryRouterConfig.model_validate(value).model_dump(exclude_unset=True)


def stored_config(value):
    try:
        return validated(json.loads(value) if isinstance(value, str) else value)
    except (TypeError, ValueError, RecursionError):
        raise publications.PublicationError(codes.ADMIN_ERR_MEMORY_UNAVAILABLE, "config_record_unreadable") from None


async def draft_row(db, *, lock=False):
    statement = select(AdminConfig).where(AdminConfig.config_key == ROUTER_KEY, AdminConfig.is_draft.is_(True))
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return (await db.scalars(statement)).one_or_none()


def project_draft(row):
    if row is None:
        return {"config": None, "draft_digest": None, "updated_at": None}
    config = stored_config(row.config_value)
    return {"config": config, "draft_digest": digest(config),
            "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None}


async def active(db):
    record = await publications.read(db, ROUTER_KEY)
    config = stored_config(record["raw"]) if record["raw"] is not None else DEFAULT_ROUTER.model_dump()
    return {"config": config, "version": str(record["version"]), "revision": str(record["revision"]),
            "source": "default" if record["raw"] is None else record["source"], "config_digest": digest(config),
            "prompt_digest": hashlib.sha256(config["prompt"].encode()).hexdigest()}


def conflict():
    return publications.PublicationError(codes.ADMIN_ERR_MEMORY_REVISION_CONFLICT, "publication_revision_conflict")


async def edit_draft(db, actor, request, config=None):
    try:
        result = await _change_draft(db, actor, request, config)
        await db.commit()
        return result
    except BaseException:
        await db.rollback()
        raise


async def _change_draft(db, actor, request, config):
    head, _ = await publications._locked_head(db, ROUTER_KEY)
    row = await draft_row(db, lock=True)
    before = project_draft(row)
    if str(head.revision) != request.expected_revision or before["draft_digest"] != request.draft_digest:
        raise conflict()
    if config is None:
        if row is not None:
            await db.delete(row)
        row = None
    else:
        if row is None:
            row = AdminConfig(config_key=ROUTER_KEY, is_active=False, is_draft=True, version=head.active_version)
            db.add(row)
        row.config_value = encode(validated(config))
        row.updated_by = str(actor.id)
    await db.flush()
    if row is not None:
        await db.refresh(row)
    result = project_draft(row)
    await log_operation(db, actor, "ai_config", "discard_draft" if config is None else "save_draft",
                        ROUTER_KEY, before["draft_digest"], result["draft_digest"])
    return result


def history_query():
    return select(AdminConfig).where(AdminConfig.config_key == ROUTER_KEY, AdminConfig.is_draft.is_(False))


def version_view(row):
    config = stored_config(row.config_value)
    return {"id": str(row.id), "version": str(row.version), "config": config, "config_digest": digest(config),
            "prompt_digest": hashlib.sha256(config["prompt"].encode()).hexdigest(),
            "is_active": row.is_active, "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None}


async def locked_candidate(db, head, current, command):
    if command["expected_revision"] != str(head.revision):
        raise conflict()
    if command["operation"] == "disable":
        return {**(current if current is not None else DEFAULT_ROUTER.model_dump()), "enabled": False}
    if command["operation"] == "publish":
        draft = await draft_row(db, lock=True)
        view = project_draft(draft)
        if draft is None or view["draft_digest"] != command["draft_digest"]:
            raise conflict()
        router = MemoryQueryRouterConfig.model_validate(view["config"])
        if router.enabled:
            provider = RouterProvider.from_config(router, environment.get_volc_model())
            if not provider.credential.reveal().strip():
                raise publications.PublicationError(codes.ADMIN_ERR_MEMORY_INVALID, "router_credential_missing")
        await db.delete(draft)
        return view["config"]
    row = await db.scalar(history_query().where(AdminConfig.version == int(command["version"])).with_for_update())
    if row is None:
        raise publications.PublicationError(codes.ADMIN_ERR_MEMORY_NOT_FOUND, "router_version_unavailable")
    view = version_view(row)
    if command.get("version_digest") is not None and view["config_digest"] != command["version_digest"]:
        raise conflict()
    return view["config"]
