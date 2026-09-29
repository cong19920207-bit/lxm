"""Opt-in isolated MySQL 8 / Redis 7 evidence. Never connects to project data.

RUN_VOICE_M4_RUNTIME=1 .venv-step001/bin/python -m pytest -q <this file>
Creates disposable, uniquely named containers from already-local images only.
"""
import asyncio
import json
import os
import secrets
import subprocess
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select, func, text, event as sql_event
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.database import Base
from backend.models.user import User
from backend.models.admin_user import AdminUser
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_config import AdminConfig
from backend.models.realtime_voice import VoiceCall, VoiceCallTurn, VoiceCrisisRecord, VoiceQuotaAccount, VoiceUsageLedger
from backend.models.user_timeline_seq import UserTimelineSeq
from tests import test_realtime_voice_step024_crisis as checks
from tests.test_realtime_voice_step009_ops import add_call, StateCache

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M4_RUNTIME')!='1', reason='opt-in disposable MySQL/Redis runtime')
DOCKER='/Applications/Docker.app/Contents/Resources/bin/docker'
TABLES=[m.__table__ for m in (User,AdminUser,AdminOperationLog,AdminConfig,VoiceCall,VoiceCallTurn,VoiceCrisisRecord,VoiceQuotaAccount,VoiceUsageLedger,UserTimelineSeq)]


@pytest.fixture(scope='module')
def containers():
    suffix=uuid4().hex[:12]
    names=['codex-m4-mysql-'+suffix,'codex-m4-redis-'+suffix]
    password=secrets.token_hex(24)
    def docker(*args,**kwargs):
        return subprocess.run([DOCKER,*args],check=True,capture_output=True,text=True,**kwargs).stdout.strip()
    started=[]
    try:
        docker('run','-d','--rm','--pull=never','--name',names[0],
            '--label','codex.scope=m4-isolated-validation','-p','127.0.0.1::3306',
            '-e','MYSQL_ROOT_PASSWORD','-e','MYSQL_DATABASE=voice_m4_runtime','mysql:8.0',
            '--default-authentication-plugin=mysql_native_password',
            env={**os.environ,'MYSQL_ROOT_PASSWORD':password})
        started.append(names[0])
        docker('run','-d','--rm','--pull=never','--name',names[1],
            '--label','codex.scope=m4-isolated-validation','-p','127.0.0.1::6379','redis:7-alpine')
        started.append(names[1])
        mysql_port=int(docker('port',names[0],'3306/tcp').rsplit(':',1)[1])
        redis_port=int(docker('port',names[1],'6379/tcp').rsplit(':',1)[1])
        yield URL.create('mysql+asyncmy',username='root',password=password,host='127.0.0.1',port=mysql_port,database='voice_m4_runtime'), redis_port
    finally:
        for name in reversed(started):
            docker('rm','-f',name)


@pytest_asyncio.fixture
async def runtime(containers):
    url,port=containers
    engine=create_async_engine(url,echo=False,hide_parameters=True)
    cache=Redis(host='127.0.0.1',port=port,decode_responses=True)
    try:
        for attempt in range(60):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text('SELECT 1'))
                break
            except Exception as exc:
                if attempt==59:
                    reason = str(exc).replace(url.password, '[redacted]')
                    raise RuntimeError('isolated_mysql_not_ready: '+reason) from None
                await asyncio.sleep(1)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=TABLES)
            await conn.run_sync(Base.metadata.create_all,tables=TABLES)
        await cache.flushdb()  # Own newly created container, never a shared Redis DB.
        factory=async_sessionmaker(engine,expire_on_commit=False)
        async with factory() as db:
            db.add(User(id=1,username='m4-runtime',password_hash='no-login'))
            db.add(AdminUser(id=1,username='m4-runtime',password_hash='no-login',role='super_admin'))
            await db.commit()
        call_id=await add_call(factory,'connected',StateCache())
        yield factory,call_id,cache
    finally:
        await cache.aclose()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('target',['isolation','turn'])
async def test_mysql_write_failure_atomicity(runtime,target,caplog):
    factory,call_id,_=runtime
    await checks.test_failed_transaction_never_leaves_partial_plaintext((factory,call_id),target,caplog)


