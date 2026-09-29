"""Real Redis/SQL behavior: isolation, atomic updates, bounds and lifecycle."""
import asyncio
import os
from datetime import datetime

import pytest
from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step009_ops import add_call, StateCache

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M5_RUNTIME') != '1', reason='isolated Redis/MySQL opt-in')


async def context(runtime):
    from backend.services.realtime_voice_session_context_service import VoiceSessionContext
    factory, _, cache = runtime
    call_id = await add_call(factory, 'connected', StateCache())
    async with factory() as db:
        owner = await db.scalar(select(VoiceCall.user_id).where(VoiceCall.call_id == call_id))
    return VoiceSessionContext(cache=cache, session_factory=factory), call_id, owner


@pytest.mark.asyncio
async def test_atomic_order_dedupe_and_reconnect(runtime):
    ctx, call, user = await context(runtime)
    results = await asyncio.gather(*(ctx.append(call_id=call, user_id=user, kind='correction',
        item_id=str(i), turn_index=i, text=f'日本旅行{i}', safe=True) for i in range(1, 21)))
    assert all(r.status == 'ok' for r in results)
    await ctx.append(call_id=call, user_id=user, kind='correction', item_id='10', turn_index=10,
                     text='日本旅行更正', safe=True)
    from backend.services.realtime_voice_session_context_service import VoiceSessionContext
    restored = VoiceSessionContext(cache=runtime[2], session_factory=runtime[0])
    found = await restored.query(call_id=call, user_id=user, turn_index=21, query='日本')
    assert found.status == 'ok' and len(found.items) == 20
    assert [v['turn_index'] for v in found.items] == list(range(1, 21))
    assert found.items[9]['text'] == '日本旅行更正'
    assert 0 < await runtime[2].ttl('voice:session_context:' + call) <= 7200


@pytest.mark.asyncio
async def test_owner_cross_call_and_late_visibility(runtime):
    ctx, call, user = await context(runtime)
    await ctx.append(call_id=call, user_id=user, kind='recall_result', item_id='japan',
                     turn_index=3, text='日本旅行', safe=True, late=True)
    assert not (await ctx.query(call_id=call, user_id=user, turn_index=3)).items
    assert len((await ctx.query(call_id=call, user_id=user, turn_index=4)).items) == 1
    assert (await ctx.query(call_id=call, user_id=user+1, turn_index=4)).status == 'forbidden'
    assert (await ctx.append(call_id=call, user_id=user+1, kind='candidate', item_id='bad',
                            turn_index=4, text='foreign', safe=True)).status == 'forbidden'
    assert not (await ctx.query(call_id='other', user_id=user, turn_index=4)).items
    assert (await ctx.cleanup(call_id=call, user_id=user+1)).status == 'forbidden'
    assert (await ctx.query(call_id=call, user_id=user, turn_index=4)).items


@pytest.mark.asyncio
async def test_bounded_unsafe_and_deleted_cannot_resurrect(runtime):
    ctx, call, user = await context(runtime)
    unsafe = await ctx.append(call_id=call, user_id=user, kind='candidate', item_id='unsafe',
                              turn_index=1, text='UNSAFE', safe=False)
    assert unsafe.status == 'filtered'
    for i in range(1, 70):
        await ctx.append(call_id=call, user_id=user, kind='turn', item_id=str(i), turn_index=i,
                         text='旅行'*1000, safe=True)
    values = await ctx.query(call_id=call, user_id=user, turn_index=100)
    assert 0 < len(values.items) <= 32
    raw = await runtime[2].get('voice:session_context:' + call)
    assert len(raw.encode()) <= 65536 and 'UNSAFE' not in raw
    oversized = await ctx.append(call_id=call, user_id=user, kind='candidate', item_id='big',
                                 turn_index=100, text='x'*65537, safe=True)
    assert oversized.status == 'too_large'
    async with runtime[0]() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call))
        row.deletion_fence_at = datetime.utcnow()
        await db.commit()
    assert (await ctx.cleanup(call_id=call, user_id=user)).status == 'ok'
    result = await ctx.append(call_id=call, user_id=user, kind='candidate', item_id='late',
                              turn_index=100, text='late result', safe=True)
    assert result.status == 'closed'
    assert not await runtime[2].exists('voice:session_context:' + call)


@pytest.mark.asyncio
async def test_redis_failure_is_explicit_and_contains_no_text(runtime, caplog):
    ctx, call, user = await context(runtime)
    class Broken:
        async def eval(self, *args):
            raise RuntimeError('SECRET_CONTEXT')
    ctx.cache = Broken()
    result = await ctx.append(call_id=call, user_id=user, kind='candidate', item_id='x',
                              turn_index=1, text='SECRET_CONTEXT', safe=True)
    assert result.status == 'unavailable' and not result.items
    assert 'SECRET_CONTEXT' not in caplog.text


