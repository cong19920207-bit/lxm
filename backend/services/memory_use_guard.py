"""Persistent final-use protection. Business Prompt/model adapters wire this in STEP-013.

Only an adapter that observed the whole input-body handoff may confirm_handoff;
confirm_stopped requires proof that its owner stopped and its input socket closed.
A lease/deadline, missing response, or missing remote record is never such proof.
"""
import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.models.memory_control import MemoryIdentity, MemoryOperation, MemoryUseClaim, MemoryUseItem
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence


class UseGuardError(MemoryControlError):
    pass


@dataclass(frozen=True)
class UseCandidate:
    identity_id: int
    generation: int
    body_hash: bytes
    route: str
    ordinal: int


@dataclass(frozen=True)
class UseReservation:
    claim_id: str
    state: str
    selected: tuple[UseCandidate, ...]
    invalidated: tuple[UseCandidate, ...]


_ROUTE_TYPES = {'cg': 'character_global', 'cp': 'character_private', 'ck': 'character_knowledge', 'user': 'user'}
_OPEN = {'reserved', 'dispatching', 'unknown'}


def _utc(value):
    if not isinstance(value, datetime):
        raise UseGuardError(20120, 'use_deadline_invalid')
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _uuid(value):
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise UseGuardError(20120, 'use_identity_invalid') from None
    return value


def _candidate(item):
    return UseCandidate(item.identity_id, item.generation, item.body_hash, item.route, item.ordinal)