@pytest.mark.asyncio
async def test_mysql_turn_update_failure_after_isolation(runtime,caplog):
    factory,call_id,_=runtime
    await checks.test_turn_update_failure_after_isolation_insert_rolls_back_both((factory,call_id),caplog)


@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','observer','tech_ops','ops_admin','ai_trainer'])
async def test_mysql_read_audit_rbac(runtime,role):
    factory,call_id,_=runtime
    await checks.test_each_read_audited_only_super_admin_can_read((factory,call_id),role)


@pytest.mark.asyncio
async def test_mysql_audit_failure_is_fail_closed(runtime):
    factory,call_id,_=runtime
    await checks.test_audit_failure_never_returns_body((factory,call_id))


@pytest.mark.asyncio
async def test_mysql_full_page_read_audit(runtime):
    factory,call_id,_=runtime
    await checks.test_full_page_audit_preserves_every_read_identity((factory,call_id))


@pytest.mark.asyncio
@pytest.mark.parametrize('interrupted',[False,True])
async def test_mysql_nonprefix_full_isolation_update(runtime,interrupted):
    factory,call_id,_=runtime
    await checks.test_full_effective_replaces_nonprefix_sentence_ack_isolation((factory,call_id),interrupted)


@pytest.mark.asyncio
async def test_mysql_unplayed_generated_privacy(runtime):
    factory,call_id,_=runtime
    await checks.test_unplayed_generated_crisis_never_enters_ordinary_turn((factory,call_id))


@pytest.mark.asyncio
async def test_mysql_scheduled_expiry(runtime,monkeypatch):
    factory,call_id,_=runtime
    await checks.test_scheduled_expiry_clears_only_due_records((factory,call_id),monkeypatch)


@pytest.mark.asyncio
async def test_real_redis_metrics_and_mysql_concurrent_final(runtime,caplog):
    from backend.services.realtime_voice_turn_service import VoiceTurnService,EffectiveText
    factory,call_id,cache=runtime
    await cache.set('banned_keywords','["blocked"]')
    await cache.set('active_config:crisis_keywords','["PRIVATE_CRISIS"]')
    await cache.set('content_block_count:untouched','17')
    await cache.set('voice.content_safety.sentinel','9')
    signals=[]
    gate=checks.gate_for(cache,signals)
    services=[VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate) for _ in range(2)]
    await asyncio.gather(*(svc.consume(checks.event(call_id,1,'asr_final','blocked '+checks.SENTINEL)) for svc in services))
    svc=services[0]
    await svc.consume(checks.event(call_id,2,'chat_text','blocked '+checks.SENTINEL,reply='r1'))
    await svc.consume(checks.event(call_id,3,'tts_finished',reply='r1'))
    await svc.apply_effective('r1',EffectiveText('blocked '+checks.SENTINEL,'full',completed=True))
    async with factory() as db:
        rows=(await db.scalars(select(VoiceCallTurn))).all()
        assert len(rows)==1 and rows[0].memory_status=='skipped'
        assert rows[0].user_text_final is rows[0].assistant_text_generated is rows[0].assistant_text_effective is None
        records=(await db.scalars(select(VoiceCrisisRecord))).all()
        assert len(records)==2 and all(checks.SENTINEL in r.content_plaintext for r in records)
        assert checks.SENTINEL not in str([r.__dict__ for r in rows])
        assert await db.scalar(select(func.count()).select_from(AdminOperationLog))==0
        for table in TABLES:
            if table.name!='voice_crisis_record':
                assert checks.SENTINEL not in str((await db.execute(select(table))).all()), table.name
    keys=await cache.keys('voice.content_safety.matched:*')
    assert len(keys)==1 and await cache.get(keys[0])=='2'
    assert 0 < await cache.ttl(keys[0]) <= 172800
    assert await cache.keys('content_block_count:*')==['content_block_count:untouched']
    assert await cache.get('content_block_count:untouched')=='17'
    assert await cache.get('voice.content_safety.sentinel')=='9'
    for key in await cache.keys('*'):
        assert checks.SENTINEL not in key and checks.SENTINEL not in str(await cache.get(key))
    assert checks.SENTINEL not in caplog.text
    assert signals==[{'type':'crisis_detected','call_id':call_id}]
