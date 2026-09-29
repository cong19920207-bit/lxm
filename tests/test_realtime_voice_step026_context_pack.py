import asyncio
import hashlib
import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest


def api():
    name = 'backend.services.realtime_voice_context_pack_service'
    assert importlib.util.find_spec(name), 'STEP-026 compiler missing'
    from backend.services import realtime_voice_context_pack_service
    return realtime_voice_context_pack_service


def persona():
    value = {'background': '稳定人格' * 2000, 'language_style': '自然'}
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return raw, {'config_key': 'persona', 'version': 8, 'content_sha256': 'sha256:' + hashlib.sha256(raw.encode()).hexdigest()}


def settings():
    from backend.constants.realtime_voice_config import get_default_voice_call_script
    return get_default_voice_call_script()['context_pack']


class Source:
    async def load(self, section, user_id, now):
        return {'schedule': '今天有会议' * 200, 'recent_dialog': 'user:最近很忙\nassistant:辛苦了\n'*100,
                'voice_history': '上次聊到工作压力',
                'memories': [{'id': str(i), 'content': '压缩记忆'+str(i)*100, 'score': i/10,
                              'quality': .8, 'updated_at': now.isoformat(), 'source_channel': 'voice' if i%2 else 'text'} for i in range(10)]}[section]


@pytest.mark.asyncio
async def test_pack_budgets_and_persona_reference_are_frozen():
    m=api(); raw,ref=persona(); cfg=settings(); barrier=asyncio.Event()
    result=await m.build_context_pack(user_id=1, persona_raw=raw, persona_ref=ref, settings=cfg,
        source=Source(), salutation='小林', relationship='朋友', now=datetime.now(timezone.utc), ready_barrier=barrier)
    assert len(result.persona)<=5000 and len(result.dynamic)<=2000
    assert result.metadata['recent_dialog_chars']<=800 and result.metadata['memory_count']<=5
    assert barrier.is_set() and result.metadata['persona_ref']['version']==8
    ref['version']=9; cfg['dynamic_max_chars']=10
    assert result.metadata['persona_ref']['version']==8 and len(result.dynamic)>10
    assert '稳定人格' not in repr(result) and '压缩记忆' not in repr(result)


@pytest.mark.asyncio
async def test_timeout_nonempty_fallback_releases_barrier_without_waiting_forever():
    m=api(); raw,ref=persona(); cfg=settings(); cfg['build_budget_ms']=20
    class Slow(Source):
        async def load(self,*args): await asyncio.sleep(10)
    barrier=asyncio.Event()
    result=await asyncio.wait_for(m.build_context_pack(user_id=1,persona_raw=raw,persona_ref=ref,
        settings=cfg,source=Slow(),salutation='你',relationship='朋友',now=datetime.now(timezone.utc),ready_barrier=barrier),.3)
    assert result.degraded and barrier.is_set()
    assert all(word in result.dynamic for word in ['朋友','你','当前时间'])


def test_memory_ranking_does_not_use_source_channel():
    m=api(); now=datetime.now(timezone.utc)
    rows=[dict(id='a',content='A',score=.9,quality=.8,updated_at=now.isoformat(),source_channel='voice'),
          dict(id='b',content='B',score=.9,quality=.8,updated_at=now.isoformat(),source_channel='text')]
    before=m.select_memories(rows,limit=5,now=now,lookback_days=30)
    rows[0]['source_channel'],rows[1]['source_channel']='text','voice'
    after=m.select_memories(rows,limit=5,now=now,lookback_days=30)
    assert [x['id'] for x in before]==[x['id'] for x in after]
    assert before[0]['rank_score']==before[1]['rank_score']


@pytest.mark.asyncio
async def test_source_failure_uses_minimum_not_partial_unreliable_pack():
    m=api(); raw,ref=persona()
    class Failed(Source):
        async def load(self,*args): raise RuntimeError('private sentinel')
    b=asyncio.Event()
    r=await m.build_context_pack(user_id=1,persona_raw=raw,persona_ref=ref,settings=settings(),source=Failed(),
        salutation='你',relationship='朋友',now=datetime.now(timezone.utc),ready_barrier=b)
    assert r.degraded and b.is_set() and 'sentinel' not in repr(r)


@pytest.mark.asyncio
async def test_persona_hash_mismatch_fails_without_claiming_ready():
    m=api(); raw,ref=persona(); b=asyncio.Event()
    with pytest.raises(m.ContextPackError):
        await m.build_context_pack(user_id=1,persona_raw=raw+' ',persona_ref=ref,settings=settings(),source=Source(),
            salutation='你',relationship='朋友',now=datetime.now(timezone.utc),ready_barrier=b)
    assert not b.is_set()


@pytest.mark.asyncio
async def test_malformed_memory_timestamp_cannot_strand_ready_barrier():
    m=api(); raw,ref=persona(); barrier=asyncio.Event()
    class Bad(Source):
        async def load(self,section,user_id,now):
            if section=='memories':
                return [dict(id='bad',content='fact',score=.9,quality=.8,updated_at=123)]
            return await super().load(section,user_id,now)
    r=await m.build_context_pack(user_id=1,persona_raw=raw,persona_ref=ref,settings=settings(),source=Bad(),
        salutation='你',relationship='朋友',now=datetime.now(timezone.utc),ready_barrier=barrier)
    assert barrier.is_set() and r.dynamic


@pytest.mark.asyncio
async def test_oversized_source_candidates_use_bounded_minimum_pack():
    m=api(); raw,ref=persona(); barrier=asyncio.Event(); cfg=settings(); cfg['build_budget_ms']=20
    class Huge(Source):
        async def load(self,section,user_id,now):
            if section=='memories':
                return [dict(id='a',content='fact',score=.9,quality=.8,updated_at=now.isoformat())]*100000
            return await super().load(section,user_id,now)
    r=await asyncio.wait_for(m.build_context_pack(user_id=1,persona_raw=raw,persona_ref=ref,settings=cfg,source=Huge(),
        salutation='你',relationship='朋友',now=datetime.now(timezone.utc),ready_barrier=barrier),.1)
    assert r.degraded and barrier.is_set() and r.metadata['memory_count']==0
