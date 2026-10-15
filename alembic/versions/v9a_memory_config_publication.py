"""Create durable memory configuration publication anchors; no config rewrite."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "v9a_memory_config_publication_001"
down_revision = "v8h_voice_master_switch_001"
branch_labels = None
depends_on = None


def upgrade():
    # This revision exceeds Alembic's legacy VARCHAR(32) ledger. Widen before
    # any application DDL so the actual revision can be committed afterward.
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        offline = op.get_context().as_sql
        inspector = None if offline else sa.inspect(bind)
        if offline or (inspector.has_table("alembic_version") and
                       inspector.get_columns("alembic_version")[0]["type"].length < 128):
            op.alter_column("alembic_version", "version_num", existing_type=sa.String(32),
                            type_=sa.String(128), existing_nullable=False)
    instant = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    uuid = sa.String(36).with_variant(mysql.CHAR(36, charset="ascii", collation="ascii_bin"), "mysql")
    digest = sa.LargeBinary(32).with_variant(mysql.BINARY(32), "mysql")
    op.create_table(
        "memory_config_head",
        sa.Column("config_key", sa.String(100), primary_key=True),
        sa.Column("active_admin_config_id", sa.Integer(), nullable=True),
        sa.Column("active_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", instant, nullable=False),
        sa.CheckConstraint("active_version >= 0 AND revision >= 0", name="ck_memory_config_head_nonnegative"),
        mysql_engine="InnoDB",
    )
    op.create_table(
        "memory_config_publish",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("publish_id", uuid, nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("source_entry", sa.String(64), nullable=False),
        sa.Column("canonical_key", sa.String(100), nullable=False),
        sa.Column("request_digest", digest, nullable=False),
        sa.Column("validated_digest", digest, nullable=True),
        sa.Column("expected_head_revision", sa.BigInteger(), nullable=True),
        sa.Column("commit_state", sa.String(16), nullable=False),
        sa.Column("committed_admin_config_id", sa.Integer(), nullable=True),
        sa.Column("committed_version", sa.BigInteger(), nullable=True),
        *(sa.Column(name, instant, nullable=name not in {"created_at", "observed_at"}) for name in
          ("created_at", "observed_at", "committed_at", "terminal_at", "receipt_until", "tombstone_until")),
        sa.Column("reason", sa.String(64), nullable=True),
        sa.Column("record_revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("lease_owner", uuid, nullable=True),
        sa.Column("lease_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_until", instant, nullable=True),
        sa.UniqueConstraint("admin_id", "publish_id", name="uq_memory_config_publish_actor_id"),
        sa.CheckConstraint("commit_state IN ('accepted','validating','committed','rejected','unknown')",
                           name="ck_memory_config_publish_state"),
        sa.CheckConstraint("record_revision >= 1 AND lease_version >= 0", name="ck_memory_config_publish_revision"),
        sa.CheckConstraint("(commit_state = 'committed' AND committed_admin_config_id IS NOT NULL "
                           "AND committed_version IS NOT NULL) OR (commit_state <> 'committed' "
                           "AND committed_admin_config_id IS NULL AND committed_version IS NULL)",
                           name="ck_memory_config_publish_commit"),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_memory_config_publish_canonical_key", "memory_config_publish", ["canonical_key"])


def downgrade():
    op.drop_index("ix_memory_config_publish_canonical_key", table_name="memory_config_publish")
    op.drop_table("memory_config_publish")
    op.drop_table("memory_config_head")
