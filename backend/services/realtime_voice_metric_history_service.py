"""Bounded read of materialized daily values; absent values are never zero-filled."""
import math
from datetime import date,timedelta,timezone
from sqlalchemy import select
from backend.models.realtime_voice import VoiceMetricDaily
from backend.services.realtime_voice_daily_metric_service import METRIC_NAMES
from backend.services.realtime_voice_daily_aggregate_service import DIMENSIONS,DIMENSION_HASH,daily_dimensions


async def read_history(db,start,end,*,pricing=None):
    dimensions, dimension_hash = daily_dimensions(pricing)
    if type(start) is not date or type(end) is not date or not 0 <= (end-start).days < 31:
        raise ValueError('invalid_voice_history_range')
    rows=(await db.scalars(select(VoiceMetricDaily).where(
        VoiceMetricDaily.business_date>=start,VoiceMetricDaily.business_date<=end,
        VoiceMetricDaily.dimension_hash==dimension_hash,VoiceMetricDaily.metric_name.in_(METRIC_NAMES)))).all()
    indexed={(row.business_date,row.metric_name):row for row in rows}
    days=[]
    for offset in range((end-start).days+1):
        day=start+timedelta(days=offset);metrics=[]
        for name in METRIC_NAMES:
            row=indexed.get((day,name))
            item=dict(name=name,value=None,status='not_measurable',reason='not_materialized',computed_at_utc=None)
            if row is not None:
                value=row.metric_value
                valid=(row.dimension_json==dimensions and type(value) in (int,float) and math.isfinite(value)
                       and value>=0 and (not name.endswith('_rate') or value<=1))
                if valid:
                    item.update(value=value,status='measured',reason=None,
                                computed_at_utc=row.updated_at.replace(tzinfo=timezone.utc).isoformat())
                else:
                    item['reason']='invalid_materialized_value'
            metrics.append(item)
        days.append(dict(date=day.isoformat(),metrics=metrics))
    return dict(start=start.isoformat(),end=end.isoformat(),timezone='Asia/Shanghai',
                formula_version=DIMENSIONS['formula_version'],history_basis='materialized_current_durable_state',
                days=days, **({'pricing':pricing.dimensions()} if pricing is not None else {}))
