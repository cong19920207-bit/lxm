"""Read and grant one user's P1 voice extra-time balance."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend.database import get_db
from backend.models.realtime_voice import VoiceQuotaAccount
from backend.models.user import User
from backend.services.realtime_voice_quota_service import QuotaError, VoiceQuotaService, _day
from backend.services.realtime_voice_runtime_config_service import realtime_voice_runtime_config_service
from backend.utils.admin_auth import log_operation, require_role


router = APIRouter()
_READ_ROLES = ("super_admin", "ops_admin", "observer")
_WRITE_ROLES = ("super_admin", "ops_admin")


class GrantExtraRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seconds: int = Field(strict=True, ge=1, le=86400)
    expected_version: int = Field(strict=True, ge=0)


async def get_daily_seconds(user_id: int) -> int:
    bundle = await realtime_voice_runtime_config_service.load_bundle(user_id=user_id)
    snapshot = bundle.build_snapshot(user_id=user_id)
    return snapshot.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"]


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def _quota_error(exc: QuotaError) -> HTTPException:
    code = str(exc)
    status = (404 if code == "quota_admin_user_missing" else
              409 if code in {"quota_admin_version_conflict", "quota_admin_active_call",
                              "quota_clock_reversed"} else 422)
    messages = {
        "quota_admin_user_missing": "用户不存在",
        "quota_admin_version_conflict": "额度可能已变化，请核对当前余额和操作日志后再操作",
        "quota_admin_active_call": "用户正在通话，请在通话结束后首次补充时长",
        "quota_admin_amount_invalid": "补充时长须为 1–86400 秒的整数",
        "quota_admin_balance_overflow": "补充后余额超过系统上限",
    }
    return HTTPException(status_code=status, detail=messages.get(code, "语音额度操作失败"))


@router.get("/users/{user_id}/quota", dependencies=[require_role(*_READ_ROLES)])
async def get_user_quota(user_id: int, daily_seconds: int = Depends(get_daily_seconds),
                         now: datetime = Depends(current_time), db=Depends(get_db)):
    if await db.scalar(select(User.id).where(User.id == user_id)) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        balance = await VoiceQuotaService().balance(db, user_id, daily_seconds=daily_seconds,
                                                    now=now, published_config=True)
    except QuotaError as exc:
        raise _quota_error(exc) from exc
    account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == user_id))
    return JSONResponse({"code": 0, "data": {
        "quota_date": _day(now).isoformat(), "daily_free_seconds": daily_seconds,
        "free_remaining_seconds": balance.free, "extra_remaining_seconds": balance.extra,
        "remaining_seconds": balance.total, "version": account.version if account else 0,
    }}, headers={"Cache-Control": "no-store"})


@router.post("/users/{user_id}/quota/extra")
async def grant_user_extra(user_id: int, body: GrantExtraRequest, request: Request,
                           admin=require_role(*_WRITE_ROLES), daily_seconds: int = Depends(get_daily_seconds),
                           now: datetime = Depends(current_time), db=Depends(get_db)):
    try:
        result = await VoiceQuotaService().grant_extra(
            db, user_id, seconds=body.seconds, expected_version=body.expected_version,
            daily_seconds=daily_seconds, now=now,
        )
        old_extra = result["extra_remaining_seconds"] - body.seconds
        await log_operation(
            db, admin, "用户管理", "edit",
            f"为用户 ID:{user_id} 补充语音额外时长 {body.seconds} 秒",
            before_value=f"额外时长剩余 {old_extra} 秒",
            after_value=f"额外时长剩余 {result['extra_remaining_seconds']} 秒",
            request=request,
        )
        await db.commit()
    except QuotaError as exc:
        await db.rollback()
        raise _quota_error(exc) from exc
    except Exception:
        await db.rollback()
        raise
    return JSONResponse({"code": 0, "data": result}, headers={"Cache-Control": "no-store"})
