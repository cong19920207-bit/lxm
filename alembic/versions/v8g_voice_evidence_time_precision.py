"""Preserve capability evidence timestamps during exact report round trips."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'v8g_voice_evidence_time_001'
down_revision = 'v8f_voice_call01_fact_001'
branch_labels = None
depends_on = None

COLUMNS = (('tested_at', False), ('verified_at', True), ('expires_at', True))


def upgrade():
    for name, nullable in COLUMNS:
        op.alter_column('voice_capability_evidence', name,
                        existing_type=mysql.DATETIME(), type_=mysql.DATETIME(fsp=6),
                        existing_nullable=nullable)


def downgrade():
    # MySQL DDL commits implicitly. Check every column before the first ALTER;
    # never silently truncate evidence timestamps and invalidate their identity.
    has_fraction = op.get_bind().execute(sa.text(
        'SELECT 1 FROM voice_capability_evidence WHERE '
        'MICROSECOND(tested_at) <> 0 OR MICROSECOND(verified_at) <> 0 '
        'OR MICROSECOND(expires_at) <> 0 LIMIT 1')).first()
    if has_fraction:
        raise RuntimeError('Evidence timestamp precision cannot be reduced without data loss')
    for name, nullable in COLUMNS:
        op.alter_column('voice_capability_evidence', name,
                        existing_type=mysql.DATETIME(fsp=6), type_=mysql.DATETIME(),
                        existing_nullable=nullable)
