"""Durable health evidence for existing pet scheduler producers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
revision='v9s_pet_health_001'
down_revision='v9r_pet_lifecycle_001'
branch_labels=None
depends_on=None
def upgrade():
 op.create_table('pet_job_health',sa.Column('producer',sa.String(64),primary_key=True),sa.Column('last_run_at',sa.DateTime().with_variant(mysql.DATETIME(fsp=6),'mysql'),nullable=False),sa.Column('last_success_at',sa.DateTime().with_variant(mysql.DATETIME(fsp=6),'mysql')),sa.Column('last_error_at',sa.DateTime().with_variant(mysql.DATETIME(fsp=6),'mysql')),sa.Column('last_error',sa.String(96)),sa.Column('summary',sa.JSON(),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4',mysql_collate='utf8mb4_bin')
def downgrade():op.drop_table('pet_job_health')
