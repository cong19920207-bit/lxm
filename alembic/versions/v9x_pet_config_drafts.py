"""Retain pet draft revisions and validation status without changing live config."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
revision='v9x_pet_drafts_001'
down_revision='v9w_pet_photo_oss_001'
branch_labels=None
depends_on=None
TIME=sa.DateTime().with_variant(mysql.DATETIME(fsp=6),'mysql')
OPTIONS={'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_bin'}

def upgrade():
    op.add_column('pet_config_head',sa.Column('validation_error',sa.String(512),nullable=True))
    table=op.create_table('pet_config_draft_revision',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('domain',sa.String(24),nullable=False),
        sa.Column('revision',sa.BigInteger(),nullable=False),sa.Column('base_version',sa.BigInteger(),nullable=False),
        sa.Column('content',sa.JSON(),nullable=False),sa.Column('content_digest',sa.String(64),nullable=False),
        sa.Column('source',sa.JSON(),nullable=False),sa.Column('saved_by',sa.Integer()),sa.Column('saved_at',TIME,nullable=False),
        sa.Column('deleted_by',sa.Integer()),sa.Column('deleted_at',TIME),
        sa.UniqueConstraint('domain','revision',name='uq_pet_config_draft_revision'),**OPTIONS)
    op.create_index('ix_pet_config_draft_revision_domain','pet_config_draft_revision',['domain'])
    # Only the latest pre-existing draft is recoverable; older overwritten drafts cannot be reconstructed.
    import json,hashlib,uuid
    bind=op.get_bind()
    for row in bind.execute(sa.text('SELECT domain,draft_revision,draft_base_version,draft,updated_by,updated_at FROM pet_config_head WHERE draft IS NOT NULL')).mappings():
        value=json.loads(row['draft']) if isinstance(row['draft'],str) else row['draft']
        if value is None:continue
        digest=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        bind.execute(table.insert().values(id=str(uuid.uuid4()),domain=row['domain'],revision=row['draft_revision'],base_version=row['draft_base_version'],content=value,content_digest=digest,source={'kind':'migration'},saved_by=row['updated_by'],saved_at=row['updated_at']))

def downgrade():
    op.drop_table('pet_config_draft_revision')
    op.drop_column('pet_config_head','validation_error')
