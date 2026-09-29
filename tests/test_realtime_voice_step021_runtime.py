"""Three-source pagination on disposable real MySQL; no business database access."""
import asyncio
import os
from datetime import datetime
import pytest
import pytest_asyncio
from sqlalchemy import select
from backend.database import Base
from backend.models.user import User
from backend.models.realtime_voice import VoiceCall
from backend.models.conversation_log import ConversationLog
from backend.models.agent_message import AgentMessage
from backend.models.user_timeline_seq import UserTimelineSeq
from backend.services.timeline_seq_service import allocate_sort_seq
from backend.services.timeline_read_service import get_timeline
from backend.services.realtime_voice_card_service import stage_call_card
from tests.test_realtime_voice_m4_runtime import containers,runtime

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL/Redis opt-in')

@pytest_asyncio.fixture
async def card_runtime(runtime):
    factory,call,cache=runtime
    tables=[m.__table__ for m in (ConversationLog,AgentMessage)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    try:
        yield factory,call
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)

@pytest.mark.asyncio
@pytest.mark.parametrize('existing_sequence',[True,False])
async def test_concurrent_three_sources_fixed_boundary_exact_multiset(card_runtime,existing_sequence):
    factory,call=card_runtime
    # Existing conversation users have an established per-user sequence.
    if existing_sequence:
        async with factory() as db:
            db.add(UserTimelineSeq(user_id=1,next_seq=1));await db.commit()
    now=datetime.utcnow().replace(microsecond=123000)
    async def write(source,index):
        async with factory() as db:
            if source=='call':
                await db.scalar(select(User.id).where(User.id==1).with_for_update())
                row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call).with_for_update())
                row.status='ended';row.ended_at=now;row.duration_seconds=9
                await stage_call_card(db,row)
            else:
                seq=(await allocate_sort_seq(1,1,db))[0]
                row=(ConversationLog(user_id=1,role='user',content=f'text-{index}',sort_seq=seq,created_at=now)
                     if source=='user' else AgentMessage(user_id=1,trigger_type='P0',content=f'agent-{index}',action_score=1,sort_seq=seq,created_at=now))
                db.add(row)
            await db.commit()
            return source,row.id,row.sort_seq
    expected=await asyncio.gather(write('call',0),*(write(source,i) for i in range(10) for source in ('user','agent')))
    async with factory() as db:
        seen=[];cursor=None
        while True:
            page=await get_timeline(1,db,limit=4,cursor=cursor,include_calls=True)
            seen.extend((item['source'],item['id'],item['sort_seq']) for item in page['items'])
            if not page['has_more']:break
            cursor=page['next_cursor']
        assert sorted(seen)==sorted(expected)
        assert len({seq for _,_,seq in seen})==21
        row=await db.scalar(select(VoiceCall));original=row.sort_seq
        row.summary_status='ready';row.call_summary='仅更新原卡片'
        await stage_call_card(db,row);await db.commit()
        assert row.sort_seq==original
