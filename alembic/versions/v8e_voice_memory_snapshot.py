"""Approved STEP-029 durable extraction; legacy rows remain NULL."""
import sqlalchemy as sa
from alembic import op

revision = 'v8e_voice_memory_snapshot_001'
down_revision = 'v8d_voice_usage_slices_001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('voice_memory_job', sa.Column('extraction_snapshot', sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    op.drop_column('voice_memory_job', 'extraction_snapshot')
