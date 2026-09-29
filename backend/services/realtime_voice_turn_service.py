"""STEP-015 final-only facts. Text stays in memory until the safety port decides.

No keyword policy lives here. M4 supplies the real detector/isolation writer;
an absent detector keeps pending, text-free metadata rather than passing text.
"""
import asyncio
import logging
import time
from contextvars import ContextVar
from functools import wraps
from backend.services.realtime_voice_metric_service import stage_voice_metrics,flush_voice_metrics
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall, VoiceCallTurn
from backend.services.realtime_voice_state_service import lock_call, TERMINAL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GateDecision:
    safety: str = 'pending'
    crisis: str = 'pending'
    crisis_keyword: str | None = field(default=None, repr=False)
    effective_final: bool = False

    def __post_init__(self):
        if self.safety not in {'pending','passed','matched','error_allowed'} or self.crisis not in {
            'pending','passed','matched','suspected','isolation_failed'}:
            raise ValueError('invalid_voice_gate_decision')

    @property
    def permits_text(self):
        return self.crisis == 'passed' and self.safety != 'pending'


class PendingGate:
    async def assess(self, **kwargs):
        return GateDecision()


@dataclass(frozen=True)
class EffectiveText:
    text: str = field(repr=False)
    evidence: str
    played_ms: int | None = None
    completed: bool = False
    interrupted: bool = False


@dataclass
class TurnDraft:
    question_id: str
    reply_id: str | None = None
    user_final: str | None = field(default=None, repr=False)
    final_seen: bool = False
    generated: str = field(default='', repr=False)
    tts_finished: bool = False
    text_finished: bool = False
    closed: bool = False
    assistant_isolated: bool = False
    started_at: datetime = field(default_factory=datetime.utcnow)
    started_clock: float = field(default_factory=time.monotonic)


_turn_observations=ContextVar('voice_turn_observations',default=None)


def observed_turn(method):
    @wraps(method)
    async def run(self,*args,**kwargs):
        events=[];token=_turn_observations.set(events)
        try:
            return await method(self,*args,**kwargs)
        finally:
            _turn_observations.reset(token)
            if hasattr(self.gate,'take_metrics'):
                events.extend(self.gate.take_metrics())
            # Finish sequence/draft updates and release locks before telemetry.
            if events and self.metrics is not None:await self.metrics.emit_many(events)
    return run


