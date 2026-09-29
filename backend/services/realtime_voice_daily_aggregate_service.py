"""Transactional daily materialization into the existing voice-only table.

The first upsert locks a deterministic count row before taking the source
snapshot. This serializes concurrent recomputation of the same day, including
its first run. The reservation is never committed separately. Unmeasurable or
provisional values have no numeric row, and old numeric rows are removed.
"""
import hashlib
import json
import math
from datetime import datetime
from sqlalchemy import select
from backend.models.realtime_voice import VoiceMetricDaily
from backend.services.realtime_voice_daily_metric_service import (
    METRIC_NAMES,business_day_bounds,compute_daily_metrics,
)

DIMENSIONS={'timezone':'Asia/Shanghai','formula_version':'voice-daily-v1'}
DIMENSION_HASH=hashlib.sha256(json.dumps(DIMENSIONS,sort_keys=True,separators=(',',':')).encode()).hexdigest()
_RATE_NAMES=frozenset({'connect_rate','missed_rate','failure_rate','call01_fallback_rate','memory_success_rate','summary_success_rate'})


def daily_dimensions(pricing=None):
    dimensions = dict(DIMENSIONS)
    if pricing is not None:
        from backend.services.realtime_voice_pricing import SimulatedPricing
        if not isinstance(pricing, SimulatedPricing):
            raise ValueError('invalid_voice_pricing')
        dimensions['pricing'] = pricing.dimensions()
    digest = hashlib.sha256(json.dumps(dimensions,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dimensions, digest


def _validated_values(projection,day):
    if (projection.get('date')!=day.isoformat() or projection.get('timezone')!='Asia/Shanghai' or
            projection.get('formula_version')!='voice-daily-v1'):
        raise ValueError('invalid_voice_daily_identity')
    metrics=projection.get('metrics')
    if not isinstance(metrics,list) or len(metrics)!=len(METRIC_NAMES):
        raise ValueError('invalid_voice_daily_metric_set')
    seen=set();values={}
    for metric in metrics:
        name=metric.get('name')
        if not isinstance(name,str) or name not in METRIC_NAMES or name in seen:
            raise ValueError('invalid_voice_daily_metric_set')
        seen.add(name)
        status,value=metric.get('status'),metric.get('value')
        if status=='not_measurable' and value is None:
            continue
        if status not in {'measured','provisional'} or type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('invalid_voice_daily_value')
        if name in _RATE_NAMES and value>1:
            raise ValueError('invalid_voice_daily_rate')
        if status=='measured':values[name]=float(value)
    return values


async def _aggregate_once(session_factory,day,pricing=None):
    dimensions, dimension_hash = daily_dimensions(pricing)
    business_day_bounds(day)
    async with session_factory() as db:
        try:
            table=VoiceMetricDaily.__table__
            dialect=db.get_bind().dialect.name
            if dialect=='mysql':
                from sqlalchemy.dialects.mysql import insert
                anchor=insert(table).values(business_date=day,metric_name='daily_call_count',
                    dimension_hash=dimension_hash,dimension_json=dimensions,metric_value=0)
                anchor=anchor.on_duplicate_key_update(metric_value=table.c.metric_value)
            elif dialect=='sqlite':
                from sqlalchemy.dialects.sqlite import insert
                anchor=insert(table).values(business_date=day,metric_name='daily_call_count',
                    dimension_hash=dimension_hash,dimension_json=dimensions,metric_value=0)
                anchor=anchor.on_conflict_do_update(index_elements=['business_date','metric_name','dimension_hash'],
                    set_={'metric_value':table.c.metric_value})
            else:
                raise RuntimeError('unsupported_voice_aggregate_database')
            # DML obtains a write lock before the first consistent source read.
            await db.execute(anchor)
            projection=await compute_daily_metrics(db,day,pricing=pricing) if pricing is not None else await compute_daily_metrics(db,day)
            if pricing is not None and projection.get('pricing') != dimensions['pricing']:
                raise ValueError('invalid_voice_daily_pricing')
            values=_validated_values(projection,day)
            rows=(await db.scalars(select(VoiceMetricDaily).where(VoiceMetricDaily.business_date==day,
                VoiceMetricDaily.dimension_hash==dimension_hash,VoiceMetricDaily.metric_name.in_(METRIC_NAMES))
                )).all()
            existing={row.metric_name:row for row in rows}
            for row in rows:
                if row.dimension_json!=dimensions:
                    raise ValueError('invalid_voice_daily_dimensions')
                if row.metric_name not in values:
                    await db.delete(row)
            for name,value in values.items():
                row=existing.get(name)
                if row is None:
                    db.add(VoiceMetricDaily(business_date=day,metric_name=name,dimension_hash=dimension_hash,
                        dimension_json=dict(dimensions),metric_value=value))
                else:
                    row.metric_value=value
                    row.updated_at=datetime.utcnow()
            await db.commit()
            return projection
        except BaseException:
            await db.rollback()
            raise


async def aggregate_daily_metrics(session_factory,day,*,pricing=None):
    """Retry only known database lock conflicts, always with a fresh transaction."""
    from sqlalchemy.exc import DBAPIError
    for attempt in range(3):
        try:
            return await _aggregate_once(session_factory,day,pricing)
        except DBAPIError as exc:
            code=exc.orig.args[0] if getattr(exc.orig,'args',()) else None
            if code not in (1205,1213) or attempt==2:
                raise
