from datetime import datetime
import pytest
import pytest_asyncio
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoicePostprocessJob, VoiceFollowupJob
from backend.models.user_timeline_seq import UserTimelineSeq
from backend.models.conversation_log import ConversationLog
from backend.models.agent_message import AgentMessage
from tests.test_realtime_voice_step028_jobs import storage,memory_env,add_turn


@pytest_asyncio.fixture
async def card_env(memory_env):
    factory,call=memory_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[m.__table__ for m in (UserTimelineSeq,ConversationLog,AgentMessage,VoicePostprocessJob,VoiceFollowupJob)])
    return factory,call


@pytest.mark.asyncio
@pytest.mark.parametrize('status,seconds,meaningful,expected',[
    ('ended',15,True,'pending'),('ended',14,True,'not_applicable'),
    ('ended',30,False,'not_applicable'),('missed',0,False,'not_applicable'),
    ('cancelled',0,False,None),('failed',0,False,None)])
async def test_card_matrix_single_sequence(card_env,status,seconds,meaningful,expected):
    from backend.services.realtime_voice_card_service import stage_call_card
    factory,call=card_env
    if meaningful: await add_turn(factory,call)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status=status;row.duration_seconds=seconds
        if status!='ended': row.connected_at=None
        row.ended_at=datetime.utcnow()
        await stage_call_card(db,row)
        if expected is None:
            assert row.sort_seq is None
        else:
            assert row.summary_status==expected and row.sort_seq==1
            row.summary_status='ready';row.call_summary='一条摘要'
            await stage_call_card(db,row)
            assert row.sort_seq==1 and row.summary_status=='ready'
        await db.commit()


@pytest.mark.asyncio
async def test_h5_three_sources_pagination_and_open_unchanged(card_env):
    from backend.services.realtime_voice_card_service import stage_call_card
    from backend.services.timeline_read_service import get_timeline
    from backend.services.timeline_seq_service import allocate_sort_seq
    factory,call=card_env
    async with factory() as db:
        seq=(await allocate_sort_seq(1,2,db))
        db.add(ConversationLog(user_id=1,role='user',content='文字',sort_seq=seq[0]))
        db.add(AgentMessage(user_id=1,trigger_type='P0',content='主动消息',action_score=1,sort_seq=seq[1]))
        row=await db.scalar(select(VoiceCall));row.status='ended';row.ended_at=datetime.utcnow();row.duration_seconds=12
        await stage_call_card(db,row);await db.commit()
    async with factory() as db:
        first=await get_timeline(1,db,limit=2,include_calls=True)
        second=await get_timeline(1,db,limit=2,cursor=first['next_cursor'],include_calls=True)
        all_items=second['items']+first['items']
        assert [(x['source'],x['sort_seq']) for x in all_items]==[('user',1),('agent',2),('call',3)]
        assert all_items[0]['call_id'] is None and all_items[-1]['call_id']==call
        assert all_items[-1]['summary_status']=='not_applicable'
        from backend.services.open_chat_service import open_get_timeline
        old=await open_get_timeline(1,db,cursor=None,limit=20)
        assert [x['source'] for x in old['items']]==['user','agent']
        assert all(set(x)=={'source','sort_seq','id','content','created_at','emotion_label',
            'is_read','trigger_type','delivery_status','skipped_in_prompt'} for x in old['items'])


@pytest.mark.asyncio
async def test_finalizer_and_missed_transition_create_card_once(storage):
    from datetime import timezone
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from backend.services.realtime_voice_ops_service import VoiceOpsService
    from backend.services.realtime_voice_state_service import transition_call
    cache=StateCache()
    call=await add_call(storage,'connected',cache)
    ops=VoiceOpsService(cache=cache,session_factory=storage)
    await ops.end_call(call_id=call,reason='user_hangup')
    await ops.end_call(call_id=call,reason='system_error')
    missed=await add_call(storage,'ringing',cache)
    async with storage() as db:
        assert await transition_call(db,call_id=missed,expected=('ringing',),target='missed',now=datetime.now(timezone.utc))
        assert not await transition_call(db,call_id=missed,expected=('ringing',),target='missed',now=datetime.now(timezone.utc))
        rows=(await db.scalars(select(VoiceCall).order_by(VoiceCall.sort_seq))).all()
        assert [(row.status,row.sort_seq,row.summary_status) for row in rows]==[('ended',1,'not_applicable'),('missed',2,'not_applicable')]


@pytest.mark.asyncio
async def test_card_sequence_and_state_rollback_atomically(card_env):
    from backend.services.realtime_voice_card_service import stage_call_card
    factory,call=card_env
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='ended';row.duration_seconds=10
        await stage_call_card(db,row)
        await db.rollback()
    async with factory() as db:
        row=await db.scalar(select(VoiceCall))
        assert row.status=='connected' and row.sort_seq is None
        assert await db.scalar(select(UserTimelineSeq)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('text,safety,expected', [('嗯，好的。','passed',False),('下个月准备去旅行','pending',False),('下个月准备去旅行','passed',True)])
async def test_only_meaningful_safe_closed_turns_qualify(card_env,text,safety,expected):
    from backend.models.realtime_voice import VoiceCallTurn
    from backend.services.realtime_voice_card_service import summary_eligible
    factory,call=card_env
    await add_turn(factory,call)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.duration_seconds=15
        turn=await db.scalar(select(VoiceCallTurn));turn.user_text_final=text;turn.user_content_safety_status=safety
        assert await summary_eligible(db,row) is expected


@pytest.mark.parametrize('status,expected', [('missed', '2026-09-20T01:00:00'), ('ended', '2026-09-20T01:00:12')])
def test_card_time_uses_initiation_for_missed_and_end_for_connected(status, expected):
    from types import SimpleNamespace
    from backend.services.realtime_voice_card_service import timeline_call_item
    row = SimpleNamespace(status=status, created_at=datetime(2026,9,20,1), ended_at=datetime(2026,9,20,1,0,12),
        transcript_expires_at=None, sort_seq=3, id=1, call_id='call', duration_seconds=0,
        summary_status='not_applicable', call_summary=None)
    assert timeline_call_item(row)['created_at'] == expected
