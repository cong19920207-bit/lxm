"""M2 approved quota slice duration and Shanghai billing date.

Legacy rows retain NULL; no inferred historical usage or date is backfilled.
"""
import sqlalchemy as sa
from alembic import op

revision = "v8d_voice_usage_slices_001"
down_revision = "v8c_voice_schema_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("voice_usage_ledger", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.add_column("voice_usage_ledger", sa.Column("quota_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("voice_usage_ledger", "quota_date")
    op.drop_column("voice_usage_ledger", "duration_seconds")
