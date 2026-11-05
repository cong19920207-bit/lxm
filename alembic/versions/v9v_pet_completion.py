"""Pet resource capability metadata; existing resources keep immutable bytes."""
from alembic import op
import sqlalchemy as sa
revision='v9v_pet_completion_001'
down_revision='v9u_pet_task_times_001'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('pet_resource',sa.Column('capabilities',sa.JSON(),nullable=True))
    op.execute("UPDATE pet_resource SET capabilities = '{}' WHERE capabilities IS NULL")
    with op.batch_alter_table('pet_resource') as batch:
        batch.alter_column('capabilities',existing_type=sa.JSON(),nullable=False)
def downgrade():
    op.drop_column('pet_resource','capabilities')
