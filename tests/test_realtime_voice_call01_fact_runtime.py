import os,importlib.util
from pathlib import Path
import pytest
from sqlalchemy import text
from backend.database import Base
from backend.models.realtime_voice import VoiceFollowupJob
from backend.models.relationship import Relationship
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_call01_fact import (
    test_decision_fact_same_transition_and_replay_immutable as check_fact,
    test_failed_commit_leaves_both_state_and_fact_unchanged as check_rollback,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_fact_migration_and_state_atomicity(runtime,monkeypatch):
    factory=runtime[0]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceFollowupJob.__table__,Relationship.__table__])
    path=Path('alembic/versions/v8f_voice_call01_fact.py')
    spec=importlib.util.spec_from_file_location('call01_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    async with factory.kw['bind'].begin() as conn:
        before=(await conn.execute(text('SELECT id,call_id,status FROM voice_call'))).all()
        def migrate(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.downgrade();migration.upgrade()
        await conn.run_sync(migrate)
        assert (await conn.execute(text('SELECT id,call_id,status FROM voice_call'))).all()==before
        assert (await conn.execute(text('SELECT call01_fallback FROM voice_call'))).scalar() is None
    for target in ('ringing','missed','cancelled'):
        for fallback in (True,False):await check_fact(factory,target,fallback)
    await check_rollback(factory,monkeypatch)
