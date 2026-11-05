"""References and durable exact-key deletion outbox for private OSS photos."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
revision='v9w_pet_photo_oss_001'
down_revision='v9v_pet_completion_001'
branch_labels=None
depends_on=None
TIME=sa.DateTime().with_variant(mysql.DATETIME(fsp=6),'mysql')
OPTIONS={'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_bin'}
def upgrade():
    op.create_table('pet_photo_asset',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('pet_id',sa.String(36),sa.ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('bucket',sa.String(128),nullable=False),sa.Column('namespace',sa.String(40),nullable=False),
        sa.Column('object_key',sa.String(512),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('mime_type',sa.String(32),nullable=False),sa.Column('size_bytes',sa.Integer(),nullable=False),
        sa.Column('width',sa.Integer(),nullable=False),sa.Column('height',sa.Integer(),nullable=False),
        sa.Column('state',sa.String(24),nullable=False),sa.Column('generation',sa.Integer(),nullable=False),
        sa.Column('expires_at',TIME,nullable=False),sa.Column('lease_until',TIME,nullable=False),
        sa.Column('upload_finished_at',TIME),sa.Column('created_at',TIME,nullable=False),sa.Column('archived_at',TIME),
        sa.UniqueConstraint('object_key',name='uq_pet_photo_object'),**OPTIONS)
    op.create_table('pet_photo_delete_job',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('bucket',sa.String(128),nullable=False),
        sa.Column('namespace',sa.String(40),nullable=False),sa.Column('object_key',sa.String(512),nullable=False),
        sa.Column('state',sa.String(24),nullable=False),sa.Column('reason',sa.String(48),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('generation',sa.Integer(),nullable=False),
        sa.Column('next_check_at',TIME,nullable=False),sa.Column('confirmed_at',TIME),**OPTIONS)
def downgrade():
    op.drop_table('pet_photo_delete_job');op.drop_table('pet_photo_asset')
