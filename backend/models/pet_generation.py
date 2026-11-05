"""Generation task lifecycle and immutable attempt ownership fences."""
from datetime import datetime
from sqlalchemy import String,Integer,ForeignKey,JSON,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS,new_id,utcnow
PET_GENERATION_TABLE_NAMES=frozenset({'pet_generation_task'})
class PetGenerationTask(Base):
 __tablename__='pet_generation_task'
 __table_args__=(UniqueConstraint('pet_id','business_key',name='uq_pet_generation_business'),TABLE_OPTIONS)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
 user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
 business_key:Mapped[str]=mapped_column(String(128),nullable=False)
 kind:Mapped[str]=mapped_column(String(32),nullable=False)
 origin:Mapped[str]=mapped_column(String(16),nullable=False)
 absence_id:Mapped[str|None]=mapped_column(ForeignKey('pet_absence.id',ondelete='RESTRICT'))
 return_id:Mapped[str|None]=mapped_column(String(36))
 source_ids:Mapped[list]=mapped_column(JSON,nullable=False)
 coverage_start:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 coverage_end:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 expires_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 pet_data_version:Mapped[int]=mapped_column(Integer,nullable=False)
 state:Mapped[str]=mapped_column(String(24),default='queued',nullable=False)
 generation:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 owner:Mapped[str|None]=mapped_column(String(96))
 lease_until:Mapped[datetime|None]=mapped_column(UTC_TIME)
 attempt_id:Mapped[str|None]=mapped_column(ForeignKey('pet_request_attempt.id',ondelete='RESTRICT'))
 configuration:Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
 result:Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
 reason:Mapped[str|None]=mapped_column(String(96))

 created_at:Mapped[datetime|None]=mapped_column(UTC_TIME,default=utcnow)
 updated_at:Mapped[datetime|None]=mapped_column(UTC_TIME,default=utcnow,onupdate=utcnow)
