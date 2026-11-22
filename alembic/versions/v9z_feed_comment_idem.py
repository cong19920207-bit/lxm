"""Persist account-scoped comment request identity and index the shared rate window."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY

revision = "v9z_feed_comment_idem_001"
down_revision = "v9y_dialogue_router_001"
branch_labels = None
depends_on = None


def upgrade():
    digest = sa.LargeBinary(32).with_variant(BINARY(32), "mysql")
    # MySQL commits each DDL; an interrupted upgrade or create_all on a fresh
    # database may already have installed part of this revision.
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("feed_comment")} if inspector else set()
    indexes = {i["name"]: i for i in inspector.get_indexes("feed_comment")} if inspector else {}
    for name in ("idempotency_key_digest", "request_digest"):
        if name not in columns:
            op.add_column("feed_comment", sa.Column(name, digest, nullable=True))
    for name, keys, unique in (
        ("uq_feed_comment_user_key", ["user_id", "idempotency_key_digest"], True),
        ("ix_feed_comment_owner_post_time", ["user_id", "post_id", "created_at"], False),
    ):
        if name not in indexes:
            op.create_index(name, "feed_comment", keys, unique=unique)
        elif indexes[name]["column_names"] != keys or bool(indexes[name]["unique"]) != unique:
            raise RuntimeError(f"feed_comment index {name} has an incompatible definition")


def downgrade():
    op.drop_index("ix_feed_comment_owner_post_time", table_name="feed_comment")
    op.drop_index("uq_feed_comment_user_key", table_name="feed_comment")
    op.drop_column("feed_comment", "request_digest")
    op.drop_column("feed_comment", "idempotency_key_digest")
