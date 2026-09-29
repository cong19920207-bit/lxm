import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import sqlalchemy as sa
from backend.models.admin_config import AdminConfig

@pytest.mark.parametrize('raw,expected', [('{"global":{"enabled":true}}', True), ('{"global":{"enabled":false}}',False), ('{}',False), ('bad',False), ('{"global":{"enabled":1}}',False), (None,False)])
def test_seed_preserves_all_existing_rows_and_is_idempotent(raw, expected):
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/v8h_voice_master_switch.py'
    spec = importlib.util.spec_from_file_location('master_switch_migration', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as db:
        AdminConfig.__table__.create(db)
        if raw is not None:
            db.execute(AdminConfig.__table__.insert(),dict(config_key='voice_call_config',config_value=raw,version=5,is_active=True,is_draft=False))
        db.execute(AdminConfig.__table__.insert(),dict(config_key='voice_call_config',config_value='{"sentinel":"unsaved"}',version=0,draft_revision=7,is_active=False,is_draft=True))
        before = db.execute(sa.text('SELECT * FROM admin_config ORDER BY id')).all()
        module.op = SimpleNamespace(get_bind=lambda:db)
        module.upgrade()
        after = db.execute(sa.text('SELECT * FROM admin_config WHERE config_key != :key ORDER BY id'),{'key':module.KEY}).all()
        assert after == before
        row = db.execute(sa.text('SELECT config_value,version,is_active,is_draft FROM admin_config WHERE config_key=:key'),{'key':module.KEY}).one()
        assert json.loads(row[0]) == {'enabled':expected}
        assert tuple(row[1:]) == (1,1,0)
        all_rows = db.execute(sa.text('SELECT * FROM admin_config ORDER BY id')).all()
        module.upgrade();module.downgrade()
        assert db.execute(sa.text('SELECT * FROM admin_config ORDER BY id')).all() == all_rows
