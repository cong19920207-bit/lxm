"""Durable attempts and per-layer reservation entries; no Redis accounting."""
from datetime import datetime,date
from sqlalchemy import String,ForeignKey,Integer,Date,JSON,Boolean,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS,new_id
PET_BUDGET_TABLE_NAMES=frozenset({'pet_budget_mutex','pet_request_attempt','pet_budget_entry'})
class PetBudgetMutex(Base):
 __tablename__='pet_budget_mutex'
 __table_args__=(TABLE_OPTIONS,)
 id:Mapped[int]=mapped_column(Integer,primary_key=True)

class PetRequestAttempt(Base):
 __tablename__='pet_request_attempt'
 __table_args__=(TABLE_OPTIONS,)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 request_key:Mapped[str]=mapped_column(String(160),unique=True,nullable=False)
 pet_id:Mapped[str|None]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'))
 user_id:Mapped[int|None]=mapped_column(ForeignKey('users.id',ondelete='RESTRICT'))
 debug_owner:Mapped[int|None]=mapped_column(Integer)
 origin:Mapped[str]=mapped_column(String(16),nullable=False)
 kind:Mapped[str]=mapped_column(String(32),nullable=False)
 absence_id:Mapped[str|None]=mapped_column(ForeignKey('pet_absence.id',ondelete='RESTRICT'))
 return_id:Mapped[str|None]=mapped_column(String(36))
 content_date:Mapped[date|None]=mapped_column(Date)
 reserved_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 submission_date:Mapped[date|None]=mapped_column(Date)
 sent_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 concurrent_until:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 concurrent_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
 state:Mapped[str]=mapped_column(String(20),nullable=False)
 reason:Mapped[str|None]=mapped_column(String(96))
 config_id:Mapped[str]=mapped_column(ForeignKey('pet_config_version.id',ondelete='RESTRICT'),nullable=False)
 result:Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)

 # Null means no result timestamp was observed, including pre-migration attempts.
 finished_at:Mapped[datetime|None]=mapped_column(UTC_TIME)

class PetBudgetEntry(Base):
 __tablename__='pet_budget_entry'
 __table_args__=(UniqueConstraint('attempt_id','layer','bucket',name='uq_pet_budget_entry'),TABLE_OPTIONS)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 attempt_id:Mapped[str]=mapped_column(ForeignKey('pet_request_attempt.id',ondelete='RESTRICT'),nullable=False)
 layer:Mapped[str]=mapped_column(String(16),nullable=False)
 bucket:Mapped[str]=mapped_column(String(128),nullable=False)
 state:Mapped[str]=mapped_column(String(16),nullable=False)
 limit_at_reserve:Mapped[int]=mapped_column(Integer,nullable=False)
