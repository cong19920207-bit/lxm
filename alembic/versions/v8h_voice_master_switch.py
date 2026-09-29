"""Seed the independent switch without rewriting voice bundles or drafts."""
from datetime import datetime
import json
from alembic import op
import sqlalchemy as sa

revision = 'v8h_voice_master_switch_001'
down_revision = 'v8g_voice_evidence_time_001'
branch_labels = None
depends_on = None
KEY = 'voice_call_master_switch'


def upgrade():
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT id FROM admin_config WHERE config_key=:key LIMIT 1'), {'key': KEY}).first():
        return
    rows = connection.execute(sa.text(
        'SELECT config_value FROM admin_config WHERE config_key=:key AND is_active=1 AND is_draft=0'
    ), {'key': 'voice_call_config'}).all()
    enabled = False
    if len(rows) == 1:
        try:
            value = json.loads(rows[0][0])['global']['enabled']
            enabled = value if type(value) is bool else False
        except (ValueError, TypeError, KeyError):
            pass
    connection.execute(sa.text(
        'INSERT INTO admin_config (config_key,config_value,version,draft_revision,is_active,is_draft,updated_by,updated_at) '
        'VALUES (:key,:value,1,NULL,1,0,:actor,:now)'
    ), {'key':KEY, 'value':json.dumps({'enabled':enabled}), 'actor':'migration:v8h', 'now':datetime.utcnow()})


def downgrade():
    # Preserve independent control/history; deleting it would silently disable calls.
    pass
