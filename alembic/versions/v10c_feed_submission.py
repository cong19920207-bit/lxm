"""Persist the original result of an explicit video submission."""
from alembic import op
import sqlalchemy as sa

revision = "v10c_feed_submission_001"
down_revision = "v10b_feed_video_upload_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("feed_video_submission",
        sa.Column("request_id",sa.String(36),primary_key=True),
        sa.Column("edit_id",sa.Integer(),sa.ForeignKey("feed_video_edit.id"),nullable=False,unique=True),
        sa.Column("actor_id",sa.Integer(),nullable=False),
        sa.Column("edit_version",sa.Integer(),nullable=False),
        sa.Column("result",sa.JSON(),nullable=False))


def downgrade():
    op.drop_table("feed_video_submission")
