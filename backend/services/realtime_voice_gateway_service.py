"""M2 authenticated socket transport and establishment; no M3 turn persistence."""
from backend.services.realtime_voice_metric_service import VoiceMetrics, flush_voice_metrics, defer_voice_metrics
import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import time
from functools import wraps
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

from sqlalchemy import select, update

from backend.models.realtime_voice import VoiceCall
from backend.models.user import User
from backend.services.realtime_voice_context_source_service import prepare_voice_context
from backend.services.realtime_voice_decision_service import call_decision_inputs, decide_call, RingGate, transition_call, ring_timing
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_provider_service import VoiceProviderAdapter, ProviderError, ENDPOINT, ADAPTER_VERSION, PROTOCOL_PROFILE
from backend.services.realtime_voice_quota_service import ConnectedMeter, VoiceQuotaService
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec, TicketError, consume_voice_ticket
from backend.services.realtime_voice_turn_service import VoiceTurnService
from backend.services.realtime_voice_barge_in_service import BargeInClassifier, BargeInController, BargeObservations, observe_barge_in
from backend.services.realtime_voice_ending_service import EndingPolicy, ClosingSemanticGate, ClosingOutputBuffer, observe_ending
from backend.services.realtime_voice_prompt_templates import build_control_prompt
from backend.services.realtime_voice_reconnect_service import ReconnectCoordinator
from backend.constants.realtime_voice_config import VOICE_INTERACTION_DEFAULTS
from backend.services.realtime_voice_playback_service import PlaybackEvidence, CLIENT_FIELDS, observe_playback

logger = logging.getLogger(__name__)


