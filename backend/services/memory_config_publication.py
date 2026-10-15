"""Durable configuration publication, with actor-scoped exact receipts.

Readers never commit or consult the legacy active cache. ``publish`` owns its
transaction boundaries; callers must not stage unrelated writes in that session.
Only AdminConfig contains the private candidate. Receipts and audit contain no
payload, credentials, provider exceptions, or public credential fingerprints.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import inspect
import json
import secrets
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, literal, or_, select, union_all, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.config import get_admin_jwt_secret
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.memory_config import MemoryConfigHead, MemoryConfigPublish

CONFIG_KEYS = frozenset({"vector_retrieval_config", "prompt_token_config", "vector_db_config",
                         "third_party:embedding", "third_party:rerank"})
CONFIG_ALIASES = {"third_party:dashvector": "vector_db_config"}
ACCEPT_WINDOW_MS = 120_000
FUTURE_DRIFT_MS = 30_000
PUBLICATION_WINDOW_SECONDS = 120


class PublicationError(Exception):
    """Only fixed, non-sensitive reasons may cross the service boundary."""
    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_or_create_publish_id(value=None, *, now=None) -> str:
    if value is None:
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        milliseconds = int(instant.timestamp() * 1000)
        bits = ((milliseconds & ((1 << 48) - 1)) << 80) | (7 << 76)
        bits |= (secrets.randbits(12) << 64) | (2 << 62) | secrets.randbits(62)
        return str(UUID(int=bits))
    try:
        parsed = UUID(value)
        if type(value) is not str or str(parsed) != value or parsed.version != 7:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise PublicationError(20120, "invalid_publish_id") from None
    return value


def canonicalize(key):
    if not isinstance(key, str):
        raise PublicationError(20120, "invalid_config_key")
    key = CONFIG_ALIASES.get(key, key)
    if key not in CONFIG_KEYS:
        raise PublicationError(20120, "invalid_config_key")
    return key


def _legacy_keys(key):
    return [key, *(alias for alias, canonical in CONFIG_ALIASES.items() if canonical == key)]


def _actor(actor):
    if type(actor) is not int or actor <= 0:
        raise PublicationError(20120, "invalid_publication_actor")


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value):
    try:
        return hmac.new(get_admin_jwt_secret().encode(), _encode(value).encode(), hashlib.sha256).digest()
    except (ValueError, TypeError, OverflowError):
        raise PublicationError(20120, "invalid_publication_payload") from None


def _decode(value):
    try:
        raw = json.loads(value)
        if not isinstance(raw, dict):
            raise ValueError()
        _encode(raw)
        return raw
    except (TypeError, ValueError, OverflowError):
        raise PublicationError(20129, "config_record_unreadable") from None


def _project(row, *, now=None):
    now = now or _now()
    state, reason = row.commit_state, row.reason
    if state in {"accepted", "validating"}:
        if row.lease_until is None or row.lease_until <= now:
            state, reason = "unknown", "publication_owner_unavailable"
        else:
            state = "pending"
    elif state in {"committed", "rejected"} and row.receipt_until and row.receipt_until <= now:
        state, reason = "expired", "publication_receipt_expired"
    return {
        "publish_id": row.publish_id, "canonical_key": row.canonical_key,
        "source_entry": row.source_entry, "commit_state": state,
        "committed_version": row.committed_version if state == "committed" else None,
        "observed_at": row.observed_at.isoformat(timespec="microseconds") + "Z",
        "reason": reason,
    }


async def get_receipt(db, actor, publish_id):
    """Read only; caller enforces the original source entry's current RBAC."""
    _actor(actor)
    publish_id = get_or_create_publish_id(publish_id)
    try:
        row = await db.scalar(select(MemoryConfigPublish).where(
            MemoryConfigPublish.admin_id == actor, MemoryConfigPublish.publish_id == publish_id,
        ).execution_options(populate_existing=True))
        return _project(row) if row else None
    except PublicationError:
        raise
    except Exception:
        raise PublicationError(20129, "publication_receipt_unreadable") from None


