"""Read-only durable business-day projection for the ten P1 voice metrics.

Call rates use a creation-day cohort. Jobs use their own creation-day cohort and
current final outcome, once per durable job. No event counters or retry attempts
are used as substitutes. The caller owns the database transaction/snapshot.
"""
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select,func,case,and_
from backend.models.realtime_voice import VoiceCall,VoiceMemoryJob,VoicePostprocessJob,VoiceUsageLedger

BUSINESS_ZONE = ZoneInfo('Asia/Shanghai')
TERMINAL_CALLS = ('ended','missed','failed','cancelled')
METRIC_NAMES = ('daily_call_count','connect_rate','missed_rate','failure_rate','avg_duration_seconds',
                'billable_seconds','estimated_cost','call01_fallback_rate','memory_success_rate','summary_success_rate')


def business_day_bounds(day):
    if type(day) is not date:
        raise ValueError('invalid_voice_business_date')
    start=datetime.combine(day,time(),BUSINESS_ZONE).astimezone(timezone.utc).replace(tzinfo=None)
    end=datetime.combine(day+timedelta(days=1),time(),BUSINESS_ZONE).astimezone(timezone.utc).replace(tzinfo=None)
    return start,end


def _count(condition):
    return func.coalesce(func.sum(case((condition,1),else_=0)),0)


def _metric(name,value,*,reason=None,provisional=False):
    return {'name':name,'value':value,'status':'not_measurable' if value is None else
            'provisional' if provisional else 'measured','reason':reason}


def _rate(name,numerator,denominator,*,provisional=False):
    return _metric(name,float(numerator/denominator) if denominator else None,
                   reason=None if denominator else 'no_eligible_samples',provisional=provisional)


async def compute_daily_metrics(db,day,*,pricing=None):
    start,end=business_day_bounds(day)
    calls=VoiceCall
    connected=calls.connected_at.is_not(None)
    completed=and_(connected,calls.status.in_(TERMINAL_CALLS))
    total,answered,missed,failed,active,duration,completed_count,fallbacks,unknown_decisions=(await db.execute(select(
        func.count(),_count(connected),_count(calls.status=='missed'),_count(calls.status=='failed'),
        _count(calls.status.not_in(TERMINAL_CALLS)),
        func.coalesce(func.sum(case((completed,calls.duration_seconds),else_=0)),0),_count(completed),_count(calls.call01_fallback.is_(True)),_count(calls.call01_fallback.is_(None))
    ).where(calls.created_at>=start,calls.created_at<end))).one()
    rows=[_metric('daily_call_count',int(total),provisional=bool(active)),
          _rate('connect_rate',answered,total,provisional=bool(active)),
          _rate('missed_rate',missed,total,provisional=bool(active)),
          _rate('failure_rate',failed,total,provisional=bool(active)),
          _rate('avg_duration_seconds',duration,completed_count,provisional=bool(active))]
    # quota_date is the writer's Shanghai slice date, not settlement/creation UTC.
    billable=await db.scalar(select(func.coalesce(func.sum(
        VoiceUsageLedger.free_seconds_used+VoiceUsageLedger.extra_seconds_used),0)).where(
        VoiceUsageLedger.quota_date==day,VoiceUsageLedger.usage_type=='connected'))
    legacy=await db.scalar(select(func.count()).select_from(VoiceUsageLedger).where(
        VoiceUsageLedger.quota_date.is_(None)))
    unsettled=await db.scalar(select(func.count()).select_from(calls).where(
        calls.connected_at.is_not(None),calls.connected_at<end,calls.status.not_in(TERMINAL_CALLS)))
    # An undated historical slice cannot safely be attributed to any requested day.
    rows.append(_metric('billable_seconds',None if legacy else int(billable),
        reason='undated_legacy_usage' if legacy else 'settlement_pending' if unsettled else None,
        provisional=bool(unsettled)))
    if pricing is None:
        rows.append(_metric('estimated_cost',None,reason='price_unconfigured'))
    else:
        rows.append(_metric('estimated_cost',None if legacy or unsettled else float(pricing.estimate(int(billable))),
            reason='undated_legacy_usage' if legacy else 'settlement_pending' if unsettled else None))
    rows.append(_metric('call01_fallback_rate',None,reason='unknown_call01_outcomes') if unknown_decisions else
                _rate('call01_fallback_rate',fallbacks,total,provisional=bool(active)))
    job=VoiceMemoryJob
    succeeded,unsuccessful,pending=(await db.execute(select(_count(job.status=='success'),
        _count(and_(job.status=='failed',job.next_retry_at.is_(None))),
        _count((job.status.in_(('pending','processing'))) | and_(job.status=='failed',job.next_retry_at.is_not(None))))
        .where(job.created_at>=start,job.created_at<end))).one()
    rows.append(_rate('memory_success_rate',succeeded,succeeded+unsuccessful,provisional=bool(pending)))
    memory_pending=int(pending)
    job=VoicePostprocessJob
    succeeded,unsuccessful,pending=(await db.execute(select(
        _count(and_(job.status=='success',calls.summary_status=='ready')),
        _count(and_(job.status=='failed',job.next_retry_at.is_(None))),
        _count(job.status.in_(('pending','processing')) | and_(job.status=='failed',job.next_retry_at.is_not(None))))
        .join(calls,calls.call_id==job.call_id).where(job.job_type=='call_summary',
            job.created_at>=start,job.created_at<end))).one()
    rows.append(_rate('summary_success_rate',succeeded,succeeded+unsuccessful,provisional=bool(pending)))
    return {**({'pricing':pricing.dimensions()} if pricing is not None else {}),'date':day.isoformat(),'timezone':'Asia/Shanghai','formula_version':'voice-daily-v1',
            'call_cohort':'created_at','job_cohort':'created_at','usage_basis':'quota_date',
            'as_of_utc':datetime.now(timezone.utc).isoformat(),
            'history_basis':'current_durable_state','settlement_pending_calls':int(unsettled),
            'pending_calls':int(active),'pending_memory_jobs':memory_pending,'pending_summary_jobs':int(pending),
            'metrics':rows}
