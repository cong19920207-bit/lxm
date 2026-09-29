"""Real migration on disposable MySQL, including refusal of a lossy downgrade."""
import importlib.util
import os
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_realtime_voice_m4_runtime import containers, runtime

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME') != '1', reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_upgrade_exact_roundtrip_and_lossless_only_downgrade(runtime):
    factory, *_ = runtime
    path = Path('alembic/versions/v8g_voice_evidence_time_precision.py')
    spec = importlib.util.spec_from_file_location('precision_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = factory.kw['bind']
    async with engine.begin() as db:
        await db.execute(text('CREATE TABLE voice_capability_evidence ('
            'id INT PRIMARY KEY, marker VARCHAR(32) NOT NULL, tested_at DATETIME NOT NULL, '
            'verified_at DATETIME NULL, expires_at DATETIME NULL)'))
        await db.execute(text("INSERT INTO voice_capability_evidence VALUES "
            "(1, 'unchanged', '2026-09-20 01:02:03', NULL, NULL)"))

    def run(connection, operation):
        with Operations.context(MigrationContext.configure(connection)):
            operation()

    async def precisions(db):
        values = (await db.execute(text('SELECT COLUMN_NAME, DATETIME_PRECISION FROM information_schema.COLUMNS '
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='voice_capability_evidence' "
            "AND COLUMN_NAME IN ('tested_at','verified_at','expires_at')"))).all()
        return dict(values)

    async with engine.begin() as db:
        await db.run_sync(run, migration.upgrade)
        assert await precisions(db) == dict.fromkeys(('tested_at','verified_at','expires_at'), 6)
        old = (await db.execute(text('SELECT marker,tested_at,verified_at,expires_at FROM voice_capability_evidence WHERE id=1'))).one()
        assert tuple(old) == ('unchanged', datetime(2026,9,20,1,2,3), None, None)
        exact = datetime(2026,9,20,1,2,3,123612)
        await db.execute(text('INSERT INTO voice_capability_evidence VALUES (2,:marker,:t,:t,:t)'), {'marker':'fraction','t':exact})
    async with engine.begin() as db:
        row = (await db.execute(text('SELECT tested_at,verified_at,expires_at FROM voice_capability_evidence WHERE id=2'))).one()
        assert tuple(row) == (exact, exact, exact)
        with pytest.raises(RuntimeError, match='data loss'):
            await db.run_sync(run, migration.downgrade)
        assert await precisions(db) == dict.fromkeys(('tested_at','verified_at','expires_at'), 6)
        assert tuple((await db.execute(text('SELECT tested_at,verified_at,expires_at FROM voice_capability_evidence WHERE id=2'))).one()) == (exact, exact, exact)
        # Only delete this test's synthetic row to exercise lossless rollback.
        await db.execute(text('DELETE FROM voice_capability_evidence WHERE id=2'))
    async with engine.begin() as db:
        await db.run_sync(run, migration.downgrade)
        assert await precisions(db) == dict.fromkeys(('tested_at','verified_at','expires_at'), 0)
        assert tuple((await db.execute(text('SELECT marker,tested_at,verified_at,expires_at FROM voice_capability_evidence'))).one()) == tuple(old)
        await db.run_sync(run, migration.upgrade)
        assert await precisions(db) == dict.fromkeys(('tested_at','verified_at','expires_at'), 6)
