"""Keep immutable text bodies while hiding their user-facing version."""
from alembic import op
import sqlalchemy as sa
revision='v9t_pet_text_visibility_001'
down_revision='v9s_pet_health_001'
branch_labels=None
depends_on=None
def upgrade():
 op.create_table('pet_text_visibility',sa.Column('text_id',sa.String(36),sa.ForeignKey('pet_formal_text.id',ondelete='RESTRICT'),primary_key=True),sa.Column('pet_id',sa.String(36),sa.ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False),sa.Column('hidden',sa.Boolean(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.Column('operation_id',sa.String(64),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4',mysql_collate='utf8mb4_bin')
def downgrade():op.drop_table('pet_text_visibility')
