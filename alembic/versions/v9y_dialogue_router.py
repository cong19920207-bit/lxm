"""Add backwards-compatible routing observations and bounded listing indexes."""
from alembic import op
import sqlalchemy as sa

revision = "v9y_dialogue_router_001"
down_revision = "v9x_pet_drafts_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_generation", sa.Column("memory_router_trace", sa.JSON(), nullable=True))
    op.add_column("memory_diagnostic_run", sa.Column("mode", sa.String(16), nullable=False, server_default="retrieval_only"))
    op.create_index("ix_chat_accepted_generation", "chat_generation", ["accepted_at","generation_id"])
    op.create_index("ix_chat_user_accepted_generation", "chat_generation", ["user_id","accepted_at","generation_id"])


def downgrade():
    op.drop_index("ix_chat_user_accepted_generation", table_name="chat_generation")
    op.drop_index("ix_chat_accepted_generation", table_name="chat_generation")
    op.drop_column("memory_diagnostic_run", "mode")
    op.drop_column("chat_generation", "memory_router_trace")
