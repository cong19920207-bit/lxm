"""One mutable candidate then frozen return scope for each stable absence."""
from datetime import datetime
from sqlalchemy import String,Integer,ForeignKey,JSON
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS,new_id
PET_RETURN_TABLE_NAMES=frozenset({'pet_return'})
class PetReturn(Base):
 __tablename__='pet_return'
 __table_args__=(TABLE_OPTIONS,)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
 absence_id:Mapped[str]=mapped_column(ForeignKey('pet_absence.id',ondelete='RESTRICT'),unique=True,nullable=False)
 version:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
 coverage_start:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 coverage_end:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 confirmed_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 presented_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 source_ids:Mapped[list]=mapped_column(JSON,default=list,nullable=False)
 growth_ids:Mapped[list]=mapped_column(JSON,default=list,nullable=False)
 highlights:Mapped[list]=mapped_column(JSON,default=list,nullable=False)
 last_snapshot_id:Mapped[str|None]=mapped_column(ForeignKey('pet_snapshot.id',ondelete='RESTRICT'))
 current_event_id:Mapped[str|None]=mapped_column(ForeignKey('pet_fact_event.id',ondelete='RESTRICT'))
 task_id:Mapped[str|None]=mapped_column(ForeignKey('pet_generation_task.id',ondelete='RESTRICT'))
 reused_text_id:Mapped[str|None]=mapped_column(ForeignKey('pet_formal_text.id',ondelete='RESTRICT'))
 reason:Mapped[str|None]=mapped_column(String(96))
