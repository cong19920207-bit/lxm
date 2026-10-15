"""Due-slot scanner: version-captured cleanup and structured consumption outcomes."""
import logging
import time
from sqlalchemy import select, and_, or_
from backend.database import async_session_maker
from backend.models.agent_message import TriggerType
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.models.future_consumption import FutureConsumption
from backend.models.chat_lifecycle import ChatLifecycleEffect
from backend.redis_client import get_redis
from backend.services.agent_service import agent_service
from backend.services.step8_subchain import execute_step8_subchain
from backend.services import future_lifecycle as life
from backend.services.memory_business_guard import business_epoch, enter_business_epoch

logger=logging.getLogger(__name__)
FUTURE_EXPIRE_WINDOW_SECONDS=1800

class FutureSlotHandler:
    def __init__(self):
        self._exhausted = set()

    async def scan_and_consume(self):
        token=business_epoch.set(await enter_business_epoch(async_session_maker))
        try:
            now=int(time.time())
            async with async_session_maker() as db:
                accepted=select(FutureConsumption.consume_id).where(FutureConsumption.user_id==Relationship.user_id,
                    FutureConsumption.slot_version==Relationship.future_slot_version).exists()
                rows=(await db.execute(select(Relationship).join(User,Relationship.user_id==User.id).where(
                    Relationship.future_timestamp<=now,Relationship.future_timestamp>now-FUTURE_EXPIRE_WINDOW_SECONDS,
                    User.is_banned.is_(False),~accepted))).scalars().all()
                slots=[life.Slot.from_row(row) for row in rows]
            consumed=0
            for slot in slots:
                try:
                    result=await self._consume_one(slot.user_id,slot.action,slot=slot)
                    if result.terminal=='success':consumed+=1
                except Exception:logger.exception('future_consume_failed user=%s',slot.user_id)
            await self._reconcile_pending()
            return consumed
        finally:business_epoch.reset(token)

    async def _consume_one(self,user_id,future_action,*,slot=None):
        slot=slot or await life.capture(user_id)
        if slot is None or slot.action!=future_action:return life.Result(None,'superseded')
        redis=await get_redis()
        if await redis.exists(f'agent:blacklist:{user_id}'):
            await self._clear_future_slot(slot)
            return life.Result(None,'failed')
        if await agent_service.calculate_action_score(user_id,TriggerType.FUTURE)<6:
            await self._clear_future_slot(slot)
            return life.Result(None,'failed')
        result=await execute_step8_subchain(user_id,future_action,slot=slot)
        if result.terminal=='success':await self._on_consume_success(user_id,result)
        elif result.terminal in ('failed','superseded'):await self._clear_future_slot(slot)
        return result

    async def _on_consume_success(self,user_id,result):
        try:await life.handler_effects(user_id,result.consume_id)
        except Exception:logger.exception('future_confirmed_success_cleanup_failed consume=%s',result.consume_id)

    async def _clear_future_slot(self,slot):
        return await life.clear_slot(slot)

    async def cleanup_expired_slots(self):
        async with async_session_maker() as db:
            rows=(await db.execute(select(Relationship).where(Relationship.future_timestamp<=int(time.time())-1800))).scalars().all()
            slots=[life.Slot.from_row(row) for row in rows]
        cleaned=0
        for slot in slots:
            # An unresolved result is not a failed/expired consumption.
            async with async_session_maker() as db:
                pending=await db.scalar(select(FutureConsumption.consume_id).where(
                    FutureConsumption.user_id==slot.user_id,FutureConsumption.slot_version==slot.version,
                    FutureConsumption.state=='pending'))
            if pending is None and await self._clear_future_slot(slot):cleaned+=1
        return cleaned

    async def _reconcile_pending(self):
        """Bounded observations of the original identity; never regenerate an old slot."""
        from datetime import datetime, timedelta
        async with async_session_maker() as db:
            now=datetime.utcnow()
            expired=(await db.scalars(select(FutureConsumption.consume_id).where(FutureConsumption.state=='pending',
                FutureConsumption.reconcile_until<=now).limit(life.TIMING.scan_batch_size))).all()
            for cid in expired:
                if cid not in self._exhausted:
                    logger.error('future_reconcile_exhausted consume=%s',cid)
                    self._exhausted.add(cid)
            unfinished=select(ChatLifecycleEffect.id).where(ChatLifecycleEffect.owner_kind=='future',
                ChatLifecycleEffect.owner_id==FutureConsumption.consume_id,
                ChatLifecycleEffect.user_id==FutureConsumption.user_id,ChatLifecycleEffect.state=='pending').exists()
            rows=(await db.execute(select(FutureConsumption).where(or_(
                and_(FutureConsumption.state=='pending',FutureConsumption.reconcile_until>now),
                and_(FutureConsumption.state=='success',FutureConsumption.accepted_at>now-timedelta(seconds=life.TIMING.retention_seconds),unfinished)))
                .order_by(FutureConsumption.deadline_at).limit(life.TIMING.scan_batch_size))).scalars().all()
            identities=[(r.user_id,r.consume_id,life.Slot(r.user_id,r.slot_version,r.slot_timestamp,r.slot_action)) for r in rows]
        for uid,cid,slot in identities:
            result=await life.reconcile(uid,cid)
            if result.terminal=='success':await life.recover_effects(uid,cid)
            elif result.terminal in ('failed','superseded'):await self._clear_future_slot(slot)

future_handler=FutureSlotHandler()
