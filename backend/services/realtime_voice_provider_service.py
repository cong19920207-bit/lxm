"""STEP-007 production protocol boundary.

Only this module sees vendor frames and connection credentials. Payloads remain
in memory; diagnostics contain identifiers and fixed categories only. A sent
control message is never a verified cancellation/truncation acknowledgement.
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import math
from functools import wraps
import os
import time
import zlib
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from uuid import uuid4

import websockets

from backend.constants.realtime_voice_config import VOICE_CAPABILITY_KEYS

MAX_FRAME_BYTES = 1024 * 1024
ADAPTER_VERSION = 'voice_adapter_v1'
PROTOCOL_PROFILE = 'doubao_dialog_v3_pcm'
SDK_VERSION = 'websockets-' + websockets.__version__
ENDPOINT = 'wss://openspeech.bytedance.com/api/v3/realtime/dialogue'
# Public protocol identifier, not an account credential (official event API).
DEFAULT_APP_KEY = 'PlgvMymc7f3tQnJ6'
ADMIN_PLAYBACK_TIMEOUT_SECONDS = 45


class ProviderError(RuntimeError):
    def __init__(self, category: str):
        allowed = {'invalid_config', 'credential_missing', 'authentication_failed',
                   'timeout', 'upstream_unavailable', 'protocol_error', 'evidence_invalid'}
        self.category = category if category in allowed else 'upstream_unavailable'
        super().__init__(self.category)


def encode_frame(event: int, payload: Mapping | bytes, session: str = '') -> bytes:
    audio = isinstance(payload, bytes)
    raw = payload if audio else json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    if len(raw) > MAX_FRAME_BYTES:
        raise ProviderError('protocol_error')
    body = gzip.compress(raw)
    header = bytes([0x11, 0x24 if audio else 0x14, 0x01 if audio else 0x11, 0])
    sid = session.encode()
    session_field = len(sid).to_bytes(4, 'big') + sid if session else b''
    return header + event.to_bytes(4, 'big') + session_field + len(body).to_bytes(4, 'big') + body


def decode_frame(raw: bytes) -> dict:
    """Length-checked, bounded decompression; malformed JSON is never audio."""
    try:
        if not isinstance(raw, bytes) or not 4 <= len(raw) <= MAX_FRAME_BYTES:
            raise ValueError
        if raw[0] >> 4 != 1 or (raw[0] & 15) != 1 or raw[3] != 0:
            raise ValueError
        kind, flags, serial, compression = raw[1] >> 4, raw[1] & 15, raw[2] >> 4, raw[2] & 15
        if kind not in (9, 11, 15) or serial not in (0, 1) or compression not in (0, 1):
            raise ValueError
        pos = 4
        def number():
            nonlocal pos
            if pos + 4 > len(raw):
                raise ValueError
            n = int.from_bytes(raw[pos:pos+4], 'big')
            pos += 4
            return n
        result = {'audio': False, 'session': '', 'event': 0}
        if kind == 15:
            result['error_code'] = number()
        else:
            if flags & 3:
                result['sequence'] = number()
            if not flags & 4:
                raise ValueError
            result['event'] = number()
            size = number()
            if size > 255 or pos + size > len(raw):
                raise ValueError
            result['session'] = raw[pos:pos+size].decode()
            pos += size
        size = number()
        if pos + size != len(raw):
            raise ValueError
        body = raw[pos:]
        if compression:
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            body = decoder.decompress(body, MAX_FRAME_BYTES + 1)
            if len(body) > MAX_FRAME_BYTES or not decoder.eof or decoder.unused_data:
                raise ValueError
        if serial:
            body = json.loads(body)
            if not isinstance(body, dict):
                raise ValueError
        elif kind == 11 and result['event'] == 352:
            result['audio'] = True
        elif kind != 15:
            raise ValueError
        result['payload'] = body
        return result
    except (ValueError, TypeError, IndexError, UnicodeError, zlib.error):
        raise ProviderError('protocol_error') from None


@dataclass(frozen=True)
class ProviderEvent:
    kind: str
    call_id: str
    session_id: str
    sequence: int
    question_id: str | None = None
    reply_id: str | None = None
    payload: Any = field(default=None, repr=False)
    asr_confidence: float | None = None

    def public_metadata(self):
        return {k: getattr(self, k) for k in ('kind', 'call_id', 'session_id', 'sequence', 'question_id', 'reply_id')}


@dataclass(frozen=True)
class CapabilityOutcome:
    mode: str
    confirmed: bool = False


def observe_provider_operation(operation):
    """Observe normalized public-boundary outcomes without changing exceptions."""
    def decorate(function):
        @wraps(function)
        async def run(self,*args,**kwargs):
            def outcome(result):
                if operation=='connect':return [('voice.provider.session',{'operation':'connect','result':result},1)]
                if operation=='start':return [('voice.provider.start',{'result':result},1)]
                return []
            previous_session=self.session_id
            continuing_session=self._metric_session_started
            await self._observe(outcome('attempt'))
            try:
                result=await function(self,*args,**kwargs)
            except asyncio.CancelledError:
                await self._observe(outcome('cancelled'))
                raise
            except Exception as exc:
                await self._observe(outcome('failure')+[
                    ('voice.provider.error',{'reason':self._error_category(exc)},1)])
                raise
            if operation=='start':
                self._metric_session_started=True
                if not continuing_session or self.session_id!=previous_session:
                    self._metric_usage_seen=False
                    self._metric_usage_missing=False
                events=outcome('success')
                for key in VOICE_CAPABILITY_KEYS:
                    enabled=self.capability_enabled(key)
                    events.append(('voice.provider.capability',{'capability':key,
                        'result':'enabled' if enabled else 'not_measurable'},1))
                await self._observe(events)
            else:await self._observe(outcome('success'))
            return result
        return run
    return decorate


def observe_rag_operation(function):
    @wraps(function)
    async def wrapped(self,*args,**kwargs):
        try:
            return await function(self,*args,**kwargs)
        except asyncio.CancelledError:
            if function.__name__=='inject_rag':
                self._recall_count('voice.recall.delivery',{'result':'cancelled'})
            raise
        except Exception:
            if function.__name__=='inject_rag':
                self._recall_count('voice.recall.delivery',{'result':'failure'})
            raise
        finally:
            await self._flush_recall_observations()
    return wrapped


class VoiceProviderAdapter:
    """One call and one immutable runtime config per instance.

    Capability projections must come from VoiceRuntimeBundle.build_snapshot;
    the adapter additionally binds enabled flags to its actual protocol identity.
    No SQL, business turns, memory writes or UI state transitions live here.
    """
    def __init__(self, *, call_id: str, config: Mapping, transport_factory=None,
                 capability_snapshot: Mapping | None = None, purpose: str = 'call',
                 diagnostic_capability: str | None = None, metrics=None):
        if diagnostic_capability is not None and (purpose != 'admin_test' or diagnostic_capability not in VOICE_CAPABILITY_KEYS):
            raise ProviderError('invalid_config')
        self.metrics=metrics
        self._metric_session_started=False
        self._metric_usage_seen=False
        self._metric_usage_missing=False
        self._connection_secret = None
        self._diagnostic_capability = diagnostic_capability
        self.call_id = call_id
        self._config = deepcopy(dict(config))
        self._capabilities = deepcopy(dict(capability_snapshot or {}))
        self._factory = transport_factory or websockets.connect
        self._purpose = purpose
        self.session_id = ''
        self.dialog_id = ''
        self._wire = None
        self._ready = False
        self._events = deque()
        self._lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()
        self._sequence = 0
        self._question = None
        self._reply = None
        self._questions = {}
        self._replies = {}
        self._reply_questions = {}
        self._text_started = set()
        self._rag_questions = set()
        self._rag_reply = {}
        self._metric_rag_replies = set()
        self._metric_rag_primary = {}
        self._metric_rag_questions = set()
        self._metric_rag_overflow = False
        self._recall_observations = {}
        self._finished = set()
        self._preserved_questions = set()
        self._seen = set()
        self._seen_order = deque()
        self._last_vendor_sequence = {}
        self._persona = ''
        self._context = ''
        self._usage = None
        self._generation = 0
        self._connecting = False
        self._audio_reply = None
        self._starting_generation = None
        self._greeting_session = None
        self._greeting_pending = False
        self._control_pending = None

    def _recall_count(self,name,dimensions):
        key=(name,tuple(sorted(dimensions.items())))
        self._recall_observations[key]=self._recall_observations.get(key,0)+1

    def _observe_rag_reply(self, question, reply):
        # IDs stay process-local; one reply can produce many suppressed frames.
        if (self.session_id, question) not in self._metric_rag_questions:
            return
        identity = (self.session_id, question, reply)
        if identity in self._metric_rag_replies:
            return
        if len(self._metric_rag_replies) >= 4096:
            if not self._metric_rag_overflow:
                self._recall_count('voice.recall.reply_observed', {'kind':'overflow','evidence':'unverified'})
                self._metric_rag_overflow = True
            return
        self._metric_rag_replies.add(identity)
        primary = self._metric_rag_primary.setdefault((self.session_id, question), reply)
        verified = self.capability_enabled('supports_current_turn_rag_gate')
        self._recall_count('voice.recall.reply_observed',
                          {'kind':'extra' if reply != primary else 'primary','evidence':'verified' if verified else 'unverified'})

    async def _flush_recall_observations(self):
        events=[(name,dict(dimensions),count) for (name,dimensions),count in self._recall_observations.items()]
        self._recall_observations.clear()
        await self._observe(events)

    async def _observe(self,events):
        if events and self.metrics is not None:await self.metrics.emit_many(events)

    async def _missing_usage(self):
        if self._metric_session_started and not self._metric_usage_seen and not self._metric_usage_missing:
            self._metric_usage_missing=True
            await self._observe([('voice.provider.usage',{'result':'missing'},1)])

    async def _downgrade(self,key):
        await self._observe([('voice.provider.capability',{'capability':key,'result':'downgraded'},1)])

    def __repr__(self):
        return f'VoiceProviderAdapter(call_id={self.call_id!r}, ready={self._ready})'

    @classmethod
    def from_snapshot(cls, *, call_id, snapshot, transport_factory=None, purpose='call'):
        from backend.services.realtime_voice_runtime_config_service import VoiceRuntimeSnapshot
        if not isinstance(snapshot, VoiceRuntimeSnapshot):
            raise ProviderError('invalid_config')
        config_snapshot, capabilities = snapshot.persistence_values()
        return cls(call_id=call_id, config=config_snapshot['resolved_config'],
                   capability_snapshot=capabilities, transport_factory=transport_factory, purpose=purpose)

    def capability_enabled(self, key: str) -> bool:
        c = self._capabilities.get(key, {})
        s2s = self._config['s2s']
        if key not in VOICE_CAPABILITY_KEYS or c.get('enabled') is not True:
            return False
        if c.get('verification_status') == 'failed' or c.get('effective_scope') == 'off':
            return False
        dimensions_match = (c.get('provider_profile') == s2s.get('provider')
                            and c.get('model_version') == s2s.get('model_version')
                            and c.get('protocol_profile') == PROTOCOL_PROFILE
                            and c.get('adapter_version') == ADAPTER_VERSION
                            and c.get('sdk_version') == SDK_VERSION)
        if not dimensions_match:
            return False
        if c.get('verification_status') in ('unverified', 'stale'):
            return (self._purpose == 'admin_test' and c.get('effective_scope') == 'test'
                    and c.get('forced_enabled') is True and bool(c.get('force_source')))
        try:
            expires = datetime.fromisoformat(c['expires_at'].replace('Z', '+00:00'))
            return (c.get('verification_status') == 'verified'
                    and c.get('last_test_result') == 'passed'
                    and c.get('effective_scope') in ('test', 'all')
                    and bool(c.get('evidence_report_id'))
                    and bool(c.get('evidence_fingerprint'))
                    and expires > datetime.now(timezone.utc))
        except (ValueError, KeyError, TypeError):
            return False

    def _operation_allowed(self, key):
        # One short, server-created admin experiment may exercise its selected
        # operation. This never changes capability_enabled or a runtime snapshot.
        return (self._purpose == 'admin_test' and self._diagnostic_capability == key) or self.capability_enabled(key)

    @observe_provider_operation('connect')
    async def create_connection(self, *, secret: str | None = None):
        if self._wire is not None or self._connecting:
            raise ProviderError('protocol_error')
        self._generation += 1
        generation = self._generation
        s = self._config.get('s2s', {})
        if (s.get('endpoint') != ENDPOINT or s.get('provider') != 'doubao'
                or s.get('adapter_version') != ADAPTER_VERSION or s.get('protocol_profile') != PROTOCOL_PROFILE):
            raise ProviderError('invalid_config')
        access = secret if secret is not None else os.getenv(s.get('credential_ref', ''), '')
        app_id = os.getenv('DOUBAO_S2S_APP_ID', '')
        app_key = os.getenv('DOUBAO_S2S_APP_KEY', '').strip() or DEFAULT_APP_KEY
        if not all(isinstance(x, str) and x.strip() for x in (access, app_id, app_key)):
            raise ProviderError('credential_missing')
        self._connecting = True
        try:
            async with asyncio.timeout(s['connect_timeout_ms'] / 1000):
                wire = await self._factory(ENDPOINT, additional_headers={
                    'X-Api-App-ID': app_id, 'X-Api-Access-Key': access,
                    'X-Api-App-Key': app_key, 'X-Api-Resource-Id': s['resource_id'],
                    'X-Api-Connect-Id': str(uuid4()),
                }, max_size=MAX_FRAME_BYTES, max_queue=16, ping_interval=20, ping_timeout=20,
                   open_timeout=s['connect_timeout_ms'] / 1000, close_timeout=3)
                if generation != self._generation:
                    async with asyncio.timeout(3):
                        await wire.close()
                    raise ProviderError('upstream_unavailable')
                self._wire = wire
                await wire.send(encode_frame(1, {}))
                msg = decode_frame(await wire.recv())
                if generation != self._generation or self._wire is not wire:
                    raise ProviderError('upstream_unavailable')
                if msg.get('event') != 50:
                    raise ProviderError('authentication_failed' if msg.get('error_code') else 'protocol_error')
                self._connection_secret = access
        except asyncio.CancelledError:
            await self.finish_session(expected_generation=generation)
            raise
        except Exception as exc:
            category = self._error_category(exc)
            await self.finish_session(expected_generation=generation)
            raise ProviderError(category) from None
        finally:
            self._connecting = False

    @staticmethod
    def _error_category(exc):
        if isinstance(exc, ProviderError):
            return exc.category
        if isinstance(exc, TimeoutError):
            return 'timeout'
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        return 'authentication_failed' if status in (401, 403) else 'upstream_unavailable'

    async def inject_context(self, persona: str, dynamic_context: str):
        if self._ready or not isinstance(persona, str) or not isinstance(dynamic_context, str):
            raise ProviderError('protocol_error')
        if not persona.strip() or len(persona) > 5000 or len(dynamic_context) > 2000:
            raise ProviderError('invalid_config')
        self._persona, self._context = persona, dynamic_context
        return CapabilityOutcome('preamble_staged', True)

    @observe_provider_operation('start')
    async def start_session(self, *, resume_dialog: str | None = None, resume_session: str | None = None):
        if (self._wire is None or self._ready or not self._persona
                or self._starting_generation == self._generation):
            raise ProviderError('protocol_error')
        if resume_session and (not resume_dialog or not self._operation_allowed('supports_session_reconnect')):
            raise ProviderError('evidence_invalid')
        if not resume_session:
            # Vendor question/reply IDs and sequences may restart in a new session.
            # Preserve these guards only when resuming the exact same session.
            for state in (self._questions, self._replies, self._reply_questions,
                          self._text_started, self._rag_questions, self._rag_reply,
                          self._finished, self._preserved_questions, self._seen,
                          self._seen_order, self._last_vendor_sequence,
                          self._metric_rag_questions, self._metric_rag_primary,
                          self._metric_rag_replies):
                state.clear()
            self._metric_rag_overflow = False
            self._events.clear()
            self._question = self._reply = self._audio_reply = None
            self._control_pending = None
            self._sequence = 0
            self._usage = None
        self.session_id = resume_session or str(uuid4())
        generation, wire = self._generation, self._wire
        self._starting_generation = generation
        voice = self._config['voice']
        extra = {'enable_user_query_exit': True, 'input_mod': 'keep_alive', 'model': self._config['s2s']['model_version']}
        if self._operation_allowed('supports_context_truncate'):
            extra['enable_conversation_truncate'] = True
        dialog = {'extra': extra, 'character_manifest': self._persona + '\n' + self._context}
        if resume_dialog:
            if not self._operation_allowed('supports_session_reconnect'):
                raise ProviderError('evidence_invalid')
            dialog['dialog_id'] = resume_dialog
        payload = {'dialog': dialog, 'asr': {'audio_info': {'format': 'pcm', 'sample_rate': 16000, 'channel': 1}},
                   'tts': {'speaker': voice['voice_id'], 'audio_config': {'format': 'pcm_s16le', 'sample_rate': 24000,
                           'channel': 1, 'bits': 16, 'speech_rate': voice['speech_rate'], 'loudness_rate': voice['loudness_rate']}}}
        if voice.get('expressive'):
            payload['tts']['extra'] = {'tts_2.0_model': 'expressive'}
        try:
            async with asyncio.timeout(self._config['s2s']['start_session_timeout_ms'] / 1000):
                await self._send(100, payload, require_ready=False)
                msg = decode_frame(await wire.recv())
                if generation != self._generation or self._wire is not wire:
                    raise ProviderError('upstream_unavailable')
                if msg['event'] != 150 or msg['session'] != self.session_id:
                    raise ProviderError('protocol_error')
                self.dialog_id = str(msg['payload'].get('dialog_id', ''))
                self._ready = True
                self._events.append(self._event('session_ready'))
        except asyncio.CancelledError:
            await self.finish_session(expected_generation=generation)
            raise
        except Exception as exc:
            category = self._error_category(exc)
            await self.finish_session(expected_generation=generation)
            raise ProviderError(category) from None
        finally:
            if self._starting_generation == generation:
                self._starting_generation = None
        return self.session_id

    def _event(self, kind, payload=None, question=None, reply=None, asr_confidence=None):
        self._sequence += 1
        return ProviderEvent(kind, self.call_id, self.session_id, self._sequence, question, reply, payload, asr_confidence)

    async def _send(self, event, payload, *, require_ready=True, send_if=None):
        generation = self._generation
        async with self._lock:
            if generation != self._generation or self._wire is None or (require_ready and not self._ready):
                raise ProviderError('upstream_unavailable')
            if send_if is not None and not send_if():
                return False
            try:
                await self._wire.send(encode_frame(event, payload, self.session_id))
                return True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise ProviderError(self._error_category(exc)) from None

    async def control_query(self, content: str, *, kind: str, token: str):
        """Official 501/553. A server control query is never an ASR final.

        Source: https://docs.volcengine.com/docs/6561/1594356
        The returned outcome confirms submission only, not model compliance.
        """
        if (kind not in {'time_low', 'silence_confirm', 'goodbye'}
                or not isinstance(content, str) or not content.strip() or len(content) > 2000
                or not isinstance(token, str) or not token or len(token) > 64):
            raise ProviderError('protocol_error')
        def claim():
            if self._control_pending is not None:
                return False
            self._control_pending = (kind, token, self._question)
            return True
        try:
            sent = await self._send(501, {'content': content}, send_if=claim)
        except BaseException:
            self._control_pending = None
            raise
        return CapabilityOutcome('control_requested' if sent else 'control_pending')

    async def say_hello(self, content: str):
        """Official event 300; submission does not prove device playback."""
        if not isinstance(content, str) or not content.strip() or len(content) > 200:
            raise ProviderError('protocol_error')
        def claim_session():
            if self._greeting_session == self.session_id:
                return False
            self._greeting_session = self.session_id
            self._greeting_pending = True
            return True
        sent = await self._send(300, {'content': content}, send_if=claim_session)
        return CapabilityOutcome('greeting_requested' if sent else 'greeting_already_requested')

    def preserve_playing_question(self, question_id):
        if question_id in self._questions.values():
            self._preserved_questions.add(question_id)

    async def delete_backchannel(self, question_id):
        raw = next((raw for raw, local in self._questions.items() if local == question_id), None)
        sid = self.session_id
        if raw is None or not any(q == question_id and r in self._finished for r,q in self._reply_questions.items()):
            raise ProviderError('evidence_invalid')
        sent = await self._send(514, {'items': [{'item_id': raw}]},
                         send_if=lambda: self.session_id == sid and self._questions.get(raw) == question_id)
        if not sent:
            raise ProviderError('evidence_invalid')

    async def send_audio(self, pcm: bytes):
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2 or len(pcm) > 32000:
            raise ProviderError('protocol_error')
        await self._send(200, pcm)

    def _normalize(self, msg):
        if msg.get('error_code') or msg['event'] in (51, 153, 599):
            raise ProviderError('upstream_unavailable')
        if msg['session'] != self.session_id:
            return None
        event, payload = msg['event'], msg['payload']
        if msg['audio']:
            if self._audio_reply is None or self._audio_reply in self._finished:
                return None
            return self._event('tts_audio', payload, self._reply_questions[self._audio_reply], self._audio_reply)
        qid, rid = payload.get('question_id'), payload.get('reply_id')
        if qid is not None and (not isinstance(qid, str) or not qid or len(qid) > 255):
            raise ProviderError('protocol_error')
        if rid is not None and (not isinstance(rid, str) or not rid or len(rid) > 255):
            raise ProviderError('protocol_error')
        seq = payload.get('sequence', msg.get('sequence'))
        if seq is not None:
            if type(seq) is not int or seq < 0:
                raise ProviderError('protocol_error')
            key = (event, qid, rid)
            if seq <= self._last_vendor_sequence.get(key, -1):
                return None
            self._last_vendor_sequence[key] = seq
        # Deduplicate semantic boundaries only; equal text/audio chunks may be real.
        if event in (150, 152, 351, 359, 459, 559, 567, 570):
            # ASREnded is an empty payload; identical bodies from different
            # questions are distinct boundaries in the official protocol.
            identity = self._question if event == 459 else None
            digest = hashlib.sha256(json.dumps([event, payload, identity], sort_keys=True).encode()).digest()
            if digest in self._seen:
                return None
            self._seen.add(digest)
            self._seen_order.append(digest)
            if len(self._seen_order) > 4096:
                self._seen.discard(self._seen_order.popleft())
        if event == 553:
            pending, self._control_pending = self._control_pending, None
            if not qid or pending is None or pending[2] != self._question:
                return None
            self._question = self._questions.setdefault(qid, str(uuid4()))
            return self._event('control_confirmed', {'control_kind': pending[0],
                               'control_token': pending[1]}, question=self._question)
        if event in (450, 451, 459):
            if event == 450:
                if not qid:
                    return None
                self._greeting_pending = False
                self._question = self._questions.setdefault(qid, str(uuid4()))
                return self._event('user_speech_started', question=self._question)
            if self._question is None or (qid and self._questions.get(qid) != self._question):
                return None
            if event == 451:
                results = payload.get('results', [])
                if not results or not isinstance(results[-1], dict):
                    raise ProviderError('protocol_error')
                result = results[-1]
                confidence = result.get('confidence')
                if confidence is not None:
                    import math
                    if type(confidence) not in {int,float} or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                        raise ProviderError('protocol_error')
                return self._event('asr_interim' if result.get('is_interim') is True else 'asr_final',
                                   result.get('text', ''), self._question, asr_confidence=confidence)
            return self._event('user_speech_finished', question=self._question)
        if event in (350, 351, 359, 550, 559):
            # SayHello has no preceding ASR; bind only the first genuine
            # sentence identity following our explicit request in this session.
            if event == 350 and qid and rid and self._greeting_pending and self._question is None:
                self._question = self._questions.setdefault(qid, str(uuid4()))
                self._greeting_pending = False
            known_reply = self._replies.get(rid)
            question = self._questions.get(qid) if qid else self._reply_questions.get(known_reply)
            if question is None or (question != self._question and question not in self._preserved_questions) or not rid:
                # No guessing that unbound text belongs to the newest question.
                return None
            if self._purpose == 'call' and question in self._rag_questions:
                # A sent 502 can race the default response. Keep the first
                # observed reply only; this is an output guard, NOT evidence
                # that it contains RAG or that upstream generated only once.
                selected = self._rag_reply.get(question)
                if selected is None:
                    if event != 350 and not (event == 550 and payload.get('content', payload.get('text', ''))):
                        return None
                    selected = self._rag_reply[question] = rid
                self._observe_rag_reply(question, rid)
                if selected != rid:
                    self._recall_count('voice.recall.double_reply',{'result':'detected','unit':'frame'})
                    self._recall_count('voice.recall.double_reply',{'result':'prevented','unit':'frame'})
                    if event == 350:
                        self._audio_reply = None
                    return None
            reply = self._replies.setdefault(rid, str(uuid4()))
            known_question = self._reply_questions.setdefault(reply, question)
            if known_question != question or reply in self._finished:
                return None
            self._reply = reply
            if event == 350:
                self._audio_reply = reply
            kind = {350: 'sentence_started', 351: 'sentence_finished', 359: 'tts_finished',
                    550: 'chat_text', 559: 'text_finished'}[event]
            if event in (350, 550):
                self._text_started.add(question)
            if event == 359:
                self._finished.add(reply)
            data = payload.get('content', payload.get('text', '')) if event == 550 else {
                k: payload[k] for k in ('sentence_id', 'start_time', 'end_time', 'text') if k in payload}
            if event == 359 and 'status_code' in payload:
                data['status_code'] = payload['status_code']
            return self._event(kind, data, question, reply)
        if event == 154:
            self._usage = {k: v for k, v in payload.items() if k in ('input_tokens', 'output_tokens', 'audio_duration') and type(v) in (int, float) and v >= 0}
            return self._event('usage', self._usage)
        if event == 152:
            self._ready = False
            return self._event('session_finished')
        if event == 571:
            ids = {item.get('item_id') for item in payload.get('items', []) if isinstance(item, dict)}
            questions = {local for raw, local in self._questions.items() if raw in ids}
            questions.update(self._reply_questions[local] for raw, local in self._replies.items()
                             if raw in ids and local in self._reply_questions)
            return self._event('context_deleted', {'question_ids': sorted(questions)})
        if event in (567, 570):
            return self._event('context_created' if event == 567 else 'context_truncated', {
                k: payload[k] for k in ('item_id', 'audio_end_ms') if k in payload})
        return None

    @observe_rag_operation
    @observe_provider_operation('receive')
    async def receive_event(self):
        async with self._read_lock:
            if self._events:
                return self._events.popleft()
            while self._wire is not None:
                try:
                    wire, generation = self._wire, self._generation
                    msg = decode_frame(await wire.recv())
                    if wire is not self._wire or generation != self._generation:
                        raise ProviderError('upstream_unavailable')
                    if msg.get('event')==154 and msg.get('session')==self.session_id:
                        payload=msg.get('payload',{})
                        values=[value for key,value in payload.items() if key in ('input_tokens','output_tokens','audio_duration')]
                        valid=bool(values) and all(type(value) in (int,float) and math.isfinite(value) and value>=0 for value in values)
                        status='invalid' if not valid else 'received' if self._ready else 'late'
                        if valid:self._metric_usage_seen=True
                        await self._observe([('voice.provider.usage',{'result':status},1)])
                    event = self._normalize(msg)
                    if event is not None and event.kind=='session_finished':await self._missing_usage()
                    if event is not None:
                        return event
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    raise ProviderError(self._error_category(exc)) from None
            raise ProviderError('upstream_unavailable')

    async def _receive_kind(self, kind):
        event = await self.receive_event()
        if event.kind != kind:
            # Consumers needing mixed streams use receive_event, never drop events.
            self._events.appendleft(event)
            raise ProviderError('protocol_error')
        return event

    async def receive_asr_interim(self):
        return await self._receive_kind('asr_interim')

    async def receive_asr_final(self):
        return await self._receive_kind('asr_final')

    async def receive_chat_text(self):
        return await self._receive_kind('chat_text')

    async def receive_tts_audio(self):
        return await self._receive_kind('tts_audio')

    def _target(self, reply_id):
        if reply_id != self._reply or reply_id in self._finished:
            raise ProviderError('protocol_error')
        return True

    def reply_context_item(self, reply_id):
        """Internal provider identity for a known reply; never projected to H5."""
        return next((item for item, mapped in self._replies.items() if mapped == reply_id), None)

    async def interrupt_reply(self, reply_id):
        self._target(reply_id)
        if not self._operation_allowed('supports_reply_cancel'):
            await self._downgrade('supports_reply_cancel')
            return CapabilityOutcome('local_stop_only')
        await self._send(515, {}, send_if=lambda: self._target(reply_id))
        return CapabilityOutcome('remote_cancel_requested')

    async def truncate_reply_context(self, reply_id, audio_end_ms, *, item_id=None):
        def target_current():
            if self._purpose=='admin_test' and self._diagnostic_capability=='supports_context_truncate':
                if reply_id!=self._reply or self._replies.get(item_id)!=reply_id:raise ProviderError('evidence_invalid')
                return True
            return self._target(reply_id)
        target_current()
        if not self._operation_allowed('supports_context_truncate'):
            await self._downgrade('supports_context_truncate')
            return CapabilityOutcome('context_not_truncated')
        if type(audio_end_ms) is not int or audio_end_ms < 0 or not isinstance(item_id, str) or not item_id:
            raise ProviderError('protocol_error')
        await self._send(513, {'item_id': item_id, 'audio_end_ms': audio_end_ms}, send_if=target_current)
        return CapabilityOutcome('context_truncate_requested')

    @observe_rag_operation
    async def inject_rag(self, question_id, content):
        if question_id != self._question:
            self._recall_count('voice.recall.late',{'reason':'stale_question'})
        if question_id != self._question or not isinstance(content, str) or len(content) > 2000:
            raise ProviderError('protocol_error')
        if question_id in self._text_started:self._recall_count('voice.recall.late',{'reason':'text_started'})
        if question_id in self._rag_questions:self._recall_count('voice.recall.double_reply',{'result':'prevented','unit':'injection'})
        if not self._operation_allowed('supports_current_turn_rag_gate'):
            self._recall_count('voice.recall.not_measurable',{'reason':'current_turn_capability'})
        if (not self._operation_allowed('supports_current_turn_rag_gate') or question_id in self._text_started
                or question_id in self._rag_questions):
            if not self._operation_allowed('supports_current_turn_rag_gate'):
                await self._downgrade('supports_current_turn_rag_gate')
            self._recall_count('voice.recall.delivery',{'result':'next_turn'})
            return CapabilityOutcome('next_turn')
        def claim():
            if question_id != self._question or question_id in self._text_started or question_id in self._rag_questions:
                if question_id!=self._question:self._recall_count('voice.recall.late',{'reason':'stale_question'})
                elif question_id in self._text_started:self._recall_count('voice.recall.late',{'reason':'text_started'})
                else:self._recall_count('voice.recall.double_reply',{'result':'prevented','unit':'injection'})
                return False
            self._rag_questions.add(question_id)
            if len(self._metric_rag_questions) < 4096:
                self._metric_rag_questions.add((self.session_id, question_id))
            elif not self._metric_rag_overflow:
                self._recall_count('voice.recall.reply_observed', {'kind':'overflow','evidence':'unverified'})
                self._metric_rag_overflow = True
            return True
        sent = await self._send(502, {'external_rag': json.dumps([{'title': 'context', 'content': content}], ensure_ascii=False)},
                                send_if=claim)
        self._recall_count('voice.recall.delivery',{'result':'current_turn_requested' if sent else 'next_turn'})
        return CapabilityOutcome('current_turn_requested' if sent else 'next_turn')

    async def reconnect_session(self):
        old_dialog, old_session = self.dialog_id, self.session_id
        connection_secret = self._connection_secret
        reuse = self._operation_allowed('supports_session_reconnect') and bool(old_dialog)
        if reuse:
            # A transport loss must not send FinishSession before restoration.
            async with self._lock:
                wire, self._wire = self._wire, None
                self._ready = False
                self._generation += 1
                if wire is not None:
                    async with asyncio.timeout(3):await wire.close()
        else:
            await self._downgrade('supports_session_reconnect')
            await self.finish_session()
        self._events.clear()
        self._preserved_questions.clear()
        self._sequence = 0
        self._control_pending = None
        self._question = self._reply = None
        self._audio_reply = None
        await self.create_connection(secret=connection_secret)
        await self.start_session(resume_dialog=old_dialog if reuse else None, resume_session=old_session if reuse else None)
        if reuse and self.dialog_id != old_dialog:
            await self.finish_session()
            raise ProviderError('evidence_invalid')
        return CapabilityOutcome('same_dialog' if reuse else 'new_session_with_preamble', True)

    def get_usage(self):
        return deepcopy(self._usage)  # None is unknown; never fabricate zero usage.

    @observe_rag_operation
    async def finish_session(self, *, expected_generation=None):
        async with self._lock:
            if expected_generation is not None and expected_generation != self._generation:
                return
            self._connection_secret = None
            wire, self._wire = self._wire, None
            self._generation += 1
            self._greeting_pending = False
            self._control_pending = None
            ready, self._ready = self._ready, False
            if wire is None:
                return
            finish_result="success"
            try:
                async with asyncio.timeout(3):
                    if ready:
                        await wire.send(encode_frame(102, {}, self.session_id))
                    await wire.send(encode_frame(2, {}))
            except Exception:
                finish_result="failure"
            finally:
                try:
                    async with asyncio.timeout(3):
                        await wire.close()
                except Exception:
                    finish_result="failure"

            await self._missing_usage()
            self._metric_session_started=False
            await self._observe([('voice.provider.session',{'operation':'finish','result':finish_result},1)])


class AdminPlaybackTarget(Protocol):
    """Request-owned trusted playback transport; never accepts caller JSON as ACK.

    The integration owns authenticating its target and observing device playback.
    Merely receiving or buffering PCM must not complete wait_played.
    """
    async def write_audio(self, event: ProviderEvent) -> None: ...

    async def wait_played(self, *, call_id: str, session_id: str,
                          reply_id: str, audio_bytes: int) -> Mapping: ...

    async def aclose(self) -> None: ...


class ProviderAdminTestRunner:
    """Request-local adapter; capability probes must supply genuine evidence.

    A connection handshake cannot stand in for a browser playback ACK or a
    capability test. Without a real probe, fail explicitly without networking.
    """
    def __init__(self, *, transport_factory=None, capability_probe=None,
                 playback_target: AdminPlaybackTarget | None = None):
        self._factory = transport_factory
        self._probe = capability_probe
        if capability_probe is not None and hasattr(capability_probe, 'transport_factory'):
            self._factory = capability_probe.transport_factory(transport_factory)
        self._adapter = None
        self._playback_target = playback_target

    async def run_playback(self, *, draft_snapshot, secret):
        """Internal playback diagnostic, separate from capability evidence.

        Requires a bound target before networking. Never manufactures a six-
        capability report or changes evidence/configuration. Caller microphone
        input is neither requested nor sent in this path.
        """
        start = time.monotonic()
        if self._playback_target is None:
            return self._result('error', 'evidence_invalid', start)
        try:
            async with asyncio.timeout(ADMIN_PLAYBACK_TIMEOUT_SECONDS):
                adapter = await self._connect(draft_snapshot, secret)
                await adapter.say_hello('管理端播放测试完成。')
                reply_id, audio_bytes = None, 0
                while True:
                    event = await adapter.receive_event()
                    if event.kind == 'tts_audio':
                        if not isinstance(event.payload, bytes) or not event.reply_id:
                            raise ProviderError('protocol_error')
                        if reply_id is not None and reply_id != event.reply_id:
                            raise ProviderError('evidence_invalid')
                        reply_id = event.reply_id
                        audio_bytes += len(event.payload)
                        await self._playback_target.write_audio(event)
                    elif event.kind == 'tts_finished':
                        if not audio_bytes or event.reply_id != reply_id:
                            raise ProviderError('evidence_invalid')
                        break
                expected = dict(call_id=adapter.call_id, session_id=adapter.session_id,
                                reply_id=reply_id, audio_bytes=audio_bytes)
                ack = await self._playback_target.wait_played(**expected)
                if (not isinstance(ack, Mapping) or set(ack) != set(expected)
                        or type(ack.get('audio_bytes')) is not int
                        or any(ack.get(k) != v for k, v in expected.items())):
                    raise ProviderError('evidence_invalid')
                result = {**self._result('passed', 'none', start),
                          'diagnostic': {'kind': 'admin_playback', **expected}}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            result = self._result('error', VoiceProviderAdapter._error_category(exc), start)
        finally:
            try:
                await self.aclose()
            finally:
                try:
                    async with asyncio.timeout(3):
                        await self._playback_target.aclose()
                except Exception:
                    result = self._result('error', 'upstream_unavailable', start)
        return result

    async def _connect(self, draft_snapshot, secret, diagnostic_capability=None):
        self._adapter = VoiceProviderAdapter(call_id=str(uuid4()), config=draft_snapshot,
            transport_factory=self._factory, purpose='admin_test', diagnostic_capability=diagnostic_capability)
        await self._adapter.inject_context('管理端连接测试', '')
        await self._adapter.create_connection(secret=secret)
        await self._adapter.start_session()
        return self._adapter

    async def run_connection(self, *, draft_snapshot, secret):
        start = time.monotonic()
        try:
            await self._connect(draft_snapshot, secret)
            return self._result('passed', 'none', start)
        except ProviderError as exc:
            return self._result('error', exc.category, start)

    @staticmethod
    def _result(status, category, start):
        return {'status': status, 'failure_category': category,
                'latency_ms': max(0, int((time.monotonic() - start) * 1000)),
                'tested_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}

    async def run_capability(self, *, capability_key, draft_snapshot, secret):
        start = time.monotonic()
        if capability_key not in VOICE_CAPABILITY_KEYS or self._probe is None:
            return self._result('error', 'evidence_invalid', start)
        try:
            adapter = await self._connect(draft_snapshot, secret, diagnostic_capability=capability_key)
            return await self._probe(adapter=adapter, capability_key=capability_key,
                                     draft_snapshot=deepcopy(draft_snapshot))
        except ProviderError as exc:
            if hasattr(self._probe, 'failure_result'):
                return self._probe.failure_result(draft_snapshot, capability_key, exc.category)
            return self._result('error', exc.category, start)

    async def aclose(self):
        try:
            if self._adapter is not None:
                await self._adapter.finish_session()
        finally:
            self._adapter = None
            if hasattr(self._probe, 'aclose'):
                await self._probe.aclose()