async def read_many(db, keys):
    """One SELECT snapshot of heads and their exact config rows, without writes.

    The union provides a row even for never-published keys. Legacy active config
    is consumed only before a head has acquired its first pointer, never as an
    alternative when a published head is corrupt.
    """
    keys = list(dict.fromkeys(canonicalize(key) for key in keys))
    if not keys:
        return {}
    requested = union_all(*(select(literal(key).label("key")) for key in keys)).cte("requested_keys")
    head, config = MemoryConfigHead.__table__, AdminConfig.__table__
    matching_key = or_(config.c.config_key == requested.c.key,
        and_(requested.c.key == "vector_db_config", config.c.config_key == "third_party:dashvector"))
    join_condition = or_(
        and_(head.c.active_admin_config_id.is_not(None), config.c.id == head.c.active_admin_config_id),
        and_(matching_key, config.c.is_active.is_(True), config.c.is_draft.is_(False)),
    )
    statement = select(
        requested.c.key, head.c.active_admin_config_id, head.c.active_version,
        head.c.revision, config.c.id, config.c.config_key.label("row_key"),
        config.c.version, config.c.config_value, config.c.is_active, config.c.is_draft,
    ).select_from(requested.outerjoin(head, head.c.config_key == requested.c.key).outerjoin(config, join_condition))
    try:
        rows = (await db.execute(statement)).mappings().all()
        result = {}
        for row in rows:
            key = row["key"]
            if key in result:
                raise PublicationError(20129, "config_head_ambiguous")
            version, pointer = row["active_version"], row["active_admin_config_id"]
            if row["id"] is None:
                if pointer is not None or version not in (None, 0):
                    raise PublicationError(20129, "config_head_unreadable")
                result[key] = {"raw": None, "version": 0, "source": "never_published", "revision": row["revision"] or 0}
                continue
            if (row["row_key"] not in _legacy_keys(key) or not row["is_active"] or row["is_draft"]
                    or row["version"] is None or row["version"] < 1
                    or (pointer is None and version not in (None, 0))
                    or (pointer is not None and (version != row["version"] or pointer != row["id"]))):
                raise PublicationError(20129, "config_head_unreadable")
            result[key] = {"raw": _decode(row["config_value"]), "version": row["version"],
                           "source": "database", "revision": row["revision"] or 0}
        return result
    except PublicationError:
        raise
    except Exception:
        raise PublicationError(20129, "config_dependency_unreadable") from None


async def read(db, key):
    return (await read_many(db, [key]))[canonicalize(key)]


async def _insert_once(db, model, values, conflict_columns):
    dialect = db.get_bind().dialect.name
    if dialect == "mysql":
        statement = mysql_insert(model).values(**values)
        first = conflict_columns[0]
        statement = statement.on_duplicate_key_update(**{first: getattr(model, first)})
    elif dialect == "sqlite":
        statement = sqlite_insert(model).values(**values).on_conflict_do_nothing(index_elements=conflict_columns)
    else:
        raise PublicationError(20129, "publication_database_unsupported")
    await db.execute(statement)


async def _locked_head(db, key):
    # The INSERT also gives SQLite a database write reservation before any reads.
    # On MySQL the unique PK serializes the previously-missing head case.
    await _insert_once(db, MemoryConfigHead, {"config_key": key, "active_version": 0,
        "revision": 0, "updated_at": _now()}, ["config_key"])
    head = await db.scalar(select(MemoryConfigHead).where(MemoryConfigHead.config_key == key)
                          .with_for_update().execution_options(populate_existing=True))
    active = list((await db.scalars(select(AdminConfig).where(
        AdminConfig.config_key.in_(_legacy_keys(key)), AdminConfig.is_active.is_(True), AdminConfig.is_draft.is_(False),
    ).with_for_update().execution_options(populate_existing=True))).all())
    if len(active) > 1:
        raise PublicationError(20129, "config_head_ambiguous")
    if head.active_admin_config_id is not None:
        if (not active or active[0].id != head.active_admin_config_id
                or active[0].version != head.active_version):
            raise PublicationError(20129, "config_head_unreadable")
    elif head.active_version != 0:
        raise PublicationError(20129, "config_head_unreadable")
    elif active:
        head.active_admin_config_id, head.active_version = active[0].id, active[0].version
    return head, _decode(active[0].config_value) if active else None


def _merge(merge_validate, current, patch):
    try:
        candidate = merge_validate(current, patch)
        if not isinstance(candidate, dict) or inspect.isawaitable(candidate):
            raise ValueError()
        _encode(candidate)
        return candidate
    except Exception:
        raise PublicationError(20120, "config_validation_failed") from None


async def _locked_receipt(db, actor, identity):
    return await db.scalar(select(MemoryConfigPublish).where(
        MemoryConfigPublish.admin_id == actor, MemoryConfigPublish.publish_id == identity,
    ).with_for_update().execution_options(populate_existing=True))


def _owns(row, owner):
    return (row is not None and row.lease_owner == owner and row.lease_version == 1
            and row.commit_state in {"accepted", "validating"}
            and row.lease_until is not None and row.lease_until > _now())


