import asyncio,hashlib,json
from datetime import datetime,timezone
from uuid import uuid4
import pytest,pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
import backend.models
from backend.database import Base
from backend.models.user import User
from backend.models.admin_config import AdminConfig
from backend.models.relationship import Relationship
from backend.models.life_plan import LifePlan
from backend.models.conversation_log import ConversationLog
from backend.models.memory import Memory
from backend.models.realtime_voice import VoiceCall
from backend.constants.realtime_voice_config import get_default_voice_call_config,get_default_voice_call_script
from backend.services.realtime_voice_context_source_service import DatabaseVoiceContextSource,prepare_voice_context

NOW=datetime(2026,9,9,6,tzinfo=timezone.utc)
@pytest_asyncio.fixture
async def factory():
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[m.__table__ for m in (User,AdminConfig,Relationship,LifePlan,ConversationLog,Memory,VoiceCall)])
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async with factory() as db:
        db.add_all([User(id=1,username='ctx',password_hash='unused'),User(id=2,username='other',password_hash='unused')]);await db.commit()
    yield factory
    await engine.dispose()

@pytest.mark.asyncio
async def test_real_database_sources_are_user_scoped_and_context_uses_pinned_persona(factory):
    raw=json.dumps(dict(background='已发布背景',personality='温和',emotion_preference='平和',language_style='自然',behavior_pattern='尊重'),ensure_ascii=False)
    ref=dict(config_key='persona',version=1,content_sha256='sha256:'+hashlib.sha256(raw.encode()).hexdigest())
    async with factory() as db:
        db.add_all([AdminConfig(config_key='persona',version=1,config_value=raw,is_active=False,is_draft=False),
                    AdminConfig(config_key='persona',version=2,config_value='新版本不能热切',is_active=True,is_draft=False),
                    Relationship(user_id=1,level=1,growth_value=5,user_hobby_name='小林',relation_description='朋友'),
                    LifePlan(plan_date=NOW.date(),scenes=[{'description':'散步'}],gen_status='ready'),
                    ConversationLog(user_id=1,role='user',content='聊过旅行',delivery_status='delivered',sort_seq=1),
                    ConversationLog(user_id=2,role='user',content='OTHER_USER_SECRET',delivery_status='delivered',sort_seq=2),
                    ConversationLog(user_id=1,role='user',content='UNDELIVERED_SECRET',delivery_status='failed_error',sort_seq=3),
                    Memory(user_id=1,content='喜欢海边',importance_score=4,source='auto',dashvector_id='mem_1',updated_at=NOW.replace(tzinfo=None))])
        await db.commit()
    async def search(query,user):
        assert user==1 and query=='聊过旅行'
        return [('user',{'id':'mem_1','score':.95,'fields':{'user_id':1}}),('user',{'id':'foreign','score':1,'fields':{'user_id':2,'content':'OTHER_VECTOR_SECRET'}})]
    source=DatabaseVoiceContextSource(factory,memory_search=search)
    call=VoiceCall(call_id=str(uuid4()),user_id=1,config_snapshot={'resolved_config':get_default_voice_call_config(ref),'resolved_script':get_default_voice_call_script()})
    barrier=asyncio.Event()
    pack=await prepare_voice_context(call=call,session_factory=factory,now=NOW,barrier=barrier,source=source)
    assert barrier.is_set() and '已发布背景' in pack.persona and '新版本' not in pack.persona
    assert '小林' in pack.dynamic and '喜欢海边' in pack.dynamic and '聊过旅行' in pack.dynamic
    assert 'SECRET' not in pack.dynamic and pack.metadata['memory_count']==1
    assert len(pack.dynamic)<=2000 and len(pack.persona)<=5000

@pytest.mark.asyncio
async def test_unknown_legacy_vector_time_is_not_fabricated(factory):
    from backend.utils.character_knowledge_validate import build_doc_id
    async def search(query,user):return [('user',{'id':build_doc_id('user','偏好-旅行-地点',1),'score':1,'fields':{'user_id':1,'content':'不能伪造时间'}})]
    source=DatabaseVoiceContextSource(factory,memory_search=search)
    rows=await source.load('memories',1,NOW)
    assert len(rows)==1 and rows[0]['updated_at'] is None