@pytest.mark.asyncio
async def test_turn_producer_captures_only_safe_closed_effective(runtime):
    from backend.services.realtime_voice_turn_service import VoiceTurnService, EffectiveText
    from tests.test_realtime_voice_step015_turns import Gate, event
    ctx, call, user = await context(runtime)
    service = VoiceTurnService(call_id=call, session_id='session1', session_factory=runtime[0],
                               gate=Gate(), session_context=ctx)
    await service.consume(event(call, 1, 'asr_final', '我准备去日本旅行'))
    await service.consume(event(call, 2, 'chat_text', '可以看看京都', reply='r1'))
    await service.consume(event(call, 3, 'tts_finished', {}, reply='r1'))
    assert not (await ctx.query(call_id=call, user_id=user, turn_index=2)).items
    await service.apply_effective('r1', EffectiveText('可以看看京都', 'full', completed=True))
    items = (await ctx.query(call_id=call, user_id=user, turn_index=2, query='日本')).items
    assert len(items) == 1 and '京都' in items[0]['text']
    unsafe = VoiceTurnService(call_id=call, session_id='session1', session_factory=runtime[0],
                              gate=Gate(safety='matched'), session_context=ctx)
    await unsafe.consume(event(call, 1, 'asr_final', 'UNSAFE', question='q2'))
    await unsafe.consume(event(call, 2, 'chat_text', 'UNSAFE', question='q2', reply='r2'))
    await unsafe.consume(event(call, 3, 'tts_finished', {}, question='q2', reply='r2'))
    await unsafe.apply_effective('r2', EffectiveText('UNSAFE', 'full', completed=True))
    assert 'UNSAFE' not in await runtime[2].get('voice:session_context:' + call)


@pytest.mark.asyncio
async def test_end_cleanup_and_expiry(runtime):
    from backend.services.realtime_voice_ops_service import VoiceOpsService
    ctx, call, user = await context(runtime)
    await ctx.append(call_id=call, user_id=user, kind='unfinished_topic', item_id='trip',
                     turn_index=1, text='旅行', safe=True)
    await runtime[2].pexpire('voice:session_context:' + call, 1)
    await asyncio.sleep(.02)
    assert not (await ctx.query(call_id=call, user_id=user, turn_index=2)).items
    await ctx.append(call_id=call, user_id=user, kind='unfinished_topic', item_id='trip',
                     turn_index=1, text='旅行', safe=True)
    async with runtime[0]() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call))
        row.status = 'ended'; row.ended_at = datetime.utcnow()
        await db.commit()
    ops = VoiceOpsService(cache=runtime[2], session_factory=runtime[0])
    await ops.end_call(call_id=call, user_id=user)
    assert not await runtime[2].exists('voice:session_context:' + call)
    assert (await ctx.append(call_id=call, user_id=user, kind='candidate', item_id='late',
                            turn_index=3, text='late', safe=True)).status == 'closed'


@pytest.mark.asyncio
@pytest.mark.parametrize('items', ['[{"text":"private"}]',
    '{"x":{"turn_index":1,"visible_from":1,"text":"private","kind":"turn","id":"1"}}'])
async def test_corrupt_cache_fails_closed_and_can_be_cleaned(runtime, items):
    ctx, call, user = await context(runtime)
    await runtime[2].set('voice:session_context:' + call,
        '{"v":1,"user_id":"1","items":' + items + '}')
    result = await ctx.query(call_id=call, user_id=user, turn_index=2)
    assert result.status == 'corrupt' and not result.items
    assert await ctx.recalled(call_id=call, user_id=user, turn_index=2, topic='trip') == ('corrupt', False)
    assert (await ctx.append(call_id=call, user_id=user, kind='candidate', item_id='x',
                            turn_index=2, text='content', safe=True)).status == 'corrupt'
    await runtime[2].set('voice:session_context:' + call, '{bad json')
    assert (await ctx.cleanup(call_id=call, user_id=user)).status == 'ok'
    assert not await runtime[2].exists('voice:session_context:' + call)


@pytest.mark.asyncio
async def test_topic_dedupe_and_actual_reconnecting_call(runtime):
    ctx, call, user = await context(runtime)
    await ctx.append(call_id=call, user_id=user, kind='recalled_topic', item_id='trip',
                     turn_index=1, text='旅行', safe=True)
    async with runtime[0]() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call))
        row.status = 'reconnecting'
        await db.commit()
    assert await ctx.recalled(call_id=call, user_id=user, turn_index=2, topic='trip') == ('ok', True)
    assert await ctx.recalled(call_id=call, user_id=user, turn_index=2, topic='food') == ('ok', False)


@pytest.mark.asyncio
async def test_stalled_cache_does_not_block_turn_processing(runtime):
    ctx, call, user = await context(runtime)
    class Stalled:
        async def eval(self, *args):
            await asyncio.sleep(10)
    ctx.cache = Stalled()
    result = await asyncio.wait_for(ctx.append(call_id=call, user_id=user, kind='candidate',
        item_id='x', turn_index=1, text='content', safe=True), timeout=3)
    assert result.status == 'unavailable'
