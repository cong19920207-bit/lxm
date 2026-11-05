"""Transactional pet fact storage; callers supply already validated business outcomes.

No gameplay calculation, network I/O, scheduler, cleanup policy or session commit.
The caller owns the outer transaction. The savepoint prevents a caught write failure
from committing a partial projection/fact/reward/outbox result.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.pet import (
    PetDiagnosticPayload, PetDisplayEntry, PetFactEvent, PetFactRequest, PetProfile, PetState,
    PetTaskCandidate,
)


class PetFactConflict(ValueError):
    """A stable key already identifies different content."""


class PetStateConflict(ValueError):
    """The caller's state version is no longer current; recompute the outcome."""


@dataclass(frozen=True)
class Candidate:
    kind: str
    business_key: str
    payload: dict


@dataclass(frozen=True)
class FactCommand:
    pet_id: str
    user_id: int
    request_key: str
    business_key: str
    expected_version: int
    event_type: str
    source: str
    participants: tuple[str, ...]
    occurred_at: datetime
    result: dict
    state_after: dict
    closeness_delta: int
    rule_snapshot_id: str
    reaction: dict | None = None
    display_surfaces: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    stage_after: str | None = None
    settled_until: datetime | None = None
    unlocked_after: tuple[str, ...] | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp requires an explicit timezone")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def append_fact(db: AsyncSession, command: FactCommand) -> PetFactEvent:
    """Apply one fact and its projection/reward/references/outbox atomically.

The pet row is the serialization point for all writers. SQL uniqueness is the final
barrier for request/business keys; current locking reads also work under MySQL RR.
Replay returns the original fact, including its original request and occurrence time.
"""
    occurred_at = _utc(command.occurred_at)
    for key in (command.request_key, command.business_key):
        if not key or len(key) > 128:
            raise ValueError("stable keys require 1..128 characters")
    payload = asdict(command)
    payload.pop("request_key")  # Repeated scanners can use another transport request ID.
    for key in ('stage_after','settled_until','unlocked_after'):
        if payload[key] is None:payload.pop(key)
    if command.settled_until is not None:
        payload['settled_until']=_utc(command.settled_until).isoformat(timespec='microseconds')
    payload["occurred_at"] = occurred_at.isoformat(timespec="microseconds")
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    digest = sha256(encoded.encode()).hexdigest()
    # Freeze mutable caller dictionaries before the first await.
    frozen = json.loads(encoded)

    async with db.begin_nested():
        pet = await db.scalar(select(PetProfile.id).where(
            PetProfile.id == command.pet_id, PetProfile.user_id == command.user_id,
        ).with_for_update())
        if pet is None:
            raise LookupError("pet not found for owner")
        bound_event = await db.scalar(select(PetFactEvent).join(PetFactRequest,
            (PetFactRequest.event_id == PetFactEvent.id) &
            (PetFactRequest.pet_id == PetFactEvent.pet_id),
        ).where(PetFactRequest.pet_id == pet, PetFactRequest.request_key == command.request_key)
            .with_for_update().execution_options(populate_existing=True))
        if bound_event is not None:
            if bound_event.request_digest != digest:
                raise PetFactConflict("request key content differs")
            return bound_event
        existing = list((await db.scalars(select(PetFactEvent).where(
            PetFactEvent.pet_id == pet,
            or_(PetFactEvent.request_key == command.request_key,
                PetFactEvent.business_key == command.business_key),
        ).with_for_update().execution_options(populate_existing=True))).all())
        if existing:
            if len(existing) != 1 or existing[0].request_digest != digest:
                raise PetFactConflict("stable key content differs")
            db.add(PetFactRequest(pet_id=pet, request_key=command.request_key, event_id=existing[0].id))
            await db.flush()
            return existing[0]

        state = (await db.execute(select(PetState.__table__).where(
            PetState.pet_id == pet,
        ).with_for_update())).mappings().one_or_none()
        if state is None or state["record_version"] != command.expected_version:
            raise PetStateConflict("state version changed")
        next_version = command.expected_version + 1
        projection=dict(values=frozen["state_after"],closeness=state["closeness"]+command.closeness_delta,record_version=next_version)
        if command.stage_after is not None:projection['stage']=command.stage_after
        if command.settled_until is not None:projection['settled_at']=_utc(command.settled_until)
        if command.unlocked_after is not None:projection['unlocked_behaviors']=frozen['unlocked_after']
        updated = await db.execute(update(PetState).where(
            PetState.pet_id == pet, PetState.record_version == command.expected_version,
        ).values(**projection).execution_options(synchronize_session=False))
        if updated.rowcount != 1:
            raise PetStateConflict("state version changed")
        fact = PetFactEvent(
            pet_id=pet, user_id=command.user_id, request_key=command.request_key,
            business_key=command.business_key, request_digest=digest,
            event_type=command.event_type, source=command.source,
            participants=frozen["participants"], occurred_at=occurred_at,
            business_date=command.occurred_at.astimezone(ZoneInfo("Asia/Shanghai")).date(),
            result=frozen["result"], reaction=frozen["reaction"],
            state_before=state["values"], state_after=frozen["state_after"],
            closeness_before=state["closeness"], closeness_delta=command.closeness_delta,
            version_before=command.expected_version, version_after=next_version,
            rule_snapshot_id=command.rule_snapshot_id,
        )
        db.add(fact)
        await db.flush()
        db.add(PetFactRequest(pet_id=pet, request_key=command.request_key, event_id=fact.id))
        for surface in dict.fromkeys(command.display_surfaces):
            db.add(PetDisplayEntry(pet_id=pet, source_event_id=fact.id, surface=surface))
        for candidate in frozen["candidates"]:
            previous = await db.scalar(select(PetTaskCandidate).where(
                PetTaskCandidate.pet_id == pet,
                PetTaskCandidate.business_key == candidate["business_key"],
            ).with_for_update())
            if previous is None:
                db.add(PetTaskCandidate(pet_id=pet, source_event_id=fact.id, **candidate))
                await db.flush()
            elif previous.kind != candidate["kind"] or previous.payload != candidate["payload"]:
                raise PetFactConflict("candidate key content differs")
        await db.flush()
        # Core DML bypasses ORM synchronization. Resolve by identity metadata, then
        # refresh with await; reading an expired instance attribute would do sync I/O.
        loaded_state = db.identity_map.get(db.sync_session.identity_key(PetState, ident=(pet,)))
        if loaded_state is not None:
            await db.refresh(loaded_state)
        return fact


async def read_display_facts(db: AsyncSession, *, pet_id: str, surface: str) -> list[PetFactEvent]:
    return list((await db.scalars(select(PetFactEvent).join(PetDisplayEntry,
        (PetDisplayEntry.source_event_id == PetFactEvent.id) &
        (PetDisplayEntry.pet_id == PetFactEvent.pet_id),
    ).where(PetDisplayEntry.pet_id == pet_id, PetDisplayEntry.surface == surface)
        .order_by(PetFactEvent.occurred_at.desc(), PetFactEvent.id.desc()))).all())


async def purge_diagnostic_payloads(db: AsyncSession, *, before: datetime) -> int:
    """An explicit internal operation, never scheduled here; touches diagnostics only."""
    result = await db.execute(delete(PetDiagnosticPayload).where(
        PetDiagnosticPayload.recorded_at < _utc(before),
    ))
    return result.rowcount