@pytest.mark.asyncio
async def test_persona_lookup_spends_shared_budget_and_slow_sources_release_barrier(factory,monkeypatch):
    from contextlib import asynccontextmanager
    import backend.services.realtime_voice_context_source_service as service
    raw=json.dumps({'background':'人格'})
    ref=dict(config_key='persona',version=1,content_sha256='sha256:'+hashlib.sha256(raw.encode()).hexdigest())
    async with factory() as db:
        db.add(AdminConfig(config_key='persona',version=1,config_value=raw,is_active=True,is_draft=False));await db.commit()
    script=get_default_voice_call_script();script['context_pack']['build_budget_ms']=80
    call=VoiceCall(call_id=str(uuid4()),user_id=1,config_snapshot={'resolved_config':get_default_voice_call_config(ref),'resolved_script':script})
    @asynccontextmanager
    async def delayed():
        await asyncio.sleep(.03)
        async with factory() as db:yield db
    budgets=[];original=service.build_context_pack
    async def build(**kw):budgets.append(kw['settings']['build_budget_ms']);return await original(**kw)
    monkeypatch.setattr(service,'build_context_pack',build)
    class Slow:
        def __init__(self):self.cancelled=0
        async def load(self,*args,**kwargs):
            try:await asyncio.sleep(10)
            finally:self.cancelled+=1
    source=Slow();barrier=asyncio.Event()
    pack=await prepare_voice_context(call=call,session_factory=delayed,now=NOW,barrier=barrier,source=source)
    assert 0<budgets[0]<=50 and script['context_pack']['build_budget_ms']==80
    assert pack.metadata['degradation_reason']=='timeout'
    await asyncio.sleep(0)  # Compiler releases the barrier without awaiting slow-source cleanup.
    assert barrier.is_set() and source.cancelled==4 and '当前时间' in pack.dynamic

@pytest.mark.asyncio
async def test_deleted_persona_history_preserves_pack_and_persisted_version_hash(factory):
    from sqlalchemy import select,delete
    raw=json.dumps({'background':'历史人格正文'},ensure_ascii=False)
    ref={'config_key':'persona','version':1,'content_sha256':'sha256:'+hashlib.sha256(raw.encode()).hexdigest()}
    async with factory() as db:
        db.add(AdminConfig(config_key='persona',version=1,config_value=raw,is_active=False,is_draft=False))
        call=VoiceCall(call_id=str(uuid4()),user_id=1,initiated_by='user',status='deciding',summary_status='pending',
            config_snapshot={'resolved_config':get_default_voice_call_config(ref),'resolved_script':get_default_voice_call_script()},
            capability_snapshot={},transcript_retention_days=180,generated_retention_days=30)
        db.add(call);await db.commit()
    class Empty:
        async def load(self,section,*args):return [] if section=='memories' else ''
    pack=await prepare_voice_context(call=call,session_factory=factory,now=NOW,barrier=asyncio.Event(),source=Empty())
    before=(pack.persona,pack.dynamic,repr(pack.metadata))
    async with factory() as db:
        await db.execute(delete(AdminConfig).where(AdminConfig.config_key=='persona',AdminConfig.version==1))
        db.add(AdminConfig(config_key='persona',version=2,config_value='新人格',is_active=True,is_draft=False));await db.commit()
    async with factory() as db:
        saved=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call.call_id))
        assert saved.config_snapshot['resolved_config']['persona_ref']==ref
        assert '历史人格正文' not in json.dumps(saved.config_snapshot,ensure_ascii=False)
        current=await db.scalar(select(AdminConfig).where(AdminConfig.is_active.is_(True)))
        assert current.version!=ref['version']
        assert 'sha256:'+hashlib.sha256(current.config_value.encode()).hexdigest()!=ref['content_sha256']
    assert (pack.persona,pack.dynamic,repr(pack.metadata))==before
    assert pack.metadata['persona_ref']==ref
