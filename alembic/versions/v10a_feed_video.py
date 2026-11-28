"""Versioned feed video edits, recoverable outputs and per-post pin order."""
from alembic import context, op
import sqlalchemy as sa

revision = "v10a_feed_video_001"
down_revision = "v9z_feed_comment_idem_001"
branch_labels = None
depends_on = None


def upgrade():
    # MySQL DDL auto-commits. Resume after any completed column, table or index.
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names()) if inspector else set()
    columns = {c["name"] for c in inspector.get_columns("feed_post")} if inspector else set()
    if "media_kind" not in columns:
        op.add_column("feed_post", sa.Column("media_kind", sa.String(16), nullable=False, server_default="image_text"))
    if "post_version" not in columns:
        op.add_column("feed_post", sa.Column("post_version", sa.Integer(), nullable=False, server_default="1"))

    if "feed_pin_order" not in existing:
        op.create_table('feed_pin_order',
            sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
            sa.Column('version', sa.Integer(), server_default='0', nullable=False),
            sa.CheckConstraint('id = 1', name='ck_feed_pin_singleton'),
            sa.PrimaryKeyConstraint('id')
        )
    if "feed_pin" not in existing:
        op.create_table('feed_pin',
            sa.Column('post_id', sa.Integer(), autoincrement=False, nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['post_id'], ['feed_post.id'], ),
            sa.PrimaryKeyConstraint('post_id'),
            sa.UniqueConstraint('position')
        )
    if "feed_video_edit" not in existing:
        op.create_table('feed_video_edit',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('admin_id', sa.Integer(), nullable=False),
            sa.Column('base_post_version', sa.Integer(), nullable=False),
            sa.Column('edit_version', sa.Integer(), server_default='1', nullable=False),
            sa.Column('state', sa.String(length=24), nullable=False),
            sa.Column('content_text', sa.Text(), nullable=False),
            sa.Column('scheduled_publish_time', sa.DateTime(), nullable=True),
            sa.Column('frame_mode', sa.String(length=16), nullable=False),
            sa.Column('frame_position', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_edited_at', sa.DateTime(), nullable=False),
            sa.Column('abandoned_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['post_id'], ['feed_post.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('post_id', 'id', name='uq_feed_edit_owner')
        )
    if "feed_video_task" not in existing:
        op.create_table('feed_video_task',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('edit_id', sa.Integer(), nullable=False),
            sa.Column('media_version', sa.String(length=36), nullable=False),
            sa.Column('state', sa.String(length=24), nullable=False),
            sa.Column('attempt', sa.Integer(), server_default='0', nullable=False),
            sa.Column('received_at', sa.DateTime(), nullable=True),
            sa.Column('first_failed_at', sa.DateTime(), nullable=True),
            sa.Column('source_path', sa.String(length=512), nullable=True),
            sa.Column('master_path', sa.String(length=512), nullable=True),
            sa.Column('master_sha256', sa.String(length=64), nullable=True),
            sa.Column('master_verified_at', sa.DateTime(), nullable=True),
            sa.Column('failure_reason', sa.String(length=512), nullable=True),
            sa.ForeignKeyConstraint(['post_id', 'edit_id'], ['feed_video_edit.post_id', 'feed_video_edit.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('media_version'),
            sa.UniqueConstraint('post_id', 'media_version', name='uq_feed_task_owner_version')
        )
    if not inspector or "ix_feed_task_queue" not in {i["name"] for i in inspector.get_indexes("feed_video_task")}:
        op.create_index('ix_feed_task_queue', 'feed_video_task', ['state', 'received_at', 'id'], unique=False)
    if "feed_video_asset" not in existing:
        op.create_table('feed_video_asset',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('media_version', sa.String(length=36), nullable=False),
            sa.Column('kind', sa.String(length=16), nullable=False),
            sa.Column('variant', sa.String(length=36), server_default='default', nullable=False),
            sa.Column('object_key', sa.String(length=255), nullable=False),
            sa.Column('public_url', sa.String(length=2048), nullable=True),
            sa.Column('mime_type', sa.String(length=64), nullable=False),
            sa.Column('width', sa.Integer(), nullable=False),
            sa.Column('height', sa.Integer(), nullable=False),
            sa.Column('size_bytes', sa.BigInteger(), nullable=False),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('sha256', sa.String(length=64), nullable=False),
            sa.Column('stream_info', sa.JSON(), nullable=True),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('unreferenced_at', sa.DateTime(), nullable=True),
            sa.CheckConstraint("kind IN ('cover_small','cover_large') OR variant = 'default'", name='ck_feed_asset_variant'),
            sa.CheckConstraint("kind IN ('video','preview','cover_small','cover_large')", name='ck_feed_asset_kind'),
            sa.ForeignKeyConstraint(['media_version'], ['feed_video_task.media_version'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('media_version', 'kind', 'variant', name='uq_feed_asset_variant'),
            sa.UniqueConstraint('object_key')
        )
    if not inspector or "ix_feed_asset_cleanup" not in {i["name"] for i in inspector.get_indexes("feed_video_asset")}:
        op.create_index('ix_feed_asset_cleanup', 'feed_video_asset', ['unreferenced_at'], unique=False)
    if "feed_video_selection" not in existing:
        op.create_table('feed_video_selection',
            sa.Column('edit_id', sa.Integer(), autoincrement=False, nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('media_version', sa.String(length=36), nullable=False),
            sa.Column('cover_variant', sa.String(length=36), server_default='default', nullable=False),
            sa.ForeignKeyConstraint(['post_id', 'edit_id'], ['feed_video_edit.post_id', 'feed_video_edit.id'], ),
            sa.ForeignKeyConstraint(['post_id', 'media_version'], ['feed_video_task.post_id', 'feed_video_task.media_version'], ),
            sa.PrimaryKeyConstraint('edit_id')
        )
    if "feed_publication" not in existing:
        op.create_table('feed_publication',
            sa.Column('post_id', sa.Integer(), autoincrement=False, nullable=False),
            sa.Column('edit_id', sa.Integer(), nullable=False),
            sa.Column('submitted_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['edit_id'], ['feed_video_selection.edit_id'], ),
            sa.ForeignKeyConstraint(['post_id', 'edit_id'], ['feed_video_edit.post_id', 'feed_video_edit.id'], ),
            sa.PrimaryKeyConstraint('post_id')
        )
    op.execute("INSERT INTO feed_pin_order (id, version) SELECT 1, 0 WHERE NOT EXISTS (SELECT 1 FROM feed_pin_order WHERE id=1)")


def downgrade():
    op.drop_table("feed_publication")
    op.drop_table("feed_video_selection")
    op.drop_table("feed_video_asset")
    op.drop_table("feed_video_task")
    op.drop_table("feed_video_edit")
    op.drop_table("feed_pin")
    op.drop_table("feed_pin_order")
    op.drop_column("feed_post", "post_version")
    op.drop_column("feed_post", "media_kind")