def defer_warmup_metrics(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        events = []
        try:
            with defer_voice_metrics(events):
                return await method(self, *args, **kwargs)
        finally:
            self._warmup_metrics.extend(events)
    return wrapped


def ticket_codec_from_environment(*, reconnect=False):
    from backend.config import get_jwt_secret
    secret = get_jwt_secret()
    if secret == 'lxm-default-jwt-secret-change-in-production' or len(secret) < 32:
        raise TicketError('ticket_signing_key_unavailable')
    # Purpose-separated child key; existing auth behavior/key remains unchanged.
    purpose = b'lxm:voice:reconnect-ticket:v1' if reconnect else b'lxm:voice:call-ticket:v1'
    return VoiceTicketCodec(hmac.digest(secret.encode(), purpose, 'sha256'),
                            purpose='voice_reconnect_v1' if reconnect else 'voice_call_v1')


async def provider_preflight(config):
    s = config['s2s']
    return (s['endpoint'] == ENDPOINT and s['adapter_version'] == ADAPTER_VERSION
            and s['protocol_profile'] == PROTOCOL_PROFILE
            and all(bool(os.getenv(key, '').strip()) for key in
                    (s['credential_ref'], 'DOUBAO_S2S_APP_ID')))


def _voice_origin(value):
    """Origin 只包含协议、主机和有效端口，拒绝路径、凭据及歧义字符。"""
    try:
        if not value or any(ord(char) <= 32 or char in '\\,?#%' for char in value):
            raise ValueError()
        parsed = urlsplit(value)
        host = parsed.hostname
        if (parsed.scheme not in ('http', 'https') or not host or parsed.path
                or parsed.username is not None or parsed.password is not None
                or parsed.netloc.endswith(':')):
            raise ValueError()
        if ':' in host:
            host = ipaddress.IPv6Address(host).compressed
        elif not re.fullmatch(r'[a-z0-9.-]+', host):
            raise ValueError()
        port = parsed.port
        if port == 0:
            raise ValueError()
        return parsed.scheme, host, port if port is not None else (443 if parsed.scheme == 'https' else 80)
    except (ValueError, TypeError):
        raise TicketError('socket_origin_or_url_rejected') from None


def socket_credentials(socket, allowed_origins, allow_local_http=False):
    origin = socket.headers.get('origin')
    if socket.url.query:
        raise TicketError('socket_origin_or_url_rejected')
    if hasattr(socket.headers, 'getlist') and any(len(socket.headers.getlist(key)) != 1 for key in ('origin', 'host')):
        raise TicketError('socket_origin_or_url_rejected')
    source = _voice_origin(origin)
    # 显式白名单保持原有严格限制；未配置时复用当前站点，避免重复维护部署域名。
    target = None
    if allowed_origins:
        if origin not in allowed_origins:
            raise TicketError('socket_origin_or_url_rejected')
    else:
        scheme = 'https' if socket.url.scheme == 'wss' else 'http'
        target = _voice_origin(scheme + '://' + (socket.headers.get('host') or ''))
        if source != target:
            raise TicketError('socket_origin_or_url_rejected')
    if socket.url.scheme != 'wss':
        try:
            peer = ipaddress.ip_address(socket.client.host)
            local_peer = peer.is_loopback or any(peer in ipaddress.ip_network(network) for network in
                ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7'))
        except (ValueError, AttributeError):
            local_peer = False
        # 仅显式开发模式允许 Docker 内网转发；本地覆盖配置必须把入口绑定到回环地址。
        # 不读取原始 Forwarded 头；线上 WSS 识别由受信任的 ASGI 代理配置负责。
        target = target or _voice_origin('http://' + (socket.headers.get('host') or ''))
        loopback_hosts = ('localhost', '127.0.0.1', '::1')
        if (socket.url.scheme != 'ws' or not allow_local_http or not local_peer
                or source[0] != 'http' or source[1] not in loopback_hosts or target[1] not in loopback_hosts):
            raise TicketError('wss_required')
    header = socket.headers.get('sec-websocket-protocol', '')
    parts = [p.strip() for p in header.split(',')]
    if len(header) > 4096 or len(parts) != 3 or parts[0] != 'voice.v1' or not parts[1].startswith('ticket.') or not parts[2].startswith('device.'):
        raise TicketError('socket_protocol_invalid')
    return parts[1][7:], parts[2][7:]


class VoiceFrameGuard:
    def __init__(self):
        self.sequence = 0
        self.window = time.monotonic()
        self.count = 0

    def parse(self, raw):
        if not isinstance(raw, str) or len(raw.encode()) > 12000:
            raise TicketError('frame_too_large')
        now = time.monotonic()
        if now-self.window >= 1:
            self.window, self.count = now, 0
        self.count += 1
        if self.count > 60:
            raise TicketError('frame_rate_exceeded')
        try:
            frame = json.loads(raw)
            if (not isinstance(frame, dict) or type(frame.get('v')) is not int or frame['v'] != 1
                    or type(frame.get('seq')) is not int or frame['seq'] != self.sequence+1
                    or frame.get('type') not in ('heartbeat','cancel','audio','microphone_state',*CLIENT_FIELDS)):
                raise ValueError()
            keys = {'v','seq','type','pcm_base64'} if frame['type'] == 'audio' else {'v','seq','type'}
            if frame['type'] == 'microphone_state':
                keys |= {'muted', 'available'}
                if type(frame.get('muted')) is not bool or type(frame.get('available')) is not bool:
                    raise ValueError()
            if frame['type'] in CLIENT_FIELDS:
                keys |= {'call_id','reply_id','event_seq'} | CLIENT_FIELDS[frame['type']]
            if set(frame) != keys:
                raise ValueError()
            if frame['type'] == 'audio':
                pcm = base64.b64decode(frame['pcm_base64'], validate=True)
                if not pcm or len(pcm) > 6400 or len(pcm)%2:
                    raise ValueError()
                frame['pcm'] = pcm
            self.sequence = frame['seq']
            return frame
        except (ValueError, TypeError, KeyError):
            raise TicketError('frame_invalid') from None


class VoiceGatewaySession:
    def __init__(self, *, socket, call, cache, session_factory, adapter_factory=VoiceProviderAdapter, context_builder=prepare_voice_context, decision_model=None, turn_gate=None, semantic_gate=None, device_id=None, reconnect_codec=None):
        self.socket, self.call, self.cache, self.factory = socket, call, cache, session_factory
        self.user_id, self.call_id, self.device_id = call.user_id, call.call_id, device_id
        self.metrics=VoiceMetrics(cache)
        self._warmup_metrics = []
        self.adapter_factory = adapter_factory
        self.closed_event = asyncio.Event()
        self.config = call.config_snapshot['resolved_config']
        self.script = call.config_snapshot['resolved_script']
        self.adapter = adapter_factory(call_id=call.call_id, config=self.config, capability_snapshot=call.capability_snapshot)
        if isinstance(self.adapter,VoiceProviderAdapter):self.adapter.metrics=VoiceMetrics(cache)
        self.context_builder, self.decision_model = context_builder, decision_model
        from backend.services.realtime_voice_session_context_service import VoiceSessionContext
        self.session_context = VoiceSessionContext(cache=cache, session_factory=session_factory)
        from backend.services.realtime_voice_memory_service import VoiceMemoryService
        self.memory_job_writer = VoiceMemoryService.stage_job
        self.turn_gate, self.turns, self.playback = turn_gate, None, None
        if self.turn_gate is None:
            from backend.services.realtime_voice_safety_service import VoiceSafetyGate
            from backend.services.realtime_voice_crisis_service import VoiceCrisisGate
            from backend.services.realtime_voice_runtime_config_service import RealtimeVoiceRuntimeConfigService
            async def redis_provider():
                return self.cache
            async def notify_crisis(signal):
                await self.send(signal['type'], call_id=signal['call_id'],
                    banner=self.script['crisis']['in_call_banner'])
            self.turn_gate = VoiceSafetyGate(cache=self.cache, crisis_gate=VoiceCrisisGate(
                loader=RealtimeVoiceRuntimeConfigService(redis_provider=redis_provider), notify=notify_crisis))
        self.barge_observations = BargeObservations()
        self.barge_in = BargeInClassifier({**VOICE_INTERACTION_DEFAULTS, **self.config.get('interaction', {})}, self.script['barge_in'], observations=self.barge_observations)
        self.recall = self._build_recall()
        self.interruptions = BargeInController(self.adapter, self.send, observations=self.barge_observations)
        from backend.services.realtime_voice_backchannel_service import BackchannelFilter
        self.backchannels = BackchannelFilter(self.script['barge_in'], self._accepted_provider_event,
                                              self._discard_backchannel_event, self._delete_backchannel, observations=self.barge_observations)
        self.ending = None
        async def disclosure_guard(data):
            if not hasattr(self.turn_gate, 'permits_generated'):
                return False
            for value in data.values():
                if not await self.turn_gate.permits_generated(call_id=self.call_id, text=value):
                    return False
            return True
        self.semantic_gate = semantic_gate or ClosingSemanticGate(disclosure_guard=disclosure_guard)
        self.closing_output = ClosingOutputBuffer(self.semantic_gate)
        self.waiting_user = True
        self.mic_available, self.mic_muted = True, False
        self.latest_user, self.closing_topic = '', ''
        self.native_question = None
        self.silence_fallback_generation = None
        self.fixed_goodbye_questions = {}
        self.control_tokens, self.control_questions = {}, {}
        self.last_clock_emit = 0
        self.ingested_sequences = {}
        self.ops = VoiceOpsService(cache=cache, session_factory=session_factory)
        self.leases = VoiceLeaseService(cache, end_call=self.request_end)
        self.meter = ConnectedMeter(call.call_id, call.user_id, self.config['quota']['daily_free_seconds'], self.config['quota']['grace_seconds'])
        self.quota = VoiceQuotaService(metrics=VoiceMetrics(cache))
        self.cancel = asyncio.Event()
        self.stopped = False
        self.connected = False
        self.user_cancelled = False
        self.end_reason = 'system_error'
        self.last_client_heartbeat = time.monotonic()
        self.sequence = 0
        self.reconnector = (ReconnectCoordinator(self, timeout_ms=self.config['concurrency']['reconnect_timeout_ms'],
            codec=reconnect_codec or ticket_codec_from_environment(reconnect=True)) if device_id else None)
        self.send_lock, self.meter_lock, self.stop_lock = asyncio.Lock(), asyncio.Lock(), asyncio.Lock()

    def _build_recall(self):
        from backend.services.realtime_voice_recall_service import VoiceRecallCoordinator, VoiceRecallService
        return VoiceRecallCoordinator(call_id=self.call_id,user_id=self.user_id,session_factory=self.factory,
            service=VoiceRecallService(session_context=self.session_context,gate=self.turn_gate,metrics=self.metrics),
            adapter=self.adapter,script=self.script['recall'])

    async def request_end(self, **kwargs):
        # The run owner alone settles; a child must not be cancelled mid-commit
        # merely because closing its socket makes the receiver finish first.
        self.end_reason = kwargs.get('reason', 'system_error')
        await self.stop_local()

    async def send(self, kind, **data):
        async with self.send_lock:
            if self.reconnector and self.reconnector.active and self.reconnector.need_socket:
                raise ConnectionError('voice_transport_detached')
            self.sequence += 1
            try:
                async with asyncio.timeout(3):
                    await self.socket.send_json(dict(v=1, seq=self.sequence, type=kind, **data))
            except Exception:
                raise ConnectionError('voice_transport_lost') from None

    async def observe(self, connected):
        async with self.meter_lock:
            async with self.factory() as db:
                return await self.quota.observe(db, self.meter, connected=connected,
                                                monotonic=time.monotonic(), now=datetime.now(timezone.utc), muted=self.mic_muted)

    @observe_playback
    @observe_barge_in
    async def stop_local(self):
        async with self.stop_lock:
            if self.stopped:
                return
            self.stopped = True
            self.interruptions.finish_observations()
            await self.recall.close()
            await self.backchannels.close()
            if self.reconnector:
                self.reconnector.cancel()
            self.connected = False
            self.cancel.set()
            if self.turns is not None:
                try:
                    if self.playback is not None:
                        for reply_id in self.playback.replies:
                            await self.turns.apply_effective(reply_id,self.playback.snapshot(reply_id))
                except Exception:
                    # An external worker may already have committed the end;
                    # persistence failure cannot prevent local audio stop.
                    # Still-pending proofs retry in the finalizer transaction.
                    logger.info('voice.turn.final_flush_pending=1')
                finally:
                    await self.turns.freeze()
                    if self.playback is not None:
                        for reply_id in self.playback.replies:
                            self.playback.release_text(reply_id)
            self.latest_user = self.closing_topic = ''
            # Observe the stop instant before awaiting transport cleanup.
            try:
                await self.observe(False)
            finally:
                try:
                    async with asyncio.timeout(1):
                        await self.socket.close(code=1000)
                except Exception:
                    pass
                try:
                    async with asyncio.timeout(3):
                        await self.adapter.finish_session()
                except Exception:
                    pass

    async def receiver(self):
        guard = VoiceFrameGuard()
        while not self.stopped:
            try:
                try:
                    raw = await self.socket.receive_text()
                except Exception:
                    if self.stopped:
                        return
                    if not self.connected and not (self.reconnector and self.reconnector.active):
                        raise
                    if self.reconnector is None:
                        raise
                    await self.reconnector.begin(client_lost=True)
                    await self.reconnector.task
                    guard = VoiceFrameGuard()
                    continue
                frame = guard.parse(raw)
            except TicketError as exc:
                logger.info('voice.ws.frame_reject reason=%s', str(exc) if str(exc) in
                            {'frame_too_large', 'frame_rate_exceeded', 'frame_invalid'} else 'invalid')
                await self.metrics.emit_many([('voice.ws.frame_rejection',{'reason':str(exc) if str(exc) in
                    {'frame_too_large','frame_rate_exceeded','frame_invalid'} else 'invalid'},1)])
                raise
            if frame['type'] == 'heartbeat':
                self.last_client_heartbeat = time.monotonic()
            elif frame['type'] == 'cancel':
                self.user_cancelled = True
                self.cancel.set()
                return
            elif frame['type'] == 'microphone_state':
                self.mic_muted, self.mic_available = frame['muted'], frame['available']
                await self.observe(self.connected)
            elif frame['type'] in CLIENT_FIELDS:
                if not self.connected and self.reconnector and self.reconnector.active:
                    continue
                await self.handle_playback(frame)
            elif self.connected and not (self.reconnector and self.reconnector.active):
                decision = self.barge_in.audio(frame['pcm'], now=time.monotonic())
                try:
                    await self.handle_barge_in(decision)
                    await self.adapter.send_audio(frame['pcm'])
                except ProviderError:
                    if self.reconnector is None:
                        raise
                    await self.reconnector.begin(client_lost=False)
                    await self.reconnector.task
                    # The failed PCM may have reached the provider: never replay it.
                except ConnectionError:
                    if self.reconnector is None:
                        raise
                    await self.reconnector.begin(client_lost=True)
                    await self.reconnector.task
                    guard = VoiceFrameGuard()

    async def heartbeat(self):
        params = self.config['concurrency']
        while not self.stopped:
            await asyncio.sleep(params['heartbeat_interval_ms']/1000)
            async with self.factory() as db:
                status = await db.scalar(select(VoiceCall.status).where(VoiceCall.call_id == self.call.call_id))
            if status not in ('deciding','ringing','connected','reconnecting'):
                await self.stop_local()
                return
            if not (self.reconnector and self.reconnector.active) and time.monotonic()-self.last_client_heartbeat >= params['user_lock_ttl_ms']/1000:
                logger.info('voice.ws.heartbeat_timeout=1')
                try:await self.request_end()
                finally:await self.metrics.emit_many([('voice.ws.heartbeat_timeout',{},1)])
                return
            if not await self.leases.renew(user_id=self.call.user_id, call_id=self.call.call_id, ttl_ms=params['user_lock_ttl_ms']):
                return
            state = await self.observe(self.connected)
            await self.quota.checkpoint(self.cache, self.meter)
            if state['must_end']:
                self.end_reason = 'quota_exhausted'
                return
            if not (self.reconnector and self.reconnector.active and self.reconnector.need_socket):
                try:
                    await self.send('heartbeat', grace_seconds=state['grace_seconds'])
                except ConnectionError:
                    if self.reconnector and self.connected:
                        await self.reconnector.begin(client_lost=True)
                    else:
                        raise

    async def _prepare_context(self, barrier, collector):
        from backend.services.realtime_voice_context_pack_service import context_pack_events
        started = time.monotonic()
        pack = error = None
        try:
            pack = await self.context_builder(call=self.call, session_factory=self.factory,
                now=datetime.now(timezone.utc), barrier=barrier)
            return pack
        except BaseException as exc:
            error = exc
            raise
        finally:
            await collector.emit_many(context_pack_events(pack=pack,error=error,
                elapsed_ms=int((time.monotonic()-started)*1000),barrier_released=barrier.is_set()))

    @defer_warmup_metrics
    async def warmup(self):
        barrier = asyncio.Event()
        events = []
        class DeferredMetrics:
            async def emit_many(self, batch):
                events.extend(batch)
        context_task = asyncio.create_task(self._prepare_context(barrier, DeferredMetrics()))
        try:
            await self.adapter.create_connection()
            pack = await context_task
            if not barrier.is_set():
                raise RuntimeError('context_barrier_not_ready')
            await self.adapter.inject_context(pack.persona, pack.dynamic)
            self.recall.preamble = pack.dynamic
            await self.adapter.start_session()
            self.turns = VoiceTurnService(call_id=self.call.call_id, session_id=self.adapter.session_id,
                session_factory=self.factory, gate=self.turn_gate, session_context=self.session_context,
                memory_job_writer=self.memory_job_writer,metrics=self.metrics)
            self.playback = PlaybackEvidence(call_id=self.call.call_id,
                capability_enabled=getattr(self.adapter,'capability_enabled',lambda key:False))
            async with self.factory() as db:
                await db.execute(update(VoiceCall).where(VoiceCall.call_id == self.call.call_id,
                    VoiceCall.status == 'ringing').values(provider_session_id=self.adapter.session_id,
                        provider_dialog_id=getattr(self.adapter, 'dialog_id', None)))
                await db.commit()
            return time.monotonic()
        finally:
            if not context_task.done():
                context_task.cancel()
            await asyncio.gather(context_task, return_exceptions=True)
            if events:
                await self.metrics.emit_many(events)

    async def _observe_ringing(self,result,order,started):
        events, self._warmup_metrics = self._warmup_metrics, []
        await self.metrics.emit_many(events + [('voice.call01.ringing_result',{'result':result},1),
            ('voice.call01.provider_ready',{'order':order},1),
            ('voice.call01.final_latency_ms',{'result':result},max(0,int((time.monotonic()-started)*1000)))])

    async def lifecycle(self):
        await self.send('state', status='deciding')
        async with self.factory() as db:
            inputs = await call_decision_inputs(db, user_id=self.call.user_id, call_id=self.call.call_id, now=datetime.now(timezone.utc))
        decision_started = time.monotonic()
        decision = await decide_call(inputs=inputs, settings=self.script['call_answer'], model=self.decision_model, metrics=self.metrics)
        logger.info('voice.call01.audit call_id=%s answer=%s delay=%s fallback=%s category=%s latency_ms=%s',
            self.call.call_id, decision.answer, decision.delay_seconds, decision.fallback, decision.failure_category,
            int((time.monotonic()-decision_started)*1000))
        target = 'cancelled' if self.cancel.is_set() else 'ringing' if decision.answer else 'missed'
        async with self.factory() as db:
            changed = await transition_call(db, call_id=self.call.call_id, expected=('deciding',), target=target, now=datetime.now(timezone.utc), metrics=VoiceMetrics(self.cache), call01_fallback=decision.fallback)
        if not changed:
            return
        if target != 'ringing':
            try:
                await self.send('state', status=target)
            finally:
                logger.info('voice.call01.ringing_result.%s=1', target)
                logger.info('voice.call01.provider_ready_order.unavailable=1')
                await self._observe_ringing(target,'unavailable',decision_started)
            return
        await self.send('state', status=target)
        started = time.monotonic()
        minimum, ceiling, _, _ = ring_timing(self.script['call_answer'])
        gate = RingGate(decision.delay_seconds, minimum, ceiling)
        connecting_sent = False
        connecting_task = None
        connect_after = max(minimum, decision.delay_seconds)
        warm = asyncio.create_task(self.warmup())
        cancellation = asyncio.create_task(self.cancel.wait())
        try:
            while not self.stopped:
                ready = (warm.done() and not warm.cancelled() and warm.exception() is None
                         and warm.result() <= started+ceiling)
                elapsed = time.monotonic()-started
                state = gate.result(elapsed=elapsed, ready=ready,
                                    cancelled=self.cancel.is_set(), provider_error=warm.done() and not ready)
                if state != 'ringing':
                    break
                if not connecting_sent and elapsed >= connect_after:
                    # A display phase only: the durable state and metering stay ringing.
                    connecting_task = asyncio.create_task(self.send('state', status='ringing', phase='connecting'))
                    connecting_sent = True
                deadline = connect_after if ready or not connecting_sent else ceiling
                delay = deadline-(time.monotonic()-started)
                waiting = [cancellation] + ([] if warm.done() else [warm])
                await asyncio.wait(waiting, timeout=max(.001, delay), return_when=asyncio.FIRST_COMPLETED)
            if self.stopped:
                return
            # Presentation must not delay ready/cancel/deadline decisions or arrive after them.
            if connecting_task is not None:
                if not connecting_task.done():
                    connecting_task.cancel()
                await asyncio.gather(connecting_task, return_exceptions=True)
            logger.info('voice.call01.ringing_result.%s=1', state)
            logger.info('voice.call01.provider_ready_order.%s=1',
                'before_target' if ready and warm.result()-started <= decision.delay_seconds else 'after_target' if ready else 'unavailable')
            async with self.factory() as db:
                changed = await transition_call(db, call_id=self.call.call_id, expected=('ringing',), target=state, now=datetime.now(timezone.utc), metrics=VoiceMetrics(self.cache))
            if not changed:
                return
            try:
                if self.stopped:return
                if state == 'connected':
                    await self.observe(True)
                    await self.quota.checkpoint(self.cache, self.meter)
                    self.connected = True
                    interaction = {**VOICE_INTERACTION_DEFAULTS, **self.config.get('interaction', {})}
                    silence = self.script['silence_and_exit']
                    self.ending = EndingPolicy(connected_at=time.monotonic(),
                        hard_limit=self.config['quota']['hard_limit_seconds'],
                        goodbye_timeout=interaction['goodbye_timeout_ms']/1000,
                        silence_confirm=silence['silence_confirm_seconds'],
                        silence_hangup=silence['silence_hangup_seconds'], time_low=interaction['time_low_seconds'],
                        post_playback_buffer_ms=interaction['post_playback_buffer_ms'])
                await self.send('state', status=state, reconnect_timeout_ms=self.config['concurrency']['reconnect_timeout_ms'])
            finally:
                await self._observe_ringing(state,
                    'before_target' if ready and warm.result()-started<=decision.delay_seconds else 'after_target' if ready else 'unavailable',
                    decision_started)
            if state != 'connected':
                return
            if decision.opening_text.strip() and not self.stopped and not self.cancel.is_set():
                await self.adapter.say_hello(decision.opening_text)
            while not self.stopped and not self.cancel.is_set():
                try:
                    if self.reconnector and self.reconnector.active:
                        await self.reconnector.task
                        if self.stopped:
                            return
                    event = await self.adapter.receive_event()
                    await self.process_provider_event(event)
                except ConnectionError:
                    if self.reconnector is None:
                        raise
                    await self.reconnector.begin(client_lost=True)
                    await self.reconnector.task
                except ProviderError:
                    if self.reconnector is None:
                        raise
                    await self.reconnector.begin(client_lost=False)
                    await self.reconnector.task
        finally:
            tasks = (warm, cancellation) + ((connecting_task,) if connecting_task is not None else ())
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    @observe_barge_in
    async def process_provider_event(self, event):
        if self.stopped or (self.reconnector and self.reconnector.active):
            return
        if self.turns is not None:
            if event.sequence <= self.ingested_sequences.get(event.session_id, 0):
                return
            self.ingested_sequences[event.session_id] = event.sequence
        elif self.playback is not None and self.playback.seen(event):
            return
        active = [(r.question_id) for r in self.playback.replies.values()
                  if r.played_ms > 0 and r.last_progress_at is not None
                  and 0 <= time.monotonic() - r.last_progress_at <= .5
                  and not r.interrupted and not r.completed and not r.audio_completed] if self.playback else []
        playing = active[-1] if active else None
        if event.kind == 'user_speech_started' and playing and hasattr(self.adapter, 'preserve_playing_question'):
            self.adapter.preserve_playing_question(playing)
        await self.backchannels.consume(event, playing=playing)

    async def _delete_backchannel(self, question_id):
        await self.adapter.delete_backchannel(question_id)

    async def _discard_backchannel_event(self, event):
        # Consume a text-free tombstone to keep the provider sequence contiguous.
        if self.turns is not None:
            from dataclasses import replace
            await self.turns.consume(replace(event, kind='backchannel_filtered', payload=None))

    async def _accepted_provider_event(self, event):
        if self.stopped:
            return
        self.interruptions.confirm(event)
        decision = None
        if event.kind == 'user_speech_started':
            self.barge_in.start(event.question_id, now=time.monotonic())
        elif event.kind in ('asr_interim', 'asr_final') and isinstance(event.payload, str):
            decision = self.barge_in.text(event.question_id, event.payload, final=event.kind == 'asr_final')
        await self.handle_barge_in(decision)
        if self.turns is not None:
            await self.turns.consume(event)
            if event.kind == 'asr_final' and not self.stopped:
                self.recall.submit(event.question_id)
        if self.stopped:
            return
        await self.observe_ending_event(event)
        if self.stopped:
            return
        if self.ending is not None and getattr(event, 'reply_id', None):
            outgoing, rejected = await self.closing_output.filter(event,
                restricted=self.ending.soft_closing or (bool(self.ending.pending_reason) and not self.ending.native_pending),
                topic=self.closing_topic or self.latest_user,
                expected_text=self.fixed_goodbye_questions.get(event.question_id))
            if rejected:
                self.waiting_user = True
                if (self.closing_output.failures.get(event.reply_id) == 'unavailable'
                        and self.ending.pending_reason == 'silence_timeout'
                        and self.silence_fallback_generation != self.ending.generation):
                    self.silence_fallback_generation = self.ending.generation
                    self.ending.goodbye_reply = None
                    self.ending.goodbye_deadline = time.monotonic() + self.ending.goodbye_timeout
                    await self.handle_end_actions(['goodbye:silence_fallback'])
            for item in outgoing:
                if not self.stopped:
                    await self.forward_provider_event(item, buffered=True)
            return
        await self.forward_provider_event(event, buffered=True)

    async def forward_provider_event(self, event, *, buffered=False):
        if isinstance(event.payload, bytes):
            if self.playback is not None and self.playback.is_stopped(event.reply_id):
                return
            self.waiting_user = False
            await self.send('audio', pcm_base64=base64.b64encode(event.payload).decode(), metadata=event.public_metadata())
            if self.playback is not None:
                self.playback.feed(event, allow_buffered=buffered)
        else:
            # Raw transcripts are server memory inputs to the gate, never a
            # debug payload in the production H5 transport.
            data = {k: event.payload[k] for k in ('sentence_id','start_time','end_time')
                    if isinstance(event.payload,dict) and k in event.payload}
            if self.playback is not None:
                data.update(self.playback.feed(event, allow_buffered=buffered))
            await self.send('provider_event', metadata=event.public_metadata(), data=data)

    @observe_barge_in
    async def handle_barge_in(self, decision):
        if decision is None or self.playback is None or not self.connected:
            return
        if decision == 'backchannel':
            logger.info('voice.barge_in.backchannel=1')
            return
        # Pending audio receipt is not actual playback. A nonzero client
        # renderer report establishes the playing reply before semantic upgrade.
        active = [(key, value) for key, value in self.playback.replies.items()
                  if value.played_ms > 0 and not value.interrupted and not value.completed and not value.audio_completed]
        if self.ending is not None and self.script['silence_and_exit']['user_resume_cancels_exit']:
            await self.handle_end_actions(self.ending.resume(now=time.monotonic()))
        if active:
            if active[-1][0] not in self.interruptions.requests:
                self.barge_observations('false_interrupt', result='not_measurable')
            await self.interruptions.upgrade(active[-1][0])
            logger.info('voice.barge_in.upgraded=1')

    @observe_playback
    @observe_barge_in
    async def handle_playback(self, frame):
        if not self.connected or self.playback is None or self.turns is None:
            raise TicketError('playback_not_connected')
        try:
            result=self.playback.client({k:v for k,v in frame.items() if k not in {'v','seq'}})
            if result is not None:
                await self.turns.apply_effective(frame['reply_id'],result)
                if result.completed or result.interrupted:
                    self.playback.release_text(frame['reply_id'])
                if frame['type'] == 'client_barge_in':
                    mode = await self.interruptions.stopped(frame['reply_id'], frame['played_audio_ms'])
                    logger.info('voice.barge_in.%s=1', mode)
                    self.waiting_user = True
                elif frame['type'] in ('client_reply_playback_completed', 'client_audio_playback_completed'):
                    self.waiting_user = self.playback.audio_idle()
                    if self.ending is not None:
                        await self.handle_end_actions(self.ending.played(frame['reply_id']))
        except ValueError:
            raise TicketError('playback_event_invalid') from None

    async def observe_ending_event(self, event):
        if self.ending is None:
            return
        if event.kind == 'user_speech_started':
            self.closing_output.discard()
            self.waiting_user = False
            new_question = self.native_question != (event.session_id, event.question_id)
            self.native_question = (event.session_id, event.question_id)
            if new_question and (self.ending.native_pending or self.ending.played_deadline is not None) and self.script['silence_and_exit']['user_resume_cancels_exit']:
                await self.handle_end_actions(self.ending.resume(now=time.monotonic()))
            elif not self.ending.pending_reason:
                self.ending.resume(now=time.monotonic())
        elif event.kind == 'asr_final' and isinstance(event.payload, str):
            self.waiting_user = False
            self.latest_user = ''
            if self.turns is not None:
                try:
                    self.latest_user = await self.turns.safe_user_context(event.question_id)
                except Exception:
                    logger.warning('voice.crisis.context_unavailable')
        elif (event.kind == 'tts_finished' and isinstance(event.payload, dict)
              and event.payload.get('status_code') == '20000002'):
            reply = self.playback.replies.get(event.reply_id) if self.playback else None
            if (self.native_question == (event.session_id, event.question_id)
                    and reply is not None and reply.question_id == event.question_id
                    and reply.audio_bytes > 0 and not reply.interrupted and not reply.completed):
                logger.info('voice.ending.native_exit_signal call_id=%s reply_id=%s', self.call_id, event.reply_id)
                await self.handle_end_actions(self.ending.native_exit(event.reply_id))
            else:
                logger.info('voice.ending.native_exit_rejected=1')
        elif event.kind == 'control_confirmed':
            token = event.payload.get('control_token')
            request = self.control_tokens.pop(token, None)
            if request:
                self.control_questions[event.question_id] = request
                if request[0] == 'fixed_goodbye' and request[1] == self.ending.generation:
                    self.fixed_goodbye_questions[event.question_id] = self.script['silence_and_exit']['silence_timeout_template']
        elif getattr(event, 'reply_id', None) and event.question_id in self.control_questions:
            kind, generation = self.control_questions[event.question_id]
            if kind in ('goodbye', 'fixed_goodbye'):
                self.ending.bind_goodbye(event.reply_id, generation)

    @observe_ending
    async def handle_end_actions(self, actions):
        for action in actions:
            if self.stopped:
                return
            if action.startswith('end:'):
                await self.request_end(reason=action.split(':', 1)[1])
                return
            if action == 'cancel_goodbye':
                for reply_id, value in (self.playback.replies.items() if self.playback else []):
                    if not value.completed and not value.interrupted:
                        await self.interruptions.upgrade(reply_id)
                self.closing_output.discard()
                continue
            kind = 'goodbye' if action.startswith('goodbye:') else action
            if kind == 'time_low':
                self.closing_topic = self.latest_user
                text = build_control_prompt('time_low')
            elif kind == 'silence_confirm':
                text = build_control_prompt('silence_confirm')
            else:
                reason = action.split(':', 1)[1]
                template = self.script['silence_and_exit'][
                    'silence_timeout_template' if reason == 'silence_timeout' else 'exit_intent_template']
                text = build_control_prompt('goodbye', template)
            fixed = action == 'goodbye:silence_fallback'
            if fixed:
                logger.info('voice.ending.silence_fallback_requested=1')
                text = build_control_prompt('silence_fallback', self.script['silence_and_exit']['silence_timeout_template'])
            token = str(uuid4())
            self.control_tokens[token] = ('fixed_goodbye' if fixed else kind, self.ending.generation)
            try:
                outcome = await self.adapter.control_query(text, kind=kind, token=token)
                if outcome.mode != 'control_requested':
                    self.control_tokens.pop(token, None)
                    logger.info('voice.ending.control_deferred=1')
            except Exception:
                self.control_tokens.pop(token, None)
                logger.info('voice.ending.control_unavailable=1')

    async def ending_clock(self):
        while not self.stopped:
            await asyncio.sleep(.25)
            if self.ending is None:
                continue
            await self.observe(self.connected)
            async with self.meter_lock:
                async with self.factory() as db:
                    remaining = await self.quota.remaining(db, self.meter, now=datetime.now(timezone.utc))
            deadline = (self.meter.grace_started + self.meter.grace_limit
                        if self.meter.grace_started is not None else None)
            actions = self.ending.tick(now=time.monotonic(),
                waiting=self.connected and self.waiting_user,
                mic_ok=self.mic_available and not self.mic_muted,
                remaining=remaining, grace_deadline=deadline)
            await self.handle_end_actions(actions)
            now = time.monotonic()
            if not self.stopped and now-self.last_clock_emit >= 1 and not (self.reconnector and self.reconnector.active and self.reconnector.need_socket):
                self.last_clock_emit = now
                try:
                    await self.send('clock', duration_seconds=sum(s['duration_seconds'] for s in self.meter.slices))
                except ConnectionError:
                    if self.reconnector and self.connected:
                        await self.reconnector.begin(client_lost=True)
                    else:
                        raise

    async def disconnected(self, client_lost):
        self.connected = False
        self.native_question = None
        if self.ending is not None and self.ending.native_pending:
            # Rebuild discards the old playback ledger; its exit cannot survive.
            self.ending.resume(now=time.monotonic())
        await self.observe(False)
        self.reconnector.boundary('pause')
        async with self.factory() as db:
            changed = await transition_call(db, call_id=self.call_id, expected=('connected',),
                                            target='reconnecting', now=datetime.now(timezone.utc), metrics=VoiceMetrics(self.cache))
        if not changed:
            raise TicketError('call_not_reconnectable')
        self.waiting_user = False
        if not client_lost:
            try:
                await self.send('state', status='reconnecting')
            except ConnectionError:
                self.reconnector.need_socket = True
        logger.info('voice.reconnect.started=1')

    @observe_playback
    @observe_barge_in
    async def rebuild(self):
        events = []
        class DeferredMetrics:
            async def emit_many(self, batch):
                events.extend(batch)
        try:
            return await self._rebuild(DeferredMetrics())
        finally:
            if events:
                await self.metrics.emit_many(events)

    async def _rebuild(self, deferred_metrics):
        self.interruptions.finish_observations()
        old_preamble = self.recall.preamble
        await self.recall.close()
        if self.turns:
            if self.playback:
                for reply in self.playback.replies:
                    await self.turns.apply_effective(reply, self.playback.snapshot(reply))
                    self.playback.release_text(reply)
            await self.turns.freeze()
            async with self.factory() as db:
                await self.turns.final_flush(db)
                await db.commit()
                await flush_voice_metrics(db, deferred_metrics)
        self.closing_output.discard()
        self.control_tokens.clear()
        self.control_questions.clear()
        self.fixed_goodbye_questions.clear()
        reuse = self.adapter.capability_enabled('supports_session_reconnect')
        pack = None
        if not reuse:
            await self.adapter.finish_session()
            barrier = asyncio.Event()
            pack = await self._prepare_context(barrier, deferred_metrics)
            if not barrier.is_set():
                raise RuntimeError('context_barrier_not_ready')
        retries = self.config['s2s']['max_retries']
        backoff = self.config['s2s']['retry_backoff_ms']
        for attempt in range(retries+1):
            if self.reconnector is not None:
                self.reconnector.observe('attempt', phase='provider')
            try:
                if reuse:
                    outcome = await self.adapter.reconnect_session()
                    if self.reconnector is not None:
                        self.reconnector.observe('mode', mode={'same_dialog':'same_session',
                            'new_session_with_preamble':'new_session'}.get(getattr(outcome,'mode',None),'unavailable'))
                else:
                    self.adapter = self.adapter_factory(call_id=self.call_id, config=self.config,
                                                        capability_snapshot=self.call.capability_snapshot)
                    if isinstance(self.adapter, VoiceProviderAdapter):
                        self.adapter.metrics = self.metrics
                    await self.adapter.create_connection()
                    await self.adapter.inject_context(pack.persona, pack.dynamic)
                    await self.adapter.start_session()
                    if self.reconnector is not None:
                        self.reconnector.observe("mode", mode="new_session")
                break
            except Exception:
                await self.adapter.finish_session()
                if attempt == retries:
                    raise
                logger.info('voice.reconnect.provider_retry=1')
                await asyncio.sleep(backoff[min(attempt,len(backoff)-1)]/1000 if backoff else 0)
        self.recall = self._build_recall()
        self.recall.preamble = old_preamble if reuse else pack.dynamic
        self.turns = VoiceTurnService(call_id=self.call_id, session_id=self.adapter.session_id,
                                      session_factory=self.factory, gate=self.turn_gate, session_context=self.session_context,
                                      memory_job_writer=self.memory_job_writer,metrics=self.metrics)
        self.playback = PlaybackEvidence(call_id=self.call_id, capability_enabled=self.adapter.capability_enabled)
        self.interruptions = BargeInController(self.adapter, self.send, observations=self.barge_observations)
        from backend.services.realtime_voice_backchannel_service import BackchannelFilter
        self.backchannels = BackchannelFilter(self.script['barge_in'], self._accepted_provider_event,
                                              self._discard_backchannel_event, self._delete_backchannel, observations=self.barge_observations)
        self.barge_in = BargeInClassifier({**VOICE_INTERACTION_DEFAULTS, **self.config.get('interaction', {})}, self.script['barge_in'], observations=self.barge_observations)
        self.ingested_sequences.clear()
        self.reconnect_new_session = not reuse

    async def restored(self):
        if self.reconnector.socket is not None:
            self.socket = self.reconnector.socket
            self.sequence = 0
        async with self.factory() as db:
            user = await db.scalar(select(User).where(User.id == self.user_id).with_for_update().execution_options(populate_existing=True))
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == self.call_id).with_for_update().execution_options(populate_existing=True))
            if user is None or user.is_banned or row is None or row.deletion_fence_at is not None or not await self.leases.owner_matches(user_id=self.user_id, call_id=self.call_id):
                raise TicketError('reconnect_owner_unavailable')
            changed = await transition_call(db, call_id=self.call_id, expected=('reconnecting',),
                                            target='connected', now=datetime.now(timezone.utc), metrics=VoiceMetrics(self.cache))
        if not changed:
            raise TicketError('call_not_reconnectable')
        async with self.factory() as db:
            await db.execute(update(VoiceCall).where(VoiceCall.call_id == self.call_id,
                VoiceCall.status == 'connected').values(provider_session_id=self.adapter.session_id,
                    provider_dialog_id=self.adapter.dialog_id))
            await db.commit()
        self.connected = True
        self.last_client_heartbeat = time.monotonic()
        self.waiting_user = True
        await self.observe(True)
        self.reconnector.boundary('resume')
        await self.send('state', status='connected', reconnected=True, reconnect_timeout_ms=self.config['concurrency']['reconnect_timeout_ms'])
        if self.reconnect_new_session:
            await self.adapter.say_hello(self.script['reconnect_bridge']['success_template'])
        logger.info('voice.reconnect.restored=1')

    async def failed(self):
        reason = 'reconnect_timeout' if time.monotonic() >= self.reconnector.deadline else 'provider_error'
        await self.request_end(reason=reason)

    async def flush_turns(self, db):
        if self.turns is not None:
            await self.turns.final_flush(db)

    async def _observe_close_reason(self):
        from backend.services.realtime_voice_state_service import REASONS,TERMINAL
        reason='unavailable'
        try:
            # Read only the committed lifecycle fact; telemetry cannot invent an
            # error from a stale gateway default, or delay cleanup indefinitely.
            async with asyncio.timeout(.1):
                async with self.factory() as db:
                    row=(await db.execute(select(VoiceCall.status,VoiceCall.end_reason).where(
                        VoiceCall.call_id==self.call_id))).first()
                    if row is not None and row.status in TERMINAL:
                        reason=row.end_reason if row.end_reason in REASONS else 'other'
        except Exception:
            pass
        await self.metrics.emit_many([('voice.ws.close_reason',{'reason':reason},1)])
        logger.info('voice.ws.close_reason.%s=1',reason)

    async def run(self):
        await self.observe(False)
        local = LocalVoiceCall(self.meter, self.stop_local, lambda reason: setattr(self, 'end_reason', reason),
                              final_flush=self.flush_turns, reconnect=self.reconnector, closed_event=self.closed_event)
        if self.call.call_id in local_voice_calls:
            raise TicketError('local_owner_already_registered')
        local_voice_calls[self.call.call_id] = local
        tasks = [asyncio.create_task(method()) for method in (self.receiver, self.heartbeat, self.lifecycle, self.ending_clock)]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Cancel before connected preserves cancelled; transport/technical
            # failures remain distinct from the character choosing missed.
            try:
                if not self.connected:
                    async with self.factory() as db:
                        await transition_call(db, call_id=self.call.call_id, expected=('deciding','ringing'),
                                              target='cancelled' if self.user_cancelled else 'failed', now=datetime.now(timezone.utc), metrics=VoiceMetrics(self.cache))
            finally:
                try:
                    await self.stop_local()
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    try:
                        await self.ops.end_call(call_id=self.call.call_id, user_id=self.call.user_id,
                                                reason='user_hangup' if self.user_cancelled else self.end_reason)
                    finally:
                        self.closed_event.set()
                        await self._observe_close_reason()
                        events, self._warmup_metrics = self._warmup_metrics, []
                        if events:
                            await self.metrics.emit_many(events)
