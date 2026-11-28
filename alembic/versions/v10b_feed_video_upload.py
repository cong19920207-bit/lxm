"""Persist idempotent draft creation, input reservations and arrival order."""
from alembic import context, op
import sqlalchemy as sa

revision = "v10b_feed_video_upload_001"
down_revision = "v10a_feed_video_001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names()) if inspector else set()
    if "feed_video_admission" not in tables:
        op.create_table("feed_video_admission",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("last_sequence", sa.BigInteger(), nullable=False, server_default="0"),
            sa.CheckConstraint("id = 1", name="ck_feed_video_admission_singleton"))
    if "feed_video_draft_request" not in tables:
        op.create_table("feed_video_draft_request",
            sa.Column("request_id", sa.String(36), primary_key=True),
            sa.Column("edit_id", sa.Integer(), sa.ForeignKey("feed_video_edit.id"), nullable=False, unique=True),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("request_digest", sa.String(64), nullable=False))
    if "feed_video_upload" not in tables:
        op.create_table("feed_video_upload",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("edit_id", sa.Integer(), sa.ForeignKey("feed_video_edit.id"), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("expected_size", sa.BigInteger(), nullable=False),
            sa.Column("reserved_bytes", sa.BigInteger(), nullable=False),
            sa.Column("state", sa.String(24), nullable=False),
            sa.Column("deadline", sa.DateTime()),
            sa.Column("arrival_sequence", sa.BigInteger(), unique=True),
            sa.Column("received_at", sa.DateTime()),
            sa.Column("source_info", sa.JSON()),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("feed_video_task.id"), unique=True),
            sa.Column("failure_reason", sa.String(200)), sa.Column("unreferenced_at", sa.DateTime()))
    if not inspector or "ix_feed_upload_edit" not in {i["name"] for i in inspector.get_indexes("feed_video_upload")}:
        op.create_index("ix_feed_upload_edit", "feed_video_upload", ["edit_id", "state"])
    op.execute("INSERT INTO feed_video_admission (id,last_sequence) SELECT 1,0 WHERE NOT EXISTS "
               "(SELECT 1 FROM feed_video_admission WHERE id=1)")


def downgrade():
    op.drop_table("feed_video_upload")
    op.drop_table("feed_video_draft_request")
    op.drop_table("feed_video_admission")
