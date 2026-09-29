"""Two-stage interruption policy; PCM energy alone is never speech evidence.

PCM must be the client's AEC input. Provider speech identity and ASR semantics
are independent gates. This policy does not claim to replace device calibration.
"""
from array import array
import math
import sys
import unicodedata
from collections import Counter
from functools import wraps
import time
import asyncio
from contextvars import ContextVar


class BargeObservations:
    def __init__(self):
        self.events = Counter()
        self.durations = []

    def __call__(self, name, **dimensions):
        self.add(name, dimensions, 1)

    def add(self, name, dimensions, amount):
        if name == 'stop_clear_latency_ms':
            # At most one ACK sample per request; the controller caps requests at 4096.
            self.durations.append(('voice.barge_in.' + name, dict(dimensions), max(0, amount)))
            return
        key = (name, tuple(sorted(dimensions.items())))
        self.events[key] = min(1000000000, self.events[key] + max(0, amount))

    def drain(self):
        events, self.events = self.events, Counter()
        durations, self.durations = self.durations, []
        return [('voice.barge_in.' + name, dict(dimensions), amount)
                for (name, dimensions), amount in events.items()] + durations


_observation_scope = ContextVar('barge_observation_scope', default=None)


def observe_barge_in(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        scope = (self.barge_observations, asyncio.current_task())
        if _observation_scope.get() == scope:
            return await method(self, *args, **kwargs)
        token = _observation_scope.set(scope)
        try:
            return await method(self, *args, **kwargs)
        finally:
            _observation_scope.reset(token)
            # The filter timeout callback can call the gateway under its lock.
            # Retain these finite samples until the next outer operation/stop.
            if not self.backchannels.lock.locked():
                events = self.barge_observations.drain()
                if events:
                    await self.metrics.emit_many(events)
    return wrapped


class BargeInClassifier:
    def __init__(self, settings, words, observations=None):
        self.observations = observations or BargeObservations()
        self.candidate_seen = False
        self.settings, self.words = settings, words
        self.question = None
        self.resolved = False
        self._has_text = self._weak = self._strong = self._meaningful = False
        self.started_at = self.last_audio = None
        self.audio_ms = 0.0
        self.wall_ms = 0.0
        self.speech_ms = 0.0

    def start(self, question_id, *, now=None):
        if question_id != self.question:
            self.question = question_id
            self.resolved = False
            self.candidate_seen = False
            self._has_text = self._weak = self._strong = self._meaningful = False
            self.speech_ms = (min(self.audio_ms, self.wall_ms) if now is not None
                              and self.last_audio is not None and 0 <= now-self.last_audio <= .25 else 0.0)

    @staticmethod
    def normalize(value):
        return ''.join(c for c in value.strip() if not c.isspace() and not unicodedata.category(c).startswith('P'))

    def audio(self, pcm, *, now):
        samples = array('h', pcm)
        if sys.byteorder != 'little':
            samples.byteswap()
        rms = math.sqrt(sum((v / 32768) ** 2 for v in samples) / max(1, len(samples)))
        duration = len(samples) / 16  # 16 kHz PCM input, milliseconds
        if rms < self.settings['vad_rms_threshold']:
            self.started_at = self.last_audio = None
            self.audio_ms = self.wall_ms = 0.0
            return None
        if self.last_audio is None or now - self.last_audio > .25:
            self.started_at = now
            self.audio_ms = 0.0
        self.audio_ms += duration
        self.wall_ms = max(0, (now - self.started_at) * 1000) + min(duration, 20)
        self.last_audio = now
        if self.question:
            self.speech_ms = max(self.speech_ms, min(self.audio_ms, self.wall_ms))
        return self._decide(final=False)

    def text(self, question_id, text, *, final):
        if not self.question or question_id != self.question or self.resolved:
            return None
        from backend.services.realtime_voice_backchannel_service import pure_ack
        normalized = self.normalize(text)
        self._has_text = bool(normalized)
        self._weak = pure_ack(normalized, self.words['weak_acknowledgements'])
        self._strong = any(word in normalized for word in self.words['strong_interruptions'] + self.words['upgrade_connectors'])
        self._meaningful = len(normalized) >= 2
        return self._decide(final=final)

    def _decide(self, *, final):
        if self.resolved or not self.question or not self._has_text:
            return None
        duration = self.speech_ms
        if duration + .001 < self.settings['candidate_ms']:
            return None
        if not self.candidate_seen:
            self.candidate_seen = True
            self.observations('decision', source='classifier', result='candidate')
        if self._strong or (not self._weak and self._meaningful and (final or duration >= 250)):
            self.resolved = True
            self.observations('decision', source='classifier', result='escalated')
            return 'barge_in'
        if final and self._weak:
            self.resolved = True
            self.observations('decision', source='classifier', result='backchannel')
            return 'backchannel'
        return None


class BargeInController:
    """Bound remote requests to the actual local-stop ACK and provider identity."""
    def __init__(self, adapter, send, observations=None):
        self.observations = observations or BargeObservations()
        self.adapter, self.send = adapter, send
        self.requests = {}

    def _truncate_outcome(self, request, result):
        if request.get('outcome_observed'):
            return
        request['outcome_observed'] = True
        evidence = 'verified' if self.adapter.capability_enabled('supports_context_truncate') else 'unverified'
        self.observations('truncate_outcome', result=result, evidence=evidence)

    async def upgrade(self, reply_id):
        import asyncio
        import time
        if reply_id in self.requests:
            return
        if len(self.requests) >= 4096:
            raise ValueError('barge_in_limit')
        self.requests[reply_id] = {'started': time.monotonic(), 'mode': 'local_stop_requested', 'confirmed': False}
        async def interrupt():
            try:
                async with asyncio.timeout(2):
                    outcome = await self.adapter.interrupt_reply(reply_id)
                self.requests[reply_id]['cancel_mode'] = outcome.mode
            except Exception:
                self.requests[reply_id]['cancel_mode'] = 'local_stop_only'
        async def stop():
            try:
                await self.send('stop_playback', reply_id=reply_id)
            except BaseException:
                self.observations('stop_clear', result='send_failed')
                raise
            else:
                self.observations('stop_clear', result='requested')
        # Stop playback is dispatched before waiting for remote cancellation.
        await asyncio.gather(stop(), interrupt())

    async def stopped(self, reply_id, played_ms):
        import asyncio
        import logging
        import time
        request = self.requests.get(reply_id)
        if request is None or 'played_ms' in request:
            return request['mode'] if request else 'context_not_truncated'
        request['played_ms'] = played_ms
        self.observations('stop_clear', result='acknowledged')
        self.observations.add('stop_clear_latency_ms', {'boundary':'server_request_to_client_ack'},
                              int((time.monotonic()-request['started'])*1000))
        logging.getLogger(__name__).info('voice.barge_in.local_stop_ms=%d',
                                        int((time.monotonic()-request['started'])*1000))
        request['mode'] = 'context_not_truncated'
        if not self.adapter.capability_enabled('supports_context_truncate'):
            self.observations('truncate', result='not_measurable', reason='capability_unavailable')
            self._truncate_outcome(request, 'unknown')
            return request['mode']
        item_id = self.adapter.reply_context_item(reply_id)
        if item_id is None:
            self.observations('truncate', result='not_measurable', reason='identity_unavailable')
            self._truncate_outcome(request, 'unknown')
            return request['mode']
        request['item_id'] = item_id
        request['session_id'] = self.adapter.session_id
        request['mode'] = 'context_truncate_requested'
        try:
            async with asyncio.timeout(2):
                outcome = await self.adapter.truncate_reply_context(reply_id, played_ms, item_id=item_id)
            request['mode'] = outcome.mode
            self.observations('truncate', result='requested' if outcome.mode == 'context_truncate_requested' else 'not_measurable', reason='request' if outcome.mode == 'context_truncate_requested' else 'capability_unavailable')
            if outcome.mode != 'context_truncate_requested':
                self._truncate_outcome(request, 'unknown')
        except Exception:
            request['mode'] = 'context_not_truncated'
            request['confirmed'] = False
            self.observations('truncate', result='failure', reason='request_failed')
            self._truncate_outcome(request, 'failure')
        return request['mode']

    def confirm(self, event):
        if event.kind != 'context_truncated' or not isinstance(event.payload, dict):
            return False
        for request in self.requests.values():
            if (request['mode'] == 'context_truncate_requested'
                    and event.session_id == request.get('session_id')
                    and event.payload.get('item_id') == request.get('item_id')
                    and type(event.payload.get('audio_end_ms')) is int
                    and event.payload['audio_end_ms'] == request.get('played_ms')
                    and self.adapter.capability_enabled('supports_context_truncate')):
                if not request['confirmed']:
                    self.observations('truncate', result='success', reason='confirmed')
                self._truncate_outcome(request, 'success')
                request['confirmed'] = True
                return True
        return False

    def finish_observations(self):
        for request in self.requests.values():
            if request.get('observations_finished'):
                continue
            request['observations_finished'] = True
            self._truncate_outcome(request, 'success' if request['confirmed'] else 'unknown')
            if 'played_ms' not in request:
                self.observations('stop_clear', result='ack_unavailable')
            if request['mode'] == 'context_truncate_requested' and not request['confirmed']:
                self.observations('truncate', result='not_measurable', reason='confirmation_unavailable')

    def confirmed(self, reply_id):
        return self.requests.get(reply_id, {}).get('confirmed', False)