def _terminal(row, state, reason=None):
    now = _now()
    row.commit_state, row.reason, row.observed_at = state, reason, now
    row.record_revision += 1
    row.lease_owner, row.lease_until = None, None
    if state in {"committed", "rejected"}:
        row.terminal_at, row.receipt_until = now, now + timedelta(days=7)
        row.tombstone_until = now + timedelta(days=30)
    if state == "committed":
        row.committed_at = now


async def _rollback(db):
    try:
        await db.rollback()
    except Exception:
        pass


def _unknown(identity, key, source_entry):
    return {"publish_id": identity, "canonical_key": key, "source_entry": source_entry,
            "commit_state": "unknown", "committed_version": None,
            "observed_at": _now().isoformat(timespec="microseconds") + "Z",
            "reason": "publication_commit_unconfirmed"}


async def _reconcile(db, factory, actor, identity, key, entry):
    # Exactly this identity on a fresh connection. No head/current-version query.
    await _rollback(db)
    factory = factory or async_sessionmaker(db.bind, expire_on_commit=False)
    try:
        async with factory() as fresh:
            receipt = await get_receipt(fresh, actor, identity)
            if receipt and receipt["commit_state"] in {"committed", "rejected", "expired"}:
                return receipt
    except Exception:
        pass
    return _unknown(identity, key, entry)


async def _finish(db, actor, identity, owner, state, reason):
    await _rollback(db)
    row = await _locked_receipt(db, actor, identity)
    if not _owns(row, owner):
        await _rollback(db)
        return _project(row) if row else None
    _terminal(row, state, reason)
    result = _project(row)
    await db.commit()
    return result


async def _prune_history(db, key):
    newest = list((await db.scalars(select(AdminConfig.id).where(
        AdminConfig.config_key == key, AdminConfig.is_draft.is_(False),
    ).order_by(AdminConfig.version.desc(), AdminConfig.id.desc()).limit(20))).all())
    protected_heads = select(MemoryConfigHead.active_admin_config_id).where(MemoryConfigHead.active_admin_config_id.is_not(None))
    protected_receipts = select(MemoryConfigPublish.committed_admin_config_id).where(
        MemoryConfigPublish.committed_admin_config_id.is_not(None),
        or_(MemoryConfigPublish.tombstone_until.is_(None), MemoryConfigPublish.tombstone_until > _now()),
    )
    await db.execute(delete(AdminConfig).where(
        AdminConfig.config_key == key, AdminConfig.is_draft.is_(False), AdminConfig.is_active.is_(False),
        AdminConfig.id.not_in(newest), AdminConfig.id.not_in(protected_heads), AdminConfig.id.not_in(protected_receipts),
    ).execution_options(synchronize_session=False))


async def _cache_committed(cache, key, version, candidate):
    try:
        if cache is None:
            from backend.redis_client import get_redis
            cache = await get_redis()
        await asyncio.wait_for(cache.setex(f"memory_config:{key}:{version}", 3600, _encode(candidate)), timeout=2)
        await asyncio.wait_for(cache.delete(f"active_config:{key}"), timeout=2)
    except Exception:
        # Head is authoritative; a cache failure cannot reverse a DB receipt.
        pass


