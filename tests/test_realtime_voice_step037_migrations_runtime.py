"""P1 v8a-v8g Alembic roundtrip on a synthetic pre-P1 MySQL baseline."""
import json
import os
import time
from collections import Counter
from datetime import datetime

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext

import backend.config
from backend.database import Base
from backend.models.realtime_voice import VOICE_TABLE_NAMES
from tests.test_realtime_voice_m4_runtime import containers

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='disposable migration drill')


def test_p1_alembic_chain_roundtrip_preserves_legacy_rows(containers, monkeypatch):
    url, _ = containers
    url = url.set(drivername='mysql+pymysql')
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool, hide_parameters=True)
    try:
        for attempt in range(60):
            try:
                with engine.connect() as conn:
                    conn.execute(sa.text('SELECT 1'))
                break
            except sa.exc.OperationalError:
                if attempt == 59:
                    raise RuntimeError('isolated migration database did not start') from None
                time.sleep(.5)
        assert sa.inspect(engine).get_table_names() == []
        legacy = [t for t in Base.metadata.sorted_tables if t.name not in VOICE_TABLE_NAMES]
        Base.metadata.create_all(engine, tables=legacy)
        # Build a pre-P1 fixture, not a production backup or historical snapshot.
        with engine.begin() as conn:
            conn.execute(sa.text('ALTER TABLE admin_config DROP COLUMN draft_revision'))
            conn.execute(sa.text('ALTER TABLE relationship_growth_log DROP INDEX uk_growth_source'))
            for name in ('source_type', 'source_id', 'eligible_seconds', 'business_date'):
                conn.execute(sa.text('ALTER TABLE relationship_growth_log DROP COLUMN ' + name))
            conn.execute(Base.metadata.tables['users'].insert().values(id=1, username='migration-fixture', password_hash='no-login'))
            conn.execute(sa.text("INSERT INTO admin_config (config_key,config_value,version,is_active,is_draft,updated_at) VALUES ('fixture','unchanged',1,1,0,:now)"), {'now': datetime(2026, 9, 20)})
            conn.execute(sa.text("INSERT INTO relationship_growth_log (user_id,action_type,points,created_at) VALUES (1,'fixture',3,:now)"), {'now': datetime(2026, 9, 20)})
        baseline = sa.MetaData()
        baseline.reflect(engine)

        def snapshot():
            with engine.connect() as conn:
                return {name: Counter(json.dumps(dict(row), default=str, sort_keys=True)
                    for row in conn.execute(sa.select(table)).mappings())
                    for name, table in baseline.tables.items()}

        before = snapshot()
        baseline_columns = {name: [c.name for c in table.columns] for name, table in baseline.tables.items()}
        monkeypatch.setattr(backend.config, 'get_mysql_sync_migration_url', lambda: url.render_as_string(hide_password=False))
        config = Config('alembic.ini')
        command.stamp(config, 'v7a_admin_token_ver_001')

        def revision():
            with engine.connect() as conn:
                return MigrationContext.configure(conn).get_current_revision()

        def verify_head():
            assert revision() == 'v8g_voice_evidence_time_001'
            inspector = sa.inspect(engine)
            assert set(inspector.get_table_names()) == set(baseline.tables) | set(VOICE_TABLE_NAMES) | {'alembic_version'}
            for name in VOICE_TABLE_NAMES:
                assert {c['name'] for c in inspector.get_columns(name)} == set(Base.metadata.tables[name].columns.keys())
            for col in inspector.get_columns('voice_capability_evidence'):
                if col['name'] in ('tested_at', 'verified_at', 'expires_at'):
                    assert col['type'].fsp == 6
            with engine.connect() as conn:
                assert conn.scalar(sa.text('SELECT draft_revision FROM admin_config')) is None
                assert tuple(conn.execute(sa.text('SELECT source_type,source_id,eligible_seconds,business_date FROM relationship_growth_log')).one()) == (None,) * 4
            assert snapshot() == before

        command.upgrade(config, 'head')
        verify_head()
        command.upgrade(config, 'head')  # Already applied is a no-op.
        verify_head()
        # Empty new voice tables: this does not claim destructive downgrade is
        # safe after business data has been written. v8g lossy guard has its own test.
        command.downgrade(config, 'v7a_admin_token_ver_001')
        assert revision() == 'v7a_admin_token_ver_001'
        inspector = sa.inspect(engine)
        assert set(inspector.get_table_names()) == set(baseline.tables) | {'alembic_version'}
        assert {name: [c['name'] for c in inspector.get_columns(name)] for name in baseline.tables} == baseline_columns
        assert snapshot() == before
        command.upgrade(config, 'head')
        verify_head()
    finally:
        engine.dispose()
