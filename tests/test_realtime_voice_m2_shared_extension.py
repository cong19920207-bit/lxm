"""Approved M2 extension: legacy data/config compatibility, bounded parameters."""
import importlib.util
from pathlib import Path
from copy import deepcopy

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.constants.realtime_voice_config import get_default_voice_call_config
from backend.services.realtime_voice_config_service import validate_voice_bundle

REF = {'config_key': 'persona', 'version': 1, 'content_sha256': 'sha256:' + 'a'*64}
DEFAULTS = dict(heartbeat_interval_ms=5000, user_lock_ttl_ms=15000,
                reconnect_timeout_ms=15000, call_ticket_ttl_ms=30000)


def test_new_seed_and_legacy_config_are_both_valid_without_mutation():
    value = get_default_voice_call_config(REF)
    assert value['concurrency'] == dict(global_limit=1, **DEFAULTS)
    value['concurrency'] = {'global_limit': 1}
    before = deepcopy(value)
    assert not validate_voice_bundle('voice_call_config', value)
    assert value == before


def test_legacy_snapshot_resolves_defaults_preserving_published_hash_and_payload():
    from datetime import datetime, timezone
    from backend.constants.realtime_voice_config import get_default_voice_call_script
    from backend.services.realtime_voice_config_service import content_sha256
    from backend.services.realtime_voice_runtime_config_service import LoadedVoiceConfig, VoiceRuntimeBundle, RuntimeConfigSource
    config = get_default_voice_call_config(REF)
    config['concurrency'] = {'global_limit': 2}
    original = deepcopy(config)
    def loaded(key, value):
        return LoadedVoiceConfig(key, 3, 1, content_sha256(value), datetime.now(timezone.utc),
                                 value, RuntimeConfigSource.MYSQL, False)
    bundle = VoiceRuntimeBundle(config=loaded('voice_call_config', config),
                               script=loaded('voice_call_script', get_default_voice_call_script()),
                               mysql_anchors_available=True, persona_anchors=(REF,))
    snapshot = bundle.build_snapshot()
    value = snapshot.config_snapshot
    assert dict(value['resolved_config']['concurrency']) == dict(global_limit=2, **DEFAULTS)
    assert value['config_content_sha256'] == content_sha256(original)
    assert config == original


@pytest.mark.parametrize('patch', [
    {'heartbeat_interval_ms': 999}, {'heartbeat_interval_ms': True},
    {'heartbeat_interval_ms': 10001}, {'user_lock_ttl_ms': 9999},
    {'user_lock_ttl_ms': 60001}, {'heartbeat_interval_ms': 6000},
    {'reconnect_timeout_ms': 0}, {'reconnect_timeout_ms': 60001},
    {'call_ticket_ttl_ms': 4999}, {'call_ticket_ttl_ms': 60001},
])
def test_invalid_connection_parameters_fail_closed(patch):
    value = get_default_voice_call_config(REF)
    value['concurrency'].update(patch)
    assert any(i['field'].startswith('concurrency.') for i in validate_voice_bundle('voice_call_config', value))


def test_migration_preserves_old_rows_and_unique_key_on_upgrade_and_downgrade():
    path = Path('alembic/versions/v8d_voice_usage_slices.py')
    assert path.exists()
    spec = importlib.util.spec_from_file_location('m2_migration', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.down_revision == 'v8c_voice_schema_001'
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE voice_usage_ledger (id INTEGER PRIMARY KEY, call_id TEXT NOT NULL, segment_seq INTEGER NOT NULL, UNIQUE(call_id, segment_seq))')
        conn.exec_driver_sql("INSERT INTO voice_usage_ledger VALUES (1, 'legacy', 1)")
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
            assert conn.exec_driver_sql('SELECT * FROM voice_usage_ledger').one() == (1, 'legacy', 1, None, None)
            assert sa.inspect(conn).get_unique_constraints('voice_usage_ledger')[0]['column_names'] == ['call_id', 'segment_seq']
            mod.downgrade()
        assert conn.exec_driver_sql('SELECT * FROM voice_usage_ledger').one() == (1, 'legacy', 1)
    engine.dispose()
