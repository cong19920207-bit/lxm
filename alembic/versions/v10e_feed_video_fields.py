"""Keep video draft topics and mood separate from the published post."""
from alembic import context, op
import sqlalchemy as sa

revision = "v10e_feed_video_fields_001"
down_revision = "v10d_feed_expiry_001"
branch_labels = None
depends_on = None


def upgrade():
    columns = set() if context.is_offline_mode() else {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("feed_video_edit")
    }
    if "hashtags" not in columns:
        op.add_column("feed_video_edit", sa.Column("hashtags", sa.JSON(), nullable=True))
    if "emotion" not in columns:
        op.add_column("feed_video_edit", sa.Column("emotion", sa.String(20), nullable=False, server_default="平静"))
    # Legacy open edits inherit metadata from their post, including replacement drafts.
    op.execute("""UPDATE feed_video_edit SET
        hashtags = (SELECT hashtags FROM feed_post WHERE id = feed_video_edit.post_id),
        emotion = (SELECT emotion FROM feed_post WHERE id = feed_video_edit.post_id)
        WHERE state = 'draft' AND hashtags IS NULL""")


def downgrade():
    op.drop_column("feed_video_edit", "emotion")
    op.drop_column("feed_video_edit", "hashtags")