async def publish(db, key, patch, admin_id, publish_id, merge_validate, *, source_entry=None,
                  cache=None, verify=None, session_factory=None):
    """Accept once, optionally verify outside locks, then atomically publish.

    ``merge_validate(current_raw, patch)`` must be pure and return the entire
    candidate. ``verify(candidate)`` may await a provider; False or a controlled
    exception rejects the candidate. A timed-out call is unknown, never replayed.
    """
    original_key = key
    key = canonicalize(key)
    _actor(admin_id)
    identity = get_or_create_publish_id(publish_id)
    entry = source_entry or original_key
    if not isinstance(entry, str) or not entry or len(entry) > 64 or not isinstance(patch, dict):
        raise PublicationError(20120, "invalid_publication_payload")
    digest = _fingerprint({"actor": admin_id, "key": key, "entry": entry, "patch": patch})
    owner = str(uuid4())
    accepted = False
    try:
        existing = await db.scalar(select(MemoryConfigPublish).where(
            MemoryConfigPublish.admin_id == admin_id, MemoryConfigPublish.publish_id == identity,
        ).execution_options(populate_existing=True))
        if existing:
            if not hmac.compare_digest(existing.request_digest, digest):
                raise PublicationError(20121, "publication_identity_conflict")
            return _project(existing)
        now = _now()
        age = int(now.replace(tzinfo=timezone.utc).timestamp() * 1000) - (UUID(identity).int >> 80)
        if age > ACCEPT_WINDOW_MS or age < -FUTURE_DRIFT_MS:
            raise PublicationError(20123, "publication_id_outside_window")
        await _insert_once(db, MemoryConfigPublish, {
            "publish_id": identity, "admin_id": admin_id, "source_entry": entry, "canonical_key": key,
            "request_digest": digest, "commit_state": "validating" if verify else "accepted",
            "created_at": now, "observed_at": now, "record_revision": 1,
            "lease_owner": owner, "lease_version": 1,
            "lease_until": now + timedelta(seconds=PUBLICATION_WINDOW_SECONDS),
        }, ["admin_id", "publish_id"])
        row = await _locked_receipt(db, admin_id, identity)
        if not hmac.compare_digest(row.request_digest, digest):
            raise PublicationError(20121, "publication_identity_conflict")
        if row.lease_owner != owner:
            result = _project(row)
            await _rollback(db)
            return result
        accepted = True
        # No provider call is possible before this durable acceptance.
        await db.commit()
        deadline = now + timedelta(seconds=PUBLICATION_WINDOW_SECONDS)
        verified_digest, verification_count = None, 0
        while True:
            if verify and verified_digest is None:
                snapshot = await read(db, key)
                candidate = _merge(merge_validate, snapshot["raw"], patch)
                await _rollback(db)  # Do not retain a transaction across network I/O.
                remaining = (deadline - _now()).total_seconds()
                if remaining <= 0:
                    return await _finish(db, admin_id, identity, owner, "unknown", "publication_owner_unavailable")
                verification_count += 1
                try:
                    async with asyncio.timeout(remaining):
                        outcome = verify(candidate)
                        if inspect.isawaitable(outcome):
                            outcome = await outcome
                    if outcome is False:
                        return await _finish(db, admin_id, identity, owner, "rejected", "provider_test_failed")
                except TimeoutError:
                    return await _finish(db, admin_id, identity, owner, "unknown", "provider_outcome_unknown")
                except Exception:
                    return await _finish(db, admin_id, identity, owner, "rejected", "provider_test_failed")
                verified_digest = _fingerprint(candidate)
            head, current = await _locked_head(db, key)
            row = await _locked_receipt(db, admin_id, identity)
            if not _owns(row, owner):
                result = _project(row) if row else _unknown(identity, key, entry)
                await _rollback(db)
                return result
            candidate = _merge(merge_validate, current, patch)
            final_digest = _fingerprint(candidate)
            if verify and not hmac.compare_digest(verified_digest, final_digest):
                await _rollback(db)
                if verification_count >= 2:
                    return await _finish(db, admin_id, identity, owner, "rejected", "publication_revision_conflict")
                verified_digest = None
                continue
            row.validated_digest, row.expected_head_revision = final_digest, head.revision
            version = head.active_version + 1
            await db.execute(update(AdminConfig).where(AdminConfig.config_key.in_(_legacy_keys(key)),
                AdminConfig.is_active.is_(True), AdminConfig.is_draft.is_(False)).values(is_active=False))
            config = AdminConfig(config_key=key, config_value=_encode(candidate), version=version,
                                 is_active=True, is_draft=False, updated_by=str(admin_id))
            db.add(config)
            await db.flush()
            head.active_admin_config_id, head.active_version = config.id, version
            head.revision, head.updated_at = head.revision + 1, _now()
            row.committed_admin_config_id, row.committed_version = config.id, version
            _terminal(row, "committed")
            db.add(AdminOperationLog(admin_user_id=admin_id, admin_username=str(admin_id),
                module="ai_config", action="publish", target_description=key,
                before_value=None, after_value=_encode({"publish_id": identity, "version": version, "source_entry": entry})))
            await db.flush()
            await _prune_history(db, key)
            result = _project(row)
            await db.commit()
            await _cache_committed(cache, key, version, candidate)
            return result
    except PublicationError as error:
        await _rollback(db)
        if accepted and error.code == 20120:
            try:
                return await _finish(db, admin_id, identity, owner, "rejected", "config_validation_failed")
            except Exception:
                return await _reconcile(db, session_factory, admin_id, identity, key, entry)
        if accepted:
            return await _reconcile(db, session_factory, admin_id, identity, key, entry)
        raise
    except asyncio.CancelledError:
        # No resumption/retry of a provider call after cancellation.
        await _rollback(db)
        raise
    except Exception:
        if accepted:
            return await _reconcile(db, session_factory, admin_id, identity, key, entry)
        await _rollback(db)
        raise PublicationError(20129, "publication_acceptance_unavailable") from None
