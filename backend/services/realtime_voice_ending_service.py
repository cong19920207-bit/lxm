"""Server-clock ending policy. Models propose; only the owner finalizes."""
import logging
import time
from collections import Counter
from functools import wraps
from backend.services.realtime_voice_prompt_templates import CLOSING_REPLY_RULES, build_closing_semantic_prompt

logger = logging.getLogger(__name__)


def observe_ending(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        policy = self.ending
        try:
            return await method(self, *args, **kwargs)
        finally:
            if policy is not None:
                events = policy.take_metrics()
                if events:
                    await self.metrics.emit_many(events)
    return wrapped


class EndingPolicy:
    def __init__(self, *, connected_at, hard_limit, goodbye_timeout,
                 silence_confirm, silence_hangup, time_low, post_playback_buffer_ms=800):
        self._observations = Counter()
        self._grace_seen = False
        self.connected_at, self.hard_limit = connected_at, hard_limit
        self.goodbye_timeout = goodbye_timeout
        self.silence_confirm, self.silence_hangup = silence_confirm, silence_hangup
        self.time_low = time_low
        self.post_playback_buffer_ms = post_playback_buffer_ms
        self.wait_started = None
        self.silence_elapsed = 0.0
        self.last_tick = None
        self.was_waiting = False
        self.confirmed_silence = False
        self.pending_reason = self.goodbye_deadline = self.goodbye_reply = None
        self.native_pending = False
        self.played_deadline = None
        self.generation = 0
        self.soft_closing = self.ended = False

    def observe(self, kind):
        self._observations[kind] = min(1000000000, self._observations[kind] + 1)

    def take_metrics(self):
        observations, self._observations = self._observations, Counter()
        return [('voice.finalizer.policy', {'kind':kind}, amount)
                for kind, amount in observations.items()]

    def _end(self, reason):
        if self.ended:
            return []
        self.ended = True
        self.observe(reason)
        logger.info('voice.ending.final_reason=%s', reason)
        return ['end:' + reason]

    def _goodbye(self, reason, now):
        if self.ended or self.pending_reason:
            return []
        self.observe("silence_goodbye" if reason == "silence_timeout" else "exit_goodbye")
        self.pending_reason = reason
        self.goodbye_deadline = now + self.goodbye_timeout
        self.generation += 1
        logger.info('voice.ending.pending_reason=%s', reason)
        return ['goodbye:' + reason]

    def native_exit(self, reply_id):
        # The provider has already spoken the goodbye. No extra query and no
        # generation-end timer may cut off audio still queued in the browser.
        if self.ended or self.pending_reason:
            return []
        self.observe('native_exit')
        self.pending_reason = 'exit_intent'
        self.native_pending = True
        self.goodbye_reply = reply_id
        self.goodbye_deadline = None
        self.generation += 1
        logger.info('voice.ending.native_exit_pending reply_id=%s', reply_id)
        return []

    def exit_intent(self, *, now, explicit):
        if explicit is not True:
            logger.info('voice.ending.exit_ambiguous=1')
            return []
        return self._goodbye('exit_intent', now)

    def resume(self, *, now):
        self.wait_started = None
        self.silence_elapsed = 0.0
        self.last_tick = None
        self.was_waiting = False
        self.confirmed_silence = False
        if self.ended or not self.pending_reason:
            return []
        self.pending_reason = self.goodbye_deadline = self.goodbye_reply = None
        self.native_pending = False
        self.played_deadline = None
        self.generation += 1
        self.observe('goodbye_cancelled')
        logger.info('voice.ending.exit_cancelled=1')
        return ['cancel_goodbye']

    def bind_goodbye(self, reply_id, generation):
        if generation == self.generation and self.pending_reason and not self.ended:
            self.goodbye_reply = reply_id

    def played(self, reply_id, *, now=None):
        if self.pending_reason and self.goodbye_reply == reply_id and not self.ended:
            if self.played_deadline is None:
                self.played_deadline = (time.monotonic() if now is None else now) + self.post_playback_buffer_ms / 1000
                self.goodbye_deadline = None
                logger.info('voice.ending.played_buffer_started reply_id=%s delay_ms=%d', reply_id, self.post_playback_buffer_ms)
        return []

    def tick(self, *, now, waiting, mic_ok, remaining, grace_deadline=None):
        if self.ended:
            return []
        if grace_deadline is not None and not self._grace_seen:
            self._grace_seen = True
            self.observe('grace_started')
        if now >= self.connected_at + self.hard_limit:
            return self._end('hard_limit')
        if grace_deadline is not None and now >= grace_deadline:
            return self._end('quota_exhausted')
        if self.pending_reason:
            if self.played_deadline is not None and now >= self.played_deadline:
                return self._end(self.pending_reason)
            if self.goodbye_deadline is not None and now >= self.goodbye_deadline:
                return self._end(self.pending_reason)
            return []
        if waiting and mic_ok:
            if self.wait_started is None:
                self.wait_started = now
            if self.was_waiting and self.last_tick is not None:
                self.silence_elapsed += max(0, now-self.last_tick)
            self.last_tick, self.was_waiting = now, True
            elapsed = self.silence_elapsed
            if elapsed >= self.silence_hangup:
                return self._goodbye('silence_timeout', now)
            if elapsed >= self.silence_confirm and not self.confirmed_silence:
                self.confirmed_silence = True
                self.observe("silence_confirm")
                return ['silence_confirm']
        else:
            self.last_tick, self.was_waiting = now, False
            if not mic_ok or not self.confirmed_silence:
                self.wait_started = None
                self.silence_elapsed = 0.0
                self.confirmed_silence = False
        if remaining <= self.time_low and not self.soft_closing:
            self.soft_closing = True
            self.observe("time_low")
            logger.info('voice.ending.time_low=1')
            return ['time_low']
        return []


class ClosingSemanticGate:
    def __init__(self, *, model=None, disclosure_guard=None):
        self.model = model
        self.disclosure_guard = disclosure_guard

    async def _decision(self, key, rule, data):
        import asyncio
        import json
        async def default_model(prompt):
            from backend.utils.llm_client import LLMClient
            client = LLMClient()
            try:
                return await client.chat_sync(prompt, timeout_sec=3)
            finally:
                await client.close()
        try:
            if self.disclosure_guard is not None and not await self.disclosure_guard(data):
                logger.info('voice.ending.semantic_unavailable=1')
                return None
            prompt = build_closing_semantic_prompt(key, rule, data)
            async with asyncio.timeout(3):
                raw = await (self.model or default_model)(prompt)
            value = json.loads(raw)
            if isinstance(value, dict) and set(value) == {key} and type(value[key]) is bool:
                return value[key]
            logger.info('voice.ending.semantic_unavailable=1')
            return None
        except Exception:
            logger.info('voice.ending.semantic_unavailable=1')
            return None

    async def explicit_exit(self, user_text):
        if len(user_text) > 8000:
            return False
        return await self._decision('explicit',
            '判断用户是否明确表示现在结束本通话，例如我先去开会晚点聊；仅描述未来安排、模糊表达或询问均否。模型只提出意图，不执行挂断。',
            {'user_text': user_text[:8000]})

    async def allow_reply(self, current_topic, reply_text):
        if len(reply_text) > 16000:
            return False
        return await self._decision('allowed',
            CLOSING_REPLY_RULES,
            {'current_topic': current_topic[:8000], 'candidate_reply': reply_text[:16000]})


class ClosingOutputBuffer:
    """Hold complete candidate output during closing until the semantic guard.

    Unplayed candidates are never playback evidence. Limits fail closed, rather
    than releasing arbitrary new-topic audio while waiting for text.
    """
    def __init__(self, gate):
        self.gate = gate
        self.pending = {}
        self.decisions = {}
        self.failures = {}

    async def filter(self, event, *, restricted, topic, expected_text=None):
        import time
        reply = event.reply_id
        if not reply:
            return [event], False
        if reply in self.decisions:
            return ([event] if self.decisions[reply] else []), False
        if not restricted and reply not in self.pending:
            return [event], False
        if reply not in self.pending:
            if len(self.pending) + len(self.decisions) >= 4096:
                raise ValueError('closing_reply_limit')
            self.pending[reply] = {'events': [], 'text': '', 'bytes': 0, 'started': time.monotonic()}
        value = self.pending[reply]
        value['events'].append(event)
        if isinstance(event.payload, bytes):
            value['bytes'] += len(event.payload)
        elif event.kind == 'chat_text' and isinstance(event.payload, str):
            value['text'] += event.payload
        if value['bytes'] > 2_000_000 or len(value['text']) > 16000 or len(value['events']) > 4096:
            self.pending.pop(reply)
            self.decisions[reply] = False
            logger.info('voice.ending.closing_output_rejected=1')
            return [], True
        if event.kind != 'text_finished':
            return [], False
        # Only a server-bound fixed goodbye may bypass the model. Compare
        # whitespace/punctuation variants, never a prefix or a substring.
        import unicodedata
        def normalized(text):
            return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))
        exact = (isinstance(expected_text, str) and bool(normalized(expected_text))
                 and normalized(value['text']) == normalized(expected_text))
        if exact:
            logger.info('voice.ending.fixed_goodbye_verified=1')
        allowed = True if exact else (bool(value['text']) and await self.gate.allow_reply(topic, value['text']))
        if allowed is None:
            self.failures[reply] = 'unavailable'
        elif not allowed:
            self.failures[reply] = 'rejected'
        allowed = allowed is True
        self.pending.pop(reply, None)
        # A user resumption may invalidate this queue while the model is awaited.
        if reply in self.decisions:
            return [], False
        self.decisions[reply] = allowed
        if not allowed:
            logger.info('voice.ending.new_topic_or_unverified_rejected=1')
        return (value['events'] if allowed else []), not allowed

    def discard(self):
        for reply in self.pending:
            self.decisions[reply] = False
        self.pending.clear()
