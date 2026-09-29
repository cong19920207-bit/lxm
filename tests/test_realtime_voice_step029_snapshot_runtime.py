"""Isolated MySQL snapshot migration and durable recovery, no external services."""
import importlib.util
import os
from pathlib import Path
import pytest
from sqlalchemy import select, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.models.realtime_voice import VoiceMemoryJob
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step028_runtime import memory_env
from tests.test_realtime_voice_step028_jobs import add_turn, Gate, Writer
from tests.test_realtime_voice_step029_snapshot import (
    test_retry_reuses_first_atoms_and_only_writes_missing,
    test_retry_limit_and_due_time,
    test_exhausted_snapshot_is_cleared_at_source_expiry,
    test_crash_after_snapshot_resumes_without_model,
    test_stale_writer_cannot_cancel_success_after_source_expires,
    test_exhausted_job_does_not_block_later_turn_and_cannot_overwrite_it,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M5_RUNTIME')!='1',reason='isolated MySQL/Redis opt-in')


@pytest.mark.asyncio
async def test_snapshot_migration_preserves_legacy_job(memory_env):
    factory,call=memory_env
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),writer=Writer())
    await service.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    path=Path('alembic/versions/v8e_voice_memory_snapshot.py')
    spec=importlib.util.spec_from_file_location('snapshot_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    async with factory.kw['bind'].begin() as conn:
        before=(await conn.execute(text('SELECT id,call_id,turn_id,status,attempt_count FROM voice_memory_job'))).all()
        def migrate(sync):
            with Operations.context(MigrationContext.configure(sync)):
                module.downgrade();module.upgrade()
        await conn.run_sync(migrate)
        after=(await conn.execute(text('SELECT id,call_id,turn_id,status,attempt_count FROM voice_memory_job'))).all()
        assert after==before
        assert (await conn.execute(text('SELECT extraction_snapshot FROM voice_memory_job'))).scalar() is None
