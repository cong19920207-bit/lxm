"""Bounded, cyclic repair of completed Shanghai business days.

Always refresh yesterday, then revisit historical days so late settlements and
job outcomes are eventually reflected. The cursor is an optimization, never a
completion watermark: restart repeats work safely using transactional upserts.
"""
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, func
from backend.models.realtime_voice import (
    VoiceCall, VoiceMemoryJob, VoicePostprocessJob, VoiceUsageLedger, VoiceMetricDaily,
)
from backend.services.realtime_voice_daily_metric_service import BUSINESS_ZONE
from backend.services.realtime_voice_daily_aggregate_service import aggregate_daily_metrics


async def run_daily_batch(session_factory, *, now=None, after_day=None, limit=7, include_simulated=False):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('voice_daily_clock_requires_timezone')
    if type(limit) is not int or not 1 <= limit <= 31:
        raise ValueError('invalid_voice_daily_batch_limit')
    if after_day is not None and type(after_day) is not date:
        raise ValueError('invalid_voice_daily_cursor')
    if type(include_simulated) is not bool:
        raise ValueError('invalid_voice_simulation_mode')
    async def aggregate(day):
        await aggregate_daily_metrics(session_factory, day)
        if include_simulated:
            from backend.services.realtime_voice_pricing import SIMULATED_PRICING
            await aggregate_daily_metrics(session_factory, day, pricing=SIMULATED_PRICING)
    yesterday = now.astimezone(BUSINESS_ZONE).date() - timedelta(days=1)
    candidates = [yesterday]
    async with session_factory() as db:
        for model in (VoiceCall, VoiceMemoryJob, VoicePostprocessJob):
            earliest = await db.scalar(select(func.min(model.created_at)))
            if earliest is not None:
                candidates.append(earliest.replace(tzinfo=timezone.utc).astimezone(BUSINESS_ZONE).date())
        for field in (VoiceUsageLedger.quota_date, VoiceMetricDaily.business_date):
            earliest = await db.scalar(select(func.min(field)))
            if earliest is not None:
                candidates.append(earliest)
    first = min(candidates)
    # A shrunk source range or future cursor must not suppress work forever.
    start = after_day + timedelta(days=1) if after_day is not None and first <= after_day < yesterday else first
    await aggregate(yesterday)
    processed = 0
    cursor = start
    while cursor < yesterday and processed < limit:
        await aggregate(cursor)
        processed += 1
        cursor += timedelta(days=1)
    # When the batch ends immediately before yesterday, wrap on the next tick.
    next_day = cursor - timedelta(days=1) if processed else None
    return {'next_day': next_day, 'historical_days': processed, 'latest_day': yesterday.isoformat()}