class VoiceTurnService:
    def __init__(self, *, call_id, session_id, session_factory, gate=None, session_context=None, memory_job_writer=None, metrics=None):
        self.call_id, self.session_id, self.factory = call_id, session_id, session_factory
        self.gate = gate or PendingGate()
        self.session_context = session_context
        self.memory_job_writer = memory_job_writer
        self.metrics=metrics
        self._lock = asyncio.Lock()
        self._frozen = False
        self._sequence = 0
        self._pending = {}
        self._drafts = {}
        self._replies = {}
        self._pending_effective = {}

    def metric(self,category,value=1,*,db=None):
        logger.info('voice.turn.%s=%s', category, value)
        events=([('voice.turn.close_duration_ms',{},max(0,value)),('voice.turn.closed',{},1)]
            if category=='close_duration_ms' else [('voice.turn.event',{'kind':category},value)])
        if db is not None:stage_voice_metrics(db,events)
        elif _turn_observations.get() is not None:_turn_observations.get().extend(events)

    @observed_turn
    async def consume(self, event):
        if event.call_id != self.call_id or event.session_id != self.session_id:
            self.metric('orphan')
            raise ValueError('voice_event_identity_mismatch')
        if type(event.sequence) is not int or event.sequence < 1:
            raise ValueError('voice_event_sequence_invalid')
        for identity in (event.question_id, event.reply_id):
            if identity is not None and (not isinstance(identity,str) or not 1 <= len(identity) <= 64):
                raise ValueError('voice_event_identity_invalid')
        async with self._lock:
            if self._frozen:
                self.metric('late')
                return
            if event.sequence <= self._sequence or event.sequence in self._pending:
                self.metric('duplicate')
                return
            if event.sequence > self._sequence + 128 or len(self._pending) >= 128:
                self.metric('out_of_order')
                raise ValueError('voice_event_reorder_limit')
            self._pending[event.sequence] = event
            if event.sequence != self._sequence + 1:
                self.metric('out_of_order')
            while self._sequence + 1 in self._pending:
                next_event = self._pending[self._sequence + 1]
                await self._handle(next_event)
                self._sequence += 1
                self._pending.pop(self._sequence)

    def _draft(self, question_id):
        if not question_id:
            self.metric('orphan')
            raise ValueError('voice_question_missing')
        if question_id not in self._drafts:
            if len(self._drafts) >= 4096:
                raise ValueError('voice_turn_limit')
            self._drafts[question_id] = TurnDraft(question_id)
        return self._drafts[question_id]

    async def _handle(self, event):
        if event.kind == 'backchannel_filtered':
            draft = self._drafts.get(event.question_id)
            if draft is not None and not draft.final_seen and not draft.generated and draft.reply_id is None:
                self._drafts.pop(event.question_id, None)
            return
        if event.kind not in {'user_speech_started','asr_interim','asr_final','user_speech_finished',
                              'chat_text','sentence_started','sentence_finished','text_finished','tts_finished'}:
            return
        if event.reply_id in self._replies and self._replies[event.reply_id] != event.question_id:
            self.metric('orphan')
            raise ValueError('voice_reply_identity_conflict')
        draft = self._draft(event.question_id)
        if draft.closed:
            self.metric('late')
            return
        if event.reply_id:
            previous = self._replies.get(event.reply_id)
            if (previous is not None and previous != draft.question_id) or (
                draft.reply_id is not None and draft.reply_id != event.reply_id):
                self.metric('orphan')
                raise ValueError('voice_reply_identity_conflict')
            draft.reply_id = event.reply_id
            self._replies[event.reply_id] = draft.question_id
        if event.kind == 'asr_interim':
            self.metric('interim')
        elif event.kind == 'asr_final':
            if draft.final_seen:
                self.metric('duplicate')
                return
            if not isinstance(event.payload,str) or len(event.payload)>65536:
                raise ValueError('voice_final_invalid')
            draft.user_final = event.payload
            try:
                async with self.factory() as db:
                    row, _ = await self._write_text(db, draft, 'user', event.payload)
                    confidence = getattr(event, 'asr_confidence', None)
                    if confidence is not None:
                        import math
                        if type(confidence) not in {int,float} or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                            raise ValueError('voice_asr_confidence_invalid')
                        row.user_asr_confidence = confidence
                    await db.commit()
                    await self._after_commit(db)
            except Exception:
                logger.error('voice.crisis.persistence_failed call_id=%s direction=user', self.call_id)
                self.metric('persistence_failed')
            finally:
                draft.user_final = None
            draft.final_seen = True
            self.metric('final')
        elif event.kind == 'chat_text':
            if not event.reply_id or not isinstance(event.payload,str) or len(draft.generated)+len(event.payload)>131072:
                raise ValueError('voice_generated_invalid')
            if not draft.assistant_isolated:
                draft.generated += event.payload
        elif event.kind == 'tts_finished':
            draft.tts_finished = True
        elif event.kind == 'text_finished':
            draft.text_finished = True

    async def _turn(self, db, draft):
        call = await lock_call(db, self.call_id)
        if call is None or call.status in TERMINAL or call.deletion_fence_at is not None:
            self.metric('late',db=db)
            raise ValueError('voice_call_not_writable')
        row = await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.call_id==self.call_id,
            VoiceCallTurn.question_id==draft.question_id).with_for_update().execution_options(populate_existing=True))
        if row is None:
            last = await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.call_id==self.call_id)
                .order_by(VoiceCallTurn.turn_index.desc()).limit(1).with_for_update())
            row = VoiceCallTurn(call_id=self.call_id, question_id=draft.question_id,
                turn_index=1 if last is None else last.turn_index+1, reply_id=draft.reply_id,
                effective_text_evidence='none', turn_status='collecting', memory_status='skipped',
                user_content_safety_status='pending', assistant_content_safety_status='pending',
                user_crisis_status='pending', assistant_crisis_status='pending', started_at=draft.started_at,
                effective_text_expires_at=draft.started_at+timedelta(days=call.transcript_retention_days),
                generated_text_expires_at=draft.started_at+timedelta(days=call.generated_retention_days))
            db.add(row)
            await db.flush()
        elif row.reply_id and draft.reply_id and row.reply_id != draft.reply_id:
            raise ValueError('voice_reply_identity_conflict')
        elif draft.reply_id:
            row.reply_id = draft.reply_id
        return call, row

    async def _write_text(self, db, draft, direction, text, *, effective_final=False):
        call, row = await self._turn(db, draft)
        # The database, not this worker's in-memory dedupe set, owns facts.
        if row.turn_status != 'collecting' or (
            direction == 'user' and (row.user_text_final is not None or row.user_crisis_status != 'pending')) or (
            direction == 'assistant' and row.assistant_crisis_status == 'isolation_failed'):
            self.metric('duplicate',db=db)
            return row, False
        if direction == 'assistant' and row.assistant_crisis_status in {'matched', 'suspected'}:
            try:
                async with db.begin_nested():
                    await self.gate.isolate(db, call=call, turn=row, direction=direction, text=text,
                        decision=GateDecision(row.assistant_content_safety_status, row.assistant_crisis_status,
                                              effective_final=effective_final))
            except Exception:
                logger.error('voice.crisis.isolation_update_failed call_id=%s', self.call_id)
            return row, False
        try:
            if hasattr(self.gate, 'assess_in_transaction'):
                decision = await self.gate.assess_in_transaction(db, call_id=self.call_id, direction=direction, text=text)
            else:
                decision = await self.gate.assess(call_id=self.call_id, direction=direction, text=text)
            if not isinstance(decision, GateDecision):
                raise ValueError('invalid_voice_gate_result')
        except Exception:
            self.metric('gate_error',db=db)
            decision = GateDecision(crisis='isolation_failed')
        previous_safety = getattr(row, direction+'_content_safety_status')
        safety = ('matched' if 'matched' in (previous_safety, decision.safety) else
                  'error_allowed' if 'error_allowed' in (previous_safety, decision.safety) else decision.safety)
        setattr(row, direction+'_content_safety_status', safety)
        setattr(row, direction+'_crisis_status', decision.crisis)
        row.memory_status = 'skipped'
        if hasattr(self.gate, 'record'):
            await self.gate.record(call_id=self.call_id, turn_index=row.turn_index,
                                   direction=direction, decision=decision)
        if decision.crisis in {'matched','suspected'}:
            try:
                async with db.begin_nested():
                    await self.gate.isolate(db, call=call, turn=row, direction=direction,
                                           text=text, decision=decision)
                    await db.flush()
            except Exception:
                self.metric('isolation_failed',db=db)
                logger.error('voice.crisis.isolation_failed call_id=%s direction=%s', self.call_id, direction)
                setattr(row, direction+'_crisis_status', 'isolation_failed')
            if direction == 'assistant':
                row.assistant_text_generated = row.assistant_text_effective = None
                draft.generated = ''
                draft.assistant_isolated = True
            else:
                row.user_text_final = None
            return row, False
        if not decision.permits_text:
            if direction == 'assistant':
                row.assistant_text_generated = row.assistant_text_effective = None
                draft.generated = ''
                draft.assistant_isolated = True
            return row, False
        if direction == 'user':
            row.user_text_final = text
        else:
            row.assistant_text_effective = text or None
            generated_allowed = True
            if hasattr(self.gate, 'permits_generated'):
                try:
                    if hasattr(self.gate, 'permits_generated_in_transaction'):
                        generated_allowed = await self.gate.permits_generated_in_transaction(db, call_id=self.call_id, text=draft.generated)
                    else:
                        generated_allowed = await self.gate.permits_generated(call_id=self.call_id, text=draft.generated)
                except Exception:
                    generated_allowed = False
            row.assistant_text_generated = (draft.generated or None) if generated_allowed else None
        return row, True

    @observed_turn
    async def apply_effective(self, reply_id, result):
        """Internal STEP-016 evidence output, never bound to a client text field."""
        if not isinstance(result, EffectiveText) or result.evidence not in {
            'none','full','exact_played','confirmed_sentences'}:
            raise ValueError('voice_effective_result_invalid')
        if (result.evidence == 'none' and result.text) or (result.evidence == 'full' and not result.completed):
            raise ValueError('voice_effective_evidence_mismatch')
        async with self._lock:
            if self._frozen:
                return False
            question = self._replies.get(reply_id)
            if question is None:
                raise ValueError('voice_reply_unknown')
            draft = self._drafts[question]
            if draft.closed:
                self.metric('duplicate')
                return False
            if result.completed and not draft.tts_finished:
                raise ValueError('voice_reply_audio_unfinished')
            if result.evidence == 'full' and not draft.assistant_isolated and result.text != draft.generated:
                raise ValueError('voice_full_text_mismatch')
            self._pending_effective[reply_id] = result
            try:
                async with self.factory() as db:
                    await self._stage_effective(db,draft,result)
                    await db.commit()
                    await self._after_commit(db)
            except Exception:
                logger.error('voice.crisis.persistence_failed call_id=%s direction=assistant', self.call_id)
                self.metric('persistence_failed')
                draft.generated = ''
                draft.closed = True
            self._pending_effective.pop(reply_id,None)
            if result.completed or result.interrupted:
                draft.closed = True
                draft.generated = ''
                if self.session_context is not None:
                    try:
                        await self.session_context.capture_turn(call_id=self.call_id, question_id=question)
                    except Exception:
                        logger.warning('voice.session_context.capture_unavailable')
                self.metric('close_duration_ms', int((time.monotonic()-draft.started_clock)*1000))
            return True

    async def _after_commit(self, db):
        class DeferredMetrics:
            async def emit_many(self,events):
                pending=_turn_observations.get()
                if pending is not None:pending.extend(events)
        await flush_voice_metrics(db,DeferredMetrics())
        if hasattr(self.gate, 'after_commit'):
            try:
                await self.gate.after_commit(db, call_id=self.call_id)
            except Exception:
                logger.error('voice.crisis.notification_failed call_id=%s', self.call_id)

    async def safe_user_context(self, question_id):
        """Only assessed ordinary text may reach closing/context consumers."""
        async with self.factory() as db:
            text = await db.scalar(select(VoiceCallTurn.user_text_final).where(
                VoiceCallTurn.call_id == self.call_id, VoiceCallTurn.question_id == question_id,
                VoiceCallTurn.user_crisis_status == 'passed',
                VoiceCallTurn.user_content_safety_status == 'passed'))
            return (text or '')[:8000]

    async def _stage_effective(self, db, draft, result):
        row, allowed = await self._write_text(db,draft,'assistant',result.text,
            effective_final=result.completed or (result.interrupted and result.evidence != 'none'))
        if row.turn_status != 'collecting':
            return
        row.effective_text_evidence = result.evidence if allowed else 'none'
        row.played_audio_ms = result.played_ms
        row.assistant_interrupted = result.interrupted
        if result.completed:
            row.playback_completed_at = datetime.utcnow()
        if result.completed or result.interrupted:
            row.turn_status = 'interrupted' if result.interrupted else 'finalized'
            row.finalized_at = datetime.utcnow()
            if (row.user_text_final and row.assistant_text_effective
                    and row.user_content_safety_status == 'passed'
                    and row.assistant_content_safety_status == 'passed'
                    and row.user_crisis_status == row.assistant_crisis_status == 'passed'):
                row.memory_status = 'pending'
            if self.memory_job_writer is not None:
                call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == self.call_id))
                await self.memory_job_writer(db, call=call, turn=row)

    @observed_turn
    async def freeze(self):
        # Called by local stop BEFORE acquiring the finalizer's DB locks.
        # Draining the producer here prevents runtime-lock / row-lock inversion.
        self._frozen = True
        async with self._lock:
            if self._pending:
                self.metric('incomplete')
                self._pending.clear()

    async def final_flush(self, db):
        if not self._frozen:
            raise ValueError('voice_turn_producer_not_frozen')
        try:
            for reply_id,result in self._pending_effective.items():
                await self._stage_effective(db,self._drafts[self._replies[reply_id]],result)
            for draft in self._drafts.values():
                if draft.closed:
                    continue
                if draft.user_final is not None:
                    await self._write_text(db,draft,'user',draft.user_final)
                _, row = await self._turn(db,draft)
                if row.turn_status == 'collecting':
                    row.turn_status = 'aborted'
                    row.memory_status = 'skipped'
                    row.finalized_at = datetime.utcnow()
                    self.metric('incomplete',db=db)
        finally:
            if hasattr(self.gate,"take_metrics"):
                stage_voice_metrics(db,self.gate.take_metrics())
            for draft in self._drafts.values():
                draft.user_final = None
                draft.generated = ''
            self._pending_effective.clear()
