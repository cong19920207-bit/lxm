"""Approved CALL-01 outcome fact; old calls remain unknown."""
import sqlalchemy as sa
from alembic import op
revision='v8f_voice_call01_fact_001'
down_revision='v8e_voice_memory_snapshot_001'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('voice_call',sa.Column('call01_fallback',sa.Boolean(),nullable=True))


def downgrade():
    op.drop_column('voice_call','call01_fallback')
