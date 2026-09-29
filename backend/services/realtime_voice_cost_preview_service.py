"""Read-only cost preview: durable seconds with explicitly simulated prices/bill."""
from datetime import date
from sqlalchemy import func, select
from backend.services.realtime_voice_pricing import estimate_amount
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_billing_metric_service import _amount, reconcile_bill
from backend.services.realtime_voice_daily_metric_service import business_day_bounds, TERMINAL_CALLS


async def preview_cost(db, *, start, end, unit_price, unit, currency, billed_cost,
                       bill_currency, bill_start, bill_end):
    if (any(type(day) is not date or day <= date.min or day >= date.max
            for day in (start, end, bill_start, bill_end)) or
            not 0 <= (end-start).days < 31):
        raise ValueError('invalid_billing_range')
    if unit not in ('minute', 'second'):
        raise ValueError('invalid_billing_unit')
    price = _amount(unit_price)
    arguments = dict(billed_cost=billed_cost, estimate_period=f'{start}/{end}',
                     bill_period=f'{bill_start}/{bill_end}', estimate_currency=currency,
                     bill_currency=bill_currency, evidence_locator='simulated-input')
    # Validate even when no usable duration exists, and before querying storage.
    result = reconcile_bill(estimated_cost='0', **arguments)
    seconds = int(await db.scalar(select(func.coalesce(func.sum(
        VoiceUsageLedger.free_seconds_used + VoiceUsageLedger.extra_seconds_used), 0)).where(
        VoiceUsageLedger.usage_type == 'connected',
        VoiceUsageLedger.quota_date.between(start, end))))
    legacy = await db.scalar(select(func.count()).select_from(VoiceUsageLedger).where(
        VoiceUsageLedger.quota_date.is_(None)))
    _, end_utc = business_day_bounds(end)
    unsettled = await db.scalar(select(func.count()).select_from(VoiceCall).where(
        VoiceCall.connected_at < end_utc, VoiceCall.status.not_in(TERMINAL_CALLS)))
    reason = 'undated_legacy_usage' if legacy else 'settlement_pending' if unsettled else None
    if reason:
        result.update(estimated_cost=None, difference_amount=None, difference_rate=None,
                      status='not_measurable')
    else:
        estimated = estimate_amount(seconds, price, unit)
        result = reconcile_bill(estimated_cost=estimated, **arguments)
    return {**result, 'start': str(start), 'end': str(end), 'timezone': 'Asia/Shanghai',
            'unit_price': str(price), 'unit': unit, 'billable_seconds': None if legacy else seconds,
            'reason': reason, 'data_source': 'simulated_pricing_and_bill',
            'rounding': 'half_up_6_decimal_places'}
