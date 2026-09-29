"""One live owner, one bounded reconnect window, purpose-separated tickets.

Another worker may not attach to this process's live provider. Routing must
preserve the owner; an unavailable owner fails closed rather than cloning a call.
"""
import asyncio
import hmac
import time
from datetime import datetime, timezone
from uuid import uuid4

from backend.services.realtime_voice_ticket_service import TicketError
from backend.services.realtime_voice_metric_service import defer_voice_metrics


class ReconnectCoordinator:
    def __init__(self, owner, *, timeout_ms, codec):
        self.owner, self.timeout_ms, self.codec = owner, timeout_ms, codec
        self.lock = asyncio.Lock()
        self.ready = asyncio.Event()
        self.active = False
        self.need_socket = False
        self.socket = None
        self.task = None
        self.deadline = None
        self.jti = None
        self.observation = None

    def observe(self, name, **dimensions):
        if self.observation is not None:
            self.observation['events'].append(('voice.reconnect.' + name, dimensions, 1))

    def boundary(self, kind):
        observation = self.observation
        if observation is None:
            return
        now = time.monotonic()
        if kind == 'pause' and observation['paused'] is None:
            observation['paused'] = now
            self.observe('no_charge_boundary', boundary='pause')
        elif kind == 'resume' and observation['paused'] is not None and observation['resumed'] is None:
            observation['resumed'] = now
            self.observe('no_charge_boundary', boundary='resume')

    async def _publish(self, observation, result):
        if observation is None:
            return
        now = time.monotonic()
        events = observation['events']
        events.extend([('voice.reconnect.result', {'result':result}, 1),
            ('voice.reconnect.duration_ms', {'result':result}, int(max(0,now-observation['started'])*1000))])
        if result == 'timeout':
            events.append(('voice.reconnect.timeout', {}, 1))
        if observation['paused'] is not None:
            end = observation['resumed'] if observation['resumed'] is not None else now
            events.append(('voice.reconnect.no_charge_ms', {'boundary':'meter_observation'},
                           int(max(0,end-observation['paused'])*1000)))
        metrics = getattr(self.owner, 'metrics', None)
        if metrics is not None:
            await metrics.emit_many(events)

    async def begin(self, *, client_lost):
        observation = None
        try:
            async with self.lock:
                if self.owner.stopped:
                    return
                if self.active:
                    if client_lost:
                        self.need_socket = True
                        self.socket = None
                        self.ready.clear()
                    return
                self.active = True
                self.need_socket = client_lost
                self.socket = None
                self.jti = None
                self.ready.clear()
                started = time.monotonic()
                self.deadline = started + self.timeout_ms / 1000
                observation = self.observation = dict(started=started, paused=None, resumed=None, events=[])
                self.observe('trigger', reason='client_disconnect' if client_lost else 'provider_disconnect')
                self.observe('attempt', phase='window')
                try:
                    await self.owner.disconnected(client_lost)
                except BaseException:
                    self.active = False
                    raise
                self.task = asyncio.create_task(self._recover(observation))
        except BaseException:
            await self._publish(observation, 'disconnect_failed')
            raise

    async def _recover(self, observation):
        result = 'cancelled'
        try:
            with defer_voice_metrics(observation["events"]):
                try:
                    async with asyncio.timeout_at(self.deadline):
                        await self.owner.rebuild()
                        while True:
                            async with self.lock:
                                if self.owner.stopped:
                                    return
                                if not self.need_socket:
                                    await self.owner.restored()
                                    self.active = False
                                    result = 'restored'
                                    return
                            await self.ready.wait()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    result = 'timeout' if time.monotonic() >= self.deadline else 'failure'
                    self.active = False
                    await self.owner.failed()
        finally:
            # Outside both the recovery deadline and coordinator lock.
            await self._publish(observation, result)

    async def issue(self, *, user_id, device_id):
        async with self.lock:
            if (self.owner.stopped or not self.active or not self.need_socket
                    or time.monotonic() >= self.deadline or user_id != self.owner.user_id
                    or not isinstance(device_id, str)
                    or not hmac.compare_digest(device_id, self.owner.device_id)):
                raise TicketError('reconnect_not_available')
            self.jti = str(uuid4())
            now = datetime.now(timezone.utc)
            expires_ms = int(now.timestamp()*1000 + (self.deadline-time.monotonic())*1000)
            return {'call_id': self.owner.call_id, 'call_ticket': self.codec.issue(
                user_id=user_id, call_id=self.owner.call_id, device_id=device_id,
                jti=self.jti, expires_ms=expires_ms), 'expires_ms': expires_ms}

    async def attach(self, socket, *, ticket, device_id):
        async with self.lock:
            value = self.codec.verify(ticket, call_id=self.owner.call_id, device_id=device_id,
                                      now=datetime.now(timezone.utc))
            if (self.owner.stopped or not self.active or not self.need_socket
                    or time.monotonic() >= self.deadline or self.jti is None
                    or value['jti'] != self.jti or value['user_id'] != self.owner.user_id
                    or not hmac.compare_digest(device_id, self.owner.device_id)):
                raise TicketError('reconnect_ticket_not_consumable')
            self.jti = None
            self.socket = socket
            self.need_socket = False
            self.ready.set()

    def cancel(self):
        self.active = False
        self.jti = None
        self.ready.set()
        if self.task and self.task is not asyncio.current_task() and not self.task.done():
            self.task.cancel()
