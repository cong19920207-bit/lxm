"""CALL-01: one schema and state path for both first and subsequent calls."""
import asyncio
import json
import logging
import secrets
import time as clock
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, update

from backend.models.realtime_voice import VoiceCall
from backend.models.relationship import Relationship
from backend.models.life_plan import LifePlan
from backend.services.realtime_voice_state_service import transition_call
from backend.services.realtime_voice_prompt_templates import build_decision_prompt

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo('Asia/Shanghai')
NEUTRAL_OPENING = '喂，我在。'


def ring_timing(settings):
    """Consume frozen timing while retaining the PRD's 4s/12s hard bounds."""
    ceiling = min(12, max(4, settings.get('max_wait_seconds', 12)))
    minimum = min(ceiling, max(4, settings.get('min_ring_seconds', 4)))
    low = min(8, max(4, settings.get('fallback_delay_min_seconds', 4)))
    high = min(8, max(low, settings.get('fallback_delay_max_seconds', 8)))
    return minimum, ceiling, low, high


class DecisionOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    answer: bool
    delay_seconds: int = Field(ge=0, le=12)
    opening_text: str = Field(max_length=200)


@dataclass(frozen=True)
class CallDecision:
    answer: bool
    delay_seconds: int
    opening_text: str
    fallback: bool
    failure_category: str | None
    forced_answer: bool


async def decide_call(*, inputs, settings, model=None, metric=None, metrics=None):
    started=clock.monotonic()
    metric = metric or (lambda name, value: logger.info('%s=%s', name, value))
    fallback = False; category = None
    minimum, ceiling, low, high = ring_timing(settings)
    if model is None:
        from backend.utils.llm_client import LLMClient
        async def model(prompt):
            client = LLMClient()
            try:
                return await client.chat_sync(prompt, timeout_sec=3)
            finally:
                await client.close()
    try:
        prompt = settings.get('prompt_template', '')
        if not prompt.strip():
            raise ValueError('unconfigured')
        prompt = build_decision_prompt(prompt, inputs)
        async with asyncio.timeout(3):
            raw = await model(prompt)
        if not isinstance(raw, str) or len(raw) > 4096:
            raise ValueError('invalid_output')
        output = DecisionOutput.model_validate_json(raw)
    except Exception as exc:
        fallback = True
        category = 'timeout' if isinstance(exc, TimeoutError) else 'decision_invalid'
        output = DecisionOutput(answer=True, delay_seconds=low+secrets.randbelow(high-low+1), opening_text=NEUTRAL_OPENING)
        metric('voice.call01.fallback.'+category, 1)
    forced = inputs.get('missed_last_5_minutes', 0) >= 5
    answer = output.answer or forced
    delay = min(ceiling, max(minimum, output.delay_seconds)) if answer else 0
    opening = NEUTRAL_OPENING if forced and not output.answer else output.opening_text
    metric('voice.call01.decision.answer' if answer else 'voice.call01.decision.missed', 1)
    if metrics is not None:
        events=[('voice.call01.decision_duration_ms',{'result':'fallback' if fallback else 'model'},
            max(0,int((clock.monotonic()-started)*1000))),
            ('voice.call01.output',{'result':'valid' if not fallback else 'timeout' if category=='timeout' else 'invalid'},1),
            ('voice.call01.decision',{'result':'answer' if answer else 'missed','mode':'forced' if forced else 'ordinary'},1)]
        if fallback:events.append(('voice.call01.fallback',{'reason':category},1))
        await metrics.emit_many(events)
    return CallDecision(answer, delay, opening, fallback, category, forced)


@dataclass(frozen=True)
class RingGate:
    target_seconds: int
    minimum: int = 4
    ceiling: int = 12

    def result(self, *, elapsed, ready, cancelled=False, provider_error=False):
        if cancelled:
            return 'cancelled'
        if provider_error or (elapsed >= self.ceiling and not ready):
            return 'failed'
        if ready and elapsed >= max(self.minimum, self.target_seconds):
            return 'connected'
        return 'ringing'


async def call_decision_inputs(db, *, user_id, call_id, now):
    local = now.astimezone(SHANGHAI)
    midnight = datetime.combine(local.date(), time(), SHANGHAI).astimezone(timezone.utc).replace(tzinfo=None)
    common = (VoiceCall.user_id == user_id, VoiceCall.call_id != call_id)
    previous = await db.scalar(select(func.count()).select_from(VoiceCall).where(*common))
    today = await db.scalar(select(func.count()).select_from(VoiceCall).where(*common, VoiceCall.created_at >= midnight))
    missed = await db.scalar(select(func.count()).select_from(VoiceCall).where(*common, VoiceCall.status == 'missed',
        VoiceCall.ended_at >= (now-timedelta(minutes=5)).replace(tzinfo=None)))
    relationship = await db.scalar(select(Relationship).where(Relationship.user_id == user_id))
    plan = await db.scalar(select(LifePlan).where(LifePlan.plan_date == local.date(), LifePlan.gen_status == 'ready'))
    scenes = plan.scenes[:24] if plan and isinstance(plan.scenes, list) else []
    schedule = [{k: str(s.get(k, ''))[:200] for k in ('time_range','description')} for s in scenes if isinstance(s, dict)]
    return dict(is_first_call=previous == 0, previous_calls=previous, calls_today=today,
                missed_last_5_minutes=missed, relationship_level=relationship.level if relationship else 0,
                relationship_description=(relationship.relation_description or '')[:300] if relationship else '',
                current_time=local.isoformat(), schedule=schedule)

