"""Fenced rule-task work; deliberately separate from future model request tasks."""
from datetime import datetime
from sqlalchemy import BigInteger,ForeignKey,Index,Integer,JSON,String,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS,new_id,utcnow

PET_RULE_JOB_TABLE_NAMES=frozenset({'pet_rule_job'})
class PetRuleJob(Base):
    __tablename__='pet_rule_job'
    __table_args__=(UniqueConstraint('pet_id','business_key',name='uq_pet_rule_job_business'),
        Index('ix_pet_rule_job_health','kind','state','lease_until'),TABLE_OPTIONS)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
    kind:Mapped[str]=mapped_column(String(32),nullable=False)
    business_key:Mapped[str]=mapped_column(String(128),nullable=False)
    covered_until:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
    pet_data_version:Mapped[int]=mapped_column(BigInteger,nullable=False)
    state:Mapped[str]=mapped_column(String(24),default='pending',nullable=False)
    generation:Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    owner:Mapped[str|None]=mapped_column(String(64))
    lease_until:Mapped[datetime|None]=mapped_column(UTC_TIME)
    attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    last_error:Mapped[str|None]=mapped_column(String(64))
    last_success_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
    recorded_at:Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)
