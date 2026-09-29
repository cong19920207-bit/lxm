"""Independent voice dashboard reads; no aggregation writes or export routes."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from backend.database import get_db
from backend.services.realtime_voice_daily_metric_service import compute_daily_metrics
from backend.services.realtime_voice_metric_read_service import metric_dictionary
from backend.utils.admin_auth import require_role

router = APIRouter()
_VOICE_DASHBOARD_READ_ROLES = ('super_admin', 'ai_trainer', 'tech_ops', 'ops_admin', 'observer')


def response(data):
    return JSONResponse({'code': 0, 'data': data}, headers={'Cache-Control': 'no-store'})


@router.get('/metrics/dictionary')
async def dictionary(admin=require_role(*_VOICE_DASHBOARD_READ_ROLES)):
    return response({'events': metric_dictionary()})


@router.get('/metrics/daily')
async def daily(day: date, simulated_pricing: bool = False, admin=require_role(*_VOICE_DASHBOARD_READ_ROLES), db=Depends(get_db)):
    # UTC conversion and the next-day upper bound must both be representable.
    if day <= date.min or day >= date.max:
        raise HTTPException(422, '业务日期超出支持范围')
    try:
        if simulated_pricing:
            from backend.services.realtime_voice_pricing import SIMULATED_PRICING
            data = await compute_daily_metrics(db, day, pricing=SIMULATED_PRICING)
        else:
            data = await compute_daily_metrics(db, day)
    except SQLAlchemyError:
        raise HTTPException(503, '语音日指标暂不可用') from None
    return response(data)


async def observation_cache():
    from backend.redis_client import get_redis
    try:
        return await get_redis()
    except Exception:
        return None


@router.get('/metrics/observations')
async def observations(day: date, admin=require_role(*_VOICE_DASHBOARD_READ_ROLES),
                       cache=Depends(observation_cache)):
    from backend.services.realtime_voice_observation_service import read_observations
    return response(await read_observations(cache, day))


@router.get('/metrics/history')
async def history(start: date, end: date, simulated_pricing: bool = False, admin=require_role(*_VOICE_DASHBOARD_READ_ROLES),db=Depends(get_db)):
    from backend.services.realtime_voice_metric_history_service import read_history
    try:
        from backend.services.realtime_voice_pricing import SIMULATED_PRICING
        data=await read_history(db,start,end,pricing=SIMULATED_PRICING if simulated_pricing else None)
    except ValueError:
        raise HTTPException(422,'起止日期需有序且范围不超过31天') from None
    except SQLAlchemyError:
        raise HTTPException(503,'语音历史指标暂不可用') from None
    return response(data)


@router.get('/metrics/billing-preview')
async def billing_preview(start: date, end: date, bill_start: date, bill_end: date,
                          unit_price: str = Query(..., max_length=64),
                          billed_cost: str = Query(..., max_length=64),
                          unit: str = Query(..., max_length=6),
                          currency: str = Query(..., max_length=3),
                          bill_currency: str = Query(..., max_length=3),
                          admin=require_role(*_VOICE_DASHBOARD_READ_ROLES), db=Depends(get_db)):
    from backend.services.realtime_voice_cost_preview_service import preview_cost
    try:
        data = await preview_cost(db, start=start, end=end, bill_start=bill_start, bill_end=bill_end,
                                  unit_price=unit_price, billed_cost=billed_cost, unit=unit,
                                  currency=currency, bill_currency=bill_currency)
    except ValueError:
        raise HTTPException(422, '日期需同周期且不超过31天，币种需一致，金额需为有效非负数') from None
    except SQLAlchemyError:
        raise HTTPException(503, '模拟成本暂不可用') from None
    return response(data)