class MemoryUseGuard:
    def __init__(self, session_factory, environment_id, *, allow_isolated=False, clock=None):
        self.sessions = session_factory
        self.environment_id = environment_id
        self.allow_isolated = allow_isolated
        self.clock = clock or datetime.utcnow

    async def _fence(self, db, epoch, fingerprint):
        return await require_active_fence(db, self.environment_id, epoch, fingerprint,
                                          allow_isolated=self.allow_isolated)

    async def _source_available(self, db, records):
        """Index-only work preserves current source truth; source intents do not."""
        operation_ids = {row.inflight_operation_id for row in records.values() if row.inflight_operation_id}
        operations = {op.operation_id: op for op in (await db.scalars(select(MemoryOperation).where(
            MemoryOperation.operation_id.in_(operation_ids)).with_for_update()
            .execution_options(populate_existing=True))).all()} if operation_ids else {}
        available = set()
        for row in records.values():
            if row.inflight_operation_id is None:
                available.add(row.id)
                continue
            op = operations.get(row.inflight_operation_id)
            if (op is not None and op.operation_kind == 'index' and op.identity_id == row.id
                    and op.generation == row.generation and op.target_epoch == row.target_epoch
                    and op.source_result == 'confirmed' and op.task_id is not None
                    and op.dispatch_state in {'prepared', 'claimed', 'dispatching', 'unknown'}):
                available.add(row.id)
        return available

    async def reserve(self, *, consumer_kind, execution_id, owner_id, user_id,
                      target_epoch, target_fingerprint, deadline_at, candidates):
        execution_id, owner_id = _uuid(execution_id), _uuid(owner_id)
        deadline_at = _utc(deadline_at)
        if (type(user_id) is not int or user_id <= 0 or not isinstance(consumer_kind, str)
                or not consumer_kind or len(consumer_kind) > 24
                or type(target_epoch) is not int or target_epoch < 1
                or not isinstance(target_fingerprint, bytes) or len(target_fingerprint) != 32):
            raise UseGuardError(20120, 'use_context_invalid')
        items = tuple(candidates)
        if any(not isinstance(item, UseCandidate) for item in items):
            raise UseGuardError(20120, 'use_candidate_invalid')
        if len({item.identity_id for item in items}) != len(items):
            raise UseGuardError(20120, 'duplicate_use_identity')
        if len({(item.route, item.ordinal) for item in items}) != len(items):
            raise UseGuardError(20120, 'duplicate_use_ordinal')
        for item in items:
            if (not isinstance(item, UseCandidate) or type(item.identity_id) is not int or item.identity_id <= 0
                    or type(item.generation) is not int or item.generation < 1 or item.route not in _ROUTE_TYPES
                    or type(item.ordinal) is not int or item.ordinal < 0 or not isinstance(item.body_hash, bytes) or len(item.body_hash) != 32):
                raise UseGuardError(20120, 'use_candidate_invalid')
        request_hash = hashlib.sha256(json.dumps({
            'owner': owner_id, 'user': user_id, 'epoch': target_epoch,
            'fingerprint': target_fingerprint.hex(), 'deadline': deadline_at.isoformat(timespec='microseconds'),
            'candidates': [(item.identity_id, item.generation, item.body_hash.hex(), item.route, item.ordinal)
                           for item in items],
        }, sort_keys=True, separators=(',', ':')).encode()).digest()
        try:
            async with asyncio.timeout(2):
                async with self.sessions() as db:
                    async with db.begin():
                        await self._fence(db, target_epoch, target_fingerprint)
                        existing = await db.scalar(select(MemoryUseClaim).where(
                            MemoryUseClaim.consumer_kind == consumer_kind, MemoryUseClaim.execution_id == execution_id))
                        if existing:
                            stored = tuple(_candidate(item) for item in (await db.scalars(select(MemoryUseItem).where(
                                MemoryUseItem.claim_id == existing.claim_id).order_by(MemoryUseItem.route, MemoryUseItem.ordinal))).all())
                            if (existing.owner_id != owner_id or existing.target_epoch != target_epoch
                                    or existing.request_hash != request_hash):
                                raise UseGuardError(20121, 'use_execution_conflict')
                            # Original candidates may include an invalidated suffix. Only selected
                            # items acquire locks; the digest preserves exact replay without bodies.
                            selected = tuple(item for item in items if item in stored)
                            return UseReservation(existing.claim_id, existing.state, selected,
                                                  tuple(item for item in items if item not in stored))
                        now = _utc(self.clock())
                        if now >= deadline_at:
                            raise UseGuardError(20126, 'use_deadline_exceeded')
                        ids = sorted(item.identity_id for item in items)
                        records = {row.id: row for row in (await db.scalars(select(MemoryIdentity).where(
                            MemoryIdentity.id.in_(ids)).order_by(MemoryIdentity.id).with_for_update())).all()}
                        source_available = await self._source_available(db, records)
                        invalid_at = {}
                        for item in sorted(items, key=lambda value: (value.route, value.ordinal)):
                            row = records.get(item.identity_id)
                            owner = 0 if item.route in {'cg', 'ck'} else user_id
                            valid = row is not None and row.id in source_available and (row.target_epoch, row.target_fingerprint, row.generation, row.body_hash,
                                                          row.source_state, row.memory_type, row.owner_user_id) == (
                                target_epoch, target_fingerprint, item.generation, item.body_hash, 'live', _ROUTE_TYPES[item.route], owner)
                            if not valid:
                                invalid_at.setdefault(item.route, item.ordinal)
                        selected = tuple(item for item in items if item.ordinal < invalid_at.get(item.route, float('inf')))
                        invalidated = tuple(item for item in items if item not in selected)
                        if _utc(self.clock()) >= deadline_at:
                            raise UseGuardError(20126, 'use_deadline_exceeded')
                        claim_id = str(uuid4())
                        db.add(MemoryUseClaim(claim_id=claim_id, consumer_kind=consumer_kind, execution_id=execution_id,
                                               target_epoch=target_epoch, owner_id=owner_id, request_hash=request_hash,
                                               state='reserved', created_deadline_at=deadline_at))
                        await db.flush()
                        db.add_all([MemoryUseItem(claim_id=claim_id, identity_id=item.identity_id, generation=item.generation,
                                                  body_hash=item.body_hash, route=item.route, ordinal=item.ordinal) for item in selected])
                    return UseReservation(claim_id, 'reserved', selected, invalidated)
        except MemoryControlError:
            raise
        except TimeoutError:
            raise UseGuardError(20124, 'use_lock_timeout') from None
        except Exception:
            raise UseGuardError(20129, 'use_reservation_unverified') from None

    async def begin_handoff(self, claim_id, owner_id):
        """Commit the one-way dispatch fence before the adapter can send input."""
        _uuid(claim_id); _uuid(owner_id)
        try:
            async with asyncio.timeout(2):
                async with self.sessions() as db:
                    async with db.begin():
                        observed = await db.get(MemoryUseClaim, claim_id)
                        if observed is None:
                            raise UseGuardError(20125, 'use_claim_missing')
                        items = list((await db.scalars(select(MemoryUseItem).where(MemoryUseItem.claim_id == claim_id))).all())
                        # All mutation/reservation paths use fence -> identities -> claim order.
                        identities = list((await db.scalars(select(MemoryIdentity).where(MemoryIdentity.id.in_(
                            sorted(item.identity_id for item in items))).order_by(MemoryIdentity.id))).all())
                        if items and len(identities) != len(items):
                            raise UseGuardError(20128, 'use_identity_missing')
                        # Empty prompts still bind to this environment's exact epoch/fingerprint.
                        from backend.models.memory_control import MemoryRuntimeFence
                        fence = await db.get(MemoryRuntimeFence, self.environment_id)
                        if fence is None:
                            raise UseGuardError(20128, 'use_fence_missing')
                        await self._fence(db, observed.target_epoch, fence.target_fingerprint)
                        current = {row.id: row for row in (await db.scalars(select(MemoryIdentity).where(
                            MemoryIdentity.id.in_(sorted(item.identity_id for item in items))).order_by(MemoryIdentity.id)
                            .with_for_update().execution_options(populate_existing=True))).all()}
                        source_available = await self._source_available(db, current)
                        claim = await db.scalar(select(MemoryUseClaim).where(MemoryUseClaim.claim_id == claim_id)
                                                .with_for_update().execution_options(populate_existing=True))
                        if claim.owner_id != owner_id:
                            raise UseGuardError(20121, 'use_owner_conflict')
                        if claim.state == 'handed_off':
                            return 'handed_off'
                        if claim.state != 'reserved':
                            raise UseGuardError(20126, 'use_dispatch_not_allowed')
                        if _utc(self.clock()) >= claim.created_deadline_at:
                            raise UseGuardError(20126, 'use_deadline_exceeded')
                        for item in items:
                            row = current.get(item.identity_id)
                            if row is None or row.id not in source_available or (row.generation, row.body_hash, row.source_state, row.target_epoch, row.target_fingerprint) != (
                                    item.generation, item.body_hash, 'live', claim.target_epoch, fence.target_fingerprint):
                                raise UseGuardError(20128, 'use_candidate_invalidated')
                        claim.state = 'dispatching'
                        claim.revision += 1
                    return 'dispatching'
        except MemoryControlError:
            raise
        except Exception:
            raise UseGuardError(20129, 'use_dispatch_unverified') from None

    async def _finish(self, claim_id, owner_id, state):
        """No deadline-based unlock after dispatch. Only explicit adapter evidence."""
        _uuid(claim_id); _uuid(owner_id)
        try:
            async with self.sessions() as db:
                async with db.begin():
                    # Only original transport completion methods may settle a
                    # pre-T0 claim while business dispatch remains sealed.
                    from backend.models.memory_control import MemoryRuntimeFence
                    from backend.models.memory_backfill import MemoryResetRun
                    fence=await db.scalar(select(MemoryRuntimeFence).where(MemoryRuntimeFence.environment_id==self.environment_id).with_for_update())
                    claim = await db.scalar(select(MemoryUseClaim).where(MemoryUseClaim.claim_id == claim_id).with_for_update())
                    if fence and fence.mode=='maintenance':
                        run=await db.get(MemoryResetRun,fence.reset_run_id) if fence.reset_run_id else None
                        if (not run or run.t0 is not None or not claim or claim.target_epoch!=fence.target_epoch
                                or run.environment_id!=self.environment_id or run.target_fingerprint!=fence.target_fingerprint):
                            raise UseGuardError(20126,'use_drain_closed')
                        db.info['s15_maintenance']=run.run_id
                    if claim is None:
                        raise UseGuardError(20125, 'use_claim_missing')
                    if claim.owner_id != owner_id:
                        raise UseGuardError(20121, 'use_owner_conflict')
                    if claim.state == state:
                        return state
                    if state == 'unknown' and claim.state in {'handed_off', 'aborted'}:
                        # A lost local commit acknowledgment must not regress a confirmed closure.
                        return claim.state
                    if claim.state not in {'dispatching', 'unknown'}:
                        raise UseGuardError(20126, 'use_resolution_not_allowed')
                    claim.state = state
                    claim.revision += 1
                    if state == 'unknown':
                        claim.error_code = 'handoff_unverified'
                    else:
                        claim.closed_at = _utc(self.clock())
                        claim.error_code = None
                        if state == 'handed_off':
                            claim.handoff_at = claim.closed_at
                return state
        except MemoryControlError:
            raise
        except Exception:
            raise UseGuardError(20129, 'use_result_unverified') from None

    async def confirm_handoff(self, claim_id, owner_id):
        return await self._finish(claim_id, owner_id, 'handed_off')

    async def confirm_stopped(self, claim_id, owner_id):
        """Trusted adapter only: owner stopped AND input socket closed, no pending handoff."""
        return await self._finish(claim_id, owner_id, 'aborted')

    async def mark_unknown(self, claim_id, owner_id):
        return await self._finish(claim_id, owner_id, 'unknown')

    async def expire_reserved(self, claim_id):
        async with self.sessions() as db:
            async with db.begin():
                claim = await db.scalar(select(MemoryUseClaim).where(MemoryUseClaim.claim_id == claim_id).with_for_update())
                if claim is None or claim.state != 'reserved' or claim.created_deadline_at > _utc(self.clock()):
                    return False
                claim.state = 'aborted'
                claim.closed_at = _utc(self.clock())
                claim.error_code = 'reserved_expired_before_dispatch'
                claim.revision += 1
            return True

    async def abort_reserved(self, claim_id, owner_id):
        """The original owner may abandon an input that never began dispatch."""
        _uuid(claim_id); _uuid(owner_id)
        async with self.sessions() as db:
            async with db.begin():
                claim = await db.scalar(select(MemoryUseClaim).where(
                    MemoryUseClaim.claim_id == claim_id).with_for_update())
                if claim is None or claim.owner_id != owner_id:
                    raise UseGuardError(20121, 'use_owner_conflict')
                if claim.state != 'reserved':
                    return False
                claim.state = 'aborted'
                claim.closed_at = _utc(self.clock())
                claim.error_code = 'aborted_before_dispatch'
                claim.revision += 1
            return True

    async def handoff(self, claim_id, owner_id, sender):
        """sender must close/finish cancellation before returning; HTTP adapter supplied in 013.

        Returns handed_off or unknown. Unknown retains protection even if a remote
        request later completes; only its original owner can reconcile evidence.
        """
        state = await self.begin_handoff(claim_id, owner_id)
        if state == 'handed_off':
            return state
        async with self.sessions() as db:
            claim = await db.get(MemoryUseClaim, claim_id)
            remaining = min(5.0, (claim.created_deadline_at - _utc(self.clock())).total_seconds())
        try:
            if remaining <= 0:
                raise TimeoutError()
            outcome = await asyncio.wait_for(sender(), timeout=remaining)
            if outcome == 'handed_off':
                return await self.confirm_handoff(claim_id, owner_id)
            if outcome == 'stopped_without_handoff':
                return await self.confirm_stopped(claim_id, owner_id)
        except asyncio.CancelledError:
            # Cancellation receipt persistence is shielded; failure still leaves dispatching protection.
            await asyncio.shield(self.mark_unknown(claim_id, owner_id))
            raise
        except Exception:
            pass
        return await self.mark_unknown(claim_id, owner_id)
