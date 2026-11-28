"""Track individual committed chat replies from activation onwards."""
from alembic import op
import sqlalchemy as sa

revision = "v10g_chat_unread_001"
down_revision = "v10f_visitor_analytics_001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = None if op.get_context().as_sql else sa.inspect(op.get_bind())
    if not inspector or "reply_is_read" not in {c["name"] for c in inspector.get_columns("conversation_log")}:
        op.add_column("conversation_log", sa.Column("reply_is_read", sa.Boolean(), nullable=True))
    for table, name, field in [
        ("conversation_log", "ix_conversation_reply_unread", "reply_is_read"),
        ("agent_message", "ix_agent_message_unread", "is_read"),
    ]:
        if not inspector or name not in {i["name"] for i in inspector.get_indexes(table)}:
            op.create_index(name, table, ["user_id", field, "sort_seq"])


def downgrade():
    op.drop_index("ix_agent_message_unread", table_name="agent_message")
    op.drop_index("ix_conversation_reply_unread", table_name="conversation_log")
    op.drop_column("conversation_log", "reply_is_read")
