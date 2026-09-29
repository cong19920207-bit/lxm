"""Server-only connected meter and transactional voice quota settlement.

Call owner supplies server monotonic observations; never bind these methods to
client counters. Observation/checkpoint do not debit SQL. Caller owns the SQL
transaction and must settle before committing an end state or releasing a lease.
"""
from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from backend.models.user import User
from backend.models.realtime_voice import VoiceCall, VoiceQuotaAccount, VoiceUsageLedger

SHANGHAI = ZoneInfo('Asia/Shanghai')
logger = logging.getLogger(__name__)
CHECKPOINT_LUA = """
local old = redis.call('GET', KEYS[1])
if old then
  local previous = cjson.decode(old)
  local candidate = cjson.decode(ARGV[1])
  if previous.user_id ~= candidate.user_id then return -1 end
  if previous.last_monotonic > candidate.last_monotonic then return 0 end
  if previous.last_monotonic == candidate.last_monotonic and old ~= ARGV[1] then return -1 end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', 86400)
return 1
"""


class QuotaError(ValueError):
    pass


def _day(now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise QuotaError('server_time_invalid')
    return now.astimezone(SHANGHAI).date()


@dataclass(frozen=True)
class Balance:
    free: int
    extra: int

    @property
    def total(self):
        return self.free + self.extra


@dataclass
class ConnectedMeter:
    call_id: str
    user_id: int
    daily_seconds: int
    grace_limit: int
    last_monotonic: float | None = None
    last_wall: str | None = None
    connected: bool = False
    # Fractional connected seconds are carried, never rounded per heartbeat.
    remainder: float = 0.0
    grace_started: float | None = None
    grace_wall: str | None = None
    grace_seconds: int = 0
    slices: list[dict] = field(default_factory=list)
    muted: bool = False
    growth_seconds: float = 0.0

    def __post_init__(self):
        if not self.call_id or type(self.user_id) is not int or self.user_id < 1:
            raise QuotaError('meter_identity_invalid')
        if type(self.daily_seconds) is not int or self.daily_seconds < 0:
            raise QuotaError('daily_quota_invalid')
        if type(self.grace_limit) is not int or not 0 <= self.grace_limit <= 30:
            raise QuotaError('grace_limit_invalid')


class VoiceQuotaService:
    def __init__(self, metric=None, *, metrics=None):
        # Low cardinality only. Never user/call IDs or text as metric labels.
        self.metric = metric or self._log_metric
        self.metrics=metrics

    async def _observe_metrics(self,events):
        if self.metrics is not None:await self.metrics.emit_many(events)

    @staticmethod
    def _log_metric(name, value):
        logger.info('%s=%s', name, value)

    async def balance(self, db, user_id, *, daily_seconds, now, lock=False, published_config=False):
        day = _day(now)
        if type(daily_seconds) is not int or daily_seconds < 0:
            raise QuotaError('daily_quota_invalid')
        query = select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == user_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        account = await db.scalar(query)
        if account is None:
            return Balance(daily_seconds, 0)
        if account.free_quota_date > day:
            raise QuotaError('quota_clock_reversed')
        free = account.free_remaining_seconds if account.free_quota_date == day else daily_seconds
        if published_config and account.free_quota_date == day:
            used, entries = (await db.execute(select(
                func.coalesce(func.sum(VoiceUsageLedger.free_seconds_used), 0),
                func.count(VoiceUsageLedger.id),
            ).select_from(VoiceUsageLedger)
             .join(VoiceCall, VoiceCall.call_id == VoiceUsageLedger.call_id)
             .where(VoiceCall.user_id == user_id, VoiceUsageLedger.quota_date == day))).one()
            # An empty account with no ledger has no provable prior grant. Do not
            # turn a manual/failed debit into fresh free time on a read.
            if entries or free:
                free = max(0, daily_seconds - used)
        return Balance(free, account.extra_remaining_seconds)

    async def grant_extra(self, db, user_id, *, seconds, expected_version, daily_seconds, now):
        """Add administrator-granted seconds to one user's persistent extra pool.

        The caller owns the transaction, including its operation-log entry.
        Lock User first, matching call creation and settlement lock order.
        """
        if type(seconds) is not int or not 1 <= seconds <= 86400:
            raise QuotaError('quota_admin_amount_invalid')
        if type(expected_version) is not int or expected_version < 0:
            raise QuotaError('quota_admin_version_invalid')
        if type(daily_seconds) is not int or daily_seconds < 0:
            raise QuotaError('daily_quota_invalid')
        day = _day(now)
        user = await db.scalar(select(User.id).where(User.id == user_id).with_for_update())
        if user is None:
            raise QuotaError('quota_admin_user_missing')
        account = await db.scalar(select(VoiceQuotaAccount).where(
            VoiceQuotaAccount.user_id == user_id).with_for_update().execution_options(populate_existing=True))
        if (account.version if account is not None else 0) != expected_version:
            raise QuotaError('quota_admin_version_conflict')
        if account is None:
            # Authentication may have opened an older MySQL RR snapshot before
            # another transaction created the call. Read its current state.
            active = await db.scalar(select(VoiceCall.call_id).where(
                VoiceCall.user_id == user_id,
                VoiceCall.status.in_(('deciding', 'ringing', 'connected', 'reconnecting', 'ending'))
            ).limit(1).with_for_update())
            if active is not None:
                raise QuotaError('quota_admin_active_call')
            used = await db.scalar(select(func.coalesce(func.sum(VoiceUsageLedger.free_seconds_used), 0))
                                   .select_from(VoiceUsageLedger)
                                   .join(VoiceCall, VoiceCall.call_id == VoiceUsageLedger.call_id)
                                   .where(VoiceCall.user_id == user_id, VoiceUsageLedger.quota_date == day))
            account = VoiceQuotaAccount(user_id=user_id, free_quota_date=day,
                                        free_remaining_seconds=max(0, daily_seconds - int(used or 0)),
                                        extra_remaining_seconds=0, version=0)
            db.add(account)
        elif account.free_quota_date > day:
            raise QuotaError('quota_clock_reversed')
        if account.extra_remaining_seconds > 2_147_483_647 - seconds:
            raise QuotaError('quota_admin_balance_overflow')
        account.extra_remaining_seconds += seconds
        account.version += 1
        await db.flush()
        balance = await self.balance(db, user_id, daily_seconds=daily_seconds, now=now,
                                     published_config=True)
        return dict(free_remaining_seconds=balance.free,
                    extra_remaining_seconds=balance.extra,
                    remaining_seconds=balance.total, version=account.version)

    async def apply_published_balance(self, db, user_id, *, now, free_remaining):
        """Commit the new-call allowance only inside the successful create transaction."""
        account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == user_id)
                                  .with_for_update().execution_options(populate_existing=True))
        if account is not None and account.free_quota_date == _day(now) and account.free_remaining_seconds != free_remaining:
            account.free_remaining_seconds = free_remaining
            account.version += 1

    async def remaining(self, db, meter, *, now):
        """Live available seconds after this call's unsettled usage, no write."""
        day_key = _day(now).isoformat()
        balance = await self.balance(db, meter.user_id, daily_seconds=meter.daily_seconds, now=now)
        committed = (await db.scalars(select(VoiceUsageLedger).where(
            VoiceUsageLedger.call_id == meter.call_id))).all()
        free = sum(s['free_seconds_used'] for s in meter.slices if s['quota_date'] == day_key)
        extra = sum(s['extra_seconds_used'] for s in meter.slices)
        free -= sum(s.free_seconds_used for s in committed if str(s.quota_date) == day_key)
        extra -= sum(s.extra_seconds_used for s in committed)
        if free < 0 or extra < 0:
            raise QuotaError('observation_checkpoint_stale')
        return max(0, balance.free-free) + max(0, balance.extra-extra)

    @staticmethod
    def _append(meter, day, kind, seconds, free=0, extra=0):
        if not seconds:
            return
        key = day.isoformat()
        if meter.slices and meter.slices[-1]['quota_date'] == key and meter.slices[-1]['usage_type'] == kind:
            row = meter.slices[-1]
            row['duration_seconds'] += seconds
            row['free_seconds_used'] += free
            row['extra_seconds_used'] += extra
        else:
            meter.slices.append(dict(quota_date=key, usage_type=kind, duration_seconds=seconds,
                                     free_seconds_used=free, extra_seconds_used=extra))

    async def observe(self, db, meter, *, connected, monotonic, now, muted=False):
        _day(now)
        if type(muted) is not bool or type(connected) is not bool or type(monotonic) not in (int, float) or not math.isfinite(monotonic):
            raise QuotaError('server_observation_invalid')
        if meter.last_monotonic is not None and monotonic < meter.last_monotonic:
            raise QuotaError('observation_out_of_order')
        candidate = deepcopy(meter)
        old_grace = candidate.grace_started
        old_grace_seconds = candidate.grace_seconds
        if candidate.last_monotonic is not None and candidate.connected and candidate.grace_started is None:
            committed = (await db.scalars(select(VoiceUsageLedger).where(
                VoiceUsageLedger.call_id == candidate.call_id))).all()
            cursor = datetime.fromisoformat(candidate.last_wall)
            remaining = monotonic - candidate.last_monotonic
            elapsed = 0.0
            while remaining > 1e-9 and candidate.grace_started is None:
                local = cursor.astimezone(SHANGHAI)
                boundary = datetime.combine(local.date() + timedelta(days=1), time(), SHANGHAI)
                portion = min(remaining, (boundary - local).total_seconds())
                balance = await self.balance(db, candidate.user_id, daily_seconds=candidate.daily_seconds, now=cursor)
                day_key = local.date().isoformat()
                free_reserved = sum(s['free_seconds_used'] for s in candidate.slices if s['quota_date'] == day_key)
                extra_reserved = sum(s['extra_seconds_used'] for s in candidate.slices)
                free_reserved -= sum(s.free_seconds_used for s in committed if str(s.quota_date) == day_key)
                extra_reserved -= sum(s.extra_seconds_used for s in committed)
                if free_reserved < 0 or extra_reserved < 0:
                    raise QuotaError('observation_checkpoint_stale')
                free = max(0, balance.free - free_reserved)
                extra = max(0, balance.extra - extra_reserved)
                available = free + extra
                previous_remainder = candidate.remainder
                seconds = int(math.floor(portion + previous_remainder + 1e-9))
                charged = min(seconds, available)
                from_free = min(charged, free)
                self._append(candidate, local.date(), 'connected', charged, from_free, charged-from_free)
                candidate.remainder = portion + previous_remainder - seconds
                offset = max(0.0, available - previous_remainder)
                resets_at_exhaustion = (
                    candidate.daily_seconds > 0
                    and abs(offset - (boundary-local).total_seconds()) < 1e-9
                )
                if seconds >= available and not resets_at_exhaustion:
                    candidate.grace_started = candidate.last_monotonic + elapsed + offset
                    candidate.grace_wall = (cursor + timedelta(seconds=offset)).isoformat()
                    candidate.remainder = 0.0
                cursor += timedelta(seconds=portion)
                remaining -= portion
                elapsed += portion
        if candidate.grace_started is not None:
            total = min(candidate.grace_limit, max(0, int(monotonic - candidate.grace_started + 1e-9)))
            cursor = datetime.fromisoformat(candidate.grace_wall) + timedelta(seconds=candidate.grace_seconds)
            left = total - candidate.grace_seconds
            while left:
                local = cursor.astimezone(SHANGHAI)
                boundary = datetime.combine(local.date() + timedelta(days=1), time(), SHANGHAI)
                seconds = min(left, max(1, math.ceil((boundary-local).total_seconds())))
                self._append(candidate, local.date(), 'grace', seconds)
                cursor += timedelta(seconds=seconds); left -= seconds
            candidate.grace_seconds = total
        # Growth has its own fractional clock: active mute still consumes quota,
        # but never growth. Bound at the actual start of free closing grace.
        if candidate.last_monotonic is not None and candidate.connected and not candidate.muted:
            growth_end = min(monotonic, candidate.grace_started) if candidate.grace_started is not None else monotonic
            candidate.growth_seconds += max(0.0, growth_end - candidate.last_monotonic)
        candidate.muted = muted
        candidate.last_monotonic = float(monotonic)
        candidate.last_wall = now.isoformat()
        candidate.connected = connected
        meter.__dict__.update(candidate.__dict__)
        if old_grace is None and meter.grace_started is not None:
            self.metric('voice.quota.balance_zero', 1)
            self.metric('voice.quota.grace_enter', 1)
            await self._observe_metrics([('voice.quota.balance_zero',{},1),('voice.quota.grace',{'result':'trigger'},1)])
        must_end = meter.grace_started is not None and monotonic >= meter.grace_started + meter.grace_limit
        if must_end and old_grace_seconds < meter.grace_limit:
            self.metric('voice.quota.grace_end', 1)
            await self._observe_metrics([('voice.quota.grace',{'result':'end'},1)])
        return dict(in_grace=meter.grace_started is not None, grace_seconds=meter.grace_seconds, must_end=must_end)

    async def settle(self, db, meter):
        from sqlalchemy.exc import DBAPIError
        try:
            return await self._settle(db,meter)
        except QuotaError as exc:
            reason={'settlement_checkpoint_conflict':'checkpoint','quota_changed_before_settlement':'balance'}.get(str(exc))
            if reason:await self._observe_metrics([('voice.quota.transaction_conflict',{'reason':reason},1)])
            raise
        except DBAPIError as exc:
            code=exc.orig.args[0] if getattr(exc.orig,'args',()) else None
            if code in (1062,1205,1213) or getattr(exc.orig,'sqlstate',None)=='40001':
                await self._observe_metrics([('voice.quota.transaction_conflict',{'reason':'database'},1)])
            raise

    async def _settle(self, db, meter):
        # Uniform lock order serializes absent account creation and duplicate ends
        # across processes on MySQL. No commit, so end/ledger/account stay atomic.
        user = await db.scalar(select(User.id).where(User.id == meter.user_id).with_for_update())
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == meter.call_id,
                                                     VoiceCall.user_id == meter.user_id).with_for_update().execution_options(populate_existing=True))
        if user is None or call is None:
            raise QuotaError('call_owner_missing')
        # A locking read is essential: a preflight query may already have opened
        # a MySQL REPEATABLE READ snapshot before another owner settled the call.
        rows = (await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.call_id == meter.call_id)
                                .order_by(VoiceUsageLedger.segment_seq).with_for_update()
                                .execution_options(populate_existing=True))).all()
        desired, existing = defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0, 0])
        for source, target in ((meter.slices, desired), (rows, existing)):
            for s in source:
                value = s if isinstance(s, dict) else {k: getattr(s, k) for k in ('quota_date','usage_type','duration_seconds','free_seconds_used','extra_seconds_used')}
                if value['duration_seconds'] is None or value['quota_date'] is None:
                    raise QuotaError('legacy_usage_not_reconstructable')
                key = (str(value['quota_date']), value['usage_type'])
                for i, k in enumerate(('duration_seconds', 'free_seconds_used', 'extra_seconds_used')):
                    target[key][i] += value[k]
        if desired == existing:
            # The fractional growth clock may cross a second while the quota
            # ledger remains unchanged. Only active calls may advance it.
            if call.status in {'deciding', 'ringing', 'connected', 'reconnecting', 'ending'}:
                billed = sum(v[0] for k, v in desired.items() if k[1] == 'connected')
                eligible = min(billed, int(math.floor(meter.growth_seconds + 1e-9)))
                call.growth_eligible_seconds = max(call.growth_eligible_seconds, eligible)
                await db.flush()
            self.metric('voice.quota.replay_deduplicated', 1)
            await self._observe_metrics([('voice.quota.deduplicated',{},1)])
            return dict(idempotent=True, free_seconds_used=call.free_seconds_used, extra_seconds_used=call.extra_seconds_used)
        deltas = []
        for key in sorted(desired.keys() | existing.keys()):
            delta = [a-b for a, b in zip(desired[key], existing[key])]
            if any(v < 0 for v in delta):
                raise QuotaError('settlement_checkpoint_conflict')
            if any(delta):
                deltas.append((key, delta))
        account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == meter.user_id).with_for_update().execution_options(populate_existing=True))
        day = _day(datetime.fromisoformat(meter.last_wall))
        if account is None:
            account = VoiceQuotaAccount(user_id=meter.user_id, free_quota_date=day,
                                        free_remaining_seconds=meter.daily_seconds, extra_remaining_seconds=0, version=0)
            db.add(account)
        if account.free_quota_date > day:
            raise QuotaError('quota_clock_reversed')
        free_by_day = defaultdict(int)
        extra_delta = 0
        for (date_key, kind), (duration, free, extra) in deltas:
            if duration < 0 or (kind == 'connected' and duration != free+extra) or (kind == 'grace' and (free or extra)) or kind not in ('connected','grace'):
                raise QuotaError('usage_slice_invalid')
            free_by_day[date.fromisoformat(date_key)] += free
            extra_delta += extra
        for billed_day, amount in free_by_day.items():
            limit = account.free_remaining_seconds if billed_day == account.free_quota_date else meter.daily_seconds
            if amount > limit:
                self.metric('voice.quota.transaction_conflict', 1)
                raise QuotaError('quota_changed_before_settlement')
        if extra_delta > account.extra_remaining_seconds:
            self.metric('voice.quota.transaction_conflict', 1)
            raise QuotaError('quota_changed_before_settlement')
        if account.free_quota_date < day:
            account.free_quota_date = day
            account.free_remaining_seconds = meter.daily_seconds
        account.free_remaining_seconds -= free_by_day[day]
        account.extra_remaining_seconds -= extra_delta
        account.version += 1
        seq = max((r.segment_seq for r in rows), default=0)
        for (date_key, kind), (duration, free, extra) in deltas:
            seq += 1
            db.add(VoiceUsageLedger(call_id=meter.call_id, segment_seq=seq, quota_date=date.fromisoformat(date_key),
                                   usage_type=kind, duration_seconds=duration, free_seconds_used=free, extra_seconds_used=extra))
        call.free_seconds_used = sum(v[1] for v in desired.values())
        call.extra_seconds_used = sum(v[2] for v in desired.values())
        call.grace_seconds = sum(v[0] for k, v in desired.items() if k[1] == 'grace')
        billable_seconds = sum(v[0] for k, v in desired.items() if k[1] == 'connected')
        call.growth_eligible_seconds = min(billable_seconds, int(math.floor(meter.growth_seconds + 1e-9)))
        call.duration_seconds = billable_seconds + call.grace_seconds
        await db.flush()
        self.metric('voice.quota.settlement_staged_seconds', sum(v[1]+v[2] for _, v in deltas))
        from backend.services.realtime_voice_metric_service import stage_voice_metrics
        events=[]
        for (_,kind),(duration,free,extra) in deltas:
            events.extend([('voice.quota.usage_slice',{'kind':kind},1),
                ('voice.quota.usage_seconds',{'kind':kind},duration)])
            if kind=='grace':events.append(('voice.quota.grace_seconds',{},duration))
            else:events.append(('voice.quota.billing_input_seconds',{'source':'server'},free+extra))
        stage_voice_metrics(db,events)
        return dict(idempotent=False, free_seconds_used=call.free_seconds_used, extra_seconds_used=call.extra_seconds_used)

    async def checkpoint(self, cache, meter):
        # Retain after recovery: deleting before caller commits would lose the only
        # recoverable checkpoint if that transaction rolls back.
        if meter.last_monotonic is None:
            raise QuotaError('checkpoint_unobserved')
        result = await cache.eval(CHECKPOINT_LUA, 1, f'voice:quota:{meter.call_id}',
                                  json.dumps(asdict(meter), sort_keys=True))
        if result == -1:
            raise QuotaError('checkpoint_conflict')
        return result == 1

    async def recover(self, db, cache, *, call_id, user_id):
        raw = await cache.get(f'voice:quota:{call_id}')
        if raw is None:
            raise QuotaError('checkpoint_missing')
        try:
            meter = ConnectedMeter(**json.loads(raw))
        except (ValueError, TypeError):
            raise QuotaError('checkpoint_invalid') from None
        if meter.call_id != call_id or meter.user_id != user_id:
            raise QuotaError('checkpoint_owner_mismatch')
        return await self.settle(db, meter)
