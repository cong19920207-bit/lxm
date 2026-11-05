"""Task diagnostics timestamps; legacy timestamps remain unknown."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME
revision='v9u_pet_task_times_001'
down_revision='v9t_pet_text_visibility_001'
branch_labels=None
depends_on=None
def upgrade():
 for name in ('created_at','updated_at'):
  op.add_column('pet_generation_task',sa.Column(name,DATETIME(fsp=6),nullable=True))
 op.add_column('pet_request_attempt',sa.Column('finished_at',DATETIME(fsp=6),nullable=True))
def downgrade():
 op.drop_column('pet_request_attempt','finished_at')
 for name in ('updated_at','created_at'):op.drop_column('pet_generation_task',name)
