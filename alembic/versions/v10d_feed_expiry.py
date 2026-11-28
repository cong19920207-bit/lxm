"""Record draft media expiry separately from the operator's last edit."""
from alembic import context, op
import sqlalchemy as sa

revision = "v10d_feed_expiry_001"
down_revision = "v10c_feed_submission_001"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode() or "media_expired_at" not in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("feed_video_edit")
    }:
        op.add_column("feed_video_edit",sa.Column("media_expired_at",sa.DateTime(),nullable=True))


def downgrade():
    op.drop_column("feed_video_edit","media_expired_at")
