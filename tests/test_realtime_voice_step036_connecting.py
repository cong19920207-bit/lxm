import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func

from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_decision_service import CallDecision
from tests.test_realtime_voice_step012_gateway import session
from tests.test_realtime_voice_step009_ops import storage


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['ready_late', 'ready_early', 'timeout', 'cancel_connecting', 'cancel_ringing', 'slow_ready', 'slow_cancel', 'slow_timeout'])
async def test_connecting_is_an_unbilled_ringing_presentation(storage, monkeypatch, outcome):
    import backend.services.realtime_voice_gateway_service as module
    gateway = await session(storage)
    clock = [0.0]
    ready = asyncio.Event()
    phase_checked = asyncio.Event()
    phase_cancelled = []
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    async def inputs(*args, **kwargs): return {}
    async def decide(**kwargs): return CallDecision(True, 6, '', False, None, False)
    monkeypatch.setattr(module, 'call_decision_inputs', inputs)
    monkeypatch.setattr(module, 'decide_call', decide)
    async def warmup():
        await ready.wait()
        return clock[0]
    gateway.warmup = warmup
    async def wait(tasks, *, timeout, return_when):
        await asyncio.sleep(0)
        if clock[0] >= 6 and outcome != 'ready_early':
            await phase_checked.wait()
        if outcome == 'cancel_ringing':
            clock[0] = 2
            gateway.cancel.set()
        elif outcome == 'ready_early' and not ready.is_set():
            clock[0] = 3
            ready.set()
        elif outcome in ('ready_late', 'slow_ready') and clock[0] >= 6:
            clock[0] = 8
            ready.set()
        elif outcome == 'slow_cancel' and clock[0] >= 6:
            clock[0] = 7
            gateway.cancel.set()
        elif not gateway.cancel.is_set():
            clock[0] += timeout
        await asyncio.sleep(0)
        return {t for t in tasks if t.done()}, {t for t in tasks if not t.done()}
    proxy = SimpleNamespace(**{name: getattr(asyncio, name) for name in dir(asyncio)})
    proxy.wait = wait
    monkeypatch.setattr(module, 'asyncio', proxy)
    phases = []
    original = gateway.send
    async def send(kind, **data):
        if data.get('phase') == 'connecting':
            phases.append(clock[0])
            assert data['status'] == 'ringing'
            assert not gateway.connected
            async with storage() as db:
                call = await db.scalar(select(VoiceCall))
                assert call.status == 'ringing' and call.connected_at is None
                assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0
            if outcome == 'cancel_connecting': gateway.cancel.set()
            phase_checked.set()
            if outcome.startswith('slow_'):
                try:
                    await asyncio.Event().wait()
                finally:
                    phase_cancelled.append(True)
        await original(kind, **data)
    gateway.send = send
    async def receive():
        gateway.cancel.set()
        return SimpleNamespace(kind='usage', payload={}, session_id='test', question_id=None, public_metadata=lambda: {})
    gateway.adapter.receive_event = receive
    await gateway.lifecycle()
    assert phases == ([] if outcome in ('ready_early', 'cancel_ringing') else [6.0])
    expected = 'connected' if outcome.startswith('ready') or outcome == 'slow_ready' else 'failed' if outcome in ('timeout', 'slow_timeout') else 'cancelled'
    async with storage() as db:
        call = await db.scalar(select(VoiceCall))
        assert call.status == expected
        assert (call.connected_at is not None) == (expected == 'connected')
    states = [frame for frame in gateway.socket.frames if frame['type'] == 'state']
    assert states[-1]['status'] == expected
    if outcome.startswith('slow_'):
        assert phase_cancelled == [True]
        assert not any(frame.get('phase') == 'connecting' for frame in states)
        assert clock[0] == {'slow_ready': 8, 'slow_cancel': 7, 'slow_timeout': 12}[outcome]
